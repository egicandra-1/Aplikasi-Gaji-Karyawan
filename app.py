import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta, date, timezone
from PIL import Image, ImageDraw, ImageFont
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
import streamlit.components.v1 as components

# --- KAMUS HARI & BULAN BAHASA INDONESIA ---
HARI_INDO = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
}

BULAN_INDO = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

URUTAN_HARI = {"Senin": 1, "Selasa": 2, "Rabu": 3, "Kamis": 4, "Jumat": 5, "Sabtu": 6, "Minggu": 7}

st.set_page_config(page_title="Sistem Perhitungan Gaji", layout="wide", page_icon="📝")

# ==========================================
# FUNGSI FONT LOKAL & PENGUKUR TEKS (AUTO-FIT CONTENT)
# ==========================================
def get_font(size, style="regular"):
    fonts = {
        "regular": [
            "arial.ttf", "calibri.ttf",
            "C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ],
        "bold": [
            "arialbd.ttf", "calibrib.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\calibrib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ],
        "mono": [
            "cour.ttf", "consola.ttf", 
            "C:\\Windows\\Fonts\\cour.ttf", "C:\\Windows\\Fonts\\consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        ]
    }
    for path in fonts.get(style, fonts["regular"]):
        try: return ImageFont.truetype(path, size)
        except IOError: continue
    try: return ImageFont.load_default(size=size)
    except: return ImageFont.load_default()

def get_text_dim(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        w, h = draw.textsize(text, font=font)
        return w, h

# ==========================================
# SUNTIKAN CSS: MODERN CLEAN UI (ADAPTIF DARK/LIGHT MODE)
# ==========================================
st.markdown("""
    <style>
    /* Menyembunyikan elemen bawaan Streamlit yang mengganggu */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    header {display: none !important;}
    .stDeployButton {display: none !important;}
    
    /* Styling Sapaan Teks (Hero Header) - Menyesuaikan tema otomatis */
    .custom-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 5px;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    .custom-subtitle {
        font-size: 1rem;
        opacity: 0.7;
        margin-bottom: 25px;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Styling Kotak Metrik (Dashboard Cards) */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.8;
    }

    /* Styling Tampilan Form Input */
    div[data-testid="stForm"] {
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }
    
    /* Styling Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--secondary-background-color);
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent;
        border-top: 3px solid #FF4B4B !important;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# Skrip agresif untuk memblokir shortcut 'C'
components.html(
    """
    <script>
    function blockC(e) {
        if (e.key === 'c' || e.key === 'C') {
            var activeTag = e.target ? e.target.tagName.toUpperCase() : '';
            if (activeTag !== 'INPUT' && activeTag !== 'TEXTAREA') {
                e.stopImmediatePropagation();
                e.stopPropagation();
                e.preventDefault();
            }
        }
    }
    window.addEventListener('keydown', blockC, true);
    if (window.parent) { window.parent.addEventListener('keydown', blockC, true); }
    if (window.top) { window.top.addEventListener('keydown', blockC, true); }
    </script>
    """,
    height=0,
    width=0,
)

# ==========================================
# 0. SISTEM KEAMANAN (LOGIN)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<div class='custom-title' style='text-align: center;'>🔐 Sistem Perhitungan Gaji</div>", unsafe_allow_html=True)
        st.markdown("<div class='custom-subtitle' style='text-align: center;'>Silakan masuk untuk mengakses data operasional.</div>", unsafe_allow_html=True)
        
        with st.form("form_login"):
            username = st.text_input("Username", placeholder="Masukkan Username...")
            password = st.text_input("Password", type="password", placeholder="Masukkan Password...")
            submit_login = st.form_submit_button("Masuk Aplikasi", type="primary", use_container_width=True)
            
            if submit_login:
                if username == "admin" and password == "admin123":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("⚠️ Akses Ditolak! Username atau Password salah.")
                    
    st.stop()


# ==========================================
# 1. KONEKSI GOOGLE SHEETS (ANTI-NYANGKUT)
# ==========================================
@st.cache_resource(ttl=600) 
def init_connection_v3():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    except:
        dict_creds = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict_creds, scope)
    return gspread.authorize(creds)

@st.cache_resource(ttl=600) 
def get_all_worksheets():
    client = init_connection_v3()
    ss = client.open_by_url("https://docs.google.com/spreadsheets/d/1nSVOJTyA48REHwPvaWbvVXUupdh_GcrCHvBqbEA-xe8/edit")
    def get_or_create(name, cols):
        try: return ss.worksheet(name)
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

try:
    ws = get_all_worksheets()
except Exception as e:
    st.error(f"Koneksi Server gagal: {e}")
    st.stop()

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


# ==========================================
# HEADER & SAPAAN DINAMIS
# ==========================================
tz_lokal = timezone(timedelta(hours=7))
jam_sekarang = datetime.now(tz_lokal).hour

if 5 <= jam_sekarang < 11:
    sapaan = "Selamat Pagi 🌅"
elif 11 <= jam_sekarang < 15:
    sapaan = "Selamat Siang ☀️"
elif 15 <= jam_sekarang < 18:
    sapaan = "Selamat Sore 🌤️"
else:
    sapaan = "Selamat Malam 🌙"

st.markdown(f"<div class='custom-title'>{sapaan}, Admin!</div>", unsafe_allow_html=True)
st.markdown("<div class='custom-subtitle'>Berikut adalah laporan operasional penggajian Anda hari ini.</div>", unsafe_allow_html=True)

# ==========================================
# PAPAN METRIK (DASHBOARD)
# ==========================================
today_date = datetime.now(tz_lokal).date()
end_date_dash = today_date 

col_filter, _ = st.columns([1, 3])
with col_filter:
    filter_waktu = st.selectbox("⏳ Filter Periode Angka:", ["Hari Ini", "1 Minggu Terakhir", "1 Bulan Terakhir", "3 Bulan Terakhir", "Kustom Tanggal"])
    
    if filter_waktu == "Kustom Tanggal":
        rentang_kustom = st.date_input("Pilih Rentang Tanggal", value=(today_date - timedelta(days=7), today_date), max_value=today_date, format="DD/MM/YYYY")
        if isinstance(rentang_kustom, tuple) and len(rentang_kustom) == 2:
            start_date_dash, end_date_dash = rentang_kustom
        else:
            start_date_dash = end_date_dash = rentang_kustom[0] if isinstance(rentang_kustom, tuple) else rentang_kustom
    elif filter_waktu == "Hari Ini":
        start_date_dash = today_date
    elif filter_waktu == "1 Minggu Terakhir":
        start_date_dash = today_date - timedelta(days=7)
    elif filter_waktu == "1 Bulan Terakhir":
        start_date_dash = today_date - timedelta(days=30)
    elif filter_waktu == "3 Bulan Terakhir":
        start_date_dash = today_date - timedelta(days=90)

total_karyawan_metrik = len(daftar_karyawan)

df_gaji_dash = st.session_state.df_gaji.copy()
if not df_gaji_dash.empty:
    df_gaji_dash['Date_Obj'] = pd.to_datetime(df_gaji_dash['Tanggal'], errors='coerce').dt.date
    gaji_filtered = df_gaji_dash[(df_gaji_dash['Date_Obj'] >= start_date_dash) & (df_gaji_dash['Date_Obj'] <= end_date_dash)]
    total_gaji_dash = pd.to_numeric(gaji_filtered['Total'], errors='coerce').fillna(0).sum()
else:
    total_gaji_dash = 0

df_kb_dash = st.session_state.df_kasbon.copy()
if not df_kb_dash.empty:
    df_kb_dash['Date_Obj'] = pd.to_datetime(df_kb_dash['Tanggal'], errors='coerce').dt.date
    kb_filtered = df_kb_dash[(df_kb_dash['Date_Obj'] >= start_date_dash) & (df_kb_dash['Date_Obj'] <= end_date_dash)]
    
    kb_tambah = kb_filtered[kb_filtered['Tipe'] == 'Penambahan']
    total_tambah_dash = pd.to_numeric(kb_tambah['Nominal'], errors='coerce').fillna(0).sum()
    catatan_tambah = f"📌 {str(kb_tambah.iloc[-1]['Keterangan'])}" if not kb_tambah.empty else "Tidak ada transaksi"
    
    kb_kurang = kb_filtered[kb_filtered['Tipe'] == 'Pengurangan']
    total_kurang_dash = pd.to_numeric(kb_kurang['Nominal'], errors='coerce').fillna(0).sum()
    catatan_kurang = f"📌 {str(kb_kurang.iloc[-1]['Keterangan'])}" if not kb_kurang.empty else "Tidak ada transaksi"
else:
    total_tambah_dash = 0
    total_kurang_dash = 0
    catatan_tambah = "Belum ada transaksi"
    catatan_kurang = "Belum ada transaksi"

if filter_waktu == "Kustom Tanggal":
    label_periode = f"Periode: {start_date_dash.strftime('%d/%m/%Y')} - {end_date_dash.strftime('%d/%m/%Y')}"
else:
    label_periode = f"Periode: {filter_waktu}"

m1, m2, m3, m4 = st.columns(4)
m1.metric(label="👥 TOTAL KARYAWAN", value=f"{total_karyawan_metrik} Orang", delta="Karyawan Terdaftar", delta_color="off")
m2.metric(label="💸 PENGELUARAN GAJI", value=f"Rp {total_gaji_dash:,.0f}".replace(",", "."), delta=label_periode, delta_color="off")
m3.metric(label="📉 KASBON (PENGURANGAN)", value=f"Rp {total_kurang_dash:,.0f}".replace(",", "."), delta=catatan_kurang, delta_color="off")
m4.metric(label="📈 KASBON (PENAMBAHAN)", value=f"Rp {total_tambah_dash:,.0f}".replace(",", "."), delta=catatan_tambah, delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# MENU TABS
# ==========================================
menu1, menu2, menu3, menu4, menu5, menu6 = st.tabs([
    "📝 1. Input Harian", 
    "📂 2. Database Pekerjaan", 
    "💸 3. Data Transaksi Tambah/Kurang", 
    "🖨️ 4. Cetak Slip Gaji", 
    "📊 5. Laporan Resume Kas", 
    "⚙️ 6. Pengaturan"
])

# ==========================================
# MENU 1: INPUT HARIAN
# ==========================================
with menu1:
    st.header("Input Pekerjaan Harian")
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
                tanggal = st.date_input("Pilih Tanggal", st.session_state.last_date_harian, max_value=datetime.now(tz_lokal).date(), format="DD/MM/YYYY")
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
                if st.session_state.notif_1_type == "success": notif_area_1.success(st.session_state.notif_1)
                else: notif_area_1.error(st.session_state.notif_1)
                time.sleep(1.5)
                notif_area_1.empty()
                del st.session_state.notif_1
                del st.session_state.notif_1_type
                
            submitted_input = st.form_submit_button("💾 Simpan Data Pekerjaan", type="primary", use_container_width=True)
            if submitted_input:
                jumlah = int(jumlah_str.strip()) if jumlah_str.strip().isdigit() else 0
                if pekerjaan != "-" and jumlah > 0:
                    upah = tarif_pekerjaan.get(pekerjaan, 0)
                    total = jumlah * upah
                    try:
                        id_data = f"ID-{int(time.time()*1000)}"
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
# MENU 2: DATABASE PEKERJAAN
# ==========================================
with menu2:
    st.header("Database Riwayat Pekerjaan")
    st.caption("💡 Pilih rentang tanggal pada kalender di bawah untuk melihat data periode tertentu. Cukup edit langsung di tabel lalu tekan **Enter**.")
    df_gaji = st.session_state.df_gaji.copy()
    if len(df_gaji) > 0:
        df_gaji['Date_Obj'] = pd.to_datetime(df_gaji['Tanggal'], errors='coerce').dt.date
        tanggal_valid = df_gaji['Date_Obj'].dropna()
        
        if len(tanggal_valid) > 0:
            max_tgl = tanggal_valid.max()
            default_start = tanggal_valid.min()
        else:
            max_tgl = datetime.now(tz_lokal).date()
            default_start = datetime.now(tz_lokal).date()
            
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1: rentang_tanggal = st.date_input("Pilih Periode Tanggal", value=(default_start, max_tgl), max_value=datetime.now(tz_lokal).date(), format="DD/MM/YYYY")
        with col_f2: filter_nama = st.selectbox("🔍 Filter Karyawan:", ["Semua Karyawan"] + daftar_karyawan, key="filter_db_kerja")
            
        if isinstance(rentang_tanggal, tuple) and len(rentang_tanggal) == 2: tgl_mulai, tgl_selesai = rentang_tanggal
        else: tgl_mulai = tgl_selesai = rentang_tanggal[0] if isinstance(rentang_tanggal, tuple) else rentang_tanggal

        df_tampil = df_gaji[(df_gaji['Date_Obj'] >= tgl_mulai) & (df_gaji['Date_Obj'] <= tgl_selesai)].copy()
        if filter_nama != "Semua Karyawan": df_tampil = df_tampil[df_tampil['Nama'] == filter_nama]
            
        if len(df_tampil) > 0:
            df_tampil['Urutan_Hari'] = df_tampil['Hari'].map(URUTAN_HARI)
            df_tampil = df_tampil.sort_values(by=["Tanggal", "Urutan_Hari"]).drop(columns=["Urutan_Hari", "Date_Obj"])
            daftar_tanggal = df_tampil[['Tanggal', 'Hari']].drop_duplicates().values
            for tgl, hari in daftar_tanggal:
                tgl_format = datetime.strptime(str(tgl), "%Y-%m-%d").strftime("%d-%m-%Y")
                with st.expander(f"📅 Hari **{hari}**, **{tgl_format}**", expanded=True):
                    df_harian = df_tampil[(df_tampil['Tanggal'] == tgl) & (df_tampil['Hari'] == hari)].copy()
                    
                    df_harian_view = df_harian[['ID Data', 'Nama', 'Pekerjaan', 'Upah', 'Jumlah', 'Total']].copy().reset_index(drop=True)
                    df_harian_view['Upah'] = pd.to_numeric(df_harian_view['Upah'], errors='coerce').fillna(0)
                    df_harian_view['Jumlah'] = pd.to_numeric(df_harian_view['Jumlah'], errors='coerce').fillna(0)
                    df_harian_view['Total'] = pd.to_numeric(df_harian_view['Total'], errors='coerce').fillna(0)
                    
                    notif_key = f"notif_2_{tgl}_{hari}"
                    notif_area_2 = st.empty()
                    if notif_key in st.session_state:
                        notif_area_2.success(st.session_state[notif_key])
                        time.sleep(1.5)
                        notif_area_2.empty()
                        del st.session_state[notif_key]
                    
                    edited_df = st.data_editor(
                        df_harian_view, 
                        num_rows="dynamic", 
                        use_container_width=True, 
                        hide_index=True, 
                        key=f"editor_{tgl}_{hari}",
                        column_config={
                            "ID Data": None,
                            "Upah": st.column_config.NumberColumn("Upah", format="Rp %,d"), 
                            "Jumlah": st.column_config.NumberColumn("Jumlah", format="%,d"), 
                            "Total": st.column_config.NumberColumn("Total", format="Rp %,d")
                        }
                    )

                    view_records = df_harian_view.fillna("").astype(str).to_dict('records')
                    edit_records = edited_df.fillna("").astype(str).to_dict('records')
                    
                    if view_records != edit_records:
                        edited_df = edited_df[edited_df['Nama'].astype(str).str.strip() != ""] 
                        
                        ids = edited_df['ID Data'].apply(lambda x: f"ID-{int(time.time()*1000)}-{pd.util.hash_pandas_object(pd.Series([x])).iloc[0]}" if pd.isna(x) or str(x).strip() == "" else str(x))
                        upahs = pd.to_numeric(edited_df['Upah'], errors='coerce').fillna(0)
                        jumlahs = pd.to_numeric(edited_df['Jumlah'], errors='coerce').fillna(0)
                        totals = jumlahs * upahs
                        
                        df_processed = pd.DataFrame({'ID Data': ids, 'Hari': hari, 'Tanggal': tgl, 'Nama': edited_df['Nama'], 'Pekerjaan': edited_df['Pekerjaan'], 'Upah': upahs, 'Jumlah': jumlahs, 'Total': totals})
                        
                        orig_ids = df_harian['ID Data'].tolist()
                        df_sisa = st.session_state.df_gaji[~st.session_state.df_gaji['ID Data'].isin(orig_ids)]
                        
                        df_final = pd.concat([df_sisa, df_processed]).sort_values(by="Tanggal").reset_index(drop=True)
                        if 'Date_Obj' in df_final.columns: df_final = df_final.drop(columns=['Date_Obj'])
                        st.session_state.df_gaji = df_final
                        ws["gaji"].clear()
                        ws["gaji"].update([df_final.columns.values.tolist()] + df_final.fillna("").values.tolist())
                        st.session_state[notif_key] = "✅ Otomatis Tersimpan!"
                        st.rerun()
        else: st.info(f"Tidak ada riwayat pekerjaan pada rentang tanggal tersebut.")
    else: st.info("Belum ada data pekerjaan yang tersimpan.")

# ==========================================
# MENU 3: PENAMBAHAN & PENGURANGAN
# ==========================================
with menu3:
    st.header("Pencatatan Penambahan & Pengurangan")
    if "last_date_kb" not in st.session_state or st.session_state.last_date_kb > today_date: st.session_state.last_date_kb = today_date
    if "last_karyawan_kb" not in st.session_state: st.session_state.last_karyawan_kb = daftar_karyawan[0] if daftar_karyawan else ""

    if len(daftar_karyawan) > 0:
        with st.form("form_kasbon", clear_on_submit=True):
            col_kb1, col_kb2, col_kb3 = st.columns(3)
            with col_kb1: tgl_kb = st.date_input("Tanggal Transaksi", st.session_state.last_date_kb, max_value=datetime.now(tz_lokal).date(), format="DD/MM/YYYY")
            with col_kb2:
                idx_kb = daftar_karyawan.index(st.session_state.last_karyawan_kb) if st.session_state.last_karyawan_kb in daftar_karyawan else 0
                nama_kb = st.selectbox("Pilih Karyawan", daftar_karyawan, index=idx_kb)
            with col_kb3: tipe_kb = st.selectbox("Jenis Transaksi", ["Penambahan", "Pengurangan"])
                
            col_kb4, col_kb5 = st.columns([2, 1])
            with col_kb4: ket_kb = st.text_input("Keterangan")
            with col_kb5: nominal_str = st.text_input("Nominal (Rp)", placeholder="Ketik nominal (contoh: 50000)")
                
            notif_area_3 = st.empty()
            if "notif_3" in st.session_state:
                if st.session_state.notif_3_type == "success": notif_area_3.success(st.session_state.notif_3)
                else: notif_area_3.error(st.session_state.notif_3)
                time.sleep(1.5)
                notif_area_3.empty()
                del st.session_state.notif_3
                del st.session_state.notif_3_type
                
            if st.form_submit_button("💾 Simpan Data", type="primary", use_container_width=True):
                nominal_kb = int(nominal_str.strip()) if nominal_str.strip().isdigit() else 0
                if nominal_kb > 0 and ket_kb.strip() != "":
                    try:
                        id_kb = f"KB-{int(time.time()*1000)}"
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
                    
        st.markdown("---")
        st.subheader("Database Riwayat Penambahan & Pengurangan")
        st.caption("💡 Edit atau Hapus langsung di tabel lalu tekan **Enter**.")
        
        df_kasbon_db = st.session_state.df_kasbon.copy()
        if len(df_kasbon_db) > 0:
            df_kasbon_db['Date_Obj'] = pd.to_datetime(df_kasbon_db['Tanggal'], errors='coerce').dt.date
            valid_dates_kb = df_kasbon_db['Date_Obj'].dropna()
            
            if len(valid_dates_kb) > 0:
                max_tgl_kb = valid_dates_kb.max()
                default_start_kb = valid_dates_kb.min()
            else:
                max_tgl_kb = datetime.now(tz_lokal).date()
                default_start_kb = datetime.now(tz_lokal).date()
            
            col_f1_kb, col_f2_kb = st.columns([2, 1])
            with col_f1_kb:
                rentang_kb = st.date_input("Pilih Periode Transaksi", value=(default_start_kb, max_tgl_kb), max_value=datetime.now(tz_lokal).date(), format="DD/MM/YYYY", key="filter_tgl_kb")
            with col_f2_kb:
                filter_nama_kb = st.selectbox("🔍 Filter Karyawan:", ["Semua Karyawan"] + daftar_karyawan, key="filter_nama_kb")
                
            if isinstance(rentang_kb, tuple) and len(rentang_kb) == 2: t_start_kb, t_end_kb = rentang_kb
            else: t_start_kb = t_end_kb = rentang_kb[0] if isinstance(rentang_kb, tuple) else rentang_kb
                
            df_tampil_kb = df_kasbon_db[(df_kasbon_db['Date_Obj'] >= t_start_kb) & (df_kasbon_db['Date_Obj'] <= t_end_kb)].copy()
            if filter_nama_kb != "Semua Karyawan":
                df_tampil_kb = df_tampil_kb[df_tampil_kb['Nama'] == filter_nama_kb]
                
            if len(df_tampil_kb) > 0:
                df_tampil_kb = df_tampil_kb.sort_values(by=["Tanggal", "Nama"]).drop(columns=["Date_Obj"])
                daftar_tanggal_kb = df_tampil_kb['Tanggal'].drop_duplicates().values
                
                for tgl_val in daftar_tanggal_kb:
                    tgl_obj_kb = datetime.strptime(str(tgl_val), "%Y-%m-%d")
                    hari_val = HARI_INDO[tgl_obj_kb.strftime("%A")]
                    tgl_format_kb = tgl_obj_kb.strftime("%d-%m-%Y")
                    
                    with st.expander(f"📅 Hari **{hari_val}**, **{tgl_format_kb}**", expanded=True):
                        df_harian_kb = df_tampil_kb[df_tampil_kb['Tanggal'] == tgl_val].copy()
                        df_harian_view_kb = df_harian_kb[['ID Kasbon', 'Nama', 'Tipe', 'Keterangan', 'Nominal']].copy().reset_index(drop=True)
                        df_harian_view_kb['Nominal'] = pd.to_numeric(df_harian_view_kb['Nominal'], errors='coerce').fillna(0)
                        
                        notif_key_kb = f"notif_3_{tgl_val}"
                        notif_area_3_db = st.empty()
                        if notif_key_kb in st.session_state:
                            notif_area_3_db.success(st.session_state[notif_key_kb])
                            time.sleep(1.5)
                            notif_area_3_db.empty()
                            del st.session_state[notif_key_kb]
                            
                        edited_df_kb = st.data_editor(
                            df_harian_view_kb,
                            num_rows="dynamic",
                            use_container_width=True,
                            column_config={
                                "ID Kasbon": None, 
                                "Tipe": st.column_config.SelectboxColumn("Tipe Transaksi", options=["Penambahan", "Pengurangan"], required=True), 
                                "Nominal": st.column_config.NumberColumn("Nominal (Rp)", format="Rp %,d", required=True)
                            },
                            hide_index=True,
                            key=f"editor_kb_{tgl_val}"
                        )
                        
                        view_records_kb = df_harian_view_kb.fillna("").astype(str).to_dict('records')
                        edit_records_kb = edited_df_kb.fillna("").astype(str).to_dict('records')
                        
                        if view_records_kb != edit_records_kb:
                            edited_df_kb = edited_df_kb[edited_df_kb['Nama'].astype(str).str.strip() != ""]
                            
                            ids_kb = edited_df_kb['ID Kasbon'].apply(lambda x: f"KB-{int(time.time()*1000)}-{pd.util.hash_pandas_object(pd.Series([x])).iloc[0]}" if pd.isna(x) or str(x).strip() == "" else str(x))
                            noms_kb = pd.to_numeric(edited_df_kb['Nominal'], errors='coerce').fillna(0)
                            
                            df_proc_kb = pd.DataFrame({'ID Kasbon': ids_kb, 'Tanggal': tgl_val, 'Nama': edited_df_kb['Nama'], 'Tipe': edited_df_kb['Tipe'], 'Keterangan': edited_df_kb['Keterangan'], 'Nominal': noms_kb})
                            
                            orig_ids_kb = df_harian_kb['ID Kasbon'].tolist()
                            df_sisa_kb = st.session_state.df_kasbon[~st.session_state.df_kasbon['ID Kasbon'].isin(orig_ids_kb)]
                            
                            df_final_kb = pd.concat([df_sisa_kb, df_proc_kb]).sort_values(by="Tanggal").reset_index(drop=True)
                            if 'Date_Obj' in df_final_kb.columns: df_final_kb = df_final_kb.drop(columns=['Date_Obj'])
                            
                            st.session_state.df_kasbon = df_final_kb
                            ws["kasbon"].clear()
                            ws["kasbon"].update([df_final_kb.columns.values.tolist()] + df_final_kb.fillna("").values.tolist())
                            st.session_state[notif_key_kb] = "✅ Database Kasbon Tersimpan Otomatis!"
                            st.rerun()
            else:
                st.info("Tidak ada riwayat transaksi pada rentang tanggal tersebut.")
        else:
            st.info("Belum ada data penambahan atau pengurangan yang tersimpan.")
    else:
        st.info("Belum ada data karyawan. Silakan isi di Menu 6.")

# ==========================================
# MENU 4: CETAK SLIP GAJI
# ==========================================
with menu4:
    st.header("Cetak & Unduh Slip Gaji")
    
    df_gaji = st.session_state.df_gaji.copy()
    df_kasbon = st.session_state.df_kasbon.copy()
    
    if len(df_gaji) > 0 and len(daftar_karyawan) > 0:
        rentang_slip = st.date_input("Pilih Periode Tanggal Slip Gaji", value=(datetime.today().date(), datetime.today().date()), max_value=datetime.now(tz_lokal).date(), format="DD/MM/YYYY", key="rentang_slip_gaji")
        if isinstance(rentang_slip, tuple) and len(rentang_slip) == 2: tgl_mulai_slip, tgl_selesai_slip = rentang_slip
        else: tgl_mulai_slip = tgl_selesai_slip = rentang_slip[0] if isinstance(rentang_slip, tuple) else rentang_slip
            
        nama_slip_pilihan = st.selectbox("Pilih Nama Karyawan", ["Semua Karyawan"] + daftar_karyawan, key="slip_nama")
        
        st.markdown("---")
        st.subheader("✍️ Catatan Opsional per Karyawan (Opsional)")
        st.caption("💡 Tulis catatan khusus yang ingin dicetak di paling bawah slip gaji (di bawah garis penutup akhir, tanpa garis bawah).")
        
        target_kar_list = daftar_karyawan if nama_slip_pilihan == "Semua Karyawan" else [nama_slip_pilihan]
        catatan_opsional_dict = {}
        
        cols_catatan = st.columns(min(len(target_kar_list), 3))
        for idx, kar_nm in enumerate(target_kar_list):
            with cols_catatan[idx % len(cols_catatan)]:
                catatan_opsional_dict[kar_nm] = st.text_input(f"Catatan untuk {kar_nm}", key=f"opt_cat_{kar_nm}", placeholder="Contoh: Sisa Pinjaman 500.000")

        st.markdown("---")
        if st.button("🖨️ Buat Slip Gaji", type="primary"):
            df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal'], errors='coerce').dt.date
            target_karyawan = daftar_karyawan if nama_slip_pilihan == "Semua Karyawan" else [nama_slip_pilihan]
            
            generated_slips = []
            
            for nama_slip in target_karyawan:
                df_filter_gaji = df_gaji[(df_gaji['Nama'] == nama_slip) & (df_gaji['Tanggal'] >= tgl_mulai_slip) & (df_gaji['Tanggal'] <= tgl_selesai_slip)]
                df_filter_kb = df_kasbon[(df_kasbon['Nama'] == nama_slip) & (pd.to_datetime(df_kasbon['Tanggal'], errors='coerce').dt.date >= tgl_mulai_slip) & (pd.to_datetime(df_kasbon['Tanggal'], errors='coerce').dt.date <= tgl_selesai_slip)] if len(df_kasbon) > 0 else pd.DataFrame()
                
                if len(df_filter_gaji) > 0 or len(df_filter_kb) > 0:
                    scale = 4 
                    f_reg = get_font(12 * scale, "mono") 
                    f_bold = get_font(14 * scale, "mono")
                    f_title = get_font(18 * scale, "mono")
                    
                    lines = []
                    lines.append(("=================================", f_bold, "left", 5 * scale))
                    lines.append(("SLIP GAJI", f_title, "center", 10 * scale))
                    lines.append(("=================================", f_bold, "left", 10 * scale))
                    lines.append((f"Nama    : {nama_slip}", f_bold, "left", 10 * scale))
                    lines.append((f"Periode : {tgl_mulai_slip.strftime('%d/%m/%Y')} - {tgl_selesai_slip.strftime('%d/%m/%Y')}", f_bold, "left", 10 * scale))
                    lines.append(("=================================", f_bold, "left", 10 * scale))
                    
                    total_upah = 0
                    first_day = True
                    for tgl, data_harian in df_filter_gaji.groupby('Tanggal'):
                        if not first_day: lines.append(("", f_bold, "left", 15 * scale))
                        first_day = False
                        hari_indo = HARI_INDO.get(tgl.strftime("%A"), "")
                        lines.append((f"Hari/Tgl: {hari_indo}, {tgl.strftime('%d/%m/%Y')}", f_bold, "left", 10 * scale))
                        sub = 0
                        for _, row in data_harian.iterrows():
                            j, u, t = float(row['Jumlah']), float(row['Upah']), float(row['Total'])
                            lines.append((f"- {row['Pekerjaan']}", f_bold, "left", 10 * scale))
                            lines.append((f"  {j:,.0f} pcs x Rp{u:,.0f} = Rp{t:,.0f}".replace(",", "."), f_bold, "left", 10 * scale))
                            sub += t
                        lines.append((f"Sub-total: Rp{sub:,.0f}".replace(",", "."), f_bold, "left", 10 * scale))
                        total_upah += sub
                        
                    tot_tambah, tot_kurang = 0, 0
                    if len(df_filter_kb) > 0:
                        lines.append(("", f_bold, "left", 15 * scale))
                        lines.append(("--- CATATAN TAMBAHAN ---", f_bold, "left", 10 * scale))
                        for _, rkb in df_filter_kb.iterrows():
                            nom = float(rkb['Nominal'])
                            sign = "+" if rkb['Tipe'] == "Penambahan" else "-"
                            lines.append((f"{sign} {rkb['Keterangan']} (Rp{nom:,.0f})".replace(",", "."), f_bold, "left", 10 * scale))
                            if rkb['Tipe'] == "Penambahan": tot_tambah += nom
                            else: tot_kurang += nom
                            
                    total_bersih = total_upah + tot_tambah - tot_kurang
                    lines.append(("=================================", f_bold, "left", 15 * scale))
                    lines.append((f"TOTAL GAJI DITERIMA: Rp{total_bersih:,.0f}".replace(",", "."), f_bold, "left", 15 * scale))
                    lines.append(("=================================", f_bold, "left", 15 * scale))
                    
                    catatan_input = catatan_opsional_dict.get(nama_slip, "").strip()
                    if catatan_input != "":
                        lines.append((f"Catatan : {catatan_input}", f_bold, "left", 8 * scale))
                    
                    dummy_img = Image.new('RGB', (10, 10))
                    dummy_draw = ImageDraw.Draw(dummy_img)
                    
                    max_w = 0
                    current_y = 10 * scale 
                    rendered_lines = []
                    for text, font, align, spacing_top in lines:
                        current_y += spacing_top
                        if text == "":
                            rendered_lines.append((0, current_y, 0, text, font, align))
                            continue
                        tw, th = get_text_dim(dummy_draw, text, font)
                        if tw > max_w: max_w = tw
                        rendered_lines.append((tw, current_y, th, text, font, align))
                        current_y += th
                    
                    margin_x = 10 * scale
                    canvas_w = int(max_w + (margin_x * 2))
                    canvas_h = int(current_y + (10 * scale))
                    
                    img_slip = Image.new('RGB', (canvas_w, canvas_h), color=(255, 255, 255))
                    draw_slip = ImageDraw.Draw(img_slip)
                    
                    for tw, c_y, th, text, font, align in rendered_lines:
                        if text == "": continue
                        if align == "center": x_pos = (canvas_w - tw) / 2
                        else: x_pos = margin_x
                        draw_slip.text((x_pos, c_y), text, font=font, fill=(0, 0, 0))
                        
                    buf_s = io.BytesIO()
                    img_slip.save(buf_s, format="JPEG", quality=100)
                    byte_slip = buf_s.getvalue()
                    
                    total_gaji_fmt_str = f"Rp{total_bersih:,.0f}".replace(",", ".")
                    caption_text = f"Slip Gaji {nama_slip}\nPeriode: {tgl_mulai_slip.strftime('%d/%m/%Y')} - {tgl_selesai_slip.strftime('%d/%m/%Y')}\nTotal Gaji: {total_gaji_fmt_str}"
                        
                    generated_slips.append((nama_slip, byte_slip, caption_text))
            
            if generated_slips:
                st.success(f"✅ Berhasil membuat {len(generated_slips)} Slip Gaji!")
                cols_per_row = 3
                for i in range(0, len(generated_slips), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        if i + j < len(generated_slips):
                            nama_slip_hasil, byte_slip_hasil, caption_res = generated_slips[i + j]
                            with cols[j]:
                                st.markdown(f"**📄 Slip: {nama_slip_hasil}**")
                                st.image(byte_slip_hasil, width=250) 
                                
                                st.text_area("📋 Copy Teks Caption:", value=caption_res, height=75, key=f"cap_{nama_slip_hasil}")
                                
                                b64_img = base64.b64encode(byte_slip_hasil).decode()
                                print_btn_html = f"""
                                <div style="text-align: center; margin-bottom: 5px;">
                                    <button onclick="printImage()" style="background-color: #FF4B4B; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; font-family: sans-serif; font-weight: bold; width: 100%;">🖨️ PRINT LANGSUNG</button>
                                </div>
                                <script>
                                function printImage() {{
                                    var win = window.open('', '_blank');
                                    win.document.write('<html><head><title>Print Slip - {nama_slip_hasil}</title>');
                                    win.document.write('<style>@page {{ margin: 0mm; size: auto; }} body {{ margin: 0px; text-align: center; background-color: white; }}</style>');
                                    win.document.write('</head><body><img src="data:image/jpeg;base64,{b64_img}" style="width: 100%; max-width: 100%; display: block; margin: 0 auto;" onload="window.print(); window.close();" /></body></html>');
                                    win.document.close();
                                }}
                                </script>
                                """
                                components.html(print_btn_html, height=50)
                                
                                st.download_button(
                                    label="📥 Unduh File JPG", 
                                    data=byte_slip_hasil, 
                                    file_name=f"Slip_{nama_slip_hasil}.jpg", 
                                    mime="image/jpeg", 
                                    key=f"dl_{nama_slip_hasil}"
                                )
            else:
                st.info("Tidak ada data pekerjaan atau kasbon untuk karyawan tersebut pada periode yang dipilih.")

# ==========================================
# MENU 5: LAPORAN RESUME KAS
# ==========================================
with menu5:
    st.header("📊 Laporan Resume Kas")
    
    df_gaji = st.session_state.df_gaji.copy()
    df_kasbon = st.session_state.df_kasbon.copy()
    df_lain_all = st.session_state.df_pengeluaran.copy()
    
    rentang_res = st.date_input("Pilih Periode Resume Kas", value=(datetime.today().date(), datetime.today().date()), max_value=datetime.now(tz_lokal).date(), format="DD/MM/YYYY", key="rentang_resume")
    if isinstance(rentang_res, tuple) and len(rentang_res) == 2: tgl_mulai_res, tgl_selesai_res = rentang_res
    else: tgl_mulai_res = tgl_selesai_res = rentang_res[0] if isinstance(rentang_res, tuple) else rentang_res
    
    tarik_uang_str = st.text_input("💵 Total Penarikan Uang Cash (Rp)", placeholder="Ketik nominal (contoh: 5000000)")
    if tarik_uang_str.strip():
        if tarik_uang_str.strip().isdigit(): st.info(f"📌 Nominal terinput: **Rp {int(tarik_uang_str.strip()):,}**".replace(",", "."))
        else: st.error("⚠️ Mohon ketik nominal penarikan berupa angka yang valid.")
    else: st.info("📌 Nominal terinput: **Rp 0**")
    
    st.markdown("---")
    
    # --- PENGELUARAN LAINNYA ---
    st.subheader("🛒 Pengeluaran Lainnya")
    st.caption("💡 Tambah data di baris kosong paling bawah. Edit/Hapus langsung di tabel, lalu klik tombol **Simpan** di bawah.")
    
    notif_area_5_db = st.empty()
    if "notif_5_db" in st.session_state:
        notif_area_5_db.success(st.session_state["notif_5_db"])
        time.sleep(1.5)
        notif_area_5_db.empty()
        del st.session_state["notif_5_db"]

    df_peng_view = st.session_state.df_pengeluaran[['ID Lain', 'Keterangan', 'Nominal']].copy().reset_index(drop=True)
    if not df_peng_view.empty:
        df_peng_view['Nominal'] = pd.to_numeric(df_peng_view['Nominal'], errors='coerce').fillna(0)
    else:
        df_peng_view = pd.DataFrame(columns=["ID Lain", "Keterangan", "Nominal"]).reset_index(drop=True)

    edited_peng_state = st.data_editor(
        df_peng_view,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID Lain": None, 
            "Keterangan": st.column_config.TextColumn("Keterangan", required=True),
            "Nominal": st.column_config.NumberColumn("Nominal (Rp)", format="Rp %,d", required=True)
        },
        key="editor_pengeluaran"
    )
    
    btn_simpan_pengeluaran = st.button("💾 Simpan Pengeluaran Lainnya", type="primary", use_container_width=True)
    
    if btn_simpan_pengeluaran:
        edited_peng_state = edited_peng_state[edited_peng_state['Keterangan'].astype(str).str.strip() != ""]
        noms_lain = pd.to_numeric(edited_peng_state['Nominal'], errors='coerce').fillna(0)
        
        ids_lain = edited_peng_state['ID Lain'].apply(lambda x: f"LAIN-{int(time.time()*1000)}-{pd.util.hash_pandas_object(pd.Series([x])).iloc[0]}" if pd.isna(x) or str(x).strip() == "" else str(x))
            
        df_final_peng = pd.DataFrame({'ID Lain': ids_lain, 'Keterangan': edited_peng_state['Keterangan'], 'Nominal': noms_lain})
        st.session_state.df_pengeluaran = df_final_peng
        ws["pengeluaran"].clear()
        ws["pengeluaran"].update([df_final_peng.columns.values.tolist()] + df_final_peng.fillna("").values.tolist())
        st.session_state["notif_5_db"] = "✅ Pengeluaran Lainnya Berhasil Disimpan Manual!"
        st.rerun()

    st.markdown("---")
    if st.button("🖼️ Generate Gambar Resume", type="primary"):
        df_lain_all = st.session_state.df_pengeluaran.copy()
        tarik_uang = int(tarik_uang_str.strip()) if tarik_uang_str.strip().isdigit() else 0
            
        df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal'], errors='coerce').dt.date
        df_f_gaji = df_gaji[(df_gaji['Tanggal'] >= tgl_mulai_res) & (df_gaji['Tanggal'] <= tgl_selesai_res)]
        
        if len(df_kasbon) > 0:
            df_kasbon['Tanggal'] = pd.to_datetime(df_kasbon['Tanggal'], errors='coerce').dt.date
            df_f_kb = df_kasbon[(df_kasbon['Tanggal'] >= tgl_mulai_res) & (df_kasbon['Tanggal'] <= tgl_selesai_res)]
        else:
            df_f_kb = pd.DataFrame()
            
        rekap_gaji = {k: 0 for k in daftar_karyawan}
        if len(df_f_gaji) > 0:
            for nama, df_n in df_f_gaji.groupby('Nama'):
                if nama in rekap_gaji: rekap_gaji[nama] += pd.to_numeric(df_n['Total'], errors='coerce').fillna(0).sum()
                
        if len(df_f_kb) > 0:
            for _, row_kb in df_f_kb.iterrows():
                nama, nom = row_kb['Nama'], float(row_kb['Nominal']) if pd.notnull(row_kb['Nominal']) else 0
                if nama in rekap_gaji:
                    if row_kb['Tipe'] == "Penambahan": rekap_gaji[nama] += nom
                    else: rekap_gaji[nama] -= nom
                        
        total_gaji_semua = sum(rekap_gaji.values())
        total_pengeluaran_lain = pd.to_numeric(df_lain_all['Nominal'], errors='coerce').fillna(0).sum() if len(df_lain_all) > 0 else 0
        total_pengeluaran_keseluruhan = total_gaji_semua + total_pengeluaran_lain
        sisa_uang = tarik_uang - total_pengeluaran_keseluruhan
        
        scale = 3 
        f_title = get_font(28 * scale, "bold")
        f_sub = get_font(18 * scale, "regular")
        f_bold = get_font(18 * scale, "bold")
        f_reg = get_font(18 * scale, "regular")
        
        dummy_img = Image.new('RGB', (10, 10))
        dummy_draw = ImageDraw.Draw(dummy_img)
        
        tot_gaji_fmt = f"Rp {total_gaji_semua:,.0f}".replace(",", ".")
        tot_lain_fmt = f"Rp {total_pengeluaran_lain:,.0f}".replace(",", ".")
        tarik_fmt = f"Rp {tarik_uang:,.0f}".replace(",", ".")
        total_keluar_fmt = f"Rp {total_pengeluaran_keseluruhan:,.0f}".replace(",", ".")
        sisa_fmt = f"Rp {sisa_uang:,.0f}".replace(",", ".")
        
        gaji_rows = [(k, f"Rp {rekap_gaji.get(k, 0):,.0f}".replace(",", ".")) for k in daftar_karyawan]
        lain_rows = [(str(r['Keterangan']), f"Rp {float(r['Nominal'] if pd.notnull(r['Nominal']) else 0):,.0f}".replace(",", ".")) for _, r in df_lain_all.iterrows()] if len(df_lain_all) > 0 else [("(Tidak ada pengeluaran lain)", "Rp 0")]
        ringkasan_rows = [
            ("Tarikan Uang Cash", tarik_fmt),
            ("Total Pengeluaran Keseluruhan", total_keluar_fmt)
        ]
        
        c1_texts = ["NAMA KARYAWAN", "TOTAL GAJI KARYAWAN", "KETERANGAN", "TOTAL PENGELUARAN LAIN", "SISA SALDO KAS", "Tarikan Uang Cash", "Total Pengeluaran Keseluruhan", "1. RINCIAN GAJI KARYAWAN", "2. PENGELUARAN LAINNYA", "3. RINGKASAN SALDO KAS"] + daftar_karyawan + [r[0] for r in lain_rows]
        c2_texts = ["JUMLAH GAJI", "JUMLAH", "NOMINAL", tot_gaji_fmt, tot_lain_fmt, tarik_fmt, total_keluar_fmt, sisa_fmt] + [r[1] for r in gaji_rows] + [r[1] for r in lain_rows]

        max_w_c1 = max([get_text_dim(dummy_draw, t, f_bold)[0] for t in c1_texts] + [get_text_dim(dummy_draw, t, f_reg)[0] for t in c1_texts])
        max_w_c2 = max([get_text_dim(dummy_draw, t, f_bold)[0] for t in c2_texts] + [get_text_dim(dummy_draw, t, f_reg)[0] for t in c2_texts])

        pad_x = 15 * scale
        pad_y = 10 * scale
        
        col1_w = int(max_w_c1 + (pad_x * 2))
        col2_w = int(max_w_c2 + (pad_x * 2))
        table_w = col1_w + col2_w
        
        _, text_h = get_text_dim(dummy_draw, "Hj", f_bold)
        row_h = int(text_h + (pad_y * 2)) 
        
        title_text = "RESUME LAPORAN KAS"
        tw, th_tit = get_text_dim(dummy_draw, title_text, f_title)
        tgl_str_res = f"Periode: {tgl_mulai_res.strftime('%d/%m/%Y')} s/d {tgl_selesai_res.strftime('%d/%m/%Y')}"
        pw, th_sub = get_text_dim(dummy_draw, tgl_str_res, f_sub)

        margin = 40 * scale
        min_canvas_w = max(tw, pw) + (margin * 2)
        actual_canvas_w = max(table_w + (margin * 2), min_canvas_w)
        table_x = (actual_canvas_w - table_w) / 2
        
        tot_h_canvas = margin
        tot_h_canvas += int(th_tit + 15 * scale)
        tot_h_canvas += int(th_sub + 40 * scale)
        
        tot_h_canvas += (len(gaji_rows) + 3) * row_h + int(30 * scale)
        tot_h_canvas += (len(lain_rows) + 3) * row_h + int(30 * scale)
        tot_h_canvas += (len(ringkasan_rows) + 3) * row_h + margin 
        
        img_res = Image.new('RGB', (int(actual_canvas_w), int(tot_h_canvas)), color=(255, 255, 255))
        draw = ImageDraw.Draw(img_res)
        
        y = margin
        draw.text(((actual_canvas_w - tw)/2, y), title_text, fill=(0, 0, 0), font=f_title)
        y += int(th_tit + 15 * scale)
        
        draw.text(((actual_canvas_w - pw)/2, y), tgl_str_res, fill=(80, 80, 80), font=f_sub)
        y += int(th_sub + 40 * scale)
        
        def draw_table_box(title_text, headers, rows_data, start_y, total_row, header_bg):
            curr_y = start_y
            draw.rectangle([table_x, curr_y, table_x + table_w, curr_y + row_h], fill=header_bg, outline=(0, 0, 0), width=2)
            draw.text((table_x + pad_x, curr_y + pad_y), title_text, fill=(0, 0, 0), font=f_bold)
            curr_y += row_h
            
            draw.rectangle([table_x, curr_y, table_x + table_w, curr_y + row_h], fill=(245, 245, 245), outline=(0, 0, 0), width=2)
            draw.line([table_x + col1_w, curr_y, table_x + col1_w, curr_y + row_h], fill=(0, 0, 0), width=2)
            draw.text((table_x + pad_x, curr_y + pad_y), headers[0], fill=(0, 0, 0), font=f_bold)
            draw.text((table_x + col1_w + pad_x, curr_y + pad_y), headers[1], fill=(0, 0, 0), font=f_bold)
            curr_y += row_h
            
            for r in rows_data:
                draw.rectangle([table_x, curr_y, table_x + table_w, curr_y + row_h], outline=(0, 0, 0), width=2)
                draw.line([table_x + col1_w, curr_y, table_x + col1_w, curr_y + row_h], fill=(0, 0, 0), width=2)
                draw.text((table_x + pad_x, curr_y + pad_y), str(r[0]), fill=(0, 0, 0), font=f_reg)
                draw.text((table_x + col1_w + pad_x, curr_y + pad_y), str(r[1]), fill=(0, 0, 0), font=f_reg)
                curr_y += row_h
                
            draw.rectangle([table_x, curr_y, table_x + table_w, curr_y + row_h], fill=header_bg, outline=(0, 0, 0), width=2)
            draw.line([table_x + col1_w, curr_y, table_x + col1_w, curr_y + row_h], fill=(0, 0, 0), width=2)
            draw.text((table_x + pad_x, curr_y + pad_y), str(total_row[0]), fill=(0, 0, 0), font=f_bold)
            draw.text((table_x + col1_w + pad_x, curr_y + pad_y), str(total_row[1]), fill=(0, 0, 0), font=f_bold)
            curr_y += row_h
            return curr_y + int(30 * scale)

        y = draw_table_box("1. RINCIAN GAJI KARYAWAN", ("NAMA KARYAWAN", "JUMLAH GAJI"), gaji_rows, y, ("TOTAL GAJI KARYAWAN", tot_gaji_fmt), (183, 222, 181))
        y = draw_table_box("2. PENGELUARAN LAINNYA", ("KETERANGAN", "JUMLAH"), lain_rows, y, ("TOTAL PENGELUARAN LAIN", tot_lain_fmt), (248, 203, 173))
        y = draw_table_box("3. RINGKASAN SALDO KAS", ("KETERANGAN", "NOMINAL"), ringkasan_rows, y, ("SISA SALDO KAS", sisa_fmt), (255, 235, 156))

        img_res = img_res.crop((0, 0, int(actual_canvas_w), int(y)))

        buf_r = io.BytesIO()
        img_res.save(buf_r, format="JPEG", quality=100)
        byte_resume_img = buf_r.getvalue()
        
        st.markdown("---")
        st.subheader("👁️ Preview Laporan Resume")
        st.image(byte_resume_img, width=400) 
        
        b64_res = base64.b64encode(byte_resume_img).decode()
        print_res_html = f"""
        <div style="text-align: left; margin-bottom: 5px;">
            <button onclick="printRes()" style="background-color: #FF4B4B; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; font-family: sans-serif; font-weight: bold;">🖨️ PRINT LAPORAN LANGSUNG</button>
        </div>
        <script>
        function printRes() {{
            var win = window.open('', '_blank');
            win.document.write('<html><head><title>Print Laporan Resume</title>');
            win.document.write('<style>@page {{ margin: 0mm; size: auto; }} body {{ margin: 0px; text-align: center; background-color: white; }}</style>');
            win.document.write('</head><body><img src="data:image/jpeg;base64,{b64_res}" style="width: 100%; max-width: 800px; display: block; margin: 0 auto;" onload="window.print(); window.close();" /></body></html>');
            win.document.close();
        }}
        </script>
        """
        components.html(print_res_html, height=50)

        st.download_button("📥 Unduh File JPG", data=byte_resume_img, file_name=f"Resume_Kas_{tgl_mulai_res.strftime('%d%m%Y')}.jpg", mime="image/jpeg")

# ==========================================
# MENU 6: PENGATURAN (KHUSUS MANUAL SAVE TANPA INDEX)
# ==========================================
with menu6:
    st.header("Pengaturan Master Data")
    col_karyawan, col_pekerjaan = st.columns(2)
    
    with col_karyawan:
        st.subheader("👥 Daftar Karyawan")
        st.caption("💡 Tambah/edit nama di tabel, lalu klik tombol **Simpan** di bawah.")
        
        notif_area_6k = st.empty()
        if "notif_6k" in st.session_state:
            notif_area_6k.success(st.session_state["notif_6k"])
            time.sleep(1.5)
            notif_area_6k.empty()
            del st.session_state["notif_6k"]

        df_kar_view = st.session_state.df_karyawan.copy().reset_index(drop=True)

        edited_kar_state = st.data_editor(
            df_kar_view, 
            num_rows="dynamic", 
            use_container_width=True,
            hide_index=True,
            key="editor_karyawan"
        )
        
        btn_simpan_kar = st.button("💾 Simpan Karyawan", type="primary", use_container_width=True)
        
        if btn_simpan_kar:
            edited_kar_state = edited_kar_state[edited_kar_state['Nama Karyawan'].astype(str).str.strip() != ""]
            st.session_state.df_karyawan = edited_kar_state
            ws["karyawan"].clear()
            ws["karyawan"].update([edited_kar_state.columns.values.tolist()] + edited_kar_state.fillna("").values.tolist())
            st.session_state["notif_6k"] = "✅ Daftar Karyawan Berhasil Disimpan Manual!"
            st.rerun()

    with col_pekerjaan:
        st.subheader("🛠️ Daftar Pekerjaan & Upah")
        st.caption("💡 Tambah/edit jenis dan upah, lalu klik tombol **Simpan** di bawah.")
        
        notif_area_6p = st.empty()
        if "notif_6p" in st.session_state:
            notif_area_6p.success(st.session_state["notif_6p"])
            time.sleep(1.5)
            notif_area_6p.empty()
            del st.session_state["notif_6p"]

        df_pek_view = st.session_state.df_pekerjaan.copy().reset_index(drop=True)
        if "Harga Per Pcs" in df_pek_view.columns: 
            df_pek_view = df_pek_view.rename(columns={"Harga Per Pcs": "Upah"})
        elif len(df_pek_view.columns) > 1 and df_pek_view.columns[1] != "Upah": 
            df_pek_view = df_pek_view.rename(columns={df_pek_view.columns[1]: "Upah"})
        df_pek_view['Upah'] = pd.to_numeric(df_pek_view['Upah'], errors='coerce').fillna(0)
        
        edited_pek_state = st.data_editor(
            df_pek_view, 
            num_rows="dynamic", 
            use_container_width=True,
            hide_index=True,
            column_config={"Upah": st.column_config.NumberColumn("Upah (Per Pcs)", format="Rp %,d")},
            key="editor_pekerjaan"
        )
        
        btn_simpan_pek = st.button("💾 Simpan Pekerjaan", type="primary", use_container_width=True)
        
        if btn_simpan_pek:
            edited_pek_state = edited_pek_state[edited_pek_state['Jenis Pekerjaan'].astype(str).str.strip() != ""]
            col_upah_target = edited_pek_state.columns[1] if len(edited_pek_state.columns) > 1 else 'Upah'
            edited_pek_state[col_upah_target] = pd.to_numeric(edited_pek_state[col_upah_target], errors='coerce').fillna(0)
            df_final_pek = pd.DataFrame({'Jenis Pekerjaan': edited_pek_state.iloc[:, 0], 'Upah': edited_pek_state[col_upah_target]})
            st.session_state.df_pekerjaan = df_final_pek
            ws["pekerjaan"].clear()
            ws["pekerjaan"].update([df_final_pek.columns.values.tolist()] + df_final_pek.fillna("").values.tolist())
            st.session_state["notif_6p"] = "✅ Daftar Pekerjaan & Upah Berhasil Disimpan Manual!"
            st.rerun()

    st.markdown("---")
    st.subheader("🔒 Keamanan")
    if st.button("🚪 Keluar Aplikasi (Logout)", type="secondary"):
        st.session_state.logged_in = False
        st.rerun()
