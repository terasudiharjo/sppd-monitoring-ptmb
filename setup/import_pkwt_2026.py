"""
Script import data pegawai PKWT dari DUK_PKWT_2026.csv ke tabel pegawai.
Jabatan: CALON PEGAWAI (id: 6d8c4b99-7199-4c8e-80a1-11d54464823b)

Jalankan dari folder root:  python setup/import_pkwt_2026.py

Mode:
  DRY_RUN = True   -> preview saja, tidak insert ke DB
  DRY_RUN = False  -> insert ke DB sungguhan
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# --- KONFIGURASI ---
DRY_RUN    = True
CSV_PATH   = os.path.join(os.path.dirname(__file__), '..', 'data', 'DUK_PKWT_2026.csv')
JABATAN_ID = "6d8c4b99-7199-4c8e-80a1-11d54464823b"  # CALON PEGAWAI

# Mapping nama divisi CSV -> divisi_id DB
DIVISI_MAP = {
    # Pengolahan Air
    "PENGOLAHAN AIR UNIT I"                  : "13e07fbd-a477-4703-99d8-8e4d0bc9f92b",
    "PENGOLAHAN AIR UNIT II"                 : "9eba8d04-0af7-4da6-a42b-f8316b32650c",
    "PENGOLAHAN AIR UNIT III"                : "43a82eac-4221-40e0-b7f9-7e4fd629b754",
    "PENGOLAHAN AIR UNIT IV"                 : "0b35a0a4-ad8f-480d-b98d-705763fb070d",
    "PENGOLAHAN AIR UNIT V"                  : "c68d217f-d9b6-44b3-8a03-3bbf86268c9c",
    "PENGOLAHAN AIR UNIT VI"                 : "0f45d9bb-cea2-4d99-806a-87244f4406f8",
    # Distribusi
    "DISTRIBUSI WIL 1"                       : "d3938fae-037f-4345-87e3-4b4860049f55",
    "DISTRIBUSI WIL 2"                       : "f13bcf50-2752-40c6-abc9-5f6034f5df13",
    "DISTRIBUSI WIL 3"                       : "8002d68b-76df-4146-9827-c8246ac9e70e",
    "DISTRIBUSI WIL 4"                       : "07a16bbf-ea87-47dc-a5cb-3f3b8ca5702a",
    "DISTRIBUSI WIL 5"                       : "44a22347-3ac3-46b9-b759-7758bf150853",
    # Lainnya
    "METER SEGEL"                            : "c288e2cb-5d01-4161-baf2-279357b0ede2",
    "PEMBACA METER"                          : "5a669f65-e63d-41a3-9ee1-862c0f343120",
    "PEMASARAN"                              : "f92f4f2a-4279-40d7-a9f9-1aa4a75cb9df",
    "CUSTOMER SERVICE"                       : "551ba508-546e-49db-9f7d-0793a918df63",
    "LABORATORIUM"                           : "256c02fd-d430-41f1-afac-91ea26a773d3",
    "AKUNTANSI"                              : "cd30bdcc-8a5e-4a23-a3cc-fb52fb3cec43",
    "PERLENGKAPAN & GUDANG"                  : "4c62a511-5b16-416b-b374-38fc5e655889",
    "IPAL & IPLT"                            : "cebf2478-2d68-4026-b170-89b1567cfd04",
    "PERALATAN IPAL & IPLT"                  : "139ccd74-8c8c-4194-b403-de88d223313d",
    "PERALATAN DISTRIBUSI"                   : "b6d32c84-cdba-45e3-beab-2098b6fcd2fd",
    "PERALATAN PRODUKSI"                     : "2a194756-8f52-4772-a165-b837fd84d6e3",
    "KESEKRETARIATAN & HUKUM"                : "86580b85-8671-479d-a072-7fec0c80f006",
    "ADM & PENGEMBANGAN KEPEGAWAIAN"         : "7d5794f4-f1eb-4116-b790-099dcd1551cf",
    "HUMAS & PI"                             : "0b30adbf-29fa-42f0-8dce-f21e8bd208ad",
    "FUNGSIONAL AUDITOR"                     : "845e4b78-572f-46e7-acaf-4365793d20e4",
    "PKA"                                    : "66c7d8c2-442c-46c6-9408-24d0184b72b4",
    "SAB"                                    : "94f9b343-2273-4333-8198-0f169353044d",
    "K3"                                     : "5e696849-0c6b-488f-9a21-0ad3857327ef",
    "DATA & APLIKASI"                        : "36c176ab-2fbf-433a-a441-135da5417149",
    "INFRASTRUKTUR & JARINGAN"               : "2b5817b5-4f14-4ea8-9a27-c60c13913373",
    "LITBANG"                                : "31ffaf14-1dba-4361-8dd4-7c792db7281e",
    "PERENCANAAN TEKNIK & PEMETAAN ASET"     : "d80c0904-749b-4cc2-8739-e0d6cb6d2e66",
    "PENGADAAN BARANG & JASA"                : "ef677495-43ab-4596-ad60-cbd7929f3d67",
    "PERBENDAHARAAN"                         : "aced2451-0ab9-4cfe-9f06-7f5e28bcf908",
    "SUMBER AIR & LINGKUNGAN"                : "94f9b343-2273-4333-8198-0f169353044d",
    # Divisi (level atas)
    "DIVISI DISTRIBUSI"                      : "0065d5d7-cf7d-4d3e-96f6-574830e61f04",
    "DIVISI PRODUKSI"                        : "1a04f399-3824-4b06-b504-4a3ab4c6a851",
    "DIVISI SDM"                             : "166c5a2e-65df-441e-be52-698b275103fe",
    "DIVISI LAYANAN PELANGGAN"               : "adc60e77-7ab6-458b-8cab-392715c26a16",
}

def get_db():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def normalize_divisi(raw):
    """Normalisasi nama divisi dari CSV ke key DIVISI_MAP."""
    s = str(raw).strip().upper()

    # Exact match dulu
    if s in DIVISI_MAP:
        return s

    import re

    # Bersihkan variasi umum
    s = s.replace("SUB.DIVISI.", "").replace("SUB DIVISI", "").strip()
    s = s.replace("/HUBLANG", "").replace("/ HUBLANG", "").replace("/AIR LIMBAH", "").strip()
    s = s.replace("/ AIR LIMBAH", "").replace("DISTRBUSI", "DISTRIBUSI").replace("DISTRIBSI", "DISTRIBUSI").strip()
    s = s.replace("DITRIBUSI", "DISTRIBUSI").replace("DISTRIBUSWI JAR", "DISTRIBUSI").strip()
    s = s.replace("DITRIBUSI", "DISTRIBUSI").replace("PERALATAN DITRIBUSI", "PERALATAN DISTRIBUSI").strip()
    s = s.replace("AKUTANSI", "AKUNTANSI").strip()
    # Hapus " / DISTRIBUSI" (termasuk double-space) di akhir
    s = re.sub(r"\s*/\s*DISTRIBUSI\b.*$", "", s).strip()
    s = s.replace("COSTUMER", "CUSTOMER").replace("CUSTOMER SERVICES", "CUSTOMER SERVICE").strip()
    s = s.replace("ADPENG & KEPEG", "").strip()
    s = s.replace("ADM & PENGEM KEPEGAWAIAN", "ADM & PENGEMBANGAN KEPEGAWAIAN").strip()
    s = s.replace("ADM & PENGEB KEPEG", "ADM & PENGEMBANGAN KEPEGAWAIAN").strip()
    s = s.replace("HUMAS PI", "HUMAS & PI").replace("HUMAS & PUSAT INFORMASI", "HUMAS & PI").strip()

    # PMA = Pembaca Meter
    if s == "PMA":
        return "PEMBACA METER"

    # Produksi IPA → Pengolahan Air (explicit, sebelum loop)
    for u in ["VI", "IV", "III", "II", "V", "I"]:
        if s == f"PRODUKSI IPA UNIT {u}":
            return f"PENGOLAHAN AIR UNIT {u}"

    # Strip lokasi tambahan (mis. "KMP BARU", "TERITIP")
    for suffix in [" KMP BARU", " TERITIP"]:
        s = s.replace(suffix, "")

    # Normalisasi IPA/Air → standar (urutan terpanjang dulu agar VI/IV tidak salah terpotong)
    for unit in ["VI", "IV", "III", "II", "V", "I"]:
        s = s.replace(f"PENGOLAHAN IPA UNIT {unit}", f"PENGOLAHAN AIR UNIT {unit}")
        s = s.replace(f"IPA UNIT {unit}", f"PENGOLAHAN AIR UNIT {unit}")
        s = s.replace(f"PRODUKSI IPA UNIT {unit}", f"PENGOLAHAN AIR UNIT {unit}")
        s = s.replace(f"IPAN UNIT {unit}", f"PENGOLAHAN AIR UNIT {unit}")

    # Normalisasi wilayah distribusi (urutan terpanjang dulu: IV sebelum I, III sebelum II)
    for n, rom in [("III", "3"), ("IV", "4"), ("II", "2"),
                   ("V", "5"), ("I", "1"), ("1", "1"), ("2", "2"),
                   ("3", "3"), ("4", "4"), ("5", "5")]:
        s = re.sub(rf"\bDISTRIBUSI\s+WILAYAH\s+{n}\b", f"DISTRIBUSI WIL {rom}", s)
        s = re.sub(rf"\bDISTRIBUSI\s+WILL?\s+{n}\b", f"DISTRIBUSI WIL {rom}", s)
        s = re.sub(rf"\bDISTRIBUSI\s+WIL\s+{n}\b",    f"DISTRIBUSI WIL {rom}", s)
        s = re.sub(rf"\bDISTRIBUSI\s+{n}\b",           f"DISTRIBUSI WIL {rom}", s)  # bare

    # Fix AKUNTANSI / KEUANGAN → AKUNTANSI
    if "AKUNTANSI" in s:
        s = "AKUNTANSI"

    # PKA / DISTRIBUSI → PKA
    if s.startswith("PKA"):
        s = "PKA"

    # IPAL & IPLT variasi
    if "IPAL" in s and "PERALATAN" not in s:
        s = "IPAL & IPLT"

    # DATA & APLIKASI
    if "DATA & APLIKASI" in s:
        s = "DATA & APLIKASI"

    # INFRASTRUKTUR & JARINGAN
    if "INFRASTRUKTUR" in s or "JARINGAN" in s:
        s = "INFRASTRUKTUR & JARINGAN"

    # LITBANG / PENELITIAN
    if "LITBANG" in s or "PENELITIAN" in s:
        s = "LITBANG"

    # LAB
    if s in ("LAB",):
        s = "LABORATORIUM"

    s = s.strip()
    return s if s in DIVISI_MAP else None


def main():
    print("=" * 60)
    print(f"IMPORT PKWT 2026 | DRY_RUN={DRY_RUN}")
    print("=" * 60)

    db = get_db()

    # Load pegawai existing untuk cek duplikat
    print("\n[1] Load data pegawai existing dari DB...")
    res = db.table("pegawai").select("nip, nama").execute()
    nip_existing  = {r['nip'] for r in res.data}
    nama_existing = {r['nama'].upper().strip() for r in res.data}
    print(f"  Pegawai di DB saat ini: {len(res.data)}")

    # Parse CSV
    print("\n[2] Parse CSV...")
    df = pd.read_csv(CSV_PATH, header=None, skiprows=4)
    df.columns = ['no', 'nama', 'nik', 'divisi']
    df = df[pd.to_numeric(df['no'], errors='coerce').notna()].copy()
    df['nama']   = df['nama'].astype(str).str.strip().str.upper()
    df['nik']    = df['nik'].apply(lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip() not in ('', 'nan') else None)
    df['divisi'] = df['divisi'].astype(str).str.strip()
    print(f"  Total PKWT di CSV: {len(df)}")

    # Cek duplikat & resolve divisi
    print("\n[3] Analisis data...")
    rows       = []
    duplikat   = []
    no_divisi  = []

    for _, r in df.iterrows():
        nama = r['nama']
        nik  = r['nik']

        # Cek duplikat NIK
        if nik and nik in nip_existing:
            duplikat.append(f"NIK {nik} ({nama}) sudah ada di DB")
            continue

        # Resolve divisi
        divisi_key = normalize_divisi(r['divisi'])
        divisi_id  = DIVISI_MAP.get(divisi_key) if divisi_key else None

        if not divisi_id:
            no_divisi.append((nama, nik, r['divisi']))

        rows.append({
            "nama"      : nama,
            "nik"       : nik,
            "divisi_raw": r['divisi'],
            "divisi_key": divisi_key,
            "divisi_id" : divisi_id,
        })

    # Laporan nama sama (warning saja, tetap diimport)
    nama_sama = [r for r in rows if r['nama'] in nama_existing]
    if nama_sama:
        print(f"\n  [!] NAMA SAMA DI DB ({len(nama_sama)} orang) — NIK berbeda, tetap diimport:")
        for r in nama_sama:
            print(f"      - {r['nama']} (NIK {r['nik']})")

    if duplikat:
        print(f"\n  [!] SKIP — NIK SUDAH ADA ({len(duplikat)}):")
        for d in duplikat:
            print(f"      - {d}")

    if no_divisi:
        print(f"\n  [!] DIVISI TIDAK DIKENALI ({len(no_divisi)}) — divisi_id akan NULL:")
        for nama, nik, raw in no_divisi:
            print(f"      - {nama} (NIK {nik}) | divisi CSV: '{raw}'")

    print(f"\n  Siap diimport: {len(rows)} orang")
    print(f"  Dengan divisi_id  : {len([r for r in rows if r['divisi_id']])}")
    print(f"  Tanpa divisi_id   : {len([r for r in rows if not r['divisi_id']])}")

    if DRY_RUN:
        print("\n  --- PREVIEW LENGKAP ---")
        for r in rows:
            status = f"divisi={r['divisi_key'] or '?TIDAK DIKENAL?'}"
            print(f"  NIK {r['nik']:6s} | {r['nama']:<45s} | {status}")
        print(f"\n[i] DRY RUN - tidak ada yang diinsert.")
        print("    Ganti DRY_RUN = False untuk import sungguhan.")
        return

    # --- INSERT ---
    print("\n[4] Insert ke DB...")
    ok = 0
    errors = []
    for r in rows:
        try:
            data = {
                "nip"       : r['nik'],
                "nama"      : r['nama'],
                "jabatan_id": JABATAN_ID,
                "divisi_id" : r['divisi_id'],
                "status"    : "aktif",
            }
            db.table("pegawai").insert(data).execute()
            ok += 1
            print(f"  [OK] {r['nama']} (NIK {r['nik']})")
        except Exception as e:
            msg = f"ERROR {r['nama']}: {e}"
            print(f"  [X] {msg}")
            errors.append(msg)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Berhasil diimport : {ok}")
    print(f"  Skip (NIK duplikat): {len(duplikat)}")
    if errors:
        print(f"  Errors            : {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    print("\n  [OK] Import selesai!")


if __name__ == "__main__":
    main()
