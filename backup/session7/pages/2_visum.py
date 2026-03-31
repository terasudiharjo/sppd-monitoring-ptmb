import streamlit as st
from utils.database import (
    get_all_pegawai, get_all_divisi,
    detect_lokasi, get_or_create_spd,
    auto_buat_semua_sppd, sync_sppd_peserta, cancel_semua_sppd_visum
)
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
KODE_VISUM  = "J"

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

# ─── HELPER ────────────────────────────────────────────
BULAN_ROMAWI = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]

def generate_nomor_visum() -> str:
    tahun = date.today().year
    bulan = BULAN_ROMAWI[date.today().month - 1]
    res = db.table("visum").select("nomor_visum")\
        .like("nomor_visum", f"%/{tahun}-{KODE_VISUM}")\
        .execute()
    urutan = len(res.data) + 1
    return f"{urutan:04d}/{KODE_STATIC}/{KODE_SEKPER}/{bulan}/{tahun}-{KODE_VISUM}"

def format_rupiah(amount) -> str:
    if not amount:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

def get_nama_pegawai(pegawai_id: str, pegawai_map: dict) -> str:
    p = pegawai_map.get(pegawai_id)
    return p["nama"] if p else pegawai_id

def cek_bisa_complete(visum_id: str) -> tuple[bool, str]:
    """Cek apakah visum bisa di-complete (semua SPPD sudah realisasi/completed)."""
    res_spd = db.table("spd").select("id").eq("visum_id", visum_id).execute()
    if not res_spd.data:
        return False, "Belum ada SPD/SPPD untuk visum ini."
    
    spd_id = res_spd.data[0]["id"]
    res_sppd = db.table("sppd").select("status")\
        .eq("spd_id", spd_id)\
        .neq("status", "cancelled")\
        .execute()
    
    if not res_sppd.data:
        return False, "Tidak ada SPPD aktif."
    
    belum_selesai = [s for s in res_sppd.data if s["status"] not in ["realisasi", "completed"]]
    if belum_selesai:
        return False, f"{len(belum_selesai)} SPPD belum realisasi."
    
    return True, "Semua SPPD sudah realisasi."

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
st.title("📄 Manajemen Visum")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📋 Daftar Visum", "➕ Buat Visum Baru", "🔍 Detail & Edit Visum"])

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
            "Berangkat": v["tanggal_berangkat"],
            "Kembali": v["tanggal_kembali"],
            "Lama": f"{v['lama_hari']} hari",
            "Peserta": len(v.get("peserta") or []),
            "Status": v["status"].upper(),
        } for v in filtered])

        st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════
