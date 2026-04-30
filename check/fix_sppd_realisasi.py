"""
Script untuk fix nilai uang saku SPPD berstatus realisasi/completed.

Gunakan HANYA jika tarif/jabatan yang dipakai saat pembuatan SPPD terbukti salah
dan tidak bisa diperbaiki dari UI (karena UI hanya support draft & pencairan).

Untuk realisasi  : uang saku di-recalculate + RKAP di-adjust (rollback lama → deduct baru)
Untuk completed  : uang saku di-recalculate, RKAP TIDAK di-adjust (selisih diabsorb)

Cara pakai:
  1. Set SPPD_ID ke UUID SPPD yang akan diperbaiki
  2. Jalankan dengan DRY_RUN = True untuk lihat preview dulu
  3. Jika oke, set DRY_RUN = False lalu jalankan lagi

Jalankan dari folder check/:
  cd check && python fix_sppd_realisasi.py
  atau dari root:
  python check/fix_sppd_realisasi.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from utils.database import (
    get_client, get_pegawai_by_id, get_rule_sppd,
    hitung_uang_saku, rollback_rkap, deduct_rkap, update_rekap_spd,
)

# ── KONFIGURASI ──────────────────────────────────────────
SPPD_ID = "isi dengan UUID SPPD yang akan di-fix"   # Ganti dengan UUID SPPD yang akan di-fix
DRY_RUN = True                        # Set False untuk benar-benar update DB
# ─────────────────────────────────────────────────────────


def fmt_rp(n):
    return f"Rp {int(n):,}".replace(",", ".")


def fix_sppd(sppd_id: str, dry_run: bool = True):
    db = get_client()

    # Ambil data SPPD
    res = db.table("sppd")\
        .select("id, status, pegawai_id, lokasi_id, total_hari,"
                " uang_harian_total, uang_makan_total, transport_lokal_total,"
                " uang_representasi_total, subtotal_uang_saku, total_hotel,"
                " total_biaya, spd_id, rkap_id,"
                " pegawai!sppd_pegawai_id_fkey(nama),"
                " visum(nomor_visum, tujuan)")\
        .eq("id", sppd_id).single().execute()

    if not res.data:
        print(f"❌ SPPD tidak ditemukan: {sppd_id}")
        return

    sppd = res.data
    nama_pegawai  = (sppd.get("pegawai") or {}).get("nama", "-")
    nomor_visum   = (sppd.get("visum") or {}).get("nomor_visum", "-")
    tujuan        = (sppd.get("visum") or {}).get("tujuan", "-")

    print(f"\n{'='*60}")
    print(f"SPPD ID     : {sppd_id}")
    print(f"Pegawai     : {nama_pegawai}")
    print(f"Visum       : {nomor_visum} — {tujuan}")
    print(f"Status      : {sppd['status'].upper()}")
    print(f"Total Hari  : {sppd['total_hari']}")
    print(f"\n[NILAI LAMA]")
    print(f"  Uang Harian    : {fmt_rp(sppd.get('uang_harian_total') or 0)}")
    print(f"  Uang Makan     : {fmt_rp(sppd.get('uang_makan_total') or 0)}")
    print(f"  Transport Lokal: {fmt_rp(sppd.get('transport_lokal_total') or 0)}")
    print(f"  Uang Representasi: {fmt_rp(sppd.get('uang_representasi_total') or 0)}")
    print(f"  Subtotal Uang Saku: {fmt_rp(sppd.get('subtotal_uang_saku') or 0)}")
    print(f"  Total Hotel    : {fmt_rp(sppd.get('total_hotel') or 0)}")
    print(f"  Total Biaya    : {fmt_rp(sppd.get('total_biaya') or 0)}")

    # Ambil pegawai + rule terkini
    pegawai = get_pegawai_by_id(sppd["pegawai_id"])
    if not pegawai:
        print("❌ Pegawai tidak ditemukan di DB")
        return

    jabatan_id = pegawai.get("jabatan_id")
    jabatan_nama = (pegawai.get("jabatan") or {}).get("nama", "-")
    lokasi_id  = sppd["lokasi_id"]
    total_hari = sppd["total_hari"] or 1

    rule = None
    if jabatan_id and lokasi_id:
        try:
            rule = get_rule_sppd(jabatan_id, lokasi_id)
        except Exception as e:
            print(f"⚠️ Gagal ambil rule: {e}")

    print(f"\n[RULE TERKINI]")
    print(f"  Jabatan : {jabatan_nama}")
    if rule:
        print(f"  Uang Saku/hari  : {fmt_rp(rule.get('uang_saku') or 0)}")
        print(f"  Uang Makan/hari : {fmt_rp(rule.get('uang_makan') or 0)}")
        print(f"  Transport/hari  : {fmt_rp(rule.get('transport_lokal') or 0)}")
        print(f"  Representasi/hr : {fmt_rp(rule.get('uang_representasi') or 0)}")
        calc = hitung_uang_saku(rule, total_hari)
    else:
        print(f"  ⚠️ Rule tidak ditemukan — semua biaya akan di-set ke 0")
        calc = {"uang_harian": 0, "uang_makan": 0,
                "transport_lokal": 0, "uang_rep": 0, "subtotal": 0}

    subtotal_baru = calc["subtotal"]
    subtotal_lama = sppd.get("subtotal_uang_saku") or 0
    selisih = subtotal_baru - subtotal_lama
    # Pertahankan var costs (hotel + transport + biaya lain); hanya uang saku yang berubah
    var_costs = (sppd.get("total_biaya") or 0) - (sppd.get("subtotal_uang_saku") or 0)
    total_biaya_baru = subtotal_baru + max(var_costs, 0)

    print(f"\n[NILAI BARU]")
    print(f"  Uang Harian    : {fmt_rp(calc['uang_harian'])}")
    print(f"  Uang Makan     : {fmt_rp(calc['uang_makan'])}")
    print(f"  Transport Lokal: {fmt_rp(calc['transport_lokal'])}")
    print(f"  Uang Representasi: {fmt_rp(calc['uang_rep'])}")
    print(f"  Subtotal Uang Saku: {fmt_rp(subtotal_baru)}")
    print(f"  Var Costs (hotel+transport+lain, tidak berubah): {fmt_rp(max(var_costs, 0))}")
    print(f"  Total Biaya Baru: {fmt_rp(total_biaya_baru)}")
    print(f"\n  Selisih uang saku: {fmt_rp(selisih)}")

    rkap_id = sppd.get("rkap_id")
    if sppd["status"] == "realisasi" and rkap_id and selisih != 0:
        print(f"\n[RKAP] Akan di-adjust: rollback {fmt_rp(subtotal_lama)} → deduct {fmt_rp(subtotal_baru)}")
    elif sppd["status"] == "completed":
        print(f"\n[RKAP] Status COMPLETED — RKAP TIDAK di-adjust (selisih diabsorb)")
    else:
        print(f"\n[RKAP] Tidak ada perubahan RKAP")

    if dry_run:
        print(f"\n{'='*60}")
        print("⚠️  DRY RUN — tidak ada yang diubah di DB")
        print("   Set DRY_RUN = False untuk benar-benar update")
        return

    # ── Eksekusi update ──────────────────────────────────
    if sppd["status"] == "realisasi" and rkap_id and selisih != 0:
        rollback_rkap(rkap_id, subtotal_lama)
        deduct_rkap(rkap_id, subtotal_baru)
        print("\n✅ RKAP di-adjust")

    db.table("sppd").update({
        "uang_harian_total":       calc["uang_harian"],
        "uang_makan_total":        calc["uang_makan"],
        "transport_lokal_total":   calc["transport_lokal"],
        "uang_representasi_total": calc["uang_rep"],
        "subtotal_uang_saku":      subtotal_baru,
        "total_biaya":             total_biaya_baru,
    }).eq("id", sppd_id).execute()
    print("✅ SPPD berhasil diupdate")

    if sppd.get("spd_id"):
        update_rekap_spd(sppd["spd_id"])
        print("✅ Rekap SPD diupdate")

    print(f"\n{'='*60}")
    print("SELESAI")


if __name__ == "__main__":
    if SPPD_ID == "ISI-UUID-SPPD-DI-SINI":
        print("❌ Isi SPPD_ID terlebih dahulu di bagian KONFIGURASI script ini")
    else:
        fix_sppd(SPPD_ID, dry_run=DRY_RUN)
