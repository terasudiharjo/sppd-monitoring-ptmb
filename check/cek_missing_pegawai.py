"""
Check which pegawai failed to import
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔍 CHECKING MISSING PEGAWAI")
print("=" * 80)
print()

# Load CSV
df = pd.read_csv("data_pegawai.csv")
print(f"✅ CSV has {len(df)} rows")

# Get imported pegawai
imported = supabase.table('pegawai').select('nip').execute()
imported_nips = {row['nip'] for row in imported.data}
print(f"✅ Database has {len(imported_nips)} pegawai")
print()

# Get maps
divisi_response = supabase.table('divisi').select('id, nama').execute()
divisi_map = {row['nama']: row['id'] for row in divisi_response.data}

jabatan_response = supabase.table('jabatan').select('id, nama').execute()
jabatan_map = {row['nama']: row['id'] for row in jabatan_response.data}

# Find missing
print("🔍 Analyzing missing pegawai...")
print()

missing_divisi = {}
missing_jabatan = {}
missing_count = 0

for idx, row in df.iterrows():
    nip = str(row['nip']).strip()
    
    if nip not in imported_nips:
        missing_count += 1
        namabag = row['namabag'].strip()
        namajab = row['namajab'].strip()
        
        # Check why missing
        if namabag not in divisi_map:
            missing_divisi[namabag] = missing_divisi.get(namabag, 0) + 1
        
        if namajab not in jabatan_map:
            missing_jabatan[namajab] = missing_jabatan.get(namajab, 0) + 1

# Report
print("=" * 80)
print("📊 SUMMARY")
print("=" * 80)
print(f"Total CSV rows: {len(df)}")
print(f"Imported: {len(imported_nips)}")
print(f"Missing: {missing_count}")
print()

if missing_divisi:
    print("❌ MISSING DIVISI (divisi not found in database):")
    print("-" * 80)
    for divisi, count in sorted(missing_divisi.items(), key=lambda x: -x[1]):
        print(f"   {count:3d} pegawai → {divisi}")
    print()

if missing_jabatan:
    print("❌ MISSING JABATAN (jabatan not found in database):")
    print("-" * 80)
    for jabatan, count in sorted(missing_jabatan.items(), key=lambda x: -x[1]):
        print(f"   {count:3d} pegawai → {jabatan}")
    print()

# Show sample missing pegawai
print("📋 SAMPLE MISSING PEGAWAI (first 20):")
print("-" * 80)
print(f"{'NIP':<10} {'Nama':<30} {'Divisi':<40} {'Jabatan':<30}")
print("-" * 80)

count = 0
for idx, row in df.iterrows():
    nip = str(row['nip']).strip()
    if nip not in imported_nips:
        nama = row['nama'].strip()
        namabag = row['namabag'].strip()
        namajab = row['namajab'].strip()
        
        print(f"{nip:<10} {nama[:28]:<30} {namabag[:38]:<40} {namajab[:28]:<30}")
        count += 1
        
        if count >= 20:
            break

if missing_count > 20:
    print(f"... and {missing_count - 20} more")

print()
print("✨ Done!")