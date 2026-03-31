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

# ─── MAPPING ───────────────────────────────────────────
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

# Urutan sort untuk Rekap SPD (level jabatan, makin kecil = makin atas)
JABATAN_SORT_ORDER = {
    "DIREKTUR UTAMA": 1,
    "DIREKTUR BIDANG UMUM": 2,
    "DIREKTUR OPERASIONAL": 2,
    "DIREKTUR TEKNIK": 2,
    "KETUA DEWAN PENGAWAS": 3,
    "ANGGOTA DEWAN PENGAWAS": 4,
    "MANAJER": 5,
    "STAF AHLI BIDANG HUKUM DAN ASET PERUSAHAAN": 6,
    "SUPERVISOR": 6,
    "KETUA REGU": 6,
    "STAF PELAKSANA": 7,
    "TIM PENGADAAN": 7,
    "BENDAHARA PEMBANTU": 7,
    "CALON PEGAWAI": 8,
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
    terpakai_baru = max(res.data["anggaran_terpakai"] - jumlah, 0)
    sisa_baru     = res.data["anggaran_sisa"] + jumlah
    db.table("rkap").update({
        "anggaran_terpakai": terpakai_baru,
        "anggaran_sisa":     sisa_baru,
    }).eq("id", rkap_id).execute()
    return True

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
    uang_rep       = (rule.get("uang_rep") or 0) * total_hari
    subtotal       = uang_harian + uang_makan + transport_lokal + uang_rep
    return {
        "uang_harian": uang_harian,
        "uang_makan": uang_makan,
        "transport_lokal": transport_lokal,
        "uang_rep": uang_rep,
        "subtotal": subtotal
    }

def resolve_kategori_rkap(struktur_rkap: str, bidang_resolved: str) -> str:
    """Mapping struktur_rkap + bidang → kategori_jabatan di tabel RKAP."""
    if struktur_rkap == "MANAJER":
        return "ADM_MANAJER" if bidang_resolved == "Administrasi" else "TEKNIK_MANAJER"
    elif struktur_rkap == "SUPERVISOR":
        return "ADM_SUPERVISOR" if bidang_resolved == "Administrasi" else "TEKNIK_SUPERVISOR"
    elif struktur_rkap == "STAF_PELAKSANA":
        return "ADM_STAF_PELAKSANA" if bidang_resolved == "Administrasi" else "TEKNIK_STAF_PELAKSANA"
    elif struktur_rkap == "DEWAS_ANGGOTA":
        return "DEWAS_ANGGOTA_1"
    else:
        return struktur_rkap  # DIRUT, DIRUM, DIRTEK, DIROPS, DEWAS_KETUA

# ══════════════════════════════════════════════════════
# AUTO SPPD — function baru session 7
# ══════════════════════════════════════════════════════

BULAN_ROMAWI = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]

def get_or_create_spd(visum_id: str, tanggal: date) -> dict:
    """Ambil SPD yang sudah ada untuk visum ini, kalau belum ada buat baru."""
    db = get_client()
    res = db.table("spd").select("*").eq("visum_id", visum_id).execute()
    if res.data:
        return res.data[0]
    
    tahun = tanggal.year
    bulan = BULAN_ROMAWI[tanggal.month - 1]
    res_count = db.table("spd").select("nomor_spd")\
        .like("nomor_spd", f"%/{tahun}-O")\
        .execute()
    urutan = len(res_count.data) + 1
    nomor_spd = f"{urutan:04d}/1421002/10a-I/{bulan}/{tahun}-O"
    
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

    # Cek apakah SPPD sudah ada (non-cancelled)
    res_cek = db.table("sppd")\
        .select("id")\
        .eq("spd_id", spd["id"])\
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
    kategori = resolve_kategori_rkap(struktur, bidang)
    
    bulan_berangkat = date.fromisoformat(visum["tanggal_berangkat"]).month
    tahun_berangkat = date.fromisoformat(visum["tanggal_berangkat"]).year
    rkap_id = get_rkap_id(kategori, lokasi_id, bulan_berangkat, tahun_berangkat)

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


