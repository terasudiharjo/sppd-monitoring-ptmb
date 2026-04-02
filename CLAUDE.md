# CLAUDE.md — Aplikasi Monitoring SPPD PTMB Balikpapan

## Gambaran Umum Project

Aplikasi web **Streamlit** untuk mengelola perjalanan dinas (SPPD) di Perumda Tirta Manuntung Balikpapan (PTMB).

- **Stack**: Python, Streamlit, Supabase (PostgreSQL cloud), ReportLab (PDF), Pandas, Plotly
- **Entry point**: `app.py` (login → langsung redirect ke Dashboard)
- **Login**: username: `sekper`, password: `ptmb2025`
- **Run app**: `streamlit run app.py` dari root folder

---

## Struktur Folder

```
Aplikasi Monitoring SPPD/
├── app.py                    # Entry point + auth → redirect ke 1_dashboard.py
├── pages/
│   ├── 1_dashboard.py        # Statistik & ringkasan SPPD
│   ├── 2_visum.py            # Visum, Surat Tugas, SPD, Disposisi
│   ├── 3_sppd.py             # Pencairan & Realisasi SPPD
│   ├── 4_rkap_monitor.py     # Monitor anggaran RKAP
│   └── 5_pegawai.py          # CRUD master data pegawai
├── utils/
│   ├── database.py           # Semua fungsi query Supabase
│   └── pdf_generator.py      # Generate 6 jenis dokumen PDF
├── data/
│   ├── *.csv                 # Data rule SPPD & RKAP
│   ├── realisasi_sppd_2026.csv  # Data historis Jan-Mar 2026 (untuk import nanti)
│   └── template_pdf/         # Template dokumen
├── setup/                    # Script import data awal
└── check/                    # Script debug & validasi DB
    └── cek_tabel.py          # Lihat semua tabel Supabase (jalankan dari folder check/)
```

### Test PDF (jalankan dari folder `utils/`):
```
utils/
├── test_visum.py
├── test_surat_tugas.py
├── test_spd.py
├── test_sppd_pencairan.py
├── test_sppd_realisasi.py
└── test_pernyataan_biaya.py
```

---

## Tabel Supabase yang Ada

| Tabel | Fungsi |
|---|---|
| `lokasi_sppd` | Dalam Kaltim / Luar Kaltim / Luar Negeri |
| `divisi` | Struktur divisi (hierarki, parent_id) |
| `jabatan` | Jabatan pegawai + level + struktur_rkap |
| `pegawai` | Data pegawai aktif |
| `rule_sppd` | Tarif perjalanan dinas per jabatan per lokasi |
| `rkap` | Anggaran per kategori per bulan |
| `visum` | Surat perintah perjalanan (header) |
| `sppd` | Detail biaya per pegawai per perjalanan |
| `spd` | Surat Penyediaan Dana (rekap per visum) |
| `sppd_biaya_lain` | Biaya lain-lain per sppd (keterangan + jumlah) |
| `sppd_trip_detail` | Rincian leg perjalanan transport per sppd |
| `sppd_sewa_kendaraan` | Sewa kendaraan (belum dipakai) |
| `dokumen` | Dokumen bukti (belum dipakai) |

### Kolom penting `visum`:
```
id, nomor_visum, tanggal_visum, tujuan, tanggal_berangkat, tanggal_kembali,
lama_hari, keperluan, peserta (jsonb), status,
disposisi (jsonb array) ← [{nomor, dari, perihal, link}, ...]
```
→ Bisa multi-surat disposisi per visum. Dipakai di Surat Tugas PDF (disposisi[0]).
→ `dari` = pengirim surat (opsional, backward compatible — data lama tanpa `dari` tetap jalan).

### Kolom penting `sppd`:
```
pegawai_id, visum_id, spd_id, rkap_id, lokasi_id,
total_hari, uang_harian_total, uang_makan_total, transport_lokal_total,
uang_representasi_total, subtotal_uang_saku,
total_transport, total_hotel, total_sewa_kendaraan,
biaya_jenazah, total_biaya,
menginap (BOOLEAN, default TRUE),
status (draft → pencairan → realisasi → completed / cancelled)
```

