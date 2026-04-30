"""
Fix one-time: pindahkan deduct RKAP Visum 0028 (Bali, berangkat 26 Maret)
dari RKAP April ke RKAP Maret yang benar.

Kondisi sekarang (salah):
  FALIQ ABDUL RAHMAN  -> rkap_id April ADM_STAF_PELAKSANA Luar Kaltim
  Supriadi, S.Pi      -> rkap_id April DEWAS_ANGGOTA_2    Luar Kaltim

Fix yang dilakukan (per SPPD):
  1. rollback_rkap  dari row RKAP April (kurangi terpakai, tambah sisa)
  2. deduct_rkap    ke   row RKAP Maret (tambah terpakai, kurangi sisa)
  3. update sppd.rkap_id ke RKAP Maret

Jalankan dari root:  python check/fix_visum0028_rkap_bulan.py
Set DRY_RUN = False untuk benar-benar mengubah data.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client, rollback_rkap, deduct_rkap, update_rekap_spd

DRY_RUN = True   # <-- Set False untuk eksekusi nyata

NOMOR_VISUM_TARGET = "0028/1421002/10a-I/III/2026-J"
BULAN_SALAH   = 4   # April (yang sekarang)
BULAN_BENAR   = 3   # Maret (yang seharusnya)
TAHUN         = 2026
LOKASI_LUAR_ID = "99c9f92f-972f-46d5-99d4-219b758d2cb7"

BULAN_LABEL = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",
               7:"Jul",8:"Agt",9:"Sep",10:"Okt",11:"Nov",12:"Des"}

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

db = get_client()

tag = "[DRY RUN]" if DRY_RUN else "[EKSEKUSI]"
print("=" * 70)
print(f"FIX RKAP BULAN: Visum 0028 Bali  {tag}")
print(f"Pindah deduct: {BULAN_LABEL[BULAN_SALAH]} --> {BULAN_LABEL[BULAN_BENAR]} {TAHUN}")
print("=" * 70)

# 1. Ambil semua SPPD dari visum target
visum_res = db.table("visum")\
    .select("id, nomor_visum, tujuan, tanggal_berangkat")\
    .eq("nomor_visum", NOMOR_VISUM_TARGET)\
    .single().execute()

if not visum_res.data:
    print(f"ERROR: Visum '{NOMOR_VISUM_TARGET}' tidak ditemukan.")
    sys.exit(1)

visum = visum_res.data
print(f"\nVisum    : {visum['nomor_visum']}")
print(f"Tujuan   : {visum['tujuan']}")
print(f"Berangkat: {visum['tanggal_berangkat'][:10]}")

sppd_res = db.table("sppd")\
    .select(
        "id, status, rkap_id, total_biaya, spd_id,"
        " pegawai!sppd_pegawai_id_fkey(nama),"
        " rkap(bulan, tahun, kategori_jabatan, lokasi_id,"
        "      anggaran_terpakai, anggaran_sisa)"
    )\
    .eq("visum_id", visum["id"])\
    .neq("status", "cancelled")\
    .not_.is_("rkap_id", "null")\
    .execute()

sppd_list = sppd_res.data or []

if not sppd_list:
    print("\nTidak ada SPPD aktif dengan rkap_id pada visum ini.")
    sys.exit(1)

print(f"\nDitemukan {len(sppd_list)} SPPD aktif.\n")

# 2. Filter hanya yang rkap bulan-nya salah (April)
to_fix = []
sudah_benar = []
for s in sppd_list:
    rkap = s.get("rkap") or {}
    if rkap.get("bulan") == BULAN_SALAH and rkap.get("tahun") == TAHUN:
        to_fix.append(s)
    else:
        sudah_benar.append(s)

if sudah_benar:
    print("SPPD yang rkap_id-nya sudah benar (skip):")
    for s in sudah_benar:
        nama = (s.get("pegawai") or {}).get("nama", "?")
        rkap = s.get("rkap") or {}
        print(f"  {nama} -- bulan {rkap.get('bulan')} {rkap.get('kategori_jabatan')}")
    print()

if not to_fix:
    print("[OK] Tidak ada SPPD yang perlu difix.")
    sys.exit(0)

print(f"SPPD yang perlu difix: {len(to_fix)}")
print("-" * 70)

errors = []
for s in to_fix:
    nama  = (s.get("pegawai") or {}).get("nama", "?")
    rkap  = s.get("rkap") or {}
    sppd_id    = s["id"]
    rkap_id_lama = s["rkap_id"]
    kategori   = rkap.get("kategori_jabatan", "?")
    total_biaya = s.get("total_biaya") or 0

    print(f"\nSPPD     : {sppd_id}")
    print(f"Pegawai  : {nama}")
    print(f"Status   : {s['status'].upper()}")
    print(f"Kategori : {kategori}")
    print(f"Total biaya: {fmt_rp(total_biaya)}")
    print()
    print(f"  RKAP April (lama) : {rkap_id_lama}")
    print(f"    terpakai: {fmt_rp(rkap.get('anggaran_terpakai'))}"
          f"  sisa: {fmt_rp(rkap.get('anggaran_sisa'))}")

    # Cari RKAP Maret yang benar
    rkap_maret_res = db.table("rkap")\
        .select("id, anggaran_awal, anggaran_terpakai, anggaran_sisa")\
        .eq("kategori_jabatan", kategori)\
        .eq("lokasi_id", LOKASI_LUAR_ID)\
        .eq("bulan", BULAN_BENAR)\
        .eq("tahun", TAHUN)\
        .single().execute()

    if not rkap_maret_res.data:
        msg = f"ERROR: RKAP Maret untuk {kategori} tidak ditemukan -- skip SPPD ini."
        print(f"  {msg}")
        errors.append(msg)
        continue

    rkap_maret = rkap_maret_res.data
    rkap_id_baru = rkap_maret["id"]

    print(f"\n  RKAP Maret (baru) : {rkap_id_baru}")
    print(f"    terpakai: {fmt_rp(rkap_maret['anggaran_terpakai'])}"
          f"  sisa: {fmt_rp(rkap_maret['anggaran_sisa'])}")

    # Preview perubahan
    print(f"\n  Rencana fix:")
    print(f"    rollback {fmt_rp(total_biaya)} dari RKAP April")
    print(f"      terpakai April: {fmt_rp(rkap['anggaran_terpakai'])} "
          f"--> {fmt_rp(rkap['anggaran_terpakai'] - total_biaya)}")
    print(f"      sisa April    : {fmt_rp(rkap['anggaran_sisa'])} "
          f"--> {fmt_rp(rkap['anggaran_sisa'] + total_biaya)}")
    print(f"    deduct {fmt_rp(total_biaya)} ke RKAP Maret")
    print(f"      terpakai Maret: {fmt_rp(rkap_maret['anggaran_terpakai'])} "
          f"--> {fmt_rp(rkap_maret['anggaran_terpakai'] + total_biaya)}")
    print(f"      sisa Maret    : {fmt_rp(rkap_maret['anggaran_sisa'])} "
          f"--> {fmt_rp(rkap_maret['anggaran_sisa'] - total_biaya)}")
    print(f"    update sppd.rkap_id --> RKAP Maret")

    if DRY_RUN:
        print(f"\n  [DRY RUN] Tidak ada yang diubah.")
    else:
        ok1 = rollback_rkap(rkap_id_lama, total_biaya)
        ok2 = deduct_rkap(rkap_id_baru, total_biaya)
        db.table("sppd").update({"rkap_id": rkap_id_baru}).eq("id", sppd_id).execute()
        if s.get("spd_id"):
            update_rekap_spd(s["spd_id"])

        status_ok = "[OK]" if (ok1 and ok2) else "[PARTIAL]"
        print(f"\n  {status_ok} rollback April: {ok1} | deduct Maret: {ok2} | rkap_id updated")
        if s.get("spd_id"):
            print(f"  [OK] Rekap SPD diperbarui.")

print()
print("=" * 70)
if errors:
    print(f"[!] {len(errors)} error terjadi:")
    for e in errors:
        print(f"    {e}")
elif DRY_RUN:
    print("[DRY RUN] Selesai. Set DRY_RUN = False untuk eksekusi nyata.")
else:
    print("[OK] Fix selesai. Jalankan cek_sppd_bulan_rkap.py untuk verifikasi.")
print("=" * 70)
