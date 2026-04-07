"""
Script repair: hitung ulang rekap kategori untuk semua SPD.

Masalah: import_histori_2026.py tidak memanggil update_rekap_spd(),
sehingga kolom total_direksi/dewas/administrasi/teknik/bantuan di tabel
spd semua bernilai 0. Dashboard & rekap SPD jadi kosong.

Jalankan dari folder root:
  python setup/fix_rekap_spd.py

Mode:
  DRY_RUN = True   -> preview saja (tampilkan spd_id yang akan diupdate)
  DRY_RUN = False  -> jalankan update_rekap_spd() sungguhan
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from utils.database import update_rekap_spd, get_client

load_dotenv()

DRY_RUN = False  # True = preview saja, False = jalankan update_rekap_spd() sungguhan

def main():
    print("=" * 60)
    print(f"FIX REKAP SPD | DRY_RUN={DRY_RUN}")
    print("=" * 60)

    db = get_client()
    res = db.table("spd").select("id, nomor_spd, grand_total, total_direksi, total_dewas, total_administrasi, total_teknik, total_bantuan").execute()
    spd_list = res.data

    print(f"\nTotal SPD ditemukan: {len(spd_list)}")
    print()

    ok = 0
    errors = []

    for spd in spd_list:
        spd_id    = spd["id"]
        nomor     = spd.get("nomor_spd", "-")
        total     = spd.get("grand_total") or 0
        direksi   = spd.get("total_direksi") or 0
        dewas     = spd.get("total_dewas") or 0
        adm       = spd.get("total_administrasi") or 0
        teknik    = spd.get("total_teknik") or 0
        bantuan   = spd.get("total_bantuan") or 0
        kat_total = direksi + dewas + adm + teknik + bantuan

        print(f"  SPD {nomor:<35s} grand={total:>12,}  kat_sum={kat_total:>12,}")

        if DRY_RUN:
            ok += 1
            continue

        try:
            update_rekap_spd(spd_id)
            ok += 1
            print(f"    -> [OK] rekap diupdate")
        except Exception as e:
            msg = f"ERROR spd_id={spd_id}: {e}"
            print(f"    -> [X] {msg}")
            errors.append(msg)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  SPD diproses : {ok}")
    if errors:
        print(f"  Errors       : {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    if DRY_RUN:
        print("\n  [i] DRY RUN - tidak ada yang diupdate.")
        print("  Ganti DRY_RUN = False untuk eksekusi sungguhan.")
    else:
        print("\n  [OK] Selesai! Cek dashboard & rekap SPD.")


if __name__ == "__main__":
    main()