### Kolom penting `rule_sppd`:
```
jabatan, lokasi_id, uang_makan, transport_lokal, uang_saku,
uang_representasi, plafon_pesawat, plafon_hotel, berlaku_dari, status
```
→ `plafon_hotel` dipakai untuk hitung 30% kalau tidak menginap.

### Kolom penting `sppd_trip_detail`:
```
id, sppd_id, urutan, kota_asal, kota_tujuan,
tanggal_berangkat (NOT NULL), tanggal_kembali (NOT NULL),
jenis_transport, biaya_transport, created_at, updated_at
```
→ `tanggal_berangkat` & `tanggal_kembali` wajib diisi — diambil dari `visum` saat save.

### Kolom penting `sppd_biaya_lain`:
```
id, sppd_id, urutan, keterangan, jumlah, created_at
```

---

## Dokumen PDF yang Dihasilkan (`utils/pdf_generator.py`)

| Fungsi | Dokumen | Halaman | Status |
|---|---|---|---|
| `generate_surat_tugas(data)` | Surat Perintah Tugas | 2 hal | ✅ |
| `generate_spd(data)` | Surat Penyediaan Dana | 1 hal | ✅ |
| `generate_visum(data)` | Visum Lembaran I & II | 2 hal | ✅ |
| `generate_sppd_pencairan(data)` | Tanda Terima Pencairan | 1 hal | ✅ |
| `generate_sppd_realisasi(data)` | Tanda Terima Realisasi | 1 hal | ✅ |
| `generate_pernyataan_biaya(data)` | Pernyataan Pengeluaran Biaya Riil | 1 hal | ✅ |

**Semua PDF sudah selesai** ✅

---

## Status Pekerjaan

### ✅ Sudah selesai (per sesi 2026-03-30):

**PDF:**
1. Semua 6 dokumen PDF selesai dan ter-integrasi di UI
2. `generate_pernyataan_biaya`: layout final — "Yang bertandatangan di bawah ini", waktu pelaksanaan auto-format (bulan teks Indonesia), hanging indent poin 2&3, TTD rata tengah, sumber TTD kiri dari `get_pegawai_by_jabatan_nama("Direktur Umum")`
3. `generate_surat_tugas`: pembuka otomatis dari data disposisi visum (nomor + perihal)

**Navigasi & Auth:**
4. `app.py` → setelah login langsung `st.switch_page` ke `1_dashboard.py`
5. Urutan halaman: Dashboard → Visum → SPPD → RKAP Monitor → Pegawai

**Dashboard (`1_dashboard.py`):**
6. Bug status fixed: `"closed"` → `"completed"`, hapus `"dalam_perjalanan"`
7. Metric row 1: Total, Draft, Pencairan, Menunggu Realisasi, Selesai

**Visum (`2_visum.py`):**
8. Kolom disposisi di DB: `disposisi` (JSONB array `[{nomor, perihal, link}]`) — bisa multi-surat per visum
9. Tab 3 visum: UI CRUD disposisi (tambah/edit/delete per baris)
10. Daftar visum: kolom "Disposisi" tampil jumlah surat
11. Detail visum: tampil semua surat disposisi + tombol 🔗 buka Drive
12. Surat Tugas PDF: pembuka dari `disposisi[0]`
13. Fix dua kota tujuan, form tidak reset saat error, tambah kota IKN/Bogor/Batam

**Database (`database.py`):**
14. `get_pegawai_by_jabatan_nama(nama_jabatan)` — ambil nama pejabat by jabatan
15. `resolve_kategori_rkap`: `DEWAS_ANGGOTA_1` & `DEWAS_ANGGOTA_2` pass-through langsung; `DEWAS_ANGGOTA` lama tetap sebagai legacy fallback ke `DEWAS_ANGGOTA_1`
16. `update_rekap_spd`: handle `DEWAS_ANGGOTA_1` dan `DEWAS_ANGGOTA_2` masuk ke `total_dewas`

