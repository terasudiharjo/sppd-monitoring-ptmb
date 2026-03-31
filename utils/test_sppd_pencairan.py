"""
test_sppd_pencairan.py
======================
Script debug lokal untuk SPPD Tanda Terima Pencairan PDF.
Run: python test_sppd_pencairan.py
→ Generate sppd_pencairan_test.pdf di folder ini, lalu auto-buka.

CARA PAKAI:
1. Taruh file ini di folder yang sama dengan pdf_generator.py
2. Run: python test_sppd_pencairan.py
3. PDF langsung terbuka
4. Edit pdf_generator.py → run lagi → lihat perubahan
"""

import os
import subprocess
import sys
from datetime import date
from pdf_generator import generate_sppd_pencairan

# ══════════════════════════════════════════════════════
# DATA TEST — edit sesuai kebutuhan debug
# ══════════════════════════════════════════════════════
DATA = {
    "nama_pejabat":      "Direktur Umum PTMB",
    "nomor_spd":         "0012/1421002/10a-I/II/2026-O",
    "tanggal":           date(2026, 2, 2),
    "tempat_tujuan":     "Semarang",
    "tgl_berangkat":     date(2026, 2, 10),
    "tgl_kembali":       date(2026, 2, 13),
    "lama_hari":         4,
    "nama_penerima":     "Purnamawati, S.E",
    "jabatan_penerima":  "Direktur Umum PTMB",
    "uang_harian":       1575000,
    "uang_representasi": 150000,
    "biaya_penginapan":  525000,    # 30% dari plafon (belum dibayar)
    "ttd_dirut":         "Dr. Saharuddin, M.M",
}

# ══════════════════════════════════════════════════════
# GENERATE & BUKA
# ══════════════════════════════════════════════════════
OUT = "sppd_pencairan_test.pdf"

print("⏳ Generating SPPD Tanda Terima Pencairan...")
pdf_bytes = generate_sppd_pencairan(DATA).read()

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
