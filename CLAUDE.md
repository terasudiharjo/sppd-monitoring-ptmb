# CLAUDE.md — Aplikasi Monitoring SPPD PTMB Balikpapan

## Gambaran Umum Project

Aplikasi web **Streamlit** untuk mengelola perjalanan dinas (SPPD) di Perumda Tirta Manuntung Balikpapan (PTMB).

- **Stack**: Python, Streamlit, Supabase (PostgreSQL cloud), ReportLab (PDF), Pandas, Plotly
- **Entry point**: `app.py` (login → langsung redirect ke Dashboard)
- **Login**: username: `sekper`, password: `ptmb2025`
- **Run app**: `streamlit run app.py` dari root folder
- **GitHub**: `github.com/terasudiharjo/sppd-monitoring-ptmb` (private)
- **Streamlit Cloud**: `https://sppd-ptmb.streamlit.app` (public, ada auth login)
- **Status**: PRODUCTION — go-live 6 April 2026 ✅

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
│   ├── 5_pegawai.py          # CRUD master data pegawai
│   └── 6_laporan.py          # Laporan Realisasi, Rekap Bulanan & Semester
├── utils/
│   ├── database.py           # Semua fungsi query Supabase
│   ├── pdf_generator.py      # Generate 9 jenis dokumen PDF
│   └── excel_generator.py    # Generate Excel laporan realisasi
├── data/                     # CSV data rule SPPD & RKAP
├── setup/                    # Script import data awal (semua DRY_RUN=True)
└── check/
    ├── cek_tabel.py                  # Lihat semua tabel Supabase
    ├── cek_sppd_anomali.py           # Cek SPPD nilai 0; FIX_TOTAL_HARI=True untuk auto-fix
    ├── cek_rkap_vs_sppd.py           # Bandingkan terpakai RKAP vs total SPPD aktif (deteksi selisih)
    ├── cek_sppd_bulan_rkap.py        # Deteksi SPPD yang bulan deduct RKAP ≠ bulan berangkat visum
    ├── fix_sppd_realisasi.py         # Fix manual uang saku SPPD realisasi/completed yang salah tarif
    ├── fix_indrastiti_total_biaya.py    # Fix total_biaya INDRASTITI (one-time, April 2026)
    ├── fix_visum0028_rkap_bulan.py      # Pindah deduct Visum 0028 dari RKAP Apr → Mar (one-time)
    ├── fix_uncancel_sppd_ganden.py      # Un-cancel SPPD Ganden Aditera Ismed Visum 0049 (one-time, Mei 2026)
    ├── fix_uncomplete_sppd.py           # Un-complete SPPD (completed → realisasi); set NAMA_PEGAWAI_PATTERN + DRY_RUN=False
    ├── fix_uncancel_visum.py            # Un-cancel visum + semua SPPD-nya; set NOMOR_VISUM_PATTERN + TARGET_STATUS_SPPD + DRY_RUN=False
    └── fix_reset_realokasi_batch.py     # Hard reset 1 batch realokasi RKAP; set BATCH_NUMBER (atau BATCH_ID) + DRY_RUN=False
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
| `pegawai` | Data pegawai aktif (345 PNS + 161 PKWT) |
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
tanpa_spd (BOOLEAN, default FALSE)
```
→ `dari` = pengirim surat (opsional, backward compatible).
→ `tanpa_spd = TRUE` → visum tidak punya SPD/SPPD (biaya tidak dari PTMB).

### Kolom penting `sppd`:
```
pegawai_id, visum_id, spd_id, rkap_id, lokasi_id,
total_hari, uang_harian_total, uang_makan_total, transport_lokal_total,
uang_representasi_total, subtotal_uang_saku,
total_transport, total_hotel, total_sewa_kendaraan,
biaya_jenazah, total_biaya,
menginap (BOOLEAN, default TRUE),
hari_tidak_menginap (INTEGER DEFAULT 0),
tanggal_berangkat_custom DATE NULL  ← override tanggal visum per orang
tanggal_kembali_custom DATE NULL    ← override tanggal visum per orang
status (draft → pencairan → realisasi → completed / cancelled)
nomor_voucher TEXT NULL
jabatan_dokumen TEXT NULL  ← override label jabatan di PDF (khusus tamu eksternal)
tanpa_uang_saku BOOLEAN DEFAULT FALSE  ← jika TRUE, uang saku = 0 (hanya tiket + hotel)
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

### Kolom penting `sppd_biaya_lain`:
```
id, sppd_id, urutan, keterangan, jumlah, created_at
```

---

## Dokumen PDF yang Dihasilkan (`utils/pdf_generator.py`)

| Fungsi | Dokumen | Status |
|---|---|---|
| `generate_surat_tugas(data)` | Surat Perintah Tugas (2 hal) | ✅ |
| `generate_spd(data)` | Surat Penyediaan Dana (1 hal) | ✅ |
| `generate_visum(data)` | Visum Lembaran I & II (2 hal) | ✅ |
| `generate_sppd_pencairan(data)` | Tanda Terima Pencairan (1 hal) | ✅ |
| `generate_sppd_realisasi(data)` | Tanda Terima Realisasi (1 hal) | ✅ |
| `generate_pernyataan_biaya(data)` | Pernyataan Pengeluaran Biaya Riil (1 hal) | ✅ |
| `generate_laporan_realisasi(data)` | Laporan Realisasi bulanan (F4 landscape) | ✅ |
| `generate_rekap_bulanan(data)` | Rekap Bulanan per jabatan (F4 portrait) | ✅ |
| `generate_rekap_semester(data)` | Rekap Semester 6 bulan (F4 landscape) | ✅ |

