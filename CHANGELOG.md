# CHANGELOG — Aplikasi Monitoring SPPD PTMB Balikpapan

Histori perubahan per sesi pengerjaan. Untuk dokumentasi operasional, lihat CLAUDE.md.

---

## Sesi 2026-06-24

**Perbaikan form hotel & PDF realisasi (`pages/3_sppd.py`, `utils/pdf_generator.py`):**
1. Tambah opsi keterangan `(30% sudah dibayar)` di dropdown hotel form realisasi.
2. Layout kolom form hotel diubah: urutan jadi **Uraian | Keterangan | Biaya | Del** (keterangan langsung di kanan uraian).
3. PDF Realisasi: keterangan hotel sekarang tampil **inline** setelah nama hotel di baris yang sama (pakai `stringWidth` untuk ukur posisi), bukan di baris terpisah di bawahnya.
4. PDF Realisasi: sub-baris hotel mendapat huruf **a., b., c.** jika ada lebih dari 1 item hotel. Huruf diindent dari angka "3" (posisi `no_x + 0.4cm`).
5. Form hotel realisasi dipisah menjadi **2 section**:
   - **Hari Tidak Menginap (30% Pagu)**: spinner hari + auto-calc nilai + dropdown keterangan status `(30% belum/sudah dibayar)` — nilai masuk RKAP.
   - **Hotel**: input manual nama hotel + biaya + keterangan. Dropdown keterangan diperluas: `(sudah dibayar)`, `(belum dibayar)`, `(pribadi sudah dibayar)`, `(pribadi belum dibayar)`.
6. Konvensi penyimpanan `sppd_hotel_detail`: item 30% disimpan dengan `uraian = ""` (penanda); item hotel biasa dengan `uraian != ""`. Keduanya masuk deduct RKAP via `total_hotel`.
7. PDF: semua sub-baris hotel (30% dan yang menginap) diberi huruf a/b/c jika lebih dari 1 baris. Item `uraian=""` tampil sebagai "30% pagu penginapan".
8. Save logic: `sppd.hari_tidak_menginap` di-update saat simpan realisasi.

---

## Sesi 2026-06-23 (lanjutan 3)

**Fitur: Rincian hotel per baris di realisasi (`pages/3_sppd.py`, `utils/database.py`, `utils/pdf_generator.py`):**
1. Tabel baru `sppd_hotel_detail` (id, sppd_id, urutan, uraian, biaya, keterangan TEXT NULL).
2. Kolom `sppd.hotel_keterangan` (ditambah sesi sebelumnya) di-drop — digantikan oleh keterangan per baris hotel.
3. Fungsi baru di `database.py`: `save_hotel_detail(sppd_id, items)` dan `get_hotel_detail(sppd_id)` — pola replace (delete all → insert baru), identik dengan `save_biaya_lain`/`save_transport_detail`.
4. UI form realisasi: section "Biaya Hotel" sekarang multi-baris (uraian | biaya | keterangan | hapus), dengan tombol "➕ Tambah Hotel". Keterangan selectbox: `— (tanpa keterangan)` | `(30% belum dibayar)` | `(sudah dibayar)` | `(belum dibayar)`.
5. Pre-fill otomatis: jika `menginap = False` dari pencairan dan belum ada detail → isi 1 baris dengan biaya 30%×plafon×hari_tidak_menginap dan keterangan `(30% belum dibayar)`.
6. PDF Tanda Terima Realisasi: "Biaya Penginapan [total]" sebagai header row, diikuti sub-baris per hotel (uraian + biaya) dengan keterangan dalam **warna merah** di baris bawahnya. Backward compat: jika tidak ada detail, tampil baris tunggal seperti sebelumnya.
7. Pernyataan Biaya Riil: tetap tampilkan total hotel saja (tidak ada sub-baris).

---

## Sesi 2026-06-23 (lanjutan 2)

