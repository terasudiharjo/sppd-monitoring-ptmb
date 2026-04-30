import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.database import get_client

# ─── AUTH CHECK ───────────────────────────────────────
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Silakan login terlebih dahulu.")
    st.stop()

# ─────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────
LOKASI_DALAM = "6f7a80e0-1ca3-4e36-8d94-500bf8645efe"
LOKASI_LUAR  = "99c9f92f-972f-46d5-99d4-219b758d2cb7"
LOKASI_LN    = "38663104-e5f5-473d-8227-640f025e595a"

LOKASI_LABEL = {
    LOKASI_DALAM: "Dalam Kaltim",
    LOKASI_LUAR:  "Luar Kaltim",
    LOKASI_LN:    "Luar Negeri",
}

BULAN_LABEL = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

TRIWULAN = {
    "TW I   (Jan–Mar)": [1, 2, 3],
    "TW II  (Apr–Jun)": [4, 5, 6],
    "TW III (Jul–Sep)": [7, 8, 9],
    "TW IV  (Okt–Des)": [10, 11, 12],
}

SEMESTER = {
    "Semester I  (Jan–Jun)": [1, 2, 3, 4, 5, 6],
    "Semester II (Jul–Des)": [7, 8, 9, 10, 11, 12],
}

KATEGORI_ORDER = [
    "DEWAS_KETUA", "DEWAS_ANGGOTA_1", "DEWAS_ANGGOTA_2",
    "DIRUT", "DIRUM", "DIRTEK", "DIROPS",
    "ADM_MANAJER", "ADM_SUPERVISOR", "ADM_STAF_PELAKSANA",
    "TEKNIK_MANAJER", "TEKNIK_SUPERVISOR", "TEKNIK_STAF_PELAKSANA",
    "bantuan_sppd", "bantuan_sppd_luar_negeri",
]

KATEGORI_DISPLAY = {
    "DEWAS_KETUA":               "Ketua Dewas",
    "DEWAS_ANGGOTA_1":           "Anggota Dewas 1",
    "DEWAS_ANGGOTA_2":           "Anggota Dewas 2",
    "DIRUT":                     "Direktur Utama",
    "DIRUM":                     "Direktur Umum",
    "DIRTEK":                    "Direktur Teknik",
    "DIROPS":                    "Direktur Operasional",
    "ADM_MANAJER":               "Manajer Administrasi",
    "ADM_SUPERVISOR":            "Supervisor Administrasi",
    "ADM_STAF_PELAKSANA":        "Staf Administrasi",
    "TEKNIK_MANAJER":            "Manajer Teknik",
    "TEKNIK_SUPERVISOR":         "Supervisor Teknik",
    "TEKNIK_STAF_PELAKSANA":     "Staf Teknik",
    "bantuan_sppd":              "Bantuan SPPD",
    "bantuan_sppd_luar_negeri":  "Bantuan SPPD Luar Negeri",
}

# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────
def format_rp(nilai: int) -> str:
    """Format angka jadi Rp x.xxx.xxx, merah kalau negatif."""
    if nilai is None:
        return "Rp 0"
    if nilai < 0:
        return f"⚠️ -Rp {abs(int(nilai)):,}".replace(",", ".")
    return f"Rp {int(nilai):,}".replace(",", ".")


def pct_bar(terpakai: int, awal: int) -> str:
    """Buat mini progress bar teks."""
    if awal == 0:
        return "—"
    pct = min(terpakai / awal * 100, 100)
    filled = int(pct / 5)
    bar = "█" * filled + "░" * (20 - filled)
    return f"{bar} {pct:.1f}%"


@st.cache_data(ttl=60)
def load_rkap(tahun: int) -> pd.DataFrame:
    """Ambil semua data RKAP untuk tahun tertentu."""
    supabase = get_client()
    res = (
        supabase.table("rkap")
        .select("*")
        .eq("tahun", tahun)
        .execute()
    )
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    df["lokasi_label"] = df["lokasi_id"].map(LOKASI_LABEL).fillna("—")
    df["kategori_display"] = df["kategori_jabatan"].map(KATEGORI_DISPLAY).fillna(df["kategori_jabatan"])
    df["bulan_label"] = df["bulan"].map(BULAN_LABEL)
    return df


