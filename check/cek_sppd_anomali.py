"""
Script cek anomali SPPD:
1. SPPD dengan total_biaya = 0 (kemungkinan rule tidak ditemukan saat buat)
2. SPPD dengan total_hari tidak sesuai lama_hari di visum yang bersangkutan
3. SPPD dengan rkap_id NULL (non-cancelled)
4. SPPD dengan biaya komponen tidak sesuai rule × total_hari (mismatch)

Jalankan dari folder root:  python check/cek_sppd_anomali.py

Set FIX_TOTAL_HARI = True untuk auto-fix total_hari dari visum.lama_hari.
Set FIX_BIAYA = True untuk recalculate biaya komponen dari rule × total_hari
  (juga adjust RKAP untuk SPPD non-draft yang sudah di-deduct).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from supabase import create_client
from utils.database import hitung_uang_saku, get_rule_sppd, rollback_rkap, deduct_rkap

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

FIX_TOTAL_HARI = False   # ganti True untuk auto-fix total_hari
FIX_BIAYA      = False   # ganti True untuk recalculate biaya komponen dari rule x total_hari

def fmt_rp(n):
    return f"Rp {int(n or 0):,}".replace(",", ".")

print("=" * 65)
print("CEK ANOMALI SPPD")
print("=" * 65)

# Ambil semua SPPD + visum
res = db.table("sppd")\
    .select(
        "id, nomor_sppd, pegawai_id, lokasi_id, rkap_id, total_hari, "
        "uang_harian_total, uang_makan_total, transport_lokal_total, uang_representasi_total, "
        "subtotal_uang_saku, total_hotel, total_transport, total_biaya, status, visum_id, "
        "visum(nomor_visum, lama_hari, tujuan), "
        "pegawai!sppd_pegawai_id_fkey(nama, jabatan_id, jabatan(id, nama))"
    )\
    .neq("status", "cancelled")\
    .order("created_at")\
    .execute()

sppd_list = res.data or []
print(f"\nTotal SPPD aktif: {len(sppd_list)}\n")

# --- 1. SPPD nilai 0 ---
print("-" * 65)
print("SPPD DENGAN TOTAL BIAYA = 0 (kemungkinan rule tidak ditemukan):")
print("-" * 65)
nol_list = [s for s in sppd_list if (s.get("total_biaya") or 0) == 0]
if not nol_list:
    print("  (tidak ada)")
else:
    for s in nol_list:
        peg  = (s.get("pegawai") or {}).get("nama", "?")
        jab  = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
        visum = s.get("visum") or {}
        print(f"  SPPD id={s['id'][:8]}... | {peg} ({jab})")
        print(f"    Nomor SPD : {s.get('nomor_sppd', '-')}")
        print(f"    Visum     : {visum.get('nomor_visum', '-')} - {visum.get('tujuan', '-')}")
        print(f"    Status    : {s['status']}")
        print(f"    Saku=0, Total=0 -> perlu isi manual di Supabase atau via 3_sppd.py")
        print()

# --- 2. SPPD total_hari beda dengan visum.lama_hari ---
print("-" * 65)
print("SPPD DENGAN total_hari != visum.lama_hari:")
print("-" * 65)
beda_list = []
for s in sppd_list:
    visum = s.get("visum") or {}
    lama_visum = visum.get("lama_hari")
    total_hari = s.get("total_hari")
    if lama_visum and total_hari and int(lama_visum) != int(total_hari):
        beda_list.append(s)

if not beda_list:
    print("  (tidak ada)")
else:
    for s in beda_list:
        peg   = (s.get("pegawai") or {}).get("nama", "?")
        visum = s.get("visum") or {}
        print(f"  SPPD id={s['id'][:8]}... | {peg}")
        print(f"    Nomor SPD    : {s.get('nomor_sppd', '-')}")
        print(f"    Visum        : {visum.get('nomor_visum', '-')} - {visum.get('tujuan', '-')}")
        print(f"    total_hari SPPD : {s.get('total_hari')}  ← SALAH")
        print(f"    lama_hari Visum : {visum.get('lama_hari')}  ← BENAR")
        print(f"    Status       : {s['status']}")

        if FIX_TOTAL_HARI:
            db.table("sppd").update({
                "total_hari": int(visum["lama_hari"])
            }).eq("id", s["id"]).execute()
            print(f"    [FIX] total_hari diupdate ke {visum['lama_hari']}")
        else:
            print(f"    [i] Set FIX_TOTAL_HARI=True untuk auto-fix")
        print()

if beda_list and not FIX_TOTAL_HARI:
    print(f"\n  -> Ada {len(beda_list)} SPPD yang total_hari-nya tidak sesuai visum.")
    print(f"  -> Set FIX_TOTAL_HARI = True dan jalankan ulang untuk memperbaiki.")

# --- 3. SPPD dengan rkap_id NULL ---
print("\n" + "-" * 65)
print("SPPD DENGAN rkap_id NULL (non-cancelled):")
print("-" * 65)
null_rkap = [s for s in sppd_list if not s.get("rkap_id")]
if not null_rkap:
    print("  (tidak ada)")
else:
    for s in null_rkap:
        peg   = (s.get("pegawai") or {}).get("nama", "?")
        jab   = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
        visum = s.get("visum") or {}
        print(f"  SPPD id={s['id'][:8]}... | {peg} ({jab})")
        print(f"    Nomor SPD : {s.get('nomor_sppd', '-')}")
        print(f"    Visum     : {visum.get('nomor_visum', '-')} - {visum.get('tujuan', '-')}")
        print(f"    Status    : {s['status']}")
        print(f"    Total Biaya: {fmt_rp(s.get('total_biaya'))}")
        print()
    print(f"  -> Ada {len(null_rkap)} SPPD tanpa rkap_id.")
    print(f"  -> Kemungkinan rule RKAP tidak ditemukan saat SPPD dibuat.")
    print(f"  -> Perlu di-assign manual via Supabase atau saat proses pencairan.")

# --- 4. Cek biaya mismatch (actual vs rule x total_hari) ---
print("\n" + "-" * 65)
print("SPPD DENGAN BIAYA TIDAK SESUAI RULE x total_hari:")
print("-" * 65)

mismatch_list = []
skip_no_rule  = []

for s in sppd_list:
    peg       = s.get("pegawai") or {}
    jabatan_id = peg.get("jabatan_id")
    lokasi_id  = s.get("lokasi_id")
    total_hari = s.get("total_hari") or 0

    if not jabatan_id or not lokasi_id or total_hari == 0:
        continue

    rule = get_rule_sppd(jabatan_id, lokasi_id)
    if not rule:
        skip_no_rule.append(s)
        continue

    expected = hitung_uang_saku(rule, total_hari)
    actual_subtotal = int(s.get("subtotal_uang_saku") or 0)
    exp_subtotal    = int(expected["subtotal"])

    if actual_subtotal != exp_subtotal:
        mismatch_list.append((s, rule, expected))

if skip_no_rule:
    print(f"  [skip] {len(skip_no_rule)} SPPD tidak ditemukan rule-nya (jabatan/lokasi tidak ada di rule_sppd):")
    for s in skip_no_rule:
        peg   = (s.get("pegawai") or {}).get("nama", "?")
        jab   = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
        print(f"    - {peg} ({jab}) | {s.get('nomor_sppd', '-')}")
    print()

if not mismatch_list:
    print("  (tidak ada mismatch)")
else:
    for s, rule, expected in mismatch_list:
        peg   = (s.get("pegawai") or {}).get("nama", "?")
        jab   = ((s.get("pegawai") or {}).get("jabatan") or {}).get("nama", "?")
        visum = s.get("visum") or {}
        old_subtotal = int(s.get("subtotal_uang_saku") or 0)
        new_subtotal = int(expected["subtotal"])
        old_total    = int(s.get("total_biaya") or 0)
        old_non_saku = old_total - old_subtotal
        new_total    = new_subtotal + old_non_saku

        print(f"  SPPD id={s['id'][:8]}... | {peg} ({jab})")
        print(f"    Nomor SPD      : {s.get('nomor_sppd', '-')}")
        print(f"    Visum          : {visum.get('nomor_visum', '-')} - {visum.get('tujuan', '-')}")
        print(f"    Status         : {s['status']}")
        print(f"    total_hari     : {s.get('total_hari')}")
        print(f"    Subtotal saku  : {fmt_rp(old_subtotal)}  ->  {fmt_rp(new_subtotal)}")
        print(f"    Total biaya    : {fmt_rp(old_total)}  ->  {fmt_rp(new_total)}")
        if s.get("rkap_id") and s.get("status") != "draft":
            selisih = old_total - new_total
            print(f"    RKAP rollback  : {fmt_rp(selisih)}  (akan dikembalikan)")

        if FIX_BIAYA:
            if s.get("status") == "completed":
                print(f"    [skip] Status completed - data historis, tidak diubah.")
            else:
                old_total_biaya = int(s.get("total_biaya") or 0)
                old_non_saku    = old_total_biaya - int(s.get("subtotal_uang_saku") or 0)
                new_total_biaya = new_subtotal + old_non_saku

                db.table("sppd").update({
                    "uang_harian_total":       int(expected["uang_harian"]),
                    "uang_makan_total":        int(expected["uang_makan"]),
                    "transport_lokal_total":   int(expected["transport_lokal"]),
                    "uang_representasi_total": int(expected["uang_rep"]),
                    "subtotal_uang_saku":      new_subtotal,
                    "total_biaya":             new_total_biaya,
                }).eq("id", s["id"]).execute()
                print(f"    [FIX] Biaya komponen diupdate. total_biaya: {fmt_rp(old_total_biaya)} -> {fmt_rp(new_total_biaya)}")

                if s.get("rkap_id") and s.get("status") != "draft":
                    selisih = old_total_biaya - new_total_biaya
                    if selisih > 0:
                        rollback_rkap(s["rkap_id"], selisih)
                        print(f"    [FIX] RKAP rollback {fmt_rp(selisih)} berhasil.")
                    elif selisih < 0:
                        deduct_rkap(s["rkap_id"], abs(selisih))
                        print(f"    [FIX] RKAP deduct tambahan {fmt_rp(abs(selisih))} berhasil.")
        else:
            if s.get("status") == "completed":
                print(f"    [i] Status completed - data historis, FIX_BIAYA akan skip ini.")
            else:
                print(f"    [i] Set FIX_BIAYA=True untuk auto-fix")
        print()

    if mismatch_list and not FIX_BIAYA:
        print(f"  -> Ada {len(mismatch_list)} SPPD biaya tidak sesuai rule x total_hari.")
        print(f"  -> Set FIX_BIAYA = True dan jalankan ulang untuk memperbaiki.")

print("\n" + "=" * 65)
print("Selesai.")
