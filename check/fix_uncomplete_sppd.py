"""
Fix: Un-complete SPPD yang tidak sengaja ter-complete.
Ubah status 'completed' kembali ke 'realisasi'.
Tidak ada RKAP yang disentuh — aman, murni ganti status saja.

Jalankan dari root:  python check/fix_uncomplete_sppd.py
Set DRY_RUN = False untuk benar-benar mengubah data.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client

DRY_RUN = True   # <-- Set False untuk eksekusi nyata

NAMA_PEGAWAI_PATTERN = "YUNIATI"   # partial match, case-insensitive di sisi Python

db = get_client()

tag = "[DRY RUN]" if DRY_RUN else "[EKSEKUSI]"
print("=" * 70)
print(f"UN-COMPLETE SPPD  {tag}")
print(f"Cari pegawai mengandung: '{NAMA_PEGAWAI_PATTERN}'")
print("=" * 70)

# Cari semua SPPD completed, join ke pegawai untuk filter nama
res = db.table("sppd")\
    .select(
        "id, status, total_biaya, total_hari, visum_id,"
        " pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama)),"
        " visum(nomor_visum, tujuan, tanggal_berangkat)"
    )\
    .eq("status", "completed")\
    .execute()

if not res.data:
    print("Tidak ada SPPD berstatus 'completed'.")
    sys.exit(0)

# Filter nama
target_list = [
    s for s in res.data
    if NAMA_PEGAWAI_PATTERN.upper() in
       (s.get("pegawai") or {}).get("nama", "").upper()
]

if not target_list:
    print(f"\nTidak ada SPPD completed untuk pegawai '{NAMA_PEGAWAI_PATTERN}'.")
    print("\nSemua SPPD completed yang ada:")
    for s in res.data:
        nama = (s.get("pegawai") or {}).get("nama", "?")
        v    = s.get("visum") or {}
        print(f"  {nama:40s} | {v.get('nomor_visum','?')} | {v.get('tujuan','?')}")
    sys.exit(1)

print(f"\nDitemukan {len(target_list)} SPPD completed untuk '{NAMA_PEGAWAI_PATTERN}':\n")
for s in target_list:
    nama    = (s.get("pegawai") or {}).get("nama", "?")
    jabatan = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
    v       = s.get("visum") or {}
    biaya   = s.get("total_biaya") or 0
    print(f"  SPPD ID  : {s['id']}")
    print(f"  Pegawai  : {nama}  ({jabatan})")
    print(f"  Visum    : {v.get('nomor_visum','?')} | {v.get('tujuan','?')} | {v.get('tanggal_berangkat','?')[:10]}")
    print(f"  Total Hari: {s.get('total_hari')}  |  Total Biaya: Rp {biaya:,}".replace(",","."))
    print(f"  Rencana  : completed --> realisasi  (RKAP tidak disentuh)")
    print()

if len(target_list) > 1:
    print("PERINGATAN: Lebih dari 1 SPPD ditemukan. Script akan memproses SEMUA di atas.")
    print("Pastikan semua memang perlu di-un-complete.\n")

if DRY_RUN:
    print("[DRY RUN] Tidak ada yang diubah. Set DRY_RUN = False untuk eksekusi.")
else:
    for s in target_list:
        db.table("sppd").update({"status": "realisasi"}).eq("id", s["id"]).execute()
        nama = (s.get("pegawai") or {}).get("nama", "?")
        print(f"  [OK] {nama} → status diubah ke 'realisasi'.")

print()
print("=" * 70)
if DRY_RUN:
    print("[DRY RUN] Selesai. Set DRY_RUN = False lalu jalankan ulang.")
else:
    print("[OK] Selesai. Cek Tab 2 SPPD untuk verifikasi.")
print("=" * 70)
