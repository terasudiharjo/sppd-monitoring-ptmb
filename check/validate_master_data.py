"""
Validate Master Data - Check if all pegawai can create SPPD
SPPD PDAM Balikpapan
"""

import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔍 MASTER DATA VALIDATION")
print("=" * 100)
print()

# ============================================
# Load all data
# ============================================

print("📂 Loading data...")

pegawai = supabase.table('pegawai').select('*, divisi:divisi_id(nama, bidang), jabatan:jabatan_id(nama, nama_rule, struktur_rkap)').execute().data
jabatan = supabase.table('jabatan').select('*').execute().data
rule_sppd = supabase.table('rule_sppd').select('*, lokasi:lokasi_id(nama)').execute().data
rkap = supabase.table('rkap').select('*').execute().data
lokasi = supabase.table('lokasi_sppd').select('*').execute().data

print(f"✅ Loaded {len(pegawai)} pegawai")
print(f"✅ Loaded {len(jabatan)} jabatan")
print(f"✅ Loaded {len(rule_sppd)} rule_sppd")
print(f"✅ Loaded {len(rkap)} rkap")
print(f"✅ Loaded {len(lokasi)} lokasi")
print()

# ============================================
# Validation 1: Pegawai → Jabatan
# ============================================

print("=" * 100)
print("✅ VALIDATION 1: Pegawai → Jabatan Mapping")
print("=" * 100)

pegawai_no_jabatan = [p for p in pegawai if not p.get('jabatan')]

if pegawai_no_jabatan:
    print(f"❌ FAIL: {len(pegawai_no_jabatan)} pegawai without jabatan!")
    for p in pegawai_no_jabatan[:5]:
        print(f"   - {p['nip']} {p['nama']}")
else:
    print(f"✅ PASS: All {len(pegawai)} pegawai have valid jabatan!")

print()

# ============================================
# Validation 2: Jabatan → Rule SPPD
# ============================================

print("=" * 100)
print("✅ VALIDATION 2: Jabatan → Rule SPPD Mapping")
print("=" * 100)

# Get unique nama_rule from jabatan
unique_rules = set([j['nama_rule'] for j in jabatan])

# Get unique jabatan from rule_sppd
rules_in_db = set([r['jabatan'] for r in rule_sppd])

missing_rules = unique_rules - rules_in_db

if missing_rules:
    print(f"❌ FAIL: {len(missing_rules)} jabatan_rule missing in rule_sppd!")
    for rule in sorted(missing_rules):
        count = len([j for j in jabatan if j['nama_rule'] == rule])
        print(f"   - {rule} ({count} jabatan affected)")
else:
    print(f"✅ PASS: All {len(unique_rules)} jabatan_rule have SPPD rules!")

print()

# ============================================
# Validation 3: Pegawai → RKAP (Complex!)
# ============================================

print("=" * 100)
print("✅ VALIDATION 3: Pegawai → RKAP Mapping")
print("=" * 100)

# Current year & month for testing
current_year = datetime.now().year
current_month = datetime.now().month

pegawai_no_rkap = []

# Buat set kategori_jabatan yang ada di RKAP untuk bulan ini (lebih cepat!)
rkap_kategori_available = set([
    r['kategori_jabatan'] for r in rkap
    if r['tahun'] == current_year
    and r['bulan'] == current_month
])

for p in pegawai:
    if not p.get('jabatan'):
        continue

    jab = p['jabatan']
    struktur_rkap = jab['struktur_rkap']
    bidang = p.get('divisi', {}).get('bidang', 'Administrasi')

    # Tentukan kategori RKAP yang seharusnya dipakai pegawai ini
    if struktur_rkap in ['DEWAS_KETUA', 'DEWAS_ANGGOTA', 'DIRUT', 'DIRUM', 'DIRTEK', 'DIROPS']:
        # Dewas & Direksi → pakai struktur_rkap langsung
        rkap_kategori = struktur_rkap

    elif struktur_rkap == 'BANTUAN':
        rkap_kategori = 'bantuan_sppd'

    elif bidang == 'Administrasi':
        rkap_kategori = {
            'MANAJER': 'ADM_MANAJER',
            'SUPERVISOR': 'ADM_SUPERVISOR',
            'STAF_PELAKSANA': 'ADM_STAF_PELAKSANA',
            'ADM_SUPERVISOR': 'ADM_SUPERVISOR',
            'ADM_STAF_PELAKSANA': 'ADM_STAF_PELAKSANA',
        }.get(struktur_rkap, struktur_rkap)

    else:  # Teknik
        rkap_kategori = {
            'MANAJER': 'TEKNIK_MANAJER',
            'SUPERVISOR': 'TEKNIK_SUPERVISOR',
            'STAF_PELAKSANA': 'TEKNIK_STAF_PELAKSANA',
            'TEKNIK_SUPERVISOR': 'TEKNIK_SUPERVISOR',
            'TEKNIK_STAF_PELAKSANA': 'TEKNIK_STAF_PELAKSANA',
        }.get(struktur_rkap, struktur_rkap)

    # Cek apakah kategori ini ada di RKAP
    can_get_rkap = rkap_kategori in rkap_kategori_available

    if not can_get_rkap:
        pegawai_no_rkap.append({
            'nip': p['nip'],
            'nama': p['nama'],
            'jabatan': jab['nama'],
            'struktur_rkap': struktur_rkap,
            'rkap_kategori': rkap_kategori,  # ← tambah ini biar keliatan mapping-nya
            'bidang': bidang
        })

