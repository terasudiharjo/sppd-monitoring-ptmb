"""
Fix: Batalkan (hard reset) satu batch realokasi RKAP.

Cara kerja:
  - Baca batch dari tabel rkap_realokasi
  - Kembalikan anggaran_awal row 'dari' (tambah kembali jumlah yang dipindah)
  - Kurangi anggaran_awal row 'ke' (tarik kembali jumlah yang diterima)
  - Update anggaran_sisa = anggaran_awal - anggaran_terpakai di tiap row yang tersentuh
  - Hapus semua record batch ini dari rkap_realokasi

Jalankan dari root:  python check/fix_reset_realokasi_batch.py
Set DRY_RUN = False untuk benar-benar mengubah data.
Set BATCH_ID ke UUID batch yang ingin di-reset (lihat di tabel rkap_realokasi),
  ATAU set BATCH_NUMBER ke nomor urut batch (1 = batch pertama, 2 = kedua, dst).
Hanya satu dari keduanya yang perlu diisi.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client

DRY_RUN      = True   # <-- Set False untuk eksekusi nyata
TAHUN        = 2026   # Tahun RKAP yang bersangkutan

# Pilih salah satu cara identifikasi batch:
BATCH_ID     = ""     # UUID batch (prioritas utama jika diisi)
BATCH_NUMBER = 1      # Nomor urut batch (1 = paling awal), dipakai jika BATCH_ID kosong

# ─────────────────────────────────────────────────────────────────────────────
db  = get_client()
tag = "[DRY RUN]" if DRY_RUN else "[EKSEKUSI]"

print("=" * 70)
print(f"RESET REALOKASI RKAP  {tag}")
print("=" * 70)

# 1. Ambil semua batch tahun ini, urutkan by created_at
res_all = (
    db.table("rkap_realokasi")
    .select("*")
    .order("created_at")
    .execute()
)
all_records = res_all.data or []

if not all_records:
    print("Tidak ada data realokasi di database.")
    sys.exit(0)

# Susun urutan batch unik
seen = {}
batches_ordered = []
for rec in all_records:
    bid = rec["batch_id"]
    if bid not in seen:
        seen[bid] = True
        batches_ordered.append(bid)

print(f"\nDitemukan {len(batches_ordered)} batch realokasi:\n")
for i, bid in enumerate(batches_ordered):
    items = [r for r in all_records if r["batch_id"] == bid]
    tgl   = items[0]["tanggal"][:10]
    ket   = items[0].get("keterangan") or "-"
    total = sum(r["jumlah"] for r in items)
    print(f"  [{i+1}] {bid[:8]}...  |  {tgl}  |  {ket}  |  Total: Rp {total:,}".replace(",", "."))

# 2. Tentukan batch target
if BATCH_ID:
    target_bid = BATCH_ID
    if target_bid not in batches_ordered:
        print(f"\n[ERROR] BATCH_ID '{BATCH_ID}' tidak ditemukan.")
        sys.exit(1)
else:
    idx = BATCH_NUMBER - 1
    if idx < 0 or idx >= len(batches_ordered):
        print(f"\n[ERROR] BATCH_NUMBER {BATCH_NUMBER} tidak valid (ada {len(batches_ordered)} batch).")
        sys.exit(1)
    target_bid = batches_ordered[idx]

target_items = [r for r in all_records if r["batch_id"] == target_bid]
tgl_batch    = target_items[0]["tanggal"][:10]
ket_batch    = target_items[0].get("keterangan") or "-"
total_batch  = sum(r["jumlah"] for r in target_items)

print(f"\nBatch yang akan di-reset:")
print(f"  batch_id   : {target_bid}")
print(f"  tanggal    : {tgl_batch}")
print(f"  keterangan : {ket_batch}")
print(f"  total      : Rp {total_batch:,}".replace(",", "."))
print(f"  jumlah item: {len(target_items)}")

# 3. Kumpulkan semua rkap_id yang tersentuh dan delta perubahan
# Reversal: dari_rkap_id dapat +jumlah kembali, ke_rkap_id dapat -jumlah
deltas = {}  # rkap_id → delta anggaran_awal (positif = bertambah)
for item in target_items:
    deltas[item["dari_rkap_id"]] = deltas.get(item["dari_rkap_id"], 0) + item["jumlah"]
    deltas[item["ke_rkap_id"]]   = deltas.get(item["ke_rkap_id"],   0) - item["jumlah"]

# 4. Preview perubahan
print(f"\n{'─'*70}")
print("Perubahan yang akan dilakukan pada tabel rkap:\n")

rkap_rows = {}
for rkap_id in deltas:
    res_r = db.table("rkap").select("id, kategori_jabatan, lokasi_id, bulan, anggaran_awal, anggaran_terpakai, anggaran_sisa").eq("id", rkap_id).single().execute()
    if res_r.data:
        rkap_rows[rkap_id] = res_r.data

for rkap_id, delta in deltas.items():
    r = rkap_rows.get(rkap_id)
    if not r:
        print(f"  [WARN] rkap_id {rkap_id[:8]}... tidak ditemukan di DB, skip.")
        continue
    awal_lama  = r["anggaran_awal"] or 0
    terpakai   = r["anggaran_terpakai"] or 0
    awal_baru  = awal_lama + delta
    sisa_baru  = awal_baru - terpakai
    print(
        f"  {r['kategori_jabatan']} | Bln {r['bulan']:02d} | "
        f"anggaran_awal: Rp {awal_lama:,} → Rp {awal_baru:,}  "
        f"(delta {'+' if delta>=0 else ''}{delta:,})  |  sisa baru: Rp {sisa_baru:,}".replace(",", ".")
    )

print(f"\n  → Hapus {len(target_items)} record dari tabel rkap_realokasi (batch_id: {target_bid[:8]}...)")

# 5. Eksekusi (jika bukan dry run)
print(f"\n{'─'*70}")
if DRY_RUN:
    print("[DRY RUN] Tidak ada perubahan yang dilakukan. Set DRY_RUN = False untuk eksekusi.")
else:
    print("[EKSEKUSI] Memulai perubahan...")

    # Update anggaran_awal + anggaran_sisa per row
    for rkap_id, delta in deltas.items():
        r = rkap_rows.get(rkap_id)
        if not r:
            continue
        awal_baru = (r["anggaran_awal"] or 0) + delta
        sisa_baru = awal_baru - (r["anggaran_terpakai"] or 0)
        db.table("rkap").update({
            "anggaran_awal":  awal_baru,
            "anggaran_sisa":  sisa_baru,
        }).eq("id", rkap_id).execute()
        print(f"  ✓ Update rkap {rkap_id[:8]}... → anggaran_awal={awal_baru:,}, sisa={sisa_baru:,}".replace(",", "."))

    # Hapus record batch dari rkap_realokasi
    db.table("rkap_realokasi").delete().eq("batch_id", target_bid).execute()
    print(f"  ✓ Hapus {len(target_items)} record batch '{target_bid[:8]}...' dari rkap_realokasi")

    print("\n[SELESAI] Batch realokasi berhasil di-reset.")
    print("Jalankan cek_rkap_vs_sppd.py untuk verifikasi konsistensi data.")
