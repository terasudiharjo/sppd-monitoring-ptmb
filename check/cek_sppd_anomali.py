"""
Script cek anomali SPPD:
1. SPPD dengan total_biaya = 0 (kemungkinan rule tidak ditemukan saat buat)
2. SPPD dengan total_hari tidak sesuai lama_hari di visum yang bersangkutan

Jalankan dari folder root:  python check/cek_sppd_anomali.py

Set FIX_TOTAL_HARI = True untuk auto-fix total_hari dari visum.lama_hari.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

FIX_TOTAL_HARI = False   # ganti True untuk auto-fix total_hari

def fmt_rp(n):
    return f"Rp {int(n or 0):,}".replace(",", ".")

print("=" * 65)
print("CEK ANOMALI SPPD")
print("=" * 65)

# Ambil semua SPPD + visum
res = db.table("sppd")\
    .select("id, nomor_sppd, pegawai_id, total_hari, subtotal_uang_saku, total_biaya, status, visum_id, visum(nomor_visum, lama_hari, tujuan), pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama))")\
    .neq("status", "cancelled")\
    .order("created_at")\
    .execute()

sppd_list = res.data or []
print(f"\nTotal SPPD aktif: {len(sppd_list)}\n")

# --- 1. SPPD nilai 0 ---
print("-" * 65)
print("SPPD DENGAN TOTAL BIAYA = 0 (kemungkinan rule tidak ditemukan):")
print("-" * 65)
nol_list = [s for s in sppd_list if (s.get("total_biaya") or 0) == 0]
if not nol_list:
    print("  (tidak ada)")
else:
    for s in nol_list:
        peg  = (s.get("pegawai") or {}).get("nama", "?")
        jab  = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
        visum = s.get("visum") or {}
        print(f"  SPPD id={s['id'][:8]}... | {peg} ({jab})")
        print(f"    Nomor SPD : {s.get('nomor_sppd', '-')}")
        print(f"    Visum     : {visum.get('nomor_visum', '-')} — {visum.get('tujuan', '-')}")
        print(f"    Status    : {s['status']}")
        print(f"    Saku=0, Total=0 → perlu isi manual di Supabase atau via 3_sppd.py")
        print()

# --- 2. SPPD total_hari beda dengan visum.lama_hari ---
print("-" * 65)
print("SPPD DENGAN total_hari ≠ visum.lama_hari:")
print("-" * 65)
beda_list = []
for s in sppd_list:
    visum = s.get("visum") or {}
    lama_visum = visum.get("lama_hari")
    total_hari = s.get("total_hari")
    if lama_visum and total_hari and int(lama_visum) != int(total_hari):
        beda_list.append(s)

if not beda_list:
    print("  (tidak ada)")
else:
    for s in beda_list:
        peg   = (s.get("pegawai") or {}).get("nama", "?")
        visum = s.get("visum") or {}
        print(f"  SPPD id={s['id'][:8]}... | {peg}")
        print(f"    Nomor SPD    : {s.get('nomor_sppd', '-')}")
        print(f"    Visum        : {visum.get('nomor_visum', '-')} — {visum.get('tujuan', '-')}")
        print(f"    total_hari SPPD : {s.get('total_hari')}  ← SALAH")
        print(f"    lama_hari Visum : {visum.get('lama_hari')}  ← BENAR")
        print(f"    Status       : {s['status']}")

        if FIX_TOTAL_HARI:
            db.table("sppd").update({
                "total_hari": int(visum["lama_hari"])
            }).eq("id", s["id"]).execute()
            print(f"    [FIX] total_hari diupdate ke {visum['lama_hari']}")
        else:
            print(f"    [i] Set FIX_TOTAL_HARI=True untuk auto-fix")
        print()

if beda_list and not FIX_TOTAL_HARI:
    print(f"\n  → Ada {len(beda_list)} SPPD yang total_hari-nya tidak sesuai visum.")
    print(f"  → Set FIX_TOTAL_HARI = True dan jalankan ulang untuk memperbaiki.")

print("\n" + "=" * 65)
print("Selesai.")
