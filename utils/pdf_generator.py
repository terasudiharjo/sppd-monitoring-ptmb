"""
pdf_generator.py - SPPD PTMB Balikpapan
========================================
Generate PDF untuk semua dokumen perjalanan dinas PTMB.

CARA ADJUST POSISI:
- Semua ukuran pakai cm (misal: 2.5*cm, 3.0*cm)
- x = horizontal, dari kiri halaman
- y = vertikal, dari BAWAH halaman (ReportLab convention)
- Naikkan y → teks naik. Turunkan y → teks turun.
- Untuk adjust margin: edit MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B

DOKUMEN:
1. generate_surat_tugas(data)         → Surat Perintah Tugas (2 halaman)
2. generate_spd(data)                 → Surat Penyediaan Dana (1 halaman)
3. generate_visum(data)               → Visum/SPPD Lembaran I & II (2 halaman)
4. generate_sppd_pencairan(data)      → SPPD Tanda Terima Pencairan (1 halaman)
5. generate_sppd_realisasi(data)      → SPPD Tanda Terima Realisasi (1 halaman)
6. generate_pernyataan_biaya(data)    → Pernyataan Pengeluaran Biaya Riil (1 halaman)
"""

import os
from io import BytesIO
from datetime import date, datetime

from numpy import pi
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas

F4 = (215*mm, 330*mm)  # ukuran kertas F4 (Folio) dalam mm

# ══════════════════════════════════════════════════════════════
# KONSTANTA LAYOUT
# Ubah nilai di sini untuk adjust margin global
# ══════════════════════════════════════════════════════════════
PAGE_W, PAGE_H = F4          # 610 x 936 pt

MARGIN_L = 1.5 * cm          # margin kiri
MARGIN_R = 1.5 * cm          # margin kanan
MARGIN_T = 1.5 * cm          # margin atas
MARGIN_B = 1.5 * cm          # margin bawah (ruang footer)

CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# Font utama dokumen (sesuai template Word asli: Gentium Basic / Bookman Old Style)
# ReportLab built-in: Helvetica (mirip cukup, tidak perlu install font tambahan)
FONT_NORMAL = "Helvetica"
FONT_BOLD   = "Helvetica-Bold"
FONT_SIZE   = 10   # font size default isi dokumen

# Path logo — logo_ptmb.png ada di folder assets/ di root project
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "logo_ptmb.png")

# ══════════════════════════════════════════════════════════════
# HELPER: FORMAT
# ══════════════════════════════════════════════════════════════
BULAN_ID = {
    1:"Januari", 2:"Februari", 3:"Maret", 4:"April",
    5:"Mei", 6:"Juni", 7:"Juli", 8:"Agustus",
    9:"September", 10:"Oktober", 11:"November", 12:"Desember"
}

def fmt_tgl(d) -> str:
    """date → '5 Januari 2026'"""
    if not d: return ""
    if isinstance(d, str):
        try: d = datetime.strptime(d, "%Y-%m-%d").date()
        except: return d
    return f"{d.day} {BULAN_ID[d.month]} {d.year}"

BULAN_SINGKAT = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"
}

def fmt_tgl_short(d) -> str:
    """date → '10-Feb-2026'"""
    if not d: return ""
    if isinstance(d, str):
        try: d = datetime.strptime(d, "%Y-%m-%d").date()
        except: return d
    return f"{d.day:02d}-{BULAN_SINGKAT[d.month]}-{d.year}"

def fmt_rp(n) -> str:
    """angka → 'Rp 19,997,900'"""
    if not n: return "Rp -"
    return "Rp {:,.0f}".format(n).replace(",", ".")

def fmt_rp2(n) -> str:
    """angka → 'Rp.19,997,900' (format tanda terima)"""
    if not n: return "Rp -"
    return "Rp.{:,.0f}".format(n).replace(",", ".")

# ══════════════════════════════════════════════════════════════
# HELPER: KOP SURAT (dipakai Surat Tugas & Pernyataan Biaya)
# ══════════════════════════════════════════════════════════════
def draw_kop(c: canvas.Canvas) -> float:
    """
    Gambar kop surat PTMB: logo kiri + nama perusahaan + 2 garis bawah.
    Return: posisi y setelah kop (siap untuk konten).

    ADJUST KOP:
    - logo_size: ubah ukuran logo
    - nama_x: jarak nama perusahaan dari logo
    - Posisi garis: edit line_y1, line_y2
    """
    y_top = PAGE_H - MARGIN_T

    logo_size = 2.3 * cm                        # ← ukuran logo
    logo_x    = MARGIN_L
    logo_y    = y_top - logo_size

    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, logo_x, logo_y,
                    width=logo_size, height=logo_size,
                    preserveAspectRatio=True, mask="auto")

    # Nama perusahaan — rata tengah di area kanan logo
    nama_x      = logo_x + logo_size + 0.5 * cm
    text_center = nama_x + (PAGE_W - MARGIN_R - nama_x) / 2
    c.setFont(FONT_BOLD, 20)
    c.setFillColor(colors.black)
    c.drawCentredString(text_center, y_top - 0.82 * cm, "PERUSAHAAN UMUM DAERAH")
    c.drawCentredString(text_center, y_top - 1.55 * cm, "TIRTA MANUNTUNG BALIKPAPAN")

    # Garis bawah kop (2 garis: tebal + tipis)
    line_y1 = y_top - logo_size - 0.25 * cm     # ← posisi garis tebal
    line_y2 = line_y1 - 0.12 * cm               # ← posisi garis tipis
    c.setStrokeColor(colors.black)
    c.setLineWidth(2.5)
    c.line(MARGIN_L, line_y1, PAGE_W - MARGIN_R, line_y1)
    c.setLineWidth(0.8)
    c.line(MARGIN_L, line_y2, PAGE_W - MARGIN_R, line_y2)

    return line_y2 - 0.4 * cm  # y mulai konten

# ══════════════════════════════════════════════════════════════
# HELPER: KOP BOX SEDERHANA (dipakai Visum & SPD)
# ══════════════════════════════════════════════════════════════
def draw_kop_box(c: canvas.Canvas, y_top: float, right_content_fn=None) -> float:
    """
    Kop kotak kiri (tanpa logo) untuk Visum & SPD.
    right_content_fn: fungsi(c, x, y) untuk menggambar konten sisi kanan.
    Return: y setelah kop.
    """
    box_x = MARGIN_L
    box_w = 5.2 * cm                # ← lebar box kiri
    box_h = 2.5 * cm                # ← tinggi box kiri
    box_y = y_top - box_h

    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(box_x, box_y, box_w, box_h)

    c.setFont(FONT_BOLD, 8.5)
    c.setFillColor(colors.black)
    c.drawCentredString(box_x + box_w/2, box_y + box_h - 0.6*cm, "PERUMDA TIRTA MANUNTUNG")
    c.drawCentredString(box_x + box_w/2, box_y + box_h - 1.1*cm, "BALIKPAPAN")
    c.setFont(FONT_NORMAL, 7.5)
    c.drawCentredString(box_x + box_w/2, box_y + box_h - 1.6*cm, "Jln. Ruhui Rahayu I")
    c.drawCentredString(box_x + box_w/2, box_y + box_h - 1.95*cm, "Tlp.(0542) 7218829/7218830")

    if right_content_fn:
        right_content_fn(c, box_x + box_w + 0.5*cm, y_top)

    return box_y - 0.4 * cm

# ══════════════════════════════════════════════════════════════
# HELPER: FOOTER (Graha Tirta)
# ══════════════════════════════════════════════════════════════
def draw_footer(c: canvas.Canvas):
    """Footer alamat bawah halaman."""
    fy = MARGIN_B - 0.3 * cm
    c.setLineWidth(0.5)
    c.line(MARGIN_L, fy + 1.2*cm, PAGE_W - MARGIN_R, fy + 1.2*cm)

    c.setFont(FONT_BOLD, 8)
    c.setFillColor(colors.black)
    c.drawCentredString(PAGE_W/2, fy + 0.85*cm, "GRAHA TIRTA")

    c.setFont(FONT_NORMAL, 7.5)
    c.setFillColor(colors.black)
    c.drawCentredString(PAGE_W/2, fy + 0.5*cm,
        "Jl. Ruhui Rahayu I Kelurahan Sepinggan, Kecamatan Balikpapan Selatan, Kalimantan Timur")
    c.drawCentredString(PAGE_W/2, fy + 0.2*cm,
        "Telp. (0542) 7218831 - 7218832, Fax. (0542) 7218863")

    # Baris email+website: label hitam, link biru
    link_parts = [
        ("Email : ",                          colors.black),
        ("humas@tirtamanuntung.co.id",        colors.HexColor("#0000CC")),
        ("  -  ",                             colors.black),
        ("https://www.tirtamanuntung.co.id",  colors.HexColor("#0000CC")),
    ]
    total_w = sum(c.stringWidth(t, FONT_NORMAL, 7.5) for t, _ in link_parts)
    lx = PAGE_W/2 - total_w/2
    for txt, clr in link_parts:
        c.setFillColor(clr)
        c.drawString(lx, fy - 0.1*cm, txt)
        lx += c.stringWidth(txt, FONT_NORMAL, 7.5)
    c.setFillColor(colors.black)

