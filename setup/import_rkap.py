"""
Import RKAP from CSV files → Supabase
SPPD PDAM Balikpapan

Transformasi: horizontal (12 kolom bulan) → vertical (12 rows per kategori)
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
# Helper: Clean angka (handle format "15,800,000" dan NaN)
# ============================================

def clean_angka(nilai):
    """Convert string angka dengan koma ke integer, NaN → 0"""
    if pd.isna(nilai) or nilai == '' or nilai is None:
        return 0
    if isinstance(nilai, str):
        nilai = nilai.replace(',', '').strip()
        if nilai == '':
            return 0
    try:
        return int(float(nilai))
    except:
        return 0

# ============================================
# Load lokasi_sppd
# ============================================

print("📊 Loading lokasi_sppd...")

lokasi_response = supabase.table('lokasi_sppd').select('*').execute()
lokasi_map = {row['nama']: row['id'] for row in lokasi_response.data}

print(f"✅ Loaded {len(lokasi_map)} lokasi:")
for nama in lokasi_map:
    print(f"   - {nama}")
print()

# Cari ID per lokasi
lokasi_dalam_id = None
lokasi_luar_id = None
lokasi_ln_id = None

for nama, id in lokasi_map.items():
    if 'Dalam' in nama:
        lokasi_dalam_id = id
    elif 'Luar' in nama and 'Negeri' not in nama:
        lokasi_luar_id = id
    elif 'Negeri' in nama:
        lokasi_ln_id = id

print(f"✅ Dalam Kaltim ID : {lokasi_dalam_id}")
print(f"✅ Luar Kaltim ID  : {lokasi_luar_id}")
print(f"✅ Luar Negeri ID  : {lokasi_ln_id}")
print()

# ============================================
# Load CSV files
# ============================================

print("📂 Loading CSV files...")

# Handle 2 versi header: "Agutus" (typo) dan "Agustus" (bener)
BULAN_MAP_TYPO = {
    'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4,
    'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agutus': 8,
    'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
}

BULAN_MAP_BENER = {
    'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4,
    'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8,
    'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
}

def get_bulan_map(df):
    """Auto-detect versi header Agustus atau Agutus"""
    if 'Agustus' in df.columns:
        return BULAN_MAP_BENER
    else:
        return BULAN_MAP_TYPO

try:
    df_dalam = pd.read_csv("data/rkap_dalam_kaltim.csv")
    print(f"✅ Dalam Kaltim : {len(df_dalam)} kategori jabatan")
except FileNotFoundError:
    print("❌ File not found: data/rkap_dalam_kaltim.csv")
    exit()

try:
    df_luar = pd.read_csv("data/rkap_luar_kaltim.csv")
    print(f"✅ Luar Kaltim  : {len(df_luar)} kategori jabatan")
except FileNotFoundError:
    print("❌ File not found: data/rkap_luar_kaltim.csv")
    exit()

try:
    df_bantuan = pd.read_csv("data/rkap_bantuan.csv")
    print(f"✅ Bantuan      : {len(df_bantuan)} kategori jabatan")
    has_bantuan = True
except FileNotFoundError:
    print("⚠️  File not found: data/rkap_bantuan.csv (akan di-skip)")
    has_bantuan = False

print()

# ============================================
# Transform: horizontal → vertical
# ============================================

def transform_csv(df, lokasi_id, lokasi_nama, tahun=2025, override_lokasi=None):
    """
    Convert 1 row per kategori (12 kolom bulan)
    → 12 rows per kategori (1 kolom bulan)

    override_lokasi: dict {kategori: lokasi_id} untuk row yang lokasi-nya berbeda
    """
    records = []
    bulan_map = get_bulan_map(df)

    for idx, row in df.iterrows():
        kategori = row['Jabatan'].strip()

        # Cek apakah row ini punya override lokasi
        if override_lokasi and kategori in override_lokasi:
            use_lokasi_id = override_lokasi[kategori]
            use_lokasi_nama = "Luar Negeri"
        else:
            use_lokasi_id = lokasi_id
            use_lokasi_nama = lokasi_nama

        for kolom_bulan, nomor_bulan in bulan_map.items():
            if kolom_bulan not in df.columns:
                continue

            anggaran = clean_angka(row[kolom_bulan])

            lokasi_kode = next((r['kode'] for r in lokasi_response.data if r['id'] == use_lokasi_id), 'XX')

            record = {
                'kode_rkap': f"RKAP-{lokasi_kode}-{kategori}-{tahun}-{nomor_bulan:02d}",
                'nama_kegiatan': f"Perjalanan Dinas {kategori} - {use_lokasi_nama}",
                'kategori_jabatan': kategori,
                'lokasi_id': use_lokasi_id,
                'tahun': tahun,
                'bulan': nomor_bulan,
                'anggaran_awal': anggaran,
                'anggaran_terpakai': 0,
                'anggaran_sisa': anggaran,
                'status': 'aktif'
            }

            records.append(record)

        print(f"   ✅ {kategori:<35} → {use_lokasi_nama}")

    return records

print("🔧 Transforming data (horizontal → vertical)...")
print()

rkap_to_insert = []

print("📌 Dalam Kaltim:")
rkap_to_insert += transform_csv(df_dalam, lokasi_dalam_id, "Dalam Kaltim")
print()

print("📌 Luar Kaltim:")
rkap_to_insert += transform_csv(df_luar, lokasi_luar_id, "Luar Kaltim")
print()

if has_bantuan:
    print("📌 Bantuan:")
    # bantuan_sppd          → Dalam Kaltim
    # bantuan_sppd_luar_negeri → Luar Negeri
    override = {
        'bantuan_sppd_luar_negeri': lokasi_ln_id
    }
    rkap_to_insert += transform_csv(df_bantuan, lokasi_dalam_id, "Dalam Kaltim", override_lokasi=override)
    print()

print(f"📋 Total records to insert: {len(rkap_to_insert)}")
print()

# ============================================
# Preview sample
# ============================================

print("👀 PREVIEW (5 records pertama):")
print("-" * 90)
print(f"{'Kategori':<35} {'Lokasi':<25} {'Bulan':<8} {'Anggaran':>15}")
print("-" * 90)
for r in rkap_to_insert[:5]:
    lokasi_nama = next((n for n, i in lokasi_map.items() if i == r['lokasi_id']), '?')
    print(f"{r['kategori_jabatan']:<35} {lokasi_nama:<25} Bulan {r['bulan']:<4} Rp {r['anggaran_awal']:>12,}")
print("-" * 90)
print()

# ============================================
# Konfirmasi & Insert
# ============================================

confirm = input("🚀 Proceed with insertion? (yes/no): ")

if confirm.lower() != 'yes':
    print("❌ Import cancelled.")
    exit()

print()
print("🚀 Inserting RKAP data...")
print("=" * 80)

BATCH_SIZE = 50
success = 0
errors = []

for i in range(0, len(rkap_to_insert), BATCH_SIZE):
    batch = rkap_to_insert[i:i+BATCH_SIZE]
    batch_num = (i // BATCH_SIZE) + 1
    total_batch = (len(rkap_to_insert) + BATCH_SIZE - 1) // BATCH_SIZE

    try:
        supabase.table('rkap').insert(batch).execute()
        success += len(batch)
        print(f"   ✅ Batch {batch_num}/{total_batch}: {len(batch)} records inserted")
    except Exception as e:
        error_msg = str(e)
        errors.append(f"Batch {batch_num}: {error_msg[:80]}")
        print(f"   ❌ Batch {batch_num}/{total_batch}: ERROR - {error_msg[:60]}")

print()
print("=" * 80)
print("📊 IMPORT SUMMARY")
print("=" * 80)
print(f"✅ Success : {success} records inserted")
print(f"❌ Errors  : {len(errors)}")
print()

if errors:
    print("🔍 Error details:")
    for err in errors:
        print(f"   - {err}")
    print()

count_response = supabase.table('rkap').select('id', count='exact').execute()
print(f"✅ Total RKAP in database: {count_response.count} records")
print()
print("🎉 Import completed!")
print("✨ Script finished!")