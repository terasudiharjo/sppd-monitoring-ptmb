# fix/fix_uang_rep.py
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

JABATAN_RULE_MAP = {
    "DIREKTUR UTAMA": "DIREKTUR UTAMA",
    "DIREKTUR BIDANG UMUM": "DIREKTUR BIDANG",
    "DIREKTUR OPERASIONAL": "DIREKTUR BIDANG",
    "DIREKTUR TEKNIK": "DIREKTUR BIDANG",
    "KETUA DEWAN PENGAWAS": "DIREKTUR UTAMA",
    "ANGGOTA DEWAN PENGAWAS": "DIREKTUR BIDANG",
}

# Ambil semua SPPD yang uang_representasi_total = 0
res = db.table("sppd")\
    .select("id, lokasi_id, total_hari, uang_representasi_total, pegawai!sppd_pegawai_id_fkey(nama, jabatan_id, jabatan(nama))")\
    .eq("uang_representasi_total", 0)\
    .execute()

print(f"SPPD dengan rep = 0: {len(res.data)}")

for s in res.data:
    nama_jab = s["pegawai"]["jabatan"]["nama"].upper().strip()
    nama_rule = JABATAN_RULE_MAP.get(nama_jab)
    
    if not nama_rule:
        # Bukan direksi/dewas, skip (memang 0)
        continue
    
    res_rule = db.table("rule_sppd")\
        .select("uang_representasi")\
        .eq("jabatan", nama_rule)\
        .eq("lokasi_id", s["lokasi_id"])\
        .single()\
        .execute()
    
    if not res_rule.data:
        print(f"  SKIP {s['pegawai']['nama']} — rule tidak ditemukan")
        continue
    
    uang_rep = (res_rule.data.get("uang_representasi") or 0) * s["total_hari"]
    
    if uang_rep == 0:
        continue
    
    # Update uang_rep + recalculate subtotal
    subtotal_lama = s.get("subtotal_uang_saku") or 0  # ini belum include rep
    subtotal_baru = subtotal_lama + uang_rep
    
    db.table("sppd").update({
        "uang_representasi_total": uang_rep,
        "subtotal_uang_saku": subtotal_baru,
        "total_biaya": subtotal_baru,
    }).eq("id", s["id"]).execute()
    
    print(f"  ✅ {s['pegawai']['nama']} | uang_rep: {uang_rep} | subtotal baru: {subtotal_baru}")

print("Done!")