# ══════════════════════════════════════════════════════════════
# HELPER: TTD BLOCK
# ══════════════════════════════════════════════════════════════
def draw_ttd(c, x, y, label_atas, label_bawah, nama, garis_panjang=4.5*cm):
    """
    Gambar satu blok TTD.
    label_atas: misal 'Mengetahui/Menyetujui :'
    label_bawah: misal 'Direktur Utama,'
    nama: nama yang ditandatangani (di-underline)
    """
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(x, y, label_atas)
    if label_bawah:
        c.drawString(x, y - 0.4*cm, label_bawah)
    # Ruang TTD
    nama_y = y - 2.5*cm
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawString(x, nama_y, nama)
    c.setLineWidth(0.8)
    c.line(x, nama_y - 2, x + garis_panjang, nama_y - 2)

# ══════════════════════════════════════════════════════════════
# HELPER: WRAP TEXT dalam kotak
# ══════════════════════════════════════════════════════════════
def draw_wrapped(c, text, x, y, max_w, font=FONT_NORMAL, size=FONT_SIZE, leading=14):
    """Gambar teks dengan word-wrap, return y setelah teks."""
    style = ParagraphStyle("s", fontName=font, fontSize=size,
                           leading=leading, alignment=4)
    p = Paragraph(text, style)
    w, h = p.wrap(max_w, 500)
    p.drawOn(c, x, y - h)
    return y - h

