# CHANGELOG — Aplikasi Monitoring SPPD PTMB Balikpapan

Histori perubahan per sesi pengerjaan. Untuk dokumentasi operasional, lihat CLAUDE.md.

---

## Sesi 2026-03-30

**PDF:**
1. Semua 6 dokumen PDF selesai dan ter-integrasi di UI
2. `generate_pernyataan_biaya`: layout final — "Yang bertandatangan di bawah ini", waktu pelaksanaan auto-format bulan Indonesia, hanging indent poin 2&3, TTD rata tengah, nama Direktur Umum dari `get_pegawai_by_jabatan_nama("Direktur Umum")`
3. `generate_surat_tugas`: pembuka otomatis dari data disposisi visum (nomor + perihal)

**Navigasi & Auth:**
4. `app.py` → setelah login langsung `st.switch_page` ke `1_dashboard.py`
5. Urutan halaman: Dashboard → Visum → SPPD → RKAP Monitor → Pegawai

**Dashboard (`1_dashboard.py`):**
6. Bug status fixed: `"closed"` → `"completed"`, hapus `"dalam_perjalanan"`
7. Metric row 1: Total, Draft, Pencairan, Menunggu Realisasi, Selesai

**Visum (`2_visum.py`):**
8. Kolom disposisi di DB: `disposisi` (JSONB array) — bisa multi-surat per visum
9. Tab 3 visum: UI CRUD disposisi (tambah/edit/delete per baris)
10. Daftar visum: kolom "Disposisi" tampil jumlah surat
11. Detail visum: tampil semua surat disposisi + tombol 🔗 buka Drive
12. Surat Tugas PDF: pembuka dari `disposisi[0]`
13. Fix dua kota tujuan, form tidak reset saat error, tambah kota IKN/Bogor/Batam

**Database (`database.py`):**
14. `get_pegawai_by_jabatan_nama(nama_jabatan)` — ambil nama pejabat by jabatan
15. `resolve_kategori_rkap`: `DEWAS_ANGGOTA_1` & `DEWAS_ANGGOTA_2` pass-through langsung
16. `update_rekap_spd`: handle `DEWAS_ANGGOTA_1` dan `DEWAS_ANGGOTA_2` masuk ke `total_dewas`

**SPPD (`3_sppd.py`):**
17. Bug fix `biaya_lain` hardcoded 0 di Pernyataan Biaya
18. Perjalanan Dalam Kaltim: input transport disembunyikan, `total_transport = 0` otomatis
19. Bug fix `tr_items` NameError kalau Dalam Kaltim — sekarang `tr_items = []` sebagai default

**RKAP Monitor (`4_rkap_monitor.py`):**
20. Over budget: format sisa negatif tampil `⚠️ -Rp xxx`, status icon `🚨 OVER`
21. Banner merah otomatis kalau ada kategori over budget
22. Threshold: 🟢 <75% | 🟡 75–90% | 🔴 90–100% | 🚨 >100%

**Pegawai (`5_pegawai.py`):**
23. Tab baru "Kelola Jabatan" — tambah jabatan baru dan nonaktifkan dari UI

---

## Sesi 2026-03-31

**Git & Deployment:**
24. Repo GitHub: `github.com/terasudiharjo/sppd-monitoring-ptmb` (private)
25. App live di Streamlit Cloud: `https://sppd-ptmb.streamlit.app`
26. Credentials login dipindah dari hardcode ke `.env` (APP_USERNAME, APP_PASSWORD)
27. Streamlit Cloud pakai Secrets untuk semua 4 env vars

**Import Data Historis:**
28. `setup/import_realisasi_2026.py` — import 19 visum + 52 sppd Jan-Mar 2026
29. `setup/deduct_rkap_historis.py` — update rkap dari sppd historis
30. Kedua script sudah dijalankan ke DB production

**Bug Fix:**
31. `3_sppd.py`: fallback lookup rkap_id saat pencairan jika rkap_id null
32. `1_dashboard.py`: total anggaran exclude draft & cancelled

---

## Sesi 2026-04-01 (Sesi 1)

**Revisi PDF Visum:**
33. Format jabatan: `Man/Spv/Staf - [divisi]` — prefix "Divisi"/"Sub Divisi" di-strip via regex
34. Nama pegawai & jabatan: title case
35. Text wrap otomatis untuk Nomor 2 (jabatan panjang) dan Nomor 7 (nama peserta panjang)
36. Extra gap 0.15cm setelah baris yang wrap di Nomor 2
37. Nomor peserta di Nomor 7: format `1.  Nama` (tambah titik)

