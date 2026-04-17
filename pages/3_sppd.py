import re
import streamlit as st
from utils.database import (
    get_rkap_id, get_rule_sppd, detect_lokasi,
    deduct_rkap, rollback_rkap, update_rekap_spd,
    JABATAN_SORT_ORDER, LOKASI_BANTUAN_ID,
    get_plafon_hotel, save_biaya_lain, get_biaya_lain,
    save_transport_detail, get_transport_detail,
    get_pegawai_by_jabatan_nama, resolve_kategori_rkap,
    recalculate_sppd,
)
from utils.pdf_generator import (
    generate_sppd_pencairan, generate_sppd_realisasi, generate_pernyataan_biaya
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

# ─── HELPER ────────────────────────────────────────────
def _strip_div_prefix(nama: str) -> str:
    return re.sub(r"^(sub[\s.]*divisi|divisi)[\s.]*", "", nama, flags=re.IGNORECASE).strip().title()

def format_jabatan_sppd_penerima(jabatan_nama: str, divisi_obj: dict, divisi_map: dict) -> str:
    """Format jabatan untuk judul & TTD PDF SPPD (tidak disingkat, title case).
    - Tamu     → '' (kosong, tidak ditampilkan)
    - Manajer  → 'Manajer [parent divisi]'
    - Supervisor → 'Supervisor [own sub-divisi]'
    - Staf     → 'Staf [own sub-divisi]'
    - Lainnya  → jabatan.title()
    """
    if jabatan_nama.upper().startswith("TAMU"):
        return ""
    if not divisi_obj or not isinstance(divisi_obj, dict):
        return jabatan_nama.title()
    jab = jabatan_nama.lower()
    if "manajer" in jab or "manager" in jab:
        parent_id = divisi_obj.get("parent_id")
        parent_nama = divisi_map.get(parent_id, {}).get("nama", "") if parent_id else ""
        div_label = _strip_div_prefix(parent_nama) if parent_nama else _strip_div_prefix(divisi_obj.get("nama", ""))
        return f"Manajer {div_label}".strip()
    elif "supervisor" in jab:
        return f"Supervisor {_strip_div_prefix(divisi_obj.get('nama', ''))}".strip()
    elif "staf" in jab or "pelaksana" in jab:
        return f"Staf {_strip_div_prefix(divisi_obj.get('nama', ''))}".strip()
    else:
        return jabatan_nama.title()

def format_rupiah(amount) -> str:
    if not amount:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
st.title("📋 Manajemen SPPD")
st.markdown("---")

# Tab "Buat SPPD Baru" dihapus — SPPD otomatis dibuat dari halaman Visum
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

    # Ambil SPD aktif (bukan completed) — tidak join visum karena SPD bisa multi-visum / tanpa visum_id
    res_spd = db.table("spd")\
        .select("id, nomor_spd, tanggal_spd, status")\
        .neq("status", "completed")\
        .order("created_at", desc=True)\
        .execute()

    spd_data_all = res_spd.data or []

    if not spd_data_all:
        st.info("Tidak ada SPPD aktif.")
    else:
        # ── Pilih SPD ──
        spd_options = {
            f"{s['nomor_spd']}": s
            for s in spd_data_all
        }
        spd_keys = list(spd_options.keys())

        # Persist pilihan SPD
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
        # Update session state hanya kalau berubah (bukan dari rerun setelah update)
        if selected_spd_key != st.session_state.detail_spd_key:
            st.session_state.detail_spd_key = selected_spd_key
            # Reset pilihan pegawai kalau SPD berubah
            for key in list(st.session_state.keys()):
                if key.startswith("detail_sppd_key_"):
                    del st.session_state[key]

        selected_spd = spd_options[st.session_state.detail_spd_key]

        st.markdown("---")

        # ── Pilih Pegawai ──
        res = db.table("sppd")\
            .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan_id, jabatan(nama, struktur_rkap), divisi(id, nama, parent_id)), visum(nomor_visum, tujuan, tanggal_visum, tanggal_berangkat, tanggal_kembali), spd(nomor_spd, tanggal_spd)")\
            .eq("spd_id", selected_spd["id"])\
            .order("created_at", desc=True)\
            .execute()
        sppd_dalam_spd = res.data
        # Build divisi_map untuk parent lookup (format jabatan)
        divisi_map_sppd = {}
        for _s in sppd_dalam_spd:
            _div = (_s.get("pegawai") or {}).get("divisi")
            if _div and _div.get("id"):
                divisi_map_sppd[_div["id"]] = _div

        if not sppd_dalam_spd:
            st.info("Belum ada SPPD dalam SPD ini.")
        else:
            sppd_options = {
                f"{s['pegawai']['nama'] if s.get('pegawai') else '-'} — {s['status'].upper()}": s
                for s in sppd_dalam_spd
            }
            sppd_keys = list(sppd_options.keys())

            # Persist pilihan pegawai per SPD
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
            # Update session state hanya kalau user yang ganti (bukan rerun)
            if selected_key != st.session_state[state_key]:
                st.session_state[state_key] = selected_key

            s = sppd_options[st.session_state[state_key]]

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
                st.markdown(f"- Uang Representasi : **{format_rupiah(s.get('uang_representasi_total', 0))}**")
                st.markdown(f"**Subtotal Uang Saku : {format_rupiah(s.get('subtotal_uang_saku', 0))}**")

            with col_r2:
                st.markdown("**Realisasi:**")
                st.markdown(f"- Transport &nbsp;&nbsp;: **{format_rupiah(s.get('total_transport', 0))}**")
                st.markdown(f"- Hotel &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: **{format_rupiah(s.get('total_hotel', 0))}**")
                biaya_lain_disp = max(0, (s.get("total_biaya") or 0) - (s.get("subtotal_uang_saku") or 0) - (s.get("total_transport") or 0) - (s.get("total_hotel") or 0))
                st.markdown(f"- Biaya Lain &nbsp;: **{format_rupiah(biaya_lain_disp)}**")
                st.markdown(f"**Total Realisasi : {format_rupiah(s.get('total_biaya', 0))}**")

            st.markdown("---")

            # ── 🖨️ PRINT DOKUMEN ──
            st.markdown("#### 🖨️ Print Dokumen")

            # Helper: siapkan data dasar untuk PDF
            def _parse_date(d):
                if not d: return date.today()
                if isinstance(d, date): return d
                try: return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
                except: return date.today()

            visum_data  = s.get("visum") or {}
            pegawai_data = s.get("pegawai") or {}
            spd_data    = s.get("spd") or {}

            _jab_fmt = format_jabatan_sppd_penerima(
                pegawai_data.get("jabatan", {}).get("nama", ""),
                pegawai_data.get("divisi"),
                divisi_map_sppd,
            )
            _jab_label = f"{_jab_fmt} PTMB" if _jab_fmt else ""
            base_data = {
                "nama_pejabat":     _jab_label,
                "nomor_spd":        spd_data.get("nomor_spd", "-"),
                "tanggal":          _parse_date(visum_data.get("tanggal_visum")) or date.today(),
                "tempat_tujuan":    visum_data.get("tujuan", ""),
                "tgl_berangkat":    _parse_date(visum_data.get("tanggal_berangkat")),
                "tgl_kembali":      _parse_date(visum_data.get("tanggal_kembali")),
                "lama_hari":        s.get("total_hari", 0),
                "nama_penerima":    pegawai_data.get("nama", "").title(),
                "jabatan_penerima": _jab_label,
                "uang_harian":      (
                    (s.get("uang_harian_total") or 0) +
                    (s.get("uang_makan_total") or 0) +
                    (s.get("transport_lokal_total") or 0)
                ) // (s.get("total_hari") or 1),
                "uang_representasi": s.get("uang_representasi_total", 0) // s.get("total_hari", 1) if s.get("total_hari") and s.get("uang_representasi_total") else 0,
                "biaya_penginapan": 0,
                "ttd_dirut":        "Dr. Saharuddin, M.M",
            }

            col_pdf1, col_pdf2, col_pdf3 = st.columns(3)

            # ── Tombol SPPD Pencairan (dari draft) ──
            with col_pdf1:
                if s["status"] == "draft":
                    st.info("Klik Print untuk generate SPPD & ubah status → **PENCAIRAN**")

                    if st.button("🔄 Hitung Ulang", key=f"btn_recalc_{s['id']}",
                                 help="Hitung ulang uang saku berdasarkan tarif rule_sppd terkini"):
                        hasil = recalculate_sppd(s["id"])
                        if hasil["success"]:
                            st.success(f"✅ {hasil['pesan']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {hasil['pesan']}")

                    # Toggle menginap — disimpan ke kolom sppd.menginap
                    menginap = st.toggle(
                        "Menginap Hotel",
                        value=s.get("menginap", True),
                        key=f"menginap_{s['id']}"
                    )

                    jabatan_id_pgw = (s.get("pegawai") or {}).get("jabatan_id")
                    plafon = get_plafon_hotel(jabatan_id_pgw, s["lokasi_id"]) if jabatan_id_pgw else 0
                    max_malam = max((s.get("total_hari") or 1) - 1, 0)
                    hotel_30pct = 0

                    if not menginap:
                        # Semua tidak menginap → seluruh malam dapat 30%
                        hari_tidak_menginap = max_malam
                        hotel_30pct = int(plafon * 0.30 * hari_tidak_menginap)
                        st.caption(f"Tidak menginap: {hari_tidak_menginap} malam × {format_rupiah(plafon)} × 30% = **{format_rupiah(hotel_30pct)}**")
                    else:
                        # Ada yang menginap — mungkin ada sebagian malam tidak menginap
                        hari_tidak_menginap = st.number_input(
                            "Hari tidak menginap hotel (dapat 30%)",
                            min_value=0, max_value=max_malam,
                            value=int(s.get("hari_tidak_menginap") or 0),
                            step=1, key=f"hari_tdk_{s['id']}"
                        )
                        hotel_30pct = int(plafon * 0.30 * hari_tidak_menginap)
                        if hari_tidak_menginap > 0:
                            st.caption(f"→ {hari_tidak_menginap} malam × {format_rupiah(plafon)} × 30% = **{format_rupiah(hotel_30pct)}**")

                    if st.button("🖨️ Print SPPD Pencairan",
                                 use_container_width=True, type="primary",
                                 key=f"btn_print_{s['id']}"):
                        uang_saku = s.get("subtotal_uang_saku") or 0
                        total_cair = uang_saku + hotel_30pct
                        # Resolve rkap_id jika belum ada
                        rkap_id = s.get("rkap_id")
                        if not rkap_id:
                            peg_data = db.table("pegawai").select("jabatan(struktur_rkap), divisi(bidang, parent_id), divisi_id").eq("id", s["pegawai_id"]).single().execute().data
                            if peg_data:
                                struktur = (peg_data.get("jabatan") or {}).get("struktur_rkap", "")
                                div = peg_data.get("divisi") or {}
                                bidang = div.get("bidang")
                                if not bidang and div.get("parent_id"):
                                    p = db.table("divisi").select("bidang").eq("id", div["parent_id"]).single().execute().data
                                    bidang = p["bidang"] if p else None
                                kategori = resolve_kategori_rkap(struktur, bidang or "", s["lokasi_id"])
                                rkap_lokasi_id = LOKASI_BANTUAN_ID if kategori == "bantuan_sppd" else s["lokasi_id"]
                                tgl = (s.get("visum") or {}).get("tanggal_berangkat", "")
                                if tgl:
                                    bulan = int(tgl[5:7]); tahun = int(tgl[:4])
                                    rkap_id = get_rkap_id(kategori, rkap_lokasi_id, bulan, tahun)
                                    if rkap_id:
                                        db.table("sppd").update({"rkap_id": rkap_id}).eq("id", s["id"]).execute()
                        # Update status + menginap + hotel (kalau tidak menginap)
                        db.table("sppd").update({
                            "status":               "pencairan",
                            "menginap":             menginap,
                            "hari_tidak_menginap":  hari_tidak_menginap,
                            "total_hotel":          hotel_30pct,
                            "total_biaya":          total_cair,
                        }).eq("id", s["id"]).execute()
                        if rkap_id:
                            deduct_rkap(rkap_id, total_cair)
                        # Generate PDF
                        pencairan_data = {**base_data, "biaya_penginapan": hotel_30pct}
                        pdf_bytes = generate_sppd_pencairan(pencairan_data).read()
                        nama_file = f"SPPD_Pencairan_{pegawai_data.get('nama','').replace(' ','_')}.pdf"
                        st.download_button(
                            label="⬇️ Unduh SPPD Pencairan",
                            data=pdf_bytes,
                            file_name=nama_file,
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"dl_pencairan_{s['id']}"
                        )
                        # Update label dropdown agar nama tidak reset
                        nama_pgw  = pegawai_data.get("nama", "-")
                        st.session_state[state_key] = f"{nama_pgw} — PENCAIRAN"
                        st.rerun()

                elif s["status"] in ["pencairan", "realisasi", "completed"]:
                    # Bisa download ulang kapan saja
                    # Rekonstruksi biaya_penginapan dari DB
                    jabatan_id_pgw = (s.get("pegawai") or {}).get("jabatan_id")
                    plafon_cair = get_plafon_hotel(jabatan_id_pgw, s["lokasi_id"]) if jabatan_id_pgw else 0
                    hari_tdk_cair = s.get("hari_tidak_menginap") or 0
                    if not s.get("menginap", True) and hari_tdk_cair == 0:
                        # Record lama (sebelum fitur partial): pakai total_hotel dari DB
                        biaya_penginapan_cair = s.get("total_hotel", 0)
                    else:
                        biaya_penginapan_cair = int(plafon_cair * 0.30 * hari_tdk_cair)
                    pencairan_data = {**base_data, "biaya_penginapan": biaya_penginapan_cair}
                    pdf_bytes = generate_sppd_pencairan(pencairan_data).read()
                    nama_file = f"SPPD_Pencairan_{pegawai_data.get('nama','').replace(' ','_')}.pdf"
                    st.download_button(
                        label="⬇️ Download SPPD Pencairan",
                        data=pdf_bytes,
                        file_name=nama_file,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_pencairan_{s['id']}"
                    )
                    if s["status"] == "pencairan":
                        if st.button("🔄 Hitung Ulang Uang Saku", key=f"btn_recalc_{s['id']}",
                                     help="Hitung ulang uang saku + adjust RKAP. Total hotel tidak berubah."):
                            hasil = recalculate_sppd(s["id"])
                            if hasil["success"]:
                                st.success(f"✅ {hasil['pesan']}")
                                st.rerun()
                            else:
                                st.error(f"❌ {hasil['pesan']}")

            # ── Tombol SPPD Realisasi (hanya kalau udah realisasi/completed) ──
            with col_pdf2:
                if s["status"] in ["realisasi", "completed"]:
                    tr_detail_pdf = get_transport_detail(s["id"])
                    real_data = {
                        **base_data,
                        "biaya_penginapan_aktual": s.get("total_hotel", 0),
                        "items_transport": [
                            {
                                "keterangan": f"{t['kota_asal']} - {t['kota_tujuan']}"
                                              + (f" ({t['jenis_transport']})" if t.get("jenis_transport") else ""),
                                "qty": 1,
                                "satuan": t["biaya_transport"],
                            }
                            for t in tr_detail_pdf if (t.get("biaya_transport") or 0) > 0
                        ],
                        "biaya_lain": get_biaya_lain(s["id"]),
                        "grand_total": s.get("total_biaya", 0),
                    }
                    pdf_bytes = generate_sppd_realisasi(real_data).read()
                    nama_file = f"SPPD_Realisasi_{pegawai_data.get('nama','').replace(' ','_')}.pdf"
                    st.download_button(
                        label="⬇️ Download SPPD Realisasi",
                        data=pdf_bytes,
                        file_name=nama_file,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_realisasi_{s['id']}"
                    )
                else:
                    st.caption("SPPD Realisasi\ntersedia setelah status REALISASI")

            # ── Tombol Pernyataan Biaya Riil ──
            with col_pdf3:
                if s["status"] in ["realisasi", "completed"]:
                    dir_umum = get_pegawai_by_jabatan_nama("DIREKTUR BIDANG UMUM")
                    dir_umum_nama = dir_umum["nama"].title() if dir_umum else "Direktur Umum"
                    pb_data = {
                        "nomor_surat":            spd_data.get("nomor_spd", "-").replace("-O", ""),
                        "nomor_spd":              spd_data.get("nomor_spd", "-"),
                        "tanggal_spd":            _parse_date(spd_data.get("tanggal_spd")) or date.today(),
                        "nama":                   pegawai_data.get("nama", "").title(),
                        "jabatan":                _jab_label,
                        "nomor_surat_tugas":      spd_data.get("nomor_spd", "-").replace("-O", "-F"),
                        "tempat_kegiatan":        visum_data.get("tujuan", ""),
                        "tanggal_berangkat":      visum_data.get("tanggal_berangkat"),
                        "tanggal_kembali":        visum_data.get("tanggal_kembali"),
                        "biaya_perjalanan":       s.get("subtotal_uang_saku", 0),
                        "biaya_penginapan":       s.get("total_hotel", 0),
                        "biaya_transport":        s.get("total_transport", 0),
                        "biaya_lain":             max(0, (s.get("total_biaya") or 0) - (s.get("subtotal_uang_saku") or 0) - (s.get("total_hotel") or 0) - (s.get("total_transport") or 0)),
                        "grand_total":            s.get("total_biaya", 0),
                        "tanggal_ttd":            date.today(),
                        "ttd_mengetahui_jabatan": "Direktur Umum",
                        "ttd_mengetahui_nama":    dir_umum_nama,
                        "nama_penerima":          pegawai_data.get("nama", "").title(),
                        "jabatan_penerima":       _jab_label,
                    }
                    pdf_bytes = generate_pernyataan_biaya(pb_data).read()
                    nama_file = f"Pernyataan_Biaya_{pegawai_data.get('nama','').replace(' ','_')}.pdf"
                    st.download_button(
                        label="⬇️ Download Pernyataan Biaya",
                        data=pdf_bytes,
                        file_name=nama_file,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_pb_{s['id']}"
                    )
                else:
                    st.caption("Pernyataan Biaya\ntersedia setelah status REALISASI")

            st.markdown("---")

            col_left, col_right = st.columns(2)

            with col_left:
                st.markdown("**Update Status Manual**")

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

                        if new_status == "pencairan" and old_status == "draft" and not rkap_id:
                            peg_data = db.table("pegawai").select("jabatan(struktur_rkap), divisi(bidang, parent_id)").eq("id", s["pegawai_id"]).single().execute().data
                            if peg_data:
                                struktur = (peg_data.get("jabatan") or {}).get("struktur_rkap", "")
                                div = peg_data.get("divisi") or {}
                                bidang = div.get("bidang")
                                if not bidang and div.get("parent_id"):
                                    p = db.table("divisi").select("bidang").eq("id", div["parent_id"]).single().execute().data
                                    bidang = p["bidang"] if p else None
                                kategori = resolve_kategori_rkap(struktur, bidang or "", s["lokasi_id"])
                                rkap_lokasi_id = LOKASI_BANTUAN_ID if kategori == "bantuan_sppd" else s["lokasi_id"]
                                tgl = (s.get("visum") or {}).get("tanggal_berangkat", "")
                                if tgl:
                                    bulan = int(tgl[5:7]); tahun = int(tgl[:4])
                                    rkap_id = get_rkap_id(kategori, rkap_lokasi_id, bulan, tahun)
                                    if rkap_id:
                                        db.table("sppd").update({"rkap_id": rkap_id}).eq("id", s["id"]).execute()

                        if rkap_id:
                            if new_status == "pencairan" and old_status == "draft":
                                deduct_rkap(rkap_id, uang_saku)
                            elif new_status == "cancelled":
                                if old_status == "pencairan":
                                    rollback_rkap(rkap_id, uang_saku)

                        st.success("✅ Status berhasil diupdate!")
                        # Persist pilihan pegawai setelah update status
                        # Label berubah karena status berubah — cari label baru
                        nama_pegawai = s["pegawai"]["nama"] if s.get("pegawai") else "-"
                        new_label = f"{nama_pegawai} — {new_status.upper()}"
                        st.session_state[state_key] = new_label
                        st.rerun()

            with col_right:
                if s["status"] == "realisasi":
                    st.markdown("**Input Realisasi Biaya**")

                    # ── Rincian Transport ──
                    st.markdown("**Rincian Transport**")
                    lokasi_info    = detect_lokasi(visum_data.get("tujuan", ""))
                    is_luar_kaltim = lokasi_info.get("lokasi_nama", "") != "Dalam Kaltim"
                    tr_items = []  # default kosong (Dalam Kaltim)

                    if not is_luar_kaltim:
                        total_transport = 0
                        st.caption("📍 Perjalanan Dalam Kaltim — tidak ada biaya transport pesawat.")
                    else:
                        transport_key = f"transport_detail_{s['id']}"
                        if transport_key not in st.session_state:
                            existing_tr = get_transport_detail(s["id"])
                            st.session_state[transport_key] = existing_tr if existing_tr else [
                                {"kota_asal": "", "kota_tujuan": "", "jenis_transport": "", "biaya_transport": 0}
                            ]

                        tr_items = st.session_state[transport_key]
                        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([3, 3, 2, 2, 1])
                        col_h1.caption("Kota Asal")
                        col_h2.caption("Kota Tujuan")
                        col_h3.caption("Jenis")
                        col_h4.caption("Biaya (Rp)")

                        for i, tr in enumerate(tr_items):
                            col_a, col_b, col_c, col_d, col_e = st.columns([3, 3, 2, 2, 1])
                            tr["kota_asal"] = col_a.text_input(
                                "Asal", tr.get("kota_asal", ""),
                                key=f"tr_asal_{s['id']}_{i}", label_visibility="collapsed", placeholder="Balikpapan"
                            )
                            tr["kota_tujuan"] = col_b.text_input(
                                "Tujuan", tr.get("kota_tujuan", ""),
                                key=f"tr_tujuan_{s['id']}_{i}", label_visibility="collapsed", placeholder="Jakarta"
                            )
                            tr["jenis_transport"] = col_c.text_input(
                                "Jenis", tr.get("jenis_transport", ""),
                                key=f"tr_jenis_{s['id']}_{i}", label_visibility="collapsed", placeholder="Pesawat"
                            )
                            biaya_val = col_d.number_input(
                                "Biaya", value=int(tr.get("biaya_transport", 0)),
                                step=50000, key=f"tr_biaya_{s['id']}_{i}", label_visibility="collapsed"
                            )
                            col_d.caption(f"→ {format_rupiah(biaya_val)}")
                            tr["biaya_transport"] = biaya_val
                            if col_e.button("🗑", key=f"tr_del_{s['id']}_{i}") and len(tr_items) > 1:
                                tr_items.pop(i)
                                st.rerun()

                        if st.button("➕ Tambah Rute", key=f"tr_add_{s['id']}"):
                            tr_items.append({"kota_asal": "", "kota_tujuan": "", "jenis_transport": "", "biaya_transport": 0})
                            st.rerun()

                        total_transport = sum(int(tr.get("biaya_transport", 0)) for tr in tr_items)
                        st.caption(f"Total Transport: **{format_rupiah(total_transport)}**")

                    # Hotel: cek status menginap dari pencairan
                    menginap_pencairan = s.get("menginap", True)
                    jabatan_id_pgw = (s.get("pegawai") or {}).get("jabatan_id")
                    plafon_real = get_plafon_hotel(jabatan_id_pgw, s["lokasi_id"]) if jabatan_id_pgw else 0
                    max_malam_real = max((s.get("total_hari") or 1) - 1, 0)

                    if not menginap_pencairan:
                        # Locked: semua tidak menginap sejak pencairan
                        hari_tdk_db = s.get("hari_tidak_menginap") or max_malam_real  # fallback record lama
                        total_hotel = int(plafon_real * 0.30 * hari_tdk_db)
                        hari_tidak_menginap = hari_tdk_db
                        st.caption(f"Tidak menginap (dari pencairan): {hari_tdk_db} malam × {format_rupiah(plafon_real)} × 30% = **{format_rupiah(total_hotel)}**")
                    else:
                        # Toggle aktif: user bisa pilih menginap atau tidak
                        menginap_real = st.toggle(
                            "Menginap Hotel",
                            value=True,
                            key=f"menginap_real_{s['id']}"
                        )
                        if menginap_real:
                            # Hitung pre-fill biaya aktual = total_hotel_DB − kompensasi 30% sebelumnya
                            hari_tdk_db = s.get("hari_tidak_menginap") or 0
                            kompensasi_lama = int(plafon_real * 0.30 * hari_tdk_db)
                            prefill_aktual = max(0, int(s.get("total_hotel") or 0) - kompensasi_lama)

                            biaya_hotel_aktual = st.number_input(
                                "Biaya Hotel Aktual (Rp)",
                                value=prefill_aktual,
                                step=50000,
                                key=f"hotel_{s['id']}"
                            )
                            hari_tidak_menginap = st.number_input(
                                "Hari tidak menginap hotel (dapat 30%)",
                                min_value=0, max_value=max_malam_real,
                                value=hari_tdk_db, step=1,
                                key=f"hari_tdk_real_{s['id']}"
                            )
                            kompensasi_30pct = int(plafon_real * 0.30 * hari_tidak_menginap)
                            if hari_tidak_menginap > 0:
                                st.caption(f"→ {hari_tidak_menginap} malam × {format_rupiah(plafon_real)} × 30% = **{format_rupiah(kompensasi_30pct)}**")
                            total_hotel = biaya_hotel_aktual + kompensasi_30pct
                            st.caption(f"Total Hotel: **{format_rupiah(total_hotel)}**")
                        else:
                            hari_tidak_menginap = max_malam_real
                            total_hotel = int(plafon_real * 0.30 * hari_tidak_menginap)
                            st.caption(f"Tidak menginap: {hari_tidak_menginap} malam × {format_rupiah(plafon_real)} × 30% = **{format_rupiah(total_hotel)}**")

                    # ── Biaya Lain-lain ──
                    st.markdown("**Biaya Lain-lain**")
                    biaya_lain_key = f"biaya_lain_{s['id']}"
                    if biaya_lain_key not in st.session_state:
                        existing = get_biaya_lain(s["id"])
                        st.session_state[biaya_lain_key] = existing if existing else [{"keterangan": "", "jumlah": 0}]

                    items = st.session_state[biaya_lain_key]
                    for i, item in enumerate(items):
                        col_ket, col_jml, col_del = st.columns([4, 2, 1])
                        item["keterangan"] = col_ket.text_input(
                            "Keterangan", item.get("keterangan", ""),
                            key=f"ket_{s['id']}_{i}", label_visibility="collapsed"
                        )
                        jml_val = col_jml.number_input(
                            "Jumlah (Rp)", value=int(item.get("jumlah", 0)),
                            step=50000, key=f"jml_{s['id']}_{i}", label_visibility="collapsed"
                        )
                        col_jml.caption(f"→ {format_rupiah(jml_val)}")
                        item["jumlah"] = jml_val
                        if col_del.button("🗑", key=f"del_{s['id']}_{i}") and len(items) > 1:
                            items.pop(i)
                            st.rerun()

                    if st.button("➕ Tambah Biaya Lain", key=f"add_{s['id']}"):
                        items.append({"keterangan": "", "jumlah": 0})
                        st.rerun()

                    total_biaya_lain = sum(int(x.get("jumlah", 0)) for x in items)
                    total_realisasi = (s.get("subtotal_uang_saku") or 0) + total_transport + total_hotel + total_biaya_lain
                    st.markdown(f"**Total Realisasi: {format_rupiah(total_realisasi)}**")

                    if st.button("💾 Simpan Realisasi", use_container_width=True, key=f"btn_realisasi_{s['id']}"):
                        # Simpan rincian transport
                        valid_transport = [
                            t for t in tr_items
                            if t.get("kota_asal") and t.get("kota_tujuan") and int(t.get("biaya_transport", 0)) > 0
                        ]
                        save_transport_detail(
                            s["id"], valid_transport,
                            tgl_berangkat=visum_data.get("tanggal_berangkat"),
                            tgl_kembali=visum_data.get("tanggal_kembali"),
                        )
                        total_transport = sum(int(t["biaya_transport"]) for t in valid_transport)

                        # Simpan biaya lain
                        valid_items = [
                            {"keterangan": x["keterangan"], "jumlah": int(x["jumlah"])}
                            for x in items if x.get("keterangan") and int(x.get("jumlah", 0)) > 0
                        ]
                        save_biaya_lain(s["id"], valid_items)
                        total_lain_valid = sum(x["jumlah"] for x in valid_items)
                        total_realisasi_final = (s.get("subtotal_uang_saku") or 0) + total_transport + total_hotel + total_lain_valid

                        db.table("sppd").update({
                            "total_transport":      total_transport,
                            "total_hotel":          total_hotel,
                            "hari_tidak_menginap":  hari_tidak_menginap,
                            "total_biaya":          total_realisasi_final,
                        }).eq("id", s["id"]).execute()

                        # Selisih RKAP: bandingkan variable cost lama vs baru
                        rkap_id  = s.get("rkap_id")
                        old_var  = (s.get("total_biaya") or 0) - (s.get("subtotal_uang_saku") or 0)
                        new_var  = total_transport + total_hotel + total_lain_valid
                        selisih  = new_var - old_var
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
        .select("*")\
        .order("created_at", desc=True)\
        .execute()
    spd_list = res_spd.data

    # Cari tujuan visum per SPD lewat tabel sppd (alur baru: spd.visum_id tidak diisi)
    res_spd_visum = db.table("sppd")\
        .select("spd_id, visum(tujuan)")\
        .not_.is_("spd_id", "null")\
        .execute()
    spd_tujuan_map = {}
    for row in (res_spd_visum.data or []):
        sid = row.get("spd_id")
        if sid and sid not in spd_tujuan_map:
            v = row.get("visum")
            if v:
                spd_tujuan_map[sid] = v.get("tujuan", "-")

    if not spd_list:
        st.info("Belum ada data SPD.")
    else:
        spd_options = {
            f"{s['nomor_spd']} — {spd_tujuan_map.get(s['id'], '-')}": s
            for s in spd_list
        }
        selected_spd_key = st.selectbox("Pilih SPD", list(spd_options.keys()), key="rekap_spd_select")
        spd = spd_options[selected_spd_key]

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

        st.markdown("#### Daftar SPPD dalam SPD ini")
        res_detail = db.table("sppd")\
            .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama))")\
            .eq("spd_id", spd["id"])\
            .execute()

        if res_detail.data:
            import pandas as pd

            def get_sort_key(row):
                try:
                    jabatan_nama = row["pegawai"]["jabatan"]["nama"].upper().strip()
                except:
                    jabatan_nama = ""
                return JABATAN_SORT_ORDER.get(jabatan_nama, 99)

            sorted_data = sorted(res_detail.data, key=get_sort_key)

            df = pd.DataFrame([{
                "Nama": d["pegawai"]["nama"] if d.get("pegawai") else "-",
                "Jabatan": d["pegawai"]["jabatan"]["nama"] if d.get("pegawai") and d["pegawai"].get("jabatan") else "-",
                "Hari": d["total_hari"],
                "Uang Saku": format_rupiah(d.get("subtotal_uang_saku", 0)),
                "Transport": format_rupiah(d.get("total_transport", 0)),
                "Hotel": format_rupiah(d.get("total_hotel", 0)),
                "Biaya Lain": format_rupiah(max(0, (d.get("total_biaya") or 0) - (d.get("subtotal_uang_saku") or 0) - (d.get("total_transport") or 0) - (d.get("total_hotel") or 0))),
                "Total": format_rupiah(d.get("total_biaya", 0)),
                "Status": d["status"].upper(),
            } for d in sorted_data])

            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("🔄 Hitung Ulang Rekap", key="btn_rekap_ulang"):
                update_rekap_spd(spd["id"])
                st.success("✅ Rekap berhasil dihitung ulang!")
                st.rerun()