---

## Status Pending

### ⏳ Belum dikerjakan:
1. **Edit minor tampilan PDF laporan** — penyesuaian lebar kolom, font, spacing
2. **Optimasi performa** — `st.form` untuk form realisasi, `@st.cache_data` untuk query master data
3. **Input RKAP 2027** — belum ada UI, sementara pakai script import CSV manual
4. **Realokasi RKAP** — ✅ Fitur lengkap & diterima (sesi 2026-06-09). Lihat bagian "Keputusan Desain - Realokasi RKAP" untuk detail desain & implementasi.
5. **Nomor otomatis Pernyataan Biaya Riil** — saat ini dikosongkan (diisi manual setelah cetak). Rencana: tambah kolom `nomor_pernyataan_biaya TEXT NULL` di tabel `sppd`, auto-generate saat SPPD masuk status `realisasi`, format sequential per tahun mirip `generate_nomor_visum`. Di `3_sppd.py` kirim kolom tsb ke `nomor_surat` di `pb_data`, di PDF sudah otomatis handle: kalau kosong → tampil garis, kalau ada → tampil nomor.
6. **Driver outsourcing** — potensi jabatan baru di `rule_sppd` untuk driver non-PKWT/non-pegawai yang ikut dinas. Belum ada rule tarif. Perlu diskusi apakah dapat SPPD atau tidak.

### ✅ Selesai sesi 2026-06-15:
- **Realokasi RKAP multi-pasang** (`pages/4_rkap_monitor.py` + `utils/database.py`): satu batch sekarang bisa berisi banyak pasang (dari→ke) yang berbeda-beda tujuan. Fungsi baru `eksekusi_realokasi_multi(moves, keterangan, tanggal)` — validasi aggregate per sumber, hitung net delta per rkap_id, satu `batch_id` bersama.
- **UI Tab 4 revamp**: form tambah move baru pilih Sumber + Tujuan sekaligus (bukan multi-sumber → 1 tujuan); hari/trip bisa beda per move (default = MIN_HARI_LOKASI sumber); effective sisa di kedua selectbox sudah memperhitungkan moves yang sudah di-queue dalam batch yang sama.
- **Preview pivot sebelum/sesudah**: tabel Jan–Des untuk semua kategori+lokasi yang terdampak, dua tabel (Sebelum & Sesudah).
- **Perbandingan per Triwulan/Semester**: radio button TW/Semester → dua tabel perbandingan: (1) Anggaran Sebelum vs Sesudah per periode, (2) Sisa Sebelum vs Sesudah per periode. Ikon 🟢/🔴 untuk naik/turun, 🚨 untuk sisa minus.
- **Draft realokasi persisten** (`rkap_realokasi_draft` di Supabase): tabel baru `rkap_realokasi_draft(id, nama, tahun, keterangan, moves jsonb, created_at, updated_at)`. Fungsi baru `simpan_draft_realokasi`, `get_draft_list_realokasi`, `hapus_draft_realokasi`. UI: panel "📂 Draft Tersimpan" (muat/hapus), input nama draft, tombol "💾 Simpan Draft" → setelah finalisasi draft aktif otomatis dihapus.
- **Riwayat realokasi**: kolom "Ke" ditambah di detail expander; summary batch multi-destination tampil "X tujuan berbeda".
- **Fix Tab 3 "Detail per Bulan" — SPPD draft tidak mencerminkan terpakai** (`pages/4_rkap_monitor.py`): sebelumnya detail penggunaan menampilkan semua SPPD non-cancelled termasuk `draft`, sehingga tampak ada pemakaian di detail padahal kolom "Terpakai" di tabel tetap 0. Fix: SPPD `draft` sekarang tampil dengan label `⏳ DRAFT*` di kolom Status; grand total caption hanya menghitung pencairan/realisasi/completed (konsisten dengan `anggaran_terpakai`); catatan otomatis muncul jika ada draft: _"X SPPD masih DRAFT — belum deduct RKAP (estimasi: Rp ...)"_.

### ✅ Selesai sesi 2026-06-09:
- **Tambah kolom No. Visum & No. SPD di tabel dashboard**: `pages/1_dashboard.py` — tabel "SPPD Aktif" dan "Menunggu Realisasi" sekarang menampilkan dua kolom baru di posisi paling kiri: `No. Visum` (urutan visum, misal `0049`) dan `No. SPD` (urutan SPD, misal `034`). Data diambil via join `visum(nomor_visum)` dan `spd(nomor_spd)` pada query sppd. Helper `_urutan(nomor)` ekstrak bagian sebelum `/` pertama.
- **Perbaikan UI Tab 4 Realokasi RKAP** (`pages/4_rkap_monitor.py`):
  - **Ringkasan Saldo per Triwulan (pivot table)**: tabel kompak per baris Kategori+Lokasi, 4 kolom TW I–IV, sisa ditampilkan 🚨 (minus) / 🟢 (surplus). Expander per TW untuk lihat detail per bulan.
  - **Snapshot/historis view**: selectbox "Lihat kondisi anggaran:" dengan pilihan `Anggaran Awal | Setelah Perubahan 1 | ... | Kondisi Saat Ini`. Merekonstruksi `anggaran_awal` dari `anggaran_pagu` + audit trail `rkap_realokasi` tanpa mengubah data. Berguna untuk presentasi ke keuangan.
  - **Riwayat Realokasi**: tabel ringkas (Tanggal | Dari | Ke | Total Pindah | Keterangan) langsung visible, detail trip/rate di expander collapsed.
