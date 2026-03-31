"""
Import Rule SPPD from CSV files
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

# ============================================
# Load CSV files
# ============================================

print("📂 Loading CSV files...")

try:
    df_dalam = pd.read_csv("data/rule_sppd_dalam_provinsi.csv")
    print(f"✅ Dalam Provinsi: {len(df_dalam)} rows")
except FileNotFoundError:
    print("❌ File not found: rule_sppd_dalam_provinsi.csv")
    exit()

try:
    df_luar = pd.read_csv("data/rule_sppd_luar_provinsi.csv")
    print(f"✅ Luar Provinsi: {len(df_luar)} rows")
except FileNotFoundError:
    print("❌ File not found: rule_sppd_luar_provinsi.csv")
    exit()

print()

# ============================================
# Get lokasi_sppd map
# ============================================

print("📊 Loading lokasi_sppd...")

lokasi_response = supabase.table('lokasi_sppd').select('*').execute()
lokasi_map = {row['nama']: row['id'] for row in lokasi_response.data}

print(f"✅ Loaded {len(lokasi_map)} lokasi")
for nama, id in lokasi_map.items():
    print(f"   - {nama}")
print()

# ============================================
# Prepare data
# ============================================

print("🔧 Preparing rule_sppd data...")
print()

rules_to_insert = []

# Process Dalam Provinsi (lokasi: Dalam Kaltim)
lokasi_dalam_id = None
for nama, id in lokasi_map.items():
    if 'Dalam' in nama and 'Kaltim' in nama:
        lokasi_dalam_id = id
        break

if lokasi_dalam_id:
    for idx, row in df_dalam.iterrows():
        jabatan_nama = row['Jabatan'].strip()
        
        rule_data = {
            'jabatan': jabatan_nama,
            'lokasi_id': lokasi_dalam_id,
            'uang_makan': int(row['uang_makan']),
            'transport_lokal': int(row['transport_lokal']),
            'uang_saku': int(row['uang_saku']),
            'uang_representasi': int(row['uang_rep']) if pd.notna(row['uang_rep']) and int(row['uang_rep']) > 0 else 0,
            'plafon_pesawat': int(row['plafon_pesawat']),
            'plafon_hotel': int(row['plafon_hotel']),
            'berlaku_dari': '2025-01-01',  # Adjust if needed
            'status': 'aktif'
        }
        
        rules_to_insert.append(rule_data)
        print(f"✅ {jabatan_nama:<40} → Dalam Kaltim")

print()

# Process Luar Provinsi (lokasi: Luar Kaltim)
lokasi_luar_id = None
for nama, id in lokasi_map.items():
    if 'Luar' in nama and 'Kaltim' in nama:
        lokasi_luar_id = id
        break

if lokasi_luar_id:
    for idx, row in df_luar.iterrows():
        jabatan_nama = row['Jabatan'].strip()
        
        rule_data = {
            'jabatan': jabatan_nama,
            'lokasi_id': lokasi_luar_id,
            'uang_makan': int(row['uang_makan']),
            'transport_lokal': int(row['transport_lokal']),
            'uang_saku': int(row['uang_saku']),
            'uang_representasi': int(row['uang_rep']) if pd.notna(row['uang_rep']) and int(row['uang_rep']) > 0 else 0,
            'plafon_pesawat': int(row['plafon_pesawat']),
            'plafon_hotel': int(row['plafon_hotel']),
            'berlaku_dari': '2025-01-01',  # Adjust if needed
            'status': 'aktif'
        }
        
        rules_to_insert.append(rule_data)
        print(f"✅ {jabatan_nama:<40} → Luar Kaltim")

print ()

# Process Luar Negeri (copy dari Luar Provinsi)
lokasi_ln_id = None
for nama, id in lokasi_map.items():
    if 'Luar Negeri' in nama or 'Negeri' in nama:
        lokasi_ln_id = id
        break

if lokasi_ln_id:
    for idx, row in df_luar.iterrows():
        jabatan_nama = row['Jabatan'].strip()
        
        rule_data = {
            'jabatan': jabatan_nama,
            'lokasi_id': lokasi_ln_id,
            'uang_makan': int(row['uang_makan']),
            'transport_lokal': int(row['transport_lokal']),
            'uang_saku': int(row['uang_saku']),
            'uang_representasi': int(row['uang_rep']) if pd.notna(row['uang_rep']) and int(row['uang_rep']) > 0 else 0,
            'plafon_pesawat': int(row['plafon_pesawat']),
            'plafon_hotel': int(row['plafon_hotel']),
            'berlaku_dari': '2025-01-01',
            'status': 'aktif'
        }
        
        rules_to_insert.append(rule_data)
        print(f"✅ {jabatan_nama:<40} → Luar Negeri (sementara = Luar Provinsi)")

print()
print(f"📋 Total rules to insert: {len(rules_to_insert)}")
print()

# ============================================
# Insert to database
# ============================================

confirm = input("🚀 Proceed with insertion? (yes/no): ")

if confirm.lower() == 'yes':
    print()
    print("🚀 Inserting rule_sppd...")
    print("=" * 80)
    
    success = 0
    errors = []
    
    for rule_data in rules_to_insert:
        try:
            supabase.table('rule_sppd').insert(rule_data).execute()
            success += 1
        except Exception as e:
            error_msg = str(e)
            if 'duplicate' not in error_msg.lower():
                errors.append(f"{rule_data['jabatan']} - {error_msg[:50]}")
    
    print()
    print("=" * 80)
    print("📊 IMPORT SUMMARY")
    print("=" * 80)
    print(f"✅ Success: {success} rules inserted")
    print(f"❌ Errors: {len(errors)}")
    print()
    
    if errors:
        print("🔍 Error details:")
        for err in errors[:10]:
            print(f"   - {err}")
        print()
    
    # Verify
    count_response = supabase.table('rule_sppd').select('id', count='exact').execute()
    total_rules = count_response.count
    
    print(f"✅ Total rule_sppd in database: {total_rules}")
    print()
    
    # Show sample
    print("📋 SAMPLE RULES (first 5):")
    print("=" * 80)
    sample = supabase.table('rule_sppd').select('*').limit(5).execute()
    
    for rule in sample.data:
        print(f"\n📌 {rule['jabatan']}")
        print(f"   Lokasi: {rule['lokasi_id']}")
        print(f"   Uang Makan: Rp {rule['uang_makan']:,}")
        print(f"   Transport Lokal: Rp {rule['transport_lokal']:,}")
        print(f"   Uang Saku: Rp {rule['uang_saku']:,}")
        print(f"   Uang Rep: Rp {rule['uang_representasi']:,}")
        print(f"   Plafon Pesawat: Rp {rule['plafon_pesawat']:,}")
        print(f"   Plafon Hotel: Rp {rule['plafon_hotel']:,}")
    
    print()
    print("🎉 Import completed!")
    
else:
    print()
    print("❌ Import cancelled.")

print()
print("✨ Script finished!")