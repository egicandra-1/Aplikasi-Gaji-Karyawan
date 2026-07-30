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
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    except:
        import json
        dict_creds = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict_creds, scope)
    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_client()
    return client.open_by_url("https://docs.google.com/spreadsheets/d/1nSVOJTyA48REHwPvaWbvVXUupdh_GcrCHvBqbEA-xe8/edit?usp=sharing")

# --- NAMA TAB SHEET GOOGLE SHEETS ---
SHEET_GAJI = "Data_Gaji"
SHEET_KASBON = "Data_Kasbon_Bonus"
SHEET_PENGELUARAN = "Data_Pengeluaran_Lain"
SHEET_KARYAWAN = "Master_Karyawan"
SHEET_PEKERJAAN = "Master_Pekerjaan"

# --- FUNGSI BANTU GOOGLE SHEETS ---
def fetch_sheet(nama_sheet, kolom_default):
    try:
        worksheet = get_spreadsheet().worksheet(nama_sheet)
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
        worksheet = get_spreadsheet().add_worksheet(title=nama_sheet, rows="100", cols="20")
        df_kosong = pd.DataFrame(columns=kolom_default)
        worksheet.update([df_kosong.columns.values.tolist()] + df_kosong.values.tolist())
        return df_kosong
    except Exception as e:
        st.error(f"Error memuat {nama_sheet}: {e}")
        return pd.DataFrame(columns=kolom_default)

def save_df_to_sheet(nama_sheet, df):
    worksheet = get_spreadsheet().worksheet(nama_sheet)
    worksheet.clear()
    data_to_write = [df.columns.values.tolist()] + df.fillna("").values.tolist()
    worksheet.update(data_to_write)

def append_row_to_sheet(nama_sheet, row_data):
    worksheet = get_spreadsheet().worksheet(nama_sheet)
    worksheet.append_row(row_data)

# --- SISTEM MEMORI RAM (SUPER CEPAT) ---
# Data hanya di-download 1x saat aplikasi pertama dibuka
if "data_loaded" not in st.session_state:
    with st.spinner("Sinkronisasi awal dari Google Sheets... (Hanya 1 kali)"):
        st.session_state.df_gaji = fetch_sheet(SHEET_GAJI, ["ID Data", "Hari", "Tanggal", "Nama", "Pekerjaan", "Upah", "Jumlah", "Total"])
        if "Harga" in st.session_state.df_gaji.columns:
            st.session_state.df_gaji = st.session_state.df_gaji.rename(columns={"Harga": "Upah"})
            
        st.session_state.df_kasbon = fetch_sheet(SHEET_KASBON, ["ID Kasbon", "Tanggal", "Nama", "Tipe", "Keterangan", "Nominal"])
        st.session_state.df_pengeluaran = fetch_sheet(SHEET_PENGELUARAN, ["ID Lain", "Keterangan", "Nominal"])
        
        st.session_state.df_karyawan = fetch_sheet(SHEET_KARYAWAN, ["Nama Karyawan"])
        if len(st.session_state.df_karyawan) == 0:
            st.session_state.df_karyawan = pd.DataFrame({"Nama Karyawan": ["Teh Eva", "Bi Nyai", "Radi", "Ula", "Sintia", "Mang Ade", "Mang Koko", "Yoga", "Samsul"]})
            save_df_to_sheet(SHEET_KARYAWAN, st.session_state.df_karyawan)
            
        st.session_state.df_pekerjaan = fetch_sheet(SHEET_PEKERJAAN, ["Jenis Pekerjaan", "Harga Per Pcs"])
        if len(st.session_state.df_pekerjaan) == 0:
            st.session_state.df_pekerjaan = pd.DataFrame({
                "Jenis Pekerjaan": ["Bungkus Patung", "Packing Styrofoam", "Bungkus Cat"],
                "Harga Per Pcs": [150, 400, 15]
            })
            save_df_to_sheet(SHEET_PEKERJAAN, st.session_state.df_pekerjaan)
            
        st.session_state.data_loaded = True

# Tombol Refresh Manual di Sidebar
if st.sidebar.button("🔄 Sinkronisasi Ulang Data"):
    del st.session_state["data_loaded"]
    st.rerun()