**Fix: Angka Romawi di nama jabatan tampil benar (tidak di-lowercase) (`utils/database.py`, `utils/pdf_generator.py`, `utils/excel_generator.py`, `pages/2_visum.py`, `pages/3_sppd.py`, `pages/6_laporan.py`):**
1. Root cause: `.title()` bawaan Python mengubah "III" → "Iii", "IV" → "Iv", dst. Terjadi di semua titik formatting nama/jabatan.
2. Fix: tambah fungsi `smart_title(s)` — sama seperti `.title()` tapi setiap kata yang merupakan angka Romawi valid (I, II, III, IV, V, …) dikembalikan ke huruf kapital semua. Fungsi didefinisikan di `database.py` (import ke pages) dan lokal di `pdf_generator.py` + `excel_generator.py` (keduanya standalone, tidak import database).
3. Semua pemanggilan `.title()` pada field nama dan jabatan diganti ke `smart_title()` — 17 titik di 6 file.

**Fitur: Status pembayaran hotel di PDF realisasi (`pages/3_sppd.py`, `utils/pdf_generator.py`):**
4. Kolom baru `sppd.hotel_keterangan TEXT NULL` — nilai: `NULL` (kosong), `'sudah_dibayar'`, `'belum_dibayar'`.
5. Di form realisasi (setelah input biaya hotel), tambah radio horizontal 3 pilihan: "— (tanpa keterangan)" | "(sudah dibayar)" | "(belum dibayar)". Nilai disimpan ke DB saat "Simpan Realisasi".
6. PDF Tanda Terima Realisasi: label "Biaya Penginapan" berubah jadi "Biaya Penginapan (sudah dibayar)" / "Biaya Penginapan (belum dibayar)" sesuai pilihan — default tetap "Biaya Penginapan" kalau kosong.
7. PDF Pernyataan Biaya Riil: idem, field "Biaya Penginapan" baris 2 ikut menampilkan keterangan yang sama.
8. Re-download PDF (status realisasi/completed) otomatis memakai keterangan yang tersimpan di DB.

---

## Sesi 2026-06-23 (lanjutan)

**Fix data: koreksi anggaran_terpakai RKAP Mei 2026 akibat perubahan status Bobby Wira Sakti (`check/fix_bobby_rkap_terpakai.py`):**
1. Root cause: Bobby sebelumnya PKWT, lalu naik jadi staf tetap. Saat pencairan, deduct masuk ke `bantuan_sppd`. Setelah rkap_id SPPD-nya diupdate ke `TEKNIK_STAF_PELAKSANA`, delta realisasi Rp 540.000 terlanjur ke-deduct ke baris bantuan_sppd (salah row).
2. Dampak: `bantuan_sppd` (Dalam Kaltim, Mei) kelebihan Rp 540.000; `TEKNIK_STAF_PELAKSANA` (Dalam Kaltim, Mei) kekurangan Rp 540.000. Total grand total tetap benar.
3. Fix: geser Rp 540.000 dari `bantuan_sppd` ke `TEKNIK_STAF_PELAKSANA` via update langsung `anggaran_terpakai` + `anggaran_sisa` di tabel `rkap` (RKAP ID bantuan: `79d3882a`, TEKNIK_STAF: `70d1c167`).
4. Script diagnostik baru: `check/cek_mei_discrepancy.py` dan `check/cek_mei_rkap_table.py` untuk deteksi mismatch serupa di bulan lain.

---

## Sesi 2026-06-23

**Fitur: Breakdown anggaran per kelompok di RKAP Monitor (`pages/4_rkap_monitor.py`):**
1. Tambah tabel "Rincian per kelompok" di bawah KPI cards — 3 baris vertikal: Non-Bantuan | Bantuan SPPD | Bantuan SPPD LN, masing-masing menampilkan Anggaran / Terpakai / Sisa / % Terpakai.
2. Tambah tabel "Rekap per Kelompok" di Tab 1 (Tabel Summary) setelah tabel utama — 6 baris: Dewas, Direksi, Administrasi, Teknik, Bantuan SPPD, Bantuan SPPD LN, ditutup baris TOTAL. Administrasi dan Teknik dipisah row masing-masing (tidak digabung).
3. Semua perubahan murni display — tidak menyentuh logika kalkulasi, query database, atau alur deduct/rollback RKAP.

