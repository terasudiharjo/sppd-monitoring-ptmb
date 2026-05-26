"""
Fix one-time: un-cancel visum yang tidak sengaja di-cancel.

Jalankan DRY_RUN=True dulu untuk melihat kondisi data.
Set DRY_RUN=False + konfirmasi untuk eksekusi nyata.

Konfigurasi:
  NOMOR_VISUM_PATTERN  : nomor visum (partial match), contoh "0059" atau "59"
  TARGET_STATUS_SPPD   : status yang akan dipulihkan ke semua SPPD cancelled
                         → "pencairan" : SPPD di-restore + RKAP di-re-deduct
                         → "draft"     : SPPD di-restore, RKAP tidak diubah
  RESTORE_VISUM_STATUS : status visum yang akan di-set setelah fix (biasanya "aktif")
  DRY_RUN              : True = hanya tampilkan preview, False = eksekusi

Jalankan dari root:  python check/fix_uncancel_visum.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client, deduct_rkap, update_rekap_spd

# ─── KONFIGURASI ─────────────────────────────────────────────────────────────
NOMOR_VISUM_PATTERN  = "0059"       # partial match nomor visum
TARGET_STATUS_SPPD   = "draft"  # "pencairan" atau "draft"
RESTORE_VISUM_STATUS = "aktif"      # status visum setelah fix
DRY_RUN = True                      # ganti False untuk eksekusi nyata
# ─────────────────────────────────────────────────────────────────────────────

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()

tag = "[DRY RUN]" if DRY_RUN else "[EKSEKUSI]"
print("=" * 70)
print(f"UN-CANCEL VISUM  {tag}")
print(f"Pattern: '{NOMOR_VISUM_PATTERN}'  |  Target SPPD: '{TARGET_STATUS_SPPD}'  |  Target Visum: '{RESTORE_VISUM_STATUS}'")
print("=" * 70)

# 1. Cari visum
visum_res = db.table("visum")\
    .select("id, nomor_visum, tujuan, keperluan, tanggal_berangkat, tanggal_kembali, status, tanpa_spd")\
    .like("nomor_visum", f"%{NOMOR_VISUM_PATTERN}%")\
    .execute()

if not visum_res.data:
    print(f"ERROR: Tidak ada visum dengan nomor mengandung '{NOMOR_VISUM_PATTERN}'.")
    sys.exit(1)

if len(visum_res.data) > 1:
    print(f"PERINGATAN: {len(visum_res.data)} visum cocok, memakai yang pertama:")
    for v in visum_res.data:
        print(f"  {v['nomor_visum']} | {v['status']} | {v['tujuan']}")
    print()

visum = visum_res.data[0]
print(f"\nVisum    : {visum['nomor_visum']}")
print(f"Tujuan   : {visum['tujuan']}")
print(f"Keperluan: {visum.get('keperluan', '-')}")
print(f"Berangkat: {visum['tanggal_berangkat'][:10]} s/d {visum['tanggal_kembali'][:10]}")
print(f"Status   : {visum['status'].upper()}")
print(f"Tanpa SPD: {visum.get('tanpa_spd', False)}")

if visum["status"] != "cancelled":
    print(f"\nWARNING: Status visum bukan 'cancelled' (saat ini: '{visum['status']}').")
    print("Script ini dirancang untuk un-cancel. Lanjutkan? Tekan Ctrl+C untuk batal.")
    print("(5 detik...)")
    import time; time.sleep(5)

# 2. Cari semua SPPD cancelled milik visum ini
sppd_res = db.table("sppd")\
    .select(
        "id, status, rkap_id, spd_id, total_hari,"
        " subtotal_uang_saku, total_hotel, total_biaya,"
        " menginap, tanggal_berangkat_custom, tanggal_kembali_custom,"
        " pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama)),"
        " rkap(bulan, tahun, kategori_jabatan, anggaran_terpakai, anggaran_sisa)"
    )\
    .eq("visum_id", visum["id"])\
    .eq("status", "cancelled")\
    .order("created_at")\
    .execute()

# Juga ambil SPPD non-cancelled (kalau ada yang sudah direstore sebelumnya)
sppd_lain_res = db.table("sppd")\
    .select("id, status, pegawai!sppd_pegawai_id_fkey(nama)")\
    .eq("visum_id", visum["id"])\
    .neq("status", "cancelled")\
    .execute()

print(f"\n{'─'*70}")
print(f"SPPD cancelled ditemukan: {len(sppd_res.data)}")
if sppd_lain_res.data:
    print(f"SPPD non-cancelled (sudah aktif/draft/dll): {len(sppd_lain_res.data)}")
    for s in sppd_lain_res.data:
        nama = (s.get("pegawai") or {}).get("nama", "?")
        print(f"  → {nama} [{s['status']}] — TIDAK akan diubah")

if not sppd_res.data:
    print(f"\nTidak ada SPPD berstatus 'cancelled' pada visum ini.")
    print("Mungkin visum saja yang perlu di-restore statusnya?")
    if not visum.get("tanpa_spd"):
        print("Pertimbangkan: jalankan manual di Supabase untuk update visum.status.")
    sys.exit(0)

print(f"\n{'─'*70}")
total_saku = 0
for i, s in enumerate(sppd_res.data, 1):
    nama    = (s.get("pegawai") or {}).get("nama", "?")
    jabatan = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
    rkap    = s.get("rkap") or {}
    uang_saku = s.get("subtotal_uang_saku") or 0
    total_saku += uang_saku

    print(f"\n[{i}] {nama}")
    print(f"     Jabatan     : {jabatan}")
    print(f"     Status      : {s['status'].upper()}")
    print(f"     Total Hari  : {s.get('total_hari')}")
    print(f"     Uang Saku   : {fmt_rp(uang_saku)}")
    print(f"     Total Biaya : {fmt_rp(s.get('total_biaya'))}")
    print(f"     Menginap    : {s.get('menginap')}")
    if s.get("tanggal_berangkat_custom"):
        print(f"     Tgl Custom  : {s['tanggal_berangkat_custom'][:10]} s/d {s.get('tanggal_kembali_custom','?')[:10]}")

    if s.get("rkap_id"):
        print(f"     RKAP        : {rkap.get('kategori_jabatan')} | Bln {rkap.get('bulan')} {rkap.get('tahun')}")
        if TARGET_STATUS_SPPD == "pencairan":
            terpakai_baru = (rkap.get("anggaran_terpakai") or 0) + uang_saku
            sisa_baru     = (rkap.get("anggaran_sisa") or 0) - uang_saku
            print(f"     RKAP terpakai: {fmt_rp(rkap.get('anggaran_terpakai'))} → {fmt_rp(terpakai_baru)}")
            print(f"     RKAP sisa    : {fmt_rp(rkap.get('anggaran_sisa'))} → {fmt_rp(sisa_baru)}")
    else:
        print(f"     RKAP        : NULL (tidak ada RKAP yang akan di-deduct)")

# Ringkasan rencana
spd_ids = {s["spd_id"] for s in sppd_res.data if s.get("spd_id")}
print(f"\n{'─'*70}")
print(f"RINGKASAN RENCANA FIX:")
print(f"  1. Visum '{visum['nomor_visum']}' : cancelled → {RESTORE_VISUM_STATUS}")
print(f"  2. {len(sppd_res.data)} SPPD : cancelled → {TARGET_STATUS_SPPD}")
if TARGET_STATUS_SPPD == "pencairan":
    n_rkap = sum(1 for s in sppd_res.data if s.get("rkap_id") and (s.get("subtotal_uang_saku") or 0) > 0)
    print(f"  3. Re-deduct RKAP untuk {n_rkap} SPPD (total {fmt_rp(total_saku)})")
else:
    print(f"  3. RKAP tidak diubah (target status = draft)")
if spd_ids:
    print(f"  4. Update rekap SPD: {len(spd_ids)} SPD")

if DRY_RUN:
    print(f"\n{'='*70}")
    print("[DRY RUN] Selesai. Tidak ada yang diubah.")
    print("Pastikan TARGET_STATUS_SPPD sesuai (pencairan/draft), lalu set DRY_RUN=False.")
    print("="*70)
    sys.exit(0)

# ── EKSEKUSI ──────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("EKSEKUSI...")

n_ok = 0
for s in sppd_res.data:
    sppd_id   = s["id"]
    rkap_id   = s.get("rkap_id")
    uang_saku = s.get("subtotal_uang_saku") or 0
    nama      = (s.get("pegawai") or {}).get("nama", "?")

    # Ubah status SPPD
    db.table("sppd").update({"status": TARGET_STATUS_SPPD})\
        .eq("id", sppd_id).execute()
    print(f"  [OK] {nama}: cancelled → {TARGET_STATUS_SPPD}")

    # Re-deduct RKAP jika target pencairan
    if TARGET_STATUS_SPPD == "pencairan" and rkap_id and uang_saku > 0:
        ok = deduct_rkap(rkap_id, uang_saku)
        print(f"       {'[OK]' if ok else '[GAGAL]'} Re-deduct RKAP {fmt_rp(uang_saku)}")
    elif TARGET_STATUS_SPPD == "pencairan" and not rkap_id:
        print(f"       [SKIP] rkap_id NULL — RKAP tidak diubah")

    n_ok += 1

# Update rekap SPD
for spd_id in spd_ids:
    update_rekap_spd(spd_id)
    print(f"  [OK] Rekap SPD diperbarui")

# Restore status visum
db.table("visum").update({"status": RESTORE_VISUM_STATUS})\
    .eq("id", visum["id"]).execute()
print(f"  [OK] Visum '{visum['nomor_visum']}' → {RESTORE_VISUM_STATUS}")

print(f"\n{'='*70}")
print(f"[OK] Fix selesai. {n_ok} SPPD dipulihkan ke '{TARGET_STATUS_SPPD}'.")
print("Cek Tab 4 Visum & Tab 1 SPPD untuk verifikasi.")
print("="*70)
