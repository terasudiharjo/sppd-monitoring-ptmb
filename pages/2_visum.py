import re
import streamlit as st
from utils.database import (
    get_all_pegawai, get_all_divisi,
    detect_lokasi, get_or_create_spd,
    create_spd_baru, get_spd_by_id, get_spd_list_semua, assign_visum_ke_spd,
    auto_buat_semua_sppd, sync_sppd_peserta, cancel_semua_sppd_visum
)
from utils.pdf_generator import (
    generate_visum, generate_surat_tugas, generate_spd, fmt_tgl_short, fmt_waktu_surat_tugas
)
from supabase import create_client
from dotenv import load_dotenv
from datetime import date, datetime
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ─── AUTH CHECK ────────────────────────────────────────
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Silakan login terlebih dahulu.")
    st.stop()

# ─── KONSTANTA ─────────────────────────────────────────
KODE_STATIC = "1421002"
KODE_SEKPER = "10a-I"
KODE_VISUM  = "J"

KOTA_OPTIONS = [
    "Samarinda", "Balikpapan", "Bontang", "Kutai Kartanegara",
    "Berau", "Paser", "Penajam Paser Utara", "Mahakam Ulu", "IKN",
    "Kutai Timur", "Kutai Barat",
    "Tenggarong", "Sangatta", "Tanjung Redeb", "Tanah Grogot",
    "Penajam", "Sendawar", "Ujoh Bilang",
    "Banjarmasin", "Palangka Raya", "Pontianak",
    "Jakarta", "Surabaya", "Bandung", "Yogyakarta", "Semarang", "Bogor",
    "Makassar", "Manado", "Palu", "Batam",
    "Medan", "Palembang", "Denpasar", "Lombok",
]

BULAN_ROMAWI = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]

def format_jabatan_divisi(jabatan_nama, divisi_nama):
    """Format singkat jabatan + divisi untuk PDF visum.
    - Manajer → Man - [nama divisi]
    - Supervisor → Spv - [nama divisi]
    - Staf/Pelaksana → Staf - [nama divisi]
    - Lainnya (Direktur, Kepala, Dewas) → jabatan apa adanya
    - Tamu → string kosong (jabatan tidak ditampilkan di surat)
    Prefix "Divisi " / "Sub Divisi " di nama DB di-strip supaya tidak redundant.
    """
    if jabatan_nama.upper().startswith("TAMU"):
        return ""
    # Strip prefix bawaan DB: "Sub Divisi", "Sub.Divisi", "Divisi", dll (case-insensitive)
    div = re.sub(r"^(sub[\s.]*divisi|divisi)[\s.]*", "", divisi_nama, flags=re.IGNORECASE).strip()
    div = div.title()

    jab = jabatan_nama.lower()
    if "manajer" in jab or "manager" in jab:
        return f"Man - {div}"
    elif "supervisor" in jab:
        return f"Spv - {div}"
    elif "staf" in jab or "pelaksana" in jab:
        return f"Staf - {div}"
    else:
        return jabatan_nama.title()

def _strip_div_prefix(nama: str) -> str:
    return re.sub(r"^(sub[\s.]*divisi|divisi)[\s.]*", "", nama, flags=re.IGNORECASE).strip().title()

def get_divisi_label_surat_tugas(jabatan_nama: str, divisi_obj: dict, divisi_map: dict) -> str:
    """Kolom divisi di tabel Surat Tugas.
    - Spv / Staf / Pelaksana → nama divisi PARENT (strip prefix + title)
    - Manajer               → nama divisi sendiri (strip prefix + title)
    - Direksi / Dewas / dll → '-'
    - Tamu                  → '' (kosong)
    """
    if jabatan_nama.upper().startswith("TAMU"):
        return ""
    if not divisi_obj or not isinstance(divisi_obj, dict):
        return "-"
    jab = jabatan_nama.lower()
    if "supervisor" in jab or "staf" in jab or "pelaksana" in jab:
        parent_id = divisi_obj.get("parent_id")
        if parent_id and parent_id in divisi_map:
            return _strip_div_prefix(divisi_map[parent_id].get("nama", "-"))
        # fallback: divisi sendiri kalau parent tidak ditemukan
        return _strip_div_prefix(divisi_obj.get("nama", "-"))
    elif "manajer" in jab or "manager" in jab:
        return _strip_div_prefix(divisi_obj.get("nama", "-"))
    else:
        return "-"

def _struktur_ke_kategori_spd(struktur: str, bidang: str = "") -> int:
    """Petakan struktur_rkap + bidang divisi ke nomor kategori SPD (untuk warna teks).
    Nilai struktur_rkap di DB: DIRUT, DIRUM, DIRTEK, DIROPS,
                                DEWAS_KETUA, DEWAS_ANGGOTA_1/2,
                                MANAJER, SUPERVISOR, STAF_PELAKSANA
    """
    s = (struktur or "").upper()
    b = (bidang or "").lower()
    if s in ("DIRUT", "DIRUM", "DIRTEK", "DIROPS"):
        return 1  # Direksi — biru
    elif "DEWAS" in s:
        return 4  # Dewan Pengawas — orange
    elif s in ("MANAJER", "SUPERVISOR", "STAF_PELAKSANA"):
        return 3 if "teknik" in b else 2  # Teknik=ungu, Administrasi=hijau
    elif s == "BANTUAN":
        return 5  # Bantuan — hitam (5 tidak ada di SPD_ROW_COLORS → default hitam)
    else:
        return 5  # default hitam

def _build_pembuka(disp: dict) -> str:
    """Bangun kalimat pembuka surat tugas dari data disposisi."""
    nomor   = disp.get("nomor", "").strip()
    dari    = disp.get("dari", "").strip()
    perihal = disp.get("perihal", "").strip()
    parts = []
    if dari:
        parts.append(f"surat dari {dari}")
    if nomor:
        parts.append(f"dengan Nomor Surat {nomor}")
    if perihal:
        parts.append(f"perihal {perihal}")
    return ", ".join(parts) if parts else ""

