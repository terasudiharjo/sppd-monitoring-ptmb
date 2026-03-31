"""
test_visum.py
=============
Script debug lokal untuk visum PDF.
Run: python test_visum.py
→ Generate visum.pdf di folder ini, lalu auto-buka.

CARA PAKAI:
1. Taruh file ini di folder yang sama dengan pdf_generator.py
2. Run: python test_visum.py
3. PDF langsung terbuka
4. Edit pdf_generator.py → run lagi → lihat perubahan
"""

import os
import subprocess
import sys
from datetime import date
from pdf_generator import generate_visum

# ══════════════════════════════════════════════════════
# DATA TEST — edit sesuai kebutuhan debug
# ══════════════════════════════════════════════════════
DATA = {
    "nomor":            "0002/1421002/10a-I/I/2026-J",
    "tanggal":          date(2026, 1, 2),
    "nama_pegawai":     "Fachrial Arifin",
    "jabatan":          "Manajer Keuangan",
    "maksud":           "Dalam Rangka Penandatanganan Rekapitulasi Tagihan Rekening Air Bulan Desember 2025 untuk TNI-AD, TNI-AU, TNI-AL, dan POLDA Kaltim",
    "alat_angkutan":    "Umum",
    "tempat_berangkat": "Balikpapan",
    "tempat_tujuan":    "Samarinda",
    "lama_hari":        "1 (Satu) hari",
    "tgl_berangkat":    date(2026, 1, 6),
    "tgl_kembali":      date(2026, 1, 6),
    "peserta_ikut":     [
        "Sayid Zain Ashad Yahya (Staf Perbendaharaan)",
    ],
    "kode_rkap":        "",
    "ttd_nama":         "Dr. SAHARUDDIN, M.M.",
}

# ══════════════════════════════════════════════════════
# GENERATE & BUKA
# ══════════════════════════════════════════════════════
OUT = "visum_test.pdf"

print("⏳ Generating visum...")
pdf_bytes = generate_visum(DATA).read()

with open(OUT, "wb") as f:
    f.write(pdf_bytes)

print(f"✅ Saved: {OUT}")

# Auto-buka PDF
if sys.platform == "win32":
    os.startfile(OUT)
elif sys.platform == "darwin":
    subprocess.run(["open", OUT])
else:
    subprocess.run(["xdg-open", OUT])

print("📄 PDF dibuka! Edit pdf_generator.py → run lagi.")