- **Script `check/fix_reset_realokasi_batch.py`**: hard reset satu batch realokasi — reversal `anggaran_awal` + `anggaran_sisa` di row yang tersentuh + hapus record dari `rkap_realokasi`. Set `BATCH_NUMBER` (atau `BATCH_ID`) + `DRY_RUN=False` untuk eksekusi.

### ✅ Selesai sesi 2026-06-03:
- **Tampilkan nomor SPD di selectbox pilih visum (Tab Detail & Edit)**: `pages/2_visum.py` — label selectbox sekarang menyertakan nomor SPD singkat, format `- SPD.034`. Data diambil dari `sppd.nomor_sppd` (query sekali, build dict `visum_id → nomor_spd`). Visum `tanpa_spd=True` tampil `- Tanpa SPD`. Visum tanpa SPPD (belum pencairan) tidak ada suffix.

### ✅ Selesai sesi 2026-06-02:
- **Fix teks PDF permintaan biaya untuk RKAP bantuan**: `pdf_generator.py` baris 1309 — kalau `is_bantuan=True`, teks sekarang berbunyi "sesuai permintaan biaya bantuan no. {nomor_spd}" (sebelumnya tidak ada kata "bantuan").
- **Fix kalkulasi nilai/trip realokasi RKAP**: `get_all_rule_rates()` di `utils/database.py` sekarang fetch semua komponen — `uang_saku`, `uang_makan`, `transport_lokal`, `uang_representasi`, `plafon_pesawat`, `plafon_hotel`. Formula nilai/trip di Tab Realokasi RKAP (`pages/4_rkap_monitor.py`) diubah menjadi: `(uang_saku + uang_makan + transport_lokal + uang_representasi) × hari + plafon_pesawat × 2 + plafon_hotel × (hari - 1)`. Sebelumnya hanya pakai `uang_saku` saja. UI kini tampilkan breakdown per komponen. Hanya Direktur Utama (Rp 250rb/hari) dan Direktur Bidang (Rp 150rb/hari) yang punya `uang_representasi > 0`.

### ✅ Selesai sesi 2026-05-29:
- **Script fix_bobby_rkap_visum0054.py**: Pindah RKAP Bobby Wira Sakti (Visum 0054) dari bucket `bantuan_sppd` → `TEKNIK_STAF_PELAKSANA` Mei 2026. SPPD dibuat waktu jabatan masih STAF PKWT, padahal Bobby sudah naik jadi STAF PELAKSANA (bidang Teknik). Tarif uang saku tidak berubah (Rp 1.650.000), hanya rkap_id dipindah. **✅ sudah dijalankan**.

### ✅ Selesai sesi 2026-05-26:
- **Tanpa Uang Saku per SPPD**: kolom baru `sppd.tanpa_uang_saku BOOLEAN DEFAULT FALSE`. Expander "✏️ Uang Saku" di Tab 2 SPPD, tersedia semua jabatan s/d status `realisasi`. Toggle ON → zero out semua komponen uang saku + rollback RKAP jika pencairan. Toggle OFF → recalc dari rule + deduct RKAP jika pencairan. `var_costs` (hotel + transport + biaya lain) tidak tersentuh. Fungsi baru `update_tanpa_uang_saku(sppd_id, enabled)` di `utils/database.py`.
- **Script fix_uncancel_visum.py**: Un-cancel visum beserta semua SPPD-nya. `TARGET_STATUS_SPPD = "draft"` disarankan (lanjutkan pencairan manual via UI). DRY_RUN=True dulu untuk preview.

### ✅ Selesai sesi 2026-05-21:
- **Script fix_uncomplete_sppd.py**: Un-complete SPPD (`completed → realisasi`). Murni ganti status, tanpa menyentuh RKAP. Set `NAMA_PEGAWAI_PATTERN` + `DRY_RUN=False` untuk eksekusi. **✅ sudah dijalankan** (fix SPPD Yuniati yang tidak sengaja ter-complete).
- **Edit Tujuan & Keperluan Visum**: Expander "✏️ Edit Tujuan & Keperluan" di Tab Detail & Edit Visum (tersedia untuk semua status kecuali cancelled). Jika hanya keperluan yang berubah → simple update visum. Jika tujuan berubah → semua SPPD non-cancelled diupdate `lokasi_id` + recalc uang saku dari rule baru + RKAP rollback lama & deduct ke bucket lokasi baru (termasuk SPPD status completed). Respects `tanggal_berangkat_custom` per SPPD untuk resolve bulan RKAP. Fungsi baru `update_tujuan_visum(visum_id, tujuan_baru, keperluan_baru)` di `utils/database.py`.