**SPPD (`3_sppd.py`):**
17. Bug fix `biaya_lain` hardcoded 0 di Pernyataan Biaya — sekarang dihitung dari `total_biaya - uang_saku - hotel - transport`
18. Perjalanan Dalam Kaltim: input transport disembunyikan, `total_transport = 0` otomatis
19. Bug fix `tr_items` NameError kalau Dalam Kaltim — sekarang `tr_items = []` sebagai default

**RKAP Monitor (`4_rkap_monitor.py`):**
20. Over budget: format sisa negatif tampil `⚠️ -Rp xxx`, status icon `🚨 OVER` untuk > 100%
21. Banner merah otomatis kalau ada kategori over budget
22. Threshold status: 🟢 < 75% | 🟡 75–90% | 🔴 90–100% | 🚨 > 100%

**Pegawai (`5_pegawai.py`):**
23. Tab baru "Kelola Jabatan" — tambah jabatan baru (termasuk `DEWAS_ANGGOTA_2`) dan nonaktifkan dari UI tanpa buka Supabase

### ✅ Sudah selesai (per sesi 2026-03-31):

**Git & Deployment:**
24. Repo GitHub: `github.com/terasudiharjo/sppd-monitoring-ptmb` (private)
25. App live di Streamlit Cloud: `https://sppd-ptmb.streamlit.app` (public, ada auth login)
26. Credentials login dipindah dari hardcode ke `.env` (APP_USERNAME, APP_PASSWORD)
27. Streamlit Cloud pakai Secrets untuk semua 4 env vars

**Import Data Historis:**
28. `setup/import_realisasi_2026.py` — import 19 visum + 52 sppd Jan-Mar 2026, DRY_RUN mode, NAMA_MAP lengkap
29. `setup/deduct_rkap_historis.py` — update rkap.anggaran_terpakai dari sppd historis (status=completed, rkap_id=null)
30. Kedua script sudah dijalankan ke DB production (data Jan-Mar 2026 sudah masuk)

**Bug Fix:**
31. `3_sppd.py`: fallback lookup rkap_id saat pencairan jika rkap_id null — cari dari jabatan+bidang+lokasi+bulan, deduct RKAP, simpan rkap_id
32. `1_dashboard.py`: total anggaran terpakai & uang saku exclude draft & cancelled (konsisten dengan RKAP Monitor)

### ✅ Sudah selesai (per sesi 2026-04-01):

**Revisi PDF Visum (`pages/2_visum.py`, `utils/pdf_generator.py`):**
33. Format jabatan di Nomor 2 & Nomor 7 visum: `Man - [divisi]` / `Spv - [divisi]` / `Staf - [divisi]` — prefix "Divisi"/"Sub Divisi" di-strip otomatis via regex
34. Nama pegawai & jabatan: title case (`.title()`)
35. Text wrap otomatis untuk Nomor 2 (jabatan panjang) dan Nomor 7 (nama peserta panjang) — tinggi row dihitung dinamis
36. Extra gap 0.15cm setelah baris yang wrap di Nomor 2 (supaya tidak terlalu rapat ke b. Pangkat)
37. Nomor peserta di Nomor 7: format `1.  Nama` (tambah titik)

**Disposisi Visum — tambah field `dari`:**
38. Field `dari` (pengirim surat) ditambah ke struktur disposisi: `{nomor, dari, perihal, link}`
39. UI Tab 3 CRUD disposisi: kolom baru "Dari" (5 kolom sekarang)
40. Form buat visum baru: input "Dari (Pengirim Surat)"
41. Pembuka Surat Tugas PDF: format baru → "surat dari [dari], dengan Nomor Surat [nomor], perihal [perihal]"
42. Helper `_build_pembuka()` — fleksibel, skip bagian yang kosong

### ✅ Sudah selesai (per sesi 2026-04-01, sesi lanjutan):

