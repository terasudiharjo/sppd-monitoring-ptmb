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
    "TAMU SETARA DIREKTUR BIDANG": "TAMU DIREKTUR BIDANG",
    "TAMU SETARA MANAJER":         "MANAJER",
    "TAMU SETARA SUPERVISOR":      "SUPERVISOR",
    "TAMU SETARA STAF":            "STAF PELAKSANA",
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
    "STAF AHLI BIDANG HUKUM DAN ASET PERUSAHAAN": 5,
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

LOKASI_LN_ID = "38663104-e5f5-473d-8227-640f025e595a"

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
    if res_count.data:
        max_urutan = max(
            int(s["nomor_spd"].split("/")[0])
            for s in res_count.data
            if s["nomor_spd"].split("/")[0].isdigit()
        )
        urutan = max_urutan + 1
    else:
        urutan = 1
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
    kategori = resolve_kategori_rkap(struktur, bidang, lokasi_id)
    
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