# ══════════════════════════════════════════════════════════════
# 1. SURAT TUGAS
# ══════════════════════════════════════════════════════════════
def generate_surat_tugas(data: dict) -> BytesIO:
    """
    data = {
        "nomor": "040/1421002/10a-I/II/2026-F",
        "tanggal": date(2026, 2, 2),
        "pembuka": "Surat dari Praktisi Auditor Internal Bersertifikat Kompetensi ...",
        "peserta": [
            {"nama": "Purnamawati, S.E", "nip": "-", "jabatan": "Direktur Umum", "divisi": "-"},
            {"nama": "Alfiansyah", "nip": "459.010408", "jabatan": "Kepala Satuan Pengawas Intern", "divisi": "SPI"},
        ],
        "tujuan":   "Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal.",
        "durasi":   4,
        "waktu":    "Selasa - Jumat, 10 - 13 Februari 2026",
        "tempat":   "Semarang",
        "target":   "Wajib Untuk Menyerahkan Laporan Perjalanan Dinas ...",
        "ttd_nama": "Dr. SAHARUDDIN, M.M.",
    }
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=F4)
    for page in [1, 2]:
        _surat_tugas_halaman(c, data, page)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _surat_tugas_halaman(c, data, page):
    y = draw_kop(c)
    y -= 0.6 * cm

    # Judul
    c.setFont(FONT_BOLD, 13)
    c.drawCentredString(PAGE_W/2, y, "SURAT PERINTAH TUGAS")
    y -= 0.35 * cm
    jw = 5.8 * cm
    c.setLineWidth(1.5)
    c.line(PAGE_W/2 - jw/2, y, PAGE_W/2 + jw/2, y)
    y -= 0.5 * cm

    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawCentredString(PAGE_W/2, y, f"Nomor : {data.get('nomor','')}")
    y -= 0.65 * cm

    # Paragraf pembuka
    pembuka = f"Memperhatikan {data.get('pembuka','')}, Direktur Utama Perumda Tirta Manuntung Balikpapan,"
    y = draw_wrapped(c, pembuka, MARGIN_L, y, CONTENT_W)
    y -= 0.5 * cm

    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(PAGE_W/2, y, "MEMERINTAHKAN :")
    y -= 0.45 * cm

    # Tabel peserta
    y = _tabel_peserta_st(c, data.get("peserta", []), y)
    y -= 0.45 * cm

    # Detail perjalanan
    lbl_w = 5.5 * cm
    val_x = MARGIN_L + lbl_w + 0.4*cm
    val_w = CONTENT_W - lbl_w - 0.4*cm

    rows = [
        ("Tujuan Perjalanan Dinas",  data.get("tujuan","")),
        ("Durasi Perjalanan Dinas",  f"{data.get('durasi','')} Hari"),
        ("Waktu Pelaksanaan",        data.get("waktu","")),
        ("Tempat Kegiatan",          data.get("tempat","")),
    ]
    for lbl, val in rows:
        c.setFont(FONT_NORMAL, FONT_SIZE)
        c.drawString(MARGIN_L, y, lbl)
        c.drawString(MARGIN_L + lbl_w, y, ":")
        c.setFont(FONT_BOLD, FONT_SIZE)
        c.drawString(val_x, y, val)
        y -= 0.5 * cm

    # Target kinerja (2 baris label)
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(MARGIN_L, y,           "Target Kinerja atau hasil")
    c.drawString(MARGIN_L, y - 0.42*cm, "yang akan dicapai")
    c.drawString(MARGIN_L + lbl_w, y,   ":")

    # Nilai target: manual word-wrap supaya baseline baris pertama sejajar ":"
    c.setFont(FONT_BOLD, FONT_SIZE)
    target_words = data.get("target", "").split()
    tgt_lines, cur = [], []
    for word in target_words:
        test = " ".join(cur + [word])
        if c.stringWidth(test, FONT_BOLD, FONT_SIZE) <= val_w:
            cur.append(word)
        else:
            tgt_lines.append(" ".join(cur))
            cur = [word]
    if cur:
        tgt_lines.append(" ".join(cur))
    line_gap = 0.45 * cm
    for k, line in enumerate(tgt_lines):
        c.drawString(val_x, y - k * line_gap, line)
    y -= len(tgt_lines) * line_gap
    y -= 0.4 * cm

    # Blok TTD kanan
    ttd_x = PAGE_W / 2 + 0.5 * cm
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(ttd_x, y,            "Dikeluarkan di  :  Balikpapan")
    c.drawString(ttd_x, y - 0.42*cm, f"Pada Tanggal    :  {fmt_tgl(data.get('tanggal'))}")
    y -= 1.0 * cm

    c.setFont(FONT_BOLD, FONT_SIZE)
    cx = ttd_x + 2.5 * cm
    c.drawCentredString(cx, y,            "PERUSAHAAN UMUM DAERAH")
    c.drawCentredString(cx, y - 0.42*cm, "TIRTA MANUNTUNG BALIKPAPAN")
    c.drawCentredString(cx, y - 0.84*cm, "DIREKTUR UTAMA")
    y -= 2.8 * cm

    nama = data.get("ttd_nama", "")
    nw   = c.stringWidth(nama, FONT_BOLD, FONT_SIZE)
    nx   = cx - nw/2
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawString(nx, y, nama)
    c.setLineWidth(0.8)
    c.line(nx, y - 2, nx + nw, y - 2)

    # Tabel paraf (halaman 2)
    if page == 2:
        _tabel_paraf_st(c, y - 1.5*cm)

    draw_footer(c)


def _tabel_peserta_st(c, peserta, y):
    """Tabel NO | NAMA | NIK | JABATAN | DIVISI untuk Surat Tugas."""
    cw_no   = 0.8  * cm
    cw_nama = 4.5  * cm
    cw_nik  = 2.5  * cm
    cw_jab  = 4.2  * cm
    cw_div  = CONTENT_W - cw_no - cw_nama - cw_nik - cw_jab  # sisa → divisi
    cw = [cw_no, cw_nama, cw_nik, cw_jab, cw_div]

    rh_hdr  = 0.65 * cm
    pad     = 0.15 * cm
    headers = ["NO", "NAMA", "NIK", "JABATAN", "DIVISI"]
    wrap_style = ParagraphStyle("tw", fontName=FONT_NORMAL, fontSize=9, leading=11)

    # Header row
    x = MARGIN_L
    for w, h in zip(cw, headers):
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        c.rect(x, y - rh_hdr, w, rh_hdr, fill=1)
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD, 9)
        c.drawCentredString(x + w/2, y - rh_hdr + 0.2*cm, h)
        x += w
    y -= rh_hdr

    # Data rows — tinggi dinamis sesuai wrap jabatan/divisi
    for i, p in enumerate(peserta, 1):
        jab_txt = p.get("jabatan", "")
        div_txt = p.get("divisi", "-")

        # Hitung tinggi cell yang butuh wrap
        p_jab = Paragraph(jab_txt, wrap_style)
        _, h_jab = p_jab.wrap(cw_jab - 2*pad, 200)
        p_div = Paragraph(div_txt, wrap_style)
        _, h_div = p_div.wrap(cw_div - 2*pad, 200)
        rh = max(0.65*cm, h_jab + 2*pad, h_div + 2*pad)

        x = MARGIN_L
        for j, w in enumerate(cw):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(colors.black)

            if j == 0:          # NO — center
                c.setFont(FONT_NORMAL, 9)
                c.drawCentredString(x + w/2, y - rh/2 - 3, str(i))
            elif j == 1:        # NAMA — left
                c.setFont(FONT_NORMAL, 9)
                c.drawString(x + pad, y - rh/2 - 3, p.get("nama", ""))
            elif j == 2:        # NIK — center
                c.setFont(FONT_NORMAL, 9)
                c.drawCentredString(x + w/2, y - rh/2 - 3, p.get("nip", "-"))
            elif j == 3:        # JABATAN — wrap, vertical center
                pg = Paragraph(jab_txt, wrap_style)
                _, h_pg = pg.wrap(w - 2*pad, rh)
                draw_y = (y - rh) + (rh - h_pg) / 2
                pg.drawOn(c, x + pad, draw_y)
            else:               # DIVISI — wrap, vertical center
                pg = Paragraph(div_txt, wrap_style)
                _, h_pg = pg.wrap(w - 2*pad, rh)
                draw_y = (y - rh) + (rh - h_pg) / 2
                pg.drawOn(c, x + pad, draw_y)
            x += w
        y -= rh
    return y


def _tabel_paraf_st(c, y):
    """Tabel paraf SPV/Manajer/Direktur di pojok kiri bawah halaman 2."""
    # Warna header tabel paraf
    HDR_COLOR = colors.HexColor("#1B3A8C")   # ← ganti warna header di sini
    TXT_COLOR = colors.white

    cw = [3.0*cm, 3.0*cm, 1.6*cm]
    rh = 0.9 * cm

    headers = ["PERUMDA TIRTA\nMANUNTUNG\nBALIKPAPAN", "DIVISI / JABATAN", "PARAF"]
    rows = [
        ("SPV",      "KESEKRETARIATAN\n& HUKUM"),
        ("MANAJER",  "SEKRETARIS\nPERUSAHAAN"),
        ("DIREKTUR", "UMUM"),
        ("DIREKTUR", "TEKNIK"),
        ("DIREKTUR", "OPERASIONAL"),
    ]

    # Header
    x = MARGIN_L
    hdr_h = 1.2 * cm
    for w, h in zip(cw, headers):
        c.setFillColor(HDR_COLOR)
        c.setStrokeColor(HDR_COLOR)
        c.rect(x, y - hdr_h, w, hdr_h, fill=1)
        c.setFillColor(TXT_COLOR)
        c.setFont(FONT_BOLD, 7)
        lines = h.split("\n")
        for k, line in enumerate(lines):
            c.drawCentredString(x + w/2, y - 0.35*cm - k*0.28*cm, line)
        x += w
    y -= hdr_h

    # Rows
    for col1, col2 in rows:
        x = MARGIN_L
        for w, v in zip(cw, [col1, col2, ""]):
            c.setFillColor(colors.white)
            c.setStrokeColor(HDR_COLOR)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(HDR_COLOR)
            c.setFont(FONT_BOLD, 7.5)
            lines = v.split("\n")
            for k, line in enumerate(lines):
                c.drawCentredString(x + w/2, y - 0.35*cm - k*0.3*cm, line)
            x += w
        y -= rh


# ══════════════════════════════════════════════════════════════
# 2. SPD (Surat Penyediaan Dana)
# ══════════════════════════════════════════════════════════════
def generate_spd(data: dict) -> BytesIO:
    """
    data = {
        "nomor": "0012/1421002/10a-I/II/2026-O",
        "tanggal": date(2026, 2, 2),
        "lokasi_label": "Biaya Perjalanan Dinas di Luar Daerah KALTIM",
        "tahun": 2026,
        "kategori": [
            {"no": 1, "uraian": "Direksi",                    "total": 19997900, "kode": "96.08.41"},
            {"no": 2, "uraian": "Bagian Administrasi/Keuangan","total": 33385800, "kode": "96.08.42"},
            {"no": 3, "uraian": "Bagian Teknik",               "total": 0,        "kode": "96.08.43"},
            {"no": 4, "uraian": "Dewan Pengawas",              "total": 0,        "kode": "96.08.30"},
            {"no": 5, "uraian": "Bantuan",                     "total": 0,        "kode": "96.08.92"},
        ],
        "grand_total": 53383700,
        "peserta": [
            {"no": 1, "nama": "Purnamawati, S.E",  "jabatan": "Direktur Umum",                      "biaya": 19997900},
            {"no": 2, "nama": "Alfiansyah",         "jabatan": "Kepala SPI",                         "biaya": 20997900},
            {"no": 3, "nama": "Rismawati",           "jabatan": "Ketua Kelompok Fungsional Auditor",  "biaya": 12387900},
        ],
        "ttd_manajer_sek":  "Abdul Ramli",
        "ttd_spv_sek":      "Ganden Aditera. I",
        "ttd_dirut":        "Dr. Saharuddin, M.M",
    }
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=F4)
    _draw_spd(c, data)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _draw_spd(c, data):
    y = PAGE_H - MARGIN_T

    # Kode unit — kanan atas
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawRightString(PAGE_W - MARGIN_R, y, "KODE UNIT :   00.12.01")
    y -= 0.5 * cm

    # Judul
    c.setFont(FONT_BOLD, 12)
    c.drawCentredString(PAGE_W/2, y, "SURAT PENYEDIAAN DANA (SPD)")
    y -= 0.3 * cm
    jw = 7.0 * cm
    c.setLineWidth(1.2)
    c.line(PAGE_W/2 - jw/2, y, PAGE_W/2 + jw/2, y)
    y -= 0.45 * cm

    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawCentredString(PAGE_W/2, y, f"Nomor :  {data.get('nomor','')}")
    y -= 0.7 * cm

    # ── TABEL ATAS: Kategori + Taksiran Harga + Kode Perk ──
    # Kolom: NO | URAIAN | TAKSIRAN HARGA | KODE PERK  → total = CONTENT_W
    cw_top = [1.2*cm, 10.3*cm, 4.5*cm, 2.5*cm]
    rh = 0.65 * cm

    def tbl_row(vals, bold=False, align_last_right=True, header=False):
        nonlocal y
        x = MARGIN_L
        for k, (w, v) in enumerate(zip(cw_top, vals)):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.4)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(colors.black)
            c.setFont(FONT_BOLD if bold else FONT_NORMAL, FONT_SIZE)
            if header:
                c.drawCentredString(x + w/2, y - rh + 0.18*cm, str(v))
            elif k == 0:
                c.drawCentredString(x + w/2, y - rh + 0.18*cm, str(v))
            elif k == 2 and align_last_right:
                c.drawRightString(x + w - 0.2*cm, y - rh + 0.18*cm, str(v))
            else:
                c.drawString(x + 0.2*cm, y - rh + 0.18*cm, str(v))
            x += w
        y -= rh

    # Header tabel atas
    tbl_row(["No.", "Uraian", "Taksiran Harga", "Kode Perk."], bold=True, header=True)

    # Row judul lokasi (merge-style, no border kiri-kanan-dalam)
    c.setFont(FONT_BOLD, FONT_SIZE)
    tbl_w = sum(cw_top)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.4)
    c.rect(MARGIN_L, y - rh, tbl_w, rh)
    c.drawString(MARGIN_L + 0.3*cm, y - rh + 0.18*cm,
                 data.get("lokasi_label", "Biaya Perjalanan Dinas"))
    y -= rh

    # Rows kategori
    for kat in data.get("kategori", []):
        total_str = fmt_rp(kat.get("total", 0)) if kat.get("total", 0) else "---"
        tbl_row([str(kat.get("no","")), kat.get("uraian",""), total_str, kat.get("kode","")])

    # Row grand total — No+Uraian di-merge, teks "JUMLAH"
    merged_top = cw_top[0] + cw_top[1]
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.4)
    c.setFillColor(colors.white)
    c.rect(MARGIN_L, y - rh, merged_top, rh, fill=1)
    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(MARGIN_L + merged_top/2, y - rh + 0.18*cm, "JUMLAH")
    c.setFillColor(colors.white)
    c.rect(MARGIN_L + merged_top, y - rh, cw_top[2], rh, fill=1)
    c.setFillColor(colors.black)
    c.drawRightString(MARGIN_L + merged_top + cw_top[2] - 0.2*cm, y - rh + 0.18*cm,
                      fmt_rp(data.get("grand_total", 0)))
    c.setFillColor(colors.white)
    c.rect(MARGIN_L + merged_top + cw_top[2], y - rh, cw_top[3], rh, fill=1)
    c.setFillColor(colors.black)
    y -= rh

    y -= 0.5 * cm

    # ── KETERANGAN ──
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawString(MARGIN_L, y, "Keterangan :")
    y -= 0.38 * cm
    c.setFont(FONT_NORMAL, FONT_SIZE)
    lokasi_label = data.get("lokasi_label", "")
    tahun = data.get("tahun", "")
    c.drawString(MARGIN_L, y, f"({lokasi_label} {tahun})")
    y -= 1.3 * cm

    # ── TABEL BAWAH: No | Nama | Jabatan | Biaya SPPD  → total = CONTENT_W
    cw_bot = [1.0*cm, 5.5*cm, 7.5*cm, 4.5*cm]

    def tbl_bot_row(vals, bold=False, header=False):
        nonlocal y
        x = MARGIN_L
        for k, (w, v) in enumerate(zip(cw_bot, vals)):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.4)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(colors.black)
            c.setFont(FONT_BOLD if bold else FONT_NORMAL, FONT_SIZE)
            if header:
                c.drawCentredString(x + w/2, y - rh + 0.18*cm, str(v))
            elif k == 0:
                c.drawCentredString(x + w/2, y - rh + 0.18*cm, str(v))
            elif k == 3:
                c.drawRightString(x + w - 0.2*cm, y - rh + 0.18*cm, str(v))
            else:
                c.drawString(x + 0.2*cm, y - rh + 0.18*cm, str(v))
            x += w
        y -= rh

    tbl_bot_row(["No", "Nama", "Jabatan", "Biaya SPPD"], bold=True, header=True)
    for p in data.get("peserta", []):
        tbl_bot_row([str(p.get("no","")), p.get("nama",""),
                     p.get("jabatan",""), fmt_rp(p.get("biaya",0))])
    # Row jumlah — No+Nama+Jabatan di-merge, teks "JUMLAH"
    total_peserta = sum(p.get("biaya", 0) for p in data.get("peserta", []))
    merged_bot = cw_bot[0] + cw_bot[1] + cw_bot[2]
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.4)
    c.setFillColor(colors.white)
    c.rect(MARGIN_L, y - rh, merged_bot, rh, fill=1)
    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(MARGIN_L + merged_bot/2, y - rh + 0.18*cm, "JUMLAH")
    c.setFillColor(colors.white)
    c.rect(MARGIN_L + merged_bot, y - rh, cw_bot[3], rh, fill=1)
    c.setFillColor(colors.black)
    c.drawRightString(MARGIN_L + merged_bot + cw_bot[3] - 0.2*cm, y - rh + 0.18*cm,
                      fmt_rp(total_peserta))
    y -= rh

    y -= 1.3 * cm

    # ── TTD ──
    # Kolom: kiri = Diketahui Oleh, tengah = Mengetahui/Dirut, kanan = Dibuat Oleh
    col_w   = CONTENT_W / 3
    col1_cx = MARGIN_L + col_w * 0.5        # kiri  : Diketahui Oleh
    col2_cx = MARGIN_L + col_w * 1.5        # tengah : Mengetahui / Dirut
    col3_cx = MARGIN_L + col_w * 2.5        # kanan  : Dibuat Oleh

    # Tanggal — rata tengah di kolom Dibuat Oleh (kanan)
    tgl = fmt_tgl(data.get("tanggal"))
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(col3_cx, y, f"Balikpapan, {tgl}")
    y -= 0.5 * cm

    # ── Baris 1: Diketahui Oleh (kiri) + Dibuat Oleh (kanan), sejajar ──
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawCentredString(col1_cx, y,            "Diketahui Oleh,")
    c.drawCentredString(col1_cx, y - 0.45*cm, "Manajer Sekretaris Perusahaan")
    c.drawCentredString(col3_cx, y,            "Dibuat Oleh,")
    c.drawCentredString(col3_cx, y - 0.45*cm, "Spv. Kesekretariatan & Hukum,")

    y -= 2.3 * cm  # ruang tanda tangan baris 1

    for cx, nama in [
        (col1_cx, data.get("ttd_manajer_sek", "")),
        (col3_cx, data.get("ttd_spv_sek",      "")),
    ]:
        c.setFont(FONT_BOLD, FONT_SIZE)
        nw = c.stringWidth(nama, FONT_BOLD, FONT_SIZE)
        c.drawCentredString(cx, y, nama)
        c.setLineWidth(0.7)
        c.line(cx - nw/2, y - 2, cx + nw/2, y - 2)

    y -= 1.5 * cm  # jarak antara baris TTD 1 dan 2

    # ── Baris 2: Mengetahui / Dirut (tengah), di bawah baris 1 ──
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawCentredString(col2_cx, y,            "Mengetahui,")
    c.drawCentredString(col2_cx, y - 0.45*cm, "Direktur Utama")

    y -= 2.3 * cm  # ruang tanda tangan baris 2

    nama_dirut = data.get("ttd_dirut", "")
    c.setFont(FONT_BOLD, FONT_SIZE)
    nw = c.stringWidth(nama_dirut, FONT_BOLD, FONT_SIZE)
    c.drawCentredString(col2_cx, y, nama_dirut)
    c.setLineWidth(0.7)
    c.line(col2_cx - nw/2, y - 2, col2_cx + nw/2, y - 2)

    # ── Kode dokumen — kotak di kanan bawah setelah TTD ──
    kode_text = "PTMBPP-QR-KEU.AKTN/01-04"
    box_w = 5.5 * cm
    box_h = 0.65 * cm
    box_x = PAGE_W - MARGIN_R - box_w
    box_y = y - 0.9 * cm
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.setFillColor(colors.white)
    c.rect(box_x, box_y, box_w, box_h, fill=1)
    c.setFillColor(colors.black)
    c.setFont(FONT_NORMAL, 8)
    c.drawCentredString(box_x + box_w / 2, box_y + 0.18 * cm, kode_text)