if pegawai_no_rkap:
    print(f"❌ FAIL: {len(pegawai_no_rkap)} pegawai CANNOT create SPPD (no RKAP)!")
    print()
    print(f"{'NIP':<10} {'Nama':<28} {'Jabatan':<25} {'RKAP Kategori':<25} {'Bidang'}")
    print("-" * 100)
    for p in pegawai_no_rkap[:20]:
        print(f"{p['nip']:<10} {p['nama'][:26]:<28} {p['jabatan'][:23]:<25} {p['rkap_kategori']:<25} {p['bidang']}")
    
    if len(pegawai_no_rkap) > 20:
        print(f"... and {len(pegawai_no_rkap) - 20} more")

print()

# ============================================
# Validation 4: RKAP Completeness (12 months)
# ============================================

print("=" * 100)
print("✅ VALIDATION 4: RKAP Completeness (12 bulan)")
print("=" * 100)

if not rkap:
    print(f"❌ FAIL: Tidak ada data RKAP sama sekali!")
    print()
else:

    # Get unique kategori_jabatan
    rkap_categories = set([r['kategori_jabatan'] for r in rkap if r.get('kategori_jabatan')])

    incomplete_rkap = []

    for kategori in rkap_categories:
        for lokasi_obj in lokasi:
          # Count months for this kategori + lokasi
          months_available = set([
                r['bulan'] for r in rkap
                if r.get('kategori_jabatan') == kategori
                and r['lokasi_id'] == lokasi_obj['id']
                and r['tahun'] == current_year
            ])
        
          missing_months = set(range(1, 13)) - months_available
        
        if missing_months:
               incomplete_rkap.append({
                 'kategori': kategori,
                 'lokasi': lokasi_obj['nama'],
                 'missing_months': sorted(missing_months)
               })

    if incomplete_rkap:
      print(f"⚠️  WARNING: {len(incomplete_rkap)} RKAP incomplete (missing months)!")
      print()
      for item in incomplete_rkap[:10]:
            months_str = ', '.join([str(m) for m in item['missing_months']])
            print(f"   - {item['kategori']} ({item['lokasi']}): Missing months {months_str}")
    
      if len(incomplete_rkap) > 10:
           print(f"   ... and {len(incomplete_rkap) - 10} more")
    else:
     print(f"✅ PASS: All RKAP have complete 12 months!")

print()

# ============================================
# Validation 5: RKAP Budget > 0
# ============================================

print("=" * 100)
print("✅ VALIDATION 5: RKAP Budget > 0")
print("=" * 100)

rkap_zero_budget = [r for r in rkap if r['anggaran_awal'] == 0]

if not rkap:
    print(f"❌ FAIL: Tidak ada data RKAP sama sekali!")
elif rkap_zero_budget:
    print(f"⚠️  WARNING: {len(rkap_zero_budget)} RKAP with zero budget!")
    for r in rkap_zero_budget[:10]:
        print(f"   - {r.get('kategori_jabatan', 'N/A')} ...")
else:
    print(f"✅ PASS: All {len(rkap)} RKAP have budget > 0!")

print()

# ============================================
# SUMMARY
# ============================================

print("=" * 100)
print("📊 VALIDATION SUMMARY")
print("=" * 100)

total_issues = len(pegawai_no_jabatan) + len(missing_rules) + len(pegawai_no_rkap) + len(incomplete_rkap) + len(rkap_zero_budget)

if total_issues == 0:
    print("🎉 ALL VALIDATIONS PASSED!")
    print("✅ Database is ready for production!")
    print("✅ All pegawai can create SPPD!")
else:
    print(f"⚠️  {total_issues} ISSUES FOUND!")
    print()
    print("📋 ACTION ITEMS:")
    
    if pegawai_no_jabatan:
        print(f"   1. Fix {len(pegawai_no_jabatan)} pegawai without jabatan")
    
    if missing_rules:
        print(f"   2. Add rule_sppd for {len(missing_rules)} missing jabatan_rule")
    
    if pegawai_no_rkap:
        print(f"   3. Add RKAP for {len(pegawai_no_rkap)} pegawai without budget")
    
    if incomplete_rkap:
        print(f"   4. Complete RKAP (add missing months)")
    
    if rkap_zero_budget:
        print(f"   5. Fix {len(rkap_zero_budget)} RKAP with zero budget")

print()
print("✨ Validation complete!")