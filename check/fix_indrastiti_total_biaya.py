"""
Fix one-time: total_biaya INDRASTITI kehilangan transport Rp 2.977.000 setelah
  fix_sppd_realisasi.py dijalankan saat koreksi tarif staf → spv.

Kondisi sekarang:
  total_biaya  = Rp 6.400.000 (saku + hotel, tanpa transport)
  total_transport = Rp 2.977.000 (sudah benar di DB)
  RKAP sudah terdeduct Rp 2.977.000 transport (sudah benar)

Fix: update total_biaya = subtotal_uang_saku + total_hotel + total_transport
     → Rp 3.100.000 + Rp 3.300.000 + Rp 2.977.000 = Rp 9.377.000
     RKAP tidak perlu diubah (sudah benar).

Jalankan dari root:  python check/fix_indrastiti_total_biaya.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client, update_rekap_spd

DRY_RUN = True   # Set False untuk benar-benar update DB

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()

RKAP_ID_BANTUAN_MARET = "42f4f7ec-a833-4cca-9710-ae753979858e"

print("=" * 65)
print("FIX: total_biaya INDRASTITI (hilang transport setelah koreksi tarif)")
print("=" * 65)

# Cari SPPD INDRASTITI yang bermasalah
res = db.table("sppd")\
    .select(
        "id, status, subtotal_uang_saku, total_hotel, total_transport, total_biaya, spd_id,"
        " pegawai!sppd_pegawai_id_fkey(nama),"
        " visum(nomor_visum, tujuan)"
    )\
    .eq("rkap_id", RKAP_ID_BANTUAN_MARET)\
    .eq("status", "realisasi")\
    .execute()

candidates = res.data or []

# Filter: cari SPPD yang total_biaya-nya tidak termasuk total_transport
masalah = []
for s in candidates:
    saku      = s.get("subtotal_uang_saku") or 0
    hotel     = s.get("total_hotel") or 0
    transport = s.get("total_transport") or 0
    total     = s.get("total_biaya") or 0
    expected  = saku + hotel + transport
    if total != expected and transport > 0:
        masalah.append((s, expected))

if not masalah:
    print("\n✅ Tidak ada SPPD bermasalah ditemukan (total_biaya sudah benar).")
    sys.exit()

for s, expected in masalah:
    nama  = (s.get("pegawai") or {}).get("nama", "?")
    visum = s.get("visum") or {}
    saku      = s.get("subtotal_uang_saku") or 0
    hotel     = s.get("total_hotel") or 0
    transport = s.get("total_transport") or 0
    total_lama = s.get("total_biaya") or 0

    print(f"\nSPPD     : {s['id']}")
    print(f"Pegawai  : {nama}")
    print(f"Visum    : {visum.get('nomor_visum','-')} | {visum.get('tujuan','-')}")
    print(f"Status   : {s['status'].upper()}")
    print()
    print(f"  Uang Saku     : {fmt_rp(saku)}")
    print(f"  Total Hotel   : {fmt_rp(hotel)}")
    print(f"  Total Transport: {fmt_rp(transport)}")
    print(f"  Total Biaya (lama): {fmt_rp(total_lama)}  ← salah, transport tidak terhitung")
    print(f"  Total Biaya (baru): {fmt_rp(expected)}  ← benar")
    print(f"  Selisih       : +{fmt_rp(expected - total_lama)}")
    print()
    print(f"  RKAP: tidak perlu diubah (transport sudah terdeduct dengan benar)")

    if dry_run := DRY_RUN:
        print(f"\n  ⚠️  DRY RUN — tidak ada yang diubah.")
        print(f"       Set DRY_RUN = False untuk eksekusi.")
    else:
        db.table("sppd").update({
            "total_biaya": expected
        }).eq("id", s["id"]).execute()
        print(f"  ✅ total_biaya diupdate: {fmt_rp(total_lama)} → {fmt_rp(expected)}")

        if s.get("spd_id"):
            update_rekap_spd(s["spd_id"])
            print(f"  ✅ Rekap SPD diperbarui.")

print()
print("=" * 65)
print("Selesai.")
