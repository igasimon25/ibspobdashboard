# Dashboard POB IBS Building Management

Dashboard Streamlit yang membaca data langsung dari Google Sheets:
https://docs.google.com/spreadsheets/d/1g3Y6GjXUgjWFtKxC9ul8i0vZgHvamkDwT7j4-_95NMk

## 1. Wajib: Atur sharing Google Sheet
Karena app membaca sheet lewat link publik (tanpa perlu API key), sheet **harus**
di-share dengan akses:

`Share` → `General access` → **Anyone with the link** → role **Viewer**

Jika sheet-nya private, `pd.read_csv()` akan gagal (403 Forbidden).

> Catatan: kode saat ini membaca **tab pertama** sheet (gid=0). Kalau data
> ada di tab lain, buka tab tersebut di browser, lihat angka `gid=...` di
> URL, lalu isi `SHEET_GID` di secrets (lihat langkah 3).

## 2. Upload ke GitHub
```bash
git init
git add .
git commit -m "Initial commit - dashboard POB IBS"
git branch -M main
git remote add origin https://github.com/<username>/<nama-repo>.git
git push -u origin main
```
File `data_pobibs.xlsx` tidak perlu diupload lagi karena data sekarang diambil
langsung dari Google Sheets.

## 3. Deploy ke Streamlit Community Cloud
1. Buka https://share.streamlit.io/ → **New app**.
2. Pilih repo GitHub yang baru dibuat, branch `main`, file utama `app.py`.
3. (Opsional) Kalau Sheet ID/tab berbeda dari default, buka menu
   **Advanced settings → Secrets** lalu isi:
   ```toml
   SHEET_ID = "1g3Y6GjXUgjWFtKxC9ul8i0vZgHvamkDwT7j4-_95NMk"
   SHEET_GID = "0"
   ```
4. Klik **Deploy**.

## 4. Menjalankan lokal (opsional, untuk testing sebelum deploy)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Struktur file
- `app.py` — script dashboard (logika/tampilan sama persis seperti aslinya,
  hanya sumber data yang diganti dari file Excel lokal menjadi Google Sheets).
- `requirements.txt` — daftar library Python yang dibutuhkan.
- `.streamlit/secrets.toml.example` — contoh konfigurasi Sheet ID (salin jadi
  `secrets.toml` untuk run lokal; jangan di-commit ke GitHub).