**Revisi PDF Surat Tugas (`pages/2_visum.py`, `utils/pdf_generator.py`):**
43. Gap setelah tabel peserta diperbesar (0.45→0.65cm)
44. "Tujuan Perjalanan Dinas" word-wrap dengan hanging indent di `val_x`
45. `fmt_waktu_surat_tugas()` — format tanggal cerdas: 1 hari, rentang 1 bulan, lintas bulan — pakai nama hari Indonesia
46. Nama, jabatan, divisi peserta: title case
47. Kolom Jabatan: format abbreviasi `Man/Spv/Staf - [nama]` (strip prefix "Divisi"/"Sub Divisi")
48. Kolom Divisi: Manajer→divisi sendiri, Spv/Staf→divisi parent, Direksi/Dewas→"-"
49. Dirut dikecualikan dari daftar peserta Surat Tugas

**Revisi PDF SPD (`pages/2_visum.py`, `utils/pdf_generator.py`):**
50. Warna teks per kategori (bukan background): Direksi=biru, Adm/Teknik hijau/ungu, Dewas=oranye
51. `SPD_ROW_COLORS` dict: `{1: biru, 2: hijau, 3: ungu, 4: oranye}` (5=hitam/default)
52. Peserta warna ikut kategorinya masing-masing (mapping via `struktur_rkap` + `bidang`)
53. Peserta diurutkan: Dirut selalu pertama, lalu per kategori, lalu level tertinggi ke bawah
54. Kolom jabatan peserta: text wrap otomatis (dynamic row height via `Paragraph.wrap()`)

**Revisi PDF SPPD Tanda Terima (`utils/pdf_generator.py`, `pages/3_sppd.py`):**
55. Garis horizontal setelah "Tanggal..." di `_draw_tanda_terima`
56. TTD kanan: "Yang Menerima," sejajar "Mengetahui/Menyetujui :"
57. `jabatan_penerima` tampil di TTD kanan (format: "Manajer/Supervisor/Staf [nama divisi] PTMB")
58. `format_jabatan_sppd_penerima()` di `3_sppd.py` — full words, Manajer→parent divisi, Spv/Staf→divisi sendiri
59. Bug fix session state: nama yang dipilih tidak reset saat status sppd berubah

**Revisi PDF Pernyataan Biaya Riil (`utils/pdf_generator.py`, `pages/3_sppd.py`):**
60. Nama penerima: title case
61. `dir_umum_nama` diambil dari DB (`get_pegawai_by_jabatan_nama("Direktur Umum")`), fallback "Direktur Umum" — `.title()`
62. TTD kanan: `jabatan_penerima` tampil di bawah "Penerima SPPD,"

### ✅ Sudah selesai (per sesi 2026-04-02):

**Bug Fix:**
63. `3_sppd.py:411`: fix `get_pegawai_by_jabatan_nama("Direktur Umum")` → `"DIREKTUR BIDANG UMUM"` — nama jabatan di DB adalah uppercase full name, bukan "Direktur Umum". Sekarang nama Direktur Umum tampil benar di PDF Pernyataan Biaya.

**Script:**
64. `setup/clean_db.py` — script bersihkan data transaksi (DRY_RUN=True default):
    - Hapus: sppd_biaya_lain → sppd_trip_detail → sppd → spd → visum (urut child→parent)
    - Reset: rkap.anggaran_terpakai=0, anggaran_sisa=anggaran_awal
    - Ada verifikasi akhir (cek semua tabel = 0 record)

### ⏳ BELUM DIKERJAKAN — lanjut sesi berikutnya:

#### Sesi berikutnya — langkah pertama:
- **Test DRY RUN clean_db**: `python setup/clean_db.py` — cek jumlah data yang akan dihapus, pastikan output sesuai

#### Setelah Testing (saat ini sedang testing di tim sekper):
1. **Fitur Laporan/Reporting** (`pages/6_laporan.py`) — halaman baru:
   - Rekap jumlah perjalanan dinas per bulan & semester (trip, orang, total biaya)
   - Laporan realisasi per bulan & semester (format tabel seperti `data/realisasi_sppd_2026.csv`)
   - Bisa di-print / export PDF