### ✅ Selesai sesi 2026-05-11:
- **Un-cancel SPPD Ganden Aditera Ismed**: script `check/fix_uncancel_sppd_ganden.py` — SPPD tidak sengaja di-cancel dari status `pencairan` (Visum 0049, SPD 34); script ubah status kembali ke `pencairan` + re-deduct RKAP + update rekap SPD; **✅ sudah dijalankan**.
- **Nomor Pernyataan Biaya dikosongkan (manual)**: `nomor_surat` di `pb_data` (`3_sppd.py`) diset `""`. PDF (`pdf_generator.py` `_draw_pernyataan`) — kalau nomor kosong, tampilkan garis bawah ~6.5cm untuk diisi tangan; kalau nomor terisi, tampilkan teks seperti biasa. Roadmap auto-nomor: lihat item 9 di "Belum dikerjakan".
- **Header SPPD Bantuan/PKWT/Tamu**: PDF header sekarang dinamis — `is_bantuan=True` → sisipkan kata "Bantuan" di header; `STAF PKWT` → format "Staf PKWT {divisi}"; Tamu → pakai `jabatan_dokumen` (tanpa suffix PTMB). Kolom baru `jabatan_dokumen TEXT NULL` di tabel `sppd` (jalankan SQL: `ALTER TABLE sppd ADD COLUMN IF NOT EXISTS jabatan_dokumen TEXT NULL`). UI: expander "✏️ Jabatan Dokumen (Tamu)" muncul untuk jabatan TAMU* di Tab 2 SPPD. Fungsi baru `update_jabatan_dokumen_sppd()` di `utils/database.py`.

### ✅ Selesai sesi 2026-05-06:
- **Custom tanggal per SPPD**: kolom `tanggal_berangkat_custom` + `tanggal_kembali_custom` (nullable) di tabel `sppd`. Expander "✏️ Edit Tanggal SPPD" di Tab 2 SPPD, bisa diedit s/d status realisasi. Recalc uang saku otomatis, RKAP di-rollback & deduct ulang (pindah rkap_id jika bulan berubah). Semua PDF (pencairan, realisasi, pernyataan biaya) pakai tanggal efektif per orang.
- Fungsi baru `update_tanggal_sppd_custom()` di `utils/database.py`

### ✅ Selesai sesi 2026-04-30:
- **Fix bug `rollback_rkap`**: hapus `max(..., 0)` yang menyebabkan inkonsistensi `terpakai + sisa ≠ anggaran_awal` jika rollback > terpakai
- **Fix bug `recalculate_sppd`**: tambah `total_biaya` ke select query; preservasi var costs (hotel + transport + biaya lain) saat recalculate uang saku — bukan hanya hotel
- **Fix bug `fix_sppd_realisasi.py`**: sama — var costs dipertahankan dengan formula `var_costs = total_biaya_lama - uang_saku_lama`
- **Tambah detail SPPD per bulan di RKAP Monitor Tab 3**: selectbox pilih bulan → tampil tabel siapa yang berangkat, kemana, pakai anggaran berapa (query by `rkap_id`)
- **Fix script `cek_rkap_vs_sppd.py`**: exclude SPPD status DRAFT dari perbandingan (DRAFT belum deduct RKAP, sebelumnya dihitung sebagai error)
- **Script diagnostik baru**: `check/investigasi_bantuan_maret.py` — investigasi targeted selisih RKAP vs SPPD
- **Script fix data**: `check/fix_indrastiti_total_biaya.py` — koreksi `total_biaya` INDRASTITI yang kehilangan transport setelah koreksi tarif staf → spv; **✅ sudah dijalankan** — `total_biaya` Rp 6.400.000 → Rp 9.377.000, data DB sudah benar
- **Script diagnostik baru**: `check/cek_sppd_bulan_rkap.py` — deteksi SPPD yang `rkap_id`-nya mengarah ke bulan RKAP berbeda dari bulan berangkat visum (jalankan dengan `PYTHONIOENCODING=utf-8`)
- **Script fix data**: `check/fix_visum0028_rkap_bulan.py` — pindah deduct Visum 0028 Bali (FALIQ + Supriadi) dari RKAP April ke RKAP Maret yang benar; total Rp 21.569.800 dipindah; **✅ sudah dijalankan** — terverifikasi bersih dengan `cek_sppd_bulan_rkap.py`
- **Realokasi RKAP** (⚠️ pending review user): Tab 4 baru di RKAP Monitor + fungsi database. Detail: lihat CHANGELOG sesi 2026-04-30 dan bagian "Keputusan Desain - Realokasi RKAP"

### ✅ Selesai sesi 2026-04-29:
- Rename jabatan `CALON PEGAWAI` → `STAF PKWT` (di Supabase + mapping kode)
- Fix tanggal Visum Lembaran II kolom kiri ("Tiba pada tanggal" pakai tgl berangkat)
- Edit NIP pegawai saat naik jabatan dari PKWT di halaman Edit Pegawai

---

## Keputusan Desain yang Sudah Disepakati

### Realokasi RKAP (✅ selesai sesi 2026-06-15)

**Konsep:** Pindahkan pagu anggaran (`anggaran_awal`) antar baris RKAP. `anggaran_terpakai` tidak berubah — hanya pagu yang digeser.