**Disposisi Visum — tambah field `dari`:**
38. Field `dari` (pengirim surat) ditambah ke struktur disposisi
39. UI Tab 3 CRUD disposisi: kolom baru "Dari" (5 kolom)
40. Form buat visum baru: input "Dari (Pengirim Surat)"
41. Pembuka Surat Tugas PDF: format baru → "surat dari [dari], Nomor [nomor], perihal [perihal]"
42. Helper `_build_pembuka()` — fleksibel, skip bagian yang kosong

---

## Sesi 2026-04-01 (Sesi 2)

**Revisi PDF Surat Tugas:**
43. Gap setelah tabel peserta diperbesar
44. "Tujuan Perjalanan Dinas" word-wrap dengan hanging indent
45. `fmt_waktu_surat_tugas()` — format tanggal cerdas dengan nama hari Indonesia
46. Nama, jabatan, divisi peserta: title case
47. Kolom Jabatan: format `Man/Spv/Staf - [nama]`
48. Kolom Divisi: Manajer→divisi sendiri, Spv/Staf→parent, Direksi/Dewas→"-"
49. Dirut dikecualikan dari daftar peserta Surat Tugas

**Revisi PDF SPD:**
50. Warna teks per kategori: Direksi=biru, Adm=hijau, Teknik=ungu, Dewas=oranye
51. `SPD_ROW_COLORS` dict
52. Peserta warna ikut kategorinya masing-masing
53. Peserta diurutkan: Dirut selalu pertama, lalu per kategori, lalu level tertinggi
54. Kolom jabatan peserta: text wrap otomatis

**Revisi PDF SPPD Tanda Terima:**
55. Garis horizontal setelah "Tanggal..."
56. TTD kanan: "Yang Menerima," sejajar "Mengetahui/Menyetujui :"
57. `jabatan_penerima` tampil di TTD kanan
58. `format_jabatan_sppd_penerima()` di `3_sppd.py`
59. Bug fix session state: nama tidak reset saat status sppd berubah

**Revisi PDF Pernyataan Biaya Riil:**
60. Nama penerima: title case
61. `dir_umum_nama` dari DB, fallback "Direktur Umum"
62. TTD kanan: `jabatan_penerima` tampil di bawah "Penerima SPPD,"

---

## Sesi 2026-04-02

**Bug Fix:**
63. `3_sppd.py`: fix `get_pegawai_by_jabatan_nama("Direktur Umum")` → `"DIREKTUR BIDANG UMUM"` (nama jabatan di DB uppercase)

**Script:**
64. `setup/clean_db.py` — script bersihkan data transaksi (DRY_RUN=True default):
    - Hapus: sppd_biaya_lain → sppd_trip_detail → sppd → spd → visum
    - Reset: rkap.anggaran_terpakai=0, anggaran_sisa=anggaran_awal

---

## Sesi 2026-04-06 — GO-LIVE ✅

**Testing & Script Go-Live:**
65. `setup/clean_db.py` — DRY RUN berhasil: 31 visum, 94 sppd, 31 spd siap dihapus
66. `setup/import_histori_2026.py` — script import untuk `histori sppd 2026.csv`:
    - Group by `Nomor Visum Lengkap` → 1 visum + 1 spd per group
    - Format tanggal `d/m/yyyy` (Indonesia)
    - `Biaya Lain-lain` > 0 → insert ke `sppd_biaya_lain`
67. `setup/import_pkwt_2026.py` — import 161 pegawai PKWT:
    - Jabatan: CALON PEGAWAI
    - `normalize_divisi()`: handle typo & variasi singkatan
    - 1 skip: NURWAHYU ISLAMIATI (NIK duplikat 2531)
68. RKAP bantuan: `resolve_kategori_rkap()` fix — BANTUAN → `bantuan_sppd` / `bantuan_sppd_luar_negeri`
69. RKAP Monitor: label "Bantuan SPPD" dan "Bantuan SPPD Luar Negeri"

