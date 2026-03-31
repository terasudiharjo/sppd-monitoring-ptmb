"""
Script import data historis realisasi SPPD Jan-Mar 2026.
Jalankan dari folder root:  python setup/import_realisasi_2026.py

Mode:
  DRY_RUN = True   -> hanya preview, tidak insert ke DB
  DRY_RUN = False  -> insert ke DB sungguhan

Strategi:
  - 1 No. SPD  = 1 visum + 1 spd
  - 1 baris    = 1 sppd (status: completed)
  - Komponen biaya diisi dari kolom CSV, uang harian terpisah tidak diketahui
    -> total_biaya diisi, breakdown diisi seadanya dari CSV
  - RKAP tidak di-deduct (adjust manual di Supabase)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ─── KONFIGURASI ────────────────────────────────────────────
DRY_RUN = False   # Ganti ke False untuk import sungguhan
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'realisasi_sppd_2026.csv')

# Mapping nama CSV -> nama di DB (untuk nama yang disingkat/beda ejaan)
NAMA_MAP = {
    "Julia Eka. N"       : "JULIA EKA NURLIANI",
    "Meidiansyah K.W"   : "MEIDIANSYAH KUSUMA W",
    "Agus Budi. P"      : "AGUS BUDI PRASETYO S",
    "Anthero Bagus P.G" : "ANTHERO BAGUS PUJI G",
    "Ganden Aditera. I" : "GANDEN ADITERA ISMED",
    "Jeffry Rachman. B" : "JEFFRY RACHMAN BATUT",
    "Joko Wibowo. A"    : "JOKO WIBOWO APRIANTO",
    "M. Deddy Moeslim"  : "M DEDDY MOESLIM",
    "M. Kohirudin"      : "MOHAMAD KOHIRUDIN",
    "M. Rahmad Hidayat" : "MUHAMAD RAHMAD HIDAYAT",
    "Sayid Zain A.Y"    : "SAYID ZAIN ASHAD YAH",   # typo di CSV -> nama DB
    "Syaid Zain A.Y"    : "SAYID ZAIN ASHAD YAH",
    "Ucu Dwi. A"        : "UCU DWI ANASTO",
    "Vunny Saras. K"    : "VUNNY SARAS KINANTI",
    "Suryo Hadi. P"     : "SURYO HADI PRABOWO",
}

# Mapping kota -> lokasi (Dalam Kaltim / Luar Kaltim / Luar Negeri)
KOTA_DALAM_KALTIM = {"Samarinda", "Balikpapan", "Bontang", "Tenggarong",
                      "Penajam", "Tanjung Redeb", "Berau", "Kutai"}
KOTA_LUAR_NEGERI  = set()  # isi kalau ada

# ─── SETUP DB ───────────────────────────────────────────────
def get_db():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

# ─── HELPER ─────────────────────────────────────────────────
def parse_uang(val):
    """' 4,900,000 ' -> 4900000"""
    if pd.isna(val) or str(val).strip() in ('', 'nan'):
        return 0
    return int(str(val).replace(',', '').replace(' ', '').strip())

def parse_tgl(val):
    """'5-Jan-26' -> date(2026,1,5)"""
    if pd.isna(val) or str(val).strip() in ('', 'nan'):
        return None
    try:
        return datetime.strptime(str(val).strip(), "%d-%b-%y").date()
    except:
        return None

def hitung_hari(tgl_berangkat, tgl_kembali):
    if not tgl_berangkat or not tgl_kembali:
        return 1
    delta = (tgl_kembali - tgl_berangkat).days + 1
    return max(1, delta)

def resolve_lokasi(kota, lokasi_map):
    """Kota -> lokasi_id berdasarkan nama lokasi di DB."""
    kota = str(kota).strip()
    if kota in KOTA_LUAR_NEGERI:
        for lid, lnama in lokasi_map.items():
            if "luar negeri" in lnama.lower():
                return lid
    if kota in KOTA_DALAM_KALTIM:
        for lid, lnama in lokasi_map.items():
            if "dalam" in lnama.lower():
                return lid
    # Default: Luar Kaltim
    for lid, lnama in lokasi_map.items():
        if "luar" in lnama.lower() and "negeri" not in lnama.lower():
            return lid
    return list(lokasi_map.keys())[0]

def cari_pegawai(nama_csv, pegawai_map):
    """Cari pegawai_id dari nama CSV. Return (id, nama_db) atau (None, None)."""
    nama_csv = str(nama_csv).strip()
    # Cek nama_map dulu
    nama_target = NAMA_MAP.get(nama_csv, nama_csv)
    nama_target_lower = nama_target.lower()

    # Exact match
    if nama_target_lower in pegawai_map:
        p = pegawai_map[nama_target_lower]
        return p['id'], p['nama']

    # Partial match: semua kata di nama_target ada di nama DB
    kata = nama_target_lower.split()
    candidates = []
    for k, p in pegawai_map.items():
        if all(w in k for w in kata):
            candidates.append(p)
    if len(candidates) == 1:
        return candidates[0]['id'], candidates[0]['nama']

    # Fallback: cari berdasarkan nama CSV langsung (partial)
    kata2 = nama_csv.lower().split()
    candidates2 = []
    for k, p in pegawai_map.items():
        if all(w in k for w in kata2):
            candidates2.append(p)
    if len(candidates2) == 1:
        return candidates2[0]['id'], candidates2[0]['nama']

    return None, None

def nomor_visum_dari_spd(spd_no):
    """'0001/I/26' -> nomor visum '001/VI/I/2026' (format PTMB)."""
    # Simpan saja nomor SPD sebagai referensi di nomor_visum
    return f"HIST-{spd_no}"

# ─── MAIN ───────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"IMPORT REALISASI SPPD 2026 | DRY_RUN={DRY_RUN}")
    print("=" * 60)

    db = get_db()

    # Load master data dari DB
    print("\n[1] Load master data dari DB...")
    res_lokasi  = db.table("lokasi_sppd").select("id, nama").execute()
    res_pegawai = db.table("pegawai").select("id, nama").eq("status", "aktif").execute()
    res_jabatan = db.table("jabatan").select("id, nama").eq("status", "aktif").execute()

    lokasi_map  = {r['id']: r['nama'] for r in res_lokasi.data}
    pegawai_map = {r['nama'].lower(): r for r in res_pegawai.data}
    jabatan_map = {r['nama'].lower(): r for r in res_jabatan.data}

    print(f"  Pegawai aktif: {len(pegawai_map)}")
    print(f"  Lokasi: {[v for v in lokasi_map.values()]}")

    # Parse CSV
    print("\n[2] Parse CSV...")
    df_raw = pd.read_csv(CSV_PATH, header=3)
    df_raw.columns = [
        'no','tgl_berangkat','tgl_kembali','nama','jabatan','kota','uraian','kegiatan',
        'spd_uang_saku','tgl_spd','voucher_uang_saku','jumlah_uang_saku',
        'spd_tiket','tgl_spd_tiket','voucher_tiket','jumlah_tiket',
        'spd_hotel','tgl_spd_hotel','voucher_hotel','jumlah_hotel',
        'spd_lain','tgl_spd_lain','voucher_lain','jumlah_lain',
        'total','c25','c26','c27','c28','c29','c30','c31','c32','c33','c34','c35'
    ]
    df = df_raw[pd.to_numeric(df_raw['no'], errors='coerce').notna()].copy()
    df['nama'] = df['nama'].astype(str).str.strip()
    df = df[df['nama'].str.lower() != 'nan'].copy()
    print(f"  Total baris data: {len(df)}")

    # Resolve pegawai
    print("\n[3] Resolve nama -> pegawai_id...")
    tidak_ditemukan = []
    df['pegawai_id']  = None
    df['nama_db']     = None
    for idx, row in df.iterrows():
        pid, nama_db = cari_pegawai(row['nama'], pegawai_map)
        df.at[idx, 'pegawai_id'] = pid
        df.at[idx, 'nama_db']    = nama_db
        if pid is None:
            tidak_ditemukan.append(row['nama'])

    if tidak_ditemukan:
        print(f"\n  [!]  TIDAK DITEMUKAN di DB ({len(tidak_ditemukan)} baris):")
        for n in set(tidak_ditemukan):
            print(f"     - '{n}'")
        print("\n  -> Tambahkan mapping ke NAMA_MAP di script ini, lalu jalankan ulang.")
        if not DRY_RUN:
            print("  -> DRY_RUN=False dibatalkan karena ada nama tidak ditemukan.")
            return
    else:
        print("  Semua nama berhasil di-resolve.")

    # Group by No. SPD
    print("\n[4] Preview per No. SPD...")
    grouped = df.groupby('spd_uang_saku', sort=False)
    print(f"  Total SPD unik: {grouped.ngroups}")

    # Tracking hasil
    ok_visum = 0
    ok_sppd  = 0
    errors   = []

    for spd_no, group in grouped:
        tgl_b = parse_tgl(group['tgl_berangkat'].iloc[0])
        tgl_k = parse_tgl(group['tgl_kembali'].iloc[0])
        tgl_spd = parse_tgl(group['tgl_spd'].iloc[0])
        kota  = str(group['kota'].iloc[0]).strip()
        uraian = str(group['uraian'].iloc[0]).strip()
        kegiatan = str(group['kegiatan'].iloc[0]).strip()
        lokasi_id = resolve_lokasi(kota, lokasi_map)
        peserta_list = []

        for _, r in group.iterrows():
            if r['pegawai_id']:
                peserta_list.append({
                    "pegawai_id": r['pegawai_id'],
                    "nama": r['nama_db']
                })

        print(f"\n  SPD {spd_no} | {tgl_b} s/d {tgl_k} | {kota} | {len(group)} peserta")
        for _, r in group.iterrows():
            status_nama = r['nama_db'] if r['nama_db'] else f"[X] {r['nama']}"
            print(f"    - {status_nama} | uang_saku={parse_uang(r['jumlah_uang_saku']):,} | "
                  f"tiket={parse_uang(r['jumlah_tiket']):,} | hotel={parse_uang(r['jumlah_hotel']):,} | "
                  f"lain={parse_uang(r['jumlah_lain']):,} | total={parse_uang(r['total']):,}")

        if DRY_RUN:
            ok_visum += 1
            ok_sppd  += len(group)
            continue

        # ── INSERT KE DB ──
        try:
            # 1. Insert visum
            visum_data = {
                "nomor_visum"     : nomor_visum_dari_spd(spd_no),
                "tanggal_visum"   : str(tgl_spd or tgl_b or date.today()),
                "tujuan"          : kota,
                "tanggal_berangkat": str(tgl_b) if tgl_b else str(date.today()),
                "tanggal_kembali" : str(tgl_k) if tgl_k else str(tgl_b or date.today()),
                "lama_hari"       : hitung_hari(tgl_b, tgl_k),
                "keperluan"       : uraian if uraian != 'nan' else kegiatan,
                "peserta"         : peserta_list,
                "status"          : "completed",
                "disposisi"       : [],
            }
            res_v = db.table("visum").insert(visum_data).execute()
            visum_id = res_v.data[0]['id']

            # 2. Insert spd
            total_spd = sum(parse_uang(r['total']) for _, r in group.iterrows())
            spd_data = {
                "nomor_spd"   : spd_no,
                "tanggal_spd" : str(tgl_spd or tgl_b or date.today()),
                "visum_id"    : visum_id,
                "grand_total" : total_spd,
                "status"      : "completed",
            }
            res_s = db.table("spd").insert(spd_data).execute()
            spd_id = res_s.data[0]['id']

            # 3. Insert sppd per peserta
            for _, r in group.iterrows():
                if not r['pegawai_id']:
                    errors.append(f"Skip {r['nama']} (tidak ditemukan di DB)")
                    continue

                uang_saku = parse_uang(r['jumlah_uang_saku'])
                tiket     = parse_uang(r['jumlah_tiket'])
                hotel     = parse_uang(r['jumlah_hotel'])
                lain      = parse_uang(r['jumlah_lain'])
                total_b   = parse_uang(r['total'])
                hari      = hitung_hari(tgl_b, tgl_k)

                sppd_data = {
                    "nomor_sppd"           : spd_no,
                    "pegawai_id"           : r['pegawai_id'],
                    "visum_id"             : visum_id,
                    "spd_id"               : spd_id,
                    "lokasi_id"            : lokasi_id,
                    "total_hari"           : hari,
                    "uang_harian_total"    : uang_saku,   # breakdown tidak ada di CSV
                    "uang_makan_total"     : 0,
                    "transport_lokal_total": 0,
                    "uang_representasi_total": 0,
                    "subtotal_uang_saku"   : uang_saku,
                    "total_transport"      : tiket,
                    "total_hotel"          : hotel,
                    "total_sewa_kendaraan" : 0,
                    "biaya_jenazah"        : 0,
                    "total_biaya"          : total_b,
                    "menginap"             : hotel > 0,
                    "status"               : "completed",
                }
                db.table("sppd").insert(sppd_data).execute()
                ok_sppd += 1

            ok_visum += 1
            print(f"    [OK] Insert berhasil: visum_id={visum_id}, spd_id={spd_id}")

        except Exception as e:
            msg = f"ERROR di SPD {spd_no}: {e}"
            print(f"    [X] {msg}")
            errors.append(msg)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Visum   : {ok_visum}")
    print(f"  SPPD    : {ok_sppd}")
    if errors:
        print(f"  Errors  : {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    if DRY_RUN:
        print("\n  [i]  DRY RUN — tidak ada data yang diinsert.")
        print("  Ganti DRY_RUN = False untuk import sungguhan.")
    else:
        print("\n  [OK] Import selesai!")

if __name__ == "__main__":
    main()