# ─── HELPER ────────────────────────────────────────────
def generate_nomor_visum(tanggal: date = None) -> str:
    tgl   = tanggal or date.today()
    tahun = tgl.year
    bulan = BULAN_ROMAWI[tgl.month - 1]
    res = db.table("visum").select("nomor_visum")\
        .like("nomor_visum", f"%/{tahun}-{KODE_VISUM}")\
        .execute()
    if res.data:
        max_urutan = max(
            int(v["nomor_visum"].split("/")[0])
            for v in res.data
            if v["nomor_visum"].split("/")[0].isdigit()
        )
        urutan = max_urutan + 1
    else:
        urutan = 1
    return f"{urutan:04d}/{KODE_STATIC}/{KODE_SEKPER}/{bulan}/{tahun}-{KODE_VISUM}"

def fmt_tgl_indo(tgl_str: str) -> str:
    """Format YYYY-MM-DD → DD/MM/YYYY (format Indonesia)."""
    if not tgl_str:
        return "-"
    try:
        return datetime.strptime(tgl_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return tgl_str

def format_rupiah(amount) -> str:
    if not amount:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

def get_nama_pegawai(pegawai_id: str, pegawai_map: dict) -> str:
    p = pegawai_map.get(pegawai_id)
    return p["nama"] if p else pegawai_id

def cek_bisa_complete(visum_id: str, tanpa_spd: bool = False) -> tuple:
    if tanpa_spd:
        return True, ""
    res_sppd = db.table("sppd").select("status")\
        .eq("visum_id", visum_id)\
        .neq("status", "cancelled")\
        .execute()
    if not res_sppd.data:
        return False, "Tidak ada SPPD aktif untuk visum ini."
    belum_selesai = [s for s in res_sppd.data if s["status"] not in ["realisasi", "completed"]]
    if belum_selesai:
        return False, f"{len(belum_selesai)} SPPD belum realisasi."
    return True, "Semua SPPD sudah realisasi."

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
st.title("📄 Manajemen Visum")
st.markdown("---")

tab1, tab4, tab2, tab3 = st.tabs(["📋 Daftar Visum", "📁 Kelola SPD", "➕ Buat Visum Baru", "🔍 Detail & Edit Visum"])

# ══════════════════════════════════════════════════════
# TAB 1: DAFTAR VISUM
# ══════════════════════════════════════════════════════
with tab1:
    st.subheader("Daftar Visum")

    res = db.table("visum").select("*").order("created_at", desc=True).execute()
    visum_list = res.data

    if not visum_list:
        st.info("Belum ada data visum.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            search = st.text_input("🔍 Cari nomor / tujuan", "")
        with col2:
            filter_status = st.selectbox("Filter Status",
                ["Semua", "draft", "active", "completed", "cancelled"])

        filtered = visum_list
        if search:
            filtered = [v for v in filtered if
                search.lower() in v["nomor_visum"].lower() or
                search.lower() in v["tujuan"].lower()]
        if filter_status != "Semua":
            filtered = [v for v in filtered if v["status"] == filter_status]

        st.caption(f"Menampilkan {len(filtered)} visum")

        import pandas as pd
        df = pd.DataFrame([{
            "Nomor Visum": v["nomor_visum"],
            "Tujuan": v["tujuan"],
            "Berangkat": fmt_tgl_indo(v["tanggal_berangkat"]),
            "Kembali": fmt_tgl_indo(v["tanggal_kembali"]),
            "Lama": f"{v['lama_hari']} hari",
            "Peserta": len(v.get("peserta") or []),
            "Disposisi": f"📎 {len(v.get('disposisi') or [])} surat" if v.get("disposisi") else "-",
            "Status": v["status"].upper(),
        } for v in filtered])

        st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════
# TAB 2: BUAT VISUM BARU
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Buat Visum Baru")

    # Setelah berhasil simpan → tampilkan sukses screen + tombol buat baru
    if st.session_state.get("visum_baru_berhasil"):
        hasil = st.session_state.visum_baru_berhasil
        st.success(f"✅ Visum **{hasil['nomor']}** berhasil dibuat!")
        st.info(f"📍 Lokasi: **{hasil['lokasi']}**")
        if hasil.get("tanpa_spd"):
            st.info("📋 Visum ini tidak menggunakan SPD — tidak ada SPPD yang dibuat.")

        if hasil.get("results"):
            pegawai_list_temp = get_all_pegawai()
            pegawai_map_temp  = {p["id"]: p for p in pegawai_list_temp}
            st.markdown("**Hasil Auto-Buat SPPD:**")
            for r in hasil["results"]:
                nama = get_nama_pegawai(r["pegawai_id"], pegawai_map_temp)
                if r["success"]:
                    st.success(f"✅ {nama} — {r['pesan']}")
                else:
                    st.warning(f"⚠️ {nama} — {r['pesan']}")

        if st.button("➕ Buat Visum Baru", use_container_width=True, type="primary"):
            del st.session_state["visum_baru_berhasil"]
            st.rerun()

    else:
        # ── Form buat visum ──
        nomor_preview = generate_nomor_visum()
        st.info(f"📌 Nomor Visum: **{nomor_preview}**")

        # ── Pilih SPD ──
        tanpa_spd_check = st.checkbox(
            "Tanpa SPD (perjalanan ini tidak ada pencairan dari PTMB)",
            help="Centang jika biaya perjalanan ditanggung sepenuhnya oleh pihak lain. Nomor visum tetap tercatat, tapi tidak ada SPD/SPPD yang dibuat."
        )
        spd_id_dipilih = None

        if not tanpa_spd_check:
            spd_list = get_spd_list_semua()
            if not spd_list:
                st.warning("⚠️ Belum ada SPD. Buat SPD terlebih dahulu di tab **📁 Kelola SPD**.")
                st.stop()

            spd_options = {
                f"{s['nomor_spd']} — {s['tanggal_spd']}": s["id"]
                for s in spd_list
            }
            spd_pilihan_key = st.selectbox(
                "📁 Pilih SPD *",
                options=list(spd_options.keys()),
                help="SPD harus dibuat terlebih dahulu di tab Kelola SPD"
            )
            spd_id_dipilih = spd_options[spd_pilihan_key]
        else:
            st.info("ℹ️ Visum ini tidak menggunakan SPD — tidak ada pencairan SPPD dari PTMB.")

        pegawai_list   = get_all_pegawai()
        pegawai_options = {f"{p['nip']} - {p['nama']}": p["id"] for p in pegawai_list}

        with st.form("form_visum", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                tanggal_visum     = st.date_input("Tanggal Visum", value=date.today())
                tanggal_berangkat = st.date_input("Tanggal Berangkat", value=date.today())
                tanggal_kembali   = st.date_input("Tanggal Kembali", value=date.today())

            with col2:
                tujuan_pilihan = st.selectbox("Kota Tujuan", [""] + KOTA_OPTIONS,
                                              format_func=lambda x: "— Pilih kota —" if x == "" else x)
                tujuan_manual  = st.text_input("Atau ketik kota lain",
                                               placeholder="Isi jika kota tidak ada di daftar atas")
                tujuan = tujuan_manual.strip() if tujuan_manual.strip() else tujuan_pilihan

                keperluan = st.text_area("Keperluan / Maksud Perjalanan *", height=80)

            st.markdown("**Peserta Perjalanan Dinas**")
            peserta_selected = st.multiselect(
                "Pilih Peserta",
                options=list(pegawai_options.keys()),
                placeholder="Ketik nama atau NIP untuk mencari..."
            )

            st.markdown("**Surat Disposisi** _(opsional — bisa ditambah lebih lanjut setelah disimpan)_")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                nomor_disposisi   = st.text_input("Nomor Surat Disposisi", placeholder="Contoh: 123/DIR/II/2026")
                dari_disposisi    = st.text_input("Dari (Pengirim Surat)", placeholder="Contoh: Kementerian PUPR")
                perihal_disposisi = st.text_input("Perihal Surat Disposisi", placeholder="Contoh: Undangan Rapat Koordinasi")
            with col_d2:
                link_disposisi = st.text_input("Link File Disposisi (Google Drive)", placeholder="https://drive.google.com/...")
                st.caption("Disposisi tambahan bisa ditambahkan di tab Detail & Edit setelah visum disimpan.")

            submitted = st.form_submit_button("💾 Simpan Visum", use_container_width=True)

            if submitted:
                if not tujuan:
                    st.error("❌ Kota tujuan wajib diisi!")
                elif not keperluan:
                    st.error("❌ Keperluan perjalanan wajib diisi!")
                elif not peserta_selected:
                    st.error("❌ Minimal 1 peserta harus dipilih!")
                elif tanggal_kembali < tanggal_berangkat:
                    st.error("❌ Tanggal kembali tidak boleh sebelum tanggal berangkat!")
                else:
                    lama_hari   = (tanggal_kembali - tanggal_berangkat).days + 1
                    peserta_ids = [pegawai_options[p] for p in peserta_selected]
                    lokasi_info = detect_lokasi(tujuan)

                    try:
                        nomor_final = generate_nomor_visum(tanggal_visum)

                        res_visum = db.table("visum").insert({
                            "nomor_visum":       nomor_final,
                            "tanggal_visum":     str(tanggal_visum),
                            "tujuan":            tujuan,
                            "tanggal_berangkat": str(tanggal_berangkat),
                            "tanggal_kembali":   str(tanggal_kembali),
                            "lama_hari":         lama_hari,
                            "keperluan":         keperluan,
                            "peserta":           peserta_ids,
                            "status":     "active",
                            "tanpa_spd":  tanpa_spd_check,
                            "disposisi":  [{"nomor": nomor_disposisi, "dari": dari_disposisi, "perihal": perihal_disposisi, "link": link_disposisi}]
                                          if (nomor_disposisi or dari_disposisi or perihal_disposisi or link_disposisi) else [],
                        }).execute()

                        visum_baru = res_visum.data[0]

                        if not tanpa_spd_check:
                            with st.spinner("Membuat SPPD untuk semua peserta..."):
                                results = auto_buat_semua_sppd(visum_baru, lokasi_info["lokasi_id"], spd_id_dipilih)
                        else:
                            results = []

                        # Simpan hasil ke session_state → rerun akan tampilkan halaman sukses (form ter-reset)
                        st.session_state["visum_baru_berhasil"] = {
                            "nomor":     nomor_final,
                            "lokasi":    lokasi_info["lokasi_nama"],
                            "results":   results,
                            "tanpa_spd": tanpa_spd_check,
                        }
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Gagal menyimpan: {e}")

# ══════════════════════════════════════════════════════
# TAB 3: DETAIL & EDIT VISUM
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Detail & Edit Visum")

    res_all    = db.table("visum").select("*").order("created_at", desc=True).execute()
    visum_semua = res_all.data

    if not visum_semua:
        st.info("Belum ada data visum.")
    else:
        col_filter, _ = st.columns([2, 2])
        with col_filter:
            show_completed = st.checkbox("Tampilkan visum completed", value=False)

        visum_filtered = visum_semua
        if not show_completed:
            visum_filtered = [v for v in visum_semua if v["status"] != "completed"]

        if not visum_filtered:
            st.info("Tidak ada visum aktif. Centang 'Tampilkan visum completed' untuk melihat semua.")
        else:
            visum_keys = [
                f"{v['nomor_visum']} — {v['tujuan']} [{v['status'].upper()}]"
                for v in visum_filtered
            ]
            visum_by_key = {
                f"{v['nomor_visum']} — {v['tujuan']} [{v['status'].upper()}]": v
                for v in visum_filtered
            }

            selected = st.selectbox("Pilih Nomor Visum", visum_keys, key="detail_visum_select")

            if selected:
                v = visum_by_key[selected]
                visum_id = v["id"]
                is_tanpa_spd = v.get("tanpa_spd", False)

                # ── Info Visum ──
                col1, col2, col3 = st.columns(3)
                col1.metric("Tujuan", v["tujuan"])
                col2.metric("Lama Perjalanan", f"{v['lama_hari']} hari")
                col3.metric("Status", v["status"].upper())

                st.markdown(f"**Keperluan:** {v['keperluan']}")
                st.markdown(f"**Berangkat:** {fmt_tgl_indo(v['tanggal_berangkat'])} → **Kembali:** {fmt_tgl_indo(v['tanggal_kembali'])}")

                lokasi_info = detect_lokasi(v["tujuan"])
                st.info(f"📍 Lokasi: **{lokasi_info['lokasi_nama']}**")
                if is_tanpa_spd:
                    st.warning("📋 Visum ini **tidak menggunakan SPD** — tidak ada pencairan/realisasi SPPD dari PTMB.")

                # ── Edit Tanggal ──
                if v["status"] not in ["completed", "cancelled"]:
                    with st.expander("✏️ Edit Tanggal Visum"):
                        with st.form(f"form_edit_tanggal_{visum_id}"):
                            col_t1, col_t2, col_t3 = st.columns(3)
                            with col_t1:
                                edit_tgl_visum = st.date_input(
                                    "Tanggal Surat",
                                    value=datetime.strptime(v["tanggal_visum"], "%Y-%m-%d").date()
                                          if v.get("tanggal_visum") else date.today()
                                )
                            with col_t2:
                                edit_tgl_berangkat = st.date_input(
                                    "Tanggal Berangkat",
                                    value=datetime.strptime(v["tanggal_berangkat"], "%Y-%m-%d").date()
                                )
                            with col_t3:
                                edit_tgl_kembali = st.date_input(
                                    "Tanggal Kembali",
                                    value=datetime.strptime(v["tanggal_kembali"], "%Y-%m-%d").date()
                                )
                            simpan_tgl = st.form_submit_button("💾 Simpan Tanggal", use_container_width=True)
                            if simpan_tgl:
                                if edit_tgl_kembali < edit_tgl_berangkat:
                                    st.error("❌ Tanggal kembali tidak boleh sebelum tanggal berangkat!")
                                else:
                                    lama_baru = (edit_tgl_kembali - edit_tgl_berangkat).days + 1
                                    db.table("visum").update({
                                        "tanggal_visum":     str(edit_tgl_visum),
                                        "tanggal_berangkat": str(edit_tgl_berangkat),
                                        "tanggal_kembali":   str(edit_tgl_kembali),
                                        "lama_hari":         lama_baru,
                                    }).eq("id", visum_id).execute()
                                    st.success(f"✅ Tanggal diperbarui! Lama: {lama_baru} hari.")
                                    st.rerun()

                # ── Surat Disposisi ──
                st.markdown("---")
                st.markdown("#### 📎 Surat Disposisi")

                sk = f"disp_{visum_id}"
                if sk not in st.session_state:
                    st.session_state[sk] = list(v.get("disposisi") or [])

                disp_list = st.session_state[sk]

                if not disp_list:
                    st.caption("Belum ada surat disposisi.")
                else:
                    hc1, hc2, hc3, hc4, _ = st.columns([2, 2, 2, 2, 1])
                    hc1.caption("Nomor Surat")
                    hc2.caption("Dari")
                    hc3.caption("Perihal")
                    hc4.caption("Link Drive")
                    for i, disp in enumerate(disp_list):
                        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
                        with c1:
                            st.text_input("Nomor", value=disp.get("nomor",""),
                                          key=f"dn_{visum_id}_{i}", label_visibility="collapsed",
                                          placeholder="Nomor surat")
                        with c2:
                            st.text_input("Dari", value=disp.get("dari",""),
                                          key=f"dd_{visum_id}_{i}", label_visibility="collapsed",
                                          placeholder="Pengirim surat")
                        with c3:
                            st.text_input("Perihal", value=disp.get("perihal",""),
                                          key=f"dp_{visum_id}_{i}", label_visibility="collapsed",
                                          placeholder="Perihal surat")
                        with c4:
                            st.text_input("Link", value=disp.get("link",""),
                                          key=f"dl_{visum_id}_{i}", label_visibility="collapsed",
                                          placeholder="Link Google Drive")
                        with c5:
                            if disp.get("link"):
                                st.link_button("🔗", disp["link"], help="Buka file")
                            if st.button("🗑️", key=f"ddel_{visum_id}_{i}", help="Hapus"):
                                st.session_state[sk].pop(i)
                                for j in range(len(st.session_state[sk]) + 2):
                                    for pfx in ["dn_", "dd_", "dp_", "dl_"]:
                                        st.session_state.pop(f"{pfx}{visum_id}_{j}", None)
                                st.rerun()

                col_dadd, col_dsave, _ = st.columns([2, 2, 2])
                with col_dadd:
                    if st.button("➕ Tambah Disposisi", use_container_width=True, key=f"dadd_{visum_id}"):
                        st.session_state[sk].append({"nomor": "", "perihal": "", "link": ""})
                        st.rerun()
                with col_dsave:
                    if st.button("💾 Simpan Disposisi", use_container_width=True,
                                 type="primary", key=f"dsave_{visum_id}"):
                        to_save = []
                        for i in range(len(disp_list)):
                            n = st.session_state.get(f"dn_{visum_id}_{i}", "").strip()
                            d = st.session_state.get(f"dd_{visum_id}_{i}", "").strip()
                            p = st.session_state.get(f"dp_{visum_id}_{i}", "").strip()
                            l = st.session_state.get(f"dl_{visum_id}_{i}", "").strip()
                            if n or d or p or l:
                                to_save.append({"nomor": n, "dari": d, "perihal": p, "link": l})
                        db.table("visum").update({"disposisi": to_save})\
                            .eq("id", visum_id).execute()
                        st.session_state[sk] = to_save
                        for j in range(len(to_save) + 2):
                            for pfx in ["dn_", "dd_", "dp_", "dl_"]:
                                st.session_state.pop(f"{pfx}{visum_id}_{j}", None)
                        st.success(f"✅ {len(to_save)} disposisi disimpan!")
                        st.rerun()

                st.markdown("---")

                # ── Daftar Peserta ──
                pegawai_all = get_all_pegawai()
                pegawai_map = {p["id"]: p for p in pegawai_all}
                divisi_map_local = {p["divisi"]["id"]: p["divisi"] for p in pegawai_all if p.get("divisi") and p["divisi"].get("id")}
                # Normalkan peserta_ids: JSONB bisa return berbagai format:
                # - string UUID (dari visum baru via UI)
                # - {"id": "uuid"}
                # - {"pegawai_id": "uuid", "nama": "..."} (dari import histori)
                _raw_peserta = v.get("peserta") or []
                peserta_ids = []
                for p in _raw_peserta:
                    if isinstance(p, dict):
                        pid = p.get("id") or p.get("pegawai_id")
                    else:
                        pid = p
                    if pid:
                        peserta_ids.append(pid)

                st.markdown("#### 👥 Peserta Perjalanan")
                if peserta_ids:
                    for pid in peserta_ids:
                        p = pegawai_map.get(pid)
                        if p:
                            jabatan_nama = (p.get("jabatan") or {}).get("nama", "-")
                            st.markdown(f"- **{p['nama']}** _{jabatan_nama}_")
                        else:
                            st.markdown(f"- _(ID tidak ditemukan: {pid})_")
                else:
                    st.caption("Tidak ada peserta.")

                # ── Edit Peserta (hanya kalau visum masih aktif) ──
                if v["status"] not in ["completed", "cancelled"]:
                    st.markdown("---")
                    st.markdown("#### ✏️ Edit Peserta")

                    pegawai_options_all = {f"{p['nip']} - {p['nama']}": p["id"] for p in pegawai_all}

                    # Key multiselect harus include visum_id supaya reset saat ganti visum
                    multiselect_key = f"edit_peserta_{visum_id}"

                    # Pre-select peserta saat ini — set default setiap kali visum berubah
                    peserta_keys_current = [
                        k for k, pid in pegawai_options_all.items() if pid in peserta_ids
                    ]

                    peserta_baru_keys = st.multiselect(
                        "Ubah Peserta",
                        options=list(pegawai_options_all.keys()),
                        default=peserta_keys_current,
                        key=multiselect_key
                    )
                    peserta_baru_ids = [pegawai_options_all[k] for k in peserta_baru_keys]

                    ditambah = [pid for pid in peserta_baru_ids if pid not in peserta_ids]
                    dihapus  = [pid for pid in peserta_ids if pid not in peserta_baru_ids]

                    if ditambah:
                        st.success(f"➕ Akan ditambah: {', '.join([get_nama_pegawai(p, pegawai_map) for p in ditambah])}")
                    if dihapus:
                        st.warning(f"➖ Akan dihapus: {', '.join([get_nama_pegawai(p, pegawai_map) for p in dihapus])}")

                    ada_perubahan = set(peserta_baru_ids) != set(peserta_ids)

                    if ada_perubahan:
                        if st.button("💾 Simpan Perubahan Peserta", use_container_width=True):
                            if is_tanpa_spd:
                                # Visum tanpa SPD — tidak ada SPPD yang perlu disinkronisasi
                                db.table("visum").update({"peserta": peserta_baru_ids})\
                                    .eq("id", visum_id).execute()
                                st.success("✅ Peserta diperbarui.")
                                st.rerun()
                            else:
                                # Cari spd_id dari sppd yang sudah ada untuk visum ini
                                res_sppd_spd = db.table("sppd").select("spd_id")\
                                    .eq("visum_id", visum_id).limit(1).execute()
                                spd_id_visum = res_sppd_spd.data[0]["spd_id"] if res_sppd_spd.data else None
                                if not spd_id_visum:
                                    st.error("❌ Tidak bisa sinkronisasi — visum ini belum punya SPD. Gunakan tab Kelola SPD untuk assign.")
                                    st.stop()
                                with st.spinner("Sinkronisasi SPPD..."):
                                    hasil = sync_sppd_peserta(v, peserta_baru_ids, lokasi_info["lokasi_id"], spd_id_visum)

                                db.table("visum").update({"peserta": peserta_baru_ids})\
                                    .eq("id", visum_id).execute()

                                for r in hasil["ditambah"]:
                                    nama = get_nama_pegawai(r["pegawai_id"], pegawai_map)
                                    if r["success"]:
                                        st.success(f"✅ {nama} — SPPD dibuat")
                                    else:
                                        st.warning(f"⚠️ {nama} — {r['pesan']}")

                                for r in hasil["dihapus"]:
                                    nama = get_nama_pegawai(r["pegawai_id"], pegawai_map)
                                    st.info(f"🗑️ {nama} — SPPD di-cancel")

                                for r in hasil["diblok"]:
                                    nama = get_nama_pegawai(r["pegawai_id"], pegawai_map)
                                    st.error(f"🚫 {nama} — {r['pesan']}")

                                st.rerun()
                    else:
                        st.caption("Tidak ada perubahan peserta.")

                st.markdown("---")

                # ── 🖨️ PRINT DOKUMEN ──
                st.markdown("#### 🖨️ Print Dokumen")

                # Ambil data peserta lengkap untuk PDF
                peserta_pdf = []
                for pid in peserta_ids:
                    p = pegawai_map.get(pid)
                    if p:
                        peserta_pdf.append({
                            "nama":    p["nama"],
                            "nip":     p.get("nip", "-"),
                            "jabatan": (p.get("jabatan") or {}).get("nama", "-"),
                            "divisi":  (p.get("divisi") or {}).get("nama", "-"),
                            "level":   (p.get("jabatan") or {}).get("level", 0),
                        })
                # Sort: jabatan tertinggi dulu, kalau sama levelnya urut nip
                peserta_pdf.sort(key=lambda x: (-x["level"], x["nip"]))
                
                # Ambil data SPD via sppd (visum bisa share SPD dengan visum lain)
                res_spd_ref = db.table("sppd").select("spd_id")\
                    .eq("visum_id", visum_id).neq("status", "cancelled").limit(1).execute()
                spd_pdf = None
                if res_spd_ref.data and res_spd_ref.data[0].get("spd_id"):
                    spd_pdf = get_spd_by_id(res_spd_ref.data[0]["spd_id"])

                col_p1, col_p2, col_p3 = st.columns(3)

                # ── Tombol Visum ──
                with col_p1:
                    if st.button("📄 Download Visum", use_container_width=True, key=f"btn_visum_pdf_{visum_id}"):
                        data_visum = {
                            "nomor":            v["nomor_visum"],
                            "tanggal":          datetime.strptime(v["tanggal_visum"], "%Y-%m-%d").date() if v.get("tanggal_visum") else date.today(),
                            "nama_pegawai":     peserta_pdf[0]["nama"].title() if peserta_pdf else "-",
                            "jabatan":          format_jabatan_divisi(peserta_pdf[0]["jabatan"], peserta_pdf[0]["divisi"]) if peserta_pdf else "-",
                            "maksud":           v.get("keperluan", ""),
                            "alat_angkutan":    "Umum",
                            "tempat_berangkat": "Balikpapan",
                            "tempat_tujuan":    v["tujuan"],
                            "lama_hari":        f"{v['lama_hari']} hari",
                            "tgl_berangkat":    datetime.strptime(v["tanggal_berangkat"], "%Y-%m-%d").date(),
                            "tgl_kembali":      datetime.strptime(v["tanggal_kembali"],   "%Y-%m-%d").date(),
                            "peserta_ikut":     [
                                f"{p['nama'].title()} ({jab})" if (jab := format_jabatan_divisi(p['jabatan'], p['divisi'])) else p['nama'].title()
                                for p in peserta_pdf[1:]
                            ],
                            "ttd_nama":         "Dr. SAHARUDDIN, M.M.",
                        }
                        pdf_bytes = generate_visum(data_visum).read()
                        st.download_button(
                            label="⬇️ Unduh Visum PDF",
                            data=pdf_bytes,
                            file_name=f"Visum_{v['nomor_visum'].replace('/','_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"dl_visum_{visum_id}"
                        )

                # ── Tombol Surat Tugas ──
                with col_p2:
                    if st.button("📋 Download Surat Tugas", use_container_width=True, key=f"btn_st_pdf_{visum_id}"):
                        data_st = {
                            "nomor":    "/".join(["____"] + v["nomor_visum"].replace("-J", "-F").split("/")[1:]),
                            "tanggal":  datetime.strptime(v["tanggal_visum"], "%Y-%m-%d").date() if v.get("tanggal_visum") else date.today(),
                            "pembuka":  (
                            _build_pembuka(v["disposisi"][0])
                            if v.get("disposisi") and (v["disposisi"][0].get("nomor") or v["disposisi"][0].get("perihal"))
                            else f"Perihal {v.get('keperluan','')}"
                        ),
                            "peserta":  [
                                {
                                    "nama":    pegawai_map[pid]["nama"].title(),
                                    "nip":     "" if (
                                        (pegawai_map[pid].get("jabatan") or {}).get("nama", "").upper().startswith("TAMU")
                                        or (pegawai_map[pid].get("jabatan") or {}).get("struktur_rkap", "") in
                                           ("DIRUT","DIRUM","DIRTEK","DIROPS","DEWAS_KETUA","DEWAS_ANGGOTA","DEWAS_ANGGOTA_1","DEWAS_ANGGOTA_2")
                                    ) else pegawai_map[pid].get("nip", "-"),
                                    "jabatan": format_jabatan_divisi(
                                        (pegawai_map[pid].get("jabatan") or {}).get("nama", "-"),
                                        (pegawai_map[pid].get("divisi") or {}).get("nama", "-"),
                                    ),
                                    "divisi":  get_divisi_label_surat_tugas(
                                        (pegawai_map[pid].get("jabatan") or {}).get("nama", "-"),
                                        pegawai_map[pid].get("divisi"),
                                        divisi_map_local,
                                    ),
                                }
                                for pid in sorted(
                                    [pid for pid in peserta_ids if pid in pegawai_map
                                     and (pegawai_map[pid].get("jabatan") or {}).get("struktur_rkap") not in
                                         {"DIRUT","DEWAS_KETUA","DEWAS_ANGGOTA","DEWAS_ANGGOTA_1","DEWAS_ANGGOTA_2"}
                                     and not (pegawai_map[pid].get("jabatan") or {}).get("nama", "").upper().startswith("TAMU")],
                                    key=lambda pid: (
                                        -(pegawai_map[pid].get("jabatan") or {}).get("level", 0),
                                        pegawai_map[pid].get("nip", "")
                                    )
                                )
                            ],
                            "tujuan":   (
                                v["disposisi"][0].get("perihal", "")
                                if v.get("disposisi") and v["disposisi"][0].get("perihal")
                                else v.get("keperluan", "")
                            ),
                            "durasi":   v["lama_hari"],
                            "waktu":    fmt_waktu_surat_tugas(v['tanggal_berangkat'], v['tanggal_kembali']),
                            "tempat":   v["tujuan"],
                            "target":   "Wajib Untuk Menyerahkan Laporan Perjalanan Dinas Kepada Direktur Utama Perumda Tirta Manuntung Balikpapan.",
                            "ttd_nama": "Dr. SAHARUDDIN, M.M.",
                        }
                        pdf_bytes = generate_surat_tugas(data_st).read()
                        st.download_button(
                            label="⬇️ Unduh Surat Tugas PDF",
                            data=pdf_bytes,
                            file_name=f"SuratTugas_{v['nomor_visum'].replace('/','_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"dl_st_{visum_id}"
                        )

                # ── Tombol SPD ──
                with col_p3:
                    if spd_pdf:
                        if st.button("💰 Download SPD", use_container_width=True, key=f"btn_spd_pdf_{visum_id}"):
                            # Susun kategori dari data SPD
                            lokasi_nama = lokasi_info.get("lokasi_nama", "")
                            lokasi_lbl  = f"Biaya Perjalanan Dinas di {'Luar' if 'Luar' in lokasi_nama else 'Dalam'} Daerah KALTIM"
                            kategori_spd = [
                                {"no": 1, "uraian": "Direksi",                     "total": spd_pdf.get("total_direksi", 0),        "kode": "96.08.41"},
                                {"no": 2, "uraian": "Bagian Administrasi/Keuangan","total": spd_pdf.get("total_administrasi", 0),    "kode": "96.08.42"},
                                {"no": 3, "uraian": "Bagian Teknik",               "total": spd_pdf.get("total_teknik", 0),          "kode": "96.08.43"},
                                {"no": 4, "uraian": "Dewan Pengawas",              "total": spd_pdf.get("total_dewas", 0),           "kode": "96.08.30"},
                                {"no": 5, "uraian": "Bantuan",                     "total": spd_pdf.get("total_bantuan", 0),         "kode": "96.08.92"},
                            ]
                            # Ambil daftar peserta + biaya dari sppd
                            res_sppd_pdf = db.table("sppd")\
                                .select("*, pegawai!sppd_pegawai_id_fkey(nama, divisi(id, nama, parent_id, bidang), jabatan(nama, level, struktur_rkap))")\
                                .eq("spd_id", spd_pdf["id"])\
                                .neq("status", "cancelled")\
                                .execute()
                            peserta_spd_raw = []
                            for sp in res_sppd_pdf.data:
                                peg = sp.get("pegawai") or {}
                                jab = peg.get("jabatan") or {}
                                div = peg.get("divisi") or {}
                                # Hitung bidang (cek parent jika divisi sendiri tidak punya bidang)
                                bidang_raw = div.get("bidang") or divisi_map_local.get(div.get("parent_id"), {}).get("bidang")
                                bidang_resolved = bidang_raw.title() if bidang_raw else ""
                                peserta_spd_raw.append({
                                    "nama":           peg.get("nama", "-"),
                                    "jabatan":        "" if (jab.get("nama") or "").upper().startswith("TAMU") else jab.get("nama", "-"),
                                    "divisi_nama":    div.get("nama", "-"),
                                    "level":          jab.get("level", 0),
                                    "struktur_rkap":  jab.get("struktur_rkap", ""),
                                    "bidang":         bidang_resolved,
                                    "biaya":          sp.get("total_biaya") or sp.get("subtotal_uang_saku") or 0,
                                })
                            peserta_spd_raw.sort(key=lambda x: (
                                _struktur_ke_kategori_spd(x["struktur_rkap"], x["bidang"]),  # 1=Direksi … 5=Bantuan
                                0 if x["struktur_rkap"] == "DIRUT" else 1,                   # Dirut selalu pertama
                                -x["level"],                                                  # dalam kategori: level tertinggi dulu
                            ))
                            peserta_spd = [
                                {
                                    "no":          i,
                                    "nama":        p["nama"].title(),
                                    "jabatan":     format_jabatan_divisi(p["jabatan"], p["divisi_nama"]),
                                    "biaya":       p["biaya"],
                                    "kategori_no": _struktur_ke_kategori_spd(p["struktur_rkap"], p["bidang"]),
                                }
                                for i, p in enumerate(peserta_spd_raw, 1)
                            ]
                            data_spd = {
                                "nomor":          spd_pdf["nomor_spd"],
                                "tanggal":        datetime.strptime(v["tanggal_visum"], "%Y-%m-%d").date() if v.get("tanggal_visum") else date.today(),
                                "lokasi_label":   lokasi_lbl,
                                "tahun":          date.today().year,
                                "kategori":       kategori_spd,
                                "grand_total":    spd_pdf.get("grand_total", 0),
                                "peserta":        peserta_spd,
                                "ttd_manajer_sek": "Abdul Ramli",
                                "ttd_spv_sek":    "Ganden Aditera. I",
                                "ttd_dirut":      "Dr. Saharuddin, M.M",
                            }
                            pdf_bytes = generate_spd(data_spd).read()
                            st.download_button(
                                label="⬇️ Unduh SPD PDF",
                                data=pdf_bytes,
                                file_name=f"SPD_{spd_pdf['nomor_spd'].replace('/','_')}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"dl_spd_{visum_id}"
                            )
                    else:
                        if is_tanpa_spd:
                            st.caption("Visum ini tidak menggunakan SPD.")
                        else:
                            st.caption("SPD belum tersedia.")

                st.markdown("---")

                # ── Update Status Visum ──
                st.markdown("#### 🔄 Update Status Visum")

                if v["status"] == "completed":
                    st.success("✅ Visum ini sudah COMPLETED dan tidak dapat diubah.")

                elif v["status"] == "cancelled":
                    st.error("❌ Visum ini sudah CANCELLED.")

                else:
                    status_tersedia = ["active", "cancelled"]
                    bisa_complete, alasan_complete = cek_bisa_complete(visum_id, tanpa_spd=is_tanpa_spd)
                    if bisa_complete:
                        status_tersedia.append("completed")

                    col_status, col_btn = st.columns([2, 1])
                    with col_status:
                        idx_current = status_tersedia.index(v["status"]) if v["status"] in status_tersedia else 0
                        new_status  = st.selectbox("Status Baru", status_tersedia, index=idx_current)
                    with col_btn:
                        st.markdown("<br>", unsafe_allow_html=True)
                        update_btn = st.button("💾 Update Status", use_container_width=True)

                    if not bisa_complete and v["status"] != "cancelled":
                        st.caption(f"ℹ️ Completed belum tersedia: {alasan_complete}")

                    if update_btn:
                        if new_status == "cancelled":
                            if is_tanpa_spd:
                                db.table("visum").update({"status": "cancelled"})\
                                    .eq("id", visum_id).execute()
                                st.success("✅ Visum dibatalkan.")
                                st.rerun()
                            else:
                                with st.spinner("Membatalkan semua SPPD..."):
                                    hasil_cancel = cancel_semua_sppd_visum(visum_id)

                                if hasil_cancel["diblok"]:
                                    st.error("❌ Tidak bisa cancel visum — ada SPPD yang sudah REALISASI:")
                                    for blok in hasil_cancel["diblok"]:
                                        st.error(f"   • {blok['pesan']}")
                                else:
                                    db.table("visum").update({"status": "cancelled"})\
                                        .eq("id", visum_id).execute()
                                    st.success(f"✅ Visum dibatalkan. {hasil_cancel['dicancelled']} SPPD di-cancel.")
                                    st.rerun()
                        else:
                            db.table("visum").update({"status": new_status})\
                                .eq("id", visum_id).execute()
                            st.success(f"✅ Status berhasil diupdate ke {new_status.upper()}!")
                            st.rerun()

# ══════════════════════════════════════════════════════
# TAB 4: KELOLA SPD
# ══════════════════════════════════════════════════════
with tab4:
    st.subheader("Kelola SPD")

    # ── A. Buat SPD Baru ──
    st.markdown("#### ➕ Buat SPD Baru")
    with st.form("form_buat_spd"):
        col_spd1, col_spd2 = st.columns([2, 3])
        with col_spd1:
            tgl_spd_baru = st.date_input("Tanggal SPD", value=date.today())
        with col_spd2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption("Nomor SPD akan di-generate otomatis (urutan lanjutan dari yang terakhir).")
        simpan_spd = st.form_submit_button("💾 Buat SPD", use_container_width=True)
        if simpan_spd:
            try:
                spd_baru = create_spd_baru(tgl_spd_baru)
                st.success(f"✅ SPD **{spd_baru['nomor_spd']}** berhasil dibuat!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Gagal membuat SPD: {e}")

    st.markdown("---")

    # ── B. Daftar SPD ──
    st.markdown("#### 📋 Daftar SPD")
    spd_semua = get_spd_list_semua()
    if not spd_semua:
        st.info("Belum ada data SPD.")
    else:
        import pandas as pd
        # Hitung jumlah visum per SPD dari tabel sppd
        spd_ids_all = [s["id"] for s in spd_semua]
        res_count_visum = db.table("sppd").select("spd_id, visum_id")\
            .in_("spd_id", spd_ids_all).neq("status", "cancelled").execute()
        # Count visum unik per spd_id
        visum_per_spd: dict = {}
        for row in (res_count_visum.data or []):
            sid = row["spd_id"]
            vid = row["visum_id"]
            if sid not in visum_per_spd:
                visum_per_spd[sid] = set()
            visum_per_spd[sid].add(vid)

        df_spd = pd.DataFrame([{
            "Nomor SPD":   s["nomor_spd"],
            "Tanggal":     fmt_tgl_indo(s["tanggal_spd"]),
            "Status":      s["status"].upper(),
            "Jml Visum":   len(visum_per_spd.get(s["id"], set())),
        } for s in spd_semua])
        st.dataframe(df_spd, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── B2. Edit SPD Eksisting ──
    st.markdown("#### ✏️ Edit SPD Eksisting")
    st.caption("Gunakan ini untuk koreksi tanggal atau nomor SPD historis.")

    if not spd_semua:
        st.info("Belum ada data SPD.")
    else:
        spd_edit_options = {
            f"{s['nomor_spd']} — {fmt_tgl_indo(s['tanggal_spd'])}": s
            for s in spd_semua
        }
        spd_edit_key = st.selectbox(
            "Pilih SPD yang akan diedit",
            options=list(spd_edit_options.keys()),
            key="edit_spd_select"
        )
        spd_edit = spd_edit_options[spd_edit_key]

        with st.form("form_edit_spd"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                tgl_spd_edit = st.date_input(
                    "Tanggal SPD",
                    value=datetime.strptime(spd_edit["tanggal_spd"], "%Y-%m-%d").date()
                )
            with col_e2:
                nomor_spd_edit = st.text_input(
                    "Nomor SPD",
                    value=spd_edit["nomor_spd"]
                )
            simpan_edit_spd = st.form_submit_button("💾 Simpan Perubahan SPD", use_container_width=True)
            if simpan_edit_spd:
                if not nomor_spd_edit.strip():
                    st.error("❌ Nomor SPD tidak boleh kosong!")
                else:
                    try:
                        db.table("spd").update({
                            "tanggal_spd": str(tgl_spd_edit),
                            "nomor_spd":   nomor_spd_edit.strip(),
                        }).eq("id", spd_edit["id"]).execute()
                        st.success(f"✅ SPD berhasil diupdate → **{nomor_spd_edit.strip()}** ({fmt_tgl_indo(str(tgl_spd_edit))})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal update SPD: {e}")

    st.markdown("---")

    # ── C. Assign Visum ke SPD ──
    st.markdown("#### 🔗 Assign Visum ke SPD")
    st.caption("Gunakan fitur ini untuk mapping data historis atau koreksi salah assign.")

    if not spd_semua:
        st.warning("Belum ada SPD. Buat SPD terlebih dahulu di atas.")
    else:
        res_visum_all = db.table("visum").select("id, nomor_visum, keperluan, tujuan, status")\
            .order("created_at", desc=True).execute()
        visum_all = res_visum_all.data or []

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            spd_assign_options = {
                f"{s['nomor_spd']} — {fmt_tgl_indo(s['tanggal_spd'])}": s["id"]
                for s in spd_semua
            }
            spd_assign_key = st.selectbox(
                "Pilih SPD Tujuan",
                options=list(spd_assign_options.keys()),
                key="assign_spd_select"
            )
            spd_assign_id = spd_assign_options[spd_assign_key]

        with col_a2:
            visum_assign_options = {
                f"{v['nomor_visum']} — {v['tujuan']} [{v['status'].upper()}]": v["id"]
                for v in visum_all
            }
            visum_assign_key = st.selectbox(
                "Pilih Visum",
                options=list(visum_assign_options.keys()),
                key="assign_visum_select"
            )
            visum_assign_id = visum_assign_options[visum_assign_key]

        # Tampilkan info SPD saat ini untuk visum yang dipilih
        res_sppd_cek = db.table("sppd").select("spd_id, spd(nomor_spd)")\
            .eq("visum_id", visum_assign_id).neq("status", "cancelled").limit(1).execute()
        if res_sppd_cek.data and res_sppd_cek.data[0].get("spd_id"):
            nomor_spd_lama = (res_sppd_cek.data[0].get("spd") or {}).get("nomor_spd", res_sppd_cek.data[0]["spd_id"])
            if res_sppd_cek.data[0]["spd_id"] == spd_assign_id:
                st.info(f"ℹ️ Visum ini sudah di SPD **{nomor_spd_lama}** (tidak perlu diubah).")
            else:
                st.warning(f"SPD saat ini: **{nomor_spd_lama}** → akan dipindah ke **{spd_assign_key.split(' — ')[0]}**")
        else:
            st.caption("Visum ini belum punya SPPD — assign akan berlaku saat visum dipakai.")

        if st.button("💾 Simpan Assignment", use_container_width=True, type="primary", key="btn_assign"):
            with st.spinner("Mengupdate SPPD..."):
                hasil_assign = assign_visum_ke_spd(visum_assign_id, spd_assign_id)
            if hasil_assign["updated"] > 0:
                st.success(f"✅ {hasil_assign['pesan']}")
            else:
                st.info(f"ℹ️ {hasil_assign['pesan']}")