2. **Optimasi performa** — `st.form` untuk form realisasi, `@st.cache_data` untuk query master data (tunggu testing selesai)

#### Flow Go-Live (setelah testing selesai):
```
1. python setup/clean_db.py
2. python setup/import_realisasi_2026.py  (DRY_RUN=False)
3. python setup/deduct_rkap_historis.py   (DRY_RUN=False)
4. App live ✅
```

#### Opsional:
- **Test file PDF**: update `test_sppd_realisasi.py` (tambah `biaya_lain`) dan `test_sppd_pencairan.py` (skenario tidak menginap)

---

## Keputusan Desain yang Sudah Disepakati

### Penginapan (Hotel)

Toggle menginap ada di **pencairan DAN realisasi**, tapi dengan perilaku berbeda:

**Di Pencairan:**
- Toggle default: **Menginap** (TRUE)
- Menginap → `total_hotel = 0` (hotel bayar sendiri dulu, reimburse nanti)
- Tidak menginap → `total_hotel = plafon_hotel × 30%`, langsung masuk pencairan
- Pilihan ini disimpan ke kolom `sppd.menginap`

**Di Realisasi:**
- Cek kolom `menginap` dari DB
- Kalau pencairan = **tidak menginap** (`menginap = False`) → **LOCKED**, auto-isi 30%, tidak bisa diubah
- Kalau pencairan = **menginap** (`menginap = True`) → toggle aktif:
  - Menginap → input nominal aktual hotel
  - Tidak menginap → auto 30% × plafon (kasus langka)

**PDF**: tampil sebagai "Biaya Penginapan" + nilai saja, **tanpa keterangan menginap/tidak/30%**

### Pencairan vs Realisasi di PDF
- **Pencairan menginap**: Hanya uang harian + uang representasi yang ada nilainya. Item 2,3,5,6,7 tampil tapi kosong.
- **Pencairan tidak menginap**: Uang harian + representasi + hotel (30%). Item 2,5,6,7 kosong.
- **Realisasi**: Semua item bisa terisi. Transport dari `sppd_trip_detail`, biaya lain dari `sppd_biaya_lain`.

### Uang Harian di PDF
- Item 1 "Uang Harian" = `(uang_harian_total + uang_makan_total + transport_lokal_total) / total_hari` per hari
- Item 4 "Uang Representasi" = terpisah (khusus jabatan tertentu)
- Keduanya bersama = `subtotal_uang_saku`

### Rincian Transport (Realisasi)
- UI: dynamic rows `[Kota Asal] [Kota Tujuan] [Jenis Transport] [Biaya]`
- Disimpan ke tabel `sppd_trip_detail`
- `tanggal_berangkat`/`tanggal_kembali` diambil dari visum (NOT NULL constraint)
- `total_transport` di tabel `sppd` = sum dari semua baris
- Pattern simpan: delete all lama → insert baru (replace strategy)

### Biaya Lain-lain (Realisasi)
- UI: dynamic rows `[Keterangan] [Jumlah]`
- Disimpan ke tabel `sppd_biaya_lain`
- Pattern simpan: delete all lama → insert baru (replace strategy)

### Surat Disposisi di Visum
- File fisik disimpan di **Google Drive sekper** (dikelola sendiri)
- DB simpan sebagai JSONB array di kolom `visum.disposisi`: `[{nomor, perihal, link}, ...]`
- Bisa multi-surat per visum — dikelola dari Tab 3 visum (tambah/edit/delete)
- Link tampil di detail visum sebagai tombol 🔗 yang langsung buka Drive
- Data disposisi dipakai sebagai pembuka **Surat Tugas PDF** (`disposisi[0]`): "Memperhatikan Surat Nomor {nomor} tentang {perihal}..."

### RKAP Over Budget
- `deduct_rkap` tetap boleh jalan walau sisa negatif (over budget diizinkan)
- `anggaran_sisa` bisa negatif — tampil `⚠️ -Rp xxx` di RKAP monitor
- Over budget tidak memblok input SPPD — hanya warning visual di UI
- Mapping manual anggaran cadangan dilakukan di Supabase oleh admin

