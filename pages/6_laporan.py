"""
6_laporan.py — Laporan Perjalanan Dinas PTMB
=============================================
Generate laporan bulanan/semester dalam format PDF dan Excel.
"""

import streamlit as st
from datetime import date

from utils.database import (
    get_sppd_realisasi_laporan,
    get_rekap_perjalanan,
    get_pegawai_by_jabatan_nama,
    smart_title,
)
from utils.pdf_generator import (
    generate_laporan_realisasi,
    generate_rekap_bulanan,
    generate_rekap_semester,
    BULAN_ID,
)
from utils.excel_generator import generate_excel_realisasi

# ── Auth check ──
if not st.session_state.get("authenticated"):
    st.warning("Silakan login terlebih dahulu.")
    st.stop()

st.title("Laporan Perjalanan Dinas")

BULAN_OPTIONS = [f"{i:02d} - {BULAN_ID[i]}" for i in range(1, 13)]
TAHUN_DEFAULT = date.today().year


def _get_ttd():
    """Ambil nama TTD dari DB."""
    nm1 = get_pegawai_by_jabatan_nama("MANAJER SEKRETARIAT PERUSAHAAN")
    nm2 = get_pegawai_by_jabatan_nama("SUPERVISOR KESEKRETARIATAN DAN HUKUM")
    return {
        "menyetujui": nm1 or "",
        "diperiksa":  nm2 or "",
        "dibuat":     "",
    }


tab1, tab2, tab3 = st.tabs(["📄 Laporan Realisasi", "📊 Rekap Bulanan", "📈 Rekap Semester"])

