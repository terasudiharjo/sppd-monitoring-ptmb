"""
Fix: SPPD Dewas (Ketua/1/2) untuk Visum 0055 (Samarinda) ter-deduct ke RKAP
Luar Kaltim, padahal seharusnya Dalam Kaltim.

Penyebab: saat tujuan visum diubah ke "Samarinda" (Dalam Kaltim), SPPD masih
berstatus draft — update_tujuan_visum tidak memperbarui rkap_id untuk draft
(tidak ada rollback/deduct karena draft belum deduct). Akibatnya rkap_id tetap
mengarah ke Luar Kaltim lama, dan saat pencairan deduct ke lokasi yang salah.

Kondisi saat ini:
  - sppd.lokasi_id  = Dalam Kaltim  ← sudah benar
  - sppd.rkap_id    = Luar Kaltim Mei ← SALAH
  - uang saku sudah dihitung dengan tarif Dalam Kaltim

Fix yang dilakukan per SPPD:
  1. rollback_rkap dari Luar Kaltim
  2. deduct_rkap ke Dalam Kaltim (total_biaya yang sama)
  3. update sppd.rkap_id ke baris Dalam Kaltim yang benar

Jalankan dari root:
    $env:PYTHONIOENCODING="utf-8"; python -u check/fix_dewas_rkap_visum0055.py

Set DRY_RUN = False untuk eksekusi nyata.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client, deduct_rkap, rollback_rkap

DRY_RUN = True   # ← ganti False untuk eksekusi

LOKASI_DALAM = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"
LOKASI_LUAR  = "99c9f92f-972f-46d5-99d4-219b758d2cb7"

BULAN_LABEL = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",
               7:"Jul",8:"Agt",9:"Sep",10:"Okt",11:"Nov",12:"Des"}

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()

print("=" * 70)
print(f"FIX DEWAS RKAP — Visum 0055 Samarinda ({'DRY RUN' if DRY_RUN else '🔴 EKSEKUSI NYATA'})")
print("=" * 70)

# ── 1. Temukan Visum 0055 ─────────────────────────────────────────────────
visum_res = db.table("visum").select("id, nomor_visum, tujuan, tanggal_berangkat")\
    .ilike("nomor_visum", "0055/%").execute()
visum_rows = visum_res.data or []

if not visum_rows:
    print("Visum 0055 tidak ditemukan!")
    sys.exit(1)

visum = visum_rows[0]
visum_id  = visum["id"]
tgl_berangkat = visum["tanggal_berangkat"]
bulan = int(tgl_berangkat[5:7])
tahun = int(tgl_berangkat[:4])

print(f"\nVisum  : {visum['nomor_visum']}")
print(f"Tujuan : {visum['tujuan']}")
print(f"Tanggal: {tgl_berangkat}  (bulan={BULAN_LABEL[bulan]}, tahun={tahun})")
print()

# ── 2. Ambil SPPD Dewas untuk visum ini (lokasi=Dalam Kaltim) ────────────
sppd_res = db.table("sppd")\
    .select("id, status, rkap_id, lokasi_id, subtotal_uang_saku, total_biaya,"
            " pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama, struktur_rkap))")\
    .eq("visum_id", visum_id)\
    .eq("lokasi_id", LOKASI_DALAM)\
    .neq("status", "cancelled")\
    .execute()

sppd_list = sppd_res.data or []

if not sppd_list:
    print("Tidak ada SPPD Dalam Kaltim aktif untuk visum ini.")
    sys.exit(0)

# ── 3. Validasi & siapkan daftar fix ─────────────────────────────────────
print(f"{'─'*70}")
print(f"SPPD yang dicek ({len(sppd_list)} record):")
print(f"{'─'*70}")

fixes = []
for s in sppd_list:
    peg = (s.get("pegawai!sppd_pegawai_id_fkey") or s.get("pegawai") or {})
    jab = peg.get("jabatan") or {}
    nama     = peg.get("nama", "?")
    struktur = jab.get("struktur_rkap", "")
    rkap_id_lama = s.get("rkap_id")
    total_biaya  = s.get("total_biaya") or 0

    if not rkap_id_lama:
        print(f"  ⚠️  {nama} — rkap_id NULL, skip (tidak ada deduct ke mana pun)")
        continue

    # Cek rkap lama apakah memang mengarah ke Luar Kaltim
    rkap_lama_res = db.table("rkap").select("kategori_jabatan, lokasi_id, bulan, anggaran_terpakai")\
        .eq("id", rkap_id_lama).single().execute()
    if not rkap_lama_res.data:
        print(f"  ⚠️  {nama} — rkap_id lama tidak ada di tabel rkap, skip")
        continue
    rkap_lama = rkap_lama_res.data

    if rkap_lama["lokasi_id"] == LOKASI_DALAM:
        print(f"  ✅ {nama} — rkap_id sudah benar (Dalam Kaltim), skip")
        continue

    # Cari baris RKAP yang benar (kategori sama, bulan sama, Dalam Kaltim)
    rkap_baru_res = db.table("rkap")\
        .select("id, kategori_jabatan, anggaran_awal, anggaran_sisa")\
        .eq("kategori_jabatan", struktur)\
        .eq("lokasi_id", LOKASI_DALAM)\
        .eq("bulan", bulan)\
        .eq("tahun", tahun)\
        .maybe_single().execute()

    if not rkap_baru_res.data:
        print(f"  ❌ {nama} — baris RKAP {struktur}|Dalam|{BULAN_LABEL[bulan]} tidak ditemukan, SKIP")
        continue

    rkap_baru = rkap_baru_res.data
    print(f"\n  {nama}  [{jab.get('nama','?')}]")
    print(f"    Status      : {s['status'].upper()}")
    print(f"    Total biaya : {fmt_rp(total_biaya)}")
    print(f"    Dari  : {rkap_lama['kategori_jabatan']} | Luar Kaltim | {BULAN_LABEL[rkap_lama['bulan']]}  "
          f"(terpakai kini={fmt_rp(rkap_lama['anggaran_terpakai'])})")
    print(f"    Ke    : {rkap_baru['kategori_jabatan']} | Dalam Kaltim | {BULAN_LABEL[bulan]}  "
          f"(sisa kini={fmt_rp(rkap_baru['anggaran_sisa'])})")

    fixes.append({
        "sppd_id":      s["id"],
        "nama":         nama,
        "total":        total_biaya,
        "rkap_id_lama": rkap_id_lama,
        "rkap_id_baru": rkap_baru["id"],
    })

# ── 4. Eksekusi ───────────────────────────────────────────────────────────
print()
print("─" * 70)
if not fixes:
    print("Tidak ada SPPD yang perlu difix.")
    sys.exit(0)

print(f"Total SPPD yang akan difix: {len(fixes)}")
print()

if DRY_RUN:
    print("⚠️  DRY RUN — tidak ada perubahan. Set DRY_RUN = False untuk eksekusi.")
else:
    print("🔴 EKSEKUSI dimulai...")
    ok = 0
    for fix in fixes:
        try:
            rollback_rkap(fix["rkap_id_lama"], fix["total"])
            deduct_rkap(fix["rkap_id_baru"], fix["total"])
            db.table("sppd").update({"rkap_id": fix["rkap_id_baru"]}).eq("id", fix["sppd_id"]).execute()
            print(f"  ✅ {fix['nama']} — {fmt_rp(fix['total'])} dipindah Luar→Dalam Kaltim")
            ok += 1
        except Exception as e:
            print(f"  ❌ {fix['nama']} — ERROR: {e}")
    print()
    print(f"Selesai: {ok}/{len(fixes)} SPPD berhasil difix.")

print("=" * 70)
