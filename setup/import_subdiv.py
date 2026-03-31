"""
Insert Sub-Divisi with PROPER HIERARCHY - FINAL VERSION
SPPD PDAM Balikpapan
"""

import os
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🔌 Connecting to Supabase...")
print()

# ============================================
# Load CSV
# ============================================

csv_path = "data/data_pegawai.csv"

try:
    df = pd.read_csv(csv_path)
    print(f"✅ CSV loaded! {len(df)} rows")
    print()
except FileNotFoundError:
    print(f"❌ File not found: {csv_path}")
    print("   Make sure the file is in the same folder as this script!")
    exit()

# ============================================
# Get parent divisi from database
# ============================================

print("📊 Loading parent divisi from database...")

parent_response = supabase.table('divisi').select('*').is_('parent_id', None).execute()
parent_map = {row['nama']: row for row in parent_response.data}

print(f"✅ Loaded {len(parent_map)} parent divisi:")
for name in sorted(parent_map.keys()):
    print(f"   - {name}")
print()

# ============================================
# Extract unique divisi from CSV
# ============================================

print("🔍 Extracting divisi names from CSV...")

all_divisi_names = set(df['namabag'].unique())

# Filter: only SUB.DIV variants (both formats!)
subdiv_names = {
    name for name in all_divisi_names 
    if 'SUB.DIV' in name or 'SUB.DIVISI' in name
}

print(f"✅ Found {len(subdiv_names)} unique subdiv to create")
print()

# ============================================
# Smart parent matching for subdiv
# ============================================

print("🧠 Matching subdiv to parent divisi...")
print()

subdiv_to_create = []
no_match = []

for subdiv_name in sorted(subdiv_names):
    parent_id = None
    parent_name = None
    bidang = 'Administrasi'  # Default
    
    # Smart matching based on subdiv name
    
    # DIVISI KEUANGAN
    if 'AKUNTANSI' in subdiv_name or 'KASIR' in subdiv_name or 'PERBENDAHARAAN' in subdiv_name:
        parent_name = 'DIVISI KEUANGAN'
        bidang = 'Administrasi'
    
    # DIVISI SISTEM INFORMASI MANAJEMEN
    elif 'DATA & APLIKASI' in subdiv_name or 'DATA DAN APLIKASI' in subdiv_name or 'JARINGAN' in subdiv_name or 'INFRASTRUKTUR' in subdiv_name:
        parent_name = 'DIVISI SISTEM INFORMASI MANAJEMEN'
        bidang = 'Teknik'
    
    # DIVISI LAYANAN PELANGGAN
    elif 'COSTUMER SERVICE' in subdiv_name or 'METER SEGEL' in subdiv_name or 'PEMBACA METER' in subdiv_name or 'PEMASARAN' in subdiv_name:
        parent_name = 'DIVISI LAYANAN PELANGGAN'
        bidang = 'Administrasi'
    
    # DIVISI DISTRIBUSI
    elif ('DISTRIBUSI WIL' in subdiv_name or 
          'PENANGGULANGAN KEHILANGAN AIR' in subdiv_name or  # ← FIXED!
          'PERALATAN DISTRIBUSI' in subdiv_name):  # ← FIXED!
        parent_name = 'DIVISI DISTRIBUSI'
        bidang = 'Teknik'
    
    # DIVISI PRODUKSI
    elif ('PENGOLAHAN AIR UNIT' in subdiv_name or 
          'SUMBER AIR' in subdiv_name or
          'PERALATAN PRODUKSI' in subdiv_name):  # ← FIXED!
        parent_name = 'DIVISI PRODUKSI'
        bidang = 'Teknik'
    
    # DIVISI PENGOLAHAN AIR LIMBAH
    elif 'IPAL' in subdiv_name or 'IPLT' in subdiv_name:
        parent_name = 'DIVISI PENGOLAHAN AIR LIMBAH'
        bidang = 'Teknik'
    
    # DIVISI PERENCANAAN DAN LITBANG
    elif ('PERENCANAAN TEKNIK' in subdiv_name or 'PEMETAAN ASSET' in subdiv_name or 
          'STANDARISASI' in subdiv_name or 'K3' in subdiv_name or
          'LABOLATORIUM' in subdiv_name): # ← FIXED!
        parent_name = 'DIVISI PERENCANAAN DAN LITBANG'
        bidang = 'Teknik'
    
    # DIVISI SATUAN PENGAWAS INTERNAL
    elif 'FUNGSIONAL AUDITOR' in subdiv_name:
        parent_name = 'DIVISI SATUAN PENGAWAS INTERNAL'
        bidang = 'Administrasi'
    
    # DIVISI SEKRETARIS PERUSAHAAN
    elif ('HUBUNGAN MASYARAKAT' in subdiv_name or 'KESEKRETARIATAN' in subdiv_name or 
          'HUKUM' in subdiv_name or 'PUSAT INFORMASI' in subdiv_name):
        parent_name = 'DIVISI SEKRETARIS PERUSAHAAN'
        bidang = 'Administrasi'
    
    # DIVISI SUMBER DAYA MANUSIA
    elif 'ADMINISTRASI & PENGEMBANGAN KEPEGAWAIAN' in subdiv_name or 'ADMINISTRASI DAN PENGEMBANGAN KEPEGAWAIAN' in subdiv_name:
        parent_name = 'DIVISI SUMBER DAYA MANUSIA'
        bidang = 'Administrasi'
    
    # DIVISI UMUM
    elif (('PENGADAAN' in subdiv_name and 'BARANG' in subdiv_name) or  # ← FIXED! (handle both & and DAN)
          ('PERLENGKAPAN' in subdiv_name and 'GUDANG' in subdiv_name)):  # ← FIXED!
        parent_name = 'DIVISI UMUM'
        bidang = 'Administrasi'
    
    # Get parent_id
    if parent_name and parent_name in parent_map:
        parent_id = parent_map[parent_name]['id']
        parent_bidang = parent_map[parent_name]['bidang']
        
        # Use parent's bidang
        bidang = parent_bidang
        
        # Generate kode (clean & short)
        kode = (subdiv_name
                .replace('SUB.DIV. ', '')
                .replace('SUB.DIVISI. ', '')
                .replace('SUB.DIVISI.', '')
                .replace(' ', '_')
                .replace('&', 'DAN')
                [:20])
        
        subdiv_to_create.append({
            'kode': kode,
            'nama': subdiv_name,
            'parent_id': parent_id,
            'bidang': bidang,
            'status': 'aktif'
        })
        
        print(f"✅ {subdiv_name[:55]:<55} → {parent_name}")
    else:
        no_match.append(subdiv_name)
        print(f"⚠️  {subdiv_name[:55]:<55} → NO MATCH!")