---

## Sesi 2026-06-19

**Fix: Bug spinner hari di Pool Distribusi RKAP (`pages/4_rkap_monitor.py`):**
1. Root cause: Streamlit hanya memakai parameter `value=` pada render pertama; setelah itu `st.session_state` mengontrol nilai widget. Akibatnya `rlk_pool_add_hari` bisa retain nilai tinggi (misal 7 hari) dari sesi sebelumnya saat destinasi baru dipilih, membuat `add_nilai_trip` lebih besar dari yang ditampilkan (tampil 15.8M/trip tapi tersimpan 21.3M, total 2 trip = 42.6M).
2. Fix: tracking `_pool_rate_key_prev` (berisi `.id` dari row RKAP yang dipakai sebagai rate basis). Setiap kali key berubah (destinasi atau radio "Tujuan/Sumber" berubah) → `st.session_state["rlk_pool_add_hari"]` di-set ulang ke `max(min_hari_lokasi, 4)`.

**Fitur: Tampilkan total rupiah sebelum tombol add di Pool Distribusi (`pages/4_rkap_monitor.py`):**
3. Kotak info biru `"Total: N trip × Rp X/trip = Rp Y"` ditampilkan setelah tiga kolom (hari/trip/info), sebelum tombol "➕ Tambah Tujuan". Memudahkan verifikasi angka sebelum klik.

**Fix: Nomor partial Pernyataan Biaya Riil (`pages/3_sppd.py`, `utils/pdf_generator.py`):**
4. `pb_data` sekarang menyertakan `nomor_surat_suffix` — dihitung dari `nomor_spd`: ambil bagian setelah `/` pertama, hilangkan trailing `-O`. Contoh: `"0034/1421002/10a-I/II/2026-O"` → suffix `"1421002/10a-I/II/2026"`.
5. `_draw_pernyataan()` di `pdf_generator.py` menangani tiga kasus: (a) `nomor_surat` terisi → tampil lengkap; (b) `nomor_surat` kosong + `nomor_surat_suffix` ada → tampil `Nomor : ___/1421002/10a-I/II/2026` (garis 2.5cm untuk nomor urut); (c) keduanya kosong → tampil garis panjang 6.5cm (backward compat).

**Fix: Urutan peserta di PDF Visum (`pages/2_visum.py`):**
6. Tambah field `struktur_rkap` ke dict `peserta_pdf` (diambil dari `jabatan.struktur_rkap`).
7. Sort diganti dari `-level, nip` ke fungsi `_tier()` context-aware:
   - **Ada Ketua Dewas:** tier 0=DEWAS_KETUA, 1=DEWAS_ANGGOTA*, 2=DIRUT, 3=DIRUM/DIRTEK/DIROPS, 99=lainnya
   - **Hanya Anggota Dewas:** tier 0=DIRUT, 1=DEWAS_ANGGOTA*, 2=DIRUM/DIRTEK/DIROPS, 99=lainnya
   - **Tanpa Dewas:** tier 0=DIRUT, 2=DIRUM/DIRTEK/DIROPS, 99=lainnya
   - Dalam satu tier: tiebreaker `-level` (seniority DB) lalu NIP ascending.

---

## Sesi 2026-06-18

