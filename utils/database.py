from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import date
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── PEGAWAI ───────────────────────────────────────────
def get_all_pegawai():
    db = get_client()
    
    res_divisi = db.table("divisi").select("id, nama, parent_id, bidang").execute()
    divisi_map = {d["id"]: d for d in res_divisi.data}
    
    res = db.table("pegawai")\
        .select("*, divisi_id, divisi(id, nama, parent_id, bidang), jabatan(nama, struktur_rkap, level)")\
        .eq("status", "aktif")\
        .order("nama")\
        .execute()
    
    for p in res.data:
        div = p.get("divisi")
        if div:
            if div.get("bidang"):
                p["bidang_resolved"] = div["bidang"]
            elif div.get("parent_id"):
                parent = divisi_map.get(div["parent_id"])
                p["bidang_resolved"] = parent["bidang"] if parent else None
            else:
                p["bidang_resolved"] = None
    
    return res.data

def get_pegawai_by_jabatan_nama(nama_jabatan):
    """Ambil pegawai aktif pertama yang jabatannya = nama_jabatan (untuk TTD)."""
    db = get_client()
    res = db.table("pegawai")\
        .select("nama, jabatan!inner(nama)")\
        .eq("jabatan.nama", nama_jabatan)\
        .eq("status", "aktif")\
        .limit(1)\
        .execute()
    return res.data[0] if res.data else None

def get_pegawai_by_id(pegawai_id):
    db = get_client()
    res = db.table("pegawai")\
        .select("*, divisi(nama, parent_id, bidang), jabatan(nama, struktur_rkap, level)")\
        .eq("id", pegawai_id)\
        .single()\
        .execute()
    
    if not res.data:
        return None

    # Resolve bidang
    p = res.data
    div = p.get("divisi")
    if div:
        if div.get("bidang"):
            p["bidang_resolved"] = div["bidang"]
        elif div.get("parent_id"):
            db2 = get_client()
            res_parent = db2.table("divisi").select("bidang").eq("id", div["parent_id"]).single().execute()
            p["bidang_resolved"] = res_parent.data["bidang"] if res_parent.data else None
        else:
            p["bidang_resolved"] = None

    return p

# ─── DIVISI ────────────────────────────────────────────
def get_all_divisi():
    db = get_client()
    res = db.table("divisi")\
        .select("*")\
        .eq("status", "aktif")\
        .order("nama")\
        .execute()
    return res.data

# ─── JABATAN ───────────────────────────────────────────
def get_all_jabatan():
    db = get_client()
    res = db.table("jabatan")\
        .select("*")\
        .eq("status", "aktif")\
        .order("nama")\
        .execute()
    return res.data

# ─── RKAP ──────────────────────────────────────────────
def get_rkap_summary(tahun: int = None):
    db = get_client()
    if tahun is None:
        tahun = date.today().year
    res = db.table("rkap")\
        .select("*")\
        .eq("tahun", tahun)\
        .execute()
    return res.data

# ─── VISUM ─────────────────────────────────────────────
def get_all_visum():
    db = get_client()
    res = db.table("visum")\
        .select("*")\
        .order("created_at", desc=True)\
        .execute()
    return res.data

# ─── SPPD ──────────────────────────────────────────────
def get_all_sppd():
    db = get_client()
    res = db.table("sppd")\
        .select("*, pegawai(nama), visum(nomor_visum, tujuan), rkap(kategori)")\
        .order("created_at", desc=True)\
        .execute()
    return res.data

def get_sppd_stats():
    db = get_client()
    res = db.table("sppd").select("status").execute()
    data = res.data
    stats = {
        "total": len(data),
        "draft": sum(1 for d in data if d["status"] == "draft"),
        "pencairan": sum(1 for d in data if d["status"] == "pencairan"),
        "dalam_perjalanan": sum(1 for d in data if d["status"] == "dalam_perjalanan"),
        "realisasi": sum(1 for d in data if d["status"] == "realisasi"),
        "closed": sum(1 for d in data if d["status"] == "closed"),
    }
    return stats

# ─── LOKASI HELPER ─────────────────────────────────────
KOTA_DALAM_KALTIM = {
    "samarinda", "balikpapan", "bontang", "kutai kartanegara",
    "berau", "paser", "penajam paser utara", "mahakam ulu",
    "kutai timur", "kutai barat",
    "tenggarong", "sangatta", "tanjung redeb", "tanah grogot",
    "penajam", "long bagun", "sendawar", "ujoh bilang",
    "ikn", "ibu kota nusantara", "nusantara",
}

LOKASI_DALAM = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"
LOKASI_LUAR  = "99c9f92f-972f-46d5-99d4-219b758d2cb7"
LOKASI_LN    = "38663104-e5f5-473d-8227-640f025e595a"

def detect_lokasi(kota_tujuan: str) -> dict:
    kota_lower = kota_tujuan.strip().lower()
    
    if kota_lower in KOTA_DALAM_KALTIM:
        return {
            "lokasi_nama": "Dalam Kaltim (Dalam Provinsi)",
            "lokasi_id": LOKASI_DALAM,
            "confidence": "auto"
        }
    elif any(x in kota_lower for x in ["luar negeri", "malaysia", "singapore", "brunei"]):
        return {
            "lokasi_nama": "Luar Negeri",
            "lokasi_id": LOKASI_LN,
            "confidence": "auto"
        }
    elif kota_lower:
        return {
            "lokasi_nama": "Luar Kaltim (Luar Provinsi)",
            "lokasi_id": LOKASI_LUAR,
            "confidence": "auto"
        }
    else:
        return {
            "lokasi_nama": "Luar Kaltim (Luar Provinsi)",
            "lokasi_id": LOKASI_LUAR,
            "confidence": "manual"
        }

# ─── MAPPING ───────────────────────────────────────────
JABATAN_RULE_MAP = {
    "DIREKTUR UTAMA": "DIREKTUR UTAMA",
    "DIREKTUR BIDANG UMUM": "DIREKTUR BIDANG",
    "DIREKTUR OPERASIONAL": "DIREKTUR BIDANG",
    "DIREKTUR TEKNIK": "DIREKTUR BIDANG",
    "MANAJER": "MANAJER",
    "TENAGA AHLI BIDANG MANAJEMEN": "MANAJER",
    "TENAGA AHLI BIDANG KEHUMASAN": "MANAJER",
    "STAF AHLI BIDANG HUKUM DAN ASET PERUSAHAAN": "SUPERVISOR",
    "SUPERVISOR": "SUPERVISOR",
    "KETUA REGU": "SUPERVISOR",
    "STAF PELAKSANA": "STAF PELAKSANA",
    "TIM PENGADAAN": "STAF PELAKSANA",
    "BENDAHARA PEMBANTU": "STAF PELAKSANA",
    "CALON PEGAWAI": "STAF PELAKSANA",
    "STAF PKWT":     "STAF PELAKSANA",
    "TAMU SETARA DIREKTUR BIDANG": "TAMU DIREKTUR BIDANG",
    "TAMU SETARA MANAJER":         "MANAJER",
    "TAMU SETARA SUPERVISOR":      "SUPERVISOR",
    "TAMU SETARA STAF":            "STAF PELAKSANA",
    "KETUA DEWAN PENGAWAS":    "DIREKTUR UTAMA",
    "ANGGOTA DEWAN PENGAWAS":  "DIREKTUR BIDANG",
    "ANGGOTA DEWAN PENGAWAS 1": "DIREKTUR BIDANG",
    "ANGGOTA DEWAN PENGAWAS 2": "DIREKTUR BIDANG",
}

