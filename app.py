import streamlit as st
import pandas as pd
import time
from datetime import datetime
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
# SUNTIKAN CSS: MENGHILANGKAN IKON RANTAI GLOBAL
# ==========================================
st.markdown("""
    <style>
    /* Menyembunyikan ikon rantai (anchor links) di semua judul Streamlit */
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Aplikasi Rekap Gaji Karyawan")

# ==========================================
# 1. KONEKSI GOOGLE SHEETS (POLA GUDANG - SUPER CEPAT)
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
    # Langsung menggunakan URL
    ss = client.open_by_url("https://docs.google.com/spreadsheets/d/1nSVOJTyA48REHwPvaWbvVXUupdh_GcrCHvBqbEA-xe8/edit")
    
    # Fungsi bantu untuk membuat tab otomatis jika belum ada di Google Sheets
    def get_or_create(name, cols):
        try:
            return ss.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            ws = ss.add_worksheet(title=name, rows="100", cols="20")
            ws.append_row(cols)
            return ws

    # Menyimpan objek worksheet langsung ke memori agar 0 detik loading
    return {
        "gaji": get_or_create("Data_Gaji", ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"]),
        "kasbon": get_or_create("Data_Kasbon_Bonus", ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"]),
        "pengeluaran": get_or_create("Data_Pengeluaran_Lain", ["ID Lain", "Keterangan", "Nominal"]),
        "karyawan": get_or_create("Master_Karyawan", ["Nama Karyawan"]),
        "pekerjaan": get_or_create("Master_Pekerjaan", ["Jenis Pekerjaan", "Harga Per Pcs"])
    }

# Panggil fungsi dan simpan worksheet ke variabel
ws = get_all_worksheets()

# ==========================================
# 2. SISTEM MEMORI LOKAL (MEMBACA DATA HANYA 1x)
# ==========================================
def load_data_to_memory():
    # Load Gaji
    data_gaji = ws["gaji"].get_all_records()
    df_gaji = pd.DataFrame(data_gaji) if data_gaji else pd.DataFrame(columns=["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
    if "Harga" in df_gaji.columns: df_gaji = df_gaji.rename(columns={"Harga": "Upah"})
    st.session_state.df_gaji = df_gaji
    
    # Load Kasbon & Pengeluaran
    data_kasbon = ws["kasbon"].get_all_records()
    st.session_state.df_kasbon = pd.DataFrame(data_kasbon) if data_kasbon else pd.DataFrame(columns=["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
    
    data_pengeluaran = ws["pengeluaran"].get_all_records()
    st.session_state.df_pengeluaran = pd.DataFrame(data_pengeluaran) if data_pengeluaran else pd.DataFrame(columns=["ID Lain", "Keterangan", "Nominal"])
    
    # Load Karyawan
    data_karyawan = ws["karyawan"].get_all_records()
    if not data_karyawan:
        df_kar = pd.DataFrame({"Nama Karyawan": ["Teh Eva", "Bi Nyai", "Radi", "Ula", "Sintia", "Mang Ade", "Mang Koko", "Yoga", "Samsul"]})
        ws["karyawan"].clear()
        ws["karyawan"].update([df_kar.columns.values.tolist()] + df_kar.values.tolist())
        st.session_state.df_karyawan = df_kar
    else:
        st.session_state.df_karyawan = pd.DataFrame(data_karyawan)
        
    # Load Pekerjaan
    data_pekerjaan = ws["pekerjaan"].get_all_records()
    if not data_pekerjaan:
        df_pek = pd.DataFrame({"Jenis Pekerjaan": ["Bungkus Patung", "Packing Styrofoam", "Bungkus Cat"], "Harga Per Pcs": [150, 400, 15]})
        ws["pekerjaan"].clear()
        ws["pekerjaan"].update([df_pek.columns.values.tolist()] + df_pek.values.tolist())
        st.session_state.df_pekerjaan = df_pek
    else:
        st.session_state.df_pekerjaan = pd.DataFrame(data_pekerjaan)

if "data_loaded" not in st.session_state:
    with st.spinner("Memuat Database dari Server... (Hanya 1x)"):
        load_data_to_memory()
        st.session_state.data_loaded = True

# Siapkan list untuk dropdown
daftar_karyawan = st.session_state.df_karyawan["Nama Karyawan"].dropna().tolist() if not st.session_state.df_karyawan.empty else []
daftar_pekerjaan = st.session_state.df_pekerjaan["Jenis Pekerjaan"].dropna().tolist() if not st.session_state.df_pekerjaan.empty else []
tarif_pekerjaan = dict(zip(st.session_state.df_pekerjaan["Jenis Pekerjaan"], pd.to_numeric(st.session_state.df_pekerjaan["Harga Per Pcs"], errors='coerce').fillna(0))) if not st.session_state.df_pekerjaan.empty else {}

# --- MENU NAVIGASI ---
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
    
    # Menampilkan Notifikasi Toast Pop-up
    if "notif_sukses_harian" in st.session_state:
        st.toast(st.session_state.notif_sukses_harian, icon="✅")
        del st.session_state.notif_sukses_harian

    # Memastikan nilai default memori tidak melebihi tanggal hari ini
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
                # Menggunakan parameter max_value=datetime.today() untuk mengunci tanggal masa depan
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
                
            submitted_input = st.form_submit_button("💾 Simpan Data Pekerjaan", type="primary", use_container_width=True)
            
            if submitted_input:
                jumlah = int(jumlah_str.strip()) if jumlah_str.strip().isdigit() else 0
                    
                if pekerjaan != "-" and jumlah > 0:
                    upah = tarif_pekerjaan[pekerjaan]
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
                        st.session_state.notif_sukses_harian = f"Tersimpan Kilat! {jml_fmt} {pekerjaan} untuk {nama}."
                        st.rerun() 
                    except Exception as e:
                        st.toast(f"Gagal simpan: {e}", icon="⚠️")
                else:
                    st.toast("Gagal! Mohon pilih pekerjaan dan ketik jumlah yang valid.", icon="⚠️")

# ==========================================
# MENU 2: DATABASE & EDIT PEKERJAAN
# ==========================================
with menu2:
    st.header("Database Riwayat Pekerjaan (Per Hari)")
    st.caption("💡 Edit angka di tabel ini 100% tanpa loading. Jangan lupa klik tombol 'Simpan Perubahan' di bawah tabel setelah selesai edit!")
    df_gaji = st.session_state.df_gaji
    
    if len(df_gaji) > 0:
        filter_nama = st.selectbox("🔍 Tampilkan data khusus untuk:", ["Semua Karyawan"] + daftar_karyawan, key="filter_db_kerja")
        df_tampil = df_gaji if filter_nama == "Semua Karyawan" else df_gaji[df_gaji['Nama'] == filter_nama]
            
        if len(df_tampil) > 0:
            df_tampil['Urutan_Hari'] = df_tampil['Hari'].map(URUTAN_HARI)
            df_tampil = df_tampil.sort_values(by=["Tanggal", "Urutan_Hari"]).drop(columns=["Urutan_Hari"])
            daftar_tanggal = df_tampil[['Tanggal', 'Hari']].drop_duplicates().values
            
            for tgl, hari in daftar_tanggal:
                with st.expander(f"📅 Hari **{hari}**, Tanggal **{tgl}**", expanded=True):
                    df_harian = df_tampil[(df_tampil['Tanggal'] == tgl) & (df_tampil['Hari'] == hari)].copy()
                    
                    with st.form(f"form_edit_harian_{tgl}_{hari}"):
                        df_harian_edit = st.data_editor(
                            df_harian, 
                            num_rows="dynamic", 
                            use_container_width=True, 
                            column_config={"ID Data": None},
                            hide_index=True, 
                            key=f"editor_{tgl}_{hari}"
                        )
                        
                        if st.form_submit_button(f"💾 Simpan Perubahan Tanggal {tgl}", type="primary"):
                            df_harian_edit['Upah'] = df_harian_edit['Upah'].astype(str).str.replace("Rp", "").str.replace(".", "").str.strip()
                            df_harian_edit['Upah'] = pd.to_numeric(df_harian_edit['Upah'], errors='coerce').fillna(0)
                            df_harian_edit['Jumlah'] = pd.to_numeric(df_harian_edit['Jumlah'], errors='coerce').fillna(0)
                            df_harian_edit['Total'] = df_harian_edit['Jumlah'] * df_harian_edit['Upah']
                            
                            for idx, row in df_harian_edit.iterrows():
                                if pd.isna(row["ID Data"]) or str(row["ID Data"]).strip() == "":
                                    df_harian_edit.at[idx, "ID Data"] = f"ID-{int(time.time())}-{idx}"
                            
                            df_sisa = st.session_state.df_gaji[~st.session_state.df_gaji['ID Data'].isin(df_harian['ID Data'])]
                            df_final = pd.concat([df_sisa, df_harian_edit]).sort_values(by="Tanggal").reset_index(drop=True)
                            
                            st.session_state.df_gaji = df_final
                            
                            ws["gaji"].clear()
                            ws["gaji"].update([df_final.columns.values.tolist()] + df_final.fillna("").values.tolist())
                            
                            st.toast("Perubahan Berhasil Disimpan!", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info(f"Tidak ada riwayat pekerjaan untuk {filter_nama}.")
    else:
        st.info("Belum ada data pekerjaan yang tersimpan.")

# ==========================================
# MENU 3: PENAMBAHAN & PENGURANGAN
# ==========================================
with menu3:
    st.header("Pencatatan Penambahan & Pengurangan")
    
    # Notifikasi Toast Pop-up
    if "notif_sukses_kb" in st.session_state:
        st.toast(st.session_state.notif_sukses_kb, icon="✅")
        del st.session_state.notif_sukses_kb

    today_date_kb = datetime.today().date()
    if "last_date_kb" not in st.session_state or st.session_state.last_date_kb > today_date_kb:
        st.session_state.last_date_kb = today_date_kb
        
    if "last_karyawan_kb" not in st.session_state:
        st.session_state.last_karyawan_kb = daftar_karyawan[0] if daftar_karyawan else ""

    if len(daftar_karyawan) > 0:
        with st.form("form_kasbon", clear_on_submit=True):
            col_kb1, col_kb2, col_kb3 = st.columns(3)
            with col_kb1:
                # Menggunakan parameter max_value=datetime.today()
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
                        
                        st.session_state.notif_sukses_kb = "Berhasil menyimpan data!"
                        st.rerun()
                    except Exception as e:
                        st.toast(f"Gagal: {e}", icon="⚠️")
                else:
                    st.toast("Mohon isi keterangan dan nominal dengan benar.", icon="⚠️")

# ==========================================
# MENU 4: CETAK SLIP GAJI
# ==========================================
with menu4:
    st.header("Cetak & Unduh Slip Gaji")
    df_gaji = st.session_state.df_gaji.copy()
    df_kasbon = st.session_state.df_kasbon.copy()
    
    if len(df_gaji) > 0 and len(daftar_karyawan) > 0:
        col_a, col_b = st.columns(2)
        with col_a:
            tgl_mulai = st.date_input("Dari Tanggal", datetime.today(), max_value=datetime.today(), format="DD/MM/YYYY", key="tgl_mulai_slip")
        with col_b:
            tgl_selesai = st.date_input("Sampai Tanggal", datetime.today(), max_value=datetime.today(), format="DD/MM/YYYY", key="tgl_selesai_slip")
            
        nama_slip_pilihan = st.selectbox("Pilih Nama Karyawan", ["Semua Karyawan"] + daftar_karyawan, key="slip_nama")
        
        if st.button("🖨️ Buat Slip Gaji (4K Ultra HD)", type="primary"):
            df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal']).dt.date
            target_karyawan = daftar_karyawan if nama_slip_pilihan == "Semua Karyawan" else [nama_slip_pilihan]
            
            for nama_slip in target_karyawan:
                df_filter_gaji = df_gaji[(df_gaji['Nama'] == nama_slip) & (df_gaji['Tanggal'] >= tgl_mulai) & (df_gaji['Tanggal'] <= tgl_selesai)]
                df_filter_kb = df_kasbon[(df_kasbon['Nama'] == nama_slip) & (pd.to_datetime(df_kasbon['Tanggal']).dt.date >= tgl_mulai) & (pd.to_datetime(df_kasbon['Tanggal']).dt.date <= tgl_selesai)] if len(df_kasbon) > 0 else pd.DataFrame()
                
                if len(df_filter_gaji) > 0 or len(df_filter_kb) > 0:
                    baris_gambar_info = [
                        ("       SLIP GAJI", True),
                        ("================================", False),
                        (f"Nama    : {nama_slip}", True),
                        (f"Periode : {tgl_mulai.strftime('%d/%m/%Y')} - {tgl_selesai.strftime('%d/%m/%Y')}", True),
                        ("================================", False),
                        ("", False)
                    ]
                    total_upah = 0
                    for tgl, data_harian in df_filter_gaji.groupby('Tanggal'):
                        baris_gambar_info.append((f"Hari/Tgl: {HARI_INDO.get(tgl.strftime('%A'), '')}, {tgl.strftime('%d/%m/%Y')}", True))
                        sub = 0
                        for _, row in data_harian.iterrows():
                            j, u, t = float(row['Jumlah']), float(row['Upah']), float(row['Total'])
                            baris_gambar_info.append((f"- {row['Pekerjaan']}", False))
                            baris_gambar_info.append((f"  {j:,.0f} pcs x Rp{u:,.0f} = Rp{t:,.0f}".replace(",", "."), False))
                            sub += t
                        baris_gambar_info.append((f"Sub-total: Rp{sub:,.0f}".replace(",", "."), False))
                        baris_gambar_info.append(("", False))
                        total_upah += sub
                    
                    tot_tambah, tot_kurang = 0, 0
                    if len(df_filter_kb) > 0:
                        baris_gambar_info.append(("--- CATATAN TAMBAHAN ---", True))
                        for _, rkb in df_filter_kb.iterrows():
                            nom = float(rkb['Nominal'])
                            sign = "+" if rkb['Tipe'] == "Penambahan" else "-"
                            baris_gambar_info.append((f"{sign} {rkb['Keterangan']} (Rp {nom:,.0f})".replace(",", "."), False))
                            if rkb['Tipe'] == "Penambahan": tot_tambah += nom
                            else: tot_kurang += nom
                        baris_gambar_info.append(("", False))
                    
                    total_bersih = total_upah + tot_tambah - tot_kurang
                    baris_gambar_info.append(("================================", False))
                    baris_gambar_info.append((f"TOTAL GAJI DITERIMA: Rp {total_bersih:,.0f}".replace(",", "."), True))
                    baris_gambar_info.append(("================================", False))
                    
                    scale = 4
                    img = Image.new('RGB', (420 * scale, ((len(baris_gambar_info) * 20) + 40) * scale), color=(255, 255, 255))
                    draw = ImageDraw.Draw(img)
                    font = ImageFont.load_default()
                    
                    y = 20 * scale
                    for txt, is_b in baris_gambar_info:
                        draw.text((20 * scale, y), txt, font=font, fill=(0, 0, 0))
                        y += 20 * scale
                    
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    byte_im = buf.getvalue()
                    
                    st.subheader(f"📄 Slip Gaji: {nama_slip}")
                    st.image(byte_im, width=400)
                    st.download_button(f"📥 Unduh Slip - {nama_slip}", data=byte_im, file_name=f"Slip_{nama_slip}.jpg", mime="image/jpeg", key=f"dl_{nama_slip}")

# ==========================================
# MENU 5: LAPORAN RESUME KAS
# ==========================================
with menu5:
    st.header("📊 Laporan Resume Kas")
    
    df_gaji = st.session_state.df_gaji.copy()
    df_kasbon = st.session_state.df_kasbon.copy()
    df_lain_all = st.session_state.df_pengeluaran.copy()
    
    col_r1, col_r2 = st.columns(2)
    with col_r1: tgl_mulai_res = st.date_input("Dari Tanggal", datetime.today(), max_value=datetime.today(), format="DD/MM/YYYY", key="res_mulai")
    with col_r2: tgl_selesai_res = st.date_input("Sampai Tanggal", datetime.today(), max_value=datetime.today(), format="DD/MM/YYYY", key="res_selesai")
    
    tarik_uang_str = st.text_input("💵 Total Penarikan Uang Cash (Rp)", placeholder="Ketik nominal...")
    
    st.markdown("---")
    st.subheader("🛒 Pencatatan Pengeluaran Lain-Lain")
    
    with st.form("form_pengeluaran_lain", clear_on_submit=True):
        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            ket_lain = st.text_input("Keterangan Pengeluaran")
        with col_l2:
            nominal_lain_str = st.text_input("Nominal (Rp)", placeholder="Ketik nominal...")
            
        submitted_lain = st.form_submit_button("➕ Tambah Pengeluaran Lain", type="primary", use_container_width=True)
        if submitted_lain:
            nominal_lain = int(nominal_lain_str.strip()) if nominal_lain_str.strip().isdigit() else 0
                
            if nominal_lain > 0 and ket_lain.strip() != "":
                try:
                    id_lain = f"LAIN-{int(time.time())}"
                    baris_lain = pd.DataFrame([{"ID Lain": id_lain, "Keterangan": ket_lain, "Nominal": nominal_lain}])
                    st.session_state.df_pengeluaran = pd.concat([st.session_state.df_pengeluaran, baris_lain], ignore_index=True)
                    
                    ws["pengeluaran"].append_row([id_lain, ket_lain, nominal_lain])
                    st.toast(f"Berhasil menambahkan '{ket_lain}'!", icon="✅")
                except Exception as e:
                    st.toast(f"Gagal menyimpan: {e}", icon="⚠️")
            else:
                st.toast("Mohon isi dengan benar.", icon="⚠️")

    if st.button("🖼️ Generate Gambar Resume", type="primary"):
        tarik_uang = int(tarik_uang_str.strip()) if tarik_uang_str.strip().isdigit() else 0
            
        df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal']).dt.date
        df_f_gaji = df_gaji[(df_gaji['Tanggal'] >= tgl_mulai_res) & (df_gaji['Tanggal'] <= tgl_selesai_res)]
        
        if len(df_kasbon) > 0:
            df_kasbon['Tanggal'] = pd.to_datetime(df_kasbon['Tanggal']).dt.date
            df_f_kb = df_kasbon[(df_kasbon['Tanggal'] >= tgl_mulai_res) & (df_kasbon['Tanggal'] <= tgl_selesai_res)]
        else:
            df_f_kb = pd.DataFrame()
            
        rekap_gaji = {k: 0 for k in daftar_karyawan}
        
        if len(df_f_gaji) > 0:
            for nama, df_n in df_f_gaji.groupby('Nama'):
                if nama in rekap_gaji:
                    rekap_gaji[nama] += pd.to_numeric(df_n['Total'], errors='coerce').fillna(0).sum()
                
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
        
        scale = 4
        w, h = 460 * scale, (350 + (len(daftar_karyawan) * 24) + (len(df_lain_all) * 24)) * scale
        img = Image.new('RGB', (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        
        y = 20 * scale
        draw.text((20 * scale, y), "LAPORAN RESUME KAS & GAJI", fill=(0, 0, 0), font=font)
        y += 22 * scale
        draw.text((20 * scale, y), f"Periode: {tgl_mulai_res.strftime('%d/%m/%Y')} - {tgl_selesai_res.strftime('%d/%m/%Y')}", fill=(80, 80, 80), font=font)
        y += 35 * scale
        
        draw.text((20 * scale, y), "A. RINCIAN GAJI KARYAWAN", fill=(0, 0, 0), font=font)
        y += 25 * scale
        
        for k in daftar_karyawan:
            val = rekap_gaji.get(k, 0)
            draw.text((20 * scale, y), f"- {k}: Rp {val:,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
            y += 24 * scale
            
        draw.text((20 * scale, y), f"TOTAL GAJI KARYAWAN: Rp {total_gaji_semua:,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
        y += 40 * scale
        
        draw.text((20 * scale, y), "B. PENGELUARAN LAIN-LAIN", fill=(0, 0, 0), font=font)
        y += 25 * scale
        
        if len(df_lain_all) > 0:
            for _, r in df_lain_all.iterrows():
                draw.text((20 * scale, y), f"- {r['Keterangan']}: Rp {float(r['Nominal']):,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
                y += 24 * scale
        else:
            draw.text((20 * scale, y), "(Tidak ada pengeluaran lain)", fill=(120, 120, 120), font=font)
            y += 24 * scale
            
        draw.text((20 * scale, y), f"TOTAL PENGELUARAN LAIN: Rp {total_pengeluaran_lain:,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
        y += 40 * scale
        
        draw.text((20 * scale, y), "C. RINGKASAN KAS", fill=(0, 0, 0), font=font)
        y += 25 * scale
        draw.text((20 * scale, y), f"Total Penarikan Cash: Rp {tarik_uang:,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
        y += 24 * scale
        draw.text((20 * scale, y), f"Total Pengeluaran Keseluruhan: Rp {total_pengeluaran_keseluruhan:,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
        y += 24 * scale
        draw.text((20 * scale, y), f"SISA SALDO KAS: Rp {sisa_uang:,.0f}".replace(",", "."), fill=(0, 0, 0), font=font)
            
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        byte_resume = buf.getvalue()
        
        st.markdown("---")
        st.subheader("👁️ Ringkasan Akhir")
        st.image(byte_resume, width=460)
        st.download_button("📥 Unduh Resume", data=byte_resume, file_name=f"Resume_{tgl_mulai_res.strftime('%d%m%Y')}.jpg", mime="image/jpeg")

# ==========================================
# MENU 6: PENGATURAN (SISTEM TABEL INSTAN ANTI-LOADING)
# ==========================================
with menu6:
    st.header("Pengaturan Master Data")
    
    col_karyawan, col_pekerjaan = st.columns(2)
    
    with col_karyawan:
        st.subheader("👥 Daftar Karyawan")
        st.caption("💡 **Cara Menambah:** Klik kotak kosong di bawah lalu ketik.\n\n💡 **Cara Menghapus:** Klik kotak kecil di ujung kiri tabel, lalu tekan tombol **Delete/Backspace** di keyboard.")
        
        with st.form("form_tabel_karyawan"):
            edited_karyawan = st.data_editor(
                st.session_state.df_karyawan, 
                num_rows="dynamic", 
                use_container_width=True,
                hide_index=True # Menghilangkan kolom nomor urut (0, 1, 2...)
            )
            
            if st.form_submit_button("💾 Simpan Perubahan Karyawan", type="primary", use_container_width=True):
                edited_karyawan = edited_karyawan[edited_karyawan['Nama Karyawan'].str.strip() != ""]
                st.session_state.df_karyawan = edited_karyawan
                
                # Bulk Update langsung ke tab worksheet
                ws["karyawan"].clear()
                ws["karyawan"].update([edited_karyawan.columns.values.tolist()] + edited_karyawan.fillna("").values.tolist())
                
                st.toast("Berhasil Disimpan!", icon="✅")
                time.sleep(0.5)
                st.rerun()

    with col_pekerjaan:
        st.subheader("🛠️ Daftar Pekerjaan & Harga")
        st.caption("💡 Klik sel paling bawah untuk menambah, atau centang kotak di ujung kiri + tombol **Delete** untuk menghapus.")
        
        with st.form("form_tabel_pekerjaan"):
            edited_pekerjaan = st.data_editor(
                st.session_state.df_pekerjaan, 
                num_rows="dynamic", 
                use_container_width=True,
                hide_index=True # Menghilangkan kolom nomor urut (0, 1, 2...)
            )
            
            if st.form_submit_button("💾 Simpan Perubahan Pekerjaan", type="primary", use_container_width=True):
                edited_pekerjaan = edited_pekerjaan[edited_pekerjaan['Jenis Pekerjaan'].str.strip() != ""]
                st.session_state.df_pekerjaan = edited_pekerjaan
                
                ws["pekerjaan"].clear()
                ws["pekerjaan"].update([edited_pekerjaan.columns.values.tolist()] + edited_pekerjaan.fillna("").values.tolist())
                
                st.toast("Berhasil Disimpan!", icon="✅")
                time.sleep(0.5)
                st.rerun()