**Fitur: Cancel SPPD Completed (`pages/3_sppd.py`):**
1. Expander konfirmasi "⚠️ Cancel SPPD Completed (koreksi data)" ditambahkan di bawah pesan status "✅ SPPD ini sudah COMPLETED" — tersedia tanpa memblokir view normal.
2. User harus centang checkbox konfirmasi sebelum tombol ❌ Cancel aktif.
3. Rollback RKAP menggunakan `total_biaya` (seluruh biaya yang tercatat di SPPD), bukan `subtotal_uang_saku`. Alasan: "Simpan Realisasi" menyesuaikan RKAP via delta `selisih = new_var - old_var`, sehingga `total_biaya` = uang saku + semua biaya riil yang sudah di-deduct ke RKAP.
4. Setelah cancel: `sppd.status → cancelled`, rekap SPD di-update, halaman di-rerun.

**Fitur: Edit Tanggal Visum propagate ke SPPD (`utils/database.py`, `pages/2_visum.py`):**
5. Fungsi baru `update_tanggal_visum(visum_id, tgl_visum, tgl_berangkat, tgl_kembali)` di `database.py`:
   - Update `visum` table (tanggal_visum, tanggal_berangkat, tanggal_kembali, lama_hari).
   - Fetch semua SPPD non-cancelled dalam visum; **skip** SPPD yang punya `tanggal_berangkat_custom` (mereka punya override tanggal sendiri).
   - Per SPPD: hitung `total_hari` baru, recalc uang saku dari rule (kecuali `tanpa_uang_saku=True` — update hari saja, uang saku tetap 0).
   - Untuk status `pencairan`/`realisasi`/`completed`: rollback `total_biaya` lama ke `rkap_id` lama, resolve `rkap_id` baru (bisa beda jika bulan berubah), deduct `total_biaya` baru.
   - Panggil `update_rekap_spd()` untuk setiap SPD yang terdampak.
   - Return dict: `{success, pesan, n_updated, n_skip, detail[]}`.
6. UI `pages/2_visum.py`: form "Edit Tanggal Visum" kini memanggil `update_tanggal_visum()` alih-alih update DB langsung. Menampilkan preview `{hari_lama} → {hari_baru} hari` sebelum submit. Pesan sukses mencantumkan berapa SPPD di-update dan berapa yang di-skip (karena tanggal custom).

**Perbaikan: Rate trip Realokasi RKAP dari Tujuan (`pages/4_rkap_monitor.py`):**
7. Rate/trip sekarang dihitung berdasarkan **tujuan** sebagai default (sebelumnya dari sumber).
8. Toggle "Basis rate trip: Tujuan | Sumber" tersedia per move — jika Sumber dipilih, min_hari juga mengikuti sumber. Caption breakdown tarif menampilkan "Rate dari: Tujuan/Sumber".
9. Label mode trip diubah dari "Trip (estimasi Staf Pelaksana)" → **"Trip (hitung per trip)"** untuk lebih generik.

**Fitur: Pool & Distribusi multi-sumber → multi-tujuan (`pages/4_rkap_monitor.py`):**
10. Expander baru "🔄 Pool & Distribusi (multi-sumber → multi-tujuan)" di Tab 4 Realokasi RKAP.
11. **Step 1 — Pilih Sumber**: `st.multiselect` untuk pilih 1+ baris RKAP sumber. Setiap opsi tampil dengan sisa efektif `Rp X`. Panel summary total pool terkumpul.
12. **Step 2 — Tentukan Tujuan**: list tujuan dinamis dari `st.session_state.rlk_pool_tujuan_list`. Setiap tujuan bisa dipilih mode Trip (dengan toggle basis rate Tujuan/Sumber + hari) atau Nominal. Tampil sisa saat ini per tujuan. Tombol "Pilih tujuan baru" + "Tambah Tujuan"; hapus per baris dengan ✕.
13. **Step 3 — Distribusi & Commit**: algoritma greedy drain-smallest-first — sumber diurutkan ascending by effective sisa, sumber terkecil dihabiskan dulu; isi tujuan satu per satu secara berurutan. Preview tabel matrix Dari×Ke dengan jumlah Rupiah per aliran + tabel sisa sumber setelah distribusi. Tombol commit mengumpulkan semua move ke `st.session_state.rlk_moves_list` (dengan `mode="nominal"`) untuk diproses bersama move reguler.
14. Session state `rlk_pool_tujuan_list` persists list tujuan antar interaksi UI.

