"""
Script sekali pakai: assign rkap_id ke 3 SPPD tamu yang rkap_id-nya NULL.

Root cause: get_rkap_id pakai lokasi_id SPPD (Luar Kaltim = 99c9f92f-...)
tapi RKAP bantuan_sppd pakai lokasi_id Dalam Kaltim (6f7a80e0-...) sebagai bucket.

Jalankan dari folder root: python check/fix_rkap_null_tamu.py

DRY_RUN = True  -> preview saja
DRY_RUN = False -> update DB
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client
from utils.database import deduct_rkap, LOKASI_BANTUAN_ID

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

DRY_RUN = True

def fmt_rp(n):
    return f"Rp {int(n or 0):,}".replace(",", ".")

print("=" * 60)
print(f"FIX RKAP_ID NULL TAMU | DRY_RUN={DRY_RUN}")
print("=" * 60)

# Ambil semua SPPD dengan rkap_id NULL (non-cancelled)
res = db.table("sppd")\
    .select(
        "id, status, lokasi_id, total_biaya, visum_id, "
        "visum(tanggal_berangkat, nomor_visum), "
        "pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama, struktur_rkap))"
    )\
    .is_("rkap_id", "null")\
    .neq("status", "cancelled")\
    .execute()

sppd_list = res.data or []
print(f"\nTotal SPPD rkap_id NULL: {len(sppd_list)}\n")

for s in sppd_list:
    peg   = (s.get("pegawai") or {}).get("nama", "?")
    jab   = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
    struk = ((s.get("pegawai") or {}).get("jabatan") or {}).get("struktur_rkap", "")
    visum = s.get("visum") or {}
    tgl   = visum.get("tanggal_berangkat", "")

    print(f"  {peg} ({jab})")
    print(f"    Visum  : {visum.get('nomor_visum', '-')}")
    print(f"    Status : {s['status']}")
    print(f"    Total  : {fmt_rp(s.get('total_biaya'))}")

    # Tentukan kategori & rkap_lokasi_id
    if struk == "BANTUAN":
        kategori       = "bantuan_sppd"
        rkap_lokasi_id = LOKASI_BANTUAN_ID
    else:
        print(f"    [!] struktur_rkap='{struk}' bukan BANTUAN, skip.")
        print()
        continue

    if not tgl:
        print(f"    [!] tanggal_berangkat kosong, skip.")
        print()
        continue

    bulan = int(tgl[5:7])
    tahun = int(tgl[:4])

    # Cari rkap row
    res_rkap = db.table("rkap")\
        .select("id, anggaran_awal, anggaran_sisa")\
        .eq("kategori_jabatan", kategori)\
        .eq("lokasi_id", rkap_lokasi_id)\
        .eq("bulan", bulan)\
        .eq("tahun", tahun)\
        .execute()

    if not res_rkap.data:
        print(f"    [!] RKAP row tidak ditemukan untuk {kategori} bulan={bulan} tahun={tahun}, skip.")
        print()
        continue

    rkap = res_rkap.data[0]
    print(f"    RKAP   : {kategori} bulan={bulan} | anggaran={fmt_rp(rkap['anggaran_awal'])} sisa={fmt_rp(rkap['anggaran_sisa'])}")
    print(f"    -> Set rkap_id = {rkap['id']}")

    if s["status"] != "draft":
        print(f"    -> Deduct RKAP {fmt_rp(s['total_biaya'])} (status={s['status']})")

    if not DRY_RUN:
        db.table("sppd").update({"rkap_id": rkap["id"]}).eq("id", s["id"]).execute()
        print(f"    [OK] rkap_id diupdate.")

        if s["status"] != "draft":
            deduct_rkap(rkap["id"], int(s["total_biaya"] or 0))
            print(f"    [OK] RKAP dideduct {fmt_rp(s['total_biaya'])}.")
    else:
        print(f"    [DRY] tidak ada perubahan.")

    print()

print("=" * 60)
if DRY_RUN:
    print("DRY_RUN selesai. Set DRY_RUN=False untuk eksekusi.")
else:
    print("Selesai.")
