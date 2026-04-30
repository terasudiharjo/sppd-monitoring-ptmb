"""
Diagnostik: cek SPPD yang bulan deduct RKAP-nya tidak cocok dengan bulan
berangkat visum.

Contoh masalah: visum berangkat Maret, tapi rkap_id mengarah ke row RKAP April.
Hal ini bisa terjadi jika:
- Visum dibuat di bulan sebelumnya dan peserta ditambah belakangan
- Bug saat auto-assign rkap_id (misalnya pakai tanggal_visum, bukan tanggal_berangkat)
- Edit manual yang tidak sinkron

Script ini HANYA membaca data, tidak mengubah apapun.
Output: daftar SPPD yang bulan rkap ≠ bulan berangkat, beserta detail.

Jalankan dari root:  python check/cek_sppd_bulan_rkap.py
"""

import sys, os
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client

# ── FILTER ──────────────────────────────────────────────
TAHUN = 2026
# Set ke None untuk cek semua bulan; atau int untuk filter 1 bulan tertentu
BULAN_FILTER = None
# ─────────────────────────────────────────────────────────

BULAN_LABEL = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agt", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des",
}
LOKASI_LABEL = {
    "6f7a80e0-1ca3-4e36-8d94-500bf8645efe": "Dalam Kaltim",
    "99c9f92f-972f-46d5-99d4-219b758d2cb7": "Luar Kaltim",
    "38663104-e5f5-473d-8227-640f025e595a": "Luar Negeri",
}

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

def parse_bulan(tgl_str):
    """Ambil bulan dari string 'YYYY-MM-DD'. Return None jika gagal."""
    try:
        return datetime.strptime(tgl_str[:10], "%Y-%m-%d").month
    except Exception:
        return None


db = get_client()

print("=" * 75)
print(f"CEK SPPD: bulan RKAP vs bulan berangkat visum — Tahun {TAHUN}", end="")
if BULAN_FILTER:
    print(f"  Bulan {BULAN_LABEL.get(BULAN_FILTER, BULAN_FILTER)}", end="")
print()
print("=" * 75)

# Ambil semua SPPD yang sudah deduct RKAP (pencairan/realisasi/completed)
# dan punya rkap_id
DEDUCT_STATUSES = {"pencairan", "realisasi", "completed"}

res = db.table("sppd")\
    .select(
        "id, status, total_biaya, rkap_id,"
        " pegawai!sppd_pegawai_id_fkey(nama),"
        " visum(nomor_visum, tujuan, keperluan, tanggal_berangkat),"
        " rkap(bulan, tahun, kategori_jabatan, lokasi_id)"
    )\
    .in_("status", list(DEDUCT_STATUSES))\
    .not_.is_("rkap_id", "null")\
    .execute()

all_sppd = res.data or []

if not all_sppd:
    print("Tidak ada SPPD aktif dengan rkap_id ditemukan.")
    sys.exit()

print(f"\nTotal SPPD aktif dengan rkap_id: {len(all_sppd)}\n")

# Filter per tahun RKAP dan bulan (jika ada filter)
mismatch_list = []
skip_count = 0

for s in all_sppd:
    rkap = s.get("rkap")
    visum = s.get("visum")

    if not rkap or not visum:
        skip_count += 1
        continue

    # Filter tahun dari RKAP
    if rkap.get("tahun") != TAHUN:
        continue

    tgl_berangkat = visum.get("tanggal_berangkat")
    if not tgl_berangkat:
        skip_count += 1
        continue

    bulan_berangkat = parse_bulan(tgl_berangkat)
    bulan_rkap = rkap.get("bulan")

    if bulan_berangkat is None or bulan_rkap is None:
        skip_count += 1
        continue

    # Filter bulan jika ada
    if BULAN_FILTER and bulan_rkap != BULAN_FILTER and bulan_berangkat != BULAN_FILTER:
        continue

    if bulan_rkap != bulan_berangkat:
        mismatch_list.append({
            "sppd_id": s["id"],
            "status": s["status"],
            "nama": (s.get("pegawai") or {}).get("nama", "?"),
            "total_biaya": s.get("total_biaya") or 0,
            "rkap_id": s["rkap_id"],
            "bulan_rkap": bulan_rkap,
            "bulan_berangkat": bulan_berangkat,
            "kategori": rkap.get("kategori_jabatan", "?"),
            "lokasi_id": rkap.get("lokasi_id", ""),
            "nomor_visum": visum.get("nomor_visum", "?"),
            "tujuan": visum.get("tujuan", "?"),
            "keperluan": visum.get("keperluan", "?"),
            "tanggal_berangkat": tgl_berangkat[:10],
        })

