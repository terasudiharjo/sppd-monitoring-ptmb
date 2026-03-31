"""
Cek semua tabel dan kolom-kolomnya di database
SPPD PDAM Balikpapan
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔍 CEK STRUKTUR TABEL DATABASE")
print("=" * 70)
print()

# Daftar semua tabel
TABLES = [
    'lokasi_sppd',
    'divisi',
    'jabatan',
    'pegawai',
    'rule_sppd',
    'rkap',
    'visum',
    'sppd',
    'sppd_trip_detail',
    'sppd_sewa_kendaraan',
    'dokumen',
]

for table_name in TABLES:
    print(f"📁 TABEL: {table_name}")
    print("-" * 70)

    try:
        # Ambil 1 record untuk liat kolom
        response = supabase.table(table_name).select('*').limit(1).execute()

        # Hitung total records
        count_response = supabase.table(table_name).select('id', count='exact').execute()
        total = count_response.count

        if response.data:
            # Ada data, tampilkan kolom + sample value
            sample = response.data[0]
            print(f"{'Kolom':<30} {'Sample Value':<35} {'Tipe'}")
            print("-" * 70)
            for kolom, nilai in sample.items():
                # Tentukan tipe sederhana
                if nilai is None:
                    tipe = "NULL"
                elif isinstance(nilai, bool):
                    tipe = "BOOLEAN"
                elif isinstance(nilai, int):
                    tipe = "INTEGER"
                elif isinstance(nilai, float):
                    tipe = "FLOAT"
                elif isinstance(nilai, dict):
                    tipe = "JSONB"
                elif isinstance(nilai, list):
                    tipe = "ARRAY/JSONB"
                else:
                    tipe = "TEXT"

                # Truncate value panjang
                nilai_str = str(nilai) if nilai is not None else "NULL"
                if len(nilai_str) > 33:
                    nilai_str = nilai_str[:30] + "..."

                print(f"{kolom:<30} {nilai_str:<35} {tipe}")
        else:
            # Tabel kosong, coba detect kolom dari insert kosong
            print(f"   ⚠️  Tabel kosong ({total} records)")
            print(f"   Tidak bisa detect kolom dari data kosong.")
            print(f"   Cek di Supabase Dashboard → Table Editor → {table_name}")

        print(f"\n   📊 Total records: {total}")

    except Exception as e:
        print(f"   ❌ Error: {str(e)[:60]}")

    print()

print("=" * 70)
print("✨ Selesai!")