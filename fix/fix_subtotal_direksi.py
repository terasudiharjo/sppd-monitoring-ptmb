# fix/fix_subtotal_direksi.py
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Ambil semua SPPD dan hitung ulang subtotal dari komponen
res = db.table("sppd")\
    .select("id, uang_harian_total, uang_makan_total, transport_lokal_total, uang_representasi_total, subtotal_uang_saku, pegawai!sppd_pegawai_id_fkey(nama)")\
    .execute()

print(f"Total SPPD: {len(res.data)}")

for s in res.data:
    uang_harian   = s.get("uang_harian_total") or 0
    uang_makan    = s.get("uang_makan_total") or 0
    transport     = s.get("transport_lokal_total") or 0
    uang_rep      = s.get("uang_representasi_total") or 0
    
    subtotal_benar = uang_harian + uang_makan + transport + uang_rep
    subtotal_lama  = s.get("subtotal_uang_saku") or 0
    
    if subtotal_benar != subtotal_lama:
        db.table("sppd").update({
            "subtotal_uang_saku": subtotal_benar,
            "total_biaya": subtotal_benar,
        }).eq("id", s["id"]).execute()
        nama = s["pegawai"]["nama"] if s.get("pegawai") else "-"
        print(f"  ✅ Fix {nama} | lama: {subtotal_lama} → baru: {subtotal_benar}")
    
print("Done!")