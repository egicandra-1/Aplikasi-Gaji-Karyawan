import streamlit as st
import pandas as pd
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- KAMUS HARI BAHASA INDONESIA ---
HARI_INDO = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
}

URUTAN_HARI = {"Senin": 1, "Selasa": 2, "Rabu": 3, "Kamis": 4, "Jumat": 5, "Sabtu": 6, "Minggu": 7}

# Mengatur tampilan halaman
st.set_page_config(page_title="Sistem Penggajian", layout="wide", page_icon="📝")
st.title("Aplikasi Rekap Gaji Karyawan")

# --- KONEKSI KE GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    except:
        import json
        dict_creds = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict_creds, scope)
    
    client = gspread.authorize(creds)
    return client

client = init_connection()
spreadsheet = client.open("Database_Aplikasi_Gaji")

# --- FUNGSI BANTU GOOGLE SHEETS (DENGAN CACHE CEPAT) ---
@st.cache_data(ttl=600)
def load_data_from_sheet(nama_sheet, kolom_default):
    try:
        worksheet = spreadsheet.worksheet(nama_sheet)
        data = worksheet.get_all_records()
        if len(data) > 0:
            df = pd.DataFrame(data)
            for col in kolom_default:
                if col not in df.columns:
                    df[col] = ""
            return df
        else:
            return pd.DataFrame(columns=kolom_default)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=nama_sheet, rows="100", cols="20")
        df_kosong = pd.DataFrame(columns=kolom_default)
        worksheet.update([df_kosong.columns.values.tolist()] + df_kosong.values.tolist())
        return df_kosong

def save_data_to_sheet(nama_sheet, df):
    try:
        worksheet = spreadsheet.worksheet(nama_sheet)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=nama_sheet, rows="100", cols="20")
    
    worksheet.clear()
    data_to_write = [df.columns.values.tolist()] + df.fillna("").values.tolist()
    worksheet.update(data_to_write)
    load_data_from_sheet.clear()

# --- NAMA TAB SHEET GOOGLE SHEETS ---
SHEET_GAJI = "Data_Gaji"
SHEET_KASBON = "Data_Kasbon_Bonus"
SHEET_PENGELUARAN = "Data_Pengeluaran_Lain"
SHEET_KARYAWAN = "Master_Karyawan"
SHEET_PEKERJAAN = "Master_Pekerjaan"

