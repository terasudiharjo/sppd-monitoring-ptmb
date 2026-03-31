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
tab1, tab2, tab3 = st.tabs(["📋 Daftar Pegawai", "➕ Tambah Pegawai", "✏️ Edit / Nonaktifkan"])

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