# ══════════════════════════════════════════════════════════════
# TAB 1 — LAPORAN REALISASI
# ══════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Laporan Realisasi SPPD (Tabel I.6)")
    st.caption("Export laporan realisasi per bulan — tersedia format PDF dan Excel.")

    c1, c2 = st.columns([2, 1])
    with c1:
        bulan_sel = st.selectbox("Bulan", BULAN_OPTIONS,
                                 index=date.today().month - 1,
                                 key="lap_bulan")
    with c2:
        tahun_sel = st.number_input("Tahun", min_value=2020, max_value=2030,
                                    value=TAHUN_DEFAULT, key="lap_tahun")

    bulan_int = int(bulan_sel[:2])

    if st.button("Buat Laporan Realisasi", type="primary", key="btn_lap"):
        with st.spinner("Mengambil data..."):
            groups = get_sppd_realisasi_laporan(bulan_int, int(tahun_sel))

        if not groups:
            st.warning("Tidak ada data realisasi/completed untuk bulan tersebut.")
        else:
            total_sppd = sum(len(g["sppd_rows"]) for g in groups)
            st.success(f"Data ditemukan: {len(groups)} perjalanan, {total_sppd} peserta.")

            ttd = _get_ttd()

            # Preview tabel
            with st.expander("Preview Data", expanded=False):
                rows_preview = []
                for no, g in enumerate(groups, 1):
                    v = g["visum"]
                    for row in g["sppd_rows"]:
                        rows_preview.append({
                            "No": no,
                            "Tgl Brgkt": str(v.get("tanggal_berangkat",""))[:10],
                            "Tgl Kmbli": str(v.get("tanggal_kembali",""))[:10],
                            "Uraian": v.get("keperluan",""),
                            "Kota": v.get("tujuan",""),
                            "No. SPD": v.get("nomor_spd",""),
                            "Nama": smart_title(row.get("nama","") or ""),
                            "Jabatan": smart_title(row.get("jabatan","") or ""),
                            "No. Voucher": row.get("nomor_voucher","") or "-",
                            "SPPD": row.get("uang_saku", 0),
                            "Tiket": row.get("tiket", 0),
                            "Hotel": row.get("hotel", 0),
                            "Biaya Lain": row.get("biaya_lain", 0),
                            "Total": row.get("total", 0),
                        })
                import pandas as pd
                st.dataframe(pd.DataFrame(rows_preview), use_container_width=True, hide_index=True)

            col_pdf, col_xl = st.columns(2)

            with col_pdf:
                with st.spinner("Generate PDF..."):
                    pdf_buf = generate_laporan_realisasi({
                        "groups": groups,
                        "bulan":  bulan_int,
                        "tahun":  int(tahun_sel),
                        "ttd":    ttd,
                    })
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_buf,
                    file_name=f"laporan_realisasi_{BULAN_ID[bulan_int].lower()}_{tahun_sel}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            with col_xl:
                with st.spinner("Generate Excel..."):
                    xl_buf = generate_excel_realisasi(groups, bulan_int, int(tahun_sel))
                st.download_button(
                    label="⬇️ Download Excel",
                    data=xl_buf,
                    file_name=f"laporan_realisasi_{BULAN_ID[bulan_int].lower()}_{tahun_sel}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

# ══════════════════════════════════════════════════════════════
# TAB 2 — REKAP BULANAN
# ══════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Rekap Data Perjalanan Dinas Bulanan")
    st.caption("Jumlah keberangkatan per jabatan per lokasi dalam satu bulan.")

    c1, c2 = st.columns([2, 1])
    with c1:
        bulan_rb = st.selectbox("Bulan", BULAN_OPTIONS,
                                index=date.today().month - 1,
                                key="rb_bulan")
    with c2:
        tahun_rb = st.number_input("Tahun", min_value=2020, max_value=2030,
                                   value=TAHUN_DEFAULT, key="rb_tahun")

    bulan_rb_int = int(bulan_rb[:2])

    if st.button("Buat Rekap Bulanan", type="primary", key="btn_rb"):
        with st.spinner("Mengambil data..."):
            rekap = get_rekap_perjalanan([(bulan_rb_int, int(tahun_rb))])
            rows  = rekap.get((bulan_rb_int, int(tahun_rb)), [])

        if not rows:
            st.warning("Tidak ada data realisasi/completed untuk bulan tersebut.")
        else:
            total_kb = sum(r["count"] for r in rows)
            st.success(f"Total keberangkatan: {total_kb} orang.")

            ttd = _get_ttd()
            with st.spinner("Generate PDF..."):
                pdf_buf = generate_rekap_bulanan({
                    "rekap": rekap,
                    "bulan": bulan_rb_int,
                    "tahun": int(tahun_rb),
                    "ttd":   ttd,
                })
            st.download_button(
                label="⬇️ Download PDF Rekap Bulanan",
                data=pdf_buf,
                file_name=f"rekap_bulanan_{BULAN_ID[bulan_rb_int].lower()}_{tahun_rb}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

# ══════════════════════════════════════════════════════════════
# TAB 3 — REKAP SEMESTER
# ══════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Rekap Data Perjalanan Dinas Semester")
    st.caption("Jumlah keberangkatan per jabatan per bulan selama satu semester.")

    c1, c2 = st.columns([2, 1])
    with c1:
        semester_sel = st.selectbox(
            "Semester",
            ["Semester I (Januari - Juni)", "Semester II (Juli - Desember)"],
            key="sem_sel"
        )
    with c2:
        tahun_sem = st.number_input("Tahun", min_value=2020, max_value=2030,
                                    value=TAHUN_DEFAULT, key="sem_tahun")

    if semester_sel.startswith("Semester I"):
        bulan_list_sem = [(b, int(tahun_sem)) for b in range(1, 7)]
    else:
        bulan_list_sem = [(b, int(tahun_sem)) for b in range(7, 13)]

    bln_label = " - ".join([
        f"{BULAN_ID[bulan_list_sem[0][0]]} {bulan_list_sem[0][1]}",
        f"{BULAN_ID[bulan_list_sem[-1][0]]} {bulan_list_sem[-1][1]}",
    ])
    st.caption(f"Periode: {bln_label}")

    if st.button("Buat Rekap Semester", type="primary", key="btn_sem"):
        with st.spinner("Mengambil data..."):
            rekap_sem = get_rekap_perjalanan(bulan_list_sem)
            total_kb = sum(
                sum(r["count"] for r in rekap_sem.get(bt, []))
                for bt in bulan_list_sem
            )

        if total_kb == 0:
            st.warning("Tidak ada data realisasi/completed untuk periode tersebut.")
        else:
            st.success(f"Total keberangkatan: {total_kb} orang-perjalanan.")

            ttd = _get_ttd()
            with st.spinner("Generate PDF..."):
                pdf_buf = generate_rekap_semester({
                    "rekap":      rekap_sem,
                    "bulan_list": bulan_list_sem,
                    "ttd":        ttd,
                })

            sem_label = "sem1" if semester_sel.startswith("Semester I") else "sem2"
            st.download_button(
                label="⬇️ Download PDF Rekap Semester",
                data=pdf_buf,
                file_name=f"rekap_{sem_label}_{tahun_sem}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