# --- INISIALISASI & MIGRASI DATA SHEET (HANYA 1X SAAT PERTAMA DIBUKA) ---
if "db_initialized" not in st.session_state:
    df_gaji_cek = load_data_from_sheet(SHEET_GAJI, ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
    if "Harga" in df_gaji_cek.columns:
        df_gaji_cek = df_gaji_cek.rename(columns={"Harga": "Upah"})
    if "Hari" not in df_gaji_cek.columns and len(df_gaji_cek) > 0:
        df_gaji_cek["Hari"] = pd.to_datetime(df_gaji_cek["Tanggal"]).dt.strftime('%A').map(HARI_INDO)
    save_data_to_sheet(SHEET_GAJI, df_gaji_cek)

    load_data_from_sheet(SHEET_KASBON, ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
    load_data_from_sheet(SHEET_PENGELUARAN, ["ID Lain", "Keterangan", "Nominal"])

    df_kar_cek = load_data_from_sheet(SHEET_KARYAWAN, ["Nama Karyawan"])
    if len(df_kar_cek) == 0:
        df_kar_cek = pd.DataFrame({"Nama Karyawan": ["Teh Eva", "Bi Nyai", "Radi", "Ula", "Sintia", "Mang Ade", "Mang Koko", "Yoga", "Samsul"]})
        save_data_to_sheet(SHEET_KARYAWAN, df_kar_cek)

    df_pek_cek = load_data_from_sheet(SHEET_PEKERJAAN, ["Jenis Pekerjaan", "Harga Per Pcs"])
    if len(df_pek_cek) == 0:
        df_pek_cek = pd.DataFrame({
            "Jenis Pekerjaan": ["Bungkus Patung", "Packing Styrofoam", "Bungkus Cat"],
            "Harga Per Pcs": [150, 400, 15]
        })
        save_data_to_sheet(SHEET_PEKERJAAN, df_pek_cek)
        
    st.session_state.db_initialized = True

# --- MEMBACA MASTER DATA ---
df_karyawan = load_data_from_sheet(SHEET_KARYAWAN, ["Nama Karyawan"])
df_pekerjaan = load_data_from_sheet(SHEET_PEKERJAAN, ["Jenis Pekerjaan", "Harga Per Pcs"])
daftar_karyawan = df_karyawan["Nama Karyawan"].dropna().tolist()
daftar_pekerjaan = df_pekerjaan["Jenis Pekerjaan"].dropna().tolist()
tarif_pekerjaan = dict(zip(df_pekerjaan["Jenis Pekerjaan"], pd.to_numeric(df_pekerjaan["Harga Per Pcs"], errors='coerce').fillna(0)))

# --- INISIALISASI SESSION STATE ---
if "pesan_notif" not in st.session_state:
    st.session_state.pesan_notif = ""
if "pesan_tipe" not in st.session_state:
    st.session_state.pesan_tipe = ""

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
# MENU 1: INPUT HARIAN (MENGGUNAKAN FORM & TOMBOL SIMPAN / ENTER)
# ==========================================
with menu1:
    st.header("Input Pekerjaan Harian")
    
    if len(daftar_karyawan) == 0 or len(daftar_pekerjaan) == 0:
        st.warning("⚠️ Data Karyawan atau Pekerjaan kosong. Silakan isi terlebih dahulu di Menu 6.")
    else:
        with st.form("form_input_harian", clear_on_submit=True):
            col_tgl, col_nama = st.columns(2)
            with col_tgl:
                tanggal = st.date_input("Pilih Tanggal", datetime.today(), format="DD/MM/YYYY")
                nama_hari = HARI_INDO[tanggal.strftime("%A")]
                st.write(f"📅 Hari terpilih: **{nama_hari}**")
                
            with col_nama:
                nama = st.selectbox("Pilih Karyawan", daftar_karyawan)
                st.write(f"👤 Karyawan: **{nama}**")

            st.markdown("---")
            st.markdown("### ⚡ Panel Input Harian")
            st.caption("Pilih pekerjaan, ketik jumlahnya, lalu **tekan Enter** pada keyboard atau klik tombol Simpan.")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                opsi_kerja = ["-"] + daftar_pekerjaan
                pekerjaan = st.selectbox("Pilih Pekerjaan", opsi_kerja)
            with col2:
                jumlah = st.number_input("Jumlah (Pcs)", min_value=0, step=1, value=None, placeholder="Ketik jumlah pcs...")
                
            submitted_input = st.form_submit_button("💾 Simpan Data Pekerjaan", type="primary", use_container_width=True)
            
            if submitted_input:
                if pekerjaan != "-" and jumlah is not None and jumlah > 0:
                    upah = tarif_pekerjaan[pekerjaan]
                    total = jumlah * upah
                    
                    try:
                        worksheet = spreadsheet.worksheet(SHEET_GAJI)
                        id_data = f"ID-{int(time.time())}"
                        tgl_str = tanggal.strftime("%Y-%m-%d")
                        worksheet.append_row([id_data, nama_hari, tgl_str, nama, pekerjaan, upah, jumlah, total])
                        load_data_from_sheet.clear()
                        
                        jml_fmt = f"{jumlah:,.0f}".replace(",", ".")
                        st.success(f"✅ Berhasil menyimpan! {jml_fmt} {pekerjaan} untuk {nama}.")
                    except Exception as e:
                        st.error(f"⚠️ Gagal menyimpan ke server: {e}")
                elif (jumlah is not None and jumlah > 0) and pekerjaan == "-":
                    st.error("⚠️ Gagal simpan! Anda belum memilih Jenis Pekerjaan.")
                else:
                    st.error("⚠️ Gagal simpan! Mohon pilih pekerjaan dan isi jumlah dengan benar.")

# ==========================================
# MENU 2: DATABASE & EDIT PEKERJAAN
# ==========================================
with menu2:
    st.header("Database Riwayat Pekerjaan (Per Hari)")
    df_gaji = load_data_from_sheet(SHEET_GAJI, ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
    if "Harga" in df_gaji.columns:
        df_gaji = df_gaji.rename(columns={"Harga": "Upah"})
    
    if len(df_gaji) > 0:
        filter_nama = st.selectbox("🔍 Tampilkan data khusus untuk:", ["Semua Karyawan"] + daftar_karyawan, key="filter_db_kerja")
        
        if filter_nama == "Semua Karyawan":
            df_tampil = df_gaji
        else:
            df_tampil = df_gaji[df_gaji['Nama'] == filter_nama]
            
        if len(df_tampil) > 0:
            df_tampil['Urutan_Hari'] = df_tampil['Hari'].map(URUTAN_HARI)
            df_tampil = df_tampil.sort_values(by=["Tanggal", "Urutan_Hari"]).drop(columns=["Urutan_Hari"])
            
            daftar_tanggal = df_tampil[['Tanggal', 'Hari']].drop_duplicates().values
            
            st.caption("💡 Tips: Klik dua kali pada kolom yang ingin diubah. Pilih baris lalu tekan 'Delete' di keyboard untuk menghapus. Data **TERSAVE OTOMATIS**.")
            
            for tgl, hari in daftar_tanggal:
                with st.expander(f"📅 Hari **{hari}**, Tanggal **{tgl}**", expanded=True):
                    df_harian = df_tampil[(df_tampil['Tanggal'] == tgl) & (df_tampil['Hari'] == hari)]
                    
                    kolom_tampil = ["Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"]
                    df_tabel_bersih = df_harian[kolom_tampil].copy()
                    
                    df_tabel_bersih['Upah'] = pd.to_numeric(df_tabel_bersih['Upah'], errors='coerce').fillna(0).apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
                    df_tabel_bersih['Total'] = pd.to_numeric(df_tabel_bersih['Total'], errors='coerce').fillna(0).apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
                    
                    df_harian_edit = st.data_editor(df_tabel_bersih, num_rows="dynamic", use_container_width=True, key=f"edit_{tgl}_{hari}")
                    
                    if not df_tabel_bersih.equals(df_harian_edit):
                        df_harian_edit['Upah'] = df_harian_edit['Upah'].astype(str).str.replace("Rp", "").str.replace(".", "").str.strip()
                        df_harian_edit['Upah'] = pd.to_numeric(df_harian_edit['Upah'], errors='coerce').fillna(0)
                        df_harian_edit['Jumlah'] = pd.to_numeric(df_harian_edit['Jumlah'], errors='coerce').fillna(0)
                        df_harian_edit['Total'] = df_harian_edit['Jumlah'] * df_harian_edit['Upah']
                        
                        df_harian_edit['ID Data'] = df_harian['ID Data'].values[:len(df_harian_edit)]
                        
                        df_sisa = df_gaji[~df_gaji['ID Data'].isin(df_harian['ID Data'])]
                        df_final = pd.concat([df_sisa, df_harian_edit]).sort_values(by="Tanggal").reset_index(drop=True)
                        save_data_to_sheet(SHEET_GAJI, df_final)
                        st.toast(f"Perubahan untuk tanggal {tgl} tersimpan otomatis! 💾", icon="✅")
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
    st.caption("Gunakan menu ini untuk mencatat transaksi tambahan (penambah) atau potongan (pengurang) di luar upah harian.")
    
    if len(daftar_karyawan) == 0:
        st.warning("⚠️ Data Karyawan kosong. Silakan isi terlebih dahulu di Menu 6.")
    else:
        with st.form("form_kasbon", clear_on_submit=True):
            col_kb1, col_kb2, col_kb3 = st.columns(3)
            with col_kb1:
                tgl_kb = st.date_input("Tanggal Transaksi", datetime.today(), format="DD/MM/YYYY")
            with col_kb2:
                nama_kb = st.selectbox("Pilih Karyawan", daftar_karyawan)
            with col_kb3:
                tipe_kb = st.selectbox("Jenis Transaksi", ["Penambahan", "Pengurangan"])
                
            col_kb4, col_kb5 = st.columns([2, 1])
            with col_kb4:
                ket_kb = st.text_input("Keterangan (Contoh: Lembur / Kasbon beras)")
            with col_kb5:
                nominal_kb = st.number_input("Nominal (Rp)", min_value=0, step=5000, value=None, placeholder="Ketik nominal...")
                
            submitted_kb = st.form_submit_button("💾 Simpan Data", type="primary", use_container_width=True)
            if submitted_kb:
                if nominal_kb is not None and nominal_kb > 0 and ket_kb.strip() != "":
                    try:
                        worksheet = spreadsheet.worksheet(SHEET_KASBON)
                        id_kb = f"KB-{int(time.time())}"
                        tgl_str = tgl_kb.strftime("%Y-%m-%d")
                        worksheet.append_row([id_kb, tgl_str, nama_kb, tipe_kb, ket_kb, nominal_kb])
                        load_data_from_sheet.clear()
                        
                        st.success(f"✅ Berhasil menyimpan {tipe_kb} untuk {nama_kb} sebesar Rp {nominal_kb:,.0f}!".replace(",", "."))
                    except Exception as e:
                        st.error(f"⚠️ Gagal simpan ke server: {e}")
                else:
                    st.error("⚠️ Gagal simpan! Mohon isi keterangan dan nominal dengan benar (harus lebih dari 0).")

        st.markdown("---")
        st.subheader("📋 Riwayat Penambahan & Pengurangan (Auto-Save)")
        df_kasbon_all = load_data_from_sheet(SHEET_KASBON, ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
        if len(df_kasbon_all) > 0:
            filter_nama_kb = st.selectbox("🔍 Filter riwayat berdasarkan karyawan:", ["Semua Karyawan"] + daftar_karyawan, key="filter_kb")
            if filter_nama_kb == "Semua Karyawan":
                df_kb_tampil = df_kasbon_all
            else:
                df_kb_tampil = df_kasbon_all[df_kasbon_all['Nama'] == filter_nama_kb]
                
            if len(df_kb_tampil) > 0:
                df_kb_tampil_fmt = df_kb_tampil.copy()
                df_kb_tampil_fmt['Nominal'] = pd.to_numeric(df_kb_tampil_fmt['Nominal'], errors='coerce').fillna(0).apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
                
                df_kb_edit = st.data_editor(df_kb_tampil_fmt, num_rows="dynamic", use_container_width=True, key="edit_tabel_kb")
                
                if not df_kb_tampil_fmt.equals(df_kb_edit):
                    df_kb_edit['Nominal'] = df_kb_edit['Nominal'].astype(str).str.replace("Rp", "").str.replace(".", "").str.strip()
                    df_kb_edit['Nominal'] = pd.to_numeric(df_kb_edit['Nominal'], errors='coerce').fillna(0)
                    
                    df_kb_sisa = df_kasbon_all[~df_kasbon_all['ID Kasbon'].isin(df_kb_tampil['ID Kasbon'])]
                    df_kb_final = pd.concat([df_kb_sisa, df_kb_edit]).sort_values(by="Tanggal").reset_index(drop=True)
                    save_data_to_sheet(SHEET_KASBON, df_kb_final)
                    st.toast("Perubahan data tersimpan otomatis! 💾", icon="✅")
                    st.rerun()
            else:
                st.info("Tidak ada riwayat transaksi untuk karyawan ini.")
        else:
            st.info("Belum ada data penambahan atau pengurangan yang tercatat.")

# ==========================================
# MENU 4: CETAK SLIP GAJI
# ==========================================
with menu4:
    st.header("Cetak & Unduh Slip Gaji")
    df_gaji = load_data_from_sheet(SHEET_GAJI, ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
    if "Harga" in df_gaji.columns:
        df_gaji = df_gaji.rename(columns={"Harga": "Upah"})
    df_kasbon = load_data_from_sheet(SHEET_KASBON, ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
    
    if len(df_gaji) > 0 and len(daftar_karyawan) > 0:
        col_a, col_b = st.columns(2)
        with col_a:
            tgl_mulai = st.date_input("Dari Tanggal", datetime.today(), format="DD/MM/YYYY", key="tgl_mulai_slip")
        with col_b:
            tgl_selesai = st.date_input("Sampai Tanggal", datetime.today(), format="DD/MM/YYYY", key="tgl_selesai_slip")
            
        opsi_pilih_slip = ["Semua Karyawan"] + daftar_karyawan
        nama_slip_pilihan = st.selectbox("Pilih Nama Karyawan", opsi_pilih_slip, key="slip_nama")
        
        if st.button("🖨️ Buat Slip Gaji (4K Ultra HD)", type="primary"):
            df_gaji['Tanggal'] = pd.to_datetime(df_gaji['Tanggal']).dt.date
            
            if nama_slip_pilihan == "Semua Karyawan":
                target_karyawan = daftar_karyawan
            else:
                target_karyawan = [nama_slip_pilihan]
                
            berhasil_cetak_count = 0
            
            for nama_slip in target_karyawan:
                df_filter_gaji = df_gaji[(df_gaji['Nama'] == nama_slip) & (df_gaji['Tanggal'] >= tgl_mulai) & (df_gaji['Tanggal'] <= tgl_selesai)]
                
                if len(df_kasbon) > 0:
                    df_kasbon['Tanggal'] = pd.to_datetime(df_kasbon['Tanggal']).dt.date
                    df_filter_kb = df_kasbon[(df_kasbon['Nama'] == nama_slip) & (df_kasbon['Tanggal'] >= tgl_mulai) & (df_kasbon['Tanggal'] <= tgl_selesai)]
                else:
                    df_filter_kb = pd.DataFrame()
                
                if len(df_filter_gaji) > 0 or len(df_filter_kb) > 0:
                    berhasil_cetak_count += 1
                    baris_gambar_info = []
                    
                    baris_gambar_info.append(("       SLIP GAJI", True))
                    baris_gambar_info.append(("================================", False))
                    baris_gambar_info.append((f"Nama    : {nama_slip}", True))
                    baris_gambar_info.append((f"Periode : {tgl_mulai.strftime('%d/%m/%Y')} - {tgl_selesai.strftime('%d/%m/%Y')}", True))
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
                                jml_val = float(row['Jumlah']) if pd.notnull(row['Jumlah']) else 0
                                upah_val = float(row['Upah']) if pd.notnull(row['Upah']) else 0
                                tot_val = float(row['Total']) if pd.notnull(row['Total']) else (jml_val * upah_val)
                                
                                jml_format = f"{jml_val:,.0f}".replace(",", ".")
                                upah_format = f"{upah_val:,.0f}".replace(",", ".")
                                total_format = f"{tot_val:,.0f}".replace(",", ".")
                                
                                baris_gambar_info.append((f"- {row['Pekerjaan']}", False))
                                baris_gambar_info.append((f"  {jml_format} pcs x Rp{upah_format} = Rp{total_format}", False))
                                subtotal += tot_val
                            
                            subtotal_format = f"{subtotal:,.0f}".replace(",", ".")
                            baris_gambar_info.append((f"Sub-total: Rp{subtotal_format}", False))
                            baris_gambar_info.append(("", False))
                            total_pendapatan_upah += subtotal
                    
                    total_tambah = 0
                    total_kurang = 0
                    
                    if len(df_filter_kb) > 0:
                        baris_gambar_info.append(("--- CATATAN TAMBAHAN ---", True))
                        for _, row_kb in df_filter_kb.iterrows():
                            nom_kb = float(row_kb['Nominal']) if pd.notnull(row_kb['Nominal']) else 0
                            nominal_fmt = f"Rp {nom_kb:,.0f}".replace(",", ".")
                            if row_kb['Tipe'] == "Penambahan":
                                baris_gambar_info.append((f"+ {row_kb['Keterangan']}", False))
                                baris_gambar_info.append((f"  ({nominal_fmt})", False))
                                total_tambah += nom_kb
                            else:
                                baris_gambar_info.append((f"- {row_kb['Keterangan']}", False))
                                baris_gambar_info.append((f"  ({nominal_fmt})", False))
                                total_kurang += nom_kb
                        baris_gambar_info.append(("", False))
                    
                    total_gaji_bersih = total_pendapatan_upah + total_tambah - total_kurang
                    total_semua_format = f"{total_gaji_bersih:,.0f}".replace(",", ".")
                    
                    baris_gambar_info.append(("================================", False))
                    total_str = f"TOTAL GAJI DITERIMA: Rp {total_semua_format}"
                    baris_gambar_info.append((total_str, True))
                    baris_gambar_info.append(("================================", False))

                    scale = 4
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
                    
                    caption_teks = f"Slip Gaji {nama_slip}\nPeriode: {tgl_mulai.strftime('%d/%m/%Y')} - {tgl_selesai.strftime('%d/%m/%Y')}\nTotal Diterima: Rp {total_semua_format}"
                    st.text_area("📋 Salin Caption Singkat:", value=caption_teks, height=80, key=f"caption_{nama_slip}_{time.time()}")
                    
                    st.download_button(
                        label=f"📥 Unduh Foto Slip - {nama_slip} (Format 4K JPG)",
                        data=byte_im,
                        file_name=f"Slip_Gaji_4K_{nama_slip}_{tgl_selesai.strftime('%d%m%Y')}.jpg",
                        mime="image/jpeg",
                        key=f"dl_slip_{nama_slip}_{time.time()}"
                    )
            
            if berhasil_cetak_count == 0:
                st.warning("⚠️ Tidak ada data pekerjaan atau catatan untuk karyawan pada periode tersebut.")
    else:
        st.info("Belum ada data yang bisa dicetak.")

# ==========================================
# MENU 5: LAPORAN RESUME KAS
# ==========================================
with menu5:
    st.header("📊 Laporan Resume Kas Mingguan/Periode")
    st.caption("Masukkan periode tanggal, catat pengeluaran lain-lain, dan masukkan total uang cash yang ditarik untuk melihat sisa uang.")
    
    df_gaji = load_data_from_sheet(SHEET_GAJI, ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
    if "Harga" in df_gaji.columns:
        df_gaji = df_gaji.rename(columns={"Harga": "Upah"})
    df_kasbon = load_data_from_sheet(SHEET_KASBON, ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
    df_lain_all = load_data_from_sheet(SHEET_PENGELUARAN, ["ID Lain", "Keterangan", "Nominal"])
    
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
                try:
                    worksheet = spreadsheet.worksheet(SHEET_PENGELUARAN)
                    id_lain = f"LAIN-{int(time.time())}"
                    worksheet.append_row([id_lain, ket_lain, nominal_lain])
                    load_data_from_sheet.clear()
                    
                    st.success(f"Berhasil menambahkan '{ket_lain}' sebesar Rp {nominal_lain:,.0f}!".replace(",", "."))
                except Exception as e:
                    st.warning(f"⚠️ Gagal menyimpan ke server: {e}")
            else:
                st.warning("⚠️ Mohon isi keterangan dan nominal pengeluaran dengan benar.")

    if len(df_lain_all) > 0:
        st.write("Daftar Pengeluaran Lainnya (Klik dua kali atau hapus baris jika ingin mengubah):")
        if "Keterangan" not in df_lain_all.columns:
            df_lain_all["Keterangan"] = ""
        if "Nominal" not in df_lain_all.columns:
            df_lain_all["Nominal"] = 0
        if "ID Lain" not in df_lain_all.columns:
            df_lain_all["ID Lain"] = [f"LAIN-{i}" for i in range(len(df_lain_all))]
            
        df_tampil_lain = df_lain_all[["ID Lain", "Keterangan", "Nominal"]].copy()
        df_tampil_lain['Nominal'] = pd.to_numeric(df_tampil_lain['Nominal'], errors='coerce').fillna(0).apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
        
        df_lain_edit = st.data_editor(df_tampil_lain, num_rows="dynamic", use_container_width=True, key="edit_tabel_lain_bersih")
        
        if not df_tampil_lain.equals(df_lain_edit):
            df_lain_edit['Nominal'] = df_lain_edit['Nominal'].astype(str).str.replace("Rp", "").str.replace(".", "").str.strip()
            df_lain_edit['Nominal'] = pd.to_numeric(df_lain_edit['Nominal'], errors='coerce').fillna(0)
            save_data_to_sheet(SHEET_PENGELUARAN, df_lain_edit)
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
            
        rekap_gaji = {k: 0 for k in daftar_karyawan}
        
        if len(df_f_gaji) > 0:
            grup_nama = df_f_gaji.groupby('Nama')
            for nama, df_n in grup_nama:
                tot_sum = pd.to_numeric(df_n['Total'], errors='coerce').fillna(0).sum()
                if nama in rekap_gaji:
                    rekap_gaji[nama] += tot_sum
                
        if len(df_f_kb) > 0:
            for _, row_kb in df_f_kb.iterrows():
                nama = row_kb['Nama']
                nom_kb = float(row_kb['Nominal']) if pd.notnull(row_kb['Nominal']) else 0
                if nama in rekap_gaji:
                    if row_kb['Tipe'] == "Penambahan":
                        rekap_gaji[nama] += nom_kb
                    else:
                        rekap_gaji[nama] -= nom_kb
                        
        total_gaji_semua = sum(rekap_gaji.values())
        total_pengeluaran_lain = pd.to_numeric(df_lain_all['Nominal'], errors='coerce').fillna(0).sum() if len(df_lain_all) > 0 else 0
        total_pengeluaran_keseluruhan = total_gaji_semua + total_pengeluaran_lain
        sisa_uang = tarik_uang - total_pengeluaran_keseluruhan
        
        scale = 4
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
    st.caption("💡 Tips: Tambahkan nama/pekerjaan baru di baris paling bawah. Data **TERSAVE OTOMATIS** ke Google Sheets.")
    col_karyawan, col_pekerjaan = st.columns(2)
    
    with col_karyawan:
        st.subheader("👥 Daftar Nama Karyawan")
        df_karyawan_baru = st.data_editor(df_karyawan, num_rows="dynamic", key="edit_kary")
        if not df_karyawan.equals(df_karyawan_baru):
            save_data_to_sheet(SHEET_KARYAWAN, df_karyawan_baru)
            st.toast("Daftar Karyawan tersimpan otomatis! 💾", icon="✅")

    with col_pekerjaan:
        st.subheader("🛠️ Daftar & Harga Pekerjaan")
        df_pekerjaan_baru = st.data_editor(df_pekerjaan, num_rows="dynamic", key="edit_pek")
        if not df_pekerjaan.equals(df_pekerjaan_baru):
            save_data_to_sheet(SHEET_PEKERJAAN, df_pekerjaan_baru)
            st.toast("Daftar Pekerjaan tersimpan otomatis! 💾", icon="✅")
