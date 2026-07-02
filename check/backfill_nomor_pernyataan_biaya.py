"""
Backfill kolom nomor_pernyataan_biaya di tabel sppd.

Dijalankan sekali setelah kolom baru ditambahkan ke Supabase.
Hanya mengisi SPPD status realisasi/completed yang belum punya nomor.
SPPD cancelled dilewati (tidak dapat nomor).
Urutan: per tahun (dari tanggal_spd), sort tanggal_berangkat visum ASC → created_at ASC.

Ubah DRY_RUN = False untuk eksekusi nyata.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_client
from collections import defaultdict

DRY_RUN = True

def run():
    db = get_client()

    # Ambil semua SPPD realisasi/completed, join visum dan spd untuk sort + tahun
    res = db.table("sppd")\
        .select("id, status, nomor_pernyataan_biaya, created_at, "
                "visum!sppd_visum_id_fkey(tanggal_berangkat), "
                "spd(tanggal_spd)")\
        .in_("status", ["realisasi", "completed"])\
        .execute()

    rows = res.data or []
    print(f"Total SPPD realisasi/completed: {len(rows)}")

    sudah_ada = [r for r in rows if r.get("nomor_pernyataan_biaya") is not None]
    perlu_diisi = [r for r in rows if r.get("nomor_pernyataan_biaya") is None]
    print(f"Sudah punya nomor: {len(sudah_ada)}")
    print(f"Perlu diisi     : {len(perlu_diisi)}")

    # Kelompokkan per tahun (dari tanggal_spd; fallback ke tanggal_berangkat visum)
    by_tahun: dict[int, list] = defaultdict(list)
    for r in perlu_diisi:
        spd_row = r.get("spd") or {}
        tgl_spd = (spd_row.get("tanggal_spd") or "")[:4]
        visum_row = r.get("visum") or {}
        tgl_brkt = (visum_row.get("tanggal_berangkat") or "")[:4]
        try:
            tahun = int(tgl_spd) if tgl_spd else (int(tgl_brkt) if tgl_brkt else 0)
        except ValueError:
            tahun = 0
        by_tahun[tahun].append(r)

    # Nomor yang sudah terpakai per tahun (dari data yang sudah ada)
    used_per_tahun: dict[int, set] = defaultdict(set)
    for r in sudah_ada:
        spd_row = r.get("spd") or {}
        tgl_spd = (spd_row.get("tanggal_spd") or "")[:4]
        try:
            tahun = int(tgl_spd) if tgl_spd else 0
        except ValueError:
            tahun = 0
        used_per_tahun[tahun].add(r["nomor_pernyataan_biaya"])

    total_diupdate = 0

    for tahun in sorted(by_tahun.keys()):
        items = by_tahun[tahun]
        # Sort: tanggal_berangkat visum ASC, lalu created_at ASC
        items.sort(key=lambda r: (
            (r.get("visum") or {}).get("tanggal_berangkat") or "9999",
            r.get("created_at") or "9999",
        ))

        used = used_per_tahun[tahun]
        print(f"\n=== Tahun {tahun} - {len(items)} SPPD akan dinomori ===")

        for r in items:
            # Cari nomor terkecil yang belum dipakai
            n = 1
            while n in used:
                n += 1
            used.add(n)

            visum_row = r.get("visum") or {}
            print(f"  {'[DRY]' if DRY_RUN else '[UPDATE]'} "
                  f"sppd_id={r['id'][:8]}... "
                  f"tgl_berangkat={visum_row.get('tanggal_berangkat','-')} "
                  f"-> nomor {n:03d}")

            if not DRY_RUN:
                db.table("sppd")\
                    .update({"nomor_pernyataan_biaya": n})\
                    .eq("id", r["id"])\
                    .execute()
                total_diupdate += 1

    if DRY_RUN:
        print("\n[DRY RUN] Tidak ada perubahan. Set DRY_RUN = False untuk eksekusi.")
    else:
        print(f"\n[SELESAI] {total_diupdate} SPPD berhasil dinomori.")

if __name__ == "__main__":
    run()