# Urutan sort untuk Rekap SPD (level jabatan, makin kecil = makin atas)
JABATAN_SORT_ORDER = {
    "DIREKTUR UTAMA": 1,
    "DIREKTUR BIDANG UMUM": 2,
    "DIREKTUR OPERASIONAL": 2,
    "DIREKTUR TEKNIK": 2,
    "KETUA DEWAN PENGAWAS":    3,
    "ANGGOTA DEWAN PENGAWAS":  4,
    "ANGGOTA DEWAN PENGAWAS 1": 4,
    "ANGGOTA DEWAN PENGAWAS 2": 4,
    "MANAJER": 5,
    "TENAGA AHLI BIDANG MANAJEMEN": 5,
    "TENAGA AHLI BIDANG KEHUMASAN": 5,
    "STAF AHLI BIDANG HUKUM DAN ASET PERUSAHAAN": 5,
    "SUPERVISOR": 6,
    "KETUA REGU": 6,
    "STAF PELAKSANA": 7,
    "TIM PENGADAAN": 7,
    "BENDAHARA PEMBANTU": 7,
    "CALON PEGAWAI": 8,
    "STAF PKWT":     8,
}

def get_rule_sppd(jabatan_id: str, lokasi_id: str):
    db = get_client()
    
    res_jab = db.table("jabatan")\
        .select("nama")\
        .eq("id", jabatan_id)\
        .single()\
        .execute()
    
    if not res_jab.data:
        return None
    
    nama_jabatan = res_jab.data["nama"].upper().strip()
    nama_rule = JABATAN_RULE_MAP.get(nama_jabatan)
    
    if not nama_rule:
        return None
    
    res = db.table("rule_sppd")\
        .select("*")\
        .eq("jabatan", nama_rule)\
        .eq("lokasi_id", lokasi_id)\
        .eq("status", "aktif")\
        .single()\
        .execute()
    
    return res.data

# ─── RKAP DEDUCT ───────────────────────────────────────
def deduct_rkap(rkap_id: str, jumlah: int):
    db = get_client()
    res = db.table("rkap").select("anggaran_terpakai, anggaran_sisa").eq("id", rkap_id).single().execute()
    if not res.data:
        return False
    terpakai_baru = res.data["anggaran_terpakai"] + jumlah
    sisa_baru     = res.data["anggaran_sisa"] - jumlah
    db.table("rkap").update({
        "anggaran_terpakai": terpakai_baru,
        "anggaran_sisa":     sisa_baru,
    }).eq("id", rkap_id).execute()
    return True

def rollback_rkap(rkap_id: str, jumlah: int):
    db = get_client()
    res = db.table("rkap").select("anggaran_terpakai, anggaran_sisa").eq("id", rkap_id).single().execute()
    if not res.data:
        return False
    terpakai_baru = res.data["anggaran_terpakai"] - jumlah
    sisa_baru     = res.data["anggaran_sisa"] + jumlah
    db.table("rkap").update({
        "anggaran_terpakai": terpakai_baru,
        "anggaran_sisa":     sisa_baru,
    }).eq("id", rkap_id).execute()
    return True

# ─── REALOKASI RKAP ────────────────────────────────────

# Mapping kategori_jabatan RKAP → nama jabatan di tabel rule_sppd
KATEGORI_TO_RULE_JABATAN = {
    "DEWAS_KETUA":               "DIREKTUR UTAMA",
    "DEWAS_ANGGOTA_1":           "DIREKTUR BIDANG",
    "DEWAS_ANGGOTA_2":           "DIREKTUR BIDANG",
    "DIRUT":                     "DIREKTUR UTAMA",
    "DIRUM":                     "DIREKTUR BIDANG",
    "DIRTEK":                    "DIREKTUR BIDANG",
    "DIROPS":                    "DIREKTUR BIDANG",
    "ADM_MANAJER":               "MANAJER",
    "TEKNIK_MANAJER":            "MANAJER",
    "ADM_SUPERVISOR":            "SUPERVISOR",
    "TEKNIK_SUPERVISOR":         "SUPERVISOR",
    "ADM_STAF_PELAKSANA":        "STAF PELAKSANA",
    "TEKNIK_STAF_PELAKSANA":     "STAF PELAKSANA",
    "bantuan_sppd":              "STAF PELAKSANA",
    "bantuan_sppd_luar_negeri":  "STAF PELAKSANA",
}

# Minimum hari per lokasi untuk 1 trip yang valid
MIN_HARI_LOKASI = {
    LOKASI_DALAM: 1,
    LOKASI_LUAR:  3,
    LOKASI_LN:    4,
}

def get_all_rule_rates() -> dict:
    """Return {(rule_jabatan, lokasi_id): {uang_harian, plafon_pesawat, plafon_hotel}} dari semua rule aktif."""
    db = get_client()
    res = db.table("rule_sppd").select(
        "jabatan, lokasi_id, uang_saku, uang_makan, transport_lokal, uang_representasi, plafon_pesawat, plafon_hotel"
    ).eq("status", "aktif").execute()
    result = {}
    for r in (res.data or []):
        key = (r["jabatan"], r["lokasi_id"])
        result[key] = {
            "uang_harian":    int(r.get("uang_saku") or 0) + int(r.get("uang_makan") or 0)
                            + int(r.get("transport_lokal") or 0) + int(r.get("uang_representasi") or 0),
            "plafon_pesawat": int(r.get("plafon_pesawat") or 0),
            "plafon_hotel":   int(r.get("plafon_hotel") or 0),
        }
    return result

def get_rkap_rows_tahun(tahun: int) -> list:
    """Semua row RKAP untuk 1 tahun, lengkap dengan anggaran_pagu."""
    db = get_client()
    res = db.table("rkap")\
        .select("id, kategori_jabatan, lokasi_id, bulan, tahun, anggaran_pagu, anggaran_awal, anggaran_terpakai, anggaran_sisa")\
        .eq("tahun", tahun)\
        .execute()
    return res.data or []

def get_realokasi_history(tahun: int) -> list:
    """History realokasi untuk tahun tertentu, urut terbaru dulu."""
    db = get_client()
    res = db.table("rkap_realokasi")\
        .select("*")\
        .gte("tanggal", f"{tahun}-01-01")\
        .lte("tanggal", f"{tahun}-12-31")\
        .order("created_at", desc=True)\
        .execute()
    return res.data or []

def eksekusi_realokasi(
    ke_rkap_id: str,
    sumber_items: list,
    keterangan: str,
    tanggal: str,
) -> tuple:
    """
    Eksekusi realokasi RKAP. Untuk setiap item sumber:
      - kurangi anggaran_awal + anggaran_sisa dari row sumber
      - tambah anggaran_awal + anggaran_sisa ke row tujuan
      - insert record audit trail ke rkap_realokasi
    Returns (True, "") atau (False, pesan_error).
    """
    import uuid as _uuid
    db = get_client()
    batch_id = str(_uuid.uuid4())
    total = sum(item["jumlah"] for item in sumber_items)

    # Validasi fresh: sisa sumber masih mencukupi
    for item in sumber_items:
        r = db.table("rkap")\
            .select("anggaran_sisa, kategori_jabatan, bulan")\
            .eq("id", item["dari_rkap_id"]).single().execute()
        if not r.data:
            return False, "RKAP sumber tidak ditemukan."
        if r.data["anggaran_sisa"] < item["jumlah"]:
            bln = r.data["bulan"]
            return False, (
                f"Sisa {r.data['kategori_jabatan']} bulan {bln} tidak cukup "
                f"(sisa Rp {r.data['anggaran_sisa']:,}, perlu Rp {item['jumlah']:,})."
            )

    # Kurangi anggaran_awal + sisa dari setiap sumber
    for item in sumber_items:
        r = db.table("rkap").select("anggaran_awal, anggaran_sisa")\
            .eq("id", item["dari_rkap_id"]).single().execute()
        db.table("rkap").update({
            "anggaran_awal": r.data["anggaran_awal"] - item["jumlah"],
            "anggaran_sisa": r.data["anggaran_sisa"] - item["jumlah"],
        }).eq("id", item["dari_rkap_id"]).execute()

    # Tambah ke tujuan
    r = db.table("rkap").select("anggaran_awal, anggaran_sisa")\
        .eq("id", ke_rkap_id).single().execute()
    if not r.data:
        return False, "RKAP tujuan tidak ditemukan."
    db.table("rkap").update({
        "anggaran_awal": r.data["anggaran_awal"] + total,
        "anggaran_sisa": r.data["anggaran_sisa"] + total,
    }).eq("id", ke_rkap_id).execute()

    # Insert audit trail (satu record per sumber → satu tujuan)
    db.table("rkap_realokasi").insert([
        {
            "batch_id": batch_id,
            "tanggal": tanggal,
            "dari_rkap_id": item["dari_rkap_id"],
            "ke_rkap_id": ke_rkap_id,
            "jumlah_token": item["jumlah_token"],
            "hari_per_token": item["hari_per_token"],
            "rate_per_hari": item["rate_per_hari"],
            "jumlah": item["jumlah"],
            "keterangan": keterangan,
        }
        for item in sumber_items
    ]).execute()

    return True, ""