**Eksekusi Go-Live:**
```
1. clean_db.py (DRY_RUN=False)              → transaksi lama dihapus, RKAP di-reset
2. import_histori_2026.py (DRY_RUN=False)   → 24 visum + 52 sppd Jan-Mar 2026 masuk DB
3. deduct_rkap_historis.py (DRY_RUN=False)  → 52 sppd di-deduct ke 21 RKAP row
4. import_pkwt_2026.py (DRY_RUN=False)      → 161 pegawai PKWT masuk DB
```
Semua script di-reset ke DRY_RUN=True setelah selesai.

---

## Sesi 2026-04-07 (Sesi 1)

**Bug Fix & Script:**
70. Root cause bug kategori kosong: `import_histori_2026.py` tidak memanggil `update_rekap_spd()`
71. `setup/fix_rekap_spd.py` — repair: call `update_rekap_spd()` untuk semua SPD existing
72. `setup/import_histori_2026.py` — 4 fix:
    - Tambah `update_rekap_spd(spd_id)` setelah insert sppd
    - `skiprows=2` dihapus
    - `tujuan`: baca dari kolom `Kota Tujuan` di CSV
    - `parse_tgl()`: tambah format `%d-%m-%y`
73. Import ulang: clean DB → import histori (24 visum, 52 sppd) → deduct RKAP

**RKAP Monitor:**
74. Tab Grafik: warna bar per lokasi — biru (Dalam), hijau (Luar), oranye (LN)
75. Tab Detail per Bulan: urutan dropdown ikut `KATEGORI_ORDER`

---

## Sesi 2026-04-07 (Sesi 2)

**Fitur Laporan (`pages/6_laporan.py`):**
76. Halaman baru `6_laporan.py` — 3 tab: Laporan Realisasi | Rekap Bulanan | Rekap Semester
77. `utils/excel_generator.py` (NEW) — generate Excel flat untuk laporan realisasi
78. `utils/pdf_generator.py` — tambah 3 fungsi: `generate_laporan_realisasi`, `generate_rekap_bulanan`, `generate_rekap_semester`
79. `utils/database.py` — tambah 2 fungsi: `get_sppd_realisasi_laporan`, `get_rekap_perjalanan`
80. Kolom laporan: No | Tgl Brgkt | Tgl Kmbli | Uraian | Kota | No. SPD | Nama | Jabatan | Voucher | SPPD | Tiket | Hotel | Biaya Lain | Total
81. Merge cell per visum (PDF): kolom No/Tgl/Uraian/Kota/SPD di-merge vertikal
82. Bug fix: FK ambiguous di Supabase — `pegawai!sppd_pegawai_id_fkey`

---

## Sesi 2026-04-07 (Sesi 3)

**Bug Fix:**
84. `2_visum.py`: `TypeError: unhashable type: 'dict'` — kolom `visum.peserta` JSONB bisa 3 format berbeda (UUID string, `{"id":"uuid"}`, full object). Fix: normalize semua format ke UUID string.
85. Visum detail: peserta UUID → nama pegawai via `get_nama_pegawai()`

**Fitur Visum Tanpa SPD:**
86. Kolom baru `visum.tanpa_spd BOOLEAN DEFAULT FALSE`
87. Form buat visum: toggle "Tanpa SPD (biaya tidak dari PTMB)"
88. Visum tanpa SPD: skip `auto_buat_semua_sppd()`, tidak ada SPPD/RKAP
89. Tab detail: badge kuning, tombol Download SPD disembunyikan
90. `cek_bisa_complete()`: visum tanpa SPD bisa langsung complete

**Refaktor Alur SPD:**
91. SPD dibuat terpisah (Tab 2 Kelola SPD) sebelum buat visum
92. Form buat visum: dropdown pilih SPD existing
93. Visum bisa di-reassign ke SPD berbeda via `assign_visum_ke_spd()`

---

## Sesi 2026-04-08

**Visum & SPD:**
94. `_generate_nomor_spd()` — sequential per bulan-tahun, format sesuai kode kantor
95. Tab "Kelola SPD": list semua SPD + form buat SPD baru
96. Dropdown SPD di form visum: filter hanya SPD bulan yang relevan
97. Detail visum Tab 4: tampil info SPD terkait + tombol reassign

**SPPD:**
98. Fallback RKAP: kalau `rkap_id` null saat pencairan, cari dari jabatan+bidang+lokasi+bulan
99. Kolom lokasi di rekap SPD Tab 3: dropdown filter lokasi

**Laporan:**
100. Tab Laporan Realisasi: filter bulan + tahun
101. Tab Rekap Bulanan: filter bulan + tahun + lokasi
102. Tab Rekap Semester: filter semester (Jan-Jun / Jul-Des) + tahun
103. Export PDF & Excel tersedia di semua tab laporan

