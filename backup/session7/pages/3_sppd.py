import streamlit as st
from utils.database import (
    get_all_pegawai, get_rkap_id, get_rule_sppd, detect_lokasi,
    get_client, deduct_rkap, rollback_rkap, update_rekap_spd,
    JABATAN_SORT_ORDER
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

# ─── HELPER ────────────────────────────────────────────
def format_rupiah(amount) -> str:
    if not amount:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
st.title("📋 Manajemen SPPD")
st.markdown("---")

# Tab 2 "Buat SPPD Baru" dihapus — SPPD otomatis dibuat dari halaman Visum
tab1, tab2, tab3 = st.tabs([
    "📋 Daftar SPPD",
    "🔍 Detail & Realisasi",
    "📊 Rekap SPD"
])

# ══════════════════════════════════════════════════════
# TAB 1: DAFTAR SPPD
# ══════════════════════════════════════════════════════
with tab1:
    st.subheader("Daftar SPPD")

    res = db.table("sppd")\
        .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama)), visum(nomor_visum, tujuan), spd(nomor_spd)")\
        .order("created_at", desc=True)\
        .execute()
    sppd_list = res.data

    if not sppd_list:
        st.info("Belum ada data SPPD.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            search = st.text_input("🔍 Cari nama pegawai / nomor SPD", "")
        with col2:
            filter_status = st.selectbox("Filter Status",
                ["Semua", "draft", "pencairan", "realisasi", "completed", "cancelled"])

        filtered = sppd_list
        if search:
            filtered = [s for s in filtered if
                (s.get("pegawai") and search.lower() in s["pegawai"]["nama"].lower()) or
                (s.get("spd") and search.lower() in s["spd"]["nomor_spd"].lower())]
        if filter_status != "Semua":
            filtered = [s for s in filtered if s["status"] == filter_status]

        st.caption(f"Menampilkan {len(filtered)} SPPD")

        import pandas as pd
        df = pd.DataFrame([{
            "Nomor SPD": s["spd"]["nomor_spd"] if s.get("spd") else "-",
            "Pegawai": s["pegawai"]["nama"] if s.get("pegawai") else "-",
            "Jabatan": s["pegawai"]["jabatan"]["nama"] if s.get("pegawai") and s["pegawai"].get("jabatan") else "-",
            "Tujuan": s["visum"]["tujuan"] if s.get("visum") else "-",
            "Uang Saku": format_rupiah(s.get("subtotal_uang_saku", 0)),
            "Total Biaya": format_rupiah(s.get("total_biaya", 0)),
            "Status": s["status"].upper(),
        } for s in filtered])

        st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════
# TAB 2: DETAIL & REALISASI
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Detail SPPD & Input Realisasi")

    # Ambil SPD — filter: jangan tampilkan visum completed
    res_spd = db.table("spd")\
        .select("*, visum(id, nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali, status)")\
        .order("created_at", desc=True)\
        .execute()

    # Filter out visum yang completed
    spd_data_all = [
        s for s in res_spd.data
        if s.get("visum") and s["visum"].get("status") != "completed"
    ]

    if not spd_data_all:
        st.info("Tidak ada SPPD aktif.")
    else:
        # ── Pilih SPD ──
        spd_options = {
            f"{s['nomor_spd']} — {s['visum']['tujuan'] if s.get('visum') else '-'}": s
            for s in spd_data_all
        }
        spd_keys = list(spd_options.keys())

        # Persist pilihan SPD di session_state
        if "detail_spd_key" not in st.session_state:
            st.session_state.detail_spd_key = spd_keys[0]
        if st.session_state.detail_spd_key not in spd_keys:
            st.session_state.detail_spd_key = spd_keys[0]

        selected_spd_key = st.selectbox(
            "📋 Pilih SPD / Visum",
            spd_keys,
            index=spd_keys.index(st.session_state.detail_spd_key),
            key="selectbox_spd"
        )
        st.session_state.detail_spd_key = selected_spd_key
        selected_spd = spd_options[selected_spd_key]

        st.markdown("---")

        # ── Pilih Pegawai dalam SPD ──
        res = db.table("sppd")\
            .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama, struktur_rkap)), visum(nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali), spd(nomor_spd)")\
            .eq("spd_id", selected_spd["id"])\
            .order("created_at", desc=True)\
            .execute()
        sppd_dalam_spd = res.data

        if not sppd_dalam_spd:
            st.info("Belum ada SPPD dalam SPD ini.")
        else:
            sppd_options = {
                f"{s['pegawai']['nama'] if s.get('pegawai') else '-'} — {s['status'].upper()}": s
                for s in sppd_dalam_spd
            }
            sppd_keys = list(sppd_options.keys())

            # Persist pilihan pegawai di session_state — reset kalau SPD berubah
            state_key = f"detail_sppd_key_{selected_spd['id']}"
            if state_key not in st.session_state:
                st.session_state[state_key] = sppd_keys[0]
            if st.session_state[state_key] not in sppd_keys:
                st.session_state[state_key] = sppd_keys[0]

            selected_key = st.selectbox(
                "👤 Pilih Pegawai",
                sppd_keys,
                index=sppd_keys.index(st.session_state[state_key]),
                key=f"selectbox_sppd_{selected_spd['id']}"
            )
            st.session_state[state_key] = selected_key
            s = sppd_options[selected_key]

            # ── Info Cards ──
            col1, col2, col3 = st.columns(3)
            col1.metric("Pegawai", s["pegawai"]["nama"] if s.get("pegawai") else "-")
            col2.metric("Tujuan", s["visum"]["tujuan"] if s.get("visum") else "-")
            col3.metric("Status", s["status"].upper())

            col4, col5, col6 = st.columns(3)
            col4.metric("Durasi", f"{s.get('total_hari', 0)} hari")
            col5.metric("Uang Saku", format_rupiah(s.get("subtotal_uang_saku", 0)))
            col6.metric("Total Realisasi", format_rupiah(s.get("total_biaya", 0)))

            st.markdown("---")

            # ── Rincian Uang Saku ──
            st.markdown("#### 💰 Rincian Uang Saku")
            col_r1, col_r2 = st.columns(2)

            with col_r1:
                st.markdown("**Komponen Uang Saku:**")
                st.markdown(f"- Uang Harian &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: **{format_rupiah(s.get('uang_harian_total', 0))}**")
                st.markdown(f"- Uang Makan &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: **{format_rupiah(s.get('uang_makan_total', 0))}**")
                st.markdown(f"- Transport Lokal &nbsp;: **{format_rupiah(s.get('transport_lokal_total', 0))}**")
                if s.get("uang_representasi_total", 0) > 0:
                    st.markdown(f"- Uang Representasi : **{format_rupiah(s.get('uang_representasi_total', 0))}**")
                st.markdown(f"**Subtotal Uang Saku : {format_rupiah(s.get('subtotal_uang_saku', 0))}**")

            with col_r2:
                st.markdown("**Realisasi:**")
                st.markdown(f"- Transport : **{format_rupiah(s.get('total_transport', 0))}**")
                st.markdown(f"- Hotel &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: **{format_rupiah(s.get('total_hotel', 0))}**")
                st.markdown(f"**Total Realisasi : {format_rupiah(s.get('total_biaya', 0))}**")

            st.markdown("---")

            col_left, col_right = st.columns(2)

            with col_left:
                st.markdown("**Update Status**")

                # Status yang tersedia berdasarkan kondisi
                if s["status"] == "completed":
                    st.success("✅ SPPD ini sudah COMPLETED.")
                elif s["status"] == "cancelled":
                    st.error("❌ SPPD ini sudah CANCELLED.")
                else:
                    # Flow: draft → pencairan → realisasi → completed
                    # Cancel hanya dari draft atau pencairan
                    status_map = {
                        "draft":     ["draft", "pencairan", "cancelled"],
                        "pencairan": ["pencairan", "realisasi", "cancelled"],
                        "realisasi": ["realisasi", "completed"],
                    }
                    status_options = status_map.get(s["status"], [s["status"]])

                    new_status = st.selectbox(
                        "Status Baru",
                        status_options,
                        index=0,
                        key=f"status_select_{s['id']}"
                    )

                    # Nomor voucher hanya muncul saat realisasi
                    nomor_voucher = ""
                    if new_status in ["realisasi", "completed"] or s["status"] == "realisasi":
                        nomor_voucher = st.text_input(
                            "Nomor Voucher",
                            value=s.get("nomor_voucher") or "",
                            key=f"voucher_{s['id']}"
                        )

                    if st.button("💾 Update Status", use_container_width=True, key=f"btn_status_{s['id']}"):
                        db.table("sppd").update({
                            "status": new_status,
                            "nomor_voucher": nomor_voucher if nomor_voucher else s.get("nomor_voucher")
                        }).eq("id", s["id"]).execute()

                        rkap_id    = s.get("rkap_id")
                        uang_saku  = s.get("subtotal_uang_saku") or 0
                        old_status = s["status"]

                        if rkap_id:
                            if new_status == "pencairan" and old_status == "draft":
                                deduct_rkap(rkap_id, uang_saku)
                            elif new_status == "cancelled":
                                if old_status == "pencairan":
                                    rollback_rkap(rkap_id, uang_saku)

                        st.success("✅ Status berhasil diupdate!")
                        st.rerun()

            with col_right:
                if s["status"] == "realisasi":
                    st.markdown("**Input Realisasi Biaya**")
                    total_transport = st.number_input(
                        "Biaya Transport (Rp)",
                        value=int(s.get("total_transport") or 0),
                        step=50000,
                        key=f"transport_{s['id']}"
                    )
                    total_hotel = st.number_input(
                        "Biaya Hotel (Rp)",
                        value=int(s.get("total_hotel") or 0),
                        step=50000,
                        key=f"hotel_{s['id']}"
                    )

                    total_realisasi = (s.get("subtotal_uang_saku") or 0) + total_transport + total_hotel
                    st.markdown(f"**Total Realisasi: {format_rupiah(total_realisasi)}**")

                    if st.button("💾 Simpan Realisasi", use_container_width=True, key=f"btn_realisasi_{s['id']}"):
                        db.table("sppd").update({
                            "total_transport": total_transport,
                            "total_hotel":     total_hotel,
                            "total_biaya":     total_realisasi,
                        }).eq("id", s["id"]).execute()

                        rkap_id       = s.get("rkap_id")
                        old_transport = s.get("total_transport") or 0
                        old_hotel     = s.get("total_hotel") or 0
                        selisih = (total_transport + total_hotel) - (old_transport + old_hotel)
                        if rkap_id and selisih != 0:
                            if selisih > 0:
                                deduct_rkap(rkap_id, selisih)
                            else:
                                rollback_rkap(rkap_id, abs(selisih))

                        if s.get("spd_id"):
                            update_rekap_spd(s["spd_id"])

                        st.success("✅ Realisasi berhasil disimpan!")
                        st.rerun()

                elif s["status"] not in ["completed", "cancelled"]:
                    st.info(f"ℹ️ Input realisasi tersedia saat status **REALISASI**.\nStatus sekarang: **{s['status'].upper()}**")