def eksekusi_realokasi_multi(
    moves: list,
    keterangan: str,
    tanggal: str,
) -> tuple:
    """
    Eksekusi realokasi multi-pasang (banyak dari→ke) dalam satu batch.
    moves: [{dari_rkap_id, ke_rkap_id, jumlah_token, hari_per_token, rate_per_hari, jumlah}]
    Setiap move bisa punya tujuan berbeda. Semua share satu batch_id.
    """
    import uuid as _uuid
    db = get_client()
    batch_id = str(_uuid.uuid4())

    # Aggregate total deduction per source untuk validasi
    source_totals = {}
    for move in moves:
        source_totals[move["dari_rkap_id"]] = (
            source_totals.get(move["dari_rkap_id"], 0) + move["jumlah"]
        )

    # Validasi: setiap sumber harus punya cukup sisa (aggregate)
    for rkap_id, total_deduct in source_totals.items():
        r = db.table("rkap").select("anggaran_sisa, kategori_jabatan, bulan")\
            .eq("id", rkap_id).single().execute()
        if not r.data:
            return False, "RKAP sumber tidak ditemukan."
        if r.data["anggaran_sisa"] < total_deduct:
            bln = r.data["bulan"]
            return False, (
                f"Sisa {r.data['kategori_jabatan']} bulan {bln} tidak cukup "
                f"(sisa Rp {r.data['anggaran_sisa']:,}, perlu Rp {total_deduct:,})."
            )

    # Hitung net delta per rkap_id (sumber dikurangi, tujuan ditambah)
    net_changes = {}
    for move in moves:
        net_changes[move["dari_rkap_id"]] = net_changes.get(move["dari_rkap_id"], 0) - move["jumlah"]
        net_changes[move["ke_rkap_id"]] = net_changes.get(move["ke_rkap_id"], 0) + move["jumlah"]

    # Terapkan net changes ke setiap rkap_id yang terdampak
    for rkap_id, delta in net_changes.items():
        r = db.table("rkap").select("anggaran_awal, anggaran_sisa")\
            .eq("id", rkap_id).single().execute()
        if not r.data:
            return False, f"RKAP {rkap_id[:8]} tidak ditemukan."
        db.table("rkap").update({
            "anggaran_awal": r.data["anggaran_awal"] + delta,
            "anggaran_sisa": r.data["anggaran_sisa"] + delta,
        }).eq("id", rkap_id).execute()

    # Insert audit trail — satu record per move, semua share batch_id
    db.table("rkap_realokasi").insert([
        {
            "batch_id": batch_id,
            "tanggal": tanggal,
            "dari_rkap_id": move["dari_rkap_id"],
            "ke_rkap_id": move["ke_rkap_id"],
            "jumlah_token": move["jumlah_token"],
            "hari_per_token": move["hari_per_token"],
            "rate_per_hari": move["rate_per_hari"],
            "jumlah": move["jumlah"],
            "keterangan": keterangan,
        }
        for move in moves
    ]).execute()

    return True, ""


# ─── CARI RKAP ID ──────────────────────────────────────
def get_rkap_id(struktur_rkap: str, lokasi_id: str, bulan: int, tahun: int):
    db = get_client()
    res = db.table("rkap")\
        .select("id")\
        .eq("kategori_jabatan", struktur_rkap)\
        .eq("lokasi_id", lokasi_id)\
        .eq("bulan", bulan)\
        .eq("tahun", tahun)\
        .execute()
    return res.data[0]["id"] if res.data else None

# ─── HELPER: KALKULASI UANG SAKU ───────────────────────
def hitung_uang_saku(rule: dict, total_hari: int) -> dict:
    uang_harian    = (rule.get("uang_saku") or 0) * total_hari
    uang_makan     = (rule.get("uang_makan") or 0) * total_hari
    transport_lokal = (rule.get("transport_lokal") or 0) * total_hari
    uang_rep       = (rule.get("uang_representasi") or 0) * total_hari
    subtotal       = uang_harian + uang_makan + transport_lokal + uang_rep
    return {
        "uang_harian": uang_harian,
        "uang_makan": uang_makan,
        "transport_lokal": transport_lokal,
        "uang_rep": uang_rep,
        "subtotal": subtotal
    }

LOKASI_LN_ID     = "38663104-e5f5-473d-8227-640f025e595a"
LOKASI_BANTUAN_ID = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"  # lokasi_id yg dipakai RKAP bantuan_sppd (Dalam Kaltim sebagai bucket non-LN)

def resolve_kategori_rkap(struktur_rkap: str, bidang_resolved: str, lokasi_id: str = "") -> str:
    """Mapping struktur_rkap + bidang + lokasi → kategori_jabatan di tabel RKAP."""
    if struktur_rkap == "MANAJER":
        return "ADM_MANAJER" if bidang_resolved == "Administrasi" else "TEKNIK_MANAJER"
    elif struktur_rkap == "SUPERVISOR":
        return "ADM_SUPERVISOR" if bidang_resolved == "Administrasi" else "TEKNIK_SUPERVISOR"
    elif struktur_rkap == "STAF_PELAKSANA":
        return "ADM_STAF_PELAKSANA" if bidang_resolved == "Administrasi" else "TEKNIK_STAF_PELAKSANA"
    elif struktur_rkap == "BANTUAN":
        return "bantuan_sppd_luar_negeri" if lokasi_id == LOKASI_LN_ID else "bantuan_sppd"
    elif struktur_rkap == "DEWAS_ANGGOTA":
        # Legacy fallback — kalau jabatan belum dipisah jadi DEWAS_ANGGOTA_1/2
        return "DEWAS_ANGGOTA_1"
    else:
        # Pass-through: DIRUT, DIRUM, DIRTEK, DIROPS, DEWAS_KETUA,
        #               DEWAS_ANGGOTA_1, DEWAS_ANGGOTA_2, dll.
        return struktur_rkap

# ══════════════════════════════════════════════════════
# AUTO SPPD — function baru session 7
# ══════════════════════════════════════════════════════

BULAN_ROMAWI = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]

def _generate_nomor_spd(tanggal: date) -> str:
    """Generate nomor SPD berikutnya (MAX+1) untuk tahun tertentu."""
    db = get_client()
    tahun = tanggal.year
    bulan = BULAN_ROMAWI[tanggal.month - 1]
    res = db.table("spd").select("nomor_spd").like("nomor_spd", f"%/{tahun}-O").execute()
    if res.data:
        max_urutan = max(
            int(s["nomor_spd"].split("/")[0])
            for s in res.data
            if s["nomor_spd"].split("/")[0].isdigit()
        )
        urutan = max_urutan + 1
    else:
        urutan = 1
    return f"{urutan:04d}/1421002/10a-I/{bulan}/{tahun}-O"


def create_spd_baru(tanggal: date) -> dict:
    """Buat SPD baru tanpa visum_id (pre-create sebelum visum)."""
    db = get_client()
    nomor_spd = _generate_nomor_spd(tanggal)
    res = db.table("spd").insert({
        "nomor_spd": nomor_spd,
        "tanggal_spd": str(tanggal),
        "status": "draft"
    }).execute()
    return res.data[0]


def get_spd_by_id(spd_id: str) -> dict:
    """Ambil satu SPD by id."""
    db = get_client()
    res = db.table("spd").select("*").eq("id", spd_id).single().execute()
    return res.data