# TAB 2: BUAT VISUM BARU
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Buat Visum Baru")

    nomor_preview = generate_nomor_visum()
    st.info(f"📌 Nomor Visum: **{nomor_preview}**")

    pegawai_list = get_all_pegawai()
    pegawai_options = {f"{p['nip']} - {p['nama']}": p["id"] for p in pegawai_list}

    with st.form("form_visum"):
        col1, col2 = st.columns(2)
        with col1:
            tanggal_visum    = st.date_input("Tanggal Visum", value=date.today())
            tanggal_berangkat = st.date_input("Tanggal Berangkat", value=date.today())
            tanggal_kembali  = st.date_input("Tanggal Kembali", value=date.today())

        with col2:
            tujuan_pilihan = st.selectbox("Kota Tujuan", KOTA_OPTIONS)
            if tujuan_pilihan == "Lainnya (ketik manual)":
                tujuan = st.text_input("Ketik Kota Tujuan *")
            else:
                tujuan = tujuan_pilihan
                st.text_input("Kota Tujuan", value=tujuan, disabled=True)

            keperluan = st.text_area("Keperluan / Maksud Perjalanan *", height=100)

        st.markdown("**Peserta Perjalanan Dinas**")
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

                # Deteksi lokasi dari kota tujuan
                lokasi_info = detect_lokasi(tujuan)

                try:
                    nomor_final = generate_nomor_visum()

                    # 1. Simpan Visum
                    res_visum = db.table("visum").insert({
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

                    visum_baru = res_visum.data[0]

                    # 2. Auto-buat SPPD untuk semua peserta
                    with st.spinner("Membuat SPPD untuk semua peserta..."):
                        results = auto_buat_semua_sppd(visum_baru, lokasi_info["lokasi_id"])

                    st.success(f"✅ Visum **{nomor_final}** berhasil dibuat!")
                    st.info(f"📍 Lokasi terdeteksi: **{lokasi_info['lokasi_nama']}**")

                    # Tampilkan hasil pembuatan SPPD
                    if results:
                        pegawai_map = {p["id"]: p for p in pegawai_list}
                        st.markdown("**Hasil Auto-Buat SPPD:**")
                        for r in results:
                            nama = get_nama_pegawai(r["pegawai_id"], pegawai_map)
                            if r["success"]:
                                st.success(f"✅ {nama} — {r['pesan']}")
                            else:
                                st.warning(f"⚠️ {nama} — {r['pesan']}")

                    st.balloons()
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Gagal menyimpan: {e}")

# ══════════════════════════════════════════════════════
# TAB 3: DETAIL & EDIT VISUM
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Detail & Edit Visum")

    # Filter: jangan tampilkan visum completed di dropdown (biar tidak crowded)
    res_all = db.table("visum").select("*").order("created_at", desc=True).execute()
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
            visum_options = {
                f"{v['nomor_visum']} — {v['tujuan']} [{v['status'].upper()}]": v
                for v in visum_filtered
            }
            selected = st.selectbox("Pilih Nomor Visum", list(visum_options.keys()))

            if selected:
                v = visum_options[selected]

                # ── Info Visum ──
                col1, col2, col3 = st.columns(3)
                col1.metric("Tujuan", v["tujuan"])
                col2.metric("Lama Perjalanan", f"{v['lama_hari']} hari")
                col3.metric("Status", v["status"].upper())

                st.markdown(f"**Keperluan:** {v['keperluan']}")
                st.markdown(f"**Berangkat:** {v['tanggal_berangkat']} → **Kembali:** {v['tanggal_kembali']}")

                # Deteksi lokasi dari tujuan
                lokasi_info = detect_lokasi(v["tujuan"])
                st.info(f"📍 Lokasi: **{lokasi_info['lokasi_nama']}**")

                st.markdown("---")

                # ── Daftar Peserta + Edit ──
                pegawai_all  = get_all_pegawai()
                pegawai_map  = {p["id"]: p for p in pegawai_all}
                peserta_ids  = v.get("peserta") or []

                st.markdown("#### 👥 Peserta Perjalanan")

                # Tampilkan peserta saat ini
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

                # Edit peserta — hanya kalau visum belum completed/cancelled
                if v["status"] not in ["completed", "cancelled"]:
                    st.markdown("---")
                    st.markdown("#### ✏️ Edit Peserta")

                    pegawai_options_all = {f"{p['nip']} - {p['nama']}": p["id"] for p in pegawai_all}
                    # Pre-select peserta yang sudah ada
                    peserta_keys_current = [
                        k for k, pid in pegawai_options_all.items() if pid in peserta_ids
                    ]

                    peserta_baru_keys = st.multiselect(
                        "Ubah Peserta",
                        options=list(pegawai_options_all.keys()),
                        default=peserta_keys_current,
                        key="edit_peserta_multiselect"
                    )
                    peserta_baru_ids = [pegawai_options_all[k] for k in peserta_baru_keys]

                    # Deteksi perubahan
                    ada_perubahan = set(peserta_baru_ids) != set(peserta_ids)

                    if ada_perubahan:
                        ditambah = [pid for pid in peserta_baru_ids if pid not in peserta_ids]
                        dihapus  = [pid for pid in peserta_ids if pid not in peserta_baru_ids]

                        if ditambah:
                            st.success(f"➕ Akan ditambah: {', '.join([get_nama_pegawai(p, pegawai_map) for p in ditambah])}")
                        if dihapus:
                            st.warning(f"➖ Akan dihapus: {', '.join([get_nama_pegawai(p, pegawai_map) for p in dihapus])}")

                        if st.button("💾 Simpan Perubahan Peserta", use_container_width=True):
                            with st.spinner("Sinkronisasi SPPD..."):
                                hasil = sync_sppd_peserta(v, peserta_baru_ids, lokasi_info["lokasi_id"])

                            # Update peserta di visum
                            db.table("visum").update({"peserta": peserta_baru_ids})\
                                .eq("id", v["id"]).execute()

                            # Tampilkan hasil
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

                # ── Update Status Visum ──
                st.markdown("#### 🔄 Update Status Visum")

                if v["status"] == "completed":
                    st.success("✅ Visum ini sudah COMPLETED dan tidak dapat diubah.")

                elif v["status"] == "cancelled":
                    st.error("❌ Visum ini sudah CANCELLED.")

                else:
                    col_status, col_btn = st.columns([2, 1])

                    status_tersedia = ["active", "cancelled"]

                    # Cek apakah bisa di-complete
                    bisa_complete, alasan_complete = cek_bisa_complete(v["id"])
                    if bisa_complete:
                        status_tersedia.append("completed")

                    with col_status:
                        idx_current = status_tersedia.index(v["status"]) if v["status"] in status_tersedia else 0
                        new_status = st.selectbox("Status Baru", status_tersedia, index=idx_current)

                    with col_btn:
                        st.markdown("<br>", unsafe_allow_html=True)
                        update_btn = st.button("💾 Update Status", use_container_width=True)

                    # Info kenapa completed tidak muncul
                    if not bisa_complete and v["status"] != "cancelled":
                        st.caption(f"ℹ️ Completed belum tersedia: {alasan_complete}")

                    if update_btn:
                        if new_status == "cancelled":
                            # Cancel semua SPPD dulu
                            with st.spinner("Membatalkan semua SPPD..."):
                                hasil_cancel = cancel_semua_sppd_visum(v["id"])

                            if hasil_cancel["diblok"]:
                                st.error("❌ Tidak bisa cancel visum — ada SPPD yang sudah REALISASI:")
                                for blok in hasil_cancel["diblok"]:
                                    st.error(f"   • {blok['pesan']}")
                            else:
                                db.table("visum").update({"status": "cancelled"})\
                                    .eq("id", v["id"]).execute()
                                st.success(f"✅ Visum dibatalkan. {hasil_cancel['dicancelled']} SPPD di-cancel.")
                                st.rerun()

                        else:
                            db.table("visum").update({"status": new_status})\
                                .eq("id", v["id"]).execute()
                            st.success(f"✅ Status berhasil diupdate ke {new_status.upper()}!")
                            st.rerun()