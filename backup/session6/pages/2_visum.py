import streamlit as st
from utils.database import get_all_pegawai, get_all_divisi
from supabase import create_client
from dotenv import load_dotenv
from datetime import date
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
KODE_VISUM = "J"
KODE_SPPD = "O"

KOTA_OPTIONS = [
    # Dalam Kaltim
    "Samarinda", "Balikpapan", "Bontang", "Kutai Kartanegara",
    "Berau", "Paser", "Penajam Paser Utara", "Mahakam Ulu",
    # Luar Kaltim - Kalimantan
    "Banjarmasin", "Palangka Raya", "Pontianak",
    # Jawa
    "Jakarta", "Surabaya", "Bandung", "Yogyakarta", "Semarang",
    # Sulawesi
    "Makassar", "Manado", "Palu",
    # Lainnya
    "Medan", "Palembang", "Denpasar", "Lombok",
    "Lainnya (ketik manual)"
]

# ─── HELPER: Generate Nomor ─────────────────────────────
def generate_nomor(kode_akhir: str) -> str:
    tahun = date.today().year
    bulan_romawi = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]
    bulan = bulan_romawi[date.today().month - 1]
    
    # Hitung nomor urut tahun ini
    tabel = "visum" if kode_akhir == KODE_VISUM else "sppd"
    field = "nomor_visum" if kode_akhir == KODE_VISUM else "nomor_sppd"
    
    res = db.table(tabel).select(field)\
        .like(field, f"%/{tahun}-{kode_akhir}")\
        .execute()
    
    urutan = len(res.data) + 1
    nomor = f"{urutan:04d}/{KODE_STATIC}/{KODE_SEKPER}/{bulan}/{tahun}-{kode_akhir}"
    return nomor

# ─── MAIN ──────────────────────────────────────────────
st.title("📄 Manajemen Visum")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📋 Daftar Visum", "➕ Buat Visum Baru", "🔍 Detail Visum"])

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
        # Filter status
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
            "Berangkat": v["tanggal_berangkat"],
            "Kembali": v["tanggal_kembali"],
            "Lama": f"{v['lama_hari']} hari",
            "Status": v["status"].upper(),
        } for v in filtered])

        st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════
# TAB 2: BUAT VISUM BARU
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Buat Visum Baru")

    # Preview nomor
    nomor_preview = generate_nomor(KODE_VISUM)
    st.info(f"📌 Nomor Visum: **{nomor_preview}**")

    pegawai_list = get_all_pegawai()
    pegawai_options = {f"{p['nip']} - {p['nama']}": p["id"] for p in pegawai_list}

    with st.form("form_visum"):
        col1, col2 = st.columns(2)
        with col1:
            tanggal_visum = st.date_input("Tanggal Visum", value=date.today())
            tanggal_berangkat = st.date_input("Tanggal Berangkat", value=date.today())
            tanggal_kembali = st.date_input("Tanggal Kembali", value=date.today())

        with col2:
            # Tujuan dengan opsi manual
            tujuan_pilihan = st.selectbox("Kota Tujuan", KOTA_OPTIONS)
            if tujuan_pilihan == "Lainnya (ketik manual)":
                tujuan = st.text_input("Ketik Kota Tujuan *")
            else:
                tujuan = tujuan_pilihan
                st.text_input("Kota Tujuan", value=tujuan, disabled=True)

            keperluan = st.text_area("Keperluan / Maksud Perjalanan *", height=100)

        st.markdown("**Peserta Perjalanan Dinas** *(pilih satu per satu)*")
        peserta_selected = st.multiselect(
            "Pilih Peserta",
            options=list(pegawai_options.keys()),
            placeholder="Ketik nama atau NIP untuk mencari..."
        )

        file_disposisi = st.file_uploader(
            "Upload Surat Disposisi (opsional)", 
            type=["pdf", "jpg", "png"]
        )

        submitted = st.form_submit_button("💾 Simpan Visum", use_container_width=True)

        if submitted:
            # Validasi
            if not tujuan:
                st.error("❌ Kota tujuan wajib diisi!")
            elif not keperluan:
                st.error("❌ Keperluan perjalanan wajib diisi!")
            elif not peserta_selected:
                st.error("❌ Minimal 1 peserta harus dipilih!")
            elif tanggal_kembali < tanggal_berangkat:
                st.error("❌ Tanggal kembali tidak boleh sebelum tanggal berangkat!")
            else:
                lama_hari = (tanggal_kembali - tanggal_berangkat).days + 1
                
                # Siapkan data peserta (simpan sebagai list of pegawai_id)
                peserta_ids = [pegawai_options[p] for p in peserta_selected]
                peserta_nama = [p.split(" - ")[1] for p in peserta_selected]

                try:
                    nomor_final = generate_nomor(KODE_VISUM)
                    db.table("visum").insert({
                        "nomor_visum": nomor_final,
                        "tanggal_visum": str(tanggal_visum),
                        "tujuan": tujuan,
                        "tanggal_berangkat": str(tanggal_berangkat),
                        "tanggal_kembali": str(tanggal_kembali),
                        "lama_hari": lama_hari,
                        "keperluan": keperluan,
                        "peserta": peserta_ids,
                        "status": "active"
                    }).execute()

                    st.success(f"✅ Visum **{nomor_final}** berhasil dibuat!")
                    st.balloons()
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Gagal menyimpan: {e}")

# ══════════════════════════════════════════════════════
# TAB 3: DETAIL VISUM
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Detail & Ubah Status Visum")

    res = db.table("visum").select("*").order("created_at", desc=True).execute()
    visum_list = res.data

    if not visum_list:
        st.info("Belum ada data visum.")
    else:
        visum_options = {v["nomor_visum"]: v for v in visum_list}
        selected = st.selectbox("Pilih Nomor Visum", list(visum_options.keys()))

        if selected:
            v = visum_options[selected]
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Tujuan", v["tujuan"])
            col2.metric("Lama Perjalanan", f"{v['lama_hari']} hari")
            col3.metric("Status", v["status"].upper())

            st.markdown(f"**Keperluan:** {v['keperluan']}")
            st.markdown(f"**Berangkat:** {v['tanggal_berangkat']} → **Kembali:** {v['tanggal_kembali']}")

            # Tampilkan peserta
            st.markdown("**Peserta:**")
            if v.get("peserta"):
                peserta_ids = v["peserta"]
                pegawai_list = get_all_pegawai()
                peserta_data = [p for p in pegawai_list if p["id"] in peserta_ids]
                for p in peserta_data:
                    jabatan_nama = p["jabatan"]["nama"] if p.get("jabatan") else "-"
                    st.markdown(f"- {p['nama']} *(_{jabatan_nama}_)*")
            
            st.markdown("---")

            # Ubah status
            col_status, col_btn = st.columns([2, 1])
            with col_status:
                new_status = st.selectbox("Ubah Status", 
                    ["active", "completed", "cancelled"],
                    index=["active", "completed", "cancelled"].index(v["status"]) 
                    if v["status"] in ["active", "completed", "cancelled"] else 0)
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Update Status", use_container_width=True):
                    db.table("visum").update({"status": new_status})\
                        .eq("id", v["id"]).execute()
                    st.success("✅ Status berhasil diupdate!")
                    st.rerun()