"""
Investigasi selisih RKAP bantuan_sppd Maret 2026 (Dalam Kaltim).

RKAP terpakai : Rp 26.829.000
SPPD aktif    : Rp 23.852.000
Selisih       : Rp  2.977.000  ← tidak ada yang cover ini

Script ini:
1. Ambil rkap_id untuk bantuan_sppd Maret Dalam Kaltim
2. Tampilkan SEMUA SPPD yang pernah referensi rkap_id ini (aktif + cancelled)
3. Hitung total yang di-deduct dan yang sudah di-rollback
4. Identifikasi sumber selisih

Jalankan dari root:  python check/investigasi_bantuan_maret.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client

TAHUN           = 2026
BULAN           = 3
KATEGORI        = "bantuan_sppd"
LOKASI_DALAM_ID = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()

print("=" * 70)
print(f"INVESTIGASI: {KATEGORI} | Maret {TAHUN} | Dalam Kaltim")
print("=" * 70)

# 1. Ambil RKAP row
rkap_res = db.table("rkap")\
    .select("id, anggaran_awal, anggaran_terpakai, anggaran_sisa")\
    .eq("kategori_jabatan", KATEGORI)\
    .eq("lokasi_id", LOKASI_DALAM_ID)\
    .eq("bulan", BULAN)\
    .eq("tahun", TAHUN)\
    .single().execute()

if not rkap_res.data:
    print("❌ RKAP row tidak ditemukan.")
    sys.exit()

rkap = rkap_res.data
rkap_id = rkap["id"]
print(f"\nRKAP row id : {rkap_id}")
print(f"Anggaran    : {fmt_rp(rkap['anggaran_awal'])}")
print(f"Terpakai    : {fmt_rp(rkap['anggaran_terpakai'])}")
print(f"Sisa        : {fmt_rp(rkap['anggaran_sisa'])}")

# 2. Semua SPPD dengan rkap_id ini (SEMUA status)
all_sppd_res = db.table("sppd")\
    .select(
        "id, status, subtotal_uang_saku, total_hotel, total_transport, total_biaya,"
        " pegawai!sppd_pegawai_id_fkey(nama),"
        " visum(nomor_visum, tujuan, tanggal_berangkat)"
    )\
    .eq("rkap_id", rkap_id)\
    .execute()

all_sppd = all_sppd_res.data or []

aktif     = [s for s in all_sppd if s["status"] != "cancelled"]
cancelled = [s for s in all_sppd if s["status"] == "cancelled"]

print(f"\nSPPD referensi rkap_id ini: {len(all_sppd)} total "
      f"({len(aktif)} aktif, {len(cancelled)} cancelled)")

DEDUCT_STATUS = {"pencairan", "realisasi", "completed"}

def print_sppd(s, prefix=""):
    nama  = (s.get("pegawai") or {}).get("nama", "?")
    visum = s.get("visum") or {}
    tgl   = (visum.get("tanggal_berangkat") or "")[:10]
    print(f"{prefix}[{s['status'].upper():10}] {nama}")
    print(f"{prefix}             Visum : {visum.get('nomor_visum','-')} | {visum.get('tujuan','-')} | tgl {tgl}")
    print(f"{prefix}             Saku  : {fmt_rp(s.get('subtotal_uang_saku'))} | "
          f"Hotel: {fmt_rp(s.get('total_hotel'))} | "
          f"Transport: {fmt_rp(s.get('total_transport') or 0)} | "
          f"Total: {fmt_rp(s.get('total_biaya'))}")

print()
print("─" * 70)
print("SPPD AKTIF (yang masih ada, sudah deduct):")
print("─" * 70)
total_aktif_deducted = 0
for s in aktif:
    print_sppd(s, "  ")
    if s["status"] in DEDUCT_STATUS:
        total_aktif_deducted += s.get("total_biaya") or 0
    print()

print("─" * 70)
print("SPPD CANCELLED (harusnya sudah di-rollback saat cancel):")
print("─" * 70)
if not cancelled:
    print("  (tidak ada SPPD cancelled dengan rkap_id ini)")
else:
    for s in cancelled:
        print_sppd(s, "  ")
        print()

# 3. Hitung estimasi net deduct
# Logika rollback saat cancel: hanya subtotal_uang_saku yang di-rollback (bukan total_biaya)
# Jika ada cancelled yang pernah di-realisasi, transport+hotel tidak di-rollback

print("─" * 70)
print("ANALISIS:")
print("─" * 70)
print(f"  RKAP terpakai sekarang      : {fmt_rp(rkap['anggaran_terpakai'])}")
print(f"  SPPD aktif (deduct statuses): {fmt_rp(total_aktif_deducted)}")
print(f"  Selisih (phantom deduct)    : {fmt_rp(rkap['anggaran_terpakai'] - total_aktif_deducted)}")

if cancelled:
    print()
    print("  Estimasi sumber dari SPPD cancelled:")
    for s in cancelled:
        if s["status"] == "cancelled" and (s.get("total_biaya") or 0) > 0:
            saku    = s.get("subtotal_uang_saku") or 0
            total   = s.get("total_biaya") or 0
            var     = total - saku  # hotel + transport + lain
            print(f"    → {(s.get('pegawai') or {}).get('nama','?')}: "
                  f"total={fmt_rp(total)}, saku={fmt_rp(saku)}, "
                  f"var_cost={fmt_rp(var)}")
            print(f"       Saat cancel: rollback HANYA saku ({fmt_rp(saku)}), "
                  f"var_cost ({fmt_rp(var)}) TIDAK di-rollback → phantom deduct")

print()
print("─" * 70)
print("REKOMENDASI FIX:")
print("─" * 70)
phantom = rkap["anggaran_terpakai"] - total_aktif_deducted
if phantom == 0:
    print("  ✅ Tidak ada selisih — tidak perlu fix.")
elif phantom > 0:
    print(f"  ⚠️  RKAP LEBIH {fmt_rp(phantom)} dari SPPD aktif.")
    print(f"  → Rollback {fmt_rp(phantom)} dari rkap_id ini.")
    print(f"  → Jalankan: fix_bantuan_maret.py dengan DRY_RUN=False")
else:
    print(f"  ⚠️  RKAP KURANG {fmt_rp(abs(phantom))} dari SPPD aktif.")
    print(f"  → Deduct tambahan {fmt_rp(abs(phantom))} ke rkap_id ini.")

print()
print("=" * 70)