def get_spd_list_semua() -> list:
    """Ambil semua SPD, urut terbaru dulu — untuk dropdown."""
    db = get_client()
    res = db.table("spd").select("id, nomor_spd, tanggal_spd, status")\
        .order("tanggal_spd", desc=True).execute()
    return res.data or []


def get_or_create_spd(visum_id: str, tanggal: date) -> dict:
    """Legacy: Ambil SPD yang sudah ada untuk visum ini, kalau belum ada buat baru.
    Dipertahankan untuk backward-compatibility (import script lama, dsb).
    """
    db = get_client()
    res = db.table("spd").select("*").eq("visum_id", visum_id).execute()
    if res.data:
        return res.data[0]
    nomor_spd = _generate_nomor_spd(tanggal)
    res_insert = db.table("spd").insert({
        "nomor_spd": nomor_spd,
        "visum_id": visum_id,
        "tanggal_spd": str(tanggal),
        "status": "draft"
    }).execute()
    return res_insert.data[0]


def buat_sppd_untuk_pegawai(pegawai_id: str, visum: dict, spd: dict, lokasi_id: str) -> dict:
    """
    Buat 1 record SPPD untuk 1 pegawai berdasarkan visum & SPD.
    Return: {"success": bool, "pesan": str, "sppd_id": str|None}
    """
    db = get_client()

    # Cek apakah SPPD sudah ada untuk pegawai ini di visum ini (non-cancelled)
    res_cek = db.table("sppd")\
        .select("id")\
        .eq("visum_id", visum["id"])\
        .eq("pegawai_id", pegawai_id)\
        .neq("status", "cancelled")\
        .execute()
    if res_cek.data:
        return {"success": False, "pesan": "SPPD sudah ada", "sppd_id": res_cek.data[0]["id"]}

    # Ambil data pegawai lengkap
    pegawai = get_pegawai_by_id(pegawai_id)
    if not pegawai:
        return {"success": False, "pesan": "Pegawai tidak ditemukan", "sppd_id": None}

    jabatan_id = pegawai.get("jabatan_id")
    total_hari = visum.get("lama_hari", 1)

    # Ambil rule SPPD
    rule = None
    if jabatan_id and lokasi_id:
        try:
            rule = get_rule_sppd(jabatan_id, lokasi_id)
        except:
            rule = None

    # Hitung uang saku (0 kalau rule tidak ditemukan)
    if rule:
        calc = hitung_uang_saku(rule, total_hari)
    else:
        calc = {"uang_harian": 0, "uang_makan": 0,
                "transport_lokal": 0, "uang_rep": 0, "subtotal": 0}

    # Cari rkap_id
    struktur = (pegawai.get("jabatan") or {}).get("struktur_rkap", "")
    bidang = pegawai.get("bidang_resolved", "") or ""
    kategori = resolve_kategori_rkap(struktur, bidang, lokasi_id)

    # bantuan_sppd: RKAP rows pakai LOKASI_BANTUAN_ID sebagai bucket (bukan lokasi actual SPPD)
    rkap_lokasi_id = LOKASI_BANTUAN_ID if kategori == "bantuan_sppd" else lokasi_id

    bulan_berangkat = date.fromisoformat(visum["tanggal_berangkat"]).month
    tahun_berangkat = date.fromisoformat(visum["tanggal_berangkat"]).year
    rkap_id = get_rkap_id(kategori, rkap_lokasi_id, bulan_berangkat, tahun_berangkat)

    # Insert SPPD
    try:
        res_insert = db.table("sppd").insert({
            "nomor_sppd": spd["nomor_spd"],
            "spd_id": spd["id"],
            "visum_id": visum["id"],
            "pegawai_id": pegawai_id,
            "rkap_id": rkap_id,
            "lokasi_id": lokasi_id,
            "total_hari": total_hari,
            "uang_harian_total": calc["uang_harian"],
            "uang_makan_total": calc["uang_makan"],
            "transport_lokal_total": calc["transport_lokal"],
            "uang_representasi_total": calc["uang_rep"],
            "subtotal_uang_saku": calc["subtotal"],
            "total_biaya": calc["subtotal"],
            "status": "draft"
        }).execute()

        pesan = f"SPPD dibuat (rule {'ditemukan' if rule else 'tidak ditemukan, biaya 0'})"
        return {"success": True, "pesan": pesan, "sppd_id": res_insert.data[0]["id"]}

    except Exception as e:
        return {"success": False, "pesan": str(e), "sppd_id": None}


def recalculate_sppd(sppd_id: str) -> dict:  # noqa
    """
    Hitung ulang komponen uang saku berdasarkan jabatan + rule terkini.
    - draft     : update biaya saja
    - pencairan : update biaya + adjust RKAP (rollback lama → deduct baru)
    - lainnya   : ditolak
    Return: {"success": bool, "pesan": str, "selisih": int}
    """
    db = get_client()

    res = db.table("sppd")\
        .select("id, status, pegawai_id, lokasi_id, total_hari,"
                " subtotal_uang_saku, total_hotel, total_biaya, spd_id, rkap_id")\
        .eq("id", sppd_id).single().execute()
    if not res.data:
        return {"success": False, "pesan": "SPPD tidak ditemukan", "selisih": 0}

    sppd = res.data
    if sppd["status"] not in ("draft", "pencairan"):
        return {"success": False,
                "pesan": f"SPPD status {sppd['status'].upper()} tidak dapat dihitung ulang",
                "selisih": 0}

    pegawai = get_pegawai_by_id(sppd["pegawai_id"])
    if not pegawai:
        return {"success": False, "pesan": "Pegawai tidak ditemukan", "selisih": 0}

    jabatan_id = pegawai.get("jabatan_id")
    lokasi_id  = sppd["lokasi_id"]
    total_hari = sppd["total_hari"] or 1

    rule = None
    if jabatan_id and lokasi_id:
        try:
            rule = get_rule_sppd(jabatan_id, lokasi_id)
        except Exception:
            rule = None

    if rule:
        calc = hitung_uang_saku(rule, total_hari)
    else:
        calc = {"uang_harian": 0, "uang_makan": 0,
                "transport_lokal": 0, "uang_rep": 0, "subtotal": 0}

    subtotal_baru = calc["subtotal"]
    subtotal_lama = sppd.get("subtotal_uang_saku") or 0
    selisih = subtotal_baru - subtotal_lama

    # Pertahankan var costs (hotel + transport + biaya lain); hanya uang saku yang berubah
    var_costs = (sppd.get("total_biaya") or 0) - (sppd.get("subtotal_uang_saku") or 0)
    total_biaya_baru = subtotal_baru + max(var_costs, 0)

    # Adjust RKAP untuk pencairan (hanya jika ada selisih)
    rkap_id = sppd.get("rkap_id")
    if sppd["status"] == "pencairan" and rkap_id and selisih != 0:
        rollback_rkap(rkap_id, subtotal_lama)
        deduct_rkap(rkap_id, subtotal_baru)

    try:
        db.table("sppd").update({
            "uang_harian_total":       calc["uang_harian"],
            "uang_makan_total":        calc["uang_makan"],
            "transport_lokal_total":   calc["transport_lokal"],
            "uang_representasi_total": calc["uang_rep"],
            "subtotal_uang_saku":      subtotal_baru,
            "total_biaya":             total_biaya_baru,
        }).eq("id", sppd_id).execute()
    except Exception as e:
        return {"success": False, "pesan": str(e), "selisih": 0}

    if sppd.get("spd_id"):
        update_rekap_spd(sppd["spd_id"])

    pesan = (f"Berhasil dihitung ulang "
             f"({'rule ditemukan' if rule else 'rule tidak ditemukan, biaya 0'}). "
             f"Selisih: Rp {selisih:,}".replace(",", "."))
    return {"success": True, "pesan": pesan, "selisih": selisih}


