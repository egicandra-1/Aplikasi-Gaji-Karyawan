import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta, date
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

st.set_page_config(page_title="Sistem Penggajian", layout="wide", page_icon="📝")

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

# =
