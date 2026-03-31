import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔧 Fixing missing subdiv...")

# Get DIVISI PRODUKSI parent_id
parent = supabase.table('divisi').select('id').eq('nama', 'DIVISI PRODUKSI').execute()
parent_id = parent.data[0]['id']

print(f"✅ Parent ID: {parent_id}")

# Insert missing subdiv
subdiv_to_add = [
    ('PENGOLAHAN_AIR_UNIT_II', 'SUB.DIVISI. PENGOLAHAN AIR UNIT II'),
    ('PENGOLAHAN_AIR_UNIT_III', 'SUB.DIVISI. PENGOLAHAN AIR UNIT III'),
    ('PENGOLAHAN_AIR_UNIT_IV', 'SUB.DIVISI. PENGOLAHAN AIR UNIT IV'),
    ('PENGOLAHAN_AIR_UNIT_V', 'SUB.DIVISI. PENGOLAHAN AIR UNIT V'),
    ('PENGOLAHAN_AIR_UNIT_VI', 'SUB.DIVISI. PENGOLAHAN AIR UNIT VI'),
]

created = 0
for kode, nama in subdiv_to_add:
    try:
        supabase.table('divisi').insert({
            'kode': kode,
            'nama': nama,
            'parent_id': parent_id,
            'bidang': 'Teknik',
            'status': 'aktif'
        }).execute()
        created += 1
        print(f"✅ Created: {nama}")
    except Exception as e:
        print(f"❌ Failed: {nama} - {e}")

print(f"\n✅ Created {created} subdiv!")