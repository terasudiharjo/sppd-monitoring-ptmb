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

import re
from numpy import pi
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

_ROMAN_RE = re.compile(
    r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'
)

def smart_title(s: str) -> str:
    """str.title() tapi angka Romawi (I, II, III, IV, ...) tetap kapital semua."""
    if not s:
        return s
    def _fix(w):
        u = w.upper()
        return u if u and _ROMAN_RE.match(u) else w
    return " ".join(_fix(w) for w in s.title().split())

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

HARI_ID = {0:"Senin", 1:"Selasa", 2:"Rabu", 3:"Kamis", 4:"Jumat", 5:"Sabtu", 6:"Minggu"}

def fmt_tgl_short(d) -> str:
    """date → '10-Feb-2026'"""
    if not d: return ""
    if isinstance(d, str):
        try: d = datetime.strptime(d, "%Y-%m-%d").date()
        except: return d
    return f"{d.day:02d}-{BULAN_SINGKAT[d.month]}-{d.year}"

def fmt_waktu_surat_tugas(tgl_berangkat, tgl_kembali) -> str:
    """Format waktu pelaksanaan untuk Surat Tugas.
    - 1 hari  : "Senin, 5 Januari 2026"
    - Bulan sama: "Senin - Rabu, 5 - 7 Januari 2026"
    - Beda bulan: "Senin, 5 Januari 2026 - Rabu, 7 Februari 2026"
    """
    if isinstance(tgl_berangkat, str):
        try: tgl_berangkat = datetime.strptime(tgl_berangkat, "%Y-%m-%d").date()
        except: return str(tgl_berangkat)
    if isinstance(tgl_kembali, str):
        try: tgl_kembali = datetime.strptime(tgl_kembali, "%Y-%m-%d").date()
        except: return str(tgl_kembali)
    hari_brkt = HARI_ID[tgl_berangkat.weekday()]
    hari_kmbl = HARI_ID[tgl_kembali.weekday()]
    if tgl_berangkat == tgl_kembali:
        return f"{hari_brkt}, {fmt_tgl(tgl_berangkat)}"
    elif tgl_berangkat.month == tgl_kembali.month and tgl_berangkat.year == tgl_kembali.year:
        return (f"{hari_brkt} - {hari_kmbl}, "
                f"{tgl_berangkat.day} - {tgl_kembali.day} "
                f"{BULAN_ID[tgl_berangkat.month]} {tgl_berangkat.year}")
    else:
        return f"{hari_brkt}, {fmt_tgl(tgl_berangkat)} - {hari_kmbl}, {fmt_tgl(tgl_kembali)}"


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
    y -= 0.75 * cm

    c.setFont(FONT_BOLD, FONT_SIZE)
    c.drawCentredString(PAGE_W/2, y, "MEMERINTAHKAN :")
    y -= 0.45 * cm

    # Tabel peserta
    y = _tabel_peserta_st(c, data.get("peserta", []), y)
    y -= 0.75 * cm

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
    line_gap = 0.45 * cm
    for lbl, val in rows:
        c.setFont(FONT_NORMAL, FONT_SIZE)
        c.drawString(MARGIN_L, y, lbl)
        c.drawString(MARGIN_L + lbl_w, y, ":")
        c.setFont(FONT_BOLD, FONT_SIZE)
        if lbl == "Tujuan Perjalanan Dinas":
            # wrap + hanging indent: semua baris mulai di val_x
            words = val.split()
            lines, cur = [], []
            for word in words:
                test = " ".join(cur + [word])
                if c.stringWidth(test, FONT_BOLD, FONT_SIZE) <= val_w:
                    cur.append(word)
                else:
                    lines.append(" ".join(cur))
                    cur = [word]
            if cur:
                lines.append(" ".join(cur))
            for k, line in enumerate(lines):
                c.drawString(val_x, y - k * line_gap, line)
            y -= max(0.5 * cm, len(lines) * line_gap + 0.05 * cm)
        else:
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
    cw_jab  = 5.5  * cm
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

    # Data rows — tinggi dinamis sesuai wrap nama/jabatan/divisi
    for i, p in enumerate(peserta, 1):
        nama_txt = p.get("nama", "")
        jab_txt  = p.get("jabatan", "")
        div_txt  = p.get("divisi", "-")

        # Hitung tinggi cell yang butuh wrap
        p_nama = Paragraph(nama_txt, wrap_style)
        _, h_nama = p_nama.wrap(cw_nama - 2*pad, 200)
        p_jab = Paragraph(jab_txt, wrap_style)
        _, h_jab = p_jab.wrap(cw_jab - 2*pad, 200)
        p_div = Paragraph(div_txt, wrap_style)
        _, h_div = p_div.wrap(cw_div - 2*pad, 200)
        rh = max(0.65*cm, h_nama + 2*pad, h_jab + 2*pad, h_div + 2*pad)

        x = MARGIN_L
        for j, w in enumerate(cw):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(colors.black)

            if j == 0:          # NO — center
                c.setFont(FONT_NORMAL, 9)
                c.drawCentredString(x + w/2, y - rh/2 - 3, str(i))
            elif j == 1:        # NAMA — wrap, vertical center
                pg = Paragraph(nama_txt, wrap_style)
                _, h_pg = pg.wrap(w - 2*pad, rh)
                draw_y = (y - rh) + (rh - h_pg) / 2
                pg.drawOn(c, x + pad, draw_y)
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