---

## Sesi 2026-06-16

**Investigasi & Fix: RKAP Dewas Dalam Kaltim tidak ter-deduct (Visum 0055)**

**Root cause:** Bug di `update_tujuan_visum()` (`utils/database.py`) — ketika tujuan visum diubah (lokasi berubah) saat SPPD masih berstatus `draft`, fungsi ini hanya memperbarui `sppd.lokasi_id` dan uang saku, tapi **tidak memperbarui `sppd.rkap_id`**. Akibatnya `rkap_id` tetap mengarah ke lokasi lama. Saat pencairan, `3_sppd.py` hanya coba recover `rkap_id` kalau nilainya `NULL` — karena `rkap_id` sudah ada (meski salah), deduct langsung ke lokasi lama yang keliru.

**Kasus konkret:** Visum 0055 (Samarinda, Dalam Kaltim). Awalnya tujuan kemungkinan kota Luar Kaltim → SPPD dibuat dengan `rkap_id → Luar Kaltim`. Tujuan diubah ke "Samarinda" saat draft → `lokasi_id` dan uang saku diperbarui ke Dalam Kaltim, tapi `rkap_id` tetap Luar Kaltim. Pencairan → deduct ke Luar Kaltim (SALAH). Akibatnya: RKAP Dalam Kaltim untuk semua DEWAS (Ketua/1/2) `terpakai=0` sepanjang tahun.

**Fix kode (`utils/database.py`):**
1. Perbaikan `update_tujuan_visum()`: branch baru untuk SPPD `draft` — `rkap_id` sekarang juga diperbarui ke lokasi baru (tanpa rollback/deduct karena draft belum deduct RKAP). Jika baris RKAP baru tidak ditemukan → `rkap_id = NULL` (akan di-recover saat pencairan oleh kode existing di `3_sppd.py`).

**Script fix data (`check/fix_dewas_rkap_visum0055.py`):**
2. Script satu kali untuk koreksi 3 SPPD Dewas Visum 0055: rollback dari Luar Kaltim → deduct ke Dalam Kaltim Mei 2026 → update `sppd.rkap_id`. Total: Rp 26.110.000 dipindah (Rita Rp 6.225.000, Supriadi Rp 8.575.000, Agus Rp 11.310.000). **✅ Sudah dijalankan** — Script dikembalikan ke DRY_RUN=True.

**Script diagnostik (`check/cek_dewas_rkap.py`):**
3. Script baru untuk audit RKAP Dewas: cek `struktur_rkap` jabatan, cek baris RKAP kategori DEWAS*, dan trace ke mana setiap SPPD Dewas aktif ter-deduct. Berguna untuk deteksi mismatched `lokasi_id` vs `rkap_id`.

**UI minor: Dropdown Realokasi RKAP (`pages/4_rkap_monitor.py`):**
4. Urutan dropdown Sumber & Tujuan: **Kategori** (Dewas → Dirut → Direksi → Manajer → Supervisor → Staf) → **Lokasi** (Dalam → Luar → LN) → **Bulan** (Jan–Des).
5. Baris RKAP dengan efektif sisa negatif kini ditandai prefix `🔴` di dropdown (Streamlit tidak support warna teks di selectbox, pakai emoji sebagai penanda visual).