def filter_bulan(df: pd.DataFrame, mode: str, pilihan: str) -> pd.DataFrame:
    """Filter dataframe berdasarkan mode periode."""
    if mode == "Tahunan":
        return df
    elif mode == "Bulanan":
        bulan_num = {v: k for k, v in BULAN_LABEL.items()}[pilihan]
        return df[df["bulan"] == bulan_num]
    elif mode == "Triwulan":
        bulan_list = TRIWULAN[pilihan]
        return df[df["bulan"].isin(bulan_list)]
    elif mode == "Semester":
        bulan_list = SEMESTER[pilihan]
        return df[df["bulan"].isin(bulan_list)]
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Group by kategori + lokasi, sum kolom numerik."""
    if df.empty:
        return df
    grp = (
        df.groupby(["kategori_jabatan", "kategori_display", "lokasi_id", "lokasi_label"], as_index=False)
        .agg(
            anggaran_awal=("anggaran_awal", "sum"),
            anggaran_terpakai=("anggaran_terpakai", "sum"),
            anggaran_sisa=("anggaran_sisa", "sum"),
        )
    )
    # Urutkan sesuai KATEGORI_ORDER
    grp["sort_key"] = grp["kategori_jabatan"].apply(
        lambda x: KATEGORI_ORDER.index(x) if x in KATEGORI_ORDER else 99
    )
    return grp.sort_values(["sort_key", "lokasi_label"]).drop(columns="sort_key")


# ─────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────
def main():
    st.title("💰 RKAP Monitor")
    st.caption("Monitor realisasi anggaran perjalanan dinas PTMB")

    # ── Sidebar filter ──────────────────────────────
    with st.sidebar:
        st.header("🔧 Filter")

        tahun = st.selectbox("Tahun", options=[2026, 2027], index=0)

        mode = st.radio(
            "Periode",
            options=["Tahunan", "Bulanan", "Triwulan", "Semester"],
            index=0,
        )

        pilihan_periode = None
        if mode == "Bulanan":
            pilihan_periode = st.selectbox("Pilih Bulan", list(BULAN_LABEL.values()))
        elif mode == "Triwulan":
            pilihan_periode = st.selectbox("Pilih Triwulan", list(TRIWULAN.keys()))
        elif mode == "Semester":
            pilihan_periode = st.selectbox("Pilih Semester", list(SEMESTER.keys()))

        lokasi_filter = st.multiselect(
            "Lokasi",
            options=list(LOKASI_LABEL.values()),
            default=list(LOKASI_LABEL.values()),
        )

        kelompok_filter = st.multiselect(
            "Kelompok",
            options=["Dewas", "Direksi", "Administrasi", "Teknik", "Bantuan"],
            default=["Dewas", "Direksi", "Administrasi", "Teknik", "Bantuan"],
        )

    # ── Load data ───────────────────────────────────
    df_raw = load_rkap(tahun)

    if df_raw.empty:
        st.warning(f"Tidak ada data RKAP untuk tahun {tahun}.")
        return

    # Filter periode
    df_filtered = filter_bulan(df_raw, mode, pilihan_periode)

    # Filter lokasi
    df_filtered = df_filtered[df_filtered["lokasi_label"].isin(lokasi_filter)]

    # Filter kelompok kategori
    KELOMPOK_MAP = {
        "Dewas":        ["DEWAS_KETUA", "DEWAS_ANGGOTA_1", "DEWAS_ANGGOTA_2"],
        "Direksi":      ["DIRUT", "DIRUM", "DIRTEK", "DIROPS"],
        "Administrasi": ["ADM_MANAJER", "ADM_SUPERVISOR", "ADM_STAF_PELAKSANA"],
        "Teknik":       ["TEKNIK_MANAJER", "TEKNIK_SUPERVISOR", "TEKNIK_STAF_PELAKSANA"],
        "Bantuan":      ["bantuan_sppd", "bantuan_sppd_luar_negeri"],
    }
    allowed_kat = []
    for k in kelompok_filter:
        allowed_kat.extend(KELOMPOK_MAP.get(k, []))
    df_filtered = df_filtered[df_filtered["kategori_jabatan"].isin(allowed_kat)]

    # Aggregate
    df_agg = aggregate(df_filtered)

    if df_agg.empty:
        st.info("Tidak ada data sesuai filter yang dipilih.")
        return

    # ── KPI cards ───────────────────────────────────
    total_awal     = df_agg["anggaran_awal"].sum()
    total_terpakai = df_agg["anggaran_terpakai"].sum()
    total_sisa     = df_agg["anggaran_sisa"].sum()
    pct_global     = (total_terpakai / total_awal * 100) if total_awal > 0 else 0

    label_periode = mode if mode == "Tahunan" else f"{mode} – {pilihan_periode}"
    st.markdown(f"**Periode:** {label_periode} &nbsp;|&nbsp; **Tahun:** {tahun}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Total Anggaran", format_rp(total_awal))
    col2.metric("✅ Terpakai", format_rp(total_terpakai))
    col3.metric("💵 Sisa", format_rp(total_sisa))
    col4.metric("📊 % Terpakai", f"{pct_global:.1f}%")

    # Peringatan over budget
    over_budget = df_agg[df_agg["anggaran_sisa"] < 0]
    if not over_budget.empty:
        items_over = ", ".join(
            f"{r['kategori_display']} ({r['lokasi_label']})"
            for _, r in over_budget.iterrows()
        )
        st.error(f"🚨 **Over Budget:** {items_over}")

    st.divider()

    # ── Tabs ────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📋 Tabel Summary", "📊 Grafik Perbandingan", "📅 Detail per Bulan"])

    # ── TAB 1: TABEL ────────────────────────────────
    with tab1:
        st.subheader("Rekapitulasi RKAP per Kategori")

        # Build display table
        rows = []
        for _, r in df_agg.iterrows():
            pct = (r["anggaran_terpakai"] / r["anggaran_awal"] * 100) if r["anggaran_awal"] > 0 else 0
            if pct > 100:
                status_icon = "🚨 OVER"
            elif pct >= 90:
                status_icon = "🔴"
            elif pct >= 75:
                status_icon = "🟡"
            else:
                status_icon = "🟢"
            rows.append({
                "Kategori":   r["kategori_display"],
                "Lokasi":     r["lokasi_label"],
                "Anggaran":   format_rp(r["anggaran_awal"]),
                "Terpakai":   format_rp(r["anggaran_terpakai"]),
                "Sisa":       format_rp(r["anggaran_sisa"]),
                "% Pakai":    f"{pct:.1f}%",
                "Status":     status_icon,
            })

        df_display = pd.DataFrame(rows)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.caption("🟢 < 75%  |  🟡 75–90%  |  🔴 90–100%  |  🚨 OVER > 100%")

    # ── TAB 2: GRAFIK ────────────────────────────────
    with tab2:
        st.subheader("Perbandingan Anggaran vs Realisasi")

        # Warna per lokasi: anggaran = solid terang, terpakai = solid gelap (kontras jelas)
        LOKASI_COLORS = {
            "Dalam Kaltim": {"anggaran": "#64B5F6", "terpakai": "#1565C0"},  # biru muda vs biru tua
            "Luar Kaltim":  {"anggaran": "#81C784", "terpakai": "#2E7D32"},  # hijau muda vs hijau tua
            "Luar Negeri":  {"anggaran": "#FFB74D", "terpakai": "#E65100"},  # oranye muda vs oranye tua
        }

        # Bar chart per kategori (grouped by lokasi)
        fig = go.Figure()

        for lok in df_agg["lokasi_label"].unique():
            df_lok  = df_agg[df_agg["lokasi_label"] == lok].copy()
            colors  = LOKASI_COLORS.get(lok, {"anggaran": "rgba(150,150,150,0.4)", "terpakai": "rgba(80,80,80,1)"})

            fig.add_trace(go.Bar(
                name=f"Anggaran – {lok}",
                x=df_lok["kategori_display"],
                y=df_lok["anggaran_awal"],
                marker_color=colors["anggaran"],
                legendgroup=lok,
            ))
            fig.add_trace(go.Bar(
                name=f"Terpakai – {lok}",
                x=df_lok["kategori_display"],
                y=df_lok["anggaran_terpakai"],
                marker_color=colors["terpakai"],
                legendgroup=lok,
            ))

        fig.update_layout(
            barmode="group",
            xaxis_tickangle=-35,
            yaxis_title="Rupiah (Rp)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=480,
            margin=dict(b=120),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Pie chart sisa vs terpakai (global)
        st.subheader("Proporsi Serapan Keseluruhan")
        fig_pie = go.Figure(go.Pie(
            labels=["Terpakai", "Sisa"],
            values=[total_terpakai, total_sisa],
            marker_colors=["tomato", "mediumseagreen"],
            hole=0.45,
            textinfo="label+percent",
        ))
        fig_pie.update_layout(height=320)
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── TAB 3: DETAIL PER BULAN ──────────────────────
    with tab3:
        st.subheader("Detail Realisasi per Bulan")

        # Pilih kategori spesifik
        kat_options = sorted(
            df_raw["kategori_display"].unique().tolist(),
            key=lambda d: KATEGORI_ORDER.index(
                next((k for k, v in KATEGORI_DISPLAY.items() if v == d), d)
            ) if any(v == d for v in KATEGORI_DISPLAY.values()) else 99
        )
        kat_pilih = st.selectbox("Pilih Kategori", kat_options)
        lok_pilih = st.selectbox("Pilih Lokasi", list(LOKASI_LABEL.values()))

        lok_id_pilih = {v: k for k, v in LOKASI_LABEL.items()}.get(lok_pilih)
        kat_raw_pilih = {v: k for k, v in KATEGORI_DISPLAY.items()}.get(kat_pilih, kat_pilih)

        df_detail = df_raw[
            (df_raw["kategori_jabatan"] == kat_raw_pilih) &
            (df_raw["lokasi_id"] == lok_id_pilih)
        ].sort_values("bulan")

        if df_detail.empty:
            st.info("Data tidak tersedia untuk kombinasi ini.")
        else:
            # Line chart
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=df_detail["bulan_label"],
                y=df_detail["anggaran_awal"],
                name="Anggaran",
                mode="lines+markers",
                line=dict(color="steelblue", width=2),
            ))
            fig_line.add_trace(go.Scatter(
                x=df_detail["bulan_label"],
                y=df_detail["anggaran_terpakai"],
                name="Terpakai",
                mode="lines+markers",
                line=dict(color="tomato", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,99,71,0.15)",
            ))
            fig_line.add_trace(go.Scatter(
                x=df_detail["bulan_label"],
                y=df_detail["anggaran_sisa"],
                name="Sisa",
                mode="lines+markers",
                line=dict(color="mediumseagreen", width=2, dash="dot"),
            ))
            fig_line.update_layout(
                yaxis_title="Rupiah (Rp)",
                height=380,
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_line, use_container_width=True)

            # Tabel detail bulanan
            tbl_rows = []
            for _, r in df_detail.iterrows():
                pct = (r["anggaran_terpakai"] / r["anggaran_awal"] * 100) if r["anggaran_awal"] > 0 else 0
                tbl_rows.append({
                    "Bulan":    r["bulan_label"],
                    "Anggaran": format_rp(r["anggaran_awal"]),
                    "Terpakai": format_rp(r["anggaran_terpakai"]),
                    "Sisa":     format_rp(r["anggaran_sisa"]),
                    "% Pakai":  f"{pct:.1f}%",
                    "Bar":      pct_bar(r["anggaran_terpakai"], r["anggaran_awal"]),
                })
            st.dataframe(pd.DataFrame(tbl_rows), use_container_width=True, hide_index=True)

            # ── Detail SPPD per bulan yang dipilih ──────────────
            st.markdown("---")
            st.markdown("**Detail penggunaan: siapa saja yang berangkat di bulan ini**")

            bulan_ada = df_detail["bulan_label"].tolist()
            # Default ke bulan pertama yang ada terpakai > 0, kalau tidak ada, bulan pertama saja
            bulan_dengan_terpakai = df_detail[df_detail["anggaran_terpakai"] > 0]["bulan_label"].tolist()
            default_idx = bulan_ada.index(bulan_dengan_terpakai[0]) if bulan_dengan_terpakai else 0

            bulan_detail_pilih = st.selectbox(
                "Pilih bulan:",
                options=bulan_ada,
                index=default_idx,
                key=f"detail_bulan_{kat_pilih}_{lok_pilih}",
            )

            row_bulan = df_detail[df_detail["bulan_label"] == bulan_detail_pilih]
            if not row_bulan.empty:
                rkap_id_pilih = row_bulan.iloc[0]["id"]

                supabase = get_client()
                res_s = supabase.table("sppd")\
                    .select(
                        "status, subtotal_uang_saku, total_hotel, total_transport, total_biaya,"
                        " pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama)),"
                        " visum(nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali)"
                    )\
                    .eq("rkap_id", rkap_id_pilih)\
                    .neq("status", "cancelled")\
                    .execute()

                sppd_rows = res_s.data or []
                if sppd_rows:
                    det_rows = []
                    for s in sppd_rows:
                        peg   = s.get("pegawai") or {}
                        visum = s.get("visum") or {}
                        det_rows.append({
                            "Nama":          peg.get("nama", "-"),
                            "Jabatan":       (peg.get("jabatan") or {}).get("nama", "-"),
                            "Visum":         visum.get("nomor_visum", "-"),
                            "Tujuan":        visum.get("tujuan", "-"),
                            "Tgl Berangkat": (visum.get("tanggal_berangkat") or "")[:10],
                            "Tgl Kembali":   (visum.get("tanggal_kembali") or "")[:10],
                            "Status":        s.get("status", "-").upper(),
                            "Uang Saku":     format_rp(s.get("subtotal_uang_saku") or 0),
                            "Hotel":         format_rp(s.get("total_hotel") or 0),
                            "Total":         format_rp(s.get("total_biaya") or 0),
                        })
                    st.dataframe(pd.DataFrame(det_rows), use_container_width=True, hide_index=True)
                    grand = sum(s.get("total_biaya") or 0 for s in sppd_rows)
                    st.caption(
                        f"**{len(sppd_rows)} SPPD aktif** di {bulan_detail_pilih} "
                        f"({kat_pilih} – {lok_pilih}) | "
                        f"Grand Total: **{format_rp(grand)}**"
                    )
                else:
                    st.info(f"Tidak ada SPPD aktif yang deduct ke RKAP {bulan_detail_pilih}.")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
else:
    main()