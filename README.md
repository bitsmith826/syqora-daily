# 🪂 Syqora Season 1 Airdrop Automation System

Sistem otomatisasi modern, simpel, dan all-in-one untuk garap **Syqora Season 1 Airdrop** (Pool 10,000,000 PTS) dengan integrasi **Camoufox Anti-Detect Browser** (Firefox C++ engine) untuk bypass Cloudflare Turnstile secara otomatis dan 100% headless.

---

## 🦊 Mengapa Menggunakan Camoufox?

Syqora menerapkan proteksi ketat **Cloudflare Turnstile** saat pendaftaran akun (`/auth/register`). Browser otomatisasi biasa (Chromium/Playwright standar) sering kali terdeteksi dan memunculkan captcha interaktif.

**Kelebihan Camoufox:**
- **C++ Level Fingerprint Spoofing**: Mengubah sidik jari browser (WebGL, Canvas, Audio, WebRTC, navigator) langsung di engine C++ Firefox.
- **Otomatis Bypass Cloudflare Turnstile**: Turnstile terverifikasi secara instan dalam 2-4 detik tanpa intervensi manusia, bahkan dalam mode **Headless** (tanpa memunculkan jendela browser).
- **Profil Perangkat Alami**: Setiap sesi context browser menghasilkan identitas perangkat yang konsisten.

---

## ⚡ Cara Menjalankan

Cukup jalankan satu skrip utama:

```bash
python main.py
```

Skrip secara cerdas akan:
1. Memeriksa `data/accounts.txt`.
2. Mendaftarkan akun baru (jika belum terdaftar) via **Camoufox Headless** dan memasang EVM Address.
3. Menjalankan klaim **Daily Check-In** dan **Quests** cepat via direct API.
4. Menampilkan tabel **Dashboard Status Berwarna** di akhir.

---

## 🛠️ Opsi Perintah Tambahan

Semua fungsi dapat diakses langsung lewat `main.py`:

```bash
# Cek Saldo & Dashboard Status saja (tanpa menjalankan check-in)
python main.py --status

# Hanya jalankan Daily Check-In (Direct API super cepat)
python main.py --checkin-only

# Hanya jalankan Registrasi Akun Baru
python main.py --register-only

# Jalankan dengan Jendela Browser Terbuka (GUI)
python main.py --no-headless

# Jalankan dengan Proxy
python main.py --proxy "http://username:password@ip:port"
```

---

## 📁 Format Data Akun

Cukup isi file `data/accounts.txt` (contoh ada di `data/accounts.example.txt`):
```text
email|password|evm_address
```
Contoh:
```text
user1@gmail.com|MyPass123!|0x71C836057a66160A4b61B10C240E87F616D1e988
user2@gmail.com|MyPass123!|0x2546BcD3c84621e976D8185a91A922aE77ECEc30
```

> [!NOTE]
> Sesi token login tersimpan otomatis di `data/sessions.json` dan secara otomatis di-refresh (self-healing) sehingga Anda tidak perlu login berulang kali.

---

## ⚠️ Disclaimer (Pernyataan Penafian)

> [!WARNING]
> **Hanya untuk Tujuan Edukasi & Riset Teknologi**:
> Repositori ini dibuat semata-mata untuk keperluan **edukasi, pembelajaran otomasi browser (*browser automation*), serta penelitian mekanisme proteksi web (*anti-bot & security research*)**.
> 
> - Penulis tidak bertanggung jawab atas penyalahgunaan skrip ini, pelanggaran ketentuan layanan (*Terms of Service*), diskualifikasi airdrop, penalti, atau penutupan akun oleh pihak penyedia layanan (**Syqora**).
> - Segala tindakan, keputusan, dan risiko yang timbul dari penggunaan alat ini sepenuhnya menjadi tanggung jawab masing-masing pengguna (**Do With Your Own Risk / DWYOR**).