**Schema Supabase:**
- `rkap.anggaran_pagu` (INTEGER) — pagu asli tahun awal, tidak pernah berubah
- Tabel `rkap_realokasi`: `id, batch_id, tanggal, dari_rkap_id, ke_rkap_id, jumlah_token, hari_per_token, rate_per_hari, jumlah, keterangan, created_at`
- Tabel `rkap_realokasi_draft`: `id, nama, tahun, keterangan, moves (jsonb), created_at, updated_at` — untuk simpan draft antar sesi

**Mekanisme kalkulasi:**
- Input per move: pilih sumber RKAP, pilih tujuan RKAP, hari/trip (bisa beda per move, default = MIN_HARI_LOKASI sumber), jumlah trip
- Rate/hari = `uang_harian` (uang_saku + uang_makan + transport_lokal + uang_representasi) + pesawat PP + hotel per trip
- Rupiah pindah = trip × (uang_harian × hari + pesawat_pp + hotel × (hari-1))
- Satu batch = banyak pasang (dari→ke) berbeda; sumber divalidasi aggregate per rkap_id
- Effective sisa di selectbox = actual sisa + net delta dari moves yang sudah di-queue
- Minimum hari: Dalam Kaltim=1, Luar Kaltim=3, Luar Negeri=4

**Konstanta di `utils/database.py`:**
- `KATEGORI_TO_RULE_JABATAN` — map kategori_jabatan RKAP → jabatan rule_sppd
- `MIN_HARI_LOKASI` — minimum hari per lokasi_id

**Fungsi di `utils/database.py`:**
- `get_all_rule_rates()` — semua rate aktif dalam satu query
- `get_rkap_rows_tahun(tahun)` — semua row RKAP + anggaran_pagu
- `get_realokasi_history(tahun)` — audit trail per tahun
- `eksekusi_realokasi(ke_rkap_id, sumber_items, keterangan, tanggal)` — lama, multi-sumber → 1 tujuan (masih ada)
- `eksekusi_realokasi_multi(moves, keterangan, tanggal)` — baru, multi-pasang dari→ke dalam 1 batch
- `simpan_draft_realokasi(nama, tahun, keterangan, moves)` — upsert draft by nama+tahun
- `get_draft_list_realokasi(tahun)` — list draft tersimpan
- `hapus_draft_realokasi(draft_id)` — hapus draft

**UI di `pages/4_rkap_monitor.py` Tab 4 "Realokasi RKAP":**
- Panel "📂 Draft Tersimpan" — muat/hapus draft yang sudah disimpan
- Form tambah move: pilih Sumber + Tujuan, hari/trip, jumlah trip → "+ Tambah ke Daftar"
- Daftar moves ter-queue ditampilkan dengan tombol ✕ per baris
- Tombol "💾 Simpan Draft" (isi nama draft dulu) → tersimpan di Supabase, bisa dilanjutkan lain waktu
- Tombol "🔍 Preview & Finalisasi" → tampilkan: tabel moves, pivot Jan–Des sebelum/sesudah, perbandingan per TW/Semester (anggaran + sisa, ikon 🟢/🔴/🚨)
- Konfirmasi → `eksekusi_realokasi_multi()` → draft aktif auto-hapus → `load_rkap.clear()`
- Script reset batch: `check/fix_reset_realokasi_batch.py` (set BATCH_NUMBER + DRY_RUN=False)

**Alur deduct tidak berubah** — `deduct_rkap`/`rollback_rkap` hanya sentuh `anggaran_terpakai` + `anggaran_sisa` via delta, tidak pernah reset `anggaran_awal`.

---

### Penginapan (Hotel)

`plafon_hotel` di `rule_sppd` adalah **per malam**. Konvensi: trip N hari = N-1 malam (`max_malam = total_hari - 1`).
Kolom baru di `sppd`: `hari_tidak_menginap INTEGER DEFAULT 0`.

**Di Pencairan:**
- Toggle "Menginap Hotel" (default TRUE)
- Menginap (TRUE) → muncul spinner "Hari tidak menginap hotel (dapat 30%)" (0 s/d max_malam)
  - `hotel_30pct = hari_tidak_menginap × plafon × 30%` (bisa 0 jika semua menginap)
- Tidak menginap (FALSE) → `hari_tidak_menginap = max_malam` otomatis, `hotel_30pct = max_malam × plafon × 30%`
- DB simpan: `menginap`, `hari_tidak_menginap`, `total_hotel = hotel_30pct`, `total_biaya = uang_saku + hotel_30pct`

**Di Realisasi:**
- `menginap = False` → LOCKED, tampil `hari_tidak_menginap × plafon × 30%`
- `menginap = True`, toggle aktif:
  - Input "Biaya Hotel Aktual (Rp)" (untuk malam yang menginap)
  - Spinner "Hari tidak menginap hotel" (editable, pre-fill dari DB)
  - `total_hotel = biaya_hotel_aktual + hari_tidak_menginap × plafon × 30%`
  - Toggle ke FALSE → `total_hotel = max_malam × plafon × 30%` (LOCKED)

**PDF**: tampil sebagai "Biaya Penginapan" + nilai total saja, tanpa rincian per hari.

**Backward compat**: Record lama (`menginap=FALSE`, `hari_tidak_menginap=0`) → PDF pencairan pakai `total_hotel` dari DB langsung.