# Membaca data langsung dari memori yang sudah tersimpan
df_karyawan = st.session_state.df_karyawan
df_pekerjaan = st.session_state.df_pekerjaan
daftar_karyawan = df_karyawan["Nama Karyawan"].dropna().tolist() if not df_karyawan.empty else []
daftar_pekerjaan = df_pekerjaan["Jenis Pekerjaan"].dropna().tolist() if not df_pekerjaan.empty else []
tarif_pekerjaan = dict(zip(df_pekerjaan["Jenis Pekerjaan"], pd.to_numeric(df_pekerjaan["Harga Per Pcs"], errors='coerce').fillna(0))) if not df_pekerjaan.empty else {}

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
            
            col1, col2 = st.columns([2, 1])
            with col1:
                opsi_kerja = ["-"] + daftar_pekerjaan
                pekerjaan = st.selectbox("Pilih Pekerjaan", opsi_kerja)
            with col2:
                # Menggunakan text_input agar tidak ada limit atau awalan 0
                jumlah_str = st.text_input("Jumlah (Pcs)", placeholder="Ketik jumlah pcs (contoh: 500)")
                
            submitted_input = st.form_submit_button("💾 Simpan Data Pekerjaan", type="primary", use_container_width=True)
            
            if submitted_input:
                try:
                    jumlah = int(jumlah_str.strip())
                except:
                    jumlah = 0
                    
                if pekerjaan != "-" and jumlah > 0:
                    upah = tarif_pekerjaan[pekerjaan]
                    total = jumlah * upah
                    try:
                        id_data = f"ID-{int(time.time())}"
                        tgl_str = tanggal.strftime("%Y-%m-%d")
                        
                        # Simpan ke Memori Instan
                        baris_baru = {"ID Data": id_data, "Hari": nama_hari, "Tanggal": tgl_str, "Nama": nama, "Pekerjaan": pekerjaan, "Upah": upah, "Jumlah": jumlah, "Total": total}
                        st.session_state.df_gaji = pd.concat([st.session_state.df_gaji, pd.DataFrame([baris_baru])], ignore_index=True)
                        
                        # Simpan ke Server Latar Belakang
                        append_row_to_sheet(SHEET_GAJI, [id_data, nama_hari, tgl_str, nama, pekerjaan, upah, jumlah, total])
                        
                        jml_fmt = f"{jumlah:,.0f}".replace(",", ".")
                        st.success(f"✅ Tersimpan Kilat! {jml_fmt} {pekerjaan} untuk {nama}.")
                    except Exception as e:
                        st.error(f"⚠️ Gagal simpan ke server: {e}")
                elif pekerjaan == "-":
                    st.error("⚠️ Gagal simpan! Anda belum memilih Jenis Pekerjaan.")
                else:
                    st.error("⚠️ Gagal simpan! Mohon ketik angka/jumlah yang valid.")