print()
print(f"📋 Matched: {len(subdiv_to_create)} subdiv")

if no_match:
    print(f"⚠️  No match: {len(no_match)} subdiv")
    print("   (These will be skipped)")
    for nm in no_match[:5]:
        print(f"   - {nm}")
    if len(no_match) > 5:
        print(f"   ... and {len(no_match)-5} more")

print()

# ============================================
# Insert subdiv
# ============================================

if subdiv_to_create:
    print(f"🚀 Ready to insert {len(subdiv_to_create)} subdiv with proper hierarchy")
    print()
    
    confirm = input("Proceed with insertion? (yes/no): ")
    
    if confirm.lower() == 'yes':
        print()
        print("🚀 Inserting subdiv...")
        
        created = 0
        errors = []
        
        for data in subdiv_to_create:
            try:
                supabase.table('divisi').insert(data).execute()
                created += 1
                
                if created % 10 == 0:
                    print(f"   ✅ {created} subdiv inserted...")
                    
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' not in error_msg.lower():
                    errors.append(f"{data['nama'][:40]}: {error_msg[:50]}")
        
        print()
        print(f"✅ Created {created} subdiv!")
        
        if errors:
            print()
            print(f"❌ {len(errors)} errors occurred:")
            for err in errors[:5]:
                print(f"   - {err}")
            if len(errors) > 5:
                print(f"   ... and {len(errors)-5} more")
        
        print()
        
        # ============================================
        # Verify hierarchy
        # ============================================
        
        print("🔍 Verifying hierarchy...")
        
        all_div = supabase.table('divisi').select('id, nama, parent_id').execute()
        parents = [d for d in all_div.data if d['parent_id'] is None]
        children = [d for d in all_div.data if d['parent_id'] is not None]
        
        print()
        print("=" * 60)
        print("📊 FINAL DATABASE STATE")
        print("=" * 60)
        print(f"✅ Total divisi: {len(all_div.data)}")
        print(f"   - Parent divisi: {len(parents)}")
        print(f"   - Sub-divisi (children): {len(children)}")
        print()
        
        # Show sample hierarchy
        print("🌳 Sample hierarchy:")
        for parent in sorted(parents, key=lambda x: x['nama'])[:3]:
            print(f"   {parent['nama']}")
            parent_children = [c for c in children if c['parent_id'] == parent['id']]
            for child in sorted(parent_children, key=lambda x: x['nama'])[:3]:
                print(f"   ├── {child['nama']}")
            if len(parent_children) > 3:
                print(f"   └── ... and {len(parent_children)-3} more subdiv")
        print()
        
        print("🎉 Subdiv insertion complete!")
        print()
        
    else:
        print()
        print("❌ Insertion cancelled.")
        print()
else:
    print("⚠️  No subdiv to insert!")
    print()

print("✨ Script finished!")