**Fitur: Mode Nominal Langsung untuk realokasi anggaran Bantuan (`pages/4_rkap_monitor.py`):**
6. Khusus sumber/tujuan kategori `bantuan_sppd` atau `bantuan_sppd_luar_negeri`: muncul radio button **"Trip (estimasi Staf Pelaksana)"** vs **"Nominal Langsung"**.
7. Mode Nominal: input satu field Rupiah langsung (step Rp 1 jt), validasi sisa cukup, tanpa perlu hitung trip. Berguna karena anggaran bantuan adalah angka bulat yang tidak bisa dibagi habis per trip.
8. Mode ini juga membuka realokasi `bantuan_sppd_luar_negeri` yang sebelumnya disabled (rate luar negeri = 0, tombol tidak bisa diklik).
9. Tampilan queue dan riwayat detail menyesuaikan: mode nominal tampil "nominal = Rp X", mode trip tetap tampil "N trip × M hr".

---

## Sesi 2026-05-29

**Script Fix Data:**
1. Dibuat `check/fix_bobby_rkap_visum0054.py` — pindah RKAP Bobby Wira Sakti (Visum 0054) dari bucket `bantuan_sppd` ke `TEKNIK_STAF_PELAKSANA`. SPPD dibuat saat jabatan Bobby masih STAF PKWT, padahal sudah naik jadi STAF PELAKSANA (bidang Teknik, tujuan Samarinda). Tarif uang saku tidak berubah (Rp 1.650.000), hanya `sppd.rkap_id` dan saldo RKAP yang dikoreksi. **✅ Sudah dijalankan** — RKAP Mei 2026 sudah benar.

---

## Sesi 2026-05-26

**Fitur: Tanpa Uang Saku per SPPD (`pages/3_sppd.py`, `utils/database.py`):**
1. Kolom baru `sppd.tanpa_uang_saku BOOLEAN DEFAULT FALSE` (jalankan SQL: `ALTER TABLE sppd ADD COLUMN IF NOT EXISTS tanpa_uang_saku BOOLEAN DEFAULT FALSE`).
2. Fungsi baru `update_tanpa_uang_saku(sppd_id, enabled)` di `database.py`:
   - `enabled=True` → zero out semua komponen uang saku (`uang_harian`, `uang_makan`, `transport_lokal`, `uang_representasi`, `subtotal_uang_saku` = 0); rollback RKAP jika status pencairan. `var_costs` (hotel + transport + biaya lain) tetap dipertahankan.
   - `enabled=False` → recalculate uang saku dari `rule_sppd`; deduct RKAP jika status pencairan.
3. UI: expander "✏️ Uang Saku" di Tab 2 SPPD, tersedia untuk semua jabatan s/d status `realisasi`. Checkbox "Tidak mendapat uang saku". Jika status pencairan, muncul warning RKAP sebelum tombol simpan. Expander auto-terbuka jika `tanpa_uang_saku=True`.

**Script Fix Data:**
4. Dibuat `check/fix_uncancel_visum.py` — un-cancel visum beserta semua SPPD-nya. Konfigurasi: `NOMOR_VISUM_PATTERN`, `TARGET_STATUS_SPPD` (`"draft"` disarankan — lanjutkan pencairan manual via UI), `RESTORE_VISUM_STATUS`. DRY_RUN=True dulu untuk preview.

---

## Sesi 2026-05-21

**Fitur: Edit Tujuan & Keperluan Visum (`pages/2_visum.py`, `utils/database.py`):**
1. Expander baru "✏️ Edit Tujuan & Keperluan" di Tab Detail & Edit Visum — tersedia untuk semua status kecuali `cancelled` (termasuk `completed` untuk koreksi data).
2. Jika hanya `keperluan` berubah → simple `UPDATE visum`, tidak ada kalkulasi.
3. Jika `tujuan` (kota) berubah → fungsi `update_tujuan_visum()` di `database.py`:
   - Update `visum.tujuan` + `visum.keperluan`
   - Loop semua SPPD non-cancelled visum tersebut
   - Update `sppd.lokasi_id` ke lokasi baru
   - Recalc uang saku dari `rule_sppd` lokasi baru (var costs hotel/transport/biaya lain dipertahankan)
   - Status pencairan/realisasi/completed: rollback RKAP lama (full `total_biaya`) → deduct RKAP bucket lokasi baru
   - Respect `tanggal_berangkat_custom` per SPPD untuk resolve bulan RKAP
   - Update rekap SPD di akhir
