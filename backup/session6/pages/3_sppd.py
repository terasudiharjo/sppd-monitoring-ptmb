import streamlit as st
from utils.database import get_all_pegawai, get_rkap_id, get_rule_sppd, detect_lokasi
from utils.database import get_client, deduct_rkap, rollback_rkap
from utils.database import get_client, deduct_rkap, rollback_rkap, get_rkap_id
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
BULAN_ROMAWI = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"]

def format_rupiah(amount) -> str:
    if not amount:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")

def get_or_create_spd(visum_id: str, tanggal: date) -> dict:
    """Ambil SPD yang sudah ada, kalau belum ada buat baru."""
    res = db.table("spd").select("*")\
        .eq("visum_id", visum_id)\
        .execute()
    
    if res.data:
        return res.data[0]
    
    # Buat nomor SPD baru
    tahun = tanggal.year
    bulan = BULAN_ROMAWI[tanggal.month - 1]
    res_count = db.table("spd").select("nomor_spd")\
        .like("nomor_spd", f"%/{tahun}-O")\
        .execute()
    urutan = len(res_count.data) + 1
    nomor_spd = f"{urutan:04d}/1421002/10a-I/{bulan}/{tahun}-O"
    
    # Insert SPD baru
    res_insert = db.table("spd").insert({
        "nomor_spd": nomor_spd,
        "visum_id": visum_id,
        "tanggal_spd": str(tanggal),
        "status": "draft"
    }).execute()
    
    return res_insert.data[0]

def hitung_uang_saku(rule: dict, total_hari: int) -> dict:
    """Hitung semua komponen uang saku berdasarkan rule & jumlah hari."""
    uang_harian = (rule.get("uang_saku") or 0) * total_hari
    uang_makan = (rule.get("uang_makan") or 0) * total_hari
    transport_lokal = (rule.get("transport_lokal") or 0) * total_hari
    uang_rep = (rule.get("uang_rep") or 0) * total_hari
    subtotal = uang_harian + uang_makan + transport_lokal + uang_rep
    return {
        "uang_harian": uang_harian,
        "uang_makan": uang_makan,
        "transport_lokal": transport_lokal,
        "uang_rep": uang_rep,
        "subtotal": subtotal
    }

