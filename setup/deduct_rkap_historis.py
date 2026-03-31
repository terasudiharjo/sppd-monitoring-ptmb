"""
Script satu kali: update RKAP berdasarkan sppd historis yang sudah di-import.
Jalankan SETELAH import_realisasi_2026.py berhasil.

Yang dilakukan:
  - Cari semua sppd status=completed, rkap_id IS NULL
  - Resolve kategori RKAP via jabatan + bidang
  - Update rkap.anggaran_terpakai & anggaran_sisa
  - Set sppd.rkap_id agar konsisten

Jalankan dari folder root:  python setup/deduct_rkap_historis.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DRY_RUN = True  # Ganti False untuk sungguhan

def get_db():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def resolve_kategori_rkap(struktur_rkap, bidang_resolved):
    if struktur_rkap == "MANAJER":
        return "ADM_MANAJER" if bidang_resolved == "Administrasi" else "TEKNIK_MANAJER"
    elif struktur_rkap == "SUPERVISOR":
        return "ADM_SUPERVISOR" if bidang_resolved == "Administrasi" else "TEKNIK_SUPERVISOR"
    elif struktur_rkap == "STAF_PELAKSANA":
        return "ADM_STAF_PELAKSANA" if bidang_resolved == "Administrasi" else "TEKNIK_STAF_PELAKSANA"
    elif struktur_rkap == "DEWAS_ANGGOTA":
        return "DEWAS_ANGGOTA_1"
    else:
        return struktur_rkap

def main():
    print("=" * 60)
    print(f"DEDUCT RKAP HISTORIS | DRY_RUN={DRY_RUN}")
    print("=" * 60)

    db = get_db()

    # ── Load lookup tables ──
    print("\n[1] Load data lookup...")

    # Divisi (untuk resolve bidang)
    res_div = db.table("divisi").select("id, nama, parent_id, bidang").execute()
    divisi_map = {d["id"]: d for d in res_div.data}

    # Pegawai (aktif) dengan jabatan
    res_peg = db.table("pegawai")\
        .select("id, divisi_id, divisi(id, nama, parent_id, bidang), jabatan(nama, struktur_rkap)")\
        .eq("status", "aktif")\
        .execute()

    pegawai_info = {}
    for p in res_peg.data:
        div = p.get("divisi")
        bidang = None
        if div:
            if div.get("bidang"):
                bidang = div["bidang"]
            elif div.get("parent_id"):
                parent = divisi_map.get(div["parent_id"])
                bidang = parent["bidang"] if parent else None
        pegawai_info[p["id"]] = {
            "struktur_rkap": p["jabatan"]["struktur_rkap"] if p.get("jabatan") else None,
            "bidang": bidang,
        }

    # RKAP rows (tahun 2026) → index by (kategori_jabatan, lokasi_id, bulan)
    res_rkap = db.table("rkap").select("*").eq("tahun", 2026).execute()
    rkap_index = {}
    for r in res_rkap.data:
        key = (r["kategori_jabatan"], r["lokasi_id"], r["bulan"])
        rkap_index[key] = r

    print(f"  Pegawai: {len(pegawai_info)} | RKAP rows: {len(rkap_index)}")

    # ── Ambil sppd yang perlu di-deduct (rkap_id IS NULL, status completed) ──
    print("\n[2] Ambil sppd historis tanpa rkap_id...")
    res_sppd = db.table("sppd")\
        .select("id, pegawai_id, lokasi_id, total_biaya, visum_id, nomor_sppd")\
        .eq("status", "completed")\
        .is_("rkap_id", "null")\
        .execute()

    sppd_list = res_sppd.data
    print(f"  Ditemukan: {len(sppd_list)} sppd")

    if not sppd_list:
        print("  Tidak ada yang perlu di-deduct.")
        return

    # Ambil visum untuk tahu tanggal (bulan)
    visum_ids = list(set(s["visum_id"] for s in sppd_list if s["visum_id"]))
    res_visum = db.table("visum").select("id, tanggal_berangkat").in_("id", visum_ids).execute()
    visum_bulan = {}
    for v in res_visum.data:
        tgl = v["tanggal_berangkat"]
        if tgl:
            bulan = int(tgl[5:7])  # "2026-01-05" → 1
            visum_bulan[v["id"]] = bulan

    # ── Proses tiap sppd ──
    print("\n[3] Proses deduct RKAP...")
    ok = 0
    skip = 0
    errors = []

    # Kumpulkan update per rkap_id (supaya tidak update satu-satu)
    rkap_updates = {}  # rkap_id → total tambahan
    sppd_rkap_map = {}  # sppd_id → rkap_id

    for s in sppd_list:
        peg = pegawai_info.get(s["pegawai_id"])
        if not peg:
            errors.append(f"sppd {s['nomor_sppd']}: pegawai_id {s['pegawai_id']} tidak ditemukan")
            skip += 1
            continue

        struktur = peg["struktur_rkap"]
        bidang   = peg["bidang"]
        if not struktur:
            errors.append(f"sppd {s['nomor_sppd']}: pegawai tidak punya struktur_rkap")
            skip += 1
            continue

        kategori = resolve_kategori_rkap(struktur, bidang)
        lokasi_id = s["lokasi_id"]
        bulan = visum_bulan.get(s["visum_id"])
        if not bulan:
            errors.append(f"sppd {s['nomor_sppd']}: visum tidak ada tanggal")
            skip += 1
            continue

        key = (kategori, lokasi_id, bulan)
        rkap_row = rkap_index.get(key)
        if not rkap_row:
            errors.append(f"sppd {s['nomor_sppd']}: RKAP row tidak ada untuk ({kategori}, lokasi={lokasi_id[:8]}..., bulan={bulan})")
            skip += 1
            continue

        rkap_id = rkap_row["id"]
        total   = s["total_biaya"] or 0

        rkap_updates[rkap_id] = rkap_updates.get(rkap_id, 0) + total
        sppd_rkap_map[s["id"]] = rkap_id

        print(f"  [OK] {s['nomor_sppd']} | {kategori} | bln {bulan} | +Rp {total:,}")
        ok += 1

    print(f"\n  Siap deduct: {ok} sppd ke {len(rkap_updates)} RKAP row")
    print(f"  Skip: {skip}")

    if errors:
        print(f"\n  PERINGATAN ({len(errors)}):")
        for e in errors:
            print(f"    - {e}")

    if DRY_RUN:
        print("\n[i] DRY RUN — tidak ada yang diupdate.")
        print("Ganti DRY_RUN = False untuk eksekusi sungguhan.")
        return

    # ── Eksekusi update RKAP ──
    print("\n[4] Update RKAP...")
    for rkap_id, tambahan in rkap_updates.items():
        row = db.table("rkap").select("anggaran_terpakai, anggaran_sisa").eq("id", rkap_id).single().execute()
        if not row.data:
            print(f"  [X] rkap_id {rkap_id} tidak ditemukan")
            continue
        baru_terpakai = row.data["anggaran_terpakai"] + tambahan
        baru_sisa     = row.data["anggaran_sisa"] - tambahan
        db.table("rkap").update({
            "anggaran_terpakai": baru_terpakai,
            "anggaran_sisa":     baru_sisa,
        }).eq("id", rkap_id).execute()
        print(f"  [OK] rkap {rkap_id[:8]}... +Rp {tambahan:,} terpakai")

    # ── Update sppd.rkap_id ──
    print("\n[5] Update sppd.rkap_id...")
    for sppd_id, rkap_id in sppd_rkap_map.items():
        db.table("sppd").update({"rkap_id": rkap_id}).eq("id", sppd_id).execute()

    print(f"\n  {len(sppd_rkap_map)} sppd.rkap_id diupdate")

    print("\n" + "=" * 60)
    print(f"SELESAI. {ok} sppd di-deduct ke RKAP.")
    print("=" * 60)

if __name__ == "__main__":
    main()
