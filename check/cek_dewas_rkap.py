"""
Diagnostik: kenapa SPPD Dewas 1/2 tidak ter-deduct atau deduct ke bucket salah.

Cek 3 hal sekaligus:
1. struktur_rkap di tabel jabatan untuk semua jabatan DEWAN PENGAWAS
2. Apakah RKAP rows DEWAS_KETUA / DEWAS_ANGGOTA_1 / DEWAS_ANGGOTA_2 ada & terpakai berapa
3. SPPD aktif milik seluruh pegawai DEWAS → rkap_id-nya mengarah ke mana?

Penyebab umum yang diperiksa:
- jabatan masih legacy struktur_rkap = "DEWAS_ANGGOTA" → resolve_kategori_rkap
  redirect ke DEWAS_ANGGOTA_1 untuk semua anggota, termasuk DEWAS 2 (SALAH)
- Row RKAP DEWAS_ANGGOTA_2 tidak ada → rkap_id NULL → tidak ada deduct

Jalankan dari root:
    $env:PYTHONIOENCODING="utf-8"; python -u check/cek_dewas_rkap.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import get_client, resolve_kategori_rkap

db = get_client()

LOKASI_LABEL = {
    "6f7a80e0-1ca3-4e36-8d94-500bf8645efe": "Dalam Kaltim",
    "99c9f92f-972f-46d5-99d4-219b758d2cb7": "Luar Kaltim",
    "38663104-e5f5-473d-8227-640f025e595a": "Luar Negeri",
}
BULAN_LABEL = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",
               7:"Jul",8:"Agt",9:"Sep",10:"Okt",11:"Nov",12:"Des"}

def fmt_rp(n):
    if n is None: return "Rp 0"
    v = int(n)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")

print("=" * 70)
print("CEK DEWAS — RKAP DEDUCTION DIAGNOSIS (Dewas 1 & Dewas 2)")
print("=" * 70)

# ── 1. Cek jabatan DEWAN PENGAWAS di tabel jabatan ───────────────────────
print()
print("1. JABATAN — struktur_rkap untuk semua jabatan DEWAN PENGAWAS:")
print("─" * 70)
jab_res = db.table("jabatan").select("id, nama, struktur_rkap").ilike("nama", "%DEWAN PENGAWAS%").execute()
jab_dewas_all = jab_res.data or []
if jab_dewas_all:
    for j in jab_dewas_all:
        srk = j.get("struktur_rkap", "NULL")
        legacy = srk == "DEWAS_ANGGOTA"
        kategori_resolved = resolve_kategori_rkap(srk, "", "")
        mark = f"  ← ⚠️  LEGACY! resolve → '{kategori_resolved}'" if legacy else ""
        print(f"  [{j['nama']}]")
        print(f"      struktur_rkap = '{srk}'{mark}")
else:
    print("  Tidak ada jabatan DEWAN PENGAWAS ditemukan!")

# ── 2. Cek RKAP rows untuk semua kategori DEWAS ───────────────────────────
print()
print("2. RKAP ROWS — kategori DEWAS* (tahun 2026):")
print("─" * 70)
rkap_res = db.table("rkap")\
    .select("id, kategori_jabatan, lokasi_id, bulan, anggaran_awal, anggaran_terpakai, anggaran_sisa")\
    .eq("tahun", 2026)\
    .ilike("kategori_jabatan", "DEWAS%")\
    .order("kategori_jabatan").order("lokasi_id").order("bulan")\
    .execute()

rkap_rows = rkap_res.data or []
# Build index: rkap_id → row (untuk lookup di bagian 3)
rkap_by_id = {r["id"]: r for r in rkap_rows}

if rkap_rows:
    last_cat_lok = None
    for r in rkap_rows:
        cat_lok = f"{r['kategori_jabatan']} | {LOKASI_LABEL.get(r['lokasi_id'], r['lokasi_id'][:8])}"
        if cat_lok != last_cat_lok:
            print(f"\n  [{cat_lok}]")
            last_cat_lok = cat_lok
        terpakai = r.get("anggaran_terpakai") or 0
        sisa     = r.get("anggaran_sisa") or 0
        mark = "  ← UTUH (terpakai=0)" if terpakai == 0 else ""
        print(f"    {BULAN_LABEL[r['bulan']]}: awal={fmt_rp(r.get('anggaran_awal'))}  "
              f"terpakai={fmt_rp(terpakai)}  sisa={fmt_rp(sisa)}{mark}")
else:
    print("  TIDAK ADA baris RKAP kategori DEWAS% untuk tahun 2026!")

# ── 3. Cek SPPD aktif milik semua pegawai DEWAS ──────────────────────────
print()
print("3. SPPD AKTIF — semua pegawai DEWAN PENGAWAS:")
print("─" * 70)

jab_id_list = [j["id"] for j in jab_dewas_all]
if not jab_id_list:
    print("  Tidak ada jabatan ditemukan, skip.")
else:
    peg_res = db.table("pegawai").select("id, nama, jabatan_id").in_("jabatan_id", jab_id_list).execute()
    pegawai_dewas = peg_res.data or []

    # Map jabatan_id → info jabatan
    jab_map = {j["id"]: j for j in jab_dewas_all}

    if not pegawai_dewas:
        print("  Tidak ada pegawai aktif dengan jabatan DEWAS.")
    else:
        for peg in pegawai_dewas:
            jab_info = jab_map.get(peg.get("jabatan_id"), {})
            print(f"\n  Pegawai: {peg['nama']}")
            print(f"  Jabatan: {jab_info.get('nama','?')}  |  struktur_rkap = '{jab_info.get('struktur_rkap','?')}'")

            sppd_res = db.table("sppd")\
                .select("id, status, rkap_id, lokasi_id, subtotal_uang_saku, total_biaya,"
                        " visum(nomor_visum, tanggal_berangkat, tujuan)")\
                .eq("pegawai_id", peg["id"])\
                .neq("status", "cancelled")\
                .order("id")\
                .execute()
            sppd_list = sppd_res.data or []

            if not sppd_list:
                print("    (tidak ada SPPD aktif)")
                continue

            for s in sppd_list:
                visum   = s.get("visum") or {}
                lok     = LOKASI_LABEL.get(s.get("lokasi_id",""), "?")
                rkap_id = s.get("rkap_id")
                tgl     = (visum.get("tanggal_berangkat") or "")[:10]

                # Resolusi rkap_id
                if rkap_id is None:
                    rkap_label = "NULL ← ⚠️  TIDAK ADA DEDUCT!"
                elif rkap_id in rkap_by_id:
                    rk = rkap_by_id[rkap_id]
                    lok_rkap = LOKASI_LABEL.get(rk["lokasi_id"], rk["lokasi_id"][:8])
                    rkap_label = f"{rk['kategori_jabatan']} | {lok_rkap} | {BULAN_LABEL[rk['bulan']]}"
                    # Periksa apakah kategori sesuai jabatan
                    expected = resolve_kategori_rkap(jab_info.get("struktur_rkap",""), "", "")
                    if rk["kategori_jabatan"] != expected:
                        rkap_label += f"  ← ⚠️  SALAH! Harusnya '{expected}'"
                else:
                    # rkap_id ada tapi row tidak di tahun 2026 (mungkin beda tahun)
                    rk_ext = db.table("rkap").select("kategori_jabatan, lokasi_id, bulan, tahun").eq("id", rkap_id).maybe_single().execute()
                    if rk_ext.data:
                        rd = rk_ext.data
                        lok_rkap = LOKASI_LABEL.get(rd["lokasi_id"], rd["lokasi_id"][:8])
                        rkap_label = f"{rd['kategori_jabatan']} | {lok_rkap} | {BULAN_LABEL[rd['bulan']]} {rd['tahun']}"
                    else:
                        rkap_label = f"ID {rkap_id[:8]}... → NOT FOUND IN RKAP!"

                print(f"    [{s['status'].upper():10}] Visum {visum.get('nomor_visum','?')} | {tgl} | {visum.get('tujuan','?')}")
                print(f"               Lokasi SPPD  : {lok}")
                print(f"               Deduct ke    : {rkap_label}")
                print(f"               Uang saku: {fmt_rp(s.get('subtotal_uang_saku'))}  Total: {fmt_rp(s.get('total_biaya'))}")

print()
print("=" * 70)
print("SELESAI — baca OUTPUT di atas untuk temukan akar masalah:")
print("  - Bagian 1: apakah struktur_rkap jabatan sudah benar?")
print("  - Bagian 2: apakah baris RKAP DEWAS_ANGGOTA_2 ada dan ada terpakai?")
print("  - Bagian 3: SPPD aktif dewas deduct ke mana? Ada yang NULL?")
print("=" * 70)
