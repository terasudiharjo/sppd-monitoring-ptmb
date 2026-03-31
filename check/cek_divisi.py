import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔍 CHECKING DIVISI STRUCTURE")
print("=" * 80)
print()

# Get all divisi
all_divisi = supabase.table('divisi').select('*').execute()

# Separate parents and children
parents = [d for d in all_divisi.data if d['parent_id'] is None]
children = [d for d in all_divisi.data if d['parent_id'] is not None]

print(f"📊 SUMMARY:")
print(f"   Total divisi: {len(all_divisi.data)}")
print(f"   - Parents: {len(parents)}")
print(f"   - Children: {len(children)}")
print()

# Show full hierarchy
print("🌳 FULL HIERARCHY:")
print("=" * 80)

for parent in sorted(parents, key=lambda x: x['nama']):
    print(f"\n📁 {parent['nama']} ({parent['kode']}) - {parent['bidang']}")
    
    # Get children of this parent
    parent_children = [c for c in children if c['parent_id'] == parent['id']]
    
    if parent_children:
        for i, child in enumerate(sorted(parent_children, key=lambda x: x['nama']), 1):
            prefix = "└──" if i == len(parent_children) else "├──"
            print(f"   {prefix} {child['nama']} ({child['kode']})")
    else:
        print("   (no sub-divisi)")

print()
print("✨ Done!")