# ══════════════════════════════════════════════════════════════
# 3. VISUM / SPPD LEMBARAN I & II
# ══════════════════════════════════════════════════════════════
def generate_visum(data: dict) -> BytesIO:
    """
    data = {
        "nomor": "0016/1421002/10a-I/II/2026-J",
        "tanggal": date(2026, 2, 2),
        "nama_pegawai":    "Purnamawati, S.E",
        "jabatan":         "Direktur Umum",
        "pangkat_gol":     "",
        "biaya_sppd":      0,
        "maksud":          "Dalam Rangka Menghadiri Undangan Seminar ...",
        "alat_angkutan":   "Umum",
        "tempat_berangkat":"Balikpapan",
        "tempat_tujuan":   "Semarang",
        "lama_hari":       "4 (Empat) hari",
        "tgl_berangkat":   date(2026, 2, 10),
        "tgl_kembali":     date(2026, 2, 13),
        "peserta_ikut":    ["Alfiansyah (Kepala Satuan Pengawas Intern)", "Rismawati (Ketua Kelompok Fungsional Auditor)"],
        "kode_rkap":       "",
        "ttd_nama":        "Dr. SAHARUDDIN, M.M.",
    }
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=F4)
    _visum_lembaran1(c, data)
    c.showPage()
    _visum_lembaran2(c, data)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _visum_lembaran1(c, data):
    """
    Lembaran I Visum — layout mengikuti template asli PTMB.

    ADJUST GUIDE:
    - lbl_w      : lebar kolom label (kiri)
    - row_*_h    : tinggi tiap row (dalam cm)
    - val_indent : jarak teks dari tepi kiri kolom value
    - lbl_indent : jarak teks dari tepi kiri kolom label
    """
    y_top = PAGE_H - MARGIN_T

    # ── LAYOUT ──
    lbl_w    = 8.2 * cm          # ← lebar kolom label (garis tengah tabel)
    val_x    = MARGIN_L + lbl_w
    val_w    = PAGE_W - MARGIN_R - val_x
    full_w   = lbl_w + val_w     # lebar total tabel
    lbl_i    = 0.25 * cm         # indent teks label dari tepi kiri
    val_i    = 0.3  * cm         # indent teks value dari tepi kiri val_x
    fs       = 9                 # font size tabel
    line_gap = 0.5 * cm         # jarak antar baris dalam satu row

    # ── ROW KOP: bagian dari tabel, 2 kolom ──
    kop_h = 5.0 * cm
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(MARGIN_L, y_top - kop_h, lbl_w, kop_h)   # kotak kiri: nama perusahaan
    c.rect(val_x,    y_top - kop_h, val_w, kop_h)   # kotak kanan: lampiran/judul

    # Isi kiri: nama perusahaan
    c.setFont(FONT_BOLD, 9)
    c.setFillColor(colors.black)
    c.drawCentredString(MARGIN_L + lbl_w/2, y_top - 0.6*cm,  "PERUMDA TIRTA MANUNTUNG")
    c.drawCentredString(MARGIN_L + lbl_w/2, y_top - 1.05*cm, "BALIKPAPAN")
    c.setFont(FONT_NORMAL, 8)
    c.drawCentredString(MARGIN_L + lbl_w/2, y_top - 1.55*cm, "Jln. Ruhui Rahayu I")
    c.drawCentredString(MARGIN_L + lbl_w/2, y_top - 1.9*cm,  "Tlp.(0542) 7218829/7218830")

    # Isi kanan: lampiran, judul, nomor
    rx = val_x + 0.4*cm
    center_kanan_kop = val_x + (val_w/2)

    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(rx, y_top - 0.45*cm, "LAMPIRAN  :  I")
    c.drawString(rx, y_top - 0.95*cm, "LEMBARAN  :  I")
    c.setFont(FONT_BOLD, 11)
    c.drawCentredString(center_kanan_kop, y_top - 1.95*cm, "SURAT PERINTAH PERJALANAN DINAS")
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawCentredString(center_kanan_kop, y_top - 2.45*cm, "Kode Nomor :")
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(center_kanan_kop, y_top - 2.95*cm, f"Nomor :  {data.get('nomor','')}")

    y = y_top - kop_h   # y mulai dari bawah kop, langsung disambung tabel

    def draw_row(label_lines, value_lines, row_h_cm, wrap_idx=None):
        """
        Gambar satu row tabel visum.
        label_lines : list string, baris-baris label kiri
        value_lines : list string, baris-baris value kanan
                      prefix "**" = bold
        row_h_cm    : tinggi row dalam cm
        wrap_idx    : index di value_lines yang mau di-wrap (None = semua drawString biasa)
        """
        nonlocal y
        rh = row_h_cm * cm
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.4)
        c.rect(MARGIN_L, y - rh, lbl_w, rh)   # kotak label
        c.rect(val_x,    y - rh, val_w, rh)   # kotak value

        # Tulis label
        c.setFillColor(colors.black)
        for k, lp in enumerate(label_lines):
            c.setFont(FONT_NORMAL, fs)
            c.drawString(MARGIN_L + lbl_i, y - 0.38*cm - k * line_gap, lp)

        # Tulis value
        cur_y = y - 0.38*cm
        for k, vl in enumerate(value_lines):
            bold = vl.startswith("**")
            txt  = vl.replace("**", "")
            fn   = FONT_BOLD if bold else FONT_NORMAL
            if wrap_idx is not None and k == wrap_idx:
                # pakai Paragraph supaya teks wrap otomatis
                style = ParagraphStyle("vs", fontName=fn, fontSize=fs, leading=fs*1.3)
                p = Paragraph(txt, style)
                pw = val_w - val_i - 0.2*cm
                _, ph = p.wrap(pw, rh)
                p.drawOn(c, val_x + val_i, cur_y - ph + fs*0.35)
            else:
                c.setFont(fn, fs)
                c.drawString(val_x + val_i, cur_y, txt)
            cur_y -= line_gap

        y -= rh

    # ── ROW 1: Nama Pegawai ──
    draw_row(
        ["1.  Nama Pegawai Yang Melaksanakan",
         "    Perjalanan Dinas"],
        [f":  **{data.get('nama_pegawai','')}"],
        1.5,
    )

    # ── ROW 2: Jabatan / Biaya ──
    draw_row(
        ["2.  Jabatan/Divisi, Pangkat & Golongan, dan Biaya",
         "    Perjalanan Dinas Yang Diperintahkan"],
        [f"a.  Jabatan/Divisi  :  **{data.get('jabatan','')}",
         "b.  Pangkat & Gol  :",
         "c.  Biaya SPPD      :"],
        2.0,
    )

    # ── ROW 3: Maksud ──
    # Hitung tinggi dinamis pakai Paragraph wrap
    maksud = data.get("maksud", "")
    from reportlab.lib.styles import ParagraphStyle as PS
    _style_msd = PS("msd", fontName=FONT_BOLD, fontSize=fs, leading=fs*1.35)
    _p_msd = Paragraph(maksud, _style_msd)
    _, _msd_h = _p_msd.wrap(val_w - val_i - 0.2*cm, 200)
    row3_h = max(2.5, (_msd_h / cm) + 0.5)
    draw_row(
        ["3.  Maksud Perjalanan Dinas"],
        [f"**{maksud}"],
        row3_h,
        wrap_idx=0,
    )

    # ── ROW 4: Alat Angkutan ──
    draw_row(
        ["4.  Alat Angkutan Yang Dipergunakan"],
        [f"a.  {data.get('alat_angkutan','Umum')}",
         "b.",
         "c."],
        2.0,
    )

    # ── ROW 5: Tempat ──
    draw_row(
        ["5.  Tempat Berangkat",
         "    Tempat Tujuan"],
        [f"Dari           :  **{data.get('tempat_berangkat','')}",
         f"Ke             :  **{data.get('tempat_tujuan','')}"],
        1.7,
    )

    # ── ROW 6: Lama / Tanggal ──
    draw_row(
        ["6.  Lama Perjalanan Dinas",
         "    Tanggal Berangkat",
         "    Tanggal Harus Kembali"],
        [f"a.  **{data.get('lama_hari','')}",
         f"b.  **{fmt_tgl(data.get('tgl_berangkat'))}",
         f"c.  **{fmt_tgl(data.get('tgl_kembali'))}"],
        2.0,
    )

    # ── ROW 7: Peserta ──
    pi = data.get("peserta_ikut", [])
    pi_lines = [f"{i+1}   **{p}" for i, p in enumerate(pi)]
    n_slot = max(len(pi), 4)             # minimal 4 slot kosong
    for i in range(len(pi), n_slot):
        pi_lines.append(f"{i+1}")
    row7_h = max(3.5, 0.38 + n_slot * 0.45)
    draw_row(
        ["7.  Nama Yang Diikutsertakan"],
        pi_lines,
        row7_h,
    )

    # ── ROW 8: Pembebanan Anggaran ──
    draw_row(
        ["8.  Pembebanan Anggaran",
         "    a. PTMB/Divisi",
         "    b. Nomor Rekening Anggaran"],
        ["a.  Perumda Tirta Manuntung Balikpapan",
         f"b.  {data.get('kode_rkap','')}"],
        2.0,
    )

    # ── ROW 9: Keterangan ──
    draw_row(
        ["9.  Keterangan"],
        [""],
        2.0,
    )

    # ── TTD ──
    y -= 0.5 * cm

    ttd_x = PAGE_W / 2 + 0.5 * cm
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(ttd_x, y,             "Dikeluarkan di   :  Balikpapan")
    c.drawString(ttd_x, y - 0.45*cm,  f"Pada tanggal     :  {fmt_tgl(data.get('tanggal'))}")

    y -= 1.0 * cm
    cx = ttd_x + 3.0 * cm
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(cx, y,            "PERUMDA TIRTA MANUNTUNG BALIKPAPAN")
    c.drawCentredString(cx, y - 0.45*cm, "Direktur Utama,")

    y -= 2.8 * cm
    nama = data.get("ttd_nama", "")
    nw   = c.stringWidth(nama, FONT_BOLD, FONT_SIZE)
    nx   = cx - nw / 2
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawString(nx, y, nama)
    c.setLineWidth(0.8)
    c.line(nx, y - 2, nx + nw, y - 2)


def _visum_lembaran2(c, data):
    y_top = PAGE_H - MARGIN_T
    tbl_x = MARGIN_L
    tbl_w = CONTENT_W
    half  = tbl_w / 2

    # ── ROW KOP LEMBARAN II ──
    kop_h = 6.0 * cm
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.rect(tbl_x,        y_top - kop_h, half, kop_h)   # kotak kiri
    c.rect(tbl_x + half, y_top - kop_h, half, kop_h)   # kotak kanan

    # Isi kiri: nama perusahaan
    c.setFont(FONT_BOLD, 9)
    c.setFillColor(colors.black)
    c.drawCentredString(tbl_x + half/2, y_top - 0.6*cm,  "PERUMDA TIRTA MANUNTUNG")
    c.drawCentredString(tbl_x + half/2, y_top - 1.05*cm, "BALIKPAPAN")
    c.setFont(FONT_NORMAL, 8)
    c.drawCentredString(tbl_x + half/2, y_top - 1.55*cm, "Jln. Ruhui Rahayu I")
    c.drawCentredString(tbl_x + half/2, y_top - 1.9*cm,  "Tlp.(0542) 7218829/7218830")

    # Isi kanan: LEMBARAN II + berangkat + TTD
    rx = tbl_x + half + 0.3*cm
    center_kanan = tbl_x + half + (half/2)
    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawString(rx, y_top - 0.45*cm, "LEMBARAN: II")

    brgkt   = data.get("tempat_berangkat","Balikpapan")
    tujuan  = data.get("tempat_tujuan","")
    tgl_b   = fmt_tgl(data.get("tgl_berangkat"))
    tgl_k   = fmt_tgl(data.get("tgl_kembali"))
    penanda = data.get("ttd_nama","")

    c.setFont(FONT_NORMAL, 9.5)
    c.drawString(rx, y_top - 1.1*cm,  f"Berangkat dari    :  {brgkt}")
    c.drawString(rx, y_top - 1.45*cm, "( tempat kedudukan )")
    c.drawString(rx, y_top - 1.85*cm, f"Ke                      :  {tujuan}")
    c.drawString(rx, y_top - 2.25*cm, f"Pada Tanggal    :  {tgl_b}")
    c.drawCentredString(center_kanan, y_top - 3.00*cm, "Perumda Tirta Manuntung Balikpapan,")
    c.drawCentredString(center_kanan, y_top - 3.40*cm, "Direktur Utama")
    c.setFont(FONT_BOLD, 9.5)
    c.drawCentredString(center_kanan, y_top - 5.5*cm,  penanda)
    nw = c.stringWidth(penanda, FONT_BOLD, 9.5)
    c.setLineWidth(0.6)
    c.line(center_kanan - nw/2, y_top - 5.52*cm - 2, center_kanan + nw/2, y_top - 5.52*cm - 2)

    y = y_top - kop_h

    # Garis tengah
    mid = tbl_x + half

    # ── Blok II, III, IV ──
    for roman in ["II", "III", "IV"]:
        bh = 4.5 * cm
        c.rect(tbl_x, y - bh, tbl_w, bh)
        c.line(mid, y, mid, y - bh)

        if roman == "II":
            tiba_kota  = tujuan; tiba_tgl = tgl_k
            brgk_kota  = tujuan; brgk_ke  = brgkt; brgk_tgl = tgl_k
        else:
            tiba_kota  = "….................................."; tiba_tgl  = "….................................."
            brgk_kota  = "….................................."; brgk_ke   = "….................................."; brgk_tgl  = "….................................."

        c.setFont(FONT_NORMAL, 9)
        c.drawString(tbl_x + 0.3*cm, y - 0.45*cm, f"{roman}.  Tiba di            :  {tiba_kota}")
        c.drawString(tbl_x + 0.3*cm, y - 0.82*cm, f"     Pada tanggal   :  {tiba_tgl}")
        c.drawString(tbl_x + 0.3*cm, y - 1.18*cm, "     Kepala            :  …..................................")
        c.drawString(tbl_x + 1.5*cm, y - 4.0*cm,  "     ( ….....................................)")

        c.drawString(mid + 0.3*cm, y - 0.45*cm, f"Berangkat dari  :  {brgk_kota}")
        c.drawString(mid + 0.3*cm, y - 0.82*cm, f"Ke                     :  {brgk_ke}")
        c.drawString(mid + 0.3*cm, y - 1.18*cm, f"Pada tanggal   :  {brgk_tgl}")
        c.drawString(mid + 1.5*cm, y - 4.0*cm,  "( …............................................)")
        y -= bh

    # ── Blok V ──
    bh = 6.5 * cm
    c.rect(tbl_x, y - bh, tbl_w, bh)
    c.line(mid, y, mid, y - bh)

    c.setFont(FONT_BOLD, 9.5)
    c.drawString(tbl_x + 0.3*cm, y - 0.45*cm, f"V.  Tiba kembali  :  {brgkt}, {tgl_k}")
    c.setFont(FONT_NORMAL, 9)
    c.drawString(tbl_x + 0.3*cm, y - 0.82*cm, "     ( tempat kedudukan )")
    c.drawString(tbl_x + 0.3*cm, y - 1.25*cm, "     Pejabat yang memberi perintah :")
    c.drawString(tbl_x + 1.5*cm, y - 5.8*cm,  "     ( ….....................................)")

    verif = ("Telah diperiksa dengan keterangan bahwa perjalanan tersebut\n"
             "diatas benar dilakukan atas perintahnya dan semata-mata\n"
             "untuk kepentingan jabatan dalam waktu yang sesingkat -\n"
             "singkatnya")
    for k, line in enumerate(verif.split("\n")):
        c.drawString(mid + 0.3*cm, y - 0.45*cm - k*0.37*cm, line)
    c.drawString(mid + 0.3*cm, y - 2.0*cm,  "Pejabat yang memberikan perintah,")
    c.drawString(mid + 0.3*cm, y - 2.38*cm, "Ketua/Kepala ………………………………………")
    c.drawString(mid + 0.3*cm, y - 2.8*cm,  "……………………………………………………………")
    c.drawString(mid + 1.5*cm, y - 5.85*cm, "( ….............................................)")
    y -= bh

    # VI & VII
    c.setFont(FONT_BOLD, 9.5)
    c.drawString(tbl_x, y - 0.4*cm, "VI.   Catatan lain-lain")
    y -= 0.75*cm
    c.drawString(tbl_x, y - 0.1*cm, "VII.  Perhatian :")
    c.setFont(FONT_NORMAL, 7.5)
    perh = ("Pejabat yang berwenang menerbitkan SPPD pegawai yang melakukan perjalanan Dinas, para pejabat yang mengesah-\n"
            "kan tgl.berangkat/tiba serta bendaharawan bertanggung jawab berdasarkan peraturan-peraturan Keuangan Negara apa\n"
            "bila Negara menderita rugi akibat kesalahan, kelalaian dan kealpaan.\n"
            "( 10 Lampiran Surat Menteri Keuangan tgl.30 April 1974 Nomor B.296/MK/ I /4/1974).")
    for k, line in enumerate(perh.split("\n")):
        c.drawString(tbl_x + 0.5*cm, y - 0.5*cm - k*0.3*cm, line)


# ══════════════════════════════════════════════════════════════
# 4 & 5. SPPD TANDA TERIMA (PENCAIRAN & REALISASI)
# ══════════════════════════════════════════════════════════════
def generate_sppd_pencairan(data: dict) -> BytesIO:
    """
    Tanda Terima Pencairan — hanya uang saku (sebelum berangkat).

    data = {
        "nama_pejabat":     "Direktur Umum PTMB",      # label di header atas
        "nomor_spd":        "0012/1421002/10a-I/II/2026-O",
        "tanggal":          date(2026, 2, 2),
        "tempat_tujuan":    "Semarang",
        "tgl_berangkat":    date(2026, 2, 10),
        "tgl_kembali":      date(2026, 2, 13),
        "lama_hari":        4,
        "nama_penerima":    "Purnamawati, S.E",
        "jabatan_penerima": "Direktur Umum PTMB",
        "uang_harian":      1575000,        # tarif per hari
        "uang_representasi":150000,         # 0 kalau tidak ada
        "biaya_penginapan": 525000,         # penginapan 30% kalau belum dibayar
        "ttd_dirut":        "Dr. Saharuddin, M.M",
    }
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=F4)
    _draw_tanda_terima(c, data, mode="pencairan")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_sppd_realisasi(data: dict) -> BytesIO:
    """
    Tanda Terima Realisasi — komplit dengan tiket + hotel aktual (setelah pulang).

    data = {
        # sama seperti pencairan, tambah:
        "items_transport": [
            {"keterangan": "Tiket Pesawat BPP - CGK", "qty": 1, "satuan": 2500000},
            {"keterangan": "Tiket Pesawat CGK - BPP", "qty": 1, "satuan": 2300000},
        ],
        "biaya_penginapan_aktual": 3600000,   # total hotel aktual
        "biaya_lain": [
            {"keterangan": "Biaya Seminar", "qty": 1, "satuan": 8850000},
        ],
    }
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=F4)
    _draw_tanda_terima(c, data, mode="realisasi")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _wrap_text(c, text, font, font_size, max_width):
    """Split text menjadi baris-baris yang muat dalam max_width. Return list of str."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if c.stringWidth(test, font, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_tanda_terima(c, data, mode="pencairan"):
    """Gambar satu halaman Tanda Terima (pencairan atau realisasi)."""
    y = PAGE_H - MARGIN_T

    nama_pejabat = data.get("nama_pejabat", "")
    nomor_spd    = data.get("nomor_spd", "")
    tujuan       = data.get("tempat_tujuan", "")
    tgl_b        = fmt_tgl(data.get("tgl_berangkat"))
    tgl_k        = fmt_tgl(data.get("tgl_kembali"))
    lama         = data.get("lama_hari", 0)

    # Header — auto-wrap kalau teks terlalu panjang
    c.setFont(FONT_BOLD, 11)
    header_text  = f"Tanda Terima Permintaan Biaya Perjalanan Dinas {nama_pejabat}"
    header_lines = _wrap_text(c, header_text, FONT_BOLD, 11, CONTENT_W)
    for line in header_lines:
        c.drawString(MARGIN_L, y, line)
        y -= 0.5 * cm
    y -= 0.1 * cm  # sedikit extra gap setelah header
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(MARGIN_L, y,
        f"Ke Kota {tujuan}, sesuai permintaan biaya no. {nomor_spd}")
    y -= 0.42 * cm
    c.drawString(MARGIN_L, y,
        f"Tanggal {tgl_b} s/d {tgl_k}. (\u00b1 {lama} hari)")
    y -= 0.65 * cm

    # ── BARIS ITEM ──
    # Layout: no | keterangan | qty x satuan = | Rp | total
    no_x   = MARGIN_L
    ket_x  = MARGIN_L + 0.7*cm
    num_x  = PAGE_W - MARGIN_R - 4.5*cm   # ujung kanan area "qty x satuan ="
    rp_x   = PAGE_W - MARGIN_R - 3.2*cm
    tot_x  = PAGE_W - MARGIN_R

    rh = 0.5 * cm

    def item_row(no, keterangan, qty=None, satuan=None, total=None, bold=False):
        nonlocal y
        c.setFont(FONT_BOLD if bold else FONT_NORMAL, FONT_SIZE)
        c.setFillColor(colors.black)
        if no: c.drawString(no_x, y, str(no))
        c.drawString(ket_x, y, keterangan)
        if qty is not None and satuan:
            qty_str = f"{qty}  x  {fmt_rp(satuan)}  ="
            c.drawRightString(num_x, y, qty_str)
        c.drawString(rp_x, y, "Rp")
        if total is not None:
            c.drawRightString(tot_x, y, f"{total:,.0f}".replace(",","."))
        y -= rh

    lama      = data.get("lama_hari", 0)
    uh        = data.get("uang_harian", 0)
    total_uh  = lama * uh

    item_row("1", "Uang Harian", lama, uh, total_uh)
    item_row("2", "Biaya Transportasi", bold=False)

    if mode == "pencairan":
        # Pencairan: belum ada tiket aktual
        item_row("", "   a.", bold=False)
    else:
        # Realisasi: tiket aktual
        for tr in data.get("items_transport", []):
            total_tr = tr.get("qty", 1) * tr.get("satuan", 0)
            item_row("", f"   {tr.get('keterangan','')}", tr.get("qty",1), tr.get("satuan",0), total_tr)

    # Penginapan
    if mode == "pencairan":
        penginapan = data.get("biaya_penginapan", 0)
        if penginapan:
            item_row("3", "Biaya Penginapan", 1, penginapan, penginapan)
        else:
            item_row("3", "Biaya Penginapan")  # kosong kalau menginap (bayar sendiri dulu)
    else:
        penginapan = data.get("biaya_penginapan_aktual", 0)
        item_row("3", "Biaya Penginapan", 1, penginapan, penginapan)

    # Uang representasi
    urep = data.get("uang_representasi", 0)
    item_row("4", "Uang Representasi Perjalanan Dinas", lama if urep else None,
             urep if urep else None, lama * urep if urep else None)

    # Sewa kendaraan
    item_row("5", "Biaya Sewa Kendaraan")
    item_row("6", "Biaya Menjemput/Mengantar Jenazah")

    # Biaya lain-lain (selalu tampil headernya, sub-item hanya kalau ada)
    item_row("7", "Biaya Lain-lain")
    if mode == "realisasi":
        for bl in data.get("biaya_lain", []):
            item_row("", f"   {bl.get('keterangan','')}", None, None, bl.get("jumlah", 0))

    # Grand total
    y -= 0.2*cm
    c.setLineWidth(0.8)
    c.line(MARGIN_L, y + 0.3*cm, PAGE_W - MARGIN_R, y + 0.3*cm)

    # Hitung grand total
    if mode == "pencairan":
        grand = total_uh + data.get("biaya_penginapan", 0) + lama * data.get("uang_representasi", 0)
    else:
        grand = data.get("grand_total", 0)

    c.setFont(FONT_BOLD, 11)
    y -= 0.2*cm
    c.drawString(rp_x, y, "Rp")
    c.drawRightString(tot_x, y, f"{grand:,.0f}".replace(",","."))
    y -= 1.5*cm

    # ── TTD ──
    tgl_str   = fmt_tgl(data.get("tanggal"))
    # Titik tengah masing-masing kolom (kiri: MARGIN_L s/d PAGE_W/2, kanan: PAGE_W/2 s/d PAGE_W-MARGIN_R)
    ctr_left  = (MARGIN_L + PAGE_W / 2) / 2
    ctr_rght  = (PAGE_W / 2 + PAGE_W - MARGIN_R) / 2

    c.setFont(FONT_NORMAL, FONT_SIZE)
    # Kanan: tanggal di baris paling atas
    c.drawCentredString(ctr_rght, y, f"Balikpapan, {tgl_str}")
    y -= 0.42 * cm

    # "Mengetahui/Menyetujui :" sejajar dengan jabatan penerima
    c.drawCentredString(ctr_left, y, "Mengetahui/Menyetujui :")
    c.drawCentredString(ctr_rght, y, data.get("jabatan_penerima", ""))
    y -= 0.42 * cm

    c.drawCentredString(ctr_left, y, "Perumda Tirta Manuntung Balikpapan")
    y -= 0.42 * cm
    c.drawCentredString(ctr_left, y, "Direktur Utama,")
    y -= 2.0 * cm

    # Nama + garis bawah, rata tengah kolom masing-masing
    for cx, nama in [
        (ctr_left, data.get("ttd_dirut", "")),
        (ctr_rght, data.get("nama_penerima", "")),
    ]:
        c.setFont(FONT_BOLD, FONT_SIZE)
        nw = c.stringWidth(nama, FONT_BOLD, FONT_SIZE)
        c.drawCentredString(cx, y, nama)
        c.setLineWidth(0.7)
        c.line(cx - nw / 2, y - 2, cx + nw / 2, y - 2)