# ══════════════════════════════════════════════════════
# TAB 3: REKAP SPD
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Rekap SPD per Visum")

    res_spd = db.table("spd")\
        .select("*, visum(nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali)")\
        .order("created_at", desc=True)\
        .execute()
    spd_list = res_spd.data

    if not spd_list:
        st.info("Belum ada data SPD.")
    else:
        spd_options = {
            f"{s['nomor_spd']} — {s['visum']['tujuan'] if s.get('visum') else '-'}": s
            for s in spd_list
        }
        selected_spd_key = st.selectbox("Pilih SPD", list(spd_options.keys()), key="rekap_spd_select")
        spd = spd_options[selected_spd_key]

        # Rekap per kategori
        st.markdown("#### Rekap Total Biaya per Kategori")
        col1, col2, col3 = st.columns(3)
        col1.metric("Direksi",        format_rupiah(spd.get("total_direksi", 0)))
        col2.metric("Dewan Pengawas", format_rupiah(spd.get("total_dewas", 0)))
        col3.metric("Administrasi",   format_rupiah(spd.get("total_administrasi", 0)))

        col4, col5, col6 = st.columns(3)
        col4.metric("Teknik",         format_rupiah(spd.get("total_teknik", 0)))
        col5.metric("Bantuan",        format_rupiah(spd.get("total_bantuan", 0)))
        col6.metric("🏆 Grand Total", format_rupiah(spd.get("grand_total", 0)))

        st.markdown("---")

        # Daftar SPPD dalam SPD — diurutkan dari jabatan tertinggi
        st.markdown("#### Daftar SPPD dalam SPD ini")
        res_detail = db.table("sppd")\
            .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama))")\
            .eq("spd_id", spd["id"])\
            .execute()

        if res_detail.data:
            import pandas as pd

            def get_sort_key(row):
                jabatan_nama = ""
                try:
                    jabatan_nama = row["pegawai"]["jabatan"]["nama"].upper().strip()
                except:
                    pass
                return JABATAN_SORT_ORDER.get(jabatan_nama, 99)

            # Sort berdasarkan level jabatan
            sorted_data = sorted(res_detail.data, key=get_sort_key)

            df = pd.DataFrame([{
                "Nama": d["pegawai"]["nama"] if d.get("pegawai") else "-",
                "Jabatan": d["pegawai"]["jabatan"]["nama"] if d.get("pegawai") and d["pegawai"].get("jabatan") else "-",
                "Hari": d["total_hari"],
                "Uang Saku": format_rupiah(d.get("subtotal_uang_saku", 0)),
                "Transport": format_rupiah(d.get("total_transport", 0)),
                "Hotel": format_rupiah(d.get("total_hotel", 0)),
                "Total": format_rupiah(d.get("total_biaya", 0)),
                "Status": d["status"].upper(),
            } for d in sorted_data])

            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("🔄 Hitung Ulang Rekap", key="btn_rekap_ulang"):
                update_rekap_spd(spd["id"])
                st.success("✅ Rekap berhasil dihitung ulang!")
                st.rerun()