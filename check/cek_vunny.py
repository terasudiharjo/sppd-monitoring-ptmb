# check/cek_vunny.py
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

res = db.table("pegawai")\
    .select("nama, divisi_id, divisi(id, nama, parent_id, bidang), jabatan(nama, struktur_rkap)")\
    .ilike("nama", "%vunny%")\
    .execute()

for p in res.data:
    div = p.get("divisi", {})
    print(f"Nama     : {p['nama']}")
    print(f"Jabatan  : {p['jabatan']['nama']} | struktur_rkap: {p['jabatan']['struktur_rkap']}")
    print(f"Divisi   : {div.get('nama')} | bidang: {div.get('bidang')} | parent_id: {div.get('parent_id')}")
    
    if div.get("parent_id"):
        res_parent = db.table("divisi")\
            .select("nama, bidang")\
            .eq("id", div["parent_id"])\
            .single()\
            .execute()
        print(f"Parent   : {res_parent.data['nama']} | bidang: {res_parent.data['bidang']}")
    print("---")