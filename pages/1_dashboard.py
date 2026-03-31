import streamlit as st
from utils.database import get_client
from datetime import date
import pandas as pd

# ─── AUTH CHECK ────────────────────────────────────────
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Silakan login terlebih dahulu.")
    st.stop()

db = get_client()

st.title("📊 Dashboard SPPD PTMB")
st.markdown("---")

# ══════════════════════════════════════════════════════
# AMBIL DATA
# ══════════════════════════════════════════════════════
tahun_ini = date.today().year
bulan_ini = date.today().month

# Data SPPD
res_sppd = db.table("sppd")\
    .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(struktur_rkap)), visum(tujuan, tanggal_berangkat)")\
    .execute()
sppd_list = res_sppd.data

# Data Visum
res_visum = db.table("visum").select("*").execute()
visum_list = res_visum.data

# Data SPD
res_spd = db.table("spd").select("*").execute()
spd_list = res_spd.data

# ══════════════════════════════════════════════════════
# ROW 1: STATISTIK UTAMA
# ══════════════════════════════════════════════════════
st.subheader("📈 Ringkasan")

col1, col2, col3, col4, col5 = st.columns(5)

total_sppd = len(sppd_list)
draft = sum(1 for s in sppd_list if s["status"] == "draft")
pencairan = sum(1 for s in sppd_list if s["status"] == "pencairan")
realisasi = sum(1 for s in sppd_list if s["status"] == "realisasi")
completed = sum(1 for s in sppd_list if s["status"] == "completed")
cancelled = sum(1 for s in sppd_list if s["status"] == "cancelled")

col1.metric("Total SPPD", total_sppd)
col2.metric("✏️ Draft", draft)
col3.metric("💰 Pencairan", pencairan)
col4.metric("⏳ Menunggu Realisasi", realisasi)
col5.metric("✅ Selesai", completed)

st.markdown("---")

# ══════════════════════════════════════════════════════
# ROW 2: TOTAL BIAYA & VISUM
# ══════════════════════════════════════════════════════
col1, col2, col3 = st.columns(3)

STATUS_TERPAKAI = {"pencairan", "realisasi", "completed"}
total_biaya = sum(s.get("total_biaya") or 0 for s in sppd_list if s["status"] in STATUS_TERPAKAI)
total_uang_saku = sum(s.get("subtotal_uang_saku") or 0 for s in sppd_list if s["status"] in STATUS_TERPAKAI)
total_transport_hotel = sum(
    (s.get("total_transport") or 0) + (s.get("total_hotel") or 0)
    for s in sppd_list if s["status"] in STATUS_TERPAKAI
)

def format_rupiah(amount):
    if not amount:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

col1.metric("Total Visum", len(visum_list))
col2.metric("Total Anggaran Terpakai", format_rupiah(total_biaya))
col3.metric("Total Uang Saku", format_rupiah(total_uang_saku))

st.markdown("---")

# ══════════════════════════════════════════════════════
# ROW 3: GRAFIK STATUS SPPD
# ══════════════════════════════════════════════════════
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 Status SPPD")
    status_data = {
        "Status": ["Draft", "Pencairan", "Realisasi", "Completed", "Cancelled"],
        "Jumlah": [draft, pencairan, realisasi, completed, cancelled]
    }
    df_status = pd.DataFrame(status_data)
    df_status = df_status[df_status["Jumlah"] > 0]  # hide yang 0
    
    if not df_status.empty:
        st.bar_chart(df_status.set_index("Status"))
    else:
        st.info("Belum ada data SPPD.")

with col_right:
    st.subheader("💰 Biaya per Kategori")
    
    if spd_list:
        kategori_data = {
            "Kategori": ["Direksi", "Dewan Pengawas", "Administrasi", "Teknik", "Bantuan"],
            "Total": [
                sum(s.get("total_direksi") or 0 for s in spd_list),
                sum(s.get("total_dewas") or 0 for s in spd_list),
                sum(s.get("total_administrasi") or 0 for s in spd_list),
                sum(s.get("total_teknik") or 0 for s in spd_list),
                sum(s.get("total_bantuan") or 0 for s in spd_list),
            ]
        }
        df_kategori = pd.DataFrame(kategori_data)
        df_kategori = df_kategori[df_kategori["Total"] > 0]
        
        if not df_kategori.empty:
            st.bar_chart(df_kategori.set_index("Kategori"))
        else:
            st.info("Belum ada data realisasi.")
    else:
        st.info("Belum ada data SPD.")

st.markdown("---")

# ══════════════════════════════════════════════════════
# ROW 4: SPPD AKTIF (dalam perjalanan / pencairan)
# ══════════════════════════════════════════════════════
st.subheader("✈️ SPPD Aktif")

sppd_aktif = [s for s in sppd_list if s["status"] in ["pencairan", "realisasi"]]

if not sppd_aktif:
    st.info("Tidak ada SPPD yang sedang aktif saat ini.")
else:
    df_aktif = pd.DataFrame([{
        "Pegawai": s["pegawai"]["nama"] if s.get("pegawai") else "-",
        "Tujuan": s["visum"]["tujuan"] if s.get("visum") else "-",
        "Berangkat": s["visum"]["tanggal_berangkat"] if s.get("visum") else "-",
        "Uang Saku": format_rupiah(s.get("subtotal_uang_saku", 0)),
        "Status": s["status"].upper(),
    } for s in sppd_aktif])
    st.dataframe(df_aktif, use_container_width=True, hide_index=True)

st.markdown("---")

# ══════════════════════════════════════════════════════
# ROW 5: SPPD MENUNGGU REALISASI
# ══════════════════════════════════════════════════════
st.subheader("⏳ Menunggu Realisasi")

sppd_realisasi = [s for s in sppd_list if s["status"] == "realisasi"]

if not sppd_realisasi:
    st.info("Tidak ada SPPD yang menunggu realisasi.")
else:
    df_realisasi = pd.DataFrame([{
        "Pegawai": s["pegawai"]["nama"] if s.get("pegawai") else "-",
        "Tujuan": s["visum"]["tujuan"] if s.get("visum") else "-",
        "Total Biaya": format_rupiah(s.get("total_biaya", 0)),
        "Voucher": s.get("nomor_voucher") or "Belum ada",
    } for s in sppd_realisasi])
    st.dataframe(df_realisasi, use_container_width=True, hide_index=True)