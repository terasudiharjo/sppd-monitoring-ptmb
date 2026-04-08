"""
Script hapus 1 visum duplikat (Bali, April 2026 - nomor 0025).

Terjadi karena bug penomoran COUNT vs MAX sebelum diperbaiki.
Hapus urut child -> parent:
  sppd_biaya_lain -> sppd_trip_detail -> sppd -> spd -> visum

Jalankan dari folder root:  python setup/delete_visum_bali.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DRY_RUN = False  # Ganti False untuk eksekusi sungguhan

db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Nomor visum yang ingin dihapus — April (bulan IV), bukan historis Maret (bulan III)
TARGET_NOMOR = "0025/1421002/10a-I/IV/2026-J"

print("=" * 60)
print("DELETE VISUM DUPLIKAT BALI")
print(f"Target : {TARGET_NOMOR}")
print(f"Mode   : {'DRY RUN' if DRY_RUN else '!!! EKSEKUSI SUNGGUHAN !!!'}")
print("=" * 60)

# 1. Cari visum
res = db.table("visum").select("id, nomor_visum, tujuan, status, tanggal_berangkat")\
    .eq("nomor_visum", TARGET_NOMOR).execute()

if not res.data:
    print(f"\n[!] Visum '{TARGET_NOMOR}' TIDAK DITEMUKAN di DB.")
    print("    Mungkin sudah dihapus, atau nomor tidak cocok.")
    sys.exit(0)

visum = res.data[0]
visum_id = visum["id"]
print(f"\nVisum ditemukan:")
print(f"  ID      : {visum_id}")
print(f"  Nomor   : {visum['nomor_visum']}")
print(f"  Tujuan  : {visum['tujuan']}")
print(f"  Tgl     : {visum['tanggal_berangkat']}")
print(f"  Status  : {visum['status']}")

# 2. Cari SPD
res_spd = db.table("spd").select("id, nomor_spd").eq("visum_id", visum_id).execute()
spd_ids = [s["id"] for s in res_spd.data]
print(f"\nSPD ditemukan: {len(spd_ids)}")
for s in res_spd.data:
    print(f"  {s['nomor_spd']} (id: {s['id']})")

# 3. Cari SPPD
sppd_ids = []
if spd_ids:
    res_sppd = db.table("sppd").select("id, status")\
        .in_("spd_id", spd_ids).execute()
    sppd_ids = [s["id"] for s in res_sppd.data]
    print(f"\nSPPD ditemukan: {len(sppd_ids)}")
    for s in res_sppd.data:
        print(f"  id={s['id']} status={s['status']}")

# 4. Cari sppd_biaya_lain & sppd_trip_detail
biaya_lain_ids = []
trip_ids = []
if sppd_ids:
    res_bl = db.table("sppd_biaya_lain").select("id").in_("sppd_id", sppd_ids).execute()
    biaya_lain_ids = [r["id"] for r in res_bl.data]
    res_tr = db.table("sppd_trip_detail").select("id").in_("sppd_id", sppd_ids).execute()
    trip_ids = [r["id"] for r in res_tr.data]
    print(f"\nsppd_biaya_lain : {len(biaya_lain_ids)} record")
    print(f"sppd_trip_detail: {len(trip_ids)} record")

print("\n" + "-" * 60)
print("Yang akan dihapus:")
print(f"  {len(biaya_lain_ids)} sppd_biaya_lain")
print(f"  {len(trip_ids)} sppd_trip_detail")
print(f"  {len(sppd_ids)} sppd")
print(f"  {len(spd_ids)} spd")
print(f"  1 visum  ({TARGET_NOMOR})")
print("-" * 60)

if DRY_RUN:
    print("\n[DRY RUN] Tidak ada yang dihapus. Ganti DRY_RUN = False untuk eksekusi.")
    sys.exit(0)

# ── EKSEKUSI ──
print("\nMulai hapus...")

if biaya_lain_ids:
    db.table("sppd_biaya_lain").delete().in_("id", biaya_lain_ids).execute()
    print(f"  [OK] {len(biaya_lain_ids)} sppd_biaya_lain dihapus")

if trip_ids:
    db.table("sppd_trip_detail").delete().in_("id", trip_ids).execute()
    print(f"  [OK] {len(trip_ids)} sppd_trip_detail dihapus")

if sppd_ids:
    db.table("sppd").delete().in_("id", sppd_ids).execute()
    print(f"  [OK] {len(sppd_ids)} sppd dihapus")

if spd_ids:
    db.table("spd").delete().in_("id", spd_ids).execute()
    print(f"  [OK] {len(spd_ids)} spd dihapus")

db.table("visum").delete().eq("id", visum_id).execute()
print(f"  [OK] Visum '{TARGET_NOMOR}' dihapus")

print("\n[SELESAI] Visum duplikat Bali berhasil dihapus.")
print("Visum berikutnya yang dibuat via UI akan dapat nomor 0026.")