def update_rekap_spd(spd_id: str):
    """Hitung ulang rekap total SPD dari semua SPPD yang linked."""
    
    # Ambil divisi juga untuk resolve bidang
    res_divisi = db.table("divisi").select("id, parent_id, bidang").execute()
    divisi_map = {d["id"]: d for d in res_divisi.data}
    
    res = db.table("sppd")\
        .select("*, pegawai!sppd_pegawai_id_fkey(jabatan(struktur_rkap), divisi_id)")\
        .eq("spd_id", spd_id)\
        .neq("status", "cancelled")\
        .execute()
    
    rekap = {
        "total_direksi": 0,
        "total_dewas": 0,
        "total_administrasi": 0,
        "total_teknik": 0,
        "total_bantuan": 0,
    }
    
    for s in res.data:
        struktur = None
        bidang = None
        try:
            struktur = s["pegawai"]["jabatan"]["struktur_rkap"]
            div_id = s["pegawai"]["divisi_id"]
            div = divisi_map.get(div_id, {})
            # Resolve bidang — kalau subdiv, ambil dari parent
            bidang_raw = div.get("bidang") or divisi_map.get(div.get("parent_id"), {}).get("bidang")
            bidang = bidang_raw.title() if bidang_raw else None  # normalize: "TEKNIK" → "Teknik"
        except:
            pass
        # DEBUG — hapus setelah fix
        print(f"Nama: {s['pegawai'].get('nama', '?')} | struktur: {struktur} | div_id: {div_id} | div keys: {list(div.keys())} | bidang_raw: {bidang_raw} | bidang: {bidang}")
        # END DEBUG

        biaya = s.get("total_biaya") or 0
        
        if struktur in ["DIRUT", "DIRUM", "DIRTEK", "DIROPS"]:
            rekap["total_direksi"] += biaya
        elif struktur in ["DEWAS_KETUA", "DEWAS_ANGGOTA"]:
            rekap["total_dewas"] += biaya
        elif struktur in ["MANAJER", "SUPERVISOR", "STAF_PELAKSANA", "ADM_MANAJER", 
                          "ADM_SUPERVISOR", "ADM_STAF_PELAKSANA"]:
            if bidang == "Teknik":
                rekap["total_teknik"] += biaya
            else:
                rekap["total_administrasi"] += biaya
        elif struktur in ["TEKNIK_MANAJER", "TEKNIK_SUPERVISOR", "TEKNIK_STAF_PELAKSANA"]:
            rekap["total_teknik"] += biaya
        elif struktur == "BANTUAN":
            rekap["total_bantuan"] += biaya
        else:
            rekap["total_administrasi"] += biaya  # fallback
    
    rekap["grand_total"] = sum(rekap.values())
    db.table("spd").update(rekap).eq("id", spd_id).execute()

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
st.title("📋 Manajemen SPPD")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Daftar SPPD", 
    "➕ Buat SPPD Baru", 
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
                ["Semua", "draft", "pencairan", "dalam_perjalanan", 
                 "realisasi", "closed", "cancelled"])

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
# TAB 2: BUAT SPPD BARU
# ══════════════════════════════════════════════════════
with tab2:
    st.subheader("Buat SPPD Baru")

    # ── Pilih Visum ──
    st.markdown("### Step 1 — Pilih Visum")
    res_visum = db.table("visum").select("*")\
        .eq("status", "active")\
        .order("created_at", desc=True)\
        .execute()
    visum_list = res_visum.data

    if not visum_list:
        st.warning("Tidak ada visum aktif. Buat visum terlebih dahulu.")
        st.stop()

    visum_options = {
        f"{v['nomor_visum']} — {v['tujuan']} ({v['tanggal_berangkat']} s/d {v['tanggal_kembali']})": v
        for v in visum_list
    }
    selected_visum_key = st.selectbox("Pilih Visum", list(visum_options.keys()))
    selected_visum = visum_options[selected_visum_key]

    # Cek/buat SPD untuk visum ini
    spd_data = get_or_create_spd(selected_visum["id"], date.today())
    st.info(f"📋 Nomor SPD: **{spd_data['nomor_spd']}**")

    # Deteksi lokasi
    lokasi_info = detect_lokasi(selected_visum["tujuan"])
    if lokasi_info["confidence"] == "manual":
        st.warning(f"⚠️ Kota **{selected_visum['tujuan']}** tidak dikenali otomatis. Konfirmasi lokasi:")
        res_lokasi = db.table("lokasi_sppd").select("id, nama").execute()
        lokasi_list = res_lokasi.data
        lokasi_map = {l["nama"]: l["id"] for l in lokasi_list}
        manual_lokasi = st.selectbox("Pilih Lokasi Perjalanan", list(lokasi_map.keys()))
        lokasi_info["lokasi_nama"] = manual_lokasi
        lokasi_info["lokasi_id"] = lokasi_map[manual_lokasi]
    else:
        st.success(f"✅ Lokasi: **{lokasi_info['lokasi_nama']}**")

    # Cek siapa aja yang sudah punya SPPD di visum ini
    res_existing = db.table("sppd").select("pegawai_id")\
        .eq("spd_id", spd_data["id"])\
        .neq("status", "cancelled")\
        .execute()
    existing_pegawai_ids = [s["pegawai_id"] for s in res_existing.data]

    st.markdown("---")

    # ── Pilih Pegawai ──
    st.markdown("### Step 2 — Pilih Pegawai")

    pegawai_all = get_all_pegawai()
    peserta_ids = selected_visum.get("peserta", [])

    # Filter: peserta visum yang belum punya SPPD
    if peserta_ids:
        peserta_list = [p for p in pegawai_all 
                       if p["id"] in peserta_ids and p["id"] not in existing_pegawai_ids]
    else:
        peserta_list = [p for p in pegawai_all if p["id"] not in existing_pegawai_ids]

    if not peserta_list:
        st.success("✅ Semua peserta visum ini sudah memiliki SPPD.")
    else:
        if existing_pegawai_ids:
            st.caption(f"✅ {len(existing_pegawai_ids)} peserta sudah punya SPPD — menampilkan yang belum.")

        peserta_options = {f"{p['nip']} - {p['nama']}": p for p in peserta_list}
        selected_pegawai_key = st.selectbox("Pilih Pegawai", list(peserta_options.keys()))
        selected_pegawai = peserta_options[selected_pegawai_key]

        # Ambil rule SPPD
        jabatan_id = selected_pegawai.get("jabatan_id")
        rule = None
        if jabatan_id and lokasi_info.get("lokasi_id"):
            try:
                rule = get_rule_sppd(jabatan_id, lokasi_info["lokasi_id"])
            except:
                rule = None

        if rule:
            st.info(f"""
            💰 **Rule SPPD — {lokasi_info['lokasi_nama']}**  
            Uang Harian: {format_rupiah(rule.get('uang_saku'))} / hari  
            Uang Makan: {format_rupiah(rule.get('uang_makan'))} / hari  
            Transport Lokal: {format_rupiah(rule.get('transport_lokal'))} / hari  
            Uang Representasi: {format_rupiah(rule.get('uang_rep'))} / hari
            """)
        else:
            st.warning("⚠️ Rule SPPD tidak ditemukan untuk jabatan ini.")

        st.markdown("---")

        # ── Form Detail ──
        st.markdown("### Step 3 — Detail Perjalanan")

        with st.form("form_sppd_baru"):
            # Total hari otomatis dari visum, tidak bisa diubah
            total_hari = selected_visum.get("lama_hari", 1)
    
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Info Perjalanan (dari Visum)**")
                st.info(f"""
                📅 Berangkat: **{selected_visum['tanggal_berangkat']}**  
                📅 Kembali: **{selected_visum['tanggal_kembali']}**  
                🕐 Lama: **{total_hari} hari**  
                📍 Tujuan: **{selected_visum['tujuan']}**
                """)
                catatan = st.text_area("Catatan (opsional)", height=80)

            with col2:
                if rule:
                    calc = hitung_uang_saku(rule, total_hari)
                    st.markdown("**Preview Uang Saku:**")
                    st.markdown(f"- Uang Harian: **{format_rupiah(calc['uang_harian'])}**")
                    st.markdown(f"- Uang Makan: **{format_rupiah(calc['uang_makan'])}**")
                    st.markdown(f"- Transport Lokal: **{format_rupiah(calc['transport_lokal'])}**")
                    if calc['uang_rep'] > 0:
                        st.markdown(f"- Uang Representasi: **{format_rupiah(calc['uang_rep'])}**")
                    st.markdown(f"### Subtotal: {format_rupiah(calc['subtotal'])}")
                else:
                    calc = {"uang_harian": 0, "uang_makan": 0,
                        "transport_lokal": 0, "uang_rep": 0, "subtotal": 0}
                    st.warning("⚠️ Rule SPPD tidak ditemukan untuk jabatan ini.")

            submitted = st.form_submit_button("💾 Simpan SPPD", use_container_width=True)

            if submitted:
                if not rule:
                    st.error("❌ Tidak bisa menyimpan — rule SPPD tidak ditemukan!")
                else:
                    # Cari rkap_id
                    from datetime import date
                    bulan_berangkat = date.fromisoformat(selected_visum["tanggal_berangkat"]).month
                    tahun_berangkat = date.fromisoformat(selected_visum["tanggal_berangkat"]).year

                    # Mapping struktur_rkap + bidang → kategori_jabatan RKAP
                    struktur = selected_pegawai.get("jabatan", {}).get("struktur_rkap", "")
                    bidang = selected_pegawai.get("bidang_resolved", "")

                    if struktur == "MANAJER":
                        kategori = "ADM_MANAJER" if bidang == "Administrasi" else "TEKNIK_MANAJER"
                    elif struktur == "SUPERVISOR":
                        kategori = "ADM_SUPERVISOR" if bidang == "Administrasi" else "TEKNIK_SUPERVISOR"
                    elif struktur == "STAF_PELAKSANA":
                        kategori = "ADM_STAF_PELAKSANA" if bidang == "Administrasi" else "TEKNIK_STAF_PELAKSANA"
                    elif struktur == "DEWAS_ANGGOTA":
                        kategori = "DEWAS_ANGGOTA_1"  # default, bisa diubah nanti
                    else:
                        kategori = struktur  # DIRUT, DIRUM, DIRTEK, DIROPS, DEWAS_KETUA langsung pakai

                    rkap_id = get_rkap_id(kategori, lokasi_info["lokasi_id"], bulan_berangkat, tahun_berangkat)
                

                    try:    
                        db.table("sppd").insert({
                            "nomor_sppd": spd_data["nomor_spd"],
                            "spd_id": spd_data["id"],
                            "visum_id": selected_visum["id"],
                            "pegawai_id": selected_pegawai["id"],
                            "rkap_id": rkap_id,
                            "lokasi_id": lokasi_info["lokasi_id"],
                            "total_hari": total_hari,
                            "uang_harian_total": calc["uang_harian"],
                            "uang_makan_total": calc["uang_makan"],
                            "transport_lokal_total": calc["transport_lokal"],
                            "uang_representasi_total": calc["uang_rep"],
                            "subtotal_uang_saku": calc["subtotal"],
                            "total_biaya": calc["subtotal"],
                            "catatan_laporan": catatan,
                            "status": "draft"
                        }).execute()

                        # Update rekap SPD
                        update_rekap_spd(spd_data["id"])

                        st.success(f"✅ SPPD untuk **{selected_pegawai['nama']}** berhasil dibuat!")
                        st.success(f"📋 Nomor SPD: **{spd_data['nomor_spd']}**")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Gagal menyimpan: {e}")