### Dewas Anggota — Pemisahan RKAP
- Dua Anggota Dewas punya jabatan dan RKAP row masing-masing:
  - "ANGGOTA DEWAN PENGAWAS 1" → `struktur_rkap = "DEWAS_ANGGOTA_1"` → row RKAP `DEWAS_ANGGOTA_1`
  - "ANGGOTA DEWAN PENGAWAS 2" → `struktur_rkap = "DEWAS_ANGGOTA_2"` → row RKAP `DEWAS_ANGGOTA_2`
- Jabatan lama "ANGGOTA DEWAN PENGAWAS" (`struktur_rkap = "DEWAS_ANGGOTA"`) di-legacy fallback ke `DEWAS_ANGGOTA_1`
- Jabatan baru ditambah via Tab "Kelola Jabatan" di halaman Pegawai

### Import Data Historis (untuk go-live)
- File: `data/realisasi_sppd_2026.csv` — data Jan-Mar 2026 (rekap realisasi akhir per pegawai)
- Strategi: script Python sekali pakai di `setup/import_realisasi_2026.py`
- Mapping: groupby No. SPD → 1 visum; per baris → 1 sppd dengan status `completed`
- Breakdown komponen tidak ada di CSV → total saja yang diisi
- RKAP tidak di-deduct otomatis (perlu adjust manual di Supabase)

---

## Fungsi Database Utama (`utils/database.py`)

| Fungsi | Keterangan |
|---|---|
| `get_rule_sppd(jabatan_id, lokasi_id)` | Ambil tarif SPPD |
| `get_plafon_hotel(jabatan_id, lokasi_id)` | Ambil plafon hotel untuk hitung 30% |
| `get_pegawai_by_jabatan_nama(nama_jabatan)` | Ambil pegawai aktif by nama jabatan (untuk TTD) |
| `save_biaya_lain(sppd_id, items)` | Simpan biaya lain-lain (replace) |
| `get_biaya_lain(sppd_id)` | Ambil biaya lain-lain |
| `save_transport_detail(sppd_id, items, tgl_berangkat, tgl_kembali)` | Simpan rincian transport (replace) |
| `get_transport_detail(sppd_id)` | Ambil rincian transport |
| `deduct_rkap(rkap_id, amount)` | Kurangi saldo RKAP (dipanggil saat pencairan) |
| `rollback_rkap(rkap_id, amount)` | Kembalikan saldo RKAP (dipanggil saat cancel) |
| `update_rekap_spd(spd_id)` | Hitung ulang grand total SPD |

---

## Cara Run / Debug

```bash
# Jalankan app
streamlit run app.py

# Test PDF (dari folder utils/)
cd utils
python test_visum.py
python test_surat_tugas.py
python test_spd.py
python test_sppd_pencairan.py
python test_sppd_realisasi.py
python test_pernyataan_biaya.py

# Cek tabel database (dari folder check/)
cd check
python cek_tabel.py

# Cek koneksi DB
cd check
python test_connection.py
```

---

## Catatan Lain

- File `.env` ada di root folder (SUPABASE_URL, SUPABASE_KEY) — jangan di-commit
- Logo perusahaan: `assets/logo_ptmb.png`
- Ukuran kertas PDF: **F4 (Folio)** = 215×330mm (bukan A4)
- Font PDF: Helvetica (built-in ReportLab, tidak perlu install)
- `check/cek_tabel.py` error encoding emoji di Windows terminal — jalankan dengan `PYTHONIOENCODING=utf-8`
- Helper `draw_wrapped()` di `pdf_generator.py` — pakai ReportLab Paragraph untuk auto-wrap + justify
- `BULAN_ID` dict di `pdf_generator.py` — format bulan Indonesia (Januari, Februari, dst)
- `fmt_tgl()` → "5 Januari 2026", `fmt_tgl_short()` → "05-Jan-2026"
