"""
Script repair: fix lokasi_id + biaya + RKAP untuk SPPD completed yang
tujuannya Dalam Kaltim (Samarinda, IKN, dll) tapi ter-import dengan
lokasi_id = Luar Kaltim.

Yang dilakukan per SPPD yang terdeteksi:
  1. Rollback RKAP lama (Luar Kaltim) sebesar total_biaya lama
  2. Recalculate komponen uang saku pakai rule Dalam Kaltim x total_hari
  3. Update sppd: lokasi_id, komponen uang saku, subtotal, total_biaya, rkap_id
     (total_hotel dan total_transport TIDAK diubah — itu biaya riil)
  4. Deduct RKAP baru (Dalam Kaltim) sebesar total_biaya baru

DRY_RUN = True (default) — preview saja, tidak ada perubahan.
Set DRY_RUN = False untuk eksekusi sungguhan.

Jalankan dari folder root:
  python setup/fix_lokasi_sppd_historis.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client
from utils.database import hitung_uang_saku, get_rule_sppd, rollback_rkap, deduct_rkap

load_dotenv()

DRY_RUN = False   # Ganti False untuk eksekusi sungguhan

# ── Konstanta lokasi ──
LOKASI_LUAR  = "99c9f92f-972f-46d5-99d4-219b758d2cb7"  # Luar Kaltim
LOKASI_DALAM = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"  # Dalam Kaltim

# Kota Dalam Kaltim — termasuk IKN yang belum ada di database.py
KOTA_DALAM = {
    "samarinda", "balikpapan", "bontang", "kutai kartanegara",
    "berau", "paser", "penajam paser utara", "mahakam ulu",
    "tenggarong", "sangatta", "tanjung redeb", "tanah grogot",
    "penajam", "long bagun",
    "ikn", "ibu kota nusantara", "nusantara",
}

def fmt_rp(n):
    return f"Rp {int(n or 0):,}".replace(",", ".")

def resolve_kategori_rkap(struktur_rkap, bidang_resolved):
    if struktur_rkap == "MANAJER":
        return "ADM_MANAJER" if bidang_resolved == "Administrasi" else "TEKNIK_MANAJER"
    elif struktur_rkap == "SUPERVISOR":
        return "ADM_SUPERVISOR" if bidang_resolved == "Administrasi" else "TEKNIK_SUPERVISOR"
    elif struktur_rkap == "STAF_PELAKSANA":
        return "ADM_STAF_PELAKSANA" if bidang_resolved == "Administrasi" else "TEKNIK_STAF_PELAKSANA"
    elif struktur_rkap == "DEWAS_ANGGOTA":
        return "DEWAS_ANGGOTA_1"   # legacy fallback
    else:
        return struktur_rkap       # pass-through: DIRUT, DIRUM, DEWAS_ANGGOTA_1, dll.

def main():
    db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    print("=" * 65)
    print(f"FIX LOKASI SPPD HISTORIS  |  DRY_RUN={DRY_RUN}")
    print("=" * 65)

    # ── Load divisi map (untuk resolve bidang lewat parent) ──
    res_div = db.table("divisi").select("id, parent_id, bidang").execute()
    divisi_map = {d["id"]: d for d in (res_div.data or [])}

    # ── Load RKAP 2026 — index by (kategori_jabatan, lokasi_id, bulan) ──
    res_rkap = db.table("rkap").select("*").eq("tahun", 2026).execute()
    rkap_index = {}
    for r in (res_rkap.data or []):
        key = (r["kategori_jabatan"], r["lokasi_id"], r["bulan"])
        rkap_index[key] = r
    print(f"\nRKAP 2026 rows: {len(rkap_index)}")

    # ── Ambil SPPD completed dengan lokasi_id = Luar Kaltim ──
    res = db.table("sppd")\
        .select(
            "id, nomor_sppd, rkap_id, lokasi_id, total_hari, "
            "uang_harian_total, uang_makan_total, transport_lokal_total, "
            "uang_representasi_total, subtotal_uang_saku, "
            "total_transport, total_hotel, total_sewa_kendaraan, biaya_jenazah, total_biaya, "
            "visum_id, "
            "visum(id, tujuan, tanggal_berangkat), "
            "pegawai!sppd_pegawai_id_fkey(id, jabatan_id, jabatan(nama, struktur_rkap), "
            "divisi_id, divisi(id, parent_id, bidang))"
        )\
        .eq("status", "completed")\
        .eq("lokasi_id", LOKASI_LUAR)\
        .execute()

    # Filter: visum tujuan ada di KOTA_DALAM
    affected = []
    for s in (res.data or []):
        visum = s.get("visum") or {}
        tujuan = (visum.get("tujuan") or "").strip().lower()
        if tujuan in KOTA_DALAM:
            affected.append(s)

    print(f"SPPD Luar Kaltim (completed): {len(res.data or [])}")
    print(f"SPPD yang tujuannya Dalam Kaltim (salah lokasi): {len(affected)}\n")

    if not affected:
        print("Tidak ada SPPD yang perlu diperbaiki. Selesai.")
        return

    ok_list   = []
    skip_list = []

    for s in affected:
        peg   = s.get("pegawai") or {}
        visum = s.get("visum") or {}
        jabatan_id = peg.get("jabatan_id")
        div        = peg.get("divisi") or {}

        # Resolve bidang (dari divisi sendiri atau parent)
        bidang = div.get("bidang")
        if not bidang and div.get("parent_id"):
            parent = divisi_map.get(div["parent_id"])
            bidang = parent.get("bidang") if parent else None

        struktur = (peg.get("jabatan") or {}).get("struktur_rkap", "")
        jab_nama = (peg.get("jabatan") or {}).get("nama", "-")
        tgl_b    = visum.get("tanggal_berangkat", "")
        bulan    = int(tgl_b[5:7]) if tgl_b else None

        # Rule tarif Dalam Kaltim
        rule = get_rule_sppd(jabatan_id, LOKASI_DALAM) if jabatan_id else None

        # Kategori RKAP + cari row Dalam Kaltim
        kategori     = resolve_kategori_rkap(struktur, bidang or "")
        new_rkap_row = rkap_index.get((kategori, LOKASI_DALAM, bulan)) if bulan else None
        old_rkap_id  = s.get("rkap_id")
        old_total    = int(s.get("total_biaya") or 0)

        # Hitung uang saku baru (rule Dalam Kaltim x total_hari)
        total_hari = s.get("total_hari") or 0
        if rule and total_hari:
            calc = hitung_uang_saku(rule, total_hari)
            new_subtotal = int(calc["subtotal"])
        else:
            calc         = None
            new_subtotal = int(s.get("subtotal_uang_saku") or 0)

        # Total biaya baru = uang saku baru + hotel + transport + sewa + jenazah
        non_saku = (
            (s.get("total_transport") or 0) +
            (s.get("total_hotel") or 0) +
            (s.get("total_sewa_kendaraan") or 0) +
            (s.get("biaya_jenazah") or 0)
        )
        new_total = new_subtotal + non_saku

        # ── Print info ──
        print("-" * 55)
        print(f"SPPD  : {s['nomor_sppd']}")
        print(f"Tujuan: {visum.get('tujuan','-')} | bln {bulan} | {total_hari} hari")
        print(f"Jabatan: {jab_nama} | struktur: {struktur} | bidang: {bidang}")
        print(f"Kategori RKAP: {kategori}")
        print(f"Rule Dalam Kaltim: {'ditemukan' if rule else '** TIDAK DITEMUKAN **'}")
        print(f"RKAP Dalam Kaltim [{kategori}, bln {bulan}]: {'ditemukan' if new_rkap_row else '** TIDAK DITEMUKAN **'}")
        old_saku = int(s.get("subtotal_uang_saku") or 0)
        print(f"Uang saku : {fmt_rp(old_saku)}  ->  {fmt_rp(new_subtotal)}")
        print(f"Total biaya: {fmt_rp(old_total)}  ->  {fmt_rp(new_total)}")

        if not new_rkap_row:
            print(f"[SKIP] RKAP Dalam Kaltim untuk ({kategori}, bln {bulan}) tidak ada di DB.")
            skip_list.append(s["nomor_sppd"])
            continue

        ok_list.append(s["nomor_sppd"])

        if DRY_RUN:
            print(f"[DRY RUN] Akan dieksekusi:")
            print(f"  - lokasi_id : Luar Kaltim -> Dalam Kaltim")
            print(f"  - rkap_id   : {(old_rkap_id or '-')[:8]}... -> {new_rkap_row['id'][:8]}...")
            print(f"  - Rollback RKAP Luar Kaltim: {fmt_rp(old_total)}")
            print(f"  - Deduct RKAP Dalam Kaltim : {fmt_rp(new_total)}")
            if calc:
                print(f"  - Uang harian: {fmt_rp(s.get('uang_harian_total'))} -> {fmt_rp(calc['uang_harian'])}")
                print(f"  - Uang makan : {fmt_rp(s.get('uang_makan_total'))} -> {fmt_rp(calc['uang_makan'])}")
                print(f"  - Transport lokal: {fmt_rp(s.get('transport_lokal_total'))} -> {fmt_rp(calc['transport_lokal'])}")
            continue

        # ── Eksekusi ──
        # 1. Rollback RKAP lama (Luar Kaltim)
        if old_rkap_id:
            rollback_rkap(old_rkap_id, old_total)
            print(f"  [1] Rollback RKAP lama: {fmt_rp(old_total)}")

        # 2. Update SPPD
        update_data = {
            "lokasi_id": LOKASI_DALAM,
            "rkap_id":   new_rkap_row["id"],
            "subtotal_uang_saku": new_subtotal,
            "total_biaya":        new_total,
        }
        if calc:
            update_data.update({
                "uang_harian_total":       int(calc["uang_harian"]),
                "uang_makan_total":        int(calc["uang_makan"]),
                "transport_lokal_total":   int(calc["transport_lokal"]),
                "uang_representasi_total": int(calc["uang_rep"]),
            })
        db.table("sppd").update(update_data).eq("id", s["id"]).execute()
        print(f"  [2] SPPD diupdate (lokasi, biaya, rkap_id)")

        # 3. Deduct RKAP baru (Dalam Kaltim)
        deduct_rkap(new_rkap_row["id"], new_total)
        print(f"  [3] Deduct RKAP baru: {fmt_rp(new_total)}")

        print(f"  [OK] Selesai.")

    # ── Ringkasan ──
    print("\n" + "=" * 65)
    if DRY_RUN:
        print(f"DRY RUN selesai.")
        print(f"  Siap diproses : {len(ok_list)} SPPD")
        print(f"  Akan diskip   : {len(skip_list)} SPPD (RKAP row tidak ada)")
        if skip_list:
            print(f"  Skip list: {skip_list}")
        print("\nSet DRY_RUN = False untuk eksekusi sungguhan.")
    else:
        print(f"SELESAI.")
        print(f"  Berhasil difix : {len(ok_list)} SPPD")
        print(f"  Diskip         : {len(skip_list)} SPPD")
        if skip_list:
            print(f"  Skip list: {skip_list}")
    print("=" * 65)

if __name__ == "__main__":
    main()