# ══════════════════════════════════════════════════════
# TAB 3: DETAIL & REALISASI
# ══════════════════════════════════════════════════════
with tab3:
    st.subheader("Detail SPPD & Input Realisasi")

    # ── Step 1: Pilih Visum dulu ──
    res_spd = db.table("spd")\
        .select("*, visum(nomor_visum, tujuan, tanggal_berangkat, tanggal_kembali)")\
        .order("created_at", desc=True)\
        .execute()
    
    if not res_spd.data:
        st.info("Belum ada data SPD.")
    else:
        spd_options = {
            f"{s['nomor_spd']} — {s['visum']['tujuan'] if s.get('visum') else '-'}": s
            for s in res_spd.data
        }
        selected_spd_key = st.selectbox("📋 Pilih SPD / Visum", list(spd_options.keys()))
        selected_spd = spd_options[selected_spd_key]

        st.markdown("---")

        # ── Step 2: Tampilkan SPPD dalam SPD yang dipilih ──
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
            selected_key = st.selectbox("👤 Pilih Pegawai", list(sppd_options.keys()))
            s = sppd_options[selected_key]

            # Info cards
            col1, col2, col3 = st.columns(3)
            col1.metric("Pegawai", s["pegawai"]["nama"] if s.get("pegawai") else "-")
            col2.metric("Tujuan", s["visum"]["tujuan"] if s.get("visum") else "-")
            col3.metric("Status", s["status"].upper())

            col4, col5, col6 = st.columns(3)
            col4.metric("Durasi", f"{s.get('total_hari', 0)} hari")  # ← ganti dari Nomor SPD
            col5.metric("Uang Saku", format_rupiah(s.get("subtotal_uang_saku", 0)))
            col6.metric("Total Realisasi", format_rupiah(s.get("total_biaya", 0)))

            st.markdown("---")

            # Rincian uang saku
            st.markdown("#### 💰 Rincian Uang Saku")
            col_r1, col_r2 = st.columns(2)

            with col_r1:
                st.markdown("**Komponen Uang Saku:**")
                st.markdown(f"- Uang Harian &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: **{format_rupiah(s.get('uang_harian_total', 0))}**")
                st.markdown(f"- Uang Makan &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: **{format_rupiah(s.get('uang_makan_total', 0))}**")
                st.markdown(f"- Transport Lokal &nbsp;: **{format_rupiah(s.get('transport_lokal_total', 0))}**")
                if s.get('uang_representasi_total', 0) > 0:
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
                status_options = ["draft", "pencairan", "realisasi", "cancelled"]
                new_status = st.selectbox("Status Baru", status_options,
                    index=status_options.index(s["status"]) if s["status"] in status_options else 0)
                
                # Nomor voucher hanya muncul saat realisasi
                nomor_voucher = ""
                if new_status == "realisasi" or s["status"] == "realisasi":
                    nomor_voucher = st.text_input("Nomor Voucher", value=s.get("nomor_voucher") or "")

                if st.button("💾 Update Status", use_container_width=True):
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
                            elif old_status == "realisasi":
                                total = s.get("total_biaya") or 0
                                rollback_rkap(rkap_id, total)

                    st.success("✅ Status berhasil diupdate!")
                    st.rerun()

            with col_right:
                # Input realisasi hanya muncul saat status realisasi
                if s["status"] == "realisasi":
                    st.markdown("**Input Realisasi Biaya**")
                    total_transport = st.number_input("Biaya Transport (Rp)",
                        value=int(s.get("total_transport") or 0), step=50000)
                    total_hotel = st.number_input("Biaya Hotel (Rp)",
                        value=int(s.get("total_hotel") or 0), step=50000)

                    total_realisasi = (s.get("subtotal_uang_saku") or 0) + total_transport + total_hotel
                    st.markdown(f"**Total Realisasi: {format_rupiah(total_realisasi)}**")

                    if st.button("💾 Simpan Realisasi", use_container_width=True):
                        db.table("sppd").update({
                            "total_transport": total_transport,
                            "total_hotel":     total_hotel,
                            "total_biaya":     total_realisasi,
                        }).eq("id", s["id"]).execute()

                        rkap_id   = s.get("rkap_id")
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
                else:
                    st.info(f"ℹ️ Input realisasi tersedia saat status **REALISASI**.\nStatus sekarang: **{s['status'].upper()}**")