### Pencairan vs Realisasi di PDF
- **Pencairan menginap**: uang harian + representasi. Item 2,3,5,6,7 kosong.
- **Pencairan tidak menginap**: uang harian + representasi + hotel 30%. Item 2,5,6,7 kosong.
- **Realisasi**: semua item terisi. Transport dari `sppd_trip_detail`, biaya lain dari `sppd_biaya_lain`.

### Uang Harian di PDF
- Item 1 = `(uang_harian_total + uang_makan_total + transport_lokal_total) / total_hari` per hari
- Item 4 "Uang Representasi" = terpisah (khusus jabatan tertentu)

### Rincian Transport & Biaya Lain (Realisasi)
- Pattern simpan: delete all lama → insert baru (replace strategy)
- Transport → `sppd_trip_detail`, Biaya lain → `sppd_biaya_lain`
- `tanggal_berangkat`/`tanggal_kembali` di trip_detail wajib diisi — diambil dari visum

### Surat Disposisi di Visum
- File fisik di Google Drive sekper
- DB: JSONB array `[{nomor, dari, perihal, link}]` di `visum.disposisi`
- Surat Tugas PDF: pembuka dari `disposisi[0]` → "surat dari [dari], Nomor [nomor], perihal [perihal]"
- Fallback jika `dari` kosong: skip bagian "dari"

### RKAP Over Budget
- `deduct_rkap` tetap jalan walau sisa negatif
- `anggaran_sisa` bisa negatif → tampil `⚠️ -Rp xxx`
- Threshold: 🟢 <75% | 🟡 75-90% | 🔴 90-100% | 🚨 >100%
- Mapping cadangan dilakukan manual di Supabase

### Dewas Anggota — Pemisahan RKAP
- "ANGGOTA DEWAN PENGAWAS 1" → `DEWAS_ANGGOTA_1`
- "ANGGOTA DEWAN PENGAWAS 2" → `DEWAS_ANGGOTA_2`
- Legacy "ANGGOTA DEWAN PENGAWAS" → fallback ke `DEWAS_ANGGOTA_1`

### Visum Tanpa SPD
- `visum.tanpa_spd = TRUE` → biaya bukan dari PTMB
- Tidak ada SPPD record, tidak deduct RKAP
- Surat Tugas & Visum PDF tetap bisa di-download

### Tanggal di PDF SPPD
- SPPD Pencairan & Realisasi: pakai `visum.tanggal_visum`
- Pernyataan Biaya `tanggal_spd`: dari `spd.tanggal_spd`
- Pernyataan Biaya `tanggal_ttd`: `date.today()`

---

## Cara Run / Debug

```bash
# Jalankan app
streamlit run app.py

# Test PDF (dari folder utils/)
cd utils && python test_visum.py

# Cek tabel database (dari folder check/)
cd check && python cek_tabel.py
```

---

## Histori Perubahan
Detail perubahan per sesi ada di `CHANGELOG.md` di root folder.
Baca CHANGELOG.md hanya jika perlu trace keputusan desain lama.
Setiap selesai satu sesi agar dapat mengupdate CHANGELOG.md

## Referensi Cepat untuk Claude

> Gunakan index ini untuk langsung tahu fungsi/lokasi yang relevan — baca hanya file/bagian yang diperlukan, jangan baca full file.

### Index Fungsi per File

#### `utils/database.py` (1000+ baris — jangan baca full)

| Fungsi | Keterangan |
|---|---|
| `get_client()` | Return Supabase client |
| `get_all_pegawai()` | Semua pegawai aktif + jabatan + divisi |
| `get_pegawai_by_id(id)` | Detail 1 pegawai |
| `get_pegawai_by_jabatan_nama(nama)` | Pegawai by nama jabatan (untuk TTD PDF) |
| `get_all_divisi()` | Semua divisi aktif (dengan parent_id) |
| `get_all_jabatan()` | Semua jabatan aktif |
| `detect_lokasi(kota)` | Auto-detect lokasi dari nama kota |
| `get_rule_sppd(jabatan_id, lokasi_id)` | Tarif SPPD per jabatan per lokasi |
| `get_plafon_hotel(jabatan_id, lokasi_id)` | Plafon hotel untuk hitung 30% |
| `hitung_uang_saku(...)` | Hitung komponen uang saku |
| `resolve_kategori_rkap(struktur, bidang)` | Map struktur_rkap + bidang → kategori RKAP |
| `get_rkap_id(kategori, lokasi_id, bulan, tahun)` | Cari UUID row RKAP |
| `get_rkap_summary(tahun)` | Summary semua row RKAP untuk 1 tahun |
| `deduct_rkap(rkap_id, amount)` | Kurangi saldo RKAP (saat pencairan) |
| `rollback_rkap(rkap_id, amount)` | Kembalikan saldo RKAP (saat cancel) |
| `create_spd_baru(tanggal)` | Buat SPD baru |
| `get_spd_by_id(id)` | Detail 1 SPD |
| `get_spd_list_semua()` | Semua SPD (untuk dropdown) |
| `assign_visum_ke_spd(visum_id, spd_id)` | Assign/reassign visum ke SPD |
| `buat_sppd_untuk_pegawai(...)` | Buat 1 SPPD untuk 1 pegawai |
| `auto_buat_semua_sppd(visum_id, spd_id)` | Buat SPPD untuk semua peserta visum |
| `sync_sppd_peserta(visum_id, spd_id, peserta)` | Sync SPPD saat peserta berubah |
| `cancel_semua_sppd_visum(visum_id)` | Cancel semua SPPD + rollback RKAP |
| `update_rekap_spd(spd_id)` | Hitung ulang total per kategori di `spd` |
| `get_all_sppd()` | Semua SPPD (join visum + pegawai) |
| `recalculate_sppd(sppd_id)` | Hitung ulang uang saku dari rule terkini (draft/pencairan saja) |
| `update_tanggal_sppd_custom(sppd_id, tgl_b, tgl_k)` | Update tanggal custom per SPPD + recalc uang saku + adjust RKAP |
| `update_jabatan_dokumen_sppd(sppd_id, jabatan_dokumen)` | Simpan override label jabatan di PDF (untuk tamu eksternal) |
| `update_tanpa_uang_saku(sppd_id, enabled)` | Toggle tanpa uang saku: zero out / recalc uang saku + adjust RKAP jika pencairan |
| `update_tujuan_visum(visum_id, tujuan_baru, keperluan_baru)` | Update tujuan+keperluan visum; jika tujuan berubah → recalc lokasi_id+uang saku semua SPPD + adjust RKAP |
| `save_biaya_lain(sppd_id, items)` | Simpan biaya lain-lain (replace) |
| `get_biaya_lain(sppd_id)` | Ambil biaya lain-lain |
| `save_transport_detail(sppd_id, items, tgl_b, tgl_k)` | Simpan rincian leg perjalanan (replace) |
| `get_transport_detail(sppd_id)` | Ambil rincian leg perjalanan |
| `get_sppd_realisasi_laporan(bulan, tahun)` | Data realisasi grouped by visum |
| `get_rekap_perjalanan(bulan_list)` | Count perjalanan per jabatan per lokasi |

