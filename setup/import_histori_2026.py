"""
Script import data historis SPPD Jan-Mar 2026 dari CSV baru.
Source: data/histori sppd 2026.csv

Jalankan dari folder root:  python setup/import_histori_2026.py

Mode:
  DRY_RUN = True   -> preview saja, tidak insert ke DB
  DRY_RUN = False  -> insert ke DB sungguhan

Strategi:
  - 1 Nomor Visum Lengkap = 1 visum + 1 spd
  - 1 baris CSV          = 1 sppd (status: completed)
  - Biaya Lain-lain > 0  -> insert ke sppd_biaya_lain
  - Nomor visum & SPD    -> langsung dari kolom CSV (bukan generate HIST-)
  - RKAP tidak di-deduct -> jalankan deduct_rkap_historis.py terpisah
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client
from utils.database import update_rekap_spd

load_dotenv()

# --- KONFIGURASI ---
DRY_RUN  = True
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'histori sppd 2026.csv')

# Mapping nama CSV -> nama di DB
NAMA_MAP = {
    "Julia Eka. N"       : "JULIA EKA NURLIANI",
    "Meidiansyah K.W"    : "MEIDIANSYAH KUSUMA W",
    "Agus Budi. P"       : "AGUS BUDI PRASETYO S",
    "Anthero Bagus P.G"  : "ANTHERO BAGUS PUJI G",
    "Ganden Aditera. I"  : "GANDEN ADITERA ISMED",
    "Jeffry Rachman. B"  : "JEFFRY RACHMAN BATUT",
    "Joko Wibowo. A"     : "JOKO WIBOWO APRIANTO",
    "M. Deddy Moeslim"   : "M DEDDY MOESLIM",
    "M. Kohirudin"       : "MOHAMAD KOHIRUDIN",
    "M. Rahmad Hidayat"  : "MUHAMAD RAHMAD HIDAYAT",
    "Sayid Zain A.Y"     : "SAYID ZAIN ASHAD YAH",
    "Syaid Zain A.Y"     : "SAYID ZAIN ASHAD YAH",
    "Ucu Dwi. A"         : "UCU DWI ANASTO",
    "Vunny Saras. K"     : "VUNNY SARAS KINANTI",
    "Suryo Hadi. P"      : "SURYO HADI PRABOWO",
}

# --- DB ---
def get_db():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- HELPER ---
def parse_uang(val):
    if pd.isna(val) or str(val).strip() in ('', 'nan'):
        return 0
    return int(float(str(val).replace(',', '').replace(' ', '').strip()))

def parse_tgl(val):
    """Handle d/m/yyyy (dengan atau tanpa leading zero) dan d-Mon-yy."""
    if pd.isna(val) or str(val).strip() in ('', 'nan'):
        return None
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%y", "%d-%b-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except:
            continue
    return None

def hitung_hari(tgl_berangkat, tgl_kembali):
    if not tgl_berangkat or not tgl_kembali:
        return 1
    return max(1, (tgl_kembali - tgl_berangkat).days + 1)

def cari_pegawai(nama_csv, pegawai_map):
    nama_csv    = str(nama_csv).strip()
    nama_target = NAMA_MAP.get(nama_csv, nama_csv)
    nama_lower  = nama_target.lower()

    # Exact match
    if nama_lower in pegawai_map:
        p = pegawai_map[nama_lower]
        return p['id'], p['nama']

    # Partial match: semua kata ada di nama DB
    kata = nama_lower.split()
    candidates = [p for k, p in pegawai_map.items() if all(w in k for w in kata)]
    if len(candidates) == 1:
        return candidates[0]['id'], candidates[0]['nama']

    # Fallback: cari dari nama CSV langsung
    kata2 = nama_csv.lower().split()
    candidates2 = [p for k, p in pegawai_map.items() if all(w in k for w in kata2)]
    if len(candidates2) == 1:
        return candidates2[0]['id'], candidates2[0]['nama']

    return None, None

def resolve_lokasi_luar_kaltim(lokasi_map):
    """Default: Luar Kaltim (perjalanan dinas umum historis)."""
    for lid, lnama in lokasi_map.items():
        if "luar" in lnama.lower() and "negeri" not in lnama.lower():
            return lid
    return list(lokasi_map.keys())[0]

# --- MAIN ---
def main():
    print("=" * 60)
    print(f"IMPORT HISTORI SPPD 2026 | DRY_RUN={DRY_RUN}")
    print("=" * 60)

    db = get_db()

    # Load master data
    print("\n[1] Load master data dari DB...")
    res_lokasi  = db.table("lokasi_sppd").select("id, nama").execute()
    res_pegawai = db.table("pegawai").select("id, nama").eq("status", "aktif").execute()

    lokasi_map  = {r['id']: r['nama'] for r in res_lokasi.data}
    pegawai_map = {r['nama'].lower(): r for r in res_pegawai.data}
    lokasi_luar = resolve_lokasi_luar_kaltim(lokasi_map)

    print(f"  Pegawai aktif : {len(pegawai_map)}")
    print(f"  Lokasi tersedia: {list(lokasi_map.values())}")
    print(f"  Default lokasi : {lokasi_map[lokasi_luar]}")

    # Parse CSV
    print("\n[2] Parse CSV...")
    df = pd.read_csv(CSV_PATH)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['Nama']).copy()
    df['Nama'] = df['Nama'].astype(str).str.strip()
    df = df[df['Nama'].str.lower() != 'nan'].copy()
    print(f"  Total baris data: {len(df)}")

    # Resolve pegawai
    print("\n[3] Resolve nama -> pegawai_id...")
    tidak_ditemukan = []
    df['pegawai_id'] = None
    df['nama_db']    = None
    for idx, row in df.iterrows():
        pid, nama_db = cari_pegawai(row['Nama'], pegawai_map)
        df.at[idx, 'pegawai_id'] = pid
        df.at[idx, 'nama_db']    = nama_db
        if pid is None:
            tidak_ditemukan.append(row['Nama'])

    if tidak_ditemukan:
        print(f"\n  [!] TIDAK DITEMUKAN ({len(tidak_ditemukan)} baris):")
        for n in sorted(set(tidak_ditemukan)):
            print(f"      - '{n}'")
        print("\n  -> Tambahkan mapping ke NAMA_MAP dan jalankan ulang.")
        if not DRY_RUN:
            print("  -> DRY_RUN=False dibatalkan karena ada nama tidak ditemukan.")
            return
    else:
        print("  Semua nama berhasil di-resolve.")

    # Group by Nomor Visum
    print("\n[4] Preview per Visum...")
    grouped = df.groupby('Nomor Visum Lengkap', sort=False)
    print(f"  Total Visum unik: {grouped.ngroups}")

    ok_visum = 0
    ok_sppd  = 0
    errors   = []

    for nomor_visum, group in grouped:
        nomor_spd = str(group['Nomor SPD Lengkap'].iloc[0]).strip()
        perihal   = str(group['Perihal/Uraian Kegiatan'].iloc[0]).strip()
        tgl_b     = parse_tgl(group['Tgl Berangkat'].iloc[0])
        tgl_k     = parse_tgl(group['Tgl Kembali'].iloc[0])
        hari      = hitung_hari(tgl_b, tgl_k)
        kota_tujuan = str(group['Kota Tujuan'].iloc[0]).strip()
        if kota_tujuan.lower() in ('', 'nan'):
            kota_tujuan = "-"

        peserta_list = [
            {"pegawai_id": r['pegawai_id'], "nama": r['nama_db']}
            for _, r in group.iterrows() if r['pegawai_id']
        ]

        print(f"\n  Visum : {nomor_visum}")
        print(f"  SPD   : {nomor_spd}")
        print(f"  Tgl   : {tgl_b} s/d {tgl_k} ({hari} hari) | {perihal[:55]}")
        for _, r in group.iterrows():
            nama_label = r['nama_db'] if r['nama_db'] else f"[X] {r['Nama']}"
            bl = parse_uang(r.get('Biaya Lain-lain', 0))
            print(f"  {'':4}- {nama_label:<30s} saku={parse_uang(r['Biaya SPPD']):>10,} "
                  f"tiket={parse_uang(r['Biaya Tiket']):>10,} hotel={parse_uang(r['Biaya Hotel']):>10,} "
                  f"lain={bl:>8,} total={parse_uang(r['Total']):>12,}")

        if DRY_RUN:
            ok_visum += 1
            ok_sppd  += len(group)
            continue

        # --- INSERT KE DB ---
        try:
            # 1. Insert visum
            visum_data = {
                "nomor_visum"      : nomor_visum,
                "tanggal_visum"    : str(tgl_b or date.today()),
                "tujuan"           : kota_tujuan,
                "tanggal_berangkat": str(tgl_b or date.today()),
                "tanggal_kembali"  : str(tgl_k or tgl_b or date.today()),
                "lama_hari"        : hari,
                "keperluan"        : perihal if perihal not in ('nan', '') else "-",
                "peserta"          : peserta_list,
                "status"           : "completed",
                "disposisi"        : [],
            }
            res_v    = db.table("visum").insert(visum_data).execute()
            visum_id = res_v.data[0]['id']

            # 2. Insert spd
            total_spd = sum(parse_uang(r['Total']) for _, r in group.iterrows())
            spd_data  = {
                "nomor_spd"   : nomor_spd,
                "tanggal_spd" : str(tgl_b or date.today()),
                "visum_id"    : visum_id,
                "grand_total" : total_spd,
                "status"      : "completed",
            }
            existing_spd = db.table("spd").select("id").eq("nomor_spd", nomor_spd).execute()
            if existing_spd.data:
                spd_id = existing_spd.data[0]['id']
                print(f"  [i] SPD '{nomor_spd}' sudah ada, reuse spd_id={spd_id}")
            else:
                res_s  = db.table("spd").insert(spd_data).execute()
                spd_id = res_s.data[0]['id']

            # 3. Insert sppd per peserta
            for _, r in group.iterrows():
                if not r['pegawai_id']:
                    errors.append(f"Skip '{r['Nama']}' (tidak ditemukan di DB)")
                    continue

                uang_saku  = parse_uang(r['Biaya SPPD'])
                tiket      = parse_uang(r['Biaya Tiket'])
                hotel      = parse_uang(r['Biaya Hotel'])
                biaya_lain = parse_uang(r.get('Biaya Lain-lain', 0))
                total_b    = parse_uang(r['Total'])

                sppd_data = {
                    "nomor_sppd"             : nomor_spd,
                    "pegawai_id"             : r['pegawai_id'],
                    "visum_id"               : visum_id,
                    "spd_id"                 : spd_id,
                    "lokasi_id"              : lokasi_luar,
                    "total_hari"             : hari,
                    "uang_harian_total"      : uang_saku,
                    "uang_makan_total"       : 0,
                    "transport_lokal_total"  : 0,
                    "uang_representasi_total": 0,
                    "subtotal_uang_saku"     : uang_saku,
                    "total_transport"        : tiket,
                    "total_hotel"            : hotel,
                    "total_sewa_kendaraan"   : 0,
                    "biaya_jenazah"          : 0,
                    "total_biaya"            : total_b,
                    "menginap"               : hotel > 0,
                    "status"                 : "completed",
                }
                res_sppd = db.table("sppd").insert(sppd_data).execute()
                sppd_id  = res_sppd.data[0]['id']
                ok_sppd += 1

                # 4. Insert biaya lain-lain (jika ada)
                if biaya_lain > 0:
                    db.table("sppd_biaya_lain").insert({
                        "sppd_id"    : sppd_id,
                        "urutan"     : 1,
                        "keterangan" : "Biaya lain-lain",
                        "jumlah"     : biaya_lain,
                    }).execute()

            # 5. Update rekap kategori di SPD
            update_rekap_spd(spd_id)

            ok_visum += 1
            print(f"  [OK] visum_id={visum_id} | spd_id={spd_id} | rekap diupdate")

        except Exception as e:
            msg = f"ERROR di Visum {nomor_visum}: {e}"
            print(f"  [X] {msg}")
            errors.append(msg)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Visum  : {ok_visum}")
    print(f"  SPPD   : {ok_sppd}")
    if errors:
        print(f"  Errors : {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    if DRY_RUN:
        print("\n  [i] DRY RUN - tidak ada data yang diinsert.")
        print("  Ganti DRY_RUN = False untuk import sungguhan.")
    else:
        print("\n  [OK] Import selesai!")


if __name__ == "__main__":
    main()
