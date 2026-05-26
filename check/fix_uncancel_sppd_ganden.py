"""
Fix one-time: un-cancel SPPD Ganden Aditera Ismed (Visum 0049, SPD 34).
SPPD tidak sengaja di-cancel dari status pencairan, sehingga:
  - status SPPD berubah ke 'cancelled'
  - RKAP sudah di-rollback otomatis

Fix yang dilakukan:
  1. Ubah status SPPD kembali ke 'pencairan'
  2. Re-deduct RKAP sebesar subtotal_uang_saku (mengembalikan state sebelum cancel)
  3. Update rekap SPD

Jalankan dari root:  python check/fix_uncancel_sppd_ganden.py
Set DRY_RUN = False untuk benar-benar mengubah data.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client, deduct_rkap, update_rekap_spd

DRY_RUN = True   # <-- Set False untuk eksekusi nyata

NAMA_PEGAWAI_PATTERN = "GANDEN"   # partial match (case-insensitive di sisi Python)
NOMOR_VISUM_PATTERN  = "0049"     # visum ke-49
NOMOR_SPD_TARGET     = "34"       # SPD nomor 34

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()

tag = "[DRY RUN]" if DRY_RUN else "[EKSEKUSI]"
print("=" * 70)
print(f"UN-CANCEL SPPD GANDEN ADITERA ISMED  {tag}")
print(f"Visum: {NOMOR_VISUM_PATTERN} | SPD: {NOMOR_SPD_TARGET}")
print("=" * 70)

# 1. Cari visum dengan nomor mengandung "0049"
visum_res = db.table("visum")\
    .select("id, nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali")\
    .like("nomor_visum", f"%{NOMOR_VISUM_PATTERN}%")\
    .execute()

if not visum_res.data:
    print(f"ERROR: Tidak ada visum dengan nomor mengandung '{NOMOR_VISUM_PATTERN}'.")
    sys.exit(1)

if len(visum_res.data) > 1:
    print(f"PERINGATAN: Ditemukan {len(visum_res.data)} visum, memakai yang pertama:")
    for v in visum_res.data:
        print(f"  {v['nomor_visum']} | {v['tujuan']} | {v['tanggal_berangkat']}")
    print()

visum = visum_res.data[0]
print(f"\nVisum    : {visum['nomor_visum']}")
print(f"Tujuan   : {visum['tujuan']}")
print(f"Berangkat: {visum['tanggal_berangkat'][:10]} s/d {visum['tanggal_kembali'][:10]}")

# 2. Cari SPPD yang cancelled untuk pegawai Ganden di visum ini
sppd_res = db.table("sppd")\
    .select(
        "id, status, rkap_id, spd_id,"
        " subtotal_uang_saku, total_biaya, total_hari,"
        " pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama)),"
        " rkap(bulan, tahun, kategori_jabatan, anggaran_terpakai, anggaran_sisa)"
    )\
    .eq("visum_id", visum["id"])\
    .eq("status", "cancelled")\
    .execute()

if not sppd_res.data:
    print(f"\nTidak ada SPPD berstatus 'cancelled' pada visum ini.")
    sys.exit(1)

# Filter nama pegawai mengandung GANDEN
target_list = [
    s for s in sppd_res.data
    if NAMA_PEGAWAI_PATTERN.upper() in
       (s.get("pegawai") or {}).get("nama", "").upper()
]

if not target_list:
    print(f"\nTidak ada SPPD cancelled untuk pegawai '{NAMA_PEGAWAI_PATTERN}'.")
    print("SPPD cancelled yang ditemukan:")
    for s in sppd_res.data:
        nama = (s.get("pegawai") or {}).get("nama", "?")
        print(f"  {nama}")
    sys.exit(1)

if len(target_list) > 1:
    print(f"\nPERINGATAN: Ditemukan {len(target_list)} SPPD cancelled untuk '{NAMA_PEGAWAI_PATTERN}'.")
    print("Script hanya memproses SPPD pertama.")

sppd = target_list[0]
nama    = (sppd.get("pegawai") or {}).get("nama", "?")
jabatan = ((sppd.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
rkap    = sppd.get("rkap") or {}
rkap_id = sppd.get("rkap_id")
uang_saku = sppd.get("subtotal_uang_saku") or 0

print(f"\n{'─'*70}")
print(f"SPPD ID  : {sppd['id']}")
print(f"Pegawai  : {nama}")
print(f"Jabatan  : {jabatan}")
print(f"Status   : {sppd['status'].upper()}")
print(f"Total Hari: {sppd.get('total_hari')}")
print(f"Uang Saku : {fmt_rp(uang_saku)}")
print(f"Total Biaya: {fmt_rp(sppd.get('total_biaya'))}")

if rkap_id:
    print(f"\nRKAP ID  : {rkap_id}")
    print(f"Kategori : {rkap.get('kategori_jabatan')} | Bln {rkap.get('bulan')} {rkap.get('tahun')}")
    print(f"Terpakai : {fmt_rp(rkap.get('anggaran_terpakai'))}")
    print(f"Sisa     : {fmt_rp(rkap.get('anggaran_sisa'))}")
else:
    print(f"\n[PERINGATAN] rkap_id = NULL — tidak ada RKAP yang akan di-deduct.")

print(f"\nRencana fix:")
print(f"  1. Ubah status: cancelled --> pencairan")
if rkap_id:
    print(f"  2. Re-deduct RKAP sebesar {fmt_rp(uang_saku)}")
    print(f"       terpakai: {fmt_rp(rkap.get('anggaran_terpakai'))} --> "
          f"{fmt_rp((rkap.get('anggaran_terpakai') or 0) + uang_saku)}")
    print(f"       sisa    : {fmt_rp(rkap.get('anggaran_sisa'))} --> "
          f"{fmt_rp((rkap.get('anggaran_sisa') or 0) - uang_saku)}")
if sppd.get("spd_id"):
    print(f"  3. Update rekap SPD {NOMOR_SPD_TARGET}")

if DRY_RUN:
    print(f"\n[DRY RUN] Tidak ada yang diubah. Set DRY_RUN = False untuk eksekusi.")
else:
    # Ubah status SPPD ke pencairan
    db.table("sppd")\
        .update({"status": "pencairan"})\
        .eq("id", sppd["id"])\
        .execute()
    print(f"\n  [OK] Status SPPD diubah ke 'pencairan'.")

    # Re-deduct RKAP
    if rkap_id and uang_saku > 0:
        ok = deduct_rkap(rkap_id, uang_saku)
        print(f"  {'[OK]' if ok else '[GAGAL]'} Re-deduct RKAP {fmt_rp(uang_saku)}.")
    elif not rkap_id:
        print(f"  [SKIP] Tidak ada rkap_id — RKAP tidak diubah.")

    # Update rekap SPD
    if sppd.get("spd_id"):
        update_rekap_spd(sppd["spd_id"])
        print(f"  [OK] Rekap SPD diperbarui.")

print()
print("=" * 70)
if DRY_RUN:
    print("[DRY RUN] Selesai. Set DRY_RUN = False lalu jalankan ulang.")
else:
    print("[OK] Fix selesai. Cek Tab 2 SPPD untuk verifikasi.")
print("=" * 70)
