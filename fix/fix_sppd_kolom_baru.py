# fix/fix_sppd_kolom_baru.py
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Ambil semua SPPD yang uang_makan_total masih 0
res = db.table("sppd")\
    .select("id, pegawai_id, lokasi_id, total_hari, uang_makan_total, pegawai!sppd_pegawai_id_fkey(jabatan_id)")\
    .eq("uang_makan_total", 0)\
    .execute()

print(f"SPPD yang perlu difix: {len(res.data)}")

JABATAN_RULE_MAP = {
    "DIREKTUR UTAMA": "DIREKTUR UTAMA",
    "DIREKTUR BIDANG UMUM": "DIREKTUR BIDANG",
    "DIREKTUR OPERASIONAL": "DIREKTUR BIDANG",
    "DIREKTUR TEKNIK": "DIREKTUR BIDANG",
    "MANAJER": "MANAJER",
    "STAF AHLI BIDANG HUKUM DAN ASET PERUSAHAAN": "MANAJER",
    "SUPERVISOR": "SUPERVISOR",
    "KETUA REGU": "SUPERVISOR",
    "STAF PELAKSANA": "STAF PELAKSANA",
    "TIM PENGADAAN": "STAF PELAKSANA",
    "BENDAHARA PEMBANTU": "STAF PELAKSANA",
    "CALON PEGAWAI": "STAF PELAKSANA",
    "KETUA DEWAN PENGAWAS": "DIREKTUR UTAMA",
    "ANGGOTA DEWAN PENGAWAS": "DIREKTUR BIDANG",
}

for s in res.data:
    jabatan_id = s["pegawai"]["jabatan_id"]
    lokasi_id = s["lokasi_id"]
    total_hari = s["total_hari"]

    # Ambil nama jabatan
    res_jab = db.table("jabatan").select("nama").eq("id", jabatan_id).single().execute()
    nama_jab = res_jab.data["nama"].upper().strip()
    nama_rule = JABATAN_RULE_MAP.get(nama_jab)

    if not nama_rule:
        print(f"  SKIP {s['id']} — jabatan {nama_jab} tidak ada di map")
        continue

    # Ambil rule
    res_rule = db.table("rule_sppd")\
        .select("*")\
        .eq("jabatan", nama_rule)\
        .eq("lokasi_id", lokasi_id)\
        .single()\
        .execute()

    if not res_rule.data:
        print(f"  SKIP {s['id']} — rule tidak ditemukan")
        continue

    rule = res_rule.data
    update_data = {
        "uang_makan_total": (rule.get("uang_makan") or 0) * total_hari,
        "transport_lokal_total": (rule.get("transport_lokal") or 0) * total_hari,
    }

    db.table("sppd").update(update_data).eq("id", s["id"]).execute()
    print(f"  ✅ Fix {s['id']} — makan: {update_data['uang_makan_total']} | transport: {update_data['transport_lokal_total']}")

print("Done!")