---

## Sesi 2026-04-09

**PDF SPPD — Fix Tanggal:**
104. `pages/3_sppd.py` tambah `tanggal_spd` ke select query SPD
105. SPPD Pencairan & Realisasi: tanggal dokumen = `visum.tanggal_visum` (bukan `date.today()`)
106. Pernyataan Biaya `tanggal_spd`: dari `spd.tanggal_spd`
107. Pernyataan Biaya `tanggal_ttd`: tetap `date.today()`

**PDF Surat Tugas — Fix Tujuan:**
108. "Tujuan Perjalanan Dinas": ambil dari `disposisi[0].perihal`, fallback ke `visum.keperluan`

---

## Sesi 2026-04-15

**Fitur Partial Hotel:**
109. `pages/3_sppd.py`: form pencairan — tambah spinner "Hari tidak menginap hotel (dapat 30%)" (0 s/d max_malam)
110. Fix bug formula 30%: sebelumnya `plafon × 30%` flat, sekarang `hari_tidak_menginap × plafon × 30%` per malam
111. Konvensi malam: trip N hari = N-1 malam (`max_malam = total_hari - 1`)
112. Form realisasi: input biaya hotel aktual + spinner hari tidak menginap, `total_hotel = aktual + kompensasi`
113. Rekonstruksi PDF pencairan (download ulang): gunakan `hari_tidak_menginap` dari DB; backward compat record lama pakai `total_hotel` langsung
114. Supabase: `ALTER TABLE sppd ADD COLUMN hari_tidak_menginap INTEGER DEFAULT 0`

**Jabatan Tenaga Ahli:**
115. `utils/database.py`: tambah `TENAGA AHLI BIDANG MANAJEMEN` dan `TENAGA AHLI BIDANG KEHUMASAN` ke `JABATAN_RULE_MAP` (rate Manajer) dan `JABATAN_SORT_ORDER` (level 5)
116. Supabase: 2 jabatan baru dibuat via UI dengan `struktur_rkap = BANTUAN`

**Form Pegawai:**
117. `pages/5_pegawai.py`: opsi "— Tanpa Divisi —" ditambah di dropdown divisi (form Tambah & Edit), simpan `divisi_id = NULL`

---

## Sesi 2026-04-17

**Fix: Kota/Kabupaten Kaltim di Dropdown & Deteksi Lokasi:**
118. `utils/database.py`: tambah `"kutai timur"`, `"kutai barat"`, `"sendawar"`, `"ujoh bilang"` ke `KOTA_DALAM_KALTIM` — sebelumnya Kutai Barat & Kutai Timur tidak ter-detect sebagai Dalam Kaltim
119. `pages/2_visum.py`: tambah kota-kota di atas plus `"Tenggarong"`, `"Sangatta"`, `"Tanjung Redeb"`, `"Tanah Grogot"`, `"Penajam"` ke `KOTA_OPTIONS` dropdown form buat visum

**Fitur: Tombol "Hitung Ulang" Uang Saku SPPD:**
120. `utils/database.py`: tambah fungsi `recalculate_sppd(sppd_id)` — hitung ulang komponen uang saku dari jabatan + rule_sppd terkini
    - `draft`: update nilai saja
    - `pencairan`: update nilai + adjust RKAP (rollback lama → deduct baru)
    - Status lain: ditolak
121. `pages/3_sppd.py`: tombol **"🔄 Hitung Ulang"** di col_pdf1 untuk SPPD status `draft`
122. `pages/3_sppd.py`: tombol **"🔄 Hitung Ulang Uang Saku"** untuk SPPD status `pencairan`
123. `check/fix_sppd_realisasi.py` (NEW): script admin untuk koreksi manual SPPD `realisasi`/`completed` — preview `DRY_RUN=True`, eksekusi `DRY_RUN=False`

**Keputusan desain:**
- Perubahan jabatan pegawai TIDAK otomatis mengubah SPPD lama (past trips tetap pakai tarif saat dibuat)
- Recalculate hanya via tombol manual, bukan otomatis saat jabatan berubah
- `total_hotel`/`total_transport`/`biaya_lain` tidak ikut di-recalculate

---

*File ini adalah arsip histori perubahan. Untuk dokumentasi operasional aktif, lihat CLAUDE.md.*