if skip_count:
    print(f"  (Dilewati {skip_count} SPPD karena data rkap/visum/tanggal kosong)\n")

if not mismatch_list:
    print("[OK] Tidak ditemukan SPPD dengan bulan RKAP != bulan berangkat.")
    print("=" * 75)
    sys.exit()

# Kelompokkan per (bulan_berangkat, bulan_rkap) untuk ringkasan
print(f"[!] Ditemukan {len(mismatch_list)} SPPD dengan bulan RKAP TIDAK COCOK:\n")

# Urutkan: bulan_berangkat dulu, lalu bulan_rkap
mismatch_list.sort(key=lambda x: (x["bulan_berangkat"], x["bulan_rkap"], x["nama"]))

# Tampilkan detail
current_group = None
for m in mismatch_list:
    group_key = (m["bulan_berangkat"], m["bulan_rkap"])
    if group_key != current_group:
        current_group = group_key
        bln_brgkt = BULAN_LABEL.get(m["bulan_berangkat"], str(m["bulan_berangkat"]))
        bln_rkap  = BULAN_LABEL.get(m["bulan_rkap"], str(m["bulan_rkap"]))
        print("-" * 75)
        print(f"  Berangkat : {bln_brgkt}  -->  deduct ke RKAP : {bln_rkap}  (SALAH BULAN)")
        print("-" * 75)

    lokasi_label = LOKASI_LABEL.get(m["lokasi_id"], m["lokasi_id"][:8] if m["lokasi_id"] else "?")
    bln_brgkt = BULAN_LABEL.get(m["bulan_berangkat"], str(m["bulan_berangkat"]))
    bln_rkap  = BULAN_LABEL.get(m["bulan_rkap"], str(m["bulan_rkap"]))

    print(f"  [{m['status'].upper():10}] {m['nama']}")
    print(f"    Visum     : {m['nomor_visum']} | {m['tujuan']}")
    print(f"    Berangkat : {m['tanggal_berangkat']} ({bln_brgkt})")
    print(f"    RKAP      : {m['kategori']} | {lokasi_label} | bulan {bln_rkap}")
    print(f"    RKAP ID   : {m['rkap_id']}")
    print(f"    Total biaya: {fmt_rp(m['total_biaya'])}")
    print()

# Ringkasan per visum (untuk tahu visum mana yang paling perlu difix)
print("=" * 75)
print("RINGKASAN per Visum:")
print("-" * 75)

visum_groups = defaultdict(list)
for m in mismatch_list:
    visum_groups[m["nomor_visum"]].append(m)

for nomor_visum in sorted(visum_groups.keys()):
    items = visum_groups[nomor_visum]
    m0 = items[0]
    bln_brgkt = BULAN_LABEL.get(m0["bulan_berangkat"], str(m0["bulan_berangkat"]))
    bln_rkap  = BULAN_LABEL.get(m0["bulan_rkap"], str(m0["bulan_rkap"]))
    total = sum(x["total_biaya"] for x in items)
    print(f"  Visum {nomor_visum}  |  {m0['tujuan']}  |  tgl {m0['tanggal_berangkat']}")
    print(f"    Deduct ke RKAP {bln_rkap} padahal seharusnya {bln_brgkt}")
    print(f"    {len(items)} peserta  --  total biaya: {fmt_rp(total)}")
    print(f"    Kategori RKAP: {m0['kategori']}")
    print()

print("=" * 75)
print("CATATAN:")
print("  Untuk fix: perlu realokasi RKAP - pindahkan deduct dari bulan salah ke")
print("  bulan yang benar. Ini akan dikerjakan di fitur Realokasi RKAP.")
print("  Simpan output ini sebagai referensi sebelum realokasi dibuat.")
print("=" * 75)
