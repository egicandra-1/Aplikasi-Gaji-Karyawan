import streamlit as st
import pandas as pd
import time
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- KAMUS HARI BAHASA INDONESIA ---
HARI_INDO = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
}

URUTAN_HARI = {"Senin": 1, "Selasa": 2, "Rabu": 3, "Kamis": 4, "Jumat": 5, "Sabtu": 6, "Minggu": 7}

st.set_page_config(page_title="Sistem Penggajian", layout="wide", page_icon="📝")

# ==========================================
# SUNTIKAN CSS & JAVASCRIPT: MATIKAN TOTAL SHORTCUT 'C'
# ==========================================
st.markdown("""
    <style>
    /* Menyembunyikan ikon rantai di semua judul */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
    }
    
    /* Animasi memudar otomatis KHUSUS untuk notifikasi menu lain */
    @keyframes fadeOutAlert {
        0% { opacity: 1; }
        80% { opacity: 1; }
        100% { opacity: 0; visibility: hidden; }
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stAlert"] {
        animation: none !important;
    }
    </style>
    
    <script>
    window.addEventListener('keydown', function(e) {
        if (e.key === 'c' || e.key === 'C') {
            e.stopImmediatePropagation();
        }
    }, true);
    </script>
""", unsafe_allow_html=True)

st.title("Aplikasi Rekap Gaji Karyawan")

# ==========================================
# 1. KONEKSI GOOGLE SHEETS
# ==========================================
@st.cache_resource
def init_connection_v3():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    except:
        dict_creds = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict_creds, scope)
    return gspread.authorize(creds)