4. UI preview lokasi (`detect_lokasi`) langsung muncul saat kota diketik; warning otomatis muncul jika tujuan berubah.
5. Perubahan di-push ke GitHub — Streamlit Cloud auto-deploy.

**Script Fix Data:**
6. Dibuat `check/fix_uncomplete_sppd.py` — un-complete SPPD (`completed → realisasi`); murni ganti status, tanpa menyentuh RKAP. Set `NAMA_PEGAWAI_PATTERN` + `DRY_RUN=False`. **✅ Sudah dijalankan** untuk SPPD Yuniati yang tidak sengaja ter-complete.

---

## Sesi 2026-04-30 (lanjutan)

**Realokasi RKAP — Implementasi Awal (⚠️ pending review user):**
10. Schema Supabase dijalankan: tambah kolom `rkap.anggaran_pagu` (pagu asli, tidak berubah) + tabel baru `rkap_realokasi` (audit trail per batch).
11. Tambah konstanta `KATEGORI_TO_RULE_JABATAN` dan `MIN_HARI_LOKASI` di `utils/database.py`.
12. Tambah fungsi `get_all_rule_rates()`, `get_rkap_rows_tahun()`, `get_realokasi_history()`, `eksekusi_realokasi()` di `utils/database.py`.
13. `pages/4_rkap_monitor.py`: Tab 1 tambah kolom "Pagu Awal" + tanda `*` jika ada realokasi. Tab 4 baru "Realokasi RKAP": riwayat per batch, form multi-sumber dengan live preview rate & sisa, tujuan, preview tabel sebelum konfirmasi, eksekusi + clear cache.
14. Desain token: 1 trip = N hari (default 4, user-configurable). Rupiah = token × hari × rate/hari sumber. Sumber hard constraint sisa ≥ 0. Multi-sumber ke 1 tujuan per batch. Boleh cross-lokasi (rupiah sumber yang pindah, bukan hari).

---

## Sesi 2026-04-30

**Investigasi & Diagnostik RKAP:**
1. Dibuat `check/cek_rkap_vs_sppd.py` — script diagnostik perbandingan `rkap.anggaran_terpakai` vs sum `sppd.total_biaya` aktif per kategori/lokasi/bulan. Hasilkan laporan selisih, SPPD aktif & cancelled per baris RKAP.
2. Fix script: SPPD status DRAFT tidak dihitung dalam perbandingan (DRAFT belum deduct RKAP). Label aktif kini split: "X sudah deduct, Y masih draft".
3. Dibuat `check/investigasi_bantuan_maret.py` — investigasi targeted bantuan_sppd Maret 2026. Temuan: selisih Rp 2.977.000 bukan dari SPPD cancelled, tapi dari `total_biaya` INDRASTITI yang kehilangan komponen transport akibat bug `fix_sppd_realisasi.py`.

**Bug Fix (`utils/database.py`):**
4. `rollback_rkap`: hapus `max(terpakai - jumlah, 0)` — clamp ini menyebabkan inkonsistensi `terpakai + sisa ≠ anggaran_awal` jika rollback > terpakai (edge case). Sekarang rollback selalu konsisten.
5. `recalculate_sppd`: tambah `total_biaya` ke select query; ubah kalkulasi `total_biaya_baru` dari `subtotal_baru + total_hotel_existing` → `subtotal_baru + var_costs` di mana `var_costs = total_biaya_lama - uang_saku_lama`. Ini mempertahankan hotel + transport + biaya lain saat uang saku direcalculate.