SPD_ROW_COLORS = {
    1: colors.HexColor("#1155CC"),  # Direksi — biru (link aktif)
    2: colors.HexColor("#2D7A2D"),  # Administrasi/Keuangan — hijau
    3: colors.HexColor("#7030A0"),  # Teknik — ungu
    4: colors.HexColor("#C55A11"),  # Dewan Pengawas — orange
    # 5 Bantuan — hitam (default)
}

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

    def tbl_row(vals, bold=False, align_last_right=True, header=False, txt_color=None):
        nonlocal y
        x = MARGIN_L
        for k, (w, v) in enumerate(zip(cw_top, vals)):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.4)
            c.rect(x, y - rh, w, rh, fill=1)
            c.setFillColor(txt_color if txt_color and not header else colors.black)
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
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.4)
    c.rect(MARGIN_L, y - rh, tbl_w, rh, fill=1)
    c.setFillColor(colors.black)
    c.drawString(MARGIN_L + 0.3*cm, y - rh + 0.18*cm,
                 data.get("lokasi_label", "Biaya Perjalanan Dinas"))
    y -= rh

    # Rows kategori — warnai teks sesuai nomor kategori
    for kat in data.get("kategori", []):
        total_str = fmt_rp(kat.get("total", 0)) if kat.get("total", 0) else "---"
        txt_color = SPD_ROW_COLORS.get(kat.get("no"))
        tbl_row([str(kat.get("no","")), kat.get("uraian",""), total_str, kat.get("kode","")],
                txt_color=txt_color)

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

    def tbl_bot_row(vals, bold=False, header=False, txt_color=None):
        nonlocal y
        fnt = FONT_BOLD if bold else FONT_NORMAL
        txt_c = txt_color if txt_color and not header else colors.black
        nama_style = ParagraphStyle("nama_spd", fontName=fnt, fontSize=FONT_SIZE,
                                    leading=12, textColor=txt_c)
        jab_style  = ParagraphStyle("jab_spd",  fontName=fnt, fontSize=FONT_SIZE,
                                    leading=12, textColor=txt_c)
        # Hitung tinggi row dinamis dari kolom nama (k=1) dan jabatan (k=2)
        if not header and len(vals) > 2:
            p_nama = Paragraph(str(vals[1]), nama_style)
            _, h_nama = p_nama.wrap(cw_bot[1] - 0.4*cm, 200)
            p_jab  = Paragraph(str(vals[2]), jab_style)
            _, h_jab  = p_jab.wrap(cw_bot[2] - 0.4*cm, 200)
            row_h = max(rh, h_nama + 0.2*cm, h_jab + 0.2*cm)
        else:
            row_h = rh
        x = MARGIN_L
        for k, (w, v) in enumerate(zip(cw_bot, vals)):
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.4)
            c.rect(x, y - row_h, w, row_h, fill=1)
            c.setFillColor(txt_c)
            c.setFont(fnt, FONT_SIZE)
            if header:
                c.drawCentredString(x + w/2, y - row_h + 0.18*cm, str(v))
            elif k == 1:  # Nama — Paragraph wrap, vertikal center
                p = Paragraph(str(v), nama_style)
                _, h_pg = p.wrap(w - 0.4*cm, row_h)
                draw_y = (y - row_h) + (row_h - h_pg) / 2
                p.drawOn(c, x + 0.2*cm, draw_y)
                c.setFillColor(txt_c)  # reset setelah Paragraph
            elif k == 2:  # Jabatan — Paragraph wrap, vertikal center
                p = Paragraph(str(v), jab_style)
                _, h_pg = p.wrap(w - 0.4*cm, row_h)
                draw_y = (y - row_h) + (row_h - h_pg) / 2
                p.drawOn(c, x + 0.2*cm, draw_y)
                c.setFillColor(txt_c)  # reset setelah Paragraph
            elif k == 0:
                c.drawCentredString(x + w/2, y - row_h/2 - 0.15*cm, str(v))
            elif k == 3:
                c.drawRightString(x + w - 0.2*cm, y - row_h/2 - 0.15*cm, str(v))
            else:
                c.drawString(x + 0.2*cm, y - row_h/2 - 0.15*cm, str(v))
            x += w
        y -= row_h

    tbl_bot_row(["No", "Nama", "Jabatan", "Biaya SPPD"], bold=True, header=True)
    for p in data.get("peserta", []):
        txt_color = SPD_ROW_COLORS.get(p.get("kategori_no"))
        tbl_bot_row([str(p.get("no","")), p.get("nama",""),
                     p.get("jabatan",""), fmt_rp(p.get("biaya",0))],
                    txt_color=txt_color)
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

    def _calc_line_h(vl, wrap_extra=0):
        """Hitung tinggi satu baris value dengan Paragraph wrap."""
        bold = vl.startswith("**")
        txt  = vl.replace("**", "")
        fn   = FONT_BOLD if bold else FONT_NORMAL
        style = ParagraphStyle("_ch", fontName=fn, fontSize=fs, leading=fs*1.3)
        p = Paragraph(txt, style)
        _, ph = p.wrap(val_w - val_i - 0.2*cm, 500)
        return max(ph, line_gap) + wrap_extra

    def draw_row(label_lines, value_lines, row_h_cm, wrap_idx=None, wrap_all=False, wrap_extra_cm=0.15):
        """
        Gambar satu row tabel visum.
        label_lines : list string, baris-baris label kiri
        value_lines : list string, baris-baris value kanan
                      prefix "**" = bold
        row_h_cm    : tinggi row dalam cm
        wrap_idx    : index tunggal di value_lines yang di-wrap
        wrap_all    : True = semua value_lines di-wrap dengan Paragraph
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
        pw = val_w - val_i - 0.2*cm
        for k, vl in enumerate(value_lines):
            bold = vl.startswith("**")
            txt  = vl.replace("**", "")
            fn   = FONT_BOLD if bold else FONT_NORMAL
            if wrap_all or (wrap_idx is not None and k == wrap_idx):
                style = ParagraphStyle("vs", fontName=fn, fontSize=fs, leading=fs*1.3)
                p = Paragraph(txt, style)
                _, ph = p.wrap(pw, rh)
                p.drawOn(c, val_x + val_i, cur_y - ph + fs*0.35)
                cur_y -= max(ph, line_gap) + wrap_extra_cm * cm
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

    # ── ROW 2: Jabatan / Biaya ── (tinggi dinamis supaya jabatan bisa wrap)
    _jab_line = f"a.  Jabatan/Divisi  :  {data.get('jabatan','')}"
    _style_jab = ParagraphStyle("jab", fontName=FONT_BOLD, fontSize=fs, leading=fs*1.35)
    _p_jab = Paragraph(_jab_line, _style_jab)
    _, _jab_h = _p_jab.wrap(val_w - val_i - 0.2*cm, 200)
    row2_h = max(2.0, (_jab_h / cm) + 1.1)   # +1.1cm untuk baris b & c
    draw_row(
        ["2.  Jabatan/Divisi, Pangkat & Golongan, dan Biaya",
         "    Perjalanan Dinas Yang Diperintahkan"],
        [f"a.  Jabatan/Divisi  :  **{data.get('jabatan','')}",
         "b.  Pangkat & Gol  :",
         "c.  Biaya SPPD      :"],
        row2_h,
        wrap_idx=0,
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

    # ── ROW 7: Peserta ── (tinggi dinamis, semua baris bisa wrap)
    pi = data.get("peserta_ikut", [])
    pi_lines = [f"{i+1}.  **{p}" for i, p in enumerate(pi)]
    n_slot = max(len(pi), 4)             # minimal 4 slot kosong
    for i in range(len(pi), n_slot):
        pi_lines.append(f"{i+1}.")
    # Hitung tinggi total dari actual Paragraph height
    _top_pad7 = 0.38 * cm
    _total7   = _top_pad7
    for _vl in pi_lines:
        _total7 += _calc_line_h(_vl, wrap_extra=0) + 0.05 * cm
    row7_h = max(3.5, _total7 / cm + 0.3)
    draw_row(
        ["7.  Nama Yang Diikutsertakan"],
        pi_lines,
        row7_h,
        wrap_all=True,
        wrap_extra_cm=0,
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
            tiba_kota  = tujuan; tiba_tgl = tgl_b
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
    _bantuan_infix = "Bantuan " if data.get("is_bantuan") else ""
    header_text  = f"Tanda Terima Permintaan Biaya {_bantuan_infix}Perjalanan Dinas {nama_pejabat}"
    header_lines = _wrap_text(c, header_text, FONT_BOLD, 11, CONTENT_W)
    for line in header_lines:
        c.drawString(MARGIN_L, y, line)
        y -= 0.5 * cm
    y -= 0.1 * cm  # sedikit extra gap setelah header
    c.setFont(FONT_NORMAL, FONT_SIZE)
    c.drawString(MARGIN_L, y,
        f"Ke Kota {tujuan}, sesuai permintaan biaya {_bantuan_infix.lower()}no. {nomor_spd}")
    y -= 0.42 * cm
    c.drawString(MARGIN_L, y,
        f"Tanggal {tgl_b} s/d {tgl_k}. (\u00b1 {lama} hari)")
    y -= 0.38 * cm
    c.setLineWidth(2.0)
    c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y - 0.12*cm, PAGE_W - MARGIN_R, y - 0.12*cm)
    y -= 0.8 * cm

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

    def hotel_sub_row(uraian, biaya, keterangan, huruf=""):
        """Sub-baris rincian hotel: uraian + keterangan merah inline di baris yang sama."""
        nonlocal y
        item_row("", f"   {uraian}", 1, biaya, biaya)
        if huruf:
            c.setFont(FONT_NORMAL, FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawString(no_x + 0.4*cm, y + rh, huruf)
        if keterangan:
            teks_uraian = f"   {uraian}"
            lebar_uraian = stringWidth(teks_uraian, FONT_NORMAL, FONT_SIZE)
            c.setFont(FONT_NORMAL, FONT_SIZE - 1)
            c.setFillColor(colors.red)
            c.drawString(ket_x + lebar_uraian + 0.15*cm, y + rh, keterangan)
            c.setFillColor(colors.black)
            c.setFont(FONT_NORMAL, FONT_SIZE)

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
        hotel_items = data.get("hotel_items", [])
        if hotel_items:
            total_h = sum(h.get("biaya", 0) for h in hotel_items)
            item_row("3", "Biaya Penginapan", None, None, total_h)
            # Pisah: item uraian="" → baris 30%; item uraian!="" → hotel biasa (dengan huruf)
            items_30pct = [h for h in hotel_items if not h.get("uraian")]
            items_hotel = [h for h in hotel_items if h.get("uraian")]
            for h in items_30pct:
                hotel_sub_row("30% pagu penginapan", h.get("biaya", 0), h.get("keterangan") or "")
            multi = len(items_hotel) > 1
            for i, h in enumerate(items_hotel):
                huruf = chr(ord('a') + i) + "." if multi else ""
                hotel_sub_row(h.get("uraian", ""), h.get("biaya", 0), h.get("keterangan") or "", huruf)
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

    # Kiri: Mengetahui | Kanan: Yang Menerima,
    c.drawCentredString(ctr_left, y, "Mengetahui/Menyetujui :")
    c.drawCentredString(ctr_rght, y, "Yang Menerima,")
    y -= 0.42 * cm

    # Kiri: Perumda... | Kanan: jabatan penerima
    c.drawCentredString(ctr_left, y, "Perumda Tirta Manuntung Balikpapan")
    c.drawCentredString(ctr_rght, y, data.get("jabatan_penerima", ""))
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
    nomor_surat = data.get("nomor_surat", "")
    nomor_suffix = data.get("nomor_surat_suffix", "")
    if nomor_surat:
        c.drawCentredString(PAGE_W/2, y, f"Nomor : {nomor_surat}")
    elif nomor_suffix:
        # "Nomor : ___/1421002/10a-I/II/2026" — nomor urut kosong untuk diisi manual
        label       = "Nomor : "
        suffix_text = f"/{nomor_suffix}"
        label_w     = c.stringWidth(label,       FONT_NORMAL, FONT_SIZE)
        suffix_w    = c.stringWidth(suffix_text, FONT_NORMAL, FONT_SIZE)
        line_w      = 2.5 * cm
        x_label = PAGE_W/2 - (label_w + line_w + suffix_w) / 2
        c.drawString(x_label, y, label)
        x_line = x_label + label_w
        c.setLineWidth(0.5)
        c.line(x_line, y - 1, x_line + line_w, y - 1)
        c.drawString(x_line + line_w, y, suffix_text)
    else:
        label = "Nomor : "
        label_w = c.stringWidth(label, FONT_NORMAL, FONT_SIZE)
        line_w = 6.5 * cm
        x_label = PAGE_W/2 - (label_w + line_w) / 2
        c.drawString(x_label, y, label)
        x_line = x_label + label_w
        c.setLineWidth(0.5)
        c.line(x_line, y - 1, x_line + line_w, y - 1)
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
    biaya_row("2.", "Biaya Penginapan", fmt_rp2(data.get("biaya_penginapan",0)))
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
    c.drawCentredString(cx_rght, y, data.get("jabatan_penerima",""))
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
# LAPORAN PERJALANAN DINAS
# ══════════════════════════════════════════════════════════════

# F4 Landscape untuk laporan realisasi & rekap semester
_F4L = (330*mm, 215*mm)
_PWL, _PHL = _F4L
_ML = _MR = 1.5*cm
_MT = _MB = 1.5*cm
_CWL = _PWL - _ML - _MR   # content width landscape ≈ 850pt
_CWP = PAGE_W - MARGIN_L - MARGIN_R   # content width portrait ≈ 524pt

# Kolom laporan realisasi (pt, sum = _CWL ≈ 850)
# Merged (6): No | Tgl_B | Tgl_K | Uraian | Kota | No.SPD
_LAP_CM = [15, 48, 48, 122, 45, 72]   # sum=350
# Per-orang (8): Nama | Jabatan | Voucher | SPPD | Tiket | Hotel | Lain | Total
_LAP_CP = [90, 80, 55, 57, 57, 50, 55, 56]  # sum=500  → total=850

_LAP_ROW_H = 0.50*cm
_LAP_HDR_H = 0.65*cm
_LAP_FS    = 7.5

_STRUKTUR_KAT = {
    "DIRUT":"Direksi", "DIRUM":"Direksi", "DIRTEK":"Direksi", "DIROPS":"Direksi",
    "DEWAS_KETUA":"Dewan Pengawas", "DEWAS_ANGGOTA":"Dewan Pengawas",
    "DEWAS_ANGGOTA_1":"Dewan Pengawas", "DEWAS_ANGGOTA_2":"Dewan Pengawas",
    "ADM_MANAJER":"Adm/Keuangan", "ADM_SUPERVISOR":"Adm/Keuangan",
    "ADM_STAF_PELAKSANA":"Adm/Keuangan",
    "TEKNIK_MANAJER":"Teknik/Operasional", "TEKNIK_SUPERVISOR":"Teknik/Operasional",
    "TEKNIK_STAF_PELAKSANA":"Teknik/Operasional", "BANTUAN":"Teknik/Operasional",
}

_STRUKTUR_KELOMPOK = {
    "DIRUT":"I", "DIRUM":"I", "DIRTEK":"I", "DIROPS":"I",
    "DEWAS_KETUA":"I", "DEWAS_ANGGOTA":"I",
    "DEWAS_ANGGOTA_1":"I", "DEWAS_ANGGOTA_2":"I",
    "ADM_MANAJER":"II", "TEKNIK_MANAJER":"II",
    "ADM_SUPERVISOR":"III", "TEKNIK_SUPERVISOR":"III",
    "ADM_STAF_PELAKSANA":"IV", "TEKNIK_STAF_PELAKSANA":"IV", "BANTUAN":"IV",
}

_KELOMPOK_LABEL = {
    "I":  "DIREKSI & DEWAN PENGAWAS",
    "II": "MANAJER",
    "III":"SUPERVISOR",
    "IV": "STAF",
}


def _draw_kop_lap(c, pw, ph, ml, mr, mt):
    """Kop surat generik untuk laporan (portrait atau landscape)."""
    y_top = ph - mt
    logo_size = 1.9 * cm
    logo_x = ml
    logo_y = y_top - logo_size
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, logo_x, logo_y, width=logo_size, height=logo_size,
                    preserveAspectRatio=True, mask="auto")
    nama_x = logo_x + logo_size + 0.4*cm
    text_cx = nama_x + (pw - mr - nama_x) / 2
    c.setFont(FONT_BOLD, 13)
    c.setFillColor(colors.black)
    c.drawCentredString(text_cx, y_top - 0.60*cm, "PERUSAHAAN UMUM DAERAH")
    c.drawCentredString(text_cx, y_top - 1.15*cm, "TIRTA MANUNTUNG BALIKPAPAN")
    ly1 = y_top - logo_size - 0.20*cm
    ly2 = ly1 - 0.12*cm
    c.setStrokeColor(colors.black)
    c.setLineWidth(2.5)
    c.line(ml, ly1, pw - mr, ly1)
    c.setLineWidth(0.8)
    c.line(ml, ly2, pw - mr, ly2)
    return ly2 - 0.25*cm


def _cell(c, text, x, y_top, w, h, fs=_LAP_FS, bold=False, align="c",
          bg=None, stroke=True, color=None):
    """Draw a single table cell. y_top = top edge of cell.
    Supports multi-line text via '\\n' (uses Paragraph)."""
    if bg:
        c.setFillColor(bg)
        c.rect(x, y_top - h, w, h, fill=1, stroke=0)
    if stroke:
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.4)
        c.rect(x, y_top - h, w, h, fill=0, stroke=1)
    c.setFillColor(color or colors.black)
    fn = FONT_BOLD if bold else FONT_NORMAL
    txt = str(text)
    pad = 1.5

    if "\n" in txt:
        # Multi-line: use Paragraph for proper line breaks
        al_map = {"c": 1, "l": 0, "r": 2}
        style = ParagraphStyle("cl", fontName=fn, fontSize=fs,
                               leading=fs * 1.3,
                               alignment=al_map.get(align, 1))
        p = Paragraph(txt.replace("\n", "<br/>"), style)
        pw2, ph2 = p.wrap(max(w - pad * 2, 1), max(h - 2, 1))
        py = y_top - h / 2 + ph2 / 2
        p.drawOn(c, x + pad, py - ph2)
    else:
        c.setFont(fn, fs)
        ty = y_top - h / 2 - fs * 0.35
        if align == "c":
            c.drawCentredString(x + w / 2, ty, txt)
        elif align == "r":
            c.drawRightString(x + w - pad, ty, txt)
        else:
            c.drawString(x + pad, ty, txt)


def _merged_cell(c, text, x, y_top, w, gh, fs=_LAP_FS, bg=None, stroke=True):
    """Draw a vertically merged cell (height gh). Text wrapped & centered."""
    if bg:
        c.setFillColor(bg)
        c.rect(x, y_top - gh, w, gh, fill=1, stroke=0)
    if stroke:
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.4)
        c.rect(x, y_top - gh, w, gh, fill=0, stroke=1)
    if not text:
        return
    c.setFillColor(colors.black)
    style = ParagraphStyle("mc", fontName=FONT_NORMAL, fontSize=fs,
                           leading=fs*1.3, alignment=1, wordWrap="LTR")
    p = Paragraph(str(text), style)
    pw2, ph2 = p.wrap(max(w - 3, 1), max(gh - 2, 1))
    py = y_top - gh/2 + ph2/2
    p.drawOn(c, x + 1.5, py - ph2)


def _rp(n):
    """Format angka ke string ribuan."""
    if not n:
        return "-"
    return "{:,.0f}".format(n).replace(",", ".")


def _d_short(s):
    """'2026-01-04' → '4-Jan'"""
    if not s:
        return ""
    try:
        d = datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
        bln = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"][d.month-1]
        return f"{d.day}-{bln}"
    except Exception:
        return str(s)[:8]


def generate_laporan_realisasi(data: dict) -> BytesIO:
    """
    Generate PDF Laporan Realisasi SPPD (Tabel I.6) — F4 Landscape.
    data = {
        "groups": [...],    # dari get_sppd_realisasi_laporan()
        "bulan": int,
        "tahun": int,
        "ttd": {"menyetujui": str, "diperiksa": str, "dibuat": str}
    }
    """
    groups = data.get("groups", [])
    bulan  = data["bulan"]
    tahun  = data["tahun"]
    ttd    = data.get("ttd", {})

    PW, PH = _PWL, _PHL
    ML, MR = _ML, _MR
    MB     = _MB
    CW     = _CWL
    CM2    = _LAP_CM   # merged col widths
    CP2    = _LAP_CP   # per-person col widths
    RH     = _LAP_ROW_H
    HH     = _LAP_HDR_H
    FS     = _LAP_FS

    GREY  = colors.HexColor("#E0E0E0")
    LGREY = colors.HexColor("#F5F5F5")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(PW, PH))

    def tbl_header(y):
        hm = ["No","Tgl\nBrgkt","Tgl\nKmbli","Uraian Kegiatan","Kota","No. SPD/\nVoucher"]
        hp = ["Nama","Jabatan","No.\nVoucher","SPPD\n(Rp)","Tiket\n(Rp)","Hotel\n(Rp)","Biaya\nLain (Rp)","Total\n(Rp)"]
        x = ML
        for w, lbl in zip(CM2, hm):
            _cell(c, lbl, x, y, w, HH, bold=True, align="c", bg=GREY, fs=FS)
            x += w
        for w, lbl in zip(CP2, hp):
            _cell(c, lbl, x, y, w, HH, bold=True, align="c", bg=GREY, fs=FS)
            x += w
        return y - HH

    def draw_group(y, no_urut, group):
        v    = group["visum"]
        rows = group["sppd_rows"]
        n    = len(rows)
        gh   = n * RH
        bg   = LGREY if no_urut % 2 == 0 else None

        mvals = [
            str(no_urut),
            _d_short(v.get("tanggal_berangkat")),
            _d_short(v.get("tanggal_kembali")),
            v.get("keperluan", "") or "",
            v.get("tujuan", "") or "",
            v.get("nomor_spd", "") or "",
        ]
        x = ML
        for w, val in zip(CM2, mvals):
            _merged_cell(c, val, x, y, w, gh, fs=FS, bg=bg)
            x += w

        x_p = x
        for row in rows:
            pvals = [
                smart_title(row.get("nama","") or ""),
                smart_title(row.get("jabatan","") or ""),
                row.get("nomor_voucher","") or "-",
                _rp(row.get("uang_saku",0)),
                _rp(row.get("tiket",0)),
                _rp(row.get("hotel",0)),
                _rp(row.get("biaya_lain",0)),
                _rp(row.get("total",0)),
            ]
            aligns = ["l","l","c","r","r","r","r","r"]
            x = x_p
            for w, val, al in zip(CP2, pvals, aligns):
                _cell(c, val, x, y, w, RH, align=al, fs=FS, bg=bg)
                x += w
            y -= RH
        return y

    def page_header():
        y = _draw_kop_lap(c, PW, PH, ML, MR, _MT)
        c.setFont(FONT_BOLD, 8.5)
        c.drawCentredString(PW/2, y, "Tabel I.6  REALISASI SURAT PERMINTAAN PERJALANAN DINAS (SPPD)")
        y -= 0.38*cm
        c.drawCentredString(PW/2, y, f"BULAN {BULAN_ID[bulan].upper()} {tahun}")
        y -= 0.35*cm
        return tbl_header(y)

    def lap_footer(y):
        from collections import defaultdict
        kat_tot = defaultdict(int)
        grand   = 0
        for g in groups:
            for row in g["sppd_rows"]:
                kat = _STRUKTUR_KAT.get(row.get("struktur_rkap",""), "Lain-lain")
                kat_tot[kat] += row.get("total", 0)
                grand += row.get("total", 0)

        y -= 0.25*cm
        c.setFont(FONT_NORMAL, FS)
        for kat in ["Dewan Pengawas","Direksi","Adm/Keuangan","Teknik/Operasional"]:
            if kat in kat_tot:
                c.drawString(ML, y, kat)
                c.drawString(ML + 5*cm, y, "Rp {:,.0f}".format(kat_tot[kat]).replace(",","."))
                y -= 0.38*cm
        c.setFont(FONT_BOLD, FS + 0.5)
        c.drawString(ML, y, f"TOTAL BIAYA SPPD BULAN {BULAN_ID[bulan].upper()} {tahun}")
        c.drawString(ML + 5*cm, y, "Rp {:,.0f}".format(grand).replace(",","."))

        # TTD
        y -= 0.5*cm
        from datetime import date as _date
        tgl_str = f"Balikpapan, {fmt_tgl(_date.today())}"
        cw3 = CW / 3
        c.setFont(FONT_NORMAL, FS)
        c.drawRightString(PW - MR, y, tgl_str)
        y -= 0.35*cm
        for i, (lbl1, lbl2) in enumerate([
            ("Menyetujui :", "Manajer Sekretaris Perusahaan"),
            ("Diperiksa Oleh :", "Supervisor Kesekretariatan & Hukum"),
            ("Dibuat Oleh :", "Staf Kesekretariatan & Hukum"),
        ]):
            cx = ML + cw3 * (i + 0.5)
            c.drawCentredString(cx, y, lbl1)
        y -= 0.35*cm
        for i, lbl2 in enumerate([
            "Manajer Sekretaris Perusahaan",
            "Supervisor Kesekretariatan & Hukum",
            "Staf Kesekretariatan & Hukum",
        ]):
            cx = ML + cw3 * (i + 0.5)
            c.drawCentredString(cx, y, lbl2)

        y -= 2.0*cm
        nms = [
            (ttd.get("menyetujui","") or "").upper(),
            (ttd.get("diperiksa","") or "").upper(),
            (ttd.get("dibuat","") or "").upper(),
        ]
        for i, nm in enumerate(nms):
            if nm:
                cx = ML + cw3 * (i + 0.5)
                c.setFont(FONT_BOLD, FS)
                nw = c.stringWidth(nm, FONT_BOLD, FS)
                c.drawCentredString(cx, y, nm)
                c.setLineWidth(0.8)
                c.line(cx - nw/2 - 2, y - 2, cx + nw/2 + 2, y - 2)

    # ── Render ──
    y = page_header()
    for no_urut, group in enumerate(groups, 1):
        gh = len(group["sppd_rows"]) * RH
        if y - gh < MB + 4.5*cm:
            c.showPage()
            y = page_header()
        y = draw_group(y, no_urut, group)

    # Garis bawah tabel
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.line(ML, y, PW - MR, y)

    lap_footer(y)
    c.save()
    buf.seek(0)
    return buf


def generate_rekap_bulanan(data: dict) -> BytesIO:
    """
    Generate PDF Rekap Perjalanan Dinas Bulanan — F4 Portrait.
    data = {
        "rekap": {(bulan,tahun): [...]},  # dari get_rekap_perjalanan([(b,t)])
        "bulan": int,
        "tahun": int,
        "ttd": {"menyetujui": str, "diperiksa": str, "dibuat": str}
    }
    """
    bulan = data["bulan"]
    tahun = data["tahun"]
    ttd   = data.get("ttd", {})
    rekap = data.get("rekap", {}).get((bulan, tahun), [])

    LOKASI_DALAM_ID = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"
    LOKASI_LUAR_ID  = "99c9f92f-972f-46d5-99d4-219b758d2cb7"

    PW, PH = PAGE_W, PAGE_H
    ML, MR = MARGIN_L, MARGIN_R
    MB     = MARGIN_B
    CW     = _CWP
    FS     = 9.0
    RH     = 0.52*cm
    HH     = 0.60*cm

    GREY  = colors.HexColor("#D9D9D9")
    LGREY = colors.HexColor("#F2F2F2")
    LBLUE = colors.HexColor("#EEF4FF")

    # Kolom: No(20) | Jabatan(285) | Dalam(76) | Luar(76) | Total(67) = 524
    CWS = [20, 285, 76, 76, 67]

    buf = BytesIO()
    c   = canvas.Canvas(buf, pagesize=(PW, PH))

    # Kelompokkan rekap by kelompok & jabatan
    from collections import defaultdict
    jab_map = {}   # jabatan → {dalam:int, luar:int}
    for row in rekap:
        jab = row["jabatan"] or "?"
        lok = row["lokasi_id"]
        cnt = row["count"]
        if jab not in jab_map:
            jab_map[jab] = {"dalam":0, "luar":0, "rkap":row.get("struktur_rkap","")}
        if lok == LOKASI_DALAM_ID:
            jab_map[jab]["dalam"] += cnt
        else:
            jab_map[jab]["luar"]  += cnt

    # Urutan kelompok
    def kel(rkap): return _STRUKTUR_KELOMPOK.get(rkap, "IV")
    jabatan_sorted = sorted(jab_map.items(), key=lambda x: (kel(x[1]["rkap"]), x[0]))

    y = _draw_kop_lap(c, PW, PH, ML, MR, MARGIN_T)
    c.setFont(FONT_BOLD, 11)
    c.drawCentredString(PW/2, y, "REKAPITULASI DATA PERJALANAN DINAS")
    y -= 0.45*cm
    c.drawCentredString(PW/2, y, f"{BULAN_ID[bulan].upper()} {tahun}")
    y -= 0.5*cm

    # Header tabel
    hdrs = ["No", "Kelompok & Jabatan", "Dalam\nProv. Kaltim", "Luar\nProv. Kaltim", "Total\nKeberangkatan"]
    x = ML
    for w, h in zip(CWS, hdrs):
        _cell(c, h, x, y, w, HH, bold=True, align="c", bg=GREY, fs=FS)
        x += w
    y -= HH

    no_jab  = 0
    cur_kel = None
    tot_dlm = tot_luar = 0

    for jab, info in jabatan_sorted:
        k = kel(info["rkap"])
        if k != cur_kel:
            # Kelompok header row
            label = f"{k}. {_KELOMPOK_LABEL.get(k, k)}"
            x = ML
            _cell(c, label, x, y, CW, RH, bold=True, align="l", bg=LGREY, fs=FS, stroke=True)
            # draw inner borders
            for w in CWS:
                c.setStrokeColor(colors.black)
                c.setLineWidth(0.4)
                c.rect(x, y - RH, w, RH, fill=0, stroke=1)
                x += w
            y -= RH
            cur_kel = k
            no_jab  = 0
            if y < MB + 4*cm:
                c.showPage()
                y = PH - MARGIN_T - 0.5*cm

        no_jab += 1
        dlm  = info["dalam"]
        luar = info["luar"]
        tot  = dlm + luar
        tot_dlm  += dlm
        tot_luar += luar

        vals  = [str(no_jab), smart_title(jab), str(dlm) if dlm else "-", str(luar) if luar else "-",
                 str(tot) if tot else "-"]
        aligns= ["c","l","c","c","c"]
        x = ML
        for w, v, al in zip(CWS, vals, aligns):
            _cell(c, v, x, y, w, RH, align=al, fs=FS)
            x += w
        y -= RH

        if y < MB + 4*cm:
            c.showPage()
            y = PH - MARGIN_T - 0.5*cm

    # Total row
    grand = tot_dlm + tot_luar
    vals  = ["", "TOTAL KESELURUHAN", str(tot_dlm), str(tot_luar), str(grand)]
    aligns= ["c","l","c","c","c"]
    x = ML
    for w, v, al in zip(CWS, vals, aligns):
        _cell(c, v, x, y, w, RH, bold=True, align=al, bg=GREY, fs=FS)
        x += w
    y -= RH

    # TTD
    from datetime import date as _date
    y -= 0.4*cm
    c.setFont(FONT_NORMAL, FS)
    tgl_str = f"Balikpapan, {fmt_tgl(_date.today())}"
    c.drawRightString(PW - MR, y, tgl_str)
    y -= 0.35*cm

    cw3 = CW / 3
    for i, (l1, l2) in enumerate([
        ("Menyetujui :", "Manajer Sekretaris Perusahaan"),
        ("Diperiksa Oleh :", "Supervisor Kesekretariatan & Hukum"),
        ("Dibuat Oleh :", "Staf Kesekretariatan & Hukum"),
    ]):
        cx = ML + cw3*(i+0.5)
        c.drawCentredString(cx, y, l1)
    y -= 0.35*cm
    for i, l2 in enumerate([
        "Manajer Sekretaris Perusahaan",
        "Supervisor Kesekretariatan & Hukum",
        "Staf Kesekretariatan & Hukum",
    ]):
        c.drawCentredString(ML + cw3*(i+0.5), y, l2)

    y -= 2.0*cm
    for i, nm_key in enumerate(["menyetujui","diperiksa","dibuat"]):
        nm = (ttd.get(nm_key,"") or "").upper()
        if nm:
            cx = ML + cw3*(i+0.5)
            c.setFont(FONT_BOLD, FS)
            nw = c.stringWidth(nm, FONT_BOLD, FS)
            c.drawCentredString(cx, y, nm)
            c.setLineWidth(0.8)
            c.line(cx - nw/2 - 2, y - 2, cx + nw/2 + 2, y - 2)

    c.save()
    buf.seek(0)
    return buf


def generate_rekap_semester(data: dict) -> BytesIO:
    """
    Generate PDF Rekap Perjalanan Dinas Semester — F4 Landscape.
    data = {
        "rekap": {(b,t): [...]},     # dari get_rekap_perjalanan(6 bulan)
        "bulan_list": [(b,t), ...],  # 6 bulan berurutan
        "ttd": {"menyetujui": str, "diperiksa": str, "dibuat": str}
    }
    """
    bulan_list = data.get("bulan_list", [])
    rekap      = data.get("rekap", {})
    ttd        = data.get("ttd", {})
    if not bulan_list:
        buf = BytesIO(); buf.write(b""); buf.seek(0); return buf

    LOKASI_DALAM_ID = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"
    LOKASI_LUAR_ID  = "99c9f92f-972f-46d5-99d4-219b758d2cb7"

    PW, PH = _PWL, _PHL
    ML, MR = _ML, _MR
    MB     = _MB
    CW     = _CWL
    FS     = 7.5
    RH     = 0.50*cm
    HH1    = 0.55*cm   # header baris 1
    HH2    = 0.50*cm   # header baris 2

    GREY  = colors.HexColor("#D9D9D9")
    LGREY = colors.HexColor("#F2F2F2")

    # Kolom: No(15) | Jabatan(260) | [Dlm(42)+Luar(42)]×6 | Total(71) = 850
    CW_NO  = 15
    CW_JAB = 260
    CW_DLM = 42
    CW_LUR = 42
    CW_TOT = 71
    # verify: 15+260+6*(42+42)+71 = 15+260+504+71 = 850 ✓

    buf = BytesIO()
    c   = canvas.Canvas(buf, pagesize=(PW, PH))

    # Build jabatan map keseluruhan
    from collections import defaultdict
    all_jab = set()
    for bt in bulan_list:
        for row in rekap.get(bt, []):
            if row["jabatan"]:
                all_jab.add((row["jabatan"], row.get("struktur_rkap","")))

    # jab_data[jabatan] = {(b,t): {dalam:n, luar:n}}
    jab_data = {}
    for jab, rkap_val in all_jab:
        jab_data[jab] = {"rkap": rkap_val}
        for bt in bulan_list:
            jab_data[jab][bt] = {"dalam": 0, "luar": 0}

    for bt in bulan_list:
        for row in rekap.get(bt, []):
            jab = row["jabatan"]
            if not jab or jab not in jab_data:
                continue
            lok = row["lokasi_id"]
            cnt = row["count"]
            if lok == LOKASI_DALAM_ID:
                jab_data[jab][bt]["dalam"] += cnt
            else:
                jab_data[jab][bt]["luar"]  += cnt

    def kel(rkap_v): return _STRUKTUR_KELOMPOK.get(rkap_v, "IV")
    jab_sorted = sorted(jab_data.items(), key=lambda x: (kel(x[1]["rkap"]), x[0]))

    y = _draw_kop_lap(c, PW, PH, ML, MR, _MT)

    b0, t0 = bulan_list[0]
    b1, t1 = bulan_list[-1]
    c.setFont(FONT_BOLD, 9)
    c.drawCentredString(PW/2, y, "REKAPITULASI DATA PERJALANAN DINAS")
    y -= 0.38*cm
    c.drawCentredString(PW/2, y,
        f"{BULAN_ID[b0].upper()} - {BULAN_ID[b1].upper()} {t1}")
    y -= 0.42*cm

    # Header 2 baris
    # Baris 1: No (span 2 rows) | Kelompok (span 2 rows) | [BulanX Dalam | BulanX Luar] | Total (span 2)
    x = ML
    _cell(c, "No", x, y, CW_NO, HH1+HH2, bold=True, align="c", bg=GREY, fs=FS)
    x += CW_NO
    _cell(c, "Kelompok & Jabatan", x, y, CW_JAB, HH1+HH2, bold=True, align="c", bg=GREY, fs=FS)
    x += CW_JAB
    for (b, t) in bulan_list:
        _cell(c, BULAN_ID[b], x, y, CW_DLM+CW_LUR, HH1, bold=True, align="c", bg=GREY, fs=FS)
        x += CW_DLM + CW_LUR
    _cell(c, "Total\nKeberangkatan", x, y, CW_TOT, HH1+HH2, bold=True, align="c", bg=GREY, fs=FS)

    # Baris 2: Dalam | Luar per bulan
    y -= HH1
    x  = ML + CW_NO + CW_JAB
    for _ in bulan_list:
        _cell(c, "Dalam\nProv.", x, y, CW_DLM, HH2, bold=True, align="c", bg=GREY, fs=FS)
        x += CW_DLM
        _cell(c, "Luar\nProv.", x, y, CW_LUR, HH2, bold=True, align="c", bg=GREY, fs=FS)
        x += CW_LUR
    y -= HH2

    no_jab  = 0
    cur_kel = None
    col_tot = {bt: {"dalam":0,"luar":0} for bt in bulan_list}
    grand   = 0

    for jab, info in jab_sorted:
        k = kel(info["rkap"])
        if k != cur_kel:
            lbl = f"{k}. {_KELOMPOK_LABEL.get(k, k)}"
            x = ML
            # Draw group label spanning full width
            _cell(c, lbl, x, y, CW, RH, bold=True, align="l", bg=LGREY, fs=FS)
            y -= RH
            cur_kel = k
            no_jab  = 0
            if y < MB + 4*cm:
                c.showPage()
                y = PH - _MT - 0.3*cm

        no_jab += 1
        row_tot = 0
        x = ML
        _cell(c, str(no_jab), x, y, CW_NO, RH, align="c", fs=FS)
        x += CW_NO
        _cell(c, smart_title(jab), x, y, CW_JAB, RH, align="l", fs=FS)
        x += CW_JAB
        for bt in bulan_list:
            dlm = info[bt]["dalam"]
            lur = info[bt]["luar"]
            col_tot[bt]["dalam"] += dlm
            col_tot[bt]["luar"]  += lur
            row_tot += dlm + lur
            _cell(c, str(dlm) if dlm else "-", x, y, CW_DLM, RH, align="c", fs=FS)
            x += CW_DLM
            _cell(c, str(lur) if lur else "-", x, y, CW_LUR, RH, align="c", fs=FS)
            x += CW_LUR
        grand += row_tot
        _cell(c, str(row_tot) if row_tot else "-", x, y, CW_TOT, RH, bold=True, align="c", fs=FS)
        y -= RH

        if y < MB + 4*cm:
            c.showPage()
            y = PH - _MT - 0.3*cm

    # Total row
    x = ML
    _cell(c, "", x, y, CW_NO, RH, bold=True, align="c", bg=GREY, fs=FS)
    x += CW_NO
    _cell(c, "TOTAL KESELURUHAN", x, y, CW_JAB, RH, bold=True, align="l", bg=GREY, fs=FS)
    x += CW_JAB
    run_grand = 0
    for bt in bulan_list:
        dlm = col_tot[bt]["dalam"]
        lur = col_tot[bt]["luar"]
        run_grand += dlm + lur
        _cell(c, str(dlm) if dlm else "-", x, y, CW_DLM, RH, bold=True, align="c", bg=GREY, fs=FS)
        x += CW_DLM
        _cell(c, str(lur) if lur else "-", x, y, CW_LUR, RH, bold=True, align="c", bg=GREY, fs=FS)
        x += CW_LUR
    _cell(c, str(run_grand), x, y, CW_TOT, RH, bold=True, align="c", bg=GREY, fs=FS)
    y -= RH

    # TTD
    from datetime import date as _date
    y -= 0.4*cm
    c.setFont(FONT_NORMAL, FS)
    tgl_str = f"Balikpapan, {fmt_tgl(_date.today())}"
    c.drawRightString(PW - MR, y, tgl_str)
    y -= 0.35*cm

    cw3 = CW / 3
    for i, l1 in enumerate(["Menyetujui :", "Diperiksa Oleh :", "Dibuat Oleh :"]):
        c.drawCentredString(ML + cw3*(i+0.5), y, l1)
    y -= 0.35*cm
    for i, l2 in enumerate([
        "Manajer Sekretaris Perusahaan",
        "Supervisor Kesekretariatan & Hukum",
        "Staf Kesekretariatan & Hukum",
    ]):
        c.drawCentredString(ML + cw3*(i+0.5), y, l2)

    y -= 2.0*cm
    for i, nm_key in enumerate(["menyetujui","diperiksa","dibuat"]):
        nm = (ttd.get(nm_key,"") or "").upper()
        if nm:
            cx = ML + cw3*(i+0.5)
            c.setFont(FONT_BOLD, FS)
            nw = c.stringWidth(nm, FONT_BOLD, FS)
            c.drawCentredString(cx, y, nm)
            c.setLineWidth(0.8)
            c.line(cx - nw/2 - 2, y - 2, cx + nw/2 + 2, y - 2)

    c.save()
    buf.seek(0)
    return buf


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