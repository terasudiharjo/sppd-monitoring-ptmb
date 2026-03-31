"""
Import 345 Pegawai - FINAL VERSION
SPPD PDAM Balikpapan
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔌 Connecting to Supabase...")
print()

# Load CSV
csv_path = "data/data_pegawai.csv"

try:
    df = pd.read_csv(csv_path)
    print(f"✅ CSV loaded! {len(df)} rows")
    print()
except FileNotFoundError:
    print(f"❌ File not found: {csv_path}")
    exit()

# Get maps
print("📊 Loading divisi & jabatan maps...")

divisi_response = supabase.table('divisi').select('id, nama').execute()
divisi_map = {row['nama']: row['id'] for row in divisi_response.data}

jabatan_response = supabase.table('jabatan').select('id, nama').execute()
jabatan_map = {row['nama']: row['id'] for row in jabatan_response.data}

print(f"✅ Loaded {len(divisi_map)} divisi")
print(f"✅ Loaded {len(jabatan_map)} jabatan")
print()

# Insert
print("🚀 Inserting pegawai...")
print("=" * 60)

success = 0
skip = 0
errors = []

for idx, row in df.iterrows():
    nip = str(row['nip']).strip()
    nama = row['nama'].strip()
    namabag = row['namabag'].strip()
    namajab = row['namajab'].strip()
    
    divisi_id = divisi_map.get(namabag)
    jabatan_id = jabatan_map.get(namajab)
    
    if not divisi_id:
        skip += 1
        errors.append(f"Row {idx+2}: Divisi '{namabag[:40]}' not found")
        continue
    
    if not jabatan_id:
        skip += 1
        errors.append(f"Row {idx+2}: Jabatan '{namajab[:40]}' not found")
        continue
    
    try:
        supabase.table('pegawai').insert({
            'nip': nip,
            'nama': nama,
            'divisi_id': divisi_id,
            'jabatan_id': jabatan_id,
            'status': 'aktif'
        }).execute()
        
        success += 1
        
        if success % 50 == 0:
            print(f"   ✅ {success} pegawai inserted...")
    
    except Exception as e:
        error_msg = str(e)
        if 'duplicate' in error_msg.lower():
            skip += 1
        else:
            errors.append(f"Row {idx+2}: {error_msg[:50]}")

# Summary
print()
print("=" * 60)
print("📊 IMPORT SUMMARY")
print("=" * 60)
print(f"✅ Success: {success} pegawai inserted")
print(f"⚠️  Skipped: {skip} records")
print(f"📋 Total processed: {len(df)} rows")
print()

if errors and len(errors) <= 20:
    print("🔍 Error details:")
    for err in errors[:20]:
        print(f"   - {err}")
    print()

print("🎉 Import completed!")
print()

# Verify
count_response = supabase.table('pegawai').select('id', count='exact').execute()
total_pegawai = count_response.count

print(f"✅ Total pegawai in database: {total_pegawai}")

if total_pegawai == 345:
    print("🎊 PERFECT! All 345 pegawai successfully imported!")
else:
    print(f"⚠️  Expected 345, got {total_pegawai}")

print()
print("✨ Script finished!")