**Bug Fix (`check/fix_sppd_realisasi.py`):**
6. Sama seperti no. 5 — `total_biaya_baru` sebelumnya hanya `subtotal_baru + total_hotel`, mengabaikan `total_transport` dan `sppd_biaya_lain`. Root cause: saat INDRASTITI dikoreksi dari tarif staf → spv, transport Rp 2.977.000 hilang dari `total_biaya` tapi sudah terdeduct di RKAP.

**Script Fix Data:**
7. Dibuat `check/fix_indrastiti_total_biaya.py` — koreksi one-time `total_biaya` INDRASTITI: dari Rp 6.400.000 → Rp 9.377.000 (tambah transport Rp 2.977.000). RKAP tidak perlu diubah (sudah benar). **✅ Script sudah dijalankan, data DB sudah benar.**
8. Dibuat `check/cek_sppd_bulan_rkap.py` — deteksi SPPD yang `rkap_id`-nya mengarah ke bulan RKAP berbeda dari bulan berangkat visum. Temuan: 2 SPPD Visum 0028 (FALIQ + Supriadi, perjalanan Bali 26-29 Maret) terdeduct ke RKAP April.
9. Dibuat `check/fix_visum0028_rkap_bulan.py` — realokasi deduct Visum 0028 dari RKAP April ke RKAP Maret (Luar Kaltim); total Rp 21.569.800 dipindah. **✅ Script sudah dijalankan, terverifikasi bersih dengan `cek_sppd_bulan_rkap.py`.**

**RKAP Monitor (`pages/4_rkap_monitor.py`):**
8. Tab "Detail per Bulan": tambah section detail SPPD di bawah tabel bulanan. Selectbox pilih bulan → query SPPD by `rkap_id` → tabel: Nama | Jabatan | Visum | Tujuan | Tgl Berangkat | Tgl Kembali | Status | Uang Saku | Hotel | Total. Default ke bulan pertama yang ada pemakaian.

**Keputusan & Temuan:**
- RKAP vs SPPD untuk DEWAS_ANGGOTA_2 April sudah seimbang (✅) — 28 juta = 2 trip Supriadi (Bali + Surabaya), bukan error
- Anggaran April DEWAS_ANGGOTA_1 & DEWAS_ANGGOTA_2 = Rp 0 (belum diinput), perlu diisi jika ada anggaran
- Kasus visum berangkat bulan X tapi deduct RKAP bulan Y (seperti visum 0028 Maret → April) adalah kondisi yang memang terjadi — perlu fitur realokasi RKAP dengan audit trail untuk pelaporan keuangan (pending)

---

## Sesi 2026-04-29

**Jabatan & RKAP (`utils/database.py`):**
1. Tambah `"STAF PKWT": "STAF PELAKSANA"` di `JABATAN_RULE_MAP` — untuk mendukung rename jabatan "Calon Pegawai" → "Staf PKWT" di tabel `jabatan` Supabase. Tarif SPPD & RKAP deduct tetap jalan. Entry `"CALON PEGAWAI"` dipertahankan sebagai fallback data lama.
2. Tambah `"STAF PKWT": 8` di `JABATAN_SORT_ORDER`.
3. Rename dilakukan manual di Supabase: kolom `nama` diubah, kolom `struktur_rkap = "BANTUAN"` tidak diubah → RKAP deduct ke kategori Bantuan tetap.

**PDF Visum (`utils/pdf_generator.py`):**
4. Fix bug Visum Lembaran II kolom kiri: "Tiba pada tanggal" sebelumnya pakai `tgl_kembali`, diperbaiki jadi `tgl_berangkat`.

**Edit Pegawai (`pages/5_pegawai.py`):**
5. Tambah field "NIP Baru" di form edit pegawai — hanya muncul kalau jabatan asal pegawai adalah `STAF PKWT` atau `CALON PEGAWAI`. NIP hanya disimpan ke DB kalau jabatan baru yang dipilih bukan PKWT (naik jabatan).

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