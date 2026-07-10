"""
test_sppd_realisasi.py
======================
Script debug lokal untuk SPPD Tanda Terima Realisasi PDF.
Run: python test_sppd_realisasi.py
→ Generate sppd_realisasi_test.pdf di folder ini, lalu auto-buka.

CARA PAKAI:
1. Taruh file ini di folder yang sama dengan pdf_generator.py
2. Run: python test_sppd_realisasi.py
3. PDF langsung terbuka
4. Edit pdf_generator.py → run lagi → lihat perubahan
"""

import os
import subprocess
import sys
from datetime import date
from pdf_generator import generate_sppd_realisasi

# ══════════════════════════════════════════════════════
# DATA TEST — edit sesuai kebutuhan debug
# ══════════════════════════════════════════════════════
DATA = {
    # Info dasar (sama seperti pencairan)
    "nama_pejabat":      "Direktur Umum PTMB",
    "nomor_spd":         "0012/1421002/10a-I/II/2026-O",
    "tanggal":           date(2026, 2, 18),
    "tempat_tujuan":     "Semarang",
    "tgl_berangkat":     date(2026, 2, 10),
    "tgl_kembali":       date(2026, 2, 13),
    "lama_hari":         4,
    "nama_penerima":     "Purnamawati, S.E",
    "jabatan_penerima":  "Direktur Umum PTMB",
    "uang_harian":       1575000,
    "uang_representasi": 150000,

    # Realisasi: tiket aktual
    "items_transport": [
        {"keterangan": "Tiket Pesawat BPN - CGK", "qty": 1, "satuan": 2500000},
        {"keterangan": "Tiket Pesawat CGK - BPN", "qty": 1, "satuan": 2300000},
    ],

    # Hotel aktual: rincian per baris, "hari" dipakai buat tampilkan "hari x rate = biaya"
    # uraian="" → baris 30% pagu penginapan
    "hotel_items": [
        {"uraian": "", "biaya": 175000, "keterangan": "(30% belum dibayar)", "hari": 1},
        {"uraian": "Hotel A", "biaya": 1500000, "keterangan": "(sudah dibayar)", "hari": 2},
        {"uraian": "Hotel B", "biaya": 500000, "keterangan": "", "hari": 1},
    ],

    # Biaya lain-lain (seminar, dll)
    "biaya_lain": [
        {"keterangan": "Biaya Seminar / Registrasi", "qty": 1, "satuan": 8850000},
    ],

    # Grand total manual (uang harian + transport + hotel + lain)
    # 4*1575000 + 4*150000 + (2500000+2300000) + (175000+1500000+500000) + 8850000 = 22725000
    "grand_total": 22725000,

    "ttd_dirut": "Dr. Saharuddin, M.M",
}

# ══════════════════════════════════════════════════════
# GENERATE & BUKA
# ══════════════════════════════════════════════════════
OUT = "sppd_realisasi_test.pdf"

print("⏳ Generating SPPD Tanda Terima Realisasi...")
pdf_bytes = generate_sppd_realisasi(DATA).read()

with open(OUT, "wb") as f:
    f.write(pdf_bytes)

print(f"✅ Saved: {OUT}")

if sys.platform == "win32":
    os.startfile(OUT)
elif sys.platform == "darwin":
    subprocess.run(["open", OUT])
else:
    subprocess.run(["xdg-open", OUT])

print("📄 PDF dibuka! Edit pdf_generator.py → run lagi.")