# ══════════════════════════════════════════════════════
# TAB 4: REKAP SPD
# ══════════════════════════════════════════════════════
with tab4:
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
        selected_spd_key = st.selectbox("Pilih SPD", list(spd_options.keys()))
        spd = spd_options[selected_spd_key]

        # Rekap per kategori
        st.markdown("#### Rekap Total Biaya per Kategori")
        col1, col2, col3 = st.columns(3)
        col1.metric("Direksi", format_rupiah(spd.get("total_direksi", 0)))
        col2.metric("Dewan Pengawas", format_rupiah(spd.get("total_dewas", 0)))
        col3.metric("Administrasi", format_rupiah(spd.get("total_administrasi", 0)))

        col4, col5, col6 = st.columns(3)
        col4.metric("Teknik", format_rupiah(spd.get("total_teknik", 0)))
        col5.metric("Bantuan", format_rupiah(spd.get("total_bantuan", 0)))
        col6.metric("🏆 Grand Total", format_rupiah(spd.get("grand_total", 0)))

        st.markdown("---")

        # Daftar SPPD dalam SPD ini
        st.markdown("#### Daftar SPPD dalam SPD ini")
        res_detail = db.table("sppd")\
            .select("*, pegawai!sppd_pegawai_id_fkey(nama, jabatan(nama))")\
            .eq("spd_id", spd["id"])\
            .execute()

        if res_detail.data:
            import pandas as pd
            df = pd.DataFrame([{
                "Nama": d["pegawai"]["nama"] if d.get("pegawai") else "-",
                "Jabatan": d["pegawai"]["jabatan"]["nama"] if d.get("pegawai") and d["pegawai"].get("jabatan") else "-",
                "Hari": d["total_hari"],
                "Uang Saku": format_rupiah(d.get("subtotal_uang_saku", 0)),
                "Transport": format_rupiah(d.get("total_transport", 0)),
                "Hotel": format_rupiah(d.get("total_hotel", 0)),
                "Total": format_rupiah(d.get("total_biaya", 0)),
                "Status": d["status"].upper(),
            } for d in res_detail.data])
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Tombol refresh rekap
            if st.button("🔄 Hitung Ulang Rekap"):
                update_rekap_spd(spd["id"])
                st.success("✅ Rekap berhasil dihitung ulang!")
                st.rerun()