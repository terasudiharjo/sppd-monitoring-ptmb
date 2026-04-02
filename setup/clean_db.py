"""
Script bersihkan data transaksi untuk keperluan testing / go-live.

Yang DIHAPUS:
  - sppd_biaya_lain  (child of sppd)
  - sppd_trip_detail (child of sppd)
  - sppd
  - spd
  - visum

Yang DIRESET (tidak dihapus):
  - rkap.anggaran_terpakai = 0
  - rkap.anggaran_sisa     = anggaran_awal

Yang TIDAK DISENTUH:
  - pegawai, jabatan, divisi, lokasi_sppd, rule_sppd, rkap (row-nya tetap)

Jalankan dari folder root:  python setup/clean_db.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DRY_RUN = True  # Ganti False untuk eksekusi sungguhan

def get_db():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def main():
    print("=" * 60)
    print(f"CLEAN DB | DRY_RUN={DRY_RUN}")
    print("=" * 60)

    db = get_db()

    # ── Hitung jumlah record sebelum ──
    print("\n[1] Cek jumlah data saat ini...")
    counts = {}
    for tabel in ["visum", "spd", "sppd", "sppd_biaya_lain", "sppd_trip_detail"]:
        res = db.table(tabel).select("id", count="exact").execute()
        counts[tabel] = res.count or 0
        print(f"  {tabel:25s}: {counts[tabel]} record")

    res_rkap = db.table("rkap").select("id, kategori_jabatan, bulan, anggaran_awal, anggaran_terpakai, anggaran_sisa").execute()
    rkap_rows = res_rkap.data or []
    total_terpakai = sum(r.get("anggaran_terpakai", 0) or 0 for r in rkap_rows)
    print(f"  {'rkap (total terpakai)':25s}: Rp {total_terpakai:,.0f}")

    if DRY_RUN:
        print("\n[i] DRY RUN — tidak ada yang diubah.")
        print("    Yang akan dilakukan kalau DRY_RUN=False:")
        print(f"    - Hapus {counts['sppd_biaya_lain']} sppd_biaya_lain")
        print(f"    - Hapus {counts['sppd_trip_detail']} sppd_trip_detail")
        print(f"    - Hapus {counts['sppd']} sppd")
        print(f"    - Hapus {counts['spd']} spd")
        print(f"    - Hapus {counts['visum']} visum")
        print(f"    - Reset {len(rkap_rows)} baris rkap → anggaran_terpakai=0, anggaran_sisa=anggaran_awal")
        print("\nGanti DRY_RUN = False untuk eksekusi sungguhan.")
        return

    # ── Hapus data transaksi (urut dari child ke parent) ──
    print("\n[2] Hapus data transaksi...")

    print("  Hapus sppd_biaya_lain...", end=" ")
    db.table("sppd_biaya_lain").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("OK")

    print("  Hapus sppd_trip_detail...", end=" ")
    db.table("sppd_trip_detail").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("OK")

    print("  Hapus sppd...", end=" ")
    db.table("sppd").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("OK")

    print("  Hapus spd...", end=" ")
    db.table("spd").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("OK")

    print("  Hapus visum...", end=" ")
    db.table("visum").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("OK")

    # ── Reset RKAP ──
    print("\n[3] Reset RKAP...")
    reset_ok = 0
    for r in rkap_rows:
        anggaran_awal = r.get("anggaran_awal", 0) or 0
        db.table("rkap").update({
            "anggaran_terpakai": 0,
            "anggaran_sisa": anggaran_awal,
        }).eq("id", r["id"]).execute()
        print(f"  [OK] {r.get('kategori_jabatan', '?'):30s} bln {r.get('bulan', '?'):2} → sisa = Rp {anggaran_awal:,.0f}")
        reset_ok += 1

    # ── Verifikasi ──
    print("\n[4] Verifikasi setelah clean...")
    for tabel in ["visum", "spd", "sppd", "sppd_biaya_lain", "sppd_trip_detail"]:
        res = db.table(tabel).select("id", count="exact").execute()
        n = res.count or 0
        status = "OK" if n == 0 else f"MASIH ADA {n}!"
        print(f"  {tabel:25s}: {n} record [{status}]")

    print("\n" + "=" * 60)
    print(f"SELESAI. Data transaksi dihapus. {reset_ok} baris RKAP di-reset.")
    print("=" * 60)


if __name__ == "__main__":
    main()