# ══════════════════════════════════════════════════════════════
# 6. PERNYATAAN PENGELUARAN BIAYA RIIL
# ══════════════════════════════════════════════════════════════
def generate_pernyataan_biaya(data: dict) -> BytesIO:
    """
    data = {
        "nomor_surat":         "015/1421002/10a-I/II/2026",
        "nomor_spd":           "0012/1421002/10a-I/II/2026-O",
        "tanggal_spd":         date(2026, 2, 2),
        "nama":                "Purnamawati, S.E",
        "jabatan":             "Direktur Umum PTMB",
        "nomor_surat_tugas":   "040/1421002/10a-I/II/2026-F",
        "tempat_kegiatan":     "Semarang",
        "waktu_pelaksanaan":   "Selasa - Jumat, 10-13 Februari 2026",
        "biaya_perjalanan":    6900000,
        "biaya_penginapan":    4800000,
        "biaya_transport":     4047900,
        "biaya_lain":          4250000,
        "grand_total":         19997900,
        "tanggal_ttd":         date(2026, 2, 18),
        "ttd_mengetahui_jabatan": "Direktur Umum",
        "ttd_mengetahui_nama":    "PURNAMAWATI, S.E",
        "nama_penerima":          "PURNAMAWATI, S.E",
    }
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=F4)
    _draw_pernyataan(c, data)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _draw_pernyataan(c, data):
    y = draw_kop(c)
    y -= 0.55 * cm

    # Judul
    c.setFont(FONT_BOLD, 13)
    c.drawCentredString(PAGE_W/2, y, "PERNYATAAN PENGELUARAN BIAYA RIIL")
    y -= 0.35*cm
    jw = 9.2*cm
    c.setLineWidth(1.5)
    c.line(PAGE_W/2 - jw/2, y, PAGE_W/2 + jw/2, y)
    y -= 0.45*cm
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawCentredString(PAGE_W/2, y, f"Nomor : {data.get('nomor_surat','')}")
    y -= 0.7*cm

    # Info lampiran
    lbl_w = 4.0*cm
    rows_info = [
        ("Lampiran SPD Nomor", data.get("nomor_spd","")),
        ("Tanggal",            fmt_tgl(data.get("tanggal_spd"))),
    ]
    for lbl, val in rows_info:
        c.setFont(FONT_NORMAL, FONT_SIZE)
        c.drawString(MARGIN_L, y, lbl)
        c.drawString(MARGIN_L + lbl_w, y, ":")
        c.drawString(MARGIN_L + lbl_w + 0.4*cm, y, val)
        y -= 0.48*cm
    y -= 0.4*cm

    # Info pegawai
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(MARGIN_L, y, "Yang bertandatangan di bawah ini :")
    y -= 0.5*cm

    # Format waktu pelaksanaan: dari tanggal_berangkat/kembali jika ada, else string
    tgl_brkt  = data.get("tanggal_berangkat")
    tgl_kmbli = data.get("tanggal_kembali")
    if isinstance(tgl_brkt, str):
        try: tgl_brkt = datetime.strptime(tgl_brkt, "%Y-%m-%d").date()
        except: tgl_brkt = None
    if isinstance(tgl_kmbli, str):
        try: tgl_kmbli = datetime.strptime(tgl_kmbli, "%Y-%m-%d").date()
        except: tgl_kmbli = None
    if tgl_brkt and tgl_kmbli:
        if tgl_brkt.month == tgl_kmbli.month and tgl_brkt.year == tgl_kmbli.year:
            waktu_str = f"{tgl_brkt.day} - {tgl_kmbli.day} {BULAN_ID[tgl_brkt.month]} {tgl_brkt.year}"
        else:
            waktu_str = f"{fmt_tgl(tgl_brkt)} s/d {fmt_tgl(tgl_kmbli)}"
    else:
        waktu_str = data.get("waktu_pelaksanaan", "")

    rows_pgw = [
        ("Nama",              data.get("nama","")),
        ("Jabatan",           data.get("jabatan","")),
        ("Nomor Surat Tugas", data.get("nomor_surat_tugas","")),
        ("Tempat Kegiatan",   data.get("tempat_kegiatan","")),
        ("Waktu Pelaksanaan", waktu_str),
    ]
    for lbl, val in rows_pgw:
        c.setFont(FONT_NORMAL, FONT_SIZE)
        c.drawString(MARGIN_L, y, lbl)
        c.drawString(MARGIN_L + lbl_w, y, ":")
        c.setFont(FONT_BOLD, FONT_SIZE)
        c.drawString(MARGIN_L + lbl_w + 0.4*cm, y, val)
        y -= 0.5*cm
    y -= 0.3*cm

    # Paragraf menyatakan
    nomor_spd = data.get("nomor_spd","")
    tgl_spd   = fmt_tgl(data.get("tanggal_spd"))
    para = (f"Berdasarkan SPD Nomor : {nomor_spd}, tanggal "
            f"{tgl_spd}, menyatakan dengan ini sesungguhnya bahwa :")
    y = draw_wrapped(c, para, MARGIN_L, y, CONTENT_W)
    y -= 0.45*cm

    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(MARGIN_L, y, "1.  Biaya dibawah ini yang dapat diperoleh bukti-bukti pengeluarannya, meliputi :")
    y -= 0.5*cm

    # Tabel biaya
    cw = [1.0*cm, 9.0*cm, 5.5*cm]
    rh = 0.62*cm

    def biaya_row(no, label, val, bold=False):
        nonlocal y
        x = MARGIN_L + 0.6*cm  # sedikit padding kiri dalam kotak
        for k, (w, txt) in enumerate(zip(cw, [no, label, val])):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.4)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(colors.black)
            c.setFont(FONT_BOLD if bold else FONT_NORMAL, FONT_SIZE)
            if k == 0:
                c.drawCentredString(x + w/2, y - rh + 0.18*cm, txt)
            else:
                c.drawString(x + 0.2*cm, y - rh + 0.18*cm, txt)
            x += w
        y -= rh

    biaya_row("NO.", "PERINCIAN BIAYA", "REALISASI (RP)", bold=True)
    biaya_row("1.", "Biaya Perjalanan Dinas", fmt_rp2(data.get("biaya_perjalanan",0)))
    biaya_row("2.", "Biaya Penginapan",       fmt_rp2(data.get("biaya_penginapan",0)))
    biaya_row("3.", "Biaya Transport",        fmt_rp2(data.get("biaya_transport",0)))
    biaya_row("4.", "Biaya Lain-lain",        fmt_rp2(data.get("biaya_lain",0)))
    biaya_row("",   "JUMLAH",                fmt_rp2(data.get("grand_total",0)), bold=True)

    y -= 0.4*cm

    # Poin 2 & 3 — hanging indent: baris pertama rata kiri, baris lanjutan indent sejajar teks awal
    pfx_w = c.stringWidth("2.  ", FONT_NORMAL, FONT_SIZE)
    hang_style = ParagraphStyle("hang", fontName=FONT_NORMAL, fontSize=FONT_SIZE,
                                leading=14, alignment=4,
                                firstLineIndent=-pfx_w, leftIndent=pfx_w)

    p2 = Paragraph(
        "2.  Jumlah uang tersebut pada angka 1 diatas benar-benar dikeluarkan untuk pelaksanaan dinas "
        "dimaksud dan apabila di kemudian hari terdapat kelebihan atas pembayaran, kami bersedia untuk "
        "menyetorkan kelebihan tersebut ke Rekening Kas Perumda Tirta Manuntung Balikpapan.", hang_style)
    _, h2 = p2.wrap(CONTENT_W, 500)
    p2.drawOn(c, MARGIN_L, y - h2)
    y -= h2 + 0.3*cm

    p3 = Paragraph(
        "3.  Demikian Pernyataan ini kami buat dengan sebenarnya, untuk dipergunakan sebagaimana mestinya.",
        hang_style)
    _, h3 = p3.wrap(CONTENT_W, 500)
    p3.drawOn(c, MARGIN_L, y - h3)
    y -= h3 + 0.9*cm

    # TTD — dua kolom dibagi rata dari CONTENT_W
    tgl_ttd  = fmt_tgl(data.get("tanggal_ttd"))
    cx_left = MARGIN_L + CONTENT_W / 4        # center kolom kiri
    cx_rght = MARGIN_L + 3 * CONTENT_W / 4   # center kolom kanan

    c.setFont(FONT_NORMAL, FONT_SIZE)
    # Kanan: tanggal kota satu baris di atas
    c.drawCentredString(cx_rght, y, f"Balikpapan, {tgl_ttd}")
    y -= 0.4*cm
    # "Mengetahui;" sejajar "Penerima SPPD"
    c.drawCentredString(cx_left, y, "Mengetahui;")
    c.drawCentredString(cx_rght, y, "Penerima SPPD,")
    y -= 0.4*cm
    c.drawCentredString(cx_left, y, data.get("ttd_mengetahui_jabatan",""))
    y -= 2.5*cm

    for cx, nama in [
        (cx_left, data.get("ttd_mengetahui_nama","")),
        (cx_rght, data.get("nama_penerima","")),
    ]:
        c.setFont(FONT_BOLD, FONT_SIZE)
        nw = c.stringWidth(nama, FONT_BOLD, FONT_SIZE)
        c.drawCentredString(cx, y, nama)
        c.setLineWidth(0.8)
        c.line(cx - nw/2, y-2, cx + nw/2, y-2)

    draw_footer(c)


# ══════════════════════════════════════════════════════════════
# TEST SEMUA DOKUMEN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from datetime import date
    os.makedirs("output_test", exist_ok=True)

    # Surat Tugas
    generate_surat_tugas({
        "nomor": "040/1421002/10a-I/II/2026-F",
        "tanggal": date(2026, 2, 2),
        "pembuka": "Surat dari Praktisi Auditor Internal Bersertifikat Kompetensi Perihal Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal",
        "peserta": [
            {"nama": "Purnamawati, S.E",  "nip": "-",          "jabatan": "Direktur Umum",                     "divisi": "-"},
            {"nama": "Alfiansyah",         "nip": "459.010408", "jabatan": "Kepala Satuan Pengawas Intern",      "divisi": "SPI"},
            {"nama": "Rismawati",           "nip": "515.010409", "jabatan": "Ketua Kelompok Fungsional Auditor",  "divisi": "SPI"},
        ],
        "tujuan":   "Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal.",
        "durasi":   4,
        "waktu":    "Selasa - Jumat, 10 - 13 Februari 2026",
        "tempat":   "Semarang",
        "target":   "Wajib Untuk Menyerahkan Laporan Perjalanan Dinas Kepada Direktur Utama Perumda Tirta Manuntung Balikpapan.",
        "ttd_nama": "Dr. SAHARUDDIN, M.M.",
    }).read(); print("✅ Surat Tugas OK")
    with open("output_test/surat_tugas.pdf","wb") as f:
        f.write(generate_surat_tugas({
            "nomor": "040/1421002/10a-I/II/2026-F","tanggal": date(2026, 2, 2),
            "pembuka": "Surat dari Praktisi Auditor Internal Bersertifikat Kompetensi Perihal Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal",
            "peserta":[{"nama":"Purnamawati, S.E","nip":"-","jabatan":"Direktur Umum","divisi":"-"},{"nama":"Alfiansyah","nip":"459.010408","jabatan":"Kepala Satuan Pengawas Intern","divisi":"SPI"},{"nama":"Rismawati","nip":"515.010409","jabatan":"Ketua Kelompok Fungsional Auditor","divisi":"SPI"}],
            "tujuan":"Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal.","durasi":4,"waktu":"Selasa - Jumat, 10 - 13 Februari 2026","tempat":"Semarang",
            "target":"Wajib Untuk Menyerahkan Laporan Perjalanan Dinas Kepada Direktur Utama Perumda Tirta Manuntung Balikpapan.","ttd_nama":"Dr. SAHARUDDIN, M.M.",
        }).read())

    # SPD
    with open("output_test/spd.pdf","wb") as f:
        f.write(generate_spd({
            "nomor":"0012/1421002/10a-I/II/2026-O","tanggal":date(2026,2,2),
            "lokasi_label":"Biaya Perjalanan Dinas di Luar Daerah KALTIM","tahun":2026,
            "kategori":[
                {"no":1,"uraian":"Direksi","total":19997900,"kode":"96.08.41"},
                {"no":2,"uraian":"Bagian Administrasi/Keuangan","total":33385800,"kode":"96.08.42"},
                {"no":3,"uraian":"Bagian Teknik","total":0,"kode":"96.08.43"},
                {"no":4,"uraian":"Dewan Pengawas","total":0,"kode":"96.08.30"},
                {"no":5,"uraian":"Bantuan","total":0,"kode":"96.08.92"},
            ],
            "grand_total":53383700,
            "peserta":[
                {"no":1,"nama":"Purnamawati, S.E","jabatan":"Direktur Umum","biaya":19997900},
                {"no":2,"nama":"Alfiansyah","jabatan":"Kepala SPI","biaya":20997900},
                {"no":3,"nama":"Rismawati","jabatan":"Ketua Kelompok Fungsional Auditor","biaya":12387900},
            ],
            "ttd_manajer_sek":"Abdul Ramli","ttd_spv_sek":"Ganden Aditera. I","ttd_dirut":"Dr. Saharuddin, M.M",
        }).read())
    print("✅ SPD OK")

    # Visum
    with open("output_test/visum.pdf","wb") as f:
        f.write(generate_visum({
            "nomor":"0016/1421002/10a-I/II/2026-J","tanggal":date(2026,2,2),
            "nama_pegawai":"Purnamawati, S.E","jabatan":"Direktur Umum",
            "maksud":"Dalam Rangka Menghadiri Undangan Seminar dan Pengukuhan Kompetensi Auditor Internal.",
            "alat_angkutan":"Umum","tempat_berangkat":"Balikpapan","tempat_tujuan":"Semarang",
            "lama_hari":"4 (Empat) hari","tgl_berangkat":date(2026,2,10),"tgl_kembali":date(2026,2,13),
            "peserta_ikut":["Alfiansyah (Kepala Satuan Pengawas Intern)","Rismawati (Ketua Kelompok Fungsional Auditor)"],
            "ttd_nama":"Dr. SAHARUDDIN, M.M.",
        }).read())
    print("✅ Visum OK")

    # SPPD Pencairan
    with open("output_test/sppd_pencairan.pdf","wb") as f:
        f.write(generate_sppd_pencairan({
            "nama_pejabat":"Direktur Umum PTMB","nomor_spd":"0012/1421002/10a-I/II/2026-O",
            "tanggal":date(2026,2,2),"tempat_tujuan":"Semarang",
            "tgl_berangkat":date(2026,2,10),"tgl_kembali":date(2026,2,13),"lama_hari":4,
            "nama_penerima":"Purnamawati, S.E","jabatan_penerima":"Direktur Umum PTMB",
            "uang_harian":1575000,"uang_representasi":150000,"biaya_penginapan":525000,
            "ttd_dirut":"Dr. Saharuddin, M.M",
        }).read())
    print("✅ SPPD Pencairan OK")

    # SPPD Realisasi
    with open("output_test/sppd_realisasi.pdf","wb") as f:
        f.write(generate_sppd_realisasi({
            "nama_pejabat":"Direktur Umum PTMB","nomor_spd":"0012/1421002/10a-I/II/2026-O",
            "tanggal":date(2026,2,2),"tempat_tujuan":"Semarang",
            "tgl_berangkat":date(2026,2,10),"tgl_kembali":date(2026,2,13),"lama_hari":4,
            "nama_penerima":"Purnamawati, S.E","jabatan_penerima":"Direktur Umum PTMB",
            "uang_harian":1575000,"uang_representasi":150000,"biaya_penginapan_aktual":3600000,
            "items_transport":[
                {"keterangan":"Tiket Pesawat BPP - SBY - SRG","qty":1,"satuan":2106700},
                {"keterangan":"Tiket Pesawat SRG - BPP","qty":1,"satuan":1941200},
            ],
            "biaya_lain":[{"keterangan":"Biaya Seminar","qty":1,"satuan":8850000}],
            "grand_total":19997900,
            "ttd_dirut":"Dr. Saharuddin, M.M",
        }).read())
    print("✅ SPPD Realisasi OK")

    # Pernyataan Biaya Riil
    with open("output_test/pernyataan_biaya.pdf","wb") as f:
        f.write(generate_pernyataan_biaya({
            "nomor_surat":"015/1421002/10a-I/II/2026","nomor_spd":"0012/1421002/10a-I/II/2026-O",
            "tanggal_spd":date(2026,2,2),"nama":"Purnamawati, S.E","jabatan":"Direktur Umum PTMB",
            "nomor_surat_tugas":"040/1421002/10a-I/II/2026-F","tempat_kegiatan":"Semarang",
            "waktu_pelaksanaan":"Selasa- Jumat, 10-13 Februari 2026",
            "biaya_perjalanan":6900000,"biaya_penginapan":4800000,"biaya_transport":4047900,"biaya_lain":4250000,
            "grand_total":19997900,"tanggal_ttd":date(2026,2,18),
            "ttd_mengetahui_jabatan":"Direktur Umum","ttd_mengetahui_nama":"PURNAMAWATI, S.E",
            "nama_penerima":"PURNAMAWATI, S.E",
        }).read())
    print("✅ Pernyataan Biaya Riil OK")

    print("\n🎉 Semua 6 dokumen berhasil! Cek folder output_test/")