@st.cache_resource
def get_all_worksheets():
    client = init_connection_v3()
    ss = client.open_by_url("https://docs.google.com/spreadsheets/d/1nSVOJTyA48REHwPvaWbvVXUupdh_GcrCHvBqbEA-xe8/edit")
    
    def get_or_create(name, cols):
        try:
            return ss.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            ws = ss.add_worksheet(title=name, rows="100", cols="20")
            ws.append_row(cols)
            return ws

    return {
        "gaji": get_or_create("Data_Gaji", ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"]),
        "kasbon": get_or_create("Data_Kasbon_Bonus", ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"]),
        "pengeluaran": get_or_create("Data_Pengeluaran_Lain", ["ID Lain", "Keterangan", "Nominal"]),
        "karyawan": get_or_create("Master_Karyawan", ["Nama Karyawan"]),
        "pekerjaan": get_or_create("Master_Pekerjaan", ["Jenis Pekerjaan", "Upah"])
    }

ws = get_all_worksheets()

# ==========================================
# 2. SISTEM MEMORI LOKAL
# ==========================================
def load_data_to_memory():
    data_gaji = ws["gaji"].get_all_records()
    df_gaji = pd.DataFrame(data_gaji) if data_gaji else pd.DataFrame(columns=["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
    if "Harga" in df_gaji.columns: df_gaji = df_gaji.rename(columns={"Harga": "Upah"})
    st.session_state.df_gaji = df_gaji
    
    data_kasbon = ws["kasbon"].get_all_records()
    st.session_state.df_kasbon = pd.DataFrame(data_kasbon) if data_kasbon else pd.DataFrame(columns=["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
    
    data_pengeluaran = ws["pengeluaran"].get_all_records()
    st.session_state.df_pengeluaran = pd.DataFrame(data_pengeluaran) if data_pengeluaran else pd.DataFrame(columns=["ID Lain", "Keterangan", "Nominal"])
    
    data_karyawan = ws["karyawan"].get_all_records()
    if not data_karyawan:
        df_kar = pd.DataFrame({"Nama Karyawan": ["Teh Eva", "Bi Nyai", "Radi", "Ula", "Sintia", "Mang Ade", "Mang Koko", "Yoga", "Samsul"]})
        ws["karyawan"].clear()
        ws["karyawan"].update([df_kar.columns.values.tolist()] + df_kar.values.tolist())
        st.session_state.df_karyawan = df_kar
    else:
        st.session_state.df_karyawan = pd.DataFrame(data_karyawan)
        
    data_pekerjaan = ws["pekerjaan"].get_all_records()
    if not data_pekerjaan:
        df_pek = pd.DataFrame({"Jenis Pekerjaan": ["Bungkus Patung", "Packing Styrofoam", "Bungkus Cat"], "Upah": [150, 400, 15]})
        ws["pekerjaan"].clear()
        ws["pekerjaan"].update([df_pek.columns.values.tolist()] + df_pek.values.tolist())
        st.session_state.df_pekerjaan = df_pek
    else:
        df_pek = pd.DataFrame(data_pekerjaan)
        if "Harga Per Pcs" in df_pek.columns:
            df_pek = df_pek.rename(columns={"Harga Per Pcs": "Upah"})
        elif len(df_pek.columns) > 1 and df_pek.columns[1] != "Upah":
            df_pek = df_pek.rename(columns={df_pek.columns[1]: "Upah"})
        st.session_state.df_pekerjaan = df_pek

if "data_loaded" not in st.session_state:
    with st.spinner("Memuat Database dari Server... (Hanya 1x)"):
        load_data_to_memory()
        st.session_state.data_loaded = True

daftar_karyawan = st.session_state.df_karyawan["Nama Karyawan"].dropna().tolist() if not st.session_state.df_karyawan.empty else []
daftar_pekerjaan = st.session_state.df_pekerjaan["Jenis Pekerjaan"].dropna().tolist() if not st.session_state.df_pekerjaan.empty else []

df_pek_temp = st.session_state.df_pekerjaan
col_upah_key = "Upah" if "Upah" in df_pek_temp.columns else (df_pek_temp.columns[1] if len(df_pek_temp.columns) > 1 else "Upah")
tarif_pekerjaan = dict(zip(df_pek_temp["Jenis Pekerjaan"], pd.to_numeric(df_pek_temp[col_upah_key], errors='coerce').fillna(0))) if not df_pek_temp.empty else {}

menu1, menu2, menu3, menu4, menu5, menu6 = st.tabs([
    "📝 1. Input Harian", 
    "📂 2. Database Pekerjaan", 
    "💸 3. Penambahan & Pengurangan", 
    "🖨️ 4. Cetak Slip Gaji", 
    "📊 5. Laporan Resume Kas", 
    "⚙️ 6. Pengaturan"
])

# ==========================================
# MENU 1: INPUT HARIAN
# ==========================================
with menu1:
    st.header("Input Pekerjaan Harian")

    today_date = datetime.today().date()
    if "last_date_harian" not in st.session_state or st.session_state.last_date_harian > today_date:
        st.session_state.last_date_harian = today_date
        
    if "last_karyawan_harian" not in st.session_state:
        st.session_state.last_karyawan_harian = daftar_karyawan[0] if daftar_karyawan else ""
    
    if len(daftar_karyawan) == 0 or len(daftar_pekerjaan) == 0:
        st.warning("⚠️ Data Karyawan atau Pekerjaan kosong. Silakan isi terlebih dahulu di Menu 6.")
    else:
        with st.form("form_input_harian", clear_on_submit=True):
            col_tgl, col_nama = st.columns(2)
            with col_tgl:
                tanggal = st.date_input("Pilih Tanggal", st.session_state.last_date_harian, max_value=datetime.today(), format="DD/MM/YYYY")
                nama_hari = HARI_INDO[tanggal.strftime("%A")]
                
            with col_nama:
                idx_kar = daftar_karyawan.index(st.session_state.last_karyawan_harian) if st.session_state.last_karyawan_harian in daftar_karyawan else 0
                nama = st.selectbox("Pilih Karyawan", daftar_karyawan, index=idx_kar)

            st.markdown("---")
            st.markdown("### ⚡ Panel Input Harian")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                opsi_kerja = ["-"] + daftar_pekerjaan
                pekerjaan = st.selectbox("Pilih Pekerjaan", opsi_kerja)
            with col2:
                jumlah_str = st.text_input("Jumlah (Pcs)", placeholder="Ketik jumlah pcs (contoh: 500)")
                
            notif_area_1 = st.empty()
            if "notif_1" in st.session_state:
                if st.session_state.notif_1_type == "success":
                    notif_area_1.success(st.session_state.notif_1)
                else:
                    notif_area_1.error(st.session_state.notif_1)
                del st.session_state.notif_1
                del st.session_state.notif_1_type
                
            submitted_input = st.form_submit_button("💾 Simpan Data Pekerjaan", type="primary", use_container_width=True)
            
            if submitted_input:
                jumlah = int(jumlah_str.strip()) if jumlah_str.strip().isdigit() else 0
                    
                if pekerjaan != "-" and jumlah > 0:
                    upah = tarif_pekerjaan.get(pekerjaan, 0)
                    total = jumlah * upah
                    try:
                        id_data = f"ID-{int(time.time())}"
                        tgl_str = tanggal.strftime("%Y-%m-%d")
                        
                        baris_baru = pd.DataFrame([{"ID Data": id_data, "Hari": nama_hari, "Tanggal": tgl_str, "Nama": nama, "Pekerjaan": pekerjaan, "Upah": upah, "Jumlah": jumlah, "Total": total}])
                        st.session_state.df_gaji = pd.concat([st.session_state.df_gaji, baris_baru], ignore_index=True)
                        ws["gaji"].append_row([id_data, nama_hari, tgl_str, nama, pekerjaan, upah, jumlah, total])
                        
                        st.session_state.last_date_harian = tanggal
                        st.session_state.last_karyawan_harian = nama
                        
                        jml_fmt = f"{jumlah:,.0f}".replace(",", ".")
                        st.session_state.notif_1 = f"✅ Tersimpan Kilat! {jml_fmt} {pekerjaan} untuk {nama}."
                        st.session_state.notif_1_type = "success"
                        st.rerun() 
                    except Exception as e:
                        st.session_state.notif_1 = f"⚠️ Gagal simpan: {e}"
                        st.session_state.notif_1_type = "error"
                        st.rerun()
                else:
                    st.session_state.notif_1 = "⚠️ Gagal! Mohon pilih pekerjaan dan ketik jumlah yang valid."
                    st.session_state.notif_1_type = "error"
                    st.rerun()

# ==========================================
# MENU 2: DATABASE & EDIT PEKERJAAN
# ==========================================
with menu2:
    st.header("Database Riwayat Pekerjaan")
    st.caption("💡 Pilih rentang tanggal pada kalender di bawah untuk melihat data periode tertentu. Cukup edit langsung di tabel lalu tekan **Enter**.")
    
    df_gaji = st.session_state.df_gaji
    
    if len(df_gaji) > 0:
        df_gaji['Date_Obj'] = pd.to_datetime(df_gaji['Tanggal']).dt.date
        max_tgl = df_gaji['Date_Obj'].max()
        default_start = df_gaji['Date_Obj'].min()
        
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            rentang_tanggal = st.date_input(
                "Pilih Periode Tanggal",
                value=(default_start, max_tgl),
                max_value=datetime.today().date(),
                format="DD/MM/YYYY"
            )
        with col_f2:
            filter_nama = st.selectbox("🔍 Filter Karyawan:", ["Semua Karyawan"] + daftar_karyawan, key="filter_db_kerja")
            
        if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2:
            tgl_mulai, tgl_selesai = rentang_tanggal
        else:
            tgl_mulai = tgl_selesai = rentang_tanggal[0] if isinstance(rentang_tanggal, tuple) else rentang_tanggal

        df_tampil = df_gaji[(df_gaji['Date_Obj'] >= tgl_mulai) & (df_gaji['Date_Obj'] <= tgl_selesai)].copy()
        if filter_nama != "Semua Karyawan":
            df_tampil = df_tampil[df_tampil['Nama'] == filter_nama]
            
        if len(df_tampil) > 0:
            df_tampil['Urutan_Hari'] = df_tampil['Hari'].map(URUTAN_HARI)
            df_tampil = df_tampil.sort_values(by=["Tanggal", "Urutan_Hari"]).drop(columns=["Urutan_Hari", "Date_Obj"])
            daftar_tanggal = df_tampil[['Tanggal', 'Hari']].drop_duplicates().values
            
            for tgl, hari in daftar_tanggal:
                with st.expander(f"📅 Hari **{hari}**, Tanggal **{tgl}**", expanded=True):
                    df_harian = df_tampil[(df_tampil['Tanggal'] == tgl) & (df_tampil['Hari'] == hari)].copy()
                    
                    df_harian_view = df_harian[['ID Data', 'Nama', 'Pekerjaan', 'Upah', 'Jumlah', 'Total']].copy().reset_index(drop=True)
                    
                    df_harian_view['Upah'] = pd.to_numeric(df_harian_view['Upah'], errors='coerce').fillna(0)
                    df_harian_view['Jumlah'] = pd.to_numeric(df_harian_view['Jumlah'], errors='coerce').fillna(0)
                    df_harian_view['Total'] = pd.to_numeric(df_harian_view['Total'], errors='coerce').fillna(0)
                    
                    notif_key = f"notif_2_{tgl}_{hari}"
                    notif_area_2 = st.empty()
                    if notif_key in st.session_state:
                        notif_area_2.success(st.session_state[notif_key])
                        del st.session_state[notif_key]
                    
                    def save_callback(t=tgl, h=hari, orig_ids=df_harian['ID Data'].tolist()):
                        edited_df = st.session_state.get(f"editor_{t}_{h}")
                        
                        if edited_df is None or not isinstance(edited_df, pd.DataFrame) or edited_df.empty:
                            df_processed = pd.DataFrame(columns=['ID Data', 'Hari', 'Tanggal', 'Nama', 'Pekerjaan', 'Upah', 'Jumlah', 'Total'])
                        else:
                            col_id = edited_df.columns[0] if len(edited_df.columns) > 0 else None
                            col_nama = edited_df.columns[1] if len(edited_df.columns) > 1 else None
                            col_pek = edited_df.columns[2] if len(edited_df.columns) > 2 else None
                            col_upah = edited_df.columns[3] if len(edited_df.columns) > 3 else None
                            col_jml = edited_df.columns[4] if len(edited_df.columns) > 4 else None
                            
                            ids = edited_df[col_id].apply(lambda x: f"ID-{int(time.time())}" if pd.isna(x) or str(x).strip() == "" else str(x)) if col_id else [f"ID-{int(time.time())}-{i}" for i in range(len(edited_df))]
                            namas = edited_df[col_nama] if col_nama else ""
                            pekerjaans = edited_df[col_pek] if col_pek else ""
                            upahs = pd.to_numeric(edited_df[col_upah], errors='coerce').fillna(0) if col_upah else 0
                            jumlahs = pd.to_numeric(edited_df[col_jml], errors='coerce').fillna(0) if col_jml else 0
                            totals = jumlahs * upahs
                            
                            df_processed = pd.DataFrame({
                                'ID Data': ids,
                                'Hari': h,
                                'Tanggal': t,
                                'Nama': namas,
                                'Pekerjaan': pekerjaans,
                                'Upah': upahs,
                                'Jumlah': jumlahs,
                                'Total': totals
                            })
                        
                        df_sisa = st.session_state.df_gaji[~st.session_state.df_gaji['ID Data'].isin(orig_ids)]
                        df_final = pd.concat([df_sisa, df_processed]).sort_values(by="Tanggal").reset_index(drop=True)
                        if 'Date_Obj' in df_final.columns: df_final = df_final.drop(columns=['Date_Obj'])
                        
                        st.session_state.df_gaji = df_final
                        ws["gaji"].clear()
                        ws["gaji"].update([df_final.columns.values.tolist()] + df_final.fillna("").values.tolist())
                        st.session_state[f"notif_2_{t}_{h}"] = "✅ Otomatis Tersimpan!"

                    st.data_editor(
                        df_harian_view, 
                        num_rows="dynamic", 
                        use_container_width=True, 
                        column_config={
                            "ID Data": None,
                            "Upah": st.column_config.NumberColumn("Upah", format="Rp %,d"),
                            "Jumlah": st.column_config.NumberColumn("Jumlah", format="%,d"),
                            "Total": st.column_config.NumberColumn("Total", format="Rp %,d")
                        }, 
                        hide_index=True, 
                        key=f"editor_{tgl}_{hari}",
                        on_change=save_callback
                    )
        else:
            st.info(f"Tidak ada riwayat pekerjaan pada rentang tanggal tersebut.")
    else:
        st.info("Belum ada data pekerjaan yang tersimpan.")

# ==========================================
# MENU 3: PENAMBAHAN & PENGURANGAN
# ==========================================
with menu3:
    st.header("Pencatatan Penambahan & Pengurangan")

    today_date_kb = datetime.today().date()
    if "last_date_kb" not in st.session_state or st.session_state.last_date_kb > today_date_kb:
        st.session_state.last_date_kb = today_date_kb
        
    if "last_karyawan_kb" not in st.session_state:
        st.session_state.last_karyawan_kb = daftar_karyawan[0] if daftar_karyawan else ""

    if len(daftar_karyawan) > 0:
        with st.form("form_kasbon", clear_on_submit=True):
            col_kb1, col_kb2, col_kb3 = st.columns(3)
            with col_kb1:
                tgl_kb = st.date_input("Tanggal Transaksi", st.session_state.last_date_kb, max_value=datetime.today(), format="DD/MM/YYYY")
            with col_kb2:
                idx_kb = daftar_karyawan.index(st.session_state.last_karyawan_kb) if st.session_state.last_karyawan_kb in daftar_karyawan else 0
                nama_kb = st.selectbox("Pilih Karyawan", daftar_karyawan, index=idx_kb)
            with col_kb3:
                tipe_kb = st.selectbox("Jenis Transaksi", ["Penambahan", "Pengurangan"])
                
            col_kb4, col_kb5 = st.columns([2, 1])
            with col_kb4:
                ket_kb = st.text_input("Keterangan")
            with col_kb5:
                nominal_str = st.text_input("Nominal (Rp)", placeholder="Ketik nominal (contoh: 50000)")
                
            notif_area_3 = st.empty()
            if "notif_3" in st.session_state:
                if st.session_state.notif_3_type == "success":
                    notif_area_3.success(st.session_state.notif_3)
                else:
                    notif_area_3.error(st.session_state.notif_3)
                del st.session_state.notif_3
                del st.session_state.notif_3_type
                
            if st.form_submit_button("💾 Simpan Data", type="primary", use_container_width=True):
                nominal_kb = int(nominal_str.strip()) if nominal_str.strip().isdigit() else 0
                    
                if nominal_kb > 0 and ket_kb.strip() != "":
                    try:
                        id_kb = f"KB-{int(time.time())}"
                        tgl_str = tgl_kb.strftime("%Y-%m-%d")
                        
                        baris_kb = pd.DataFrame([{"ID Kasbon": id_kb, "Tanggal": tgl_str, "Nama": nama_kb, "Tipe": tipe_kb, "Keterangan": ket_kb, "Nominal": nominal_kb}])
                        st.session_state.df_kasbon = pd.concat([st.session_state.df_kasbon, baris_kb], ignore_index=True)
                        ws["kasbon"].append_row([id_kb, tgl_str, nama_kb, tipe_kb, ket_kb, nominal_kb])
                        
                        st.session_state.last_date_kb = tgl_kb
                        st.session_state.last_karyawan_kb = nama_kb
                        
                        st.session_state.notif_3 = "✅ Berhasil menyimpan data!"
                        st.session_state.notif_3_type = "success"
                        st.rerun()
                    except Exception as e:
                        st.session_state.notif_3 = f"⚠️ Gagal: {e}"
                        st.session_state.notif_3_type = "error"
                        st.rerun()
                else:
                    st.session_state.notif_3 = "⚠️ Mohon isi keterangan dan nominal dengan benar."
                    st.session_state.notif_3_type = "error"
                    st.rerun()

# ==========================================
# MENU 4: CETAK SLIP GAJI (MENGGUNAKAN LOGIKA GAMBAR CONTOH 4K YANG BAGUS)
# ==========================================
with menu4:
    st.header("Cetak & Unduh Slip Gaji")
    df_gaji = st.session_state.df_gaji.copy()
    df_kasbon = st.session_state.df_kasbon.copy()
    
    if len(df_gaji) > 0 and len(daftar_karyawan) > 0:
        rentang_slip = st.date_input(
            "Pilih Periode Tanggal Slip Gaji",
            value=(datetime.today().date(), datetime.today().date()),
            max_value=datetime.today().date(),
            format="DD/MM/YYYY",
            key="rentang_slip_gaji"
        )
        
        if isinstance(rentang_slip, tuple) and len(rentang_slip) == 2:
            tgl_mulai_slip, tgl_selesai_slip = rentang_slip
        else:
            tgl_mulai_slip = tgl_selesai_slip = rentang_slip[0] if isinstance(rentang_slip, tuple) else rentang_slip
            
        nama_slip_pilihan = st.selectbox("Pilih Nama Karyawan", ["Semua Karyawan"] + daftar_karyawan, key="slip_nama")
        
        if st.button("🖨️ Buat Slip Gaji (4K Ultra HD)", type="primary"):
            df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal']).dt.date
            target_karyawan = daftar_karyawan if nama_slip_pilihan == "Semua Karyawan" else [nama_slip_pilihan]
            
            berhasil_cetak_count = 0
            
            for nama_slip in target_karyawan:
                df_filter_gaji = df_gaji[(df_gaji['Nama'] == nama_slip) & (df_gaji['Tanggal'] >= tgl_mulai_slip) & (df_gaji['Tanggal'] <= tgl_selesai_slip)]
                df_filter_kb = df_kasbon[(df_kasbon['Nama'] == nama_slip) & (pd.to_datetime(df_kasbon['Tanggal']).dt.date >= tgl_mulai_slip) & (pd.to_datetime(df_kasbon['Tanggal']).dt.date <= tgl_selesai_slip)] if len(df_kasbon) > 0 else pd.DataFrame()
                
                if len(df_filter_gaji) > 0 or len(df_filter_kb) > 0:
                    berhasil_cetak_count += 1
                    baris_gambar_info = []
                    
                    baris_gambar_info.append(("       SLIP GAJI", True))
                    baris_gambar_info.append(("================================", False))
                    baris_gambar_info.append((f"Nama    : {nama_slip}", True))
                    baris_gambar_info.append((f"Periode : {tgl_mulai_slip.strftime('%d/%m/%Y')} - {tgl_selesai_slip.strftime('%d/%m/%Y')}", True))
                    baris_gambar_info.append(("================================", False))
                    baris_gambar_info.append(("", False))
                    
                    total_pendapatan_upah = 0
                    if len(df_filter_gaji) > 0:
                        grup_tanggal = df_filter_gaji.groupby('Tanggal')
                        for tgl, data_harian in grup_tanggal:
                            hari_slip = HARI_INDO.get(tgl.strftime("%A"), "")
                            tgl_str = f"Hari/Tgl: {hari_slip}, {tgl.strftime('%d/%m/%Y')}"
                            baris_gambar_info.append((tgl_str, True))
                            
                            subtotal = 0
                            for _, row in data_harian.iterrows():
                                jml_format = f"{row['Jumlah']:,.0f}".replace(",", ".")
                                upah_format = f"{row['Upah']:,.0f}".replace(",", ".")
                                total_format = f"{row['Total']:,.0f}".replace(",", ".")
                                
                                baris_gambar_info.append((f"- {row['Pekerjaan']}", False))
                                baris_gambar_info.append((f"  {jml_format} pcs x Rp{upah_format} = Rp{total_format}", False))
                                subtotal += row['Total']
                            
                            subtotal_format = f"{subtotal:,.0f}".replace(",", ".")
                            baris_gambar_info.append((f"Sub-total: Rp{subtotal_format}", False))
                            baris_gambar_info.append(("", False))
                            total_pendapatan_upah += subtotal
                    
                    total_tambah = 0
                    total_kurang = 0
                    
                    if len(df_filter_kb) > 0:
                        baris_gambar_info.append(("--- CATATAN TAMBAHAN ---", True))
                        for _, row_kb in df_filter_kb.iterrows():
                            nominal_fmt = f"Rp {row_kb['Nominal']:,.0f}".replace(",", ".")
                            if row_kb['Tipe'] == "Penambahan":
                                baris_gambar_info.append((f"+ {row_kb['Keterangan']}", False))
                                baris_gambar_info.append((f"  ({nominal_fmt})", False))
                                total_tambah += row_kb['Nominal']
                            else:
                                baris_gambar_info.append((f"- {row_kb['Keterangan']}", False))
                                baris_gambar_info.append((f"  ({nominal_fmt})", False))
                                total_kurang += row_kb['Nominal']
                        baris_gambar_info.append(("", False))
                    
                    total_gaji_bersih = total_pendapatan_upah + total_tambah - total_kurang
                    total_semua_format = f"{total_gaji_bersih:,.0f}".replace(",", ".")
                    
                    baris_gambar_info.append(("================================", False))
                    total_str = f"TOTAL GAJI DITERIMA: Rp {total_semua_format}"
                    baris_gambar_info.append((total_str, True))
                    baris_gambar_info.append(("================================", False))

                    scale = 4  # SKALA 4K
                    base_width = 420
                    base_line_height = 20
                    base_margin = 20
                    
                    img_w = base_width * scale
                    img_h = ((len(baris_gambar_info) * base_line_height) + (base_margin * 2)) * scale
                    
                    img = Image.new('RGB', (img_w, img_h), color=(255, 255, 255))
                    draw = ImageDraw.Draw(img)
                    
                    try:
                        font_size = 14 * scale
                        font_regular = ImageFont.truetype("cour.ttf", font_size) 
                        font_bold = ImageFont.truetype("courbd.ttf", font_size) 
                    except:
                        font_regular = ImageFont.load_default()
                        font_bold = font_regular
                        
                    y_pos = base_margin * scale
                    line_spacing = base_line_height * scale
                    
                    for text_line, is_bold in baris_gambar_info:
                        pilih_font = font_bold if is_bold else font_regular
                        draw.text((base_margin * scale, y_pos), text_line, font=pilih_font, fill=(0, 0, 0))
                        y_pos += line_spacing
                        
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    byte_im = buf.getvalue()
                    
                    st.markdown("---")
                    st.subheader(f"📄 Slip Gaji: {nama_slip}")
                    st.image(byte_im, width=400)
                    
                    caption_teks = f"Slip Gaji {nama_slip}\nPeriode: {tgl_mulai_slip.strftime('%d/%m/%Y')} - {tgl_selesai_slip.strftime('%d/%m/%Y')}\nTotal Diterima: Rp {total_semua_format}"
                    st.text_area("📋 Salin Caption Singkat:", value=caption_teks, height=80, key=f"caption_{nama_slip}_{time.time()}")
                    
                    st.download_button(
                        label=f"📥 Unduh Foto Slip - {nama_slip} (Format 4K JPG)",
                        data=byte_im,
                        file_name=f"Slip_Gaji_4K_{nama_slip}_{tgl_selesai_slip.strftime('%d%m%Y')}.jpg",
                        mime="image/jpeg",
                        key=f"dl_slip_{nama_slip}_{time.time()}"
                    )
            
            if berhasil_cetak_count == 0:
                st.warning("⚠️ Tidak ada data pekerjaan atau catatan untuk karyawan pada periode tersebut.")
    else:
        st.info("Belum ada data yang bisa dicetak.")

# ==========================================
# MENU 5: LAPORAN RESUME KAS (MENGGUNAKAN LOGIKA GAMBAR CONTOH 4K YANG BAGUS)
# ==========================================
with menu5:
    st.header("📊 Laporan Resume Kas Mingguan/Periode")
    st.caption("Masukkan periode tanggal, catat pengeluaran lain-lain, dan masukkan total uang cash yang ditarik untuk melihat sisa uang.")
    
    df_gaji = st.session_state.df_gaji.copy()
    df_kasbon = st.session_state.df_kasbon.copy()
    df_lain_all = st.session_state.df_pengeluaran.copy()
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        tgl_mulai_res = st.date_input("Dari Tanggal", datetime.today(), format="DD/MM/YYYY", key="res_mulai")
    with col_r2:
        tgl_selesai_res = st.date_input("Sampai Tanggal", datetime.today(), format="DD/MM/YYYY", key="res_selesai")
        
    tarik_uang = st.number_input("💵 Total Penarikan Uang Cash (Rp)", min_value=0, step=100000, value=None, placeholder="Ketik nominal tarikan uang...")
    
    if tarik_uang is not None and tarik_uang > 0:
        tarik_format = f"{tarik_uang:,.0f}".replace(",", ".")
        st.caption(f"✨ Anda memasukan: **Rp {tarik_format}**")
        
    st.markdown("---")
    st.subheader("🛒 Pencatatan Pengeluaran Lain-Lain (Tak Terduga)")
    st.caption("Gunakan form di bawah ini untuk menambahkan pengeluaran lain dengan lancar.")
    
    with st.form("form_pengeluaran_lain", clear_on_submit=True):
        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            ket_lain = st.text_input("Keterangan Pengeluaran (Contoh: Admin, Roko, Belanja)")
        with col_l2:
            nominal_lain = st.number_input("Nominal (Rp)", min_value=0, step=5000, value=None, placeholder="Ketik nominal...")
            
        submitted_lain = st.form_submit_button("➕ Tambah Pengeluaran Lain", type="primary", use_container_width=True)
        if submitted_lain:
            if nominal_lain is not None and nominal_lain > 0 and ket_lain.strip() != "":
                baris_baru_lain = pd.DataFrame([{
                    "ID Lain": f"LAIN-{int(time.time())}",
                    "Keterangan": ket_lain,
                    "Nominal": nominal_lain
                }])
                df_lain_updated = pd.concat([df_lain_all, baris_baru_lain], ignore_index=True)
                st.session_state.df_pengeluaran = df_lain_updated
                ws["pengeluaran"].clear()
                ws["pengeluaran"].update([df_lain_updated.columns.values.tolist()] + df_lain_updated.fillna("").values.tolist())
                st.success(f"Berhasil menambahkan '{ket_lain}' sebesar Rp {nominal_lain:,.0f}!".replace(",", "."))
                st.rerun()
            else:
                st.warning("⚠️ Mohon isi keterangan dan nominal pengeluaran dengan benar.")

    if len(df_lain_all) > 0:
        st.write("Daftar Pengeluaran Lainnya (Klik dua kali atau hapus baris jika ingin mengubah):")
        if "Keterangan" not in df_lain_all.columns:
            if "Jenis" in df_lain_all.columns:
                df_lain_all = df_lain_all.rename(columns={"Jenis": "Keterangan"})
            else:
                df_lain_all["Keterangan"] = ""
        if "Nominal" not in df_lain_all.columns:
            df_lain_all["Nominal"] = 0
        if "ID Lain" not in df_lain_all.columns:
            df_lain_all["ID Lain"] = [f"LAIN-{i}" for i in range(len(df_lain_all))]
            
        df_tampil_lain = df_lain_all[["ID Lain", "Keterangan", "Nominal"]].copy()
        df_tampil_lain['Nominal'] = df_tampil_lain['Nominal'].apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
        
        df_lain_edit = st.data_editor(df_tampil_lain, num_rows="dynamic", use_container_width=True, key="edit_tabel_lain_bersih")
        
        if not df_tampil_lain.equals(df_lain_edit):
            df_lain_edit['Nominal'] = df_lain_edit['Nominal'].astype(str).str.replace("Rp", "").str.replace(".", "").str.strip().astype(float)
            st.session_state.df_pengeluaran = df_lain_edit
            ws["pengeluaran"].clear()
            ws["pengeluaran"].update([df_lain_edit.columns.values.tolist()] + df_lain_edit.fillna("").values.tolist())
            st.toast("Data pengeluaran lain diperbarui! 💾", icon="✅")
            st.rerun()
            
    st.markdown("---")
    if st.button("🖼️ Generate Gambar Resume", type="primary"):
        if tarik_uang is None:
            tarik_uang = 0
            
        df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal']).dt.date
        df_f_gaji = df_gaji[(df_gaji['Tanggal'] >= tgl_mulai_res) & (df_gaji['Tanggal'] <= tgl_selesai_res)]
        
        if len(df_kasbon) > 0:
            df_kasbon['Tanggal'] = pd.to_datetime(df_kasbon['Tanggal']).dt.date
            df_f_kb = df_kasbon[(df_kasbon['Tanggal'] >= tgl_mulai_res) & (df_kasbon['Tanggal'] <= tgl_selesai_res)]
        else:
            df_f_kb = pd.DataFrame()
            
        rekap_gaji = {}
        for k in daftar_karyawan:
            rekap_gaji[k] = 0
            
        if len(df_f_gaji) > 0:
            grup_nama = df_f_gaji.groupby('Nama')
            for nama, df_n in grup_nama:
                rekap_gaji[nama] = rekap_gaji.get(nama, 0) + df_n['Total'].sum()
                
        if len(df_f_kb) > 0:
            for _, row_kb in df_f_kb.iterrows():
                nama = row_kb['Nama']
                if nama in rekap_gaji:
                    if row_kb['Tipe'] == "Penambahan":
                        rekap_gaji[nama] += row_kb['Nominal']
                    else:
                        rekap_gaji[nama] -= row_kb['Nominal']
                        
        total_gaji_semua = sum(rekap_gaji.values())
        total_pengeluaran_lain = df_lain_all['Nominal'].sum() if len(df_lain_all) > 0 else 0
        total_pengeluaran_keseluruhan = total_gaji_semua + total_pengeluaran_lain
        sisa_uang = tarik_uang - total_pengeluaran_keseluruhan
        
        scale = 4  # SKALA 4K
        w = 460 * scale
        
        base_h = 350
        row_h = 24
        h = (base_h + (len(daftar_karyawan) * row_h) + (len(df_lain_all) * row_h)) * scale
        
        img = Image.new('RGB', (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        try:
            f_title = ImageFont.truetype("courbd.ttf", 15 * scale)
            f_bold = ImageFont.truetype("courbd.ttf", 11 * scale)
            f_reg = ImageFont.truetype("cour.ttf", 11 * scale)
        except:
            f_title = ImageFont.load_default()
            f_bold = f_title
            f_reg = f_title
            
        margin = 20 * scale
        y = margin
        
        draw.text((margin, y), "LAPORAN RESUME KAS & GAJI", fill=(0, 0, 0), font=f_title)
        y += 22 * scale
        periode_str = f"Periode: {tgl_mulai_res.strftime('%d/%m/%Y')} s/d {tgl_selesai_res.strftime('%d/%m/%Y')}"
        draw.text((margin, y), periode_str, fill=(80, 80, 80), font=f_bold)
        y += 25 * scale
        
        draw.line([(margin, y), (w - margin, y)], fill=(0, 0, 0), width=2 * scale)
        y += 15 * scale
        
        draw.text((margin, y), "A. RINCIAN GAJI KARYAWAN", fill=(0, 0, 0), font=f_bold)
        y += 20 * scale
        
        table_width = w - (margin * 2)
        col_nama_w = int(table_width * 0.6)
        
        draw.rectangle([margin, y, margin + table_width, y + 22 * scale], fill=(230, 230, 230), outline=(0, 0, 0))
        draw.text((margin + 8 * scale, y + 4 * scale), "NAMA KARYAWAN", fill=(0, 0, 0), font=f_bold)
        draw.text((margin + col_nama_w + 8 * scale, y + 4 * scale), "JUMLAH (Rp)", fill=(0, 0, 0), font=f_bold)
        y += 22 * scale
        
        for k in daftar_karyawan:
            val = rekap_gaji.get(k, 0)
            val_fmt = f"{val:,.0f}".replace(",", ".")
            draw.rectangle([margin, y, margin + table_width, y + 20 * scale], outline=(0, 0, 0))
            draw.text((margin + 8 * scale, y + 3 * scale), k, fill=(0, 0, 0), font=f_reg)
            draw.text((margin + col_nama_w + 8 * scale, y + 3 * scale), val_fmt, fill=(0, 0, 0), font=f_reg)
            y += 20 * scale
            
        draw.rectangle([margin, y, margin + table_width, y + 22 * scale], fill=(240, 240, 240), outline=(0, 0, 0))
        draw.text((margin + 8 * scale, y + 4 * scale), "TOTAL GAJI KARYAWAN", fill=(0, 0, 0), font=f_bold)
        tot_gaji_fmt = f"{total_gaji_semua:,.0f}".replace(",", ".")
        draw.text((margin + col_nama_w + 8 * scale, y + 4 * scale), tot_gaji_fmt, fill=(0, 0, 0), font=f_bold)
        y += 30 * scale
        
        draw.text((margin, y), "B. PENGELUARAN LAIN-LAIN", fill=(0, 0, 0), font=f_bold)
        y += 20 * scale
        
        draw.rectangle([margin, y, margin + table_width, y + 22 * scale], fill=(230, 230, 230), outline=(0, 0, 0))
        draw.text((margin + 8 * scale, y + 4 * scale), "KETERANGAN", fill=(0, 0, 0), font=f_bold)
        draw.text((margin + col_nama_w + 8 * scale, y + 4 * scale), "JUMLAH (Rp)", fill=(0, 0, 0), font=f_bold)
        y += 22 * scale
        
        if len(df_lain_all) > 0:
            for _, row_l in df_lain_all.iterrows():
                ket = str(row_l['Keterangan'])
                nom = float(row_l['Nominal']) if pd.notnull(row_l['Nominal']) else 0
                nom_fmt = f"{nom:,.0f}".replace(",", ".")
                draw.rectangle([margin, y, margin + table_width, y + 20 * scale], outline=(0, 0, 0))
                draw.text((margin + 8 * scale, y + 3 * scale), ket, fill=(0, 0, 0), font=f_reg)
                draw.text((margin + col_nama_w + 8 * scale, y + 3 * scale), nom_fmt, fill=(0, 0, 0), font=f_reg)
                y += 20 * scale
        else:
            draw.rectangle([margin, y, margin + table_width, y + 20 * scale], outline=(0, 0, 0))
            draw.text((margin + 8 * scale, y + 3 * scale), "(Tidak ada pengeluaran lain)", fill=(120, 120, 120), font=f_reg)
            draw.text((margin + col_nama_w + 8 * scale, y + 3 * scale), "0", fill=(120, 120, 120), font=f_reg)
            y += 20 * scale
            
        draw.rectangle([margin, y, margin + table_width, y + 22 * scale], fill=(240, 240, 240), outline=(0, 0, 0))
        draw.text((margin + 8 * scale, y + 4 * scale), "TOTAL PENGELUARAN LAIN", fill=(0, 0, 0), font=f_bold)
        tot_lain_fmt = f"{total_pengeluaran_lain:,.0f}".replace(",", ".")
        draw.text((margin + col_nama_w + 8 * scale, y + 4 * scale), tot_lain_fmt, fill=(0, 0, 0), font=f_bold)
        y += 30 * scale
        
        draw.text((margin, y), "C. RINGKASAN KAS", fill=(0, 0, 0), font=f_bold)
        y += 20 * scale
        
        ringkasan_data = [
            ("Total Penarikan Uang Cash", f"Rp {tarik_uang:,.0f}".replace(",", ".")),
            ("Total Pengeluaran Keseluruhan", f"Rp {total_pengeluaran_keseluruhan:,.0f}".replace(",", ".")),
            ("SISA SALDO KAS", f"Rp {sisa_uang:,.0f}".replace(",", "."))
        ]
        
        for idx_r, (lbl, val_r) in enumerate(ringkasan_data):
            is_last = (idx_r == len(ringkasan_data) - 1)
            bg_col = (210, 230, 250) if is_last else (255, 255, 255)
            draw.rectangle([margin, y, margin + table_width, y + 24 * scale], fill=bg_col, outline=(0, 0, 0))
            draw.text((margin + 8 * scale, y + 5 * scale), lbl, fill=(0, 0, 0), font=f_bold)
            draw.text((margin + col_nama_w - 20 * scale, y + 5 * scale), val_r, fill=(0, 0, 0), font=f_bold)
            y += 24 * scale
            
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        byte_resume = buf.getvalue()
        
        st.markdown("---")
        st.subheader("👁️ Ringkasan Akhir")
        st.image(byte_resume, width=460)
        
        st.download_button(
            label="📥 Unduh Resume (Format 4K JPG)",
            data=byte_resume,
            file_name=f"Resume_Kas_4K_{tgl_mulai_res.strftime('%d%m%Y')}.jpg",
            mime="image/jpeg",
            use_container_width=True
        )

# ==========================================
# MENU 6: PENGATURAN KARYAWAN & PEKERJAAN
# ==========================================
with menu6:
    st.header("Pengaturan Master Data")
    st.caption("💡 Tips: Tambahkan nama/pekerjaan baru di baris paling bawah. Data **TERSAVE OTOMATIS** saat Anda menekan Enter atau klik di luar tabel.")
    col_karyawan, col_pekerjaan = st.columns(2)
    
    with col_karyawan:
        st.subheader("👥 Daftar Nama Karyawan")
        df_karyawan_baru = st.data_editor(df_karyawan, num_rows="dynamic", key="edit_kary")
        if not df_karyawan.equals(df_karyawan_baru):
            df_karyawan_baru.to_csv(FILE_KARYAWAN, index=False)
            st.toast("Daftar Karyawan tersimpan otomatis! 💾", icon="✅")

    with col_pekerjaan:
        st.subheader("🛠️ Daftar & Harga Pekerjaan")
        df_pekerjaan_baru = st.data_editor(df_pekerjaan, num_rows="dynamic", key="edit_pek")
        if not df_pekerjaan.equals(df_pekerjaan_baru):
            df_pekerjaan_baru.to_csv(FILE_PEKERJAAN, index=False)
            st.toast("Daftar Pekerjaan tersimpan otomatis! 💾", icon="✅")