def auto_buat_semua_sppd(visum: dict, lokasi_id: str) -> list:
    """
    Buat SPPD otomatis untuk semua peserta visum.
    Dipanggil saat visum baru disimpan.
    Return: list of result dict per pegawai.
    """
    peserta_ids = visum.get("peserta") or []
    if not peserta_ids:
        return []

    tgl_visum = date.fromisoformat(visum.get("tanggal_visum") or str(date.today()))
    spd = get_or_create_spd(visum["id"], tgl_visum)

    results = []
    for pegawai_id in peserta_ids:
        result = buat_sppd_untuk_pegawai(pegawai_id, visum, spd, lokasi_id)
        results.append({"pegawai_id": pegawai_id, **result})

    # Update rekap SPD setelah semua SPPD dibuat
    update_rekap_spd(spd["id"])

    return results


def sync_sppd_peserta(visum: dict, peserta_baru: list, lokasi_id: str) -> dict:
    """
    Sinkronisasi SPPD saat peserta visum diedit.
    - Peserta baru ditambahkan → buat SPPD baru
    - Peserta dihapus → cancel SPPD (hanya kalau status draft/pencairan)
    
    Return: {"ditambah": [...], "dihapus": [...], "diblok": [...]}
    """
    db = get_client()
    visum_id = visum["id"]
    peserta_lama = visum.get("peserta") or []

    ditambah_ids = [p for p in peserta_baru if p not in peserta_lama]
    dihapus_ids  = [p for p in peserta_lama if p not in peserta_baru]

    hasil = {"ditambah": [], "dihapus": [], "diblok": []}

    # Ambil atau buat SPD
    tgl_visum = date.fromisoformat(visum.get("tanggal_visum") or str(date.today()))
    spd = get_or_create_spd(visum_id, tgl_visum)

    # Tambah SPPD untuk peserta baru
    for pid in ditambah_ids:
        result = buat_sppd_untuk_pegawai(pid, visum, spd, lokasi_id)
        hasil["ditambah"].append({"pegawai_id": pid, **result})

    # Cancel SPPD untuk peserta yang dihapus
    for pid in dihapus_ids:
        res_sppd = db.table("sppd")\
            .select("id, status, rkap_id, subtotal_uang_saku, total_biaya")\
            .eq("spd_id", spd["id"])\
            .eq("pegawai_id", pid)\
            .neq("status", "cancelled")\
            .execute()
        
        if not res_sppd.data:
            continue

        s = res_sppd.data[0]
        status = s["status"]

        # Block kalau status realisasi atau completed
        if status in ["realisasi", "completed"]:
            hasil["diblok"].append({
                "pegawai_id": pid,
                "pesan": f"SPPD tidak bisa dihapus — status sudah {status.upper()}"
            })
            continue

        # Rollback RKAP kalau status pencairan
        if status == "pencairan" and s.get("rkap_id"):
            rollback_rkap(s["rkap_id"], s.get("subtotal_uang_saku") or 0)

        # Cancel SPPD
        db.table("sppd").update({"status": "cancelled"})\
            .eq("id", s["id"]).execute()
        
        hasil["dihapus"].append({"pegawai_id": pid, "pesan": "SPPD di-cancel"})

    # Update rekap SPD
    update_rekap_spd(spd["id"])

    return hasil


def cancel_semua_sppd_visum(visum_id: str) -> dict:
    """
    Cancel semua SPPD dalam visum (saat visum di-cancel).
    Block kalau ada SPPD yang sudah realisasi/completed.
    Return: {"success": bool, "diblok": [...], "dicancelled": int}
    """
    db = get_client()

    # Cari SPD untuk visum ini
    res_spd = db.table("spd").select("id").eq("visum_id", visum_id).execute()
    if not res_spd.data:
        return {"success": True, "diblok": [], "dicancelled": 0}

    spd_id = res_spd.data[0]["id"]

    # Ambil semua SPPD aktif
    res_sppd = db.table("sppd")\
        .select("id, status, rkap_id, subtotal_uang_saku, total_biaya")\
        .eq("spd_id", spd_id)\
        .neq("status", "cancelled")\
        .execute()

    diblok = []
    dicancelled = 0

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
        elif struktur in ["DEWAS_KETUA", "DEWAS_ANGGOTA"]:
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