def update_tanggal_sppd_custom(sppd_id: str, tgl_berangkat: date, tgl_kembali: date) -> dict:
    """
    Update tanggal custom per SPPD (override tanggal visum) + recalc uang saku + adjust RKAP.
    Boleh dipanggil untuk status: draft, pencairan, realisasi.
    Jika bulan berangkat berubah → RKAP lama di-rollback, rkap_id baru dicari & di-deduct.
    Return: {"success": bool, "pesan": str}
    """
    db = get_client()

    res = db.table("sppd")\
        .select("id, status, pegawai_id, lokasi_id, total_hari,"
                " subtotal_uang_saku, total_biaya, rkap_id, spd_id")\
        .eq("id", sppd_id).single().execute()
    if not res.data:
        return {"success": False, "pesan": "SPPD tidak ditemukan"}

    sppd = res.data
    if sppd["status"] in ("completed", "cancelled"):
        return {"success": False, "pesan": f"SPPD status {sppd['status'].upper()} tidak dapat diubah tanggalnya"}

    total_hari_baru = (tgl_kembali - tgl_berangkat).days + 1

    pegawai = get_pegawai_by_id(sppd["pegawai_id"])
    if not pegawai:
        return {"success": False, "pesan": "Pegawai tidak ditemukan"}

    jabatan_id = pegawai.get("jabatan_id")
    lokasi_id  = sppd["lokasi_id"]

    rule = None
    if jabatan_id and lokasi_id:
        try:
            rule = get_rule_sppd(jabatan_id, lokasi_id)
        except Exception:
            rule = None

    calc = hitung_uang_saku(rule, total_hari_baru) if rule else {
        "uang_harian": 0, "uang_makan": 0, "transport_lokal": 0, "uang_rep": 0, "subtotal": 0
    }

    subtotal_baru = calc["subtotal"]
    subtotal_lama = sppd.get("subtotal_uang_saku") or 0

    # Pertahankan var costs (hotel + transport + biaya lain) — hanya uang saku yang recalc
    var_costs = max(0, (sppd.get("total_biaya") or 0) - subtotal_lama)
    total_biaya_baru = subtotal_baru + var_costs

    # Adjust RKAP hanya jika status pencairan/realisasi
    rkap_id_lama = sppd.get("rkap_id")
    rkap_id_baru = rkap_id_lama

    if sppd["status"] in ("pencairan", "realisasi") and rkap_id_lama:
        total_biaya_lama = sppd.get("total_biaya") or 0

        # Resolve rkap_id untuk bulan/tahun baru
        struktur = (pegawai.get("jabatan") or {}).get("struktur_rkap", "")
        bidang   = pegawai.get("bidang_resolved", "") or ""
        kategori = resolve_kategori_rkap(struktur, bidang, lokasi_id)
        rkap_lokasi_id = LOKASI_BANTUAN_ID if kategori == "bantuan_sppd" else lokasi_id

        rkap_id_cek = get_rkap_id(kategori, rkap_lokasi_id, tgl_berangkat.month, tgl_berangkat.year)

        # Rollback seluruh total_biaya lama dari rkap lama
        rollback_rkap(rkap_id_lama, total_biaya_lama)

        if rkap_id_cek:
            rkap_id_baru = rkap_id_cek
            deduct_rkap(rkap_id_baru, total_biaya_baru)
        else:
            rkap_id_baru = None  # RKAP bulan baru tidak ada, deduct tidak dilakukan

    db.table("sppd").update({
        "tanggal_berangkat_custom": str(tgl_berangkat),
        "tanggal_kembali_custom":   str(tgl_kembali),
        "total_hari":               total_hari_baru,
        "uang_harian_total":        calc["uang_harian"],
        "uang_makan_total":         calc["uang_makan"],
        "transport_lokal_total":    calc["transport_lokal"],
        "uang_representasi_total":  calc["uang_rep"],
        "subtotal_uang_saku":       subtotal_baru,
        "total_biaya":              total_biaya_baru,
        "rkap_id":                  rkap_id_baru,
    }).eq("id", sppd_id).execute()

    if sppd.get("spd_id"):
        update_rekap_spd(sppd["spd_id"])

    pesan = f"Tanggal diperbarui. Durasi: {total_hari_baru} hari."
    if rkap_id_lama and rkap_id_lama != rkap_id_baru:
        pesan += " RKAP dipindah ke bulan baru." if rkap_id_baru else \
                 " ⚠️ RKAP untuk bulan baru tidak ditemukan — deduct tidak dilakukan."
    return {"success": True, "pesan": pesan}


def update_jabatan_dokumen_sppd(sppd_id: str, jabatan_dokumen: str) -> dict:
    """Simpan jabatan_dokumen (override label jabatan di PDF) untuk SPPD tamu."""
    db = get_client()
    try:
        db.table("sppd").update({"jabatan_dokumen": jabatan_dokumen or None}).eq("id", sppd_id).execute()
        return {"success": True, "pesan": "Jabatan dokumen berhasil disimpan."}
    except Exception as e:
        return {"success": False, "pesan": str(e)}


def update_tanpa_uang_saku(sppd_id: str, enabled: bool) -> dict:
    """
    Toggle 'tanpa uang saku' untuk satu SPPD.
    enabled=True  → zero out semua komponen uang saku; rollback RKAP jika status pencairan.
    enabled=False → recalculate uang saku dari rule; deduct RKAP jika status pencairan.
    Return: {"success": bool, "pesan": str}
    """
    db = get_client()

    res = db.table("sppd").select(
        "id, status, rkap_id, lokasi_id, total_hari, pegawai_id,"
        " subtotal_uang_saku, total_biaya, jabatan_dokumen"
    ).eq("id", sppd_id).single().execute()

    if not res.data:
        return {"success": False, "pesan": "SPPD tidak ditemukan."}

    s       = res.data
    status  = s["status"]
    rkap_id = s.get("rkap_id")
    subtotal_lama = s.get("subtotal_uang_saku") or 0
    # var_costs = semua biaya selain uang saku (hotel, transport, biaya lain)
    var_costs = max(0, (s.get("total_biaya") or 0) - subtotal_lama)

    if enabled:
        if status == "pencairan" and rkap_id and subtotal_lama > 0:
            rollback_rkap(rkap_id, subtotal_lama)

        db.table("sppd").update({
            "tanpa_uang_saku":          True,
            "uang_harian_total":        0,
            "uang_makan_total":         0,
            "transport_lokal_total":    0,
            "uang_representasi_total":  0,
            "subtotal_uang_saku":       0,
            "total_biaya":              var_costs,
        }).eq("id", sppd_id).execute()

        pesan = "Uang saku di-nolkan."
        if status == "pencairan" and rkap_id and subtotal_lama > 0:
            pesan += f" RKAP di-rollback Rp {subtotal_lama:,}.".replace(",", ".")
        return {"success": True, "pesan": pesan}

    else:
        # Ambil jabatan_id pegawai
        peg = db.table("pegawai").select("jabatan_id").eq("id", s["pegawai_id"]).single().execute().data
        jabatan_id = (peg or {}).get("jabatan_id")
        rule = get_rule_sppd(jabatan_id, s["lokasi_id"]) if jabatan_id else None
        if not rule:
            return {"success": False, "pesan": "Rule SPPD tidak ditemukan untuk jabatan ini."}

        calc = hitung_uang_saku(rule, s.get("total_hari") or 1)
        subtotal_baru = calc["subtotal"]

        db.table("sppd").update({
            "tanpa_uang_saku":          False,
            "uang_harian_total":        calc["uang_harian"],
            "uang_makan_total":         calc["uang_makan"],
            "transport_lokal_total":    calc["transport_lokal"],
            "uang_representasi_total":  calc["uang_rep"],
            "subtotal_uang_saku":       subtotal_baru,
            "total_biaya":              subtotal_baru + var_costs,
        }).eq("id", sppd_id).execute()

        if status == "pencairan" and rkap_id and subtotal_baru > 0:
            deduct_rkap(rkap_id, subtotal_baru)

        pesan = f"Uang saku dikembalikan ({subtotal_baru:,}).".replace(",", ".")
        if status == "pencairan" and rkap_id and subtotal_baru > 0:
            pesan += " RKAP di-deduct kembali."
        return {"success": True, "pesan": pesan}


