# check/debug_rekap.py
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Tampilkan semua SPD dulu, biar bisa pilih
res_spd_all = db.table("spd").select("id, nomor_spd").order("created_at", desc=True).execute()
print("=== DAFTAR SPD ===")
for i, s in enumerate(res_spd_all.data):
    print(f"{i+1}. {s['nomor_spd']} | {s['id']}")

# ← GANTI ANGKA INI sesuai nomor urut di atas (1, 2, 3, dst)
PILIHAN = 3

res_spd = type('obj', (object,), {'data': [res_spd_all.data[PILIHAN-1]]})()
if not res_spd.data:
    print("Tidak ada data SPD!")
    exit()

SPD_ID = res_spd.data[0]["id"]
print(f"SPD: {res_spd.data[0]['nomor_spd']} | ID: {SPD_ID}\n")

res_divisi = db.table("divisi").select("id, parent_id, bidang").execute()
divisi_map = {d["id"]: d for d in res_divisi.data}

res = db.table("sppd")\
    .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(struktur_rkap), divisi_id)")\
    .eq("spd_id", SPD_ID)\
    .neq("status", "cancelled")\
    .execute()

for s in res.data:
    try:
        nama = s["pegawai"]["nama"]
        struktur = s["pegawai"]["jabatan"]["struktur_rkap"]
        div_id = s["pegawai"]["divisi_id"]
        div = divisi_map.get(div_id, {})
        bidang_raw = div.get("bidang") or divisi_map.get(div.get("parent_id"), {}).get("bidang")
        bidang = bidang_raw.title() if bidang_raw else None
        print(f"{nama} | struktur: {struktur} | bidang_raw: {bidang_raw} | bidang: {bidang}")
    except Exception as e:
        print(f"ERROR: {e} | data: {s}")