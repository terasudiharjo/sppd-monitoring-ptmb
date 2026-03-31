"""
test_pernyataan_biaya.py
========================
Script debug lokal untuk Pernyataan Pengeluaran Biaya Riil PDF.
Run: python test_pernyataan_biaya.py
→ Generate pernyataan_biaya_test.pdf di folder ini, lalu auto-buka.

CARA PAKAI:
1. Taruh file ini di folder yang sama dengan pdf_generator.py
2. Run: python test_pernyataan_biaya.py
3. PDF langsung terbuka
4. Edit pdf_generator.py → run lagi → lihat perubahan
"""

import os
import subprocess
import sys
from datetime import date
from pdf_generator import generate_pernyataan_biaya

# ══════════════════════════════════════════════════════
# DATA TEST — edit sesuai kebutuhan debug
# ══════════════════════════════════════════════════════
DATA = {
    "nomor_surat":            "015/1421002/10a-I/II/2026",
    "nomor_spd":              "0012/1421002/10a-I/II/2026-O",
    "tanggal_spd":            date(2026, 2, 2),
    "nama":                   "Purnamawati, S.E",
    "jabatan":                "Direktur Umum PTMB",
    "nomor_surat_tugas":      "040/1421002/10a-I/II/2026-F",
    "tempat_kegiatan":        "Semarang",
    "tanggal_berangkat":      date(2026, 2, 10),
    "tanggal_kembali":        date(2026, 2, 13),
    "biaya_perjalanan":       6900000,
    "biaya_penginapan":       4800000,
    "biaya_transport":        4047900,
    "biaya_lain":             4250000,
    "grand_total":            19997900,
    "tanggal_ttd":            date(2026, 2, 18),
    "ttd_mengetahui_jabatan": "Direktur Umum",
    "ttd_mengetahui_nama":    "PURNAMAWATI, S.E",
    "nama_penerima":          "PURNAMAWATI, S.E",
}

# ══════════════════════════════════════════════════════
# GENERATE & BUKA
# ══════════════════════════════════════════════════════
OUT = "pernyataan_biaya_test.pdf"

print("⏳ Generating Pernyataan Pengeluaran Biaya Riil...")
pdf_bytes = generate_pernyataan_biaya(DATA).read()

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
