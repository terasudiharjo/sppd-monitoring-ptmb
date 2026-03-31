"""
test_spd.py
===========
Script debug lokal untuk Surat Penyediaan Dana (SPD) PDF.
Run: python test_spd.py
→ Generate spd_test.pdf di folder ini, lalu auto-buka.

CARA PAKAI:
1. Taruh file ini di folder yang sama dengan pdf_generator.py
2. Run: python test_spd.py
3. PDF langsung terbuka
4. Edit pdf_generator.py → run lagi → lihat perubahan
"""

import os
import subprocess
import sys
from datetime import date
from pdf_generator import generate_spd

# ══════════════════════════════════════════════════════
# DATA TEST — edit sesuai kebutuhan debug
# ══════════════════════════════════════════════════════
DATA = {
    "nomor":         "0012/1421002/10a-I/II/2026-O",
    "tanggal":       date(2026, 2, 2),
    "lokasi_label":  "Biaya Perjalanan Dinas di Luar Daerah KALTIM",
    "tahun":         2026,
    "kategori": [
        {"no": 1, "uraian": "Direksi",                     "total": 19997900, "kode": "96.08.41"},
        {"no": 2, "uraian": "Bagian Administrasi/Keuangan", "total": 33385800, "kode": "96.08.42"},
        {"no": 3, "uraian": "Bagian Teknik",                "total": 0,        "kode": "96.08.43"},
        {"no": 4, "uraian": "Dewan Pengawas",               "total": 0,        "kode": "96.08.30"},
        {"no": 5, "uraian": "Bantuan",                      "total": 0,        "kode": "96.08.92"},
    ],
    "grand_total": 53383700,
    "peserta": [
        {"no": 1, "nama": "Purnamawati, S.E",  "jabatan": "Direktur Umum",                     "biaya": 19997900},
        {"no": 2, "nama": "Alfiansyah",         "jabatan": "Kepala SPI",                        "biaya": 20997900},
        {"no": 3, "nama": "Rismawati",           "jabatan": "Ketua Kelompok Fungsional Auditor", "biaya": 12387900},
    ],
    "ttd_manajer_sek": "Abdul Ramli",
    "ttd_spv_sek":     "Ganden Aditera. I",
    "ttd_dirut":       "Dr. Saharuddin, M.M",
}

# ══════════════════════════════════════════════════════
# GENERATE & BUKA
# ══════════════════════════════════════════════════════
OUT = "spd_test.pdf"

print("⏳ Generating SPD (Surat Penyediaan Dana)...")
pdf_bytes = generate_spd(DATA).read()

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