def update_tujuan_visum(visum_id: str, tujuan_baru: str, keperluan_baru: str) -> dict:
    """
    Update tujuan + keperluan visum. Jika tujuan berubah:
    - Semua SPPD non-cancelled diupdate lokasi_id + recalc uang saku
    - RKAP di-rollback (lama) + di-deduct ke bucket lokasi baru
    Return: {"success": bool, "pesan": str, "n_sppd_updated": int, "lokasi_nama": str}
    """
    db = get_client()

    res_v = db.table("visum").select("tujuan, tanggal_berangkat").eq("id", visum_id).single().execute()
    if not res_v.data:
        return {"success": False, "pesan": "Visum tidak ditemukan", "n_sppd_updated": 0, "lokasi_nama": ""}

    visum = res_v.data
    tujuan_lama = visum["tujuan"]
    tujuan_berubah = tujuan_baru != tujuan_lama

    lokasi_info = detect_lokasi(tujuan_baru)
    lokasi_id_baru = lokasi_info["lokasi_id"]

    db.table("visum").update({"tujuan": tujuan_baru, "keperluan": keperluan_baru}).eq("id", visum_id).execute()

    if not tujuan_berubah:
        return {
            "success": True,
            "pesan": "Keperluan diperbarui.",
            "n_sppd_updated": 0,
            "lokasi_nama": lokasi_info["lokasi_nama"],
        }

    # Ambil semua SPPD non-cancelled untuk visum ini
    res_sppd = db.table("sppd").select(
        "id, status, pegawai_id, lokasi_id, total_hari, "
        "subtotal_uang_saku, total_biaya, rkap_id, spd_id, tanggal_berangkat_custom"
    ).eq("visum_id", visum_id).neq("status", "cancelled").execute()

    spd_ids_updated: set = set()
    n_ok = 0

    for sppd in (res_sppd.data or []):
        sppd_id = sppd["id"]

        pegawai = get_pegawai_by_id(sppd["pegawai_id"])
        if not pegawai:
            continue

        jabatan_id = pegawai.get("jabatan_id")
        total_hari = sppd.get("total_hari") or 1

        rule = None
        if jabatan_id and lokasi_id_baru:
            try:
                rule = get_rule_sppd(jabatan_id, lokasi_id_baru)
            except Exception:
                rule = None

        calc = hitung_uang_saku(rule, total_hari) if rule else {
            "uang_harian": 0, "uang_makan": 0, "transport_lokal": 0, "uang_rep": 0, "subtotal": 0,
        }

        subtotal_baru = calc["subtotal"]
        subtotal_lama = sppd.get("subtotal_uang_saku") or 0
        var_costs = max(0, (sppd.get("total_biaya") or 0) - subtotal_lama)
        total_biaya_baru = subtotal_baru + var_costs

        rkap_id_lama = sppd.get("rkap_id")
        rkap_id_baru = rkap_id_lama

        if sppd["status"] in ("pencairan", "realisasi", "completed") and rkap_id_lama:
            tgl_eff_str = sppd.get("tanggal_berangkat_custom") or visum["tanggal_berangkat"]
            tgl_eff = date.fromisoformat(tgl_eff_str)

            struktur = (pegawai.get("jabatan") or {}).get("struktur_rkap", "")
            bidang = pegawai.get("bidang_resolved", "") or ""
            kategori = resolve_kategori_rkap(struktur, bidang, lokasi_id_baru)
            rkap_lokasi_id = LOKASI_BANTUAN_ID if kategori == "bantuan_sppd" else lokasi_id_baru

            rkap_id_cek = get_rkap_id(kategori, rkap_lokasi_id, tgl_eff.month, tgl_eff.year)

            rollback_rkap(rkap_id_lama, sppd.get("total_biaya") or 0)

            if rkap_id_cek:
                rkap_id_baru = rkap_id_cek
                deduct_rkap(rkap_id_baru, total_biaya_baru)
            else:
                rkap_id_baru = None

        db.table("sppd").update({
            "lokasi_id":               lokasi_id_baru,
            "uang_harian_total":       calc["uang_harian"],
            "uang_makan_total":        calc["uang_makan"],
            "transport_lokal_total":   calc["transport_lokal"],
            "uang_representasi_total": calc["uang_rep"],
            "subtotal_uang_saku":      subtotal_baru,
            "total_biaya":             total_biaya_baru,
            "rkap_id":                 rkap_id_baru,
        }).eq("id", sppd_id).execute()

        if sppd.get("spd_id"):
            spd_ids_updated.add(sppd["spd_id"])

        n_ok += 1

    for spd_id in spd_ids_updated:
        update_rekap_spd(spd_id)

    return {
        "success": True,
        "pesan": f"Tujuan & keperluan diperbarui. {n_ok} SPPD direcalculate.",
        "n_sppd_updated": n_ok,
        "lokasi_nama": lokasi_info["lokasi_nama"],
    }


def auto_buat_semua_sppd(visum: dict, lokasi_id: str, spd_id: str) -> list:
    """
    Buat SPPD otomatis untuk semua peserta visum.
    spd_id: ID SPD yang sudah dipilih/dibuat sebelumnya.
    Return: list of result dict per pegawai.
    """
    peserta_ids = visum.get("peserta") or []
    if not peserta_ids:
        return []

    spd = get_spd_by_id(spd_id)
    if not spd:
        return [{"pegawai_id": p, "success": False, "pesan": "SPD tidak ditemukan"} for p in peserta_ids]

    results = []
    for pegawai_id in peserta_ids:
        result = buat_sppd_untuk_pegawai(pegawai_id, visum, spd, lokasi_id)
        results.append({"pegawai_id": pegawai_id, **result})

    update_rekap_spd(spd["id"])
    return results


def sync_sppd_peserta(visum: dict, peserta_baru: list, lokasi_id: str, spd_id: str) -> dict:
    """
    Sinkronisasi SPPD saat peserta visum diedit.
    - Peserta baru ditambahkan → buat SPPD baru
    - Peserta dihapus → cancel SPPD milik visum ini (hanya kalau status draft/pencairan)
    spd_id: ID SPD yang dipakai visum ini.

    Return: {"ditambah": [...], "dihapus": [...], "diblok": [...]}
    """
    db = get_client()
    visum_id = visum["id"]
    peserta_lama = visum.get("peserta") or []

    ditambah_ids = [p for p in peserta_baru if p not in peserta_lama]
    dihapus_ids  = [p for p in peserta_lama if p not in peserta_baru]

    hasil = {"ditambah": [], "dihapus": [], "diblok": []}

    spd = get_spd_by_id(spd_id)
    if not spd:
        return hasil

    # Tambah SPPD untuk peserta baru
    for pid in ditambah_ids:
        result = buat_sppd_untuk_pegawai(pid, visum, spd, lokasi_id)
        hasil["ditambah"].append({"pegawai_id": pid, **result})

    # Cancel SPPD untuk peserta yang dihapus — filter by visum_id agar tidak kena sppd dari visum lain
    for pid in dihapus_ids:
        res_sppd = db.table("sppd")\
            .select("id, status, rkap_id, subtotal_uang_saku, total_biaya")\
            .eq("visum_id", visum_id)\
            .eq("pegawai_id", pid)\
            .neq("status", "cancelled")\
            .execute()

        if not res_sppd.data:
            continue

        s = res_sppd.data[0]
        status = s["status"]

        if status in ["realisasi", "completed"]:
            hasil["diblok"].append({
                "pegawai_id": pid,
                "pesan": f"SPPD tidak bisa dihapus — status sudah {status.upper()}"
            })
            continue

        if status == "pencairan" and s.get("rkap_id"):
            rollback_rkap(s["rkap_id"], s.get("subtotal_uang_saku") or 0)

        db.table("sppd").update({"status": "cancelled"})\
            .eq("id", s["id"]).execute()

        hasil["dihapus"].append({"pegawai_id": pid, "pesan": "SPPD di-cancel"})

    update_rekap_spd(spd["id"])
    return hasil


