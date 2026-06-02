"""
Fix one-time: Pindah RKAP Bobby Wira Sakti (Visum 0054).
Bobby tercatat sebagai STAF PKWT saat visum dibuat, sehingga RKAP di-deduct
ke bucket 'bantuan_sppd'. Seharusnya STAF PELAKSANA → bucket ADM/TEKNIK_STAF_PELAKSANA.

Apa yang berubah:
  - RKAP bucket: bantuan_sppd --> ADM_STAF_PELAKSANA / TEKNIK_STAF_PELAKSANA
  - Tarif uang saku TIDAK berubah (kedua jabatan pakai tarif STAF PELAKSANA yang sama)
  - sppd.rkap_id diupdate ke row RKAP yang benar

Catatan: Update jabatan Bobby di tabel pegawai (STAF PKWT → STAF PELAKSANA) dilakukan
terpisah via UI halaman Kelola Pegawai (5_pegawai.py) → Tab 3 Kelola Jabatan.

Jalankan dari root:  python check/fix_bobby_rkap_visum0054.py
Set DRY_RUN = False untuk eksekusi nyata.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from datetime import date
from utils.database import (
    get_client, get_pegawai_by_id,
    resolve_kategori_rkap, get_rkap_id,
    deduct_rkap, rollback_rkap,
    update_rekap_spd,
    LOKASI_BANTUAN_ID,
)

DRY_RUN = False   # <-- Set False untuk eksekusi nyata

NAMA_PEGAWAI_PATTERN = "BOBBY"   # partial match (case-insensitive)
NOMOR_VISUM_PATTERN  = "0054"

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()
tag = "[DRY RUN]" if DRY_RUN else "[EKSEKUSI]"
print("=" * 70)
print(f"FIX RKAP BOBBY WIRA SAKTI — Visum {NOMOR_VISUM_PATTERN}  {tag}")
print("=" * 70)

# ── 1. Cari visum ──────────────────────────────────────────────────────────
visum_res = db.table("visum")\
    .select("id, nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali, lama_hari")\
    .like("nomor_visum", f"%{NOMOR_VISUM_PATTERN}%")\
    .execute()

if not visum_res.data:
    print(f"ERROR: Tidak ada visum dengan nomor mengandung '{NOMOR_VISUM_PATTERN}'.")
    sys.exit(1)

visum = visum_res.data[0]
print(f"\nVisum    : {visum['nomor_visum']}")
print(f"Tujuan   : {visum['tujuan']}")
print(f"Berangkat: {visum['tanggal_berangkat'][:10]} s/d {visum['tanggal_kembali'][:10]}")

# ── 2. Cari SPPD Bobby di visum ini ───────────────────────────────────────
sppd_res = db.table("sppd")\
    .select(
        "id, status, rkap_id, spd_id, lokasi_id, pegawai_id,"
        " total_hari, subtotal_uang_saku, total_biaya,"
        " tanggal_berangkat_custom, tanggal_kembali_custom,"
        " tanpa_uang_saku,"
        " pegawai!sppd_pegawai_id_fkey(nama, jabatan_id, jabatan(nama, struktur_rkap)),"
        " rkap(bulan, tahun, kategori_jabatan, lokasi_id, anggaran_terpakai, anggaran_sisa)"
    )\
    .eq("visum_id", visum["id"])\
    .neq("status", "cancelled")\
    .execute()

target_list = [
    s for s in sppd_res.data
    if NAMA_PEGAWAI_PATTERN.upper() in
       (s.get("pegawai") or {}).get("nama", "").upper()
]

if not target_list:
    print(f"\nERROR: Tidak ada SPPD aktif untuk pegawai '{NAMA_PEGAWAI_PATTERN}' di visum ini.")
    print("SPPD aktif yang ditemukan:")
    for s in sppd_res.data:
        nama = (s.get("pegawai") or {}).get("nama", "?")
        jab  = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
        print(f"  {nama} ({jab}) — status: {s['status']}")
    sys.exit(1)

if len(target_list) > 1:
    print(f"\nPERINGATAN: Ditemukan {len(target_list)} SPPD untuk '{NAMA_PEGAWAI_PATTERN}', memakai yang pertama.")

sppd = target_list[0]
peg  = sppd.get("pegawai") or {}
rkap_lama = sppd.get("rkap") or {}

nama_peg   = peg.get("nama", "?")
jab_nama   = (peg.get("jabatan") or {}).get("nama", "?")
jab_str    = (peg.get("jabatan") or {}).get("struktur_rkap", "?")
uang_saku  = sppd.get("subtotal_uang_saku") or 0
sppd_status = sppd["status"]
rkap_id_lama = sppd.get("rkap_id")
lokasi_id    = sppd.get("lokasi_id")
tanpa_saku   = sppd.get("tanpa_uang_saku") or False

print(f"\n{'-'*70}")
print(f"SPPD ID    : {sppd['id']}")
print(f"Pegawai    : {nama_peg}")
print(f"Jabatan DB : {jab_nama}  (struktur_rkap: {jab_str})")
print(f"Status SPPD: {sppd_status.upper()}")
print(f"Uang Saku  : {fmt_rp(uang_saku)}")
print(f"Total Biaya: {fmt_rp(sppd.get('total_biaya'))}")
print(f"Tanpa Saku : {'YA' if tanpa_saku else 'TIDAK'}")

print(f"\nRKAP Lama:")
if rkap_id_lama:
    print(f"  ID       : {rkap_id_lama}")
    print(f"  Kategori : {rkap_lama.get('kategori_jabatan')}")
    print(f"  Bulan    : {rkap_lama.get('bulan')} / {rkap_lama.get('tahun')}")
    print(f"  Terpakai : {fmt_rp(rkap_lama.get('anggaran_terpakai'))}")
    print(f"  Sisa     : {fmt_rp(rkap_lama.get('anggaran_sisa'))}")
else:
    print(f"  [NULL] — RKAP belum di-assign (status draft tanpa rkap_id)")

# ── 3. Hitung RKAP yang benar ──────────────────────────────────────────────
# Ambil data pegawai lengkap untuk resolve bidang_resolved
pegawai_lengkap = get_pegawai_by_id(sppd["pegawai_id"])
if not pegawai_lengkap:
    print("\nERROR: Tidak bisa ambil data pegawai lengkap.")
    sys.exit(1)

bidang = pegawai_lengkap.get("bidang_resolved") or ""
print(f"\nBidang divisi Bobby : '{bidang}'  (untuk menentukan ADM vs TEKNIK)")

# Jabatan Bobby harusnya STAF_PELAKSANA
# resolve_kategori_rkap("STAF_PELAKSANA", bidang, lokasi_id)
kategori_baru = resolve_kategori_rkap("STAF_PELAKSANA", bidang, lokasi_id or "")

# Tentukan bulan/tahun dari tanggal efektif SPPD
tgl_eff_str = sppd.get("tanggal_berangkat_custom") or visum["tanggal_berangkat"]
tgl_eff = date.fromisoformat(tgl_eff_str[:10])
bulan_eff = tgl_eff.month
tahun_eff = tgl_eff.year

# Untuk STAF_PELAKSANA, rkap_lokasi_id = lokasi aktual SPPD (bukan LOKASI_BANTUAN_ID)
rkap_lokasi_id_baru = lokasi_id

rkap_id_baru = get_rkap_id(kategori_baru, rkap_lokasi_id_baru, bulan_eff, tahun_eff)

print(f"\nRKAP Baru (seharusnya):")
print(f"  Kategori : {kategori_baru}")
print(f"  Bulan    : {bulan_eff} / {tahun_eff}")
print(f"  lokasi_id: {rkap_lokasi_id_baru}")

if rkap_id_baru:
    rkap_baru_res = db.table("rkap")\
        .select("anggaran_terpakai, anggaran_sisa, anggaran_awal")\
        .eq("id", rkap_id_baru)\
        .single().execute()
    rb = rkap_baru_res.data or {}
    print(f"  ID       : {rkap_id_baru}")
    print(f"  Terpakai : {fmt_rp(rb.get('anggaran_terpakai'))}")
    print(f"  Sisa     : {fmt_rp(rb.get('anggaran_sisa'))}")
else:
    print(f"  [ERROR] RKAP row tidak ditemukan! Cek apakah baris RKAP untuk")
    print(f"  kategori '{kategori_baru}', bulan {bulan_eff}/{tahun_eff} sudah ada di Supabase.")
    sys.exit(1)

# ── 4. Preview perubahan ───────────────────────────────────────────────────
sudah_deduct = sppd_status in ("pencairan", "realisasi", "completed")

print(f"\n{'-'*70}")
print(f"Rencana fix:")
if sudah_deduct:
    print(f"  1. Rollback RKAP lama  ({fmt_rp(uang_saku)} dari bantuan_sppd)")
    print(f"       terpakai: {fmt_rp(rkap_lama.get('anggaran_terpakai'))} --> "
          f"{fmt_rp((rkap_lama.get('anggaran_terpakai') or 0) - uang_saku)}")
    print(f"  2. Deduct RKAP baru   ({fmt_rp(uang_saku)} ke {kategori_baru})")
    print(f"       terpakai: {fmt_rp(rb.get('anggaran_terpakai'))} --> "
          f"{fmt_rp((rb.get('anggaran_terpakai') or 0) + uang_saku)}")
else:
    print(f"  Status SPPD adalah '{sppd_status}' — RKAP belum di-deduct,")
    print(f"  tidak perlu rollback/deduct. Cukup update rkap_id.")
print(f"  3. Update sppd.rkap_id  --> {rkap_id_baru}")
if sppd.get("spd_id"):
    print(f"  4. Update rekap SPD")

if tanpa_saku:
    print(f"\n  PERHATIAN: tanpa_uang_saku=TRUE, uang_saku=0. Rollback/deduct RKAP = Rp 0.")

# ── 5. Eksekusi ────────────────────────────────────────────────────────────
if DRY_RUN:
    print(f"\n[DRY RUN] Tidak ada yang diubah. Set DRY_RUN = False untuk eksekusi.")
else:
    if sudah_deduct and rkap_id_lama and uang_saku > 0 and not tanpa_saku:
        ok = rollback_rkap(rkap_id_lama, uang_saku)
        print(f"\n  {'[OK]' if ok else '[GAGAL]'} Rollback RKAP lama {fmt_rp(uang_saku)} dari bantuan_sppd.")

    if sudah_deduct and rkap_id_baru and uang_saku > 0 and not tanpa_saku:
        ok = deduct_rkap(rkap_id_baru, uang_saku)
        print(f"  {'[OK]' if ok else '[GAGAL]'} Deduct RKAP baru {fmt_rp(uang_saku)} ke {kategori_baru}.")

    db.table("sppd").update({"rkap_id": rkap_id_baru}).eq("id", sppd["id"]).execute()
    print(f"  [OK] sppd.rkap_id diupdate ke {rkap_id_baru}.")

    if sppd.get("spd_id"):
        update_rekap_spd(sppd["spd_id"])
        print(f"  [OK] Rekap SPD diperbarui.")

print()
print("=" * 70)
if DRY_RUN:
    print("[DRY RUN] Selesai. Cek output di atas, lalu set DRY_RUN = False.")
else:
    print("[OK] Fix selesai. Cek RKAP Monitor untuk verifikasi.")
print("=" * 70)