# ==========================================
# MENU 2: DATABASE & EDIT PEKERJAAN
# ==========================================
with menu2:
    st.header("Database Riwayat Pekerjaan (Per Hari)")
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
                        
                        df_sisa = st.session_state.df_gaji[~st.session_state.df_gaji['ID Data'].isin(df_harian['ID Data'])]
                        df_final = pd.concat([df_sisa, df_harian_edit]).sort_values(by="Tanggal").reset_index(drop=True)
                        
                        st.session_state.df_gaji = df_final
                        save_df_to_sheet(SHEET_GAJI, df_final)
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
    if len(daftar_karyawan) > 0:
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
                ket_kb = st.text_input("Keterangan")
            with col_kb5:
                nominal_str = st.text_input("Nominal (Rp)", placeholder="Ketik nominal...")
                
            if st.form_submit_button("💾 Simpan Data", type="primary", use_container_width=True):
                try:
                    nominal_kb = int(nominal_str.strip())
                except:
                    nominal_kb = 0
                    
                if nominal_kb > 0 and ket_kb.strip() != "":
                    try:
                        id_kb = f"KB-{int(time.time())}"
                        tgl_str = tgl_kb.strftime("%Y-%m-%d")
                        
                        baris_kb = {"ID Kasbon": id_kb, "Tanggal": tgl_str, "Nama": nama_kb, "Tipe": tipe_kb, "Keterangan": ket_kb, "Nominal": nominal_kb}
                        st.session_state.df_kasbon = pd.concat([st.session_state.df_kasbon, pd.DataFrame([baris_kb])], ignore_index=True)
                        
                        append_row_to_sheet(SHEET_KASBON, [id_kb, tgl_str, nama_kb, tipe_kb, ket_kb, nominal_kb])
                        st.success("✅ Berhasil menyimpan data!")
                    except Exception as e:
                        st.error(f"Gagal: {e}")
                else:
                    st.error("⚠️ Mohon isi keterangan dan nominal dengan angka yang valid.")

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
            tgl_mulai = st.date_input("Dari Tanggal", datetime.today(), format="DD/MM/YYYY", key="tgl_mulai_slip")
        with col_b:
            tgl_selesai = st.date_input("Sampai Tanggal", datetime.today(), format="DD/MM/YYYY", key="tgl_selesai_slip")
            
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
    with col_r1: tgl_mulai_res = st.date_input("Dari Tanggal", datetime.today(), format="DD/MM/YYYY", key="res_mulai")
    with col_r2: tgl_selesai_res = st.date_input("Sampai Tanggal", datetime.today(), format="DD/MM/YYYY", key="res_selesai")
    
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
            try:
                nominal_lain = int(nominal_lain_str.strip())
            except:
                nominal_lain = 0
                
            if nominal_lain > 0 and ket_lain.strip() != "":
                try:
                    id_lain = f"LAIN-{int(time.time())}"
                    baris_lain = {"ID Lain": id_lain, "Keterangan": ket_lain, "Nominal": nominal_lain}
                    st.session_state.df_pengeluaran = pd.concat([st.session_state.df_pengeluaran, pd.DataFrame([baris_lain])], ignore_index=True)
                    
                    append_row_to_sheet(SHEET_PENGELUARAN, [id_lain, ket_lain, nominal_lain])
                    st.success(f"Berhasil menambahkan '{ket_lain}'!")
                    st.rerun()
                except Exception as e:
                    st.warning(f"⚠️ Gagal menyimpan: {e}")
            else:
                st.warning("⚠️ Mohon isi dengan benar.")

    if st.button("🖼️ Generate Gambar Resume", type="primary"):
        try:
            tarik_uang = int(tarik_uang_str.strip())
        except:
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
# MENU 6: PENGATURAN (DENGAN TOMBOL HAPUS ❌ INSTAN)
# ==========================================
with menu6:
    st.header("Pengaturan Master Data")
    col_karyawan, col_pekerjaan = st.columns(2)
    
    with col_karyawan:
        st.subheader("👥 Daftar Nama Karyawan")
        with st.form("form_tambah_karyawan", clear_on_submit=True):
            nama_baru = st.text_input("Nama Karyawan Baru", placeholder="Ketik nama...")
            if st.form_submit_button("➕ Tambah Karyawan", type="primary", use_container_width=True):
                if nama_baru.strip() and nama_baru not in daftar_karyawan:
                    # Update local memory instan
                    new_df = pd.DataFrame([{"Nama Karyawan": nama_baru.strip()}])
                    st.session_state.df_karyawan = pd.concat([st.session_state.df_karyawan, new_df], ignore_index=True)
                    # Update google sheet di background
                    append_row_to_sheet(SHEET_KARYAWAN, [nama_baru.strip()])
                    st.success(f"Berhasil menambah {nama_baru}!")
                    st.rerun()
        
        st.write("Daftar Karyawan (Klik ❌ untuk menghapus):")
        for idx, row in st.session_state.df_karyawan.iterrows():
            c1, c2 = st.columns([4, 1])
            with c1:
                st.text(row['Nama Karyawan'])
            with c2:
                if st.button("❌", key=f"del_kar_{idx}"):
                    # Hapus instan di local memory
                    st.session_state.df_karyawan = st.session_state.df_karyawan.drop(idx).reset_index(drop=True)
                    # Kirim sinkronisasi ke sheet
                    save_df_to_sheet(SHEET_KARYAWAN, st.session_state.df_karyawan)
                    st.rerun()

    with col_pekerjaan:
        st.subheader("🛠️ Daftar & Harga Pekerjaan")
        with st.form("form_tambah_pekerjaan", clear_on_submit=True):
            pek_baru = st.text_input("Jenis Pekerjaan Baru", placeholder="Ketik jenis pekerjaan...")
            harga_baru_str = st.text_input("Harga Per Pcs (Rp)", placeholder="Ketik harga...")
            if st.form_submit_button("➕ Tambah Pekerjaan", type="primary", use_container_width=True):
                try:
                    harga_baru = int(harga_baru_str.strip())
                except:
                    harga_baru = 0
                    
                if pek_baru.strip() and harga_baru > 0:
                    if pek_baru not in daftar_pekerjaan:
                        new_df = pd.DataFrame([{"Jenis Pekerjaan": pek_baru.strip(), "Harga Per Pcs": harga_baru}])
                        st.session_state.df_pekerjaan = pd.concat([st.session_state.df_pekerjaan, new_df], ignore_index=True)
                        append_row_to_sheet(SHEET_PEKERJAAN, [pek_baru.strip(), harga_baru])
                        st.success(f"Berhasil menambah {pek_baru}!")
                        st.rerun()
        
        st.write("Daftar Pekerjaan (Klik ❌ untuk menghapus):")
        for idx, row in st.session_state.df_pekerjaan.iterrows():
            c1, c2 = st.columns([4, 1])
            with c1:
                st.text(f"{row['Jenis Pekerjaan']} (Rp {row['Harga Per Pcs']:,.0f})".replace(",", "."))
            with c2:
                if st.button("❌", key=f"del_pek_{idx}"):
                    st.session_state.df_pekerjaan = st.session_state.df_pekerjaan.drop(idx).reset_index(drop=True)
                    save_df_to_sheet(SHEET_PEKERJAAN, st.session_state.df_pekerjaan)
                    st.rerun()