def cancel_semua_sppd_visum(visum_id: str) -> dict:
    """
    Cancel semua SPPD dalam visum (saat visum di-cancel).
    Hanya cancel SPPD milik visum ini — tidak ikut cancel SPPD visum lain yang kebetulan satu SPD.
    Block kalau ada SPPD yang sudah realisasi/completed.
    Return: {"success": bool, "diblok": [...], "dicancelled": int}
    """
    db = get_client()

    # Cari SPPD langsung by visum_id (tidak perlu via spd.visum_id)
    res_sppd = db.table("sppd")\
        .select("id, status, rkap_id, subtotal_uang_saku, total_biaya, spd_id")\
        .eq("visum_id", visum_id)\
        .neq("status", "cancelled")\
        .execute()

    if not res_sppd.data:
        return {"success": True, "diblok": [], "dicancelled": 0}

    diblok = []
    dicancelled = 0
    spd_ids_terdampak = set()

    for s in res_sppd.data:
        if s["status"] in ["realisasi", "completed"]:
            diblok.append({
                "sppd_id": s["id"],
                "pesan": f"Status sudah {s['status'].upper()}, tidak bisa di-cancel"
            })
            continue

        # Rollback RKAP
        if s["status"] == "pencairan" and s.get("rkap_id"):
            rollback_rkap(s["rkap_id"], s.get("subtotal_uang_saku") or 0)

        db.table("sppd").update({"status": "cancelled"})\
            .eq("id", s["id"]).execute()
        dicancelled += 1
        if s.get("spd_id"):
            spd_ids_terdampak.add(s["spd_id"])

    # Update rekap untuk semua SPD yang terdampak
    for spd_id in spd_ids_terdampak:
        update_rekap_spd(spd_id)

    return {
        "success": len(diblok) == 0,
        "diblok": diblok,
        "dicancelled": dicancelled
    }


def update_rekap_spd(spd_id: str):
    """Hitung ulang rekap total SPD dari semua SPPD yang linked."""
    db = get_client()

    res_divisi = db.table("divisi").select("id, parent_id, bidang").execute()
    divisi_map = {d["id"]: d for d in res_divisi.data}
    
    res = db.table("sppd")\
        .select("*, pegawai!sppd_pegawai_id_fkey(jabatan(struktur_rkap), divisi_id)")\
        .eq("spd_id", spd_id)\
        .neq("status", "cancelled")\
        .execute()
    
    rekap = {
        "total_direksi": 0,
        "total_dewas": 0,
        "total_administrasi": 0,
        "total_teknik": 0,
        "total_bantuan": 0,
    }
    
    for s in res.data:
        struktur = None
        bidang = None
        try:
            struktur = s["pegawai"]["jabatan"]["struktur_rkap"]
            div_id = s["pegawai"]["divisi_id"]
            div = divisi_map.get(div_id, {})
            bidang_raw = div.get("bidang") or divisi_map.get(div.get("parent_id"), {}).get("bidang")
            bidang = bidang_raw.title() if bidang_raw else None
        except:
            pass

        biaya = s.get("total_biaya") or 0
        
        if struktur in ["DIRUT", "DIRUM", "DIRTEK", "DIROPS"]:
            rekap["total_direksi"] += biaya
        elif struktur in ["DEWAS_KETUA", "DEWAS_ANGGOTA",
                          "DEWAS_ANGGOTA_1", "DEWAS_ANGGOTA_2"]:
            rekap["total_dewas"] += biaya
        elif struktur in ["MANAJER", "SUPERVISOR", "STAF_PELAKSANA",
                          "ADM_MANAJER", "ADM_SUPERVISOR", "ADM_STAF_PELAKSANA"]:
            if bidang == "Teknik":
                rekap["total_teknik"] += biaya
            else:
                rekap["total_administrasi"] += biaya
        elif struktur in ["TEKNIK_MANAJER", "TEKNIK_SUPERVISOR", "TEKNIK_STAF_PELAKSANA"]:
            rekap["total_teknik"] += biaya
        elif struktur == "BANTUAN":
            rekap["total_bantuan"] += biaya
        else:
            rekap["total_administrasi"] += biaya
    
    rekap["grand_total"] = sum(rekap.values())
    db.table("spd").update(rekap).eq("id", spd_id).execute()


def assign_visum_ke_spd(visum_id: str, spd_id_baru: str) -> dict:
    """
    Pindahkan semua SPPD dari suatu visum ke SPD yang dipilih.
    Update spd_id + nomor_sppd di semua sppd dengan visum_id tsb.
    Berguna untuk mapping data historis atau koreksi salah assign.
    Return: {"updated": int, "pesan": str}
    """
    db = get_client()
    spd_baru = get_spd_by_id(spd_id_baru)
    if not spd_baru:
        return {"updated": 0, "pesan": "SPD tidak ditemukan"}

    res_sppd = db.table("sppd").select("id, spd_id")\
        .eq("visum_id", visum_id).execute()
    if not res_sppd.data:
        return {"updated": 0, "pesan": "Tidak ada SPPD untuk visum ini"}

    # Kumpulkan spd_id lama yang berbeda dari SPD baru
    spd_ids_lama = list({
        s["spd_id"] for s in res_sppd.data
        if s.get("spd_id") and s["spd_id"] != spd_id_baru
    })

    # Update semua SPPD visum ini ke SPD baru
    db.table("sppd").update({
        "spd_id":    spd_id_baru,
        "nomor_sppd": spd_baru["nomor_spd"],
    }).eq("visum_id", visum_id).execute()

    # Update rekap SPD lama dan baru
    for sid in spd_ids_lama:
        update_rekap_spd(sid)
    update_rekap_spd(spd_id_baru)

    jumlah = len(res_sppd.data)
    return {"updated": jumlah, "pesan": f"{jumlah} SPPD dipindah ke {spd_baru['nomor_spd']}"}


# ─── HOTEL & BIAYA LAIN ────────────────────────────────
def get_plafon_hotel(jabatan_id: str, lokasi_id: str) -> int:
    """Return plafon_hotel dari rule_sppd. Return 0 kalau tidak ketemu."""
    rule = get_rule_sppd(jabatan_id, lokasi_id)
    return rule.get("plafon_hotel", 0) if rule else 0


def save_biaya_lain(sppd_id: str, items: list):
    """Hapus semua biaya lain lama lalu insert baru.
    items = [{"keterangan": str, "jumlah": int}, ...]
    """
    db = get_client()
    db.table("sppd_biaya_lain").delete().eq("sppd_id", sppd_id).execute()
    if items:
        rows = [
            {"sppd_id": sppd_id, "urutan": i + 1,
             "keterangan": item["keterangan"], "jumlah": item["jumlah"]}
            for i, item in enumerate(items)
        ]
        db.table("sppd_biaya_lain").insert(rows).execute()


def get_biaya_lain(sppd_id: str) -> list:
    """Return list biaya lain untuk satu sppd_id, urut by urutan."""
    db = get_client()
    res = db.table("sppd_biaya_lain")\
        .select("*")\
        .eq("sppd_id", sppd_id)\
        .order("urutan")\
        .execute()
    return res.data or []


def save_transport_detail(sppd_id: str, items: list, tgl_berangkat=None, tgl_kembali=None):
    """Hapus semua rincian transport lama lalu insert baru.
    items = [{"kota_asal": str, "kota_tujuan": str, "jenis_transport": str, "biaya_transport": int}, ...]
    tgl_berangkat / tgl_kembali diisi dari visum untuk memenuhi NOT NULL constraint.
    """
    from datetime import date as _date
    fallback = str(_date.today())
    tgl_b = str(tgl_berangkat) if tgl_berangkat else fallback
    tgl_k = str(tgl_kembali)   if tgl_kembali   else fallback

    db = get_client()
    db.table("sppd_trip_detail").delete().eq("sppd_id", sppd_id).execute()
    if items:
        rows = [
            {
                "sppd_id":           sppd_id,
                "urutan":            i + 1,
                "kota_asal":         item.get("kota_asal", ""),
                "kota_tujuan":       item.get("kota_tujuan", ""),
                "jenis_transport":   item.get("jenis_transport", ""),
                "biaya_transport":   item.get("biaya_transport", 0),
                "tanggal_berangkat": tgl_b,
                "tanggal_kembali":   tgl_k,
            }
            for i, item in enumerate(items)
        ]
        db.table("sppd_trip_detail").insert(rows).execute()


