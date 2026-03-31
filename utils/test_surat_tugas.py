"""
test_surat_tugas.py
===================
Script debug lokal untuk Surat Perintah Tugas PDF.
Run: python test_surat_tugas.py
→ Generate surat_tugas_test.pdf di folder ini, lalu auto-buka.

CARA PAKAI:
1. Taruh file ini di folder yang sama dengan pdf_generator.py
2. Run: python test_surat_tugas.py
3. PDF langsung terbuka
4. Edit pdf_generator.py → run lagi → lihat perubahan
"""

import os
import subprocess
import sys
from datetime import date
from pdf_generator import generate_surat_tugas

# ══════════════════════════════════════════════════════
# DATA TEST — edit sesuai kebutuhan debug
# ══════════════════════════════════════════════════════
DATA = {
    "nomor":    "040/1421002/10a-I/II/2026-F",
    "tanggal":  date(2026, 2, 2),
    "pembuka":  "Surat dari Praktisi Auditor Internal Bersertifikat Kompetensi "
                "Nomor: 002/STTD-PPAK/2026 tanggal 15 Januari 2026",
    "peserta": [
        {"nama": "Purnamawati, S.E",    "nip": "-",          "jabatan": "Direktur Umum",                           "divisi": "-"},
        {"nama": "Alfiansyah",          "nip": "459.010408", "jabatan": "Kepala Satuan Pengawas Intern",            "divisi": "SPI"},
        {"nama": "Rismawati",           "nip": "459.010512", "jabatan": "Ketua Kelompok Fungsional Auditor",        "divisi": "SPI"},
    ],
    "tujuan":   "Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal.",
    "durasi":   4,
    "waktu":    "Selasa - Jumat, 10 - 13 Februari 2026",
    "tempat":   "Semarang",
    "target":   "Wajib Untuk Menyerahkan Laporan Perjalanan Dinas Paling Lambat 5 Hari Kerja "
                "Setelah Selesai Melaksanakan Perjalanan Dinas.",
    "ttd_nama": "Dr. SAHARUDDIN, M.M.",
}

# ══════════════════════════════════════════════════════
# GENERATE & BUKA
# ══════════════════════════════════════════════════════
OUT = "surat_tugas_test.pdf"

print("⏳ Generating Surat Perintah Tugas...")
pdf_bytes = generate_surat_tugas(DATA).read()

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