**Konstanta penting:**
- `JABATAN_RULE_MAP` — nama jabatan DB → nama rule tarif SPPD (termasuk `"STAF PKWT"` → `"STAF PELAKSANA"` sejak sesi 2026-04-29)
- `JABATAN_SORT_ORDER` — nama jabatan → angka urutan sorting
- `KOTA_DALAM_KALTIM` — set nama kota dalam Kaltim (termasuk Kutai Timur, Kutai Barat, Sendawar, Ujoh Bilang per sesi 2026-04-17)
- `LOKASI_DALAM` / `LOKASI_LUAR` / `LOKASI_LN` — UUID 3 lokasi (hardcoded)
- `LOKASI_BANTUAN_ID` — UUID bucket RKAP bantuan (= `LOKASI_DALAM`; semua SPPD bantuan Dalam+Luar Kaltim di-deduct ke sini)
- `KODE_STATIC = "1421002"`, `KODE_SEKPER = "10a-I"`, `KODE_VISUM = "J"`, `KODE_SPD = "O"`
- `KATEGORI_TO_RULE_JABATAN` — map kategori_jabatan RKAP → jabatan rule_sppd (untuk kalkulasi rate realokasi)
- `MIN_HARI_LOKASI` — minimum hari per lokasi_id (Dalam=1, Luar=3, LN=4)

**Fungsi realokasi & draft:**
| Fungsi | Keterangan |
|---|---|
| `get_all_rule_rates()` | Semua rate aktif (uang_harian, plafon_pesawat, plafon_hotel) |
| `get_rkap_rows_tahun(tahun)` | Semua row RKAP + anggaran_pagu untuk 1 tahun |
| `get_realokasi_history(tahun)` | Audit trail realokasi per tahun |
| `eksekusi_realokasi(ke_rkap_id, sumber_items, keterangan, tanggal)` | Lama: multi-sumber → 1 tujuan |
| `eksekusi_realokasi_multi(moves, keterangan, tanggal)` | Baru: multi-pasang dari→ke dalam 1 batch |
| `simpan_draft_realokasi(nama, tahun, keterangan, moves)` | Upsert draft by nama+tahun ke Supabase |
| `get_draft_list_realokasi(tahun)` | List draft tersimpan untuk tahun ini |
| `hapus_draft_realokasi(draft_id)` | Hapus draft by id |

---

#### `utils/pdf_generator.py` (2000+ baris — jangan baca full)

| Fungsi | Keterangan |
|---|---|
| `fmt_tgl(tgl)` | Date → "5 Januari 2026" |
| `fmt_tgl_short(tgl)` | Date → "05-Jan-2026" |
| `fmt_waktu_surat_tugas(tgl_b, tgl_k)` | Range tanggal cerdas dengan nama hari Indonesia |
| `fmt_rp(n)` / `fmt_rp2(n)` | Angka → "Rp 1.500.000" |
| `draw_kop(c, y, lebar)` | Gambar kop surat + logo PTMB |
| `draw_kop_box(c, ...)` | Kop dengan konten kiri/kanan |
| `draw_footer(c)` | Footer halaman |
| `draw_ttd(c, x, y, nama, jabatan)` | Blok tanda tangan |
| `draw_wrapped(c, x, y, lebar, teks)` | Teks auto-wrap justify |
| `generate_surat_tugas(data)` | PDF Surat Perintah Tugas |
| `generate_spd(data)` | PDF SPD (warna teks per kategori) |
| `generate_visum(data)` | PDF Visum Lembaran I & II |
| `generate_sppd_pencairan(data)` | PDF Tanda Terima Pencairan |
| `generate_sppd_realisasi(data)` | PDF Tanda Terima Realisasi |
| `generate_pernyataan_biaya(data)` | PDF Pernyataan Biaya Riil |
| `generate_laporan_realisasi(data)` | PDF Laporan Realisasi (F4 landscape) |
| `generate_rekap_bulanan(data)` | PDF Rekap Bulanan (F4 portrait) |
| `generate_rekap_semester(data)` | PDF Rekap Semester (F4 landscape) |

