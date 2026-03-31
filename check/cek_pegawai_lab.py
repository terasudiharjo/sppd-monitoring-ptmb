import os
from supabase import create_client
from dotenv import load_dotenv

# 1. Setup koneksi
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

def cek_pegawai_lab():
    print("🧪 MENCARI PEGAWAI DI SUB.DIV LABORATORIUM")
    print("=" * 50)

    # 2. Cari ID Divisi Lab dulu (Ingat: Case Sensitive!)
    # Kita cari berdasarkan kode 'LAB' yang baru kamu buat
    divisi_req = supabase.table('divisi').select('id, nama').eq('kode', 'LAB').execute()
    
    # Cek return value dari divisi
    if not divisi_req.data:
        print("❌ Divisi dengan kode 'LAB' tidak ditemukan!")
        return

    lab_id = divisi_req.data[0]['id']
    lab_nama = divisi_req.data[0]['nama']

    print(f"📍 Ditemukan: {lab_nama} (ID: {lab_id})")
    print("-" * 50)

    # 3. Cari Pegawai yang divisi_id nya sama dengan ID Lab
    # Asumsi nama tabelnya adalah 'pegawai'
    pegawai_req = supabase.table('pegawai').select('nama, nip, jabatan(nama)').eq('divisi_id', lab_id).execute()

    if not pegawai_req.data:
        print("📭 Tidak ada pegawai yang terdaftar di divisi ini.")
    else:
        print(f"👥 Total Pegawai: {len(pegawai_req.data)}")
        print()
        for i, p in enumerate(pegawai_req.data, 1):
            # Mengambil nama jabatan dari relasi (join)
            jabatan = p.get('jabatan', {}).get('nama', 'N/A')
            print(f"{i}. {p['nama']} - [{p['nip']}]")
            print(f"   Jabatan: {jabatan}")
            print("-" * 30)

    print("\n✨ Done!")

if __name__ == "__main__":
    cek_pegawai_lab()