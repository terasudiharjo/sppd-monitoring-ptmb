import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.database import (
    get_client,
    get_all_rule_rates, get_rkap_rows_tahun, get_realokasi_history,
    eksekusi_realokasi, eksekusi_realokasi_multi, MIN_HARI_LOKASI, KATEGORI_TO_RULE_JABATAN,
)
from datetime import date as _date
from collections import OrderedDict

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
    # anggaran_pagu: fallback ke anggaran_awal kalau belum diisi
    if "anggaran_pagu" not in df.columns:
        df["anggaran_pagu"] = df["anggaran_awal"]
    else:
        df["anggaran_pagu"] = df["anggaran_pagu"].fillna(df["anggaran_awal"])
    return df


@st.cache_data(ttl=300)
def load_rule_rates() -> dict:
    """Cache rate uang_saku dari rule_sppd. TTL 5 menit."""
    return get_all_rule_rates()


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
            anggaran_pagu=("anggaran_pagu", "sum"),
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
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Tabel Summary", "📊 Grafik Perbandingan", "📅 Detail per Bulan", "🔄 Realokasi RKAP"])

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
            pagu = r.get("anggaran_pagu") or r["anggaran_awal"]
            ada_realokasi = pagu != r["anggaran_awal"]
            rows.append({
                "Kategori":     r["kategori_display"],
                "Lokasi":       r["lokasi_label"],
                "Pagu Awal":    format_rp(pagu),
                "Anggaran":     format_rp(r["anggaran_awal"]) + (" *" if ada_realokasi else ""),
                "Terpakai":     format_rp(r["anggaran_terpakai"]),
                "Sisa":         format_rp(r["anggaran_sisa"]),
                "% Pakai":      f"{pct:.1f}%",
                "Status":       status_icon,
            })

        df_display = pd.DataFrame(rows)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.caption("🟢 < 75%  |  🟡 75–90%  |  🔴 90–100%  |  🚨 OVER > 100%  |  * = sudah ada realokasi")

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
                        peg    = s.get("pegawai") or {}
                        visum  = s.get("visum") or {}
                        status = s.get("status", "-")
                        det_rows.append({
                            "Nama":          peg.get("nama", "-"),
                            "Jabatan":       (peg.get("jabatan") or {}).get("nama", "-"),
                            "Visum":         visum.get("nomor_visum", "-"),
                            "Tujuan":        visum.get("tujuan", "-"),
                            "Tgl Berangkat": (visum.get("tanggal_berangkat") or "")[:10],
                            "Tgl Kembali":   (visum.get("tanggal_kembali") or "")[:10],
                            "Status":        ("⏳ DRAFT*" if status == "draft" else status.upper()),
                            "Uang Saku":     format_rp(s.get("subtotal_uang_saku") or 0),
                            "Hotel":         format_rp(s.get("total_hotel") or 0),
                            "Total":         format_rp(s.get("total_biaya") or 0),
                        })
                    st.dataframe(pd.DataFrame(det_rows), use_container_width=True, hide_index=True)

                    # Grand total hanya dari yang sudah deduct RKAP (pencairan/realisasi/completed)
                    sudah_pencairan = [s for s in sppd_rows if s.get("status") != "draft"]
                    draft_rows      = [s for s in sppd_rows if s.get("status") == "draft"]
                    grand           = sum(s.get("total_biaya") or 0 for s in sudah_pencairan)

                    caption_parts = [
                        f"**{len(sudah_pencairan)} SPPD** (pencairan/realisasi/completed) di {bulan_detail_pilih} "
                        f"({kat_pilih} – {lok_pilih}) | Total terpakai: **{format_rp(grand)}**"
                    ]
                    if draft_rows:
                        grand_draft = sum(s.get("total_biaya") or 0 for s in draft_rows)
                        caption_parts.append(
                            f"⚠️ *\\* {len(draft_rows)} SPPD masih DRAFT — belum deduct RKAP "
                            f"(estimasi: {format_rp(grand_draft)})*"
                        )
                    for cp in caption_parts:
                        st.caption(cp)
                else:
                    st.info(f"Tidak ada SPPD aktif yang deduct ke RKAP {bulan_detail_pilih}.")

    # ── TAB 4: REALOKASI RKAP ───────────────────────────
    with tab4:
        st.subheader("Realokasi Anggaran RKAP")
        st.caption(
            "Pindahkan sisa anggaran dari satu baris RKAP ke baris lain. "
            "Setiap perubahan tercatat sebagai audit trail dan dapat dilakukan berkali-kali."
        )

        # Load semua baris RKAP tahun ini (fresh, tidak pakai cache load_rkap)
        all_rows = get_rkap_rows_tahun(tahun)
        rkap_by_id = {r["id"]: r for r in all_rows}

        # Load rate uang_saku dari rule_sppd (cached)
        all_rates = load_rule_rates()

        LOKASI_ID_ORDER = [LOKASI_DALAM, LOKASI_LUAR, LOKASI_LN]

        def _row_label(r, show_sisa=True):
            kat = KATEGORI_DISPLAY.get(r["kategori_jabatan"], r["kategori_jabatan"])
            lok = LOKASI_LABEL.get(r["lokasi_id"], "?")
            bln = BULAN_LABEL.get(r["bulan"], str(r["bulan"]))
            if show_sisa:
                sisa = r.get("anggaran_sisa") or 0
                sisa_str = (f"Rp {sisa:,}" if sisa >= 0 else f"-Rp {abs(sisa):,}").replace(",", ".")
                return f"{kat} – {lok} – {bln}  |  sisa: {sisa_str}"
            return f"{kat} – {lok} – {bln}"

        _EMPTY_RULE = {"uang_harian": 0, "plafon_pesawat": 0, "plafon_hotel": 0}

        def _get_rate(r):
            rule_jab = KATEGORI_TO_RULE_JABATAN.get(r.get("kategori_jabatan", ""))
            if not rule_jab:
                return _EMPTY_RULE
            return all_rates.get((rule_jab, r.get("lokasi_id", "")), _EMPTY_RULE)

        sorted_rows = sorted(all_rows, key=lambda r: (
            KATEGORI_ORDER.index(r["kategori_jabatan"]) if r["kategori_jabatan"] in KATEGORI_ORDER else 99,
            LOKASI_ID_ORDER.index(r["lokasi_id"]) if r["lokasi_id"] in LOKASI_ID_ORDER else 9,
            r["bulan"],
        ))

        # ── Session state ──
        if "rlk_moves_list" not in st.session_state:
            st.session_state.rlk_moves_list = []
        if "rlk_show_preview" not in st.session_state:
            st.session_state.rlk_show_preview = False
        if "rlk_last_success" not in st.session_state:
            st.session_state.rlk_last_success = None  # pesan sukses terakhir

        # ── Load history (dipakai di ringkasan & riwayat) ─────────────────────
        history = get_realokasi_history(tahun)
        batches_order = list(OrderedDict.fromkeys(h["batch_id"] for h in history))
        batch_map = {}
        for h in history:
            batch_map.setdefault(h["batch_id"], []).append(h)

        # ── Ringkasan Saldo per Triwulan (pivot) ─────────────────────────────
        st.markdown("### Ringkasan Saldo Anggaran per Triwulan")

        TW_COLS = {
            "TW I\n(Jan–Mar)":   [1, 2, 3],
            "TW II\n(Apr–Jun)":  [4, 5, 6],
            "TW III\n(Jul–Sep)": [7, 8, 9],
            "TW IV\n(Okt–Des)":  [10, 11, 12],
        }

        # ── Snapshot selector ─────────────────────────────────────────────────
        snap_options = ["📌 Anggaran Awal (sebelum semua perubahan)"]
        for i, bid in enumerate(batches_order):
            items_b = batch_map[bid]
            tgl = items_b[0]["tanggal"][:10]
            ket = items_b[0].get("keterangan") or f"Perubahan {i + 1}"
            snap_options.append(f"Setelah Perubahan {i + 1}: {ket} ({tgl})")
        snap_options.append("✅ Kondisi Saat Ini")

        snap_sel = st.selectbox(
            "Lihat kondisi anggaran:",
            options=snap_options,
            index=len(snap_options) - 1,
            key="rlk_snap_sel",
        )
        snap_idx = snap_options.index(snap_sel)
        is_current = snap_idx == len(snap_options) - 1
        is_awal    = snap_idx == 0

        if not is_current:
            st.info(f"Mode historis — menampilkan simulasi kondisi anggaran **{snap_sel}**. Data pengeluaran (terpakai) tetap menggunakan data aktual saat ini.")

        # ── Bangun snap_awal: anggaran_awal tiap row di snapshot yang dipilih ─
        # Mulai dari anggaran_pagu (anggaran asli, tidak pernah berubah)
        snap_awal = {r["id"]: (r.get("anggaran_pagu") or r.get("anggaran_awal") or 0) for r in all_rows}

        if is_current:
            snap_awal = {r["id"]: (r.get("anggaran_awal") or 0) for r in all_rows}
        elif not is_awal:
            # Apply batch 1 s/d snap_idx (snap_idx=1 → batch pertama, dst)
            for bid in batches_order[:snap_idx]:
                for item in batch_map[bid]:
                    if item["dari_rkap_id"] in snap_awal:
                        snap_awal[item["dari_rkap_id"]] -= item["jumlah"]
                    if item["ke_rkap_id"] in snap_awal:
                        snap_awal[item["ke_rkap_id"]]   += item["jumlah"]

        def _sisa_snap(r):
            awal     = snap_awal.get(r["id"], 0)
            terpakai = r.get("anggaran_terpakai") or 0
            if is_current:
                return r.get("anggaran_sisa") or 0
            return awal - terpakai

        # ── Pivot tabel TW ────────────────────────────────────────────────────
        def _fmt_tw_sisa(val):
            if val < 0:
                return f"🚨 -{abs(int(val)):,}".replace(",", ".")
            return f"🟢 {int(val):,}".replace(",", ".")

        tw_totals = {}
        for r in all_rows:
            key = (r["kategori_jabatan"], r["lokasi_id"])
            if key not in tw_totals:
                tw_totals[key] = {tw: 0 for tw in TW_COLS}
            for tw_label, bulan_list in TW_COLS.items():
                if r["bulan"] in bulan_list:
                    tw_totals[key][tw_label] += _sisa_snap(r)

        pivot_rows = []
        for (kat_raw, lok_id), tw_vals in sorted(
            tw_totals.items(),
            key=lambda x: (
                KATEGORI_ORDER.index(x[0][0]) if x[0][0] in KATEGORI_ORDER else 99,
                LOKASI_ID_ORDER.index(x[0][1]) if x[0][1] in LOKASI_ID_ORDER else 9,
            )
        ):
            row = {
                "Kategori": KATEGORI_DISPLAY.get(kat_raw, kat_raw),
                "Lokasi":   LOKASI_LABEL.get(lok_id, "?"),
            }
            for tw_label in TW_COLS:
                row[tw_label.replace("\n", " ")] = _fmt_tw_sisa(tw_vals[tw_label])
            pivot_rows.append(row)

        if pivot_rows:
            st.dataframe(pd.DataFrame(pivot_rows), use_container_width=True, hide_index=True)
        st.caption("🚨 = minus (perlu tambahan)  |  🟢 = surplus (bisa jadi sumber)")

        # ── Detail per TW (expander) ──────────────────────────────────────────
        st.markdown("**Detail saldo per bulan dalam triwulan:**")
        for tw_label, bulan_list in TW_COLS.items():
            tw_label_short = tw_label.replace("\n", " ")
            with st.expander(f"📅 {tw_label_short}", expanded=False):
                det_rows = []
                for r in sorted_rows:
                    if r["bulan"] not in bulan_list:
                        continue
                    awal_r   = snap_awal.get(r["id"], 0)
                    terpakai = r.get("anggaran_terpakai") or 0
                    sisa     = _sisa_snap(r)
                    pct      = (terpakai / awal_r * 100) if awal_r > 0 else 0
                    if sisa < 0:
                        st_icon = "🚨"
                    elif pct >= 90:
                        st_icon = "🔴"
                    elif pct >= 75:
                        st_icon = "🟡"
                    else:
                        st_icon = "🟢"
                    det_rows.append({
                        "Kategori": KATEGORI_DISPLAY.get(r["kategori_jabatan"], r["kategori_jabatan"]),
                        "Lokasi":   LOKASI_LABEL.get(r["lokasi_id"], "?"),
                        "Bulan":    BULAN_LABEL.get(r["bulan"], str(r["bulan"])),
                        "Anggaran": format_rp(awal_r),
                        "Terpakai": format_rp(terpakai),
                        "Sisa":     format_rp(sisa),
                        "St":       st_icon,
                    })
                if det_rows:
                    st.dataframe(pd.DataFrame(det_rows), use_container_width=True, hide_index=True)

        st.divider()

        # ── Riwayat Realokasi ──────────────────────────────────────────────────
        st.markdown(f"### Riwayat Realokasi {tahun}")
        if not history:
            st.info("Belum ada riwayat realokasi untuk tahun ini.")
        else:
            # Tabel ringkas semua batch (langsung visible)
            summary_hist = []
            for bid in batches_order:
                items_b = batch_map[bid]
                total_b = sum(i["jumlah"] for i in items_b)
                tgl     = items_b[0]["tanggal"][:10]
                unique_ke   = list(dict.fromkeys(i["ke_rkap_id"] for i in items_b))
                unique_dari = list(dict.fromkeys(i["dari_rkap_id"] for i in items_b))
                if len(unique_ke) == 1:
                    ke_r = rkap_by_id.get(unique_ke[0])
                    ke_str = _row_label(ke_r, show_sisa=False) if ke_r else unique_ke[0][:8]
                else:
                    ke_str = f"{len(unique_ke)} tujuan berbeda"
                if len(unique_dari) <= 2:
                    dari_labels = []
                    for did in unique_dari:
                        dari_r = rkap_by_id.get(did)
                        dari_labels.append(_row_label(dari_r, show_sisa=False) if dari_r else did[:8])
                    dari_str = " + ".join(dari_labels)
                else:
                    dari_str = f"{len(unique_dari)} sumber"
                summary_hist.append({
                    "Tanggal":      tgl,
                    "Move":         len(items_b),
                    "Dari":         dari_str,
                    "Ke":           ke_str,
                    "Total Pindah": format_rp(total_b),
                    "Keterangan":   items_b[0].get("keterangan") or "-",
                })
            st.dataframe(pd.DataFrame(summary_hist), use_container_width=True, hide_index=True)

            # Detail per batch (collapsed)
            with st.expander("Lihat detail rincian per batch", expanded=False):
                for bid in batches_order:
                    items_b = batch_map[bid]
                    total_b = sum(i["jumlah"] for i in items_b)
                    tgl     = items_b[0]["tanggal"][:10]
                    ket     = items_b[0].get("keterangan") or "-"
                    unique_ke = list(dict.fromkeys(i["ke_rkap_id"] for i in items_b))
                    if len(unique_ke) == 1:
                        ke_r = rkap_by_id.get(unique_ke[0])
                        ke_str = _row_label(ke_r, show_sisa=False) if ke_r else unique_ke[0][:8]
                        st.markdown(f"**{tgl}** — {len(items_b)} move → **{ke_str}** | Total: **{format_rp(total_b)}**")
                    else:
                        st.markdown(f"**{tgl}** — {len(items_b)} move ke {len(unique_ke)} tujuan | Total: **{format_rp(total_b)}**")
                    st.caption(f"Keterangan: {ket}")
                    rows_h = []
                    for i in items_b:
                        dari_r = rkap_by_id.get(i["dari_rkap_id"])
                        ke_r   = rkap_by_id.get(i["ke_rkap_id"])
                        rows_h.append({
                            "Dari":      _row_label(dari_r, show_sisa=False) if dari_r else i["dari_rkap_id"][:8],
                            "Ke":        _row_label(ke_r, show_sisa=False) if ke_r else i["ke_rkap_id"][:8],
                            "Trip":      i["jumlah_token"],
                            "Hari/Trip": i["hari_per_token"],
                            "Rate/Hari": format_rp(i["rate_per_hari"]),
                            "Jumlah":    format_rp(i["jumlah"]),
                        })
                    st.dataframe(pd.DataFrame(rows_h), use_container_width=True, hide_index=True)
                    st.markdown("---")

        st.divider()
        st.markdown("### Buat Realokasi Baru")

        moves_list = st.session_state.rlk_moves_list

        # ── Helper: net delta dari moves yang sudah diqueue ──
        def _pending_deltas(ml):
            d = {}
            for m in ml:
                d[m["dari_rkap_id"]] = d.get(m["dari_rkap_id"], 0) - m["jumlah"]
                d[m["ke_rkap_id"]]   = d.get(m["ke_rkap_id"], 0)   + m["jumlah"]
            return d

        def _eff_sisa(rid, deltas):
            r = rkap_by_id.get(rid, {})
            return (r.get("anggaran_sisa") or 0) + deltas.get(rid, 0)

        # ── Tampilkan daftar moves yang sudah diqueue ──
        if moves_list:
            st.markdown(f"**Daftar Perpindahan yang Direncanakan ({len(moves_list)} move):**")
            for idx, move in enumerate(moves_list):
                r_d = rkap_by_id.get(move["dari_rkap_id"])
                r_k = rkap_by_id.get(move["ke_rkap_id"])
                lbl_d = _row_label(r_d, show_sisa=False) if r_d else move["dari_rkap_id"][:8]
                lbl_k = _row_label(r_k, show_sisa=False) if r_k else move["ke_rkap_id"][:8]
                nilai_trip = move["jumlah"] // move["jumlah_token"] if move["jumlah_token"] else 0
                col_d, col_k, col_v, col_x = st.columns([4, 4, 3, 1])
                with col_d: st.write(f"**{lbl_d}**")
                with col_k: st.write(f"→ {lbl_k}")
                with col_v:
                    st.write(
                        f"{move['jumlah_token']} trip × {format_rp(nilai_trip)}"
                        f" = **{format_rp(move['jumlah'])}**"
                    )
                with col_x:
                    if st.button("✕", key=f"rlk_del_{idx}", help="Hapus move ini"):
                        st.session_state.rlk_moves_list.pop(idx)
                        st.session_state.rlk_show_preview = False
                        st.rerun()
            st.divider()

        # ── Form tambah move baru ──
        st.markdown("**Tambah Perpindahan Baru:**")
        pending = _pending_deltas(moves_list)

        col_src, col_dst = st.columns(2)
        with col_src:
            sumber_sel_id = st.selectbox(
                "Sumber (Dari)",
                options=[r["id"] for r in sorted_rows],
                format_func=lambda rid: (
                    _row_label(rkap_by_id[rid], show_sisa=False)
                    + f"  |  efektif sisa: {format_rp(max(0, _eff_sisa(rid, pending)))}"
                    if _eff_sisa(rid, pending) >= 0
                    else _row_label(rkap_by_id[rid], show_sisa=False)
                    + f"  |  efektif sisa: -{format_rp(abs(_eff_sisa(rid, pending)))}"
                ),
                key="rlk_sumber_sel",
            )
        with col_dst:
            tujuan_avail = [r for r in sorted_rows if r["id"] != sumber_sel_id]
            tujuan_sel_id = st.selectbox(
                "Tujuan (Ke)",
                options=[r["id"] for r in tujuan_avail],
                format_func=lambda rid: _row_label(rkap_by_id[rid], show_sisa=False),
                key="rlk_tujuan_sel",
            )

        r_sel = rkap_by_id.get(sumber_sel_id, {})
        rule_sel    = _get_rate(r_sel)
        uang_harian = rule_sel["uang_harian"]
        min_hari    = MIN_HARI_LOKASI.get(r_sel.get("lokasi_id", ""), 1)
        eff_sisa_src = _eff_sisa(sumber_sel_id, pending)

        col_h, col_t, col_info = st.columns(3)
        with col_h:
            hari_per_token = st.number_input(
                f"Hari/trip (min {min_hari})",
                min_value=min_hari, max_value=30,
                value=max(min_hari, 4), step=1,
                key="rlk_hari_per_token",
            )
        pesawat_pp      = rule_sel["plafon_pesawat"] * 2
        hotel_per_trip  = rule_sel["plafon_hotel"] * max(0, hari_per_token - 1)
        nilai_per_token = uang_harian * hari_per_token + pesawat_pp + hotel_per_trip
        max_tok = max(1, int(eff_sisa_src // nilai_per_token)) if nilai_per_token > 0 else 1

        with col_t:
            jumlah_token = st.number_input(
                f"Jumlah trip (maks {max_tok})",
                min_value=1, max_value=max(1, max_tok),
                value=1, step=1,
                key="rlk_token_input",
            )
        jumlah_rp    = int(jumlah_token * nilai_per_token)
        sisa_after   = eff_sisa_src - jumlah_rp
        sisa_ok      = sisa_after >= 0 and nilai_per_token > 0

        with col_info:
            st.metric("Nilai/trip", format_rp(nilai_per_token))
            st.caption(
                f"Harian: {format_rp(uang_harian)}/hr × {hari_per_token}  \n"
                f"Pesawat PP: {format_rp(pesawat_pp)}  \n"
                f"Hotel: {format_rp(rule_sel['plafon_hotel'])}/mlm × {max(0, hari_per_token-1)}"
            )

        col_rp, col_btn = st.columns([3, 2])
        with col_rp:
            st.metric("Rupiah dipindah", format_rp(jumlah_rp))
            if sisa_ok:
                st.caption(f"Sisa sumber setelah: {format_rp(int(sisa_after))} ✓")
            elif nilai_per_token == 0:
                st.caption("Rate tidak ditemukan untuk kategori ini")
            else:
                st.caption(f"Sisa sumber tidak cukup ({format_rp(int(eff_sisa_src))} < {format_rp(jumlah_rp)})")
        with col_btn:
            st.write("")
            if st.button("+ Tambah ke Daftar", disabled=not sisa_ok, key="rlk_tambah_btn", use_container_width=True):
                st.session_state.rlk_moves_list.append({
                    "dari_rkap_id": sumber_sel_id,
                    "ke_rkap_id":   tujuan_sel_id,
                    "jumlah_token": int(jumlah_token),
                    "hari_per_token": int(hari_per_token),
                    "rate_per_hari": int(uang_harian),
                    "jumlah": jumlah_rp,
                })
                st.session_state.rlk_show_preview = False
                st.rerun()

        # ── Keterangan + tombol aksi ──
        if moves_list:
            st.divider()
            keterangan = st.text_input(
                "Keterangan batch realokasi ini",
                placeholder="Contoh: Realokasi Dewas semester 1 → semester 2",
                key="rlk_keterangan",
            )

            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                if st.button("🔍 Preview & Konfirmasi", type="primary", key="rlk_preview_btn"):
                    st.session_state.rlk_show_preview = True
            with col_btn2:
                if st.button("🗑️ Reset Semua", type="secondary", key="rlk_reset_btn"):
                    st.session_state.rlk_moves_list = []
                    st.session_state.rlk_show_preview = False
                    st.rerun()

            # ── Preview ──
            if st.session_state.rlk_show_preview:
                st.divider()
                st.markdown("#### Preview Realokasi")

                # Tabel daftar moves
                prev_rows = []
                for move in moves_list:
                    r_d = rkap_by_id.get(move["dari_rkap_id"], {})
                    r_k = rkap_by_id.get(move["ke_rkap_id"], {})
                    nilai_trip = move["jumlah"] // move["jumlah_token"] if move["jumlah_token"] else 0
                    prev_rows.append({
                        "Dari":        _row_label(r_d, show_sisa=False) if r_d else move["dari_rkap_id"][:8],
                        "Ke":          _row_label(r_k, show_sisa=False) if r_k else move["ke_rkap_id"][:8],
                        "Trip":        move["jumlah_token"],
                        "Hari/Trip":   move["hari_per_token"],
                        "Nilai/Trip":  format_rp(nilai_trip),
                        "Total Pindah": format_rp(move["jumlah"]),
                    })
                st.dataframe(pd.DataFrame(prev_rows), use_container_width=True, hide_index=True)

                total_pindah = sum(m["jumlah"] for m in moves_list)
                st.caption(f"**Total semua perpindahan: {format_rp(total_pindah)}**  |  Keterangan: {keterangan or '(kosong)'}")

                # ── Pivot sebelum/sesudah per kategori+lokasi per bulan ──
                st.divider()
                st.markdown("#### Dampak ke Anggaran per Bulan")

                BULAN_SHORT = {
                    1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Mei",6:"Jun",
                    7:"Jul",8:"Agu",9:"Sep",10:"Okt",11:"Nov",12:"Des"
                }

                # Temukan kombinasi kategori+lokasi yang terdampak
                affected_delta = _pending_deltas(moves_list)
                affected_combos = set()
                for rid in affected_delta:
                    r = rkap_by_id.get(rid, {})
                    affected_combos.add((r.get("kategori_jabatan",""), r.get("lokasi_id","")))

                # Kumpulkan semua 12 bulan untuk setiap combo yang terdampak
                combo_before = {}  # (kat,lok) → {bulan: anggaran_awal}
                combo_after  = {}
                for r in sorted_rows:
                    kat = r.get("kategori_jabatan","")
                    lok = r.get("lokasi_id","")
                    if (kat, lok) not in affected_combos:
                        continue
                    bln = r.get("bulan", 0)
                    key = (kat, lok)
                    if key not in combo_before:
                        combo_before[key] = {}
                        combo_after[key]  = {}
                    aa = r.get("anggaran_awal", 0)
                    delta = affected_delta.get(r["id"], 0)
                    combo_before[key][bln] = aa
                    combo_after[key][bln]  = aa + delta

                # Sort sesuai urutan kategori
                def _sort_key(key_tuple):
                    kat, lok = key_tuple
                    return (
                        KATEGORI_ORDER.index(kat) if kat in KATEGORI_ORDER else 99,
                        LOKASI_ID_ORDER.index(lok) if lok in LOKASI_ID_ORDER else 9,
                    )

                def _build_pivot(combo_data):
                    rows = []
                    for key in sorted(combo_data.keys(), key=_sort_key):
                        kat, lok = key
                        row = {
                            "Kategori": KATEGORI_DISPLAY.get(kat, kat),
                            "Lokasi":   LOKASI_LABEL.get(lok, lok),
                        }
                        for m in range(1, 13):
                            row[BULAN_SHORT[m]] = combo_data[key].get(m, 0)
                        rows.append(row)
                    return pd.DataFrame(rows) if rows else pd.DataFrame()

                df_before = _build_pivot(combo_before)
                df_after  = _build_pivot(combo_after)

                st.markdown("**Anggaran Sebelum Realokasi (Rp)**")
                st.dataframe(df_before, use_container_width=True, hide_index=True)

                st.markdown("**Anggaran Sesudah Realokasi (Rp)**")
                st.dataframe(df_after, use_container_width=True, hide_index=True)

                st.divider()
                col_ok, col_cancel = st.columns([3, 1])
                with col_ok:
                    if st.button("✅ Konfirmasi & Simpan Realokasi", type="primary", use_container_width=True, key="rlk_konfirmasi"):
                        ok, err = eksekusi_realokasi_multi(
                            moves=moves_list,
                            keterangan=keterangan,
                            tanggal=str(_date.today()),
                        )
                        if ok:
                            st.session_state.rlk_last_success = (
                                f"Realokasi berhasil! {len(moves_list)} perpindahan, "
                                f"total {format_rp(total_pindah)} direlokasi."
                            )
                            st.session_state.rlk_moves_list   = []
                            st.session_state.rlk_show_preview = False
                            load_rkap.clear()
                            st.rerun()
                        else:
                            st.error(f"Gagal: {err}")
                with col_cancel:
                    if st.button("Batal", type="secondary", use_container_width=True, key="rlk_batal"):
                        st.session_state.rlk_show_preview = False
                        st.rerun()

        # ── Notifikasi sukses ──
        if st.session_state.rlk_last_success:
            st.success(st.session_state.rlk_last_success)
            if st.button("✓ Tutup notifikasi", key="rlk_tutup_notif"):
                st.session_state.rlk_last_success = None
                st.rerun()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
else:
    main()