"""
Check all Jabatan in database
SPPD PDAM Balikpapan
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔍 CHECKING JABATAN")
print("=" * 100)
print()

# Get all jabatan
jabatan_response = supabase.table('jabatan').select('*').execute()

print(f"📊 SUMMARY:")
print(f"   Total jabatan: {len(jabatan_response.data)}")
print()

# Sort by level (descending) then name
jabatan_sorted = sorted(jabatan_response.data, key=lambda x: (-x['level'], x['nama']))

print("📋 FULL JABATAN LIST:")
print("=" * 100)
print(f"{'No':<4} {'Jabatan':<50} {'Rule':<20} {'Level':<7} {'Struktur RKAP':<25} {'Status':<10}")
print("-" * 100)

for i, jab in enumerate(jabatan_sorted, 1):
    print(f"{i:<4} {jab['nama']:<50} {jab['nama_rule']:<20} {jab['level']:<7} {jab['struktur_rkap']:<25} {jab['status']:<10}")

print()

# Group by level
print("=" * 100)
print("📊 JABATAN BY LEVEL:")
print("=" * 100)

levels = {
    5: "Dewan Pengawas",
    4: "Direksi", 
    3: "Manajer",
    2: "Supervisor",
    1: "Staff Pelaksana",
    0: "Calon Pegawai"
}

for level_num, level_name in sorted(levels.items(), reverse=True):
    jabs_in_level = [j for j in jabatan_sorted if j['level'] == level_num]
    
    if jabs_in_level:
        print(f"\n🏢 Level {level_num}: {level_name} ({len(jabs_in_level)} jabatan)")
        print("-" * 100)
        
        for jab in jabs_in_level:
            print(f"   • {jab['nama']:<50} → Rule: {jab['nama_rule']:<20} RKAP: {jab['struktur_rkap']}")

print()

# Group by struktur_rkap
print("=" * 100)
print("📊 JABATAN BY STRUKTUR RKAP:")
print("=" * 100)

rkap_groups = {}
for jab in jabatan_response.data:
    rkap = jab['struktur_rkap']
    if rkap not in rkap_groups:
        rkap_groups[rkap] = []
    rkap_groups[rkap].append(jab['nama'])

for rkap, jabatan_list in sorted(rkap_groups.items()):
    print(f"\n📦 {rkap} ({len(jabatan_list)} jabatan)")
    print("-" * 100)
    for jab_nama in sorted(jabatan_list):
        print(f"   • {jab_nama}")

print()
print("=" * 100)
print("✨ Done!")
print()