**Konstanta & layout:**
- `SPD_ROW_COLORS` — kategori → warna teks
- `BULAN_ID` — dict bulan Indonesia
- Layout: F4=215×330mm, margin 1.5cm, font Helvetica, `1cm=28.35pt`, Y dari bawah

---

#### `utils/excel_generator.py` (~150 baris)

| Fungsi | Keterangan |
|---|---|
| `generate_excel_realisasi(groups, bulan, tahun)` | Export realisasi bulanan ke BytesIO Excel |

---

#### `pages/2_visum.py` — Helper functions

| Fungsi | Keterangan |
|---|---|
| `generate_nomor_visum(tanggal)` | Nomor visum sequential |
| `fmt_tgl_indo(tgl_str)` | "YYYY-MM-DD" → "DD/MM/YYYY" |
| `format_jabatan_divisi(peg)` | Format "Man/Spv/Staf - [divisi]" untuk PDF |
| `_strip_div_prefix(nama)` | Strip prefix "Divisi"/"Sub Divisi" |
| `get_divisi_label_surat_tugas(peg)` | Label divisi untuk Surat Tugas |
| `_struktur_ke_kategori_spd(struktur)` | Map struktur_rkap → nomor kategori warna SPD |
| `_build_pembuka(disposisi)` | Build kalimat pembuka Surat Tugas |
| `get_nama_pegawai(peg_id)` | Lookup nama pegawai dari UUID |
| `cek_bisa_complete(visum_id, tanpa_spd)` | Cek apakah visum boleh di-complete |

---

#### `pages/3_sppd.py` — Helper functions

| Fungsi | Keterangan |
|---|---|
| `format_jabatan_sppd_penerima(peg)` | Format jabatan untuk TTD kanan PDF SPPD |
| `format_rupiah(n)` | Angka → "Rp 1.500.000" |
| `_strip_div_prefix(nama)` | Strip prefix divisi |

---

### Struktur Tab per Halaman

| Halaman | Tab (urutan) |
|---|---|
| `pages/2_visum.py` | 1-Daftar Visum, 2-Kelola SPD, 3-Buat Visum Baru, 4-Detail & Edit |
| `pages/3_sppd.py` | 1-Daftar SPPD, 2-Detail & Realisasi, 3-Rekap SPD |
| `pages/4_rkap_monitor.py` | 1-Summary, 2-Grafik, 3-Detail per Bulan |
| `pages/5_pegawai.py` | 1-Daftar Pegawai, 2-Tambah Pegawai, 3-Kelola Jabatan |
| `pages/6_laporan.py` | 1-Laporan Realisasi, 2-Rekap Bulanan, 3-Rekap Semester |

---

### Pola Kode Umum

**Query Supabase:**
```python
db = get_client()
res = db.table("table_name")\
    .select("col1, col2, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama))")\
    .eq("status", "aktif")\
    .execute()
return res.data
# PENTING: tabel sppd punya 2 FK ke pegawai → wajib pakai pegawai!sppd_pegawai_id_fkey
```

**Download PDF:**
```python
pdf_bytes = generate_xxx(data)
st.download_button("Download PDF", pdf_bytes, "nama.pdf", "application/pdf")
```

**Session state:** `st.session_state.authenticated` — True jika sudah login

---

### Alur Bisnis Utama

**Alur normal:**
1. **Kelola SPD** (Tab 2 Visum) → buat SPD baru
2. **Buat Visum** (Tab 3 Visum) → pilih SPD, isi tanggal/tujuan/peserta → `auto_buat_semua_sppd()`
3. **Download PDF** (Tab 4 Visum) → Surat Tugas + SPD + Visum
4. **Pencairan** (Tab 2 SPPD) → input hotel/transport → status `pencairan` → RKAP di-deduct
5. **Realisasi** (Tab 2 SPPD) → input biaya riil → status `realisasi` → `completed`
6. Cancel kapan saja → rollback RKAP otomatis

**Status SPPD:** `draft` → `pencairan` → `realisasi` → `completed` / `cancelled`

**Visum Tanpa SPD:** centang "Tanpa SPD" → skip SPPD/RKAP, tapi Surat Tugas & Visum PDF tetap bisa download.

---

## Catatan Teknis

- `.env`: `SUPABASE_URL`, `SUPABASE_KEY`, `APP_USERNAME`, `APP_PASSWORD`
- Logo: `assets/logo_ptmb.png`
- Kertas PDF: **F4 (Folio)** = 215×330mm
- Font PDF: Helvetica (built-in ReportLab)
- `cek_tabel.py`: jalankan dengan `PYTHONIOENCODING=utf-8` di Windows
- Schema lengkap semua tabel: lihat `schema_reference.sql`