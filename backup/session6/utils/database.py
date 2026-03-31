from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── PEGAWAI ───────────────────────────────────────────
def get_all_pegawai():
    db = get_client()
    
    # Ambil semua divisi dulu (untuk lookup bidang)
    res_divisi = db.table("divisi").select("id, nama, parent_id, bidang").execute()
    divisi_map = {d["id"]: d for d in res_divisi.data}
    
    # Ambil pegawai
    res = db.table("pegawai")\
        .select("*, divisi_id, divisi(id, nama, parent_id, bidang), jabatan(nama, struktur_rkap)")\
        .eq("status", "aktif")\
        .order("nama")\
        .execute()
    
    # Resolve bidang — kalau subdiv, ambil bidang dari parent
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

def get_pegawai_by_id(pegawai_id):
    db = get_client()
    res = db.table("pegawai")\
        .select("*, divisi(nama), jabatan(nama)")\
        .eq("id", pegawai_id)\
        .single()\
        .execute()
    return res.data

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
        from datetime import date
        tahun = date.today().year # default ke tahun berjalan
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
    "tenggarong", "sangatta", "tanjung redeb", "tanah grogot",
    "penajam", "long bagun"
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

# Mapping nama jabatan pegawai → nama jabatan di rule_sppd
JABATAN_RULE_MAP = {
    "DIREKTUR UTAMA": "DIREKTUR UTAMA",
    "DIREKTUR BIDANG UMUM": "DIREKTUR BIDANG",
    "DIREKTUR OPERASIONAL": "DIREKTUR BIDANG",
    "DIREKTUR TEKNIK": "DIREKTUR BIDANG",
    "MANAJER": "MANAJER",
    "STAF AHLI BIDANG HUKUM DAN ASET PERUSAHAAN": "SUPERVISOR",
    "SUPERVISOR": "SUPERVISOR",
    "KETUA REGU": "SUPERVISOR",
    "STAF PELAKSANA": "STAF PELAKSANA",
    "TIM PENGADAAN": "STAF PELAKSANA",
    "BENDAHARA PEMBANTU": "STAF PELAKSANA",
    "CALON PEGAWAI": "STAF PELAKSANA",
    "KETUA DEWAN PENGAWAS": "DIREKTUR UTAMA",
    "ANGGOTA DEWAN PENGAWAS": "DIREKTUR BIDANG",
}

def get_rule_sppd(jabatan_id: str, lokasi_id: str):
    db = get_client()
    
    # Ambil nama jabatan dari jabatan_id
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
    """Tambah anggaran_terpakai dan kurangi anggaran_sisa."""
    db = get_client()
    # Ambil data RKAP dulu
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
    """Kembalikan anggaran saat SPPD dibatalkan."""
    db = get_client()
    res = db.table("rkap").select("anggaran_terpakai, anggaran_sisa").eq("id", rkap_id).single().execute()
    if not res.data:
        return False
    terpakai_baru = max(res.data["anggaran_terpakai"] - jumlah, 0)
    sisa_baru     = res.data["anggaran_sisa"] + jumlah
    db.table("rkap").update({
        "anggaran_terpakai": terpakai_baru,
        "anggaran_sisa":     sisa_baru,
    }).eq("id", rkap_id).execute()
    return True

# ─── CARI RKAP ID ──────────────────────────────────────
def get_rkap_id(struktur_rkap: str, lokasi_id: str, bulan: int, tahun: int):
    """Cari rkap_id berdasarkan kategori jabatan + lokasi + bulan + tahun."""
    db = get_client()
    res = db.table("rkap")\
        .select("id")\
        .eq("kategori_jabatan", struktur_rkap)\
        .eq("lokasi_id", lokasi_id)\
        .eq("bulan", bulan)\
        .eq("tahun", tahun)\
        .execute()
    return res.data[0]["id"] if res.data else None