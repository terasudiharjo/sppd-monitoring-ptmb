import streamlit as st
from utils.database import get_all_pegawai, get_all_divisi, get_all_jabatan
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
db = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ─── AUTH CHECK ────────────────────────────────────────
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Silakan login terlebih dahulu.")
    st.stop()

st.title("👤 Master Data Pegawai")
st.markdown("---")

# ─── TABS ──────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Daftar Pegawai", "➕ Tambah Pegawai",
    "✏️ Edit / Nonaktifkan", "🏷️ Kelola Jabatan"
])

# ══════════════════════════════════════════════════════
# TAB 1: DAFTAR PEGAWAI
# ══════════════════════════════════════════════════════
with tab1:
    st.subheader("Daftar Pegawai Aktif")
    
    pegawai_list = get_all_pegawai()
    
    if not pegawai_list:
        st.info("Belum ada data pegawai.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            search = st.text_input("🔍 Cari nama / NIP", "")
        with col2:
            # Ambil parent divisi aja (yang parent_id = NULL)
            divisi_list = get_all_divisi()
            parent_divisi = [d for d in divisi_list if not d.get("parent_id")]
            divisi_options = ["Semua Divisi"] + [d["nama"] for d in parent_divisi]
            filter_divisi = st.selectbox("Filter Divisi", divisi_options)
        
        # Apply filter
        filtered = pegawai_list
        if search:
            filtered = [p for p in filtered if 
                        search.lower() in p["nama"].lower() or 
                        search.lower() in p["nip"].lower()]
        
        if filter_divisi != "Semua Divisi":
            # Cari parent divisi yang dipilih
            selected_parent = next(d for d in parent_divisi if d["nama"] == filter_divisi)
            # Kumpulkan ID: parent + semua sub-divisi yang parent_id-nya sama
            valid_ids = {selected_parent["id"]} | {
                d["id"] for d in divisi_list 
                if d.get("parent_id") == selected_parent["id"]
            }
            filtered = [p for p in filtered if p.get("divisi_id") in valid_ids]
        
        st.caption(f"Menampilkan {len(filtered)} dari {len(pegawai_list)} pegawai")
        
        import pandas as pd
        df = pd.DataFrame([{
            "NIP": p["nip"],
            "Nama": p["nama"],
            "Divisi": p["divisi"]["nama"] if p.get("divisi") else "-",
            "Jabatan": p["jabatan"]["nama"] if p.get("jabatan") else "-",
        } for p in filtered])
        
        st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════
# TAB 2: TAMBAH PEGAWAI
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Tambah Pegawai Baru")
    
    divisi_list = get_all_divisi()
    jabatan_list = get_all_jabatan()
    
    with st.form("form_tambah_pegawai"):
        col1, col2 = st.columns(2)
        with col1:
            nip = st.text_input("NIP *")
            nama = st.text_input("Nama Lengkap *")
            email = st.text_input("Email")
        with col2:
            divisi_options = {d["nama"]: d["id"] for d in divisi_list}
            jabatan_options = {j["nama"]: j["id"] for j in jabatan_list}
            
            selected_divisi = st.selectbox("Divisi *", list(divisi_options.keys()))
            selected_jabatan = st.selectbox("Jabatan *", list(jabatan_options.keys()))
            no_hp = st.text_input("No. HP")
        
        submitted = st.form_submit_button("💾 Simpan", use_container_width=True)
        
        if submitted:
            if not nip or not nama:
                st.error("NIP dan Nama wajib diisi!")
            else:
                try:
                    db.table("pegawai").insert({
                        "nip": nip,
                        "nama": nama,
                        "email": email,
                        "no_hp": no_hp,
                        "divisi_id": divisi_options[selected_divisi],
                        "jabatan_id": jabatan_options[selected_jabatan],
                        "status": "aktif"
                    }).execute()
                    st.success(f"✅ Pegawai **{nama}** berhasil ditambahkan!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Gagal menyimpan: {e}")

# ══════════════════════════════════════════════════════
# TAB 3: EDIT / NONAKTIFKAN
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Edit atau Nonaktifkan Pegawai")
    
    pegawai_list = get_all_pegawai()
    pegawai_options = {f"{p['nip']} - {p['nama']}": p for p in pegawai_list}
    
    selected = st.selectbox("Pilih Pegawai", list(pegawai_options.keys()))
    
    if selected:
        pegawai = pegawai_options[selected]
        divisi_list = get_all_divisi()
        jabatan_list = get_all_jabatan()
        
        with st.form("form_edit_pegawai"):
            col1, col2 = st.columns(2)
            with col1:
                new_nama = st.text_input("Nama", value=pegawai["nama"])
                new_email = st.text_input("Email", value=pegawai.get("email") or "")
            with col2:
                divisi_options = {d["nama"]: d["id"] for d in divisi_list}
                jabatan_options = {j["nama"]: j["id"] for j in jabatan_list}
                
                current_divisi = pegawai["divisi"]["nama"] if pegawai.get("divisi") else list(divisi_options.keys())[0]
                current_jabatan = pegawai["jabatan"]["nama"] if pegawai.get("jabatan") else list(jabatan_options.keys())[0]
                
                new_divisi = st.selectbox("Divisi", list(divisi_options.keys()),
                    index=list(divisi_options.keys()).index(current_divisi) if current_divisi in divisi_options else 0)
                new_jabatan = st.selectbox("Jabatan", list(jabatan_options.keys()),
                    index=list(jabatan_options.keys()).index(current_jabatan) if current_jabatan in jabatan_options else 0)
                new_hp = st.text_input("No. HP", value=pegawai.get("no_hp") or "")
            
            col_save, col_deactivate = st.columns(2)
            with col_save:
                save = st.form_submit_button("💾 Update", use_container_width=True)
            with col_deactivate:
                deactivate = st.form_submit_button("🚫 Nonaktifkan", use_container_width=True, type="secondary")
            
            if save:
                try:
                    db.table("pegawai").update({
                        "nama": new_nama,
                        "email": new_email,
                        "no_hp": new_hp,
                        "divisi_id": divisi_options[new_divisi],
                        "jabatan_id": jabatan_options[new_jabatan],
                    }).eq("id", pegawai["id"]).execute()
                    st.success("✅ Data pegawai berhasil diupdate!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Gagal update: {e}")
            
            if deactivate:
                try:
                    db.table("pegawai").update({"status": "nonaktif"})\
                        .eq("id", pegawai["id"]).execute()
                    st.success(f"✅ Pegawai **{pegawai['nama']}** dinonaktifkan.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Gagal nonaktifkan: {e}")

# ══════════════════════════════════════════════════════
# TAB 4: KELOLA JABATAN
# ══════════════════════════════════════════════════════
with tab4:
    st.subheader("Kelola Master Jabatan")

    # Nilai-nilai struktur RKAP yang valid
    STRUKTUR_RKAP_OPTIONS = [
        "DEWAS_KETUA", "DEWAS_ANGGOTA", "DEWAS_ANGGOTA_1", "DEWAS_ANGGOTA_2",
        "DIRUT", "DIRUM", "DIRTEK", "DIROPS",
        "MANAJER", "SUPERVISOR", "STAF_PELAKSANA",
        "ADM_MANAJER", "ADM_SUPERVISOR", "ADM_STAF_PELAKSANA",
        "TEKNIK_MANAJER", "TEKNIK_SUPERVISOR", "TEKNIK_STAF_PELAKSANA",
        "BANTUAN",
    ]
    NAMA_RULE_OPTIONS = [
        "DIREKTUR UTAMA", "DIREKTUR BIDANG",
        "MANAJER", "SUPERVISOR", "STAF PELAKSANA",
    ]

    # Daftar jabatan yang ada
    jabatan_list_all = get_all_jabatan()
    if jabatan_list_all:
        import pandas as pd
        df_jbt = pd.DataFrame([{
            "Nama Jabatan":  j["nama"],
            "Nama Rule":     j.get("nama_rule", "-"),
            "Level":         j.get("level", "-"),
            "Struktur RKAP": j.get("struktur_rkap", "-"),
            "Status":        j.get("status", "-"),
        } for j in jabatan_list_all])
        st.dataframe(df_jbt, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data jabatan.")

    st.markdown("---")

    col_add, col_edit = st.columns(2)

    # ── Tambah Jabatan Baru ──
    with col_add:
        st.markdown("#### ➕ Tambah Jabatan Baru")
        with st.form("form_tambah_jabatan"):
            j_nama       = st.text_input("Nama Jabatan *", placeholder="ANGGOTA DEWAN PENGAWAS 2")
            j_nama_rule  = st.selectbox("Nama Rule *", NAMA_RULE_OPTIONS,
                                        index=NAMA_RULE_OPTIONS.index("DIREKTUR BIDANG"))
            j_level      = st.number_input("Level (0–5)", min_value=0, max_value=5, value=5)
            j_struktur   = st.selectbox("Struktur RKAP *", STRUKTUR_RKAP_OPTIONS,
                                        index=STRUKTUR_RKAP_OPTIONS.index("DEWAS_ANGGOTA_2"))

            if st.form_submit_button("💾 Tambah Jabatan", use_container_width=True):
                if not j_nama:
                    st.error("Nama jabatan wajib diisi!")
                else:
                    try:
                        db.table("jabatan").insert({
                            "nama":         j_nama.strip().upper(),
                            "nama_rule":    j_nama_rule,
                            "level":        j_level,
                            "struktur_rkap": j_struktur,
                            "status":       "aktif",
                        }).execute()
                        st.success(f"✅ Jabatan **{j_nama.upper()}** berhasil ditambahkan!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal: {e}")

    # ── Nonaktifkan Jabatan ──
    with col_edit:
        st.markdown("#### 🚫 Nonaktifkan Jabatan")
        if jabatan_list_all:
            jbt_options = {j["nama"]: j for j in jabatan_list_all}
            selected_jbt = st.selectbox("Pilih Jabatan", list(jbt_options.keys()),
                                        key="select_jbt_nonaktif")
            jbt = jbt_options[selected_jbt]
            st.caption(f"Struktur RKAP: **{jbt.get('struktur_rkap', '-')}**  |  Level: **{jbt.get('level', '-')}**")
            if st.button("🚫 Nonaktifkan Jabatan Ini", use_container_width=True,
                         key="btn_nonaktif_jbt"):
                try:
                    db.table("jabatan").update({"status": "nonaktif"})\
                        .eq("id", jbt["id"]).execute()
                    st.success(f"✅ Jabatan **{jbt['nama']}** dinonaktifkan.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Gagal: {e}")