"""
Diagnostik: bandingkan isi tabel rkap vs SPPD aktif yang merefer ke row tersebut.

Berguna untuk mendeteksi:
- RKAP terpakai lebih besar dari jumlah SPPD aktif (double-deduct atau gagal rollback)
- RKAP terpakai lebih kecil dari jumlah SPPD aktif (deduct tidak berjalan)

Jalankan dari root:  python check/cek_rkap_vs_sppd.py

Ubah TAHUN / BULAN_FILTER / KATEGORI_FILTER sesuai kebutuhan.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client

# ── FILTER (kosongkan untuk ambil semua) ────────────────
TAHUN           = 2026
BULAN_FILTER    = 5        # None = semua bulan
KATEGORI_FILTER = None     # mis. "DEWAS_ANGGOTA_2", None = semua
# ─────────────────────────────────────────────────────────

BULAN_LABEL = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agt", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des",
}
LOKASI_LABEL = {
    "6f7a80e0-1ca3-4e36-8d94-500bf8645efe": "Dalam Kaltim",
    "99c9f92f-972f-46d5-99d4-219b758d2cb7": "Luar Kaltim",
    "38663104-e5f5-473d-8227-640f025e595a": "Luar Negeri",
}

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")


db = get_client()

print("=" * 70)
print(f"CEK RKAP vs SPPD — Tahun {TAHUN}", end="")
if BULAN_FILTER: print(f"  Bulan {BULAN_LABEL.get(BULAN_FILTER, BULAN_FILTER)}", end="")
if KATEGORI_FILTER: print(f"  Kategori {KATEGORI_FILTER}", end="")
print()
print("=" * 70)

# 1. Ambil semua row RKAP sesuai filter
q = db.table("rkap").select("*").eq("tahun", TAHUN)
if BULAN_FILTER:
    q = q.eq("bulan", BULAN_FILTER)
if KATEGORI_FILTER:
    q = q.eq("kategori_jabatan", KATEGORI_FILTER)
rkap_rows = (q.order("kategori_jabatan").order("bulan").execute()).data or []

if not rkap_rows:
    print("Tidak ada data RKAP ditemukan.")
    sys.exit()

# 2. Ambil semua SPPD non-cancelled dengan rkap_id terisi
sppd_res = db.table("sppd")\
    .select(
        "id, rkap_id, status, subtotal_uang_saku, total_hotel, total_biaya,"
        " pegawai!sppd_pegawai_id_fkey(nama),"
        " visum(nomor_visum, tujuan, tanggal_berangkat)"
    )\
    .neq("status", "cancelled")\
    .not_.is_("rkap_id", "null")\
    .execute()
sppd_list = sppd_res.data or []

# Index SPPD per rkap_id
from collections import defaultdict
sppd_by_rkap = defaultdict(list)
for s in sppd_list:
    sppd_by_rkap[s["rkap_id"]].append(s)

# 3. Juga ambil SPPD *cancelled* per rkap_id untuk info tambahan
sppd_cancel_res = db.table("sppd")\
    .select("id, rkap_id, status, subtotal_uang_saku, total_hotel, total_biaya,"
            " pegawai!sppd_pegawai_id_fkey(nama),"
            " visum(nomor_visum, tujuan, tanggal_berangkat)")\
    .eq("status", "cancelled")\
    .not_.is_("rkap_id", "null")\
    .execute()
cancelled_by_rkap = defaultdict(list)
for s in (sppd_cancel_res.data or []):
    cancelled_by_rkap[s["rkap_id"]].append(s)

# 4. Tampilkan per row RKAP
masalah_count = 0
for r in rkap_rows:
    rkap_id  = r["id"]
    kategori = r["kategori_jabatan"]
    bulan    = r["bulan"]
    lokasi   = LOKASI_LABEL.get(r["lokasi_id"], r["lokasi_id"][:8])
    angg     = r.get("anggaran_awal") or 0
    terpakai = r.get("anggaran_terpakai") or 0
    sisa     = r.get("anggaran_sisa") or 0

    aktif    = sppd_by_rkap.get(rkap_id, [])
    cancel   = cancelled_by_rkap.get(rkap_id, [])

    # Hitung total dari SPPD yang sudah deduct RKAP (bukan draft)
    # DRAFT belum deduct RKAP, jadi tidak dihitung
    DEDUCT_STATUSES = {"pencairan", "realisasi", "completed"}
    aktif_deducted = [s for s in aktif if s.get("status") in DEDUCT_STATUSES]
    total_sppd_aktif = sum((s.get("total_biaya") or 0) for s in aktif_deducted)
    selisih = terpakai - total_sppd_aktif

    label_bln = BULAN_LABEL.get(bulan, str(bulan))
    header = f"{kategori} | {label_bln} | {lokasi}"
    print()
    print(f"{'─'*70}")
    print(f"  {header}")
    print(f"{'─'*70}")
    print(f"  Anggaran awal   : {fmt_rp(angg)}")
    print(f"  Terpakai (RKAP) : {fmt_rp(terpakai)}")
    print(f"  Sisa (RKAP)     : {fmt_rp(sisa)}")
    print(f"  SPPD aktif      : {len(aktif)} record  →  total_biaya = {fmt_rp(total_sppd_aktif)}")

    if selisih != 0:
        masalah_count += 1
        tanda = "⚠️  LEBIH" if selisih > 0 else "⚠️  KURANG"
        print(f"  Selisih RKAP vs SPPD : {tanda}  {fmt_rp(abs(selisih))}")
    else:
        print(f"  Selisih RKAP vs SPPD : ✅ Seimbang")

    # Detail SPPD aktif
    if aktif:
        draft_list = [s for s in aktif if s.get("status") == "draft"]
        print(f"\n  SPPD Aktif ({len(aktif_deducted)} sudah deduct, {len(draft_list)} masih draft):")
        for s in aktif:
            nama  = (s.get("pegawai") or {}).get("nama", "?")
            visum = s.get("visum") or {}
            tgl   = (visum.get("tanggal_berangkat") or "")[:10]
            print(f"    [{s['status'].upper():10}] {nama}")
            print(f"               Visum : {visum.get('nomor_visum','-')} | {visum.get('tujuan','-')} | tgl berangkat {tgl}")
            print(f"               Uang saku: {fmt_rp(s.get('subtotal_uang_saku'))}  "
                  f"Hotel: {fmt_rp(s.get('total_hotel'))}  "
                  f"Total: {fmt_rp(s.get('total_biaya'))}")

    # Info SPPD cancelled (untuk trace rollback)
    if cancel:
        print(f"\n  SPPD Cancelled (referencing same rkap_id — rollback seharusnya sudah terjadi):")
        for s in cancel:
            nama  = (s.get("pegawai") or {}).get("nama", "?")
            visum = s.get("visum") or {}
            tgl   = (visum.get("tanggal_berangkat") or "")[:10]
            print(f"    [CANCELLED] {nama}")
            print(f"               Visum : {visum.get('nomor_visum','-')} | {visum.get('tujuan','-')} | tgl {tgl}")
            print(f"               Uang saku: {fmt_rp(s.get('subtotal_uang_saku'))}  "
                  f"Hotel: {fmt_rp(s.get('total_hotel'))}  "
                  f"Total: {fmt_rp(s.get('total_biaya'))}")

print()
print("=" * 70)
if masalah_count:
    print(f"⚠️  Ditemukan {masalah_count} baris RKAP dengan selisih vs SPPD aktif.")
    print("   Kemungkinan penyebab:")
    print("   1. SPPD dibatalkan tapi rollback RKAP tidak berjalan (gagal/partial)")
    print("   2. Deduct terjadi dua kali untuk SPPD yang sama")
    print("   3. SPPD rkap_id berubah setelah deduct (deduct ke row lama, sppd sekarang ke row baru)")
else:
    print("✅ Semua baris RKAP seimbang dengan SPPD aktif.")
print("=" * 70)