def get_transport_detail(sppd_id: str) -> list:
    """Return list rincian transport untuk satu sppd_id, urut by urutan."""
    db = get_client()
    res = db.table("sppd_trip_detail")\
        .select("urutan, kota_asal, kota_tujuan, jenis_transport, biaya_transport")\
        .eq("sppd_id", sppd_id)\
        .order("urutan")\
        .execute()
    return res.data or []


# ─── LAPORAN ────────────────────────────────────────────

def get_sppd_realisasi_laporan(bulan: int, tahun: int) -> list:
    """Ambil data realisasi SPPD untuk laporan bulanan.

    Return: list of dict per visum, masing-masing berisi:
      {
        "visum": {id, nomor_visum, tanggal_berangkat, tanggal_kembali, tujuan, keperluan, nomor_spd},
        "sppd_rows": [
          {nama, jabatan, struktur_rkap, lokasi_id, nomor_voucher,
           uang_saku, tiket, hotel, biaya_lain, total},
          ...
        ]
      }
    Diurutkan berdasarkan tanggal_berangkat visum ASC.
    """
    from datetime import date as _date
    import calendar

    db = get_client()

    # Range tanggal untuk bulan yg diminta
    start = f"{tahun}-{bulan:02d}-01"
    last_day = calendar.monthrange(tahun, bulan)[1]
    end = f"{tahun}-{bulan:02d}-{last_day}"

    # 1. Ambil visum dalam bulan ini
    res_v = db.table("visum")\
        .select("id, nomor_visum, tanggal_berangkat, tanggal_kembali, tujuan, keperluan")\
        .gte("tanggal_berangkat", start)\
        .lte("tanggal_berangkat", end)\
        .order("tanggal_berangkat")\
        .execute()
    visums = res_v.data or []
    if not visums:
        return []

    visum_ids = [v["id"] for v in visums]

    # 2. Ambil semua sppd untuk visum tersebut (status realisasi / completed)
    res_s = db.table("sppd")\
        .select("id, visum_id, spd_id, lokasi_id, nomor_voucher, "
                "subtotal_uang_saku, total_transport, total_hotel, total_biaya, "
                "biaya_jenazah, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama, struktur_rkap))")\
        .in_("visum_id", visum_ids)\
        .in_("status", ["realisasi", "completed"])\
        .execute()
    sppd_list = res_s.data or []

    # 3. Ambil nomor_spd untuk setiap spd_id unik
    spd_ids = list({s["spd_id"] for s in sppd_list if s.get("spd_id")})
    spd_map = {}
    if spd_ids:
        res_spd = db.table("spd")\
            .select("id, nomor_spd")\
            .in_("id", spd_ids)\
            .execute()
        spd_map = {row["id"]: row["nomor_spd"] for row in (res_spd.data or [])}

    # 4. Biaya lain per sppd (batch)
    sppd_ids = [s["id"] for s in sppd_list]
    biaya_lain_map = {}
    if sppd_ids:
        res_bl = db.table("sppd_biaya_lain")\
            .select("sppd_id, jumlah")\
            .in_("sppd_id", sppd_ids)\
            .execute()
        for row in (res_bl.data or []):
            biaya_lain_map[row["sppd_id"]] = biaya_lain_map.get(row["sppd_id"], 0) + row["jumlah"]

    # 5. Build sppd dict yang lebih ringkas, indeks by visum_id
    sppd_by_visum = {}
    for s in sppd_list:
        vid = s["visum_id"]
        peg = s.get("pegawai!sppd_pegawai_id_fkey") or s.get("pegawai") or {}
        jab = peg.get("jabatan") or {}
        bl_sum = biaya_lain_map.get(s["id"], 0)
        # Biaya lain = total_biaya - uang_saku - tiket - hotel (- jenazah kalau ada)
        biaya_lain_calc = (
            s.get("total_biaya", 0)
            - s.get("subtotal_uang_saku", 0)
            - s.get("total_transport", 0)
            - s.get("total_hotel", 0)
            - s.get("biaya_jenazah", 0)
        )
        row = {
            "nama": peg.get("nama", ""),
            "jabatan": jab.get("nama", ""),
            "struktur_rkap": jab.get("struktur_rkap", ""),
            "lokasi_id": s.get("lokasi_id", ""),
            "nomor_voucher": s.get("nomor_voucher") or "",
            "nomor_spd": spd_map.get(s.get("spd_id"), ""),
            "uang_saku": s.get("subtotal_uang_saku", 0),
            "tiket": s.get("total_transport", 0),
            "hotel": s.get("total_hotel", 0),
            "biaya_lain": max(biaya_lain_calc, 0),
            "total": s.get("total_biaya", 0),
        }
        sppd_by_visum.setdefault(vid, []).append(row)

    # 6. Susun output terurut by tanggal_berangkat
    result = []
    for v in visums:
        rows = sppd_by_visum.get(v["id"], [])
        if not rows:
            continue
        # nomor_spd untuk visum ini (ambil dari baris pertama)
        nomor_spd = rows[0]["nomor_spd"] if rows else ""
        result.append({
            "visum": {
                "id": v["id"],
                "nomor_visum": v["nomor_visum"],
                "tanggal_berangkat": v["tanggal_berangkat"],
                "tanggal_kembali": v["tanggal_kembali"],
                "tujuan": v.get("tujuan", ""),
                "keperluan": v.get("keperluan", ""),
                "nomor_spd": nomor_spd,
            },
            "sppd_rows": rows,
        })
    return result


def get_rekap_perjalanan(bulan_list: list) -> dict:
    """Ambil rekap jumlah keberangkatan per jabatan per lokasi.

    bulan_list: [(bulan, tahun), ...]  — bisa 1 bulan (bulanan) atau 6 bulan (semester)

    Return: {
      (bulan, tahun): [
        {"jabatan": str, "struktur_rkap": str, "lokasi_id": str, "count": int},
        ...
      ]
    }
    """
    import calendar

    db = get_client()
    result = {}

    for bulan, tahun in bulan_list:
        start = f"{tahun}-{bulan:02d}-01"
        last_day = calendar.monthrange(tahun, bulan)[1]
        end = f"{tahun}-{bulan:02d}-{last_day}"

        # Ambil visum IDs dalam bulan ini
        res_v = db.table("visum")\
            .select("id")\
            .gte("tanggal_berangkat", start)\
            .lte("tanggal_berangkat", end)\
            .execute()
        visum_ids = [v["id"] for v in (res_v.data or [])]

        if not visum_ids:
            result[(bulan, tahun)] = []
            continue

        # Ambil sppd (status realisasi/completed) beserta jabatan & lokasi
        res_s = db.table("sppd")\
            .select("lokasi_id, pegawai!sppd_pegawai_id_fkey(jabatan(nama, struktur_rkap))")\
            .in_("visum_id", visum_ids)\
            .in_("status", ["realisasi", "completed"])\
            .execute()

        # Group by jabatan + lokasi
        counts = {}
        for s in (res_s.data or []):
            peg = s.get("pegawai!sppd_pegawai_id_fkey") or s.get("pegawai") or {}
            jab = peg.get("jabatan") or {}
            key = (jab.get("nama", ""), jab.get("struktur_rkap", ""), s.get("lokasi_id", ""))
            counts[key] = counts.get(key, 0) + 1

        rows = [
            {"jabatan": k[0], "struktur_rkap": k[1], "lokasi_id": k[2], "count": v}
            for k, v in counts.items()
        ]
        result[(bulan, tahun)] = rows

    return result