"""
Check Database Schema - Tables, Columns, Relationships
SPPD PDAM Balikpapan
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

print("🔍 DATABASE SCHEMA ANALYZER")
print("=" * 100)
print()

# Get all tables
tables_query = """
SELECT 
    table_name,
    (SELECT COUNT(*) 
     FROM information_schema.columns 
     WHERE table_schema = 'public' 
     AND table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
"""

# Note: Supabase doesn't allow direct SQL execution via Python client for information_schema
# So we'll do it table by table

# List of tables (from our schema)
tables = [
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
    'dokumen'
]

print("📊 TABLES SUMMARY")
print("=" * 100)
print(f"{'Table Name':<30} {'Records':<15} {'Status':<20}")
print("-" * 100)

total_records = 0

for table in tables:
    try:
        response = supabase.table(table).select('*', count='exact').limit(0).execute()
        count = response.count
        total_records += count
        status = "✅ Active" if count > 0 else "⚠️  Empty"
        print(f"{table:<30} {count:<15} {status:<20}")
    except Exception as e:
        print(f"{table:<30} {'ERROR':<15} ❌ Not found")

print("-" * 100)
print(f"{'TOTAL':<30} {total_records:<15}")
print()

# Detailed schema per table
print("=" * 100)
print("📋 DETAILED SCHEMA")
print("=" * 100)
print()

# Sample one record from each table to infer schema
for table in tables:
    print(f"📁 TABLE: {table}")
    print("-" * 100)
    
    try:
        # Get one record to see structure
        response = supabase.table(table).select('*').limit(1).execute()
        
        if response.data:
            record = response.data[0]
            print(f"{'Column Name':<30} {'Sample Value':<40} {'Type':<20}")
            print("-" * 100)
            
            for key, value in record.items():
                value_str = str(value)[:37] + "..." if len(str(value)) > 40 else str(value)
                value_type = type(value).__name__
                
                # Infer SQL type
                if isinstance(value, str):
                    if len(value) == 36 and '-' in value:  # UUID pattern
                        sql_type = "UUID"
                    else:
                        sql_type = "TEXT"
                elif isinstance(value, int):
                    sql_type = "INTEGER / BIGINT"
                elif isinstance(value, bool):
                    sql_type = "BOOLEAN"
                elif value is None:
                    sql_type = "NULL (check schema)"
                else:
                    sql_type = value_type.upper()
                
                print(f"{key:<30} {value_str:<40} {sql_type:<20}")
        else:
            print("   (No records yet - table empty)")
        
        print()
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()

# Relationships (manual documentation since we can't query FK directly via Supabase client)
print("=" * 100)
print("🔗 RELATIONSHIPS")
print("=" * 100)
print()

relationships = [
    ("divisi", "parent_id", "divisi", "id", "Self-reference (hierarchy)"),
    ("divisi", "→", "pegawai", "divisi_id", "1 divisi has many pegawai"),
    ("jabatan", "→", "pegawai", "jabatan_id", "1 jabatan has many pegawai"),
    ("jabatan", "→", "rule_sppd", "jabatan", "1 jabatan has many tarif rules"),
    ("lokasi_sppd", "→", "rule_sppd", "lokasi_id", "1 lokasi has many rules"),
    ("lokasi_sppd", "→", "rkap", "lokasi_id", "1 lokasi has many RKAP"),
    ("lokasi_sppd", "→", "sppd", "lokasi_id", "1 lokasi has many SPPD"),
    ("pegawai", "→", "rkap", "pegawai_id", "1 pegawai can have individual RKAP"),
    ("pegawai", "→", "visum", "dibuat_oleh", "1 pegawai creates many visum"),
    ("visum", "→", "sppd", "visum_id", "1 visum has many SPPD"),
    ("pegawai", "→", "sppd", "pegawai_id", "1 pegawai has many SPPD"),
    ("rkap", "→", "sppd", "rkap_id", "1 RKAP funds many SPPD"),
    ("sppd", "→", "sppd_trip_detail", "sppd_id", "1 SPPD has many trips"),
    ("sppd", "→", "sppd_sewa_kendaraan", "sppd_id", "1 SPPD has many rentals"),
    ("dokumen", "→", "visum/sppd/trips", "ref_id", "Polymorphic (multiple tables)"),
]

print(f"{'Parent Table':<25} {'→':<5} {'Child Table':<25} {'FK Column':<20} {'Description':<40}")
print("-" * 100)

for parent, arrow, child, fk, desc in relationships:
    print(f"{parent:<25} {arrow:<5} {child:<25} {fk:<20} {desc:<40}")

print()
print("=" * 100)
print("✨ Schema analysis complete!")
print()

# Summary stats
print("📊 SUMMARY:")
print(f"   Total tables: {len(tables)}")
print(f"   Total records: {total_records}")
print(f"   Total relationships: {len(relationships)}")
print()