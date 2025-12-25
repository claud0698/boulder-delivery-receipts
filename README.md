# Boulder Delivery Receipt Tracker

Sistem pelacakan pengiriman material batu otomatis menggunakan AI untuk mengekstrak data dari bukti penimbangan.

---

## 🎯 Overview

Kirim foto bukti penimbangan via Telegram → AI ekstrak data → Otomatis tersimpan di Google Sheets + Google Drive

## 🏗️ Arsitektur Sistem

```
User (Telegram) → Foto Bukti → Bot Server → Gemini Vision API → Google Sheets
                                     ↓
                              Upload ke Google Drive (folder harian)
                              Validasi Data
                              Error Handling
```

## 🛠️ Tech Stack

### Core Components
- **Messaging**: Telegram Bot API (python-telegram-bot 20.7)
- **AI/OCR**: Google Gemini 2.5 Flash Vision API
- **Storage**: Google Sheets API v4 + Google Drive API
- **Backend**: FastAPI (async)
- **Language**: Python 3.11+

### Key Libraries
```
python-telegram-bot==20.7      # Telegram bot integration
google-generativeai==0.3.1     # Gemini API
google-api-python-client==2.108.0  # Google Sheets & Drive
fastapi==0.104.1               # Web framework
uvicorn[standard]==0.24.0      # ASGI server
pydantic==2.5.0                # Data validation
tenacity==8.2.3                # Retry logic
loguru==0.7.2                  # Logging
Pillow==10.1.0                 # Image processing
python-dotenv==1.0.0           # Environment config
```

## ✨ Fitur

### MVP Features
- ✅ Terima foto bukti penimbangan via Telegram
- ✅ Ekstraksi OCR (no nota, kendaraan, material, berat)
- ✅ Kategorisasi material otomatis dengan AI
- ✅ Upload foto ke Google Drive (folder per tanggal)
- ✅ Logging otomatis ke Google Sheets
- ✅ Validasi data (perhitungan berat, format tanggal)
- ✅ Error handling dengan feedback ke user
- ✅ Rate limiting dan retry logic

### Data yang Diekstrak
Dari bukti penimbangan (BUKTI PENIMBANGAN):
- **NO NOTA**: Nomor bukti penimbangan
- **NOMOR TIMBANGAN**: Nomor timbangan yang digunakan
- **WAKTU PENIMBANGAN**: Tanggal dan waktu penimbangan
- **NOMOR UNIT**: Nomor polisi kendaraan
- **NAMA MATERIAL**: Jenis material (termasuk karakter Mandarin)
- **BERAT ISI**: Berat kotor (ton)
- **BERAT KOSONG**: Berat kosong kendaraan (ton)
- **BERAT BERSIH**: Berat bersih material (ton)

## 📁 Struktur Project

```
boulder-delivery-receipts/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Application entry point
│   ├── config.py                  # Configuration management
│   ├── messaging/
│   │   ├── __init__.py
│   │   └── telegram_handler.py    # Telegram bot (Bahasa Indonesia)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gemini_client.py       # Gemini Vision API integration
│   │   └── prompts.py             # Prompts untuk Indonesian receipts
│   ├── storage/
│   │   ├── __init__.py
│   │   └── sheets_client.py       # Google Sheets + Drive integration
│   ├── models/
│   │   ├── __init__.py
│   │   └── expense.py             # Delivery data models
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_gemini_delivery.py    # Test Gemini extraction
│   ├── test_sheets_delivery.py    # Test Google Sheets
│   ├── test_drive_upload.py       # Test Google Drive upload
│   └── test_full_pipeline.py      # Test complete flow
├── Samples/
│   ├── Sample1.jpeg               # Sample bukti penimbangan 1
│   └── Sample2.jpeg               # Sample bukti penimbangan 2
├── credentials/                    # Git-ignored
│   └── .gitkeep
├── .env.example                    # Environment template
├── requirements.txt                # Dependencies
├── Dockerfile                      # Container config
├── docker-compose.yml             # Multi-container setup
└── README.md                       # This file
```

## 🚀 Setup Instructions

### Prerequisites
- Python 3.11 or higher
- Akun Telegram
- Google Cloud account (untuk Gemini API, Sheets, dan Drive)
- Git

### 1. Clone Repository
```bash
cd boulder-delivery-receipts
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Setup Telegram Bot
1. Buka Telegram dan cari [@BotFather](https://t.me/botfather)
2. Kirim `/newbot` command
3. Ikuti instruksi untuk membuat bot
4. Copy API token yang diberikan

### 4. Setup Google Gemini API
1. Kunjungi [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Buat API key baru
3. Copy API key

### 5. Setup Google Sheets API
1. Kunjungi [Google Cloud Console](https://console.cloud.google.com/)
2. Buat project baru
3. Enable Google Sheets API dan Google Drive API
4. Buat Service Account:
   - Pergi ke IAM & Admin → Service Accounts
   - Create Service Account
   - Download JSON key file
5. Buat Google Sheet:
   - Buat spreadsheet baru
   - Share dengan service account email (ada di JSON)
   - Copy spreadsheet ID dari URL

### 6. Setup Google Drive (Optional)
1. Buat folder di Google Drive untuk menyimpan foto bukti
2. Share folder dengan service account email
3. Copy folder ID dari URL (string setelah `/folders/`)

### 7. Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env` file:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here

# Google Sheets
GOOGLE_SHEETS_ID=your_spreadsheet_id_here
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service_account.json

# Google Drive (Optional - untuk organize foto per hari)
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id_here

# Application
LOG_LEVEL=INFO
ENVIRONMENT=development
WEBHOOK_URL=https://your-domain.com/webhook  # For production
```

### 8. Add Service Account Key
```bash
mkdir -p credentials
# Pindahkan file service_account.json yang didownload ke folder credentials/
mv ~/Downloads/service_account.json credentials/
```

### 9. Setup Google Sheets Headers
Buat sheet dengan nama **"Pengiriman"** dan header berikut di row 1:

| No | Tanggal | No Nota | Waktu | No Timbangan | No Kendaraan | Nama Material | Jenis Material | Berat Isi (t) | Berat Kosong (t) | Berat Bersih (t) | Status | Catatan | URL Bukti | Ditambahkan |
|----|---------|---------|-------|--------------|--------------|---------------|----------------|---------------|------------------|------------------|--------|---------|-----------|-------------|

### 10. Run Tests
```bash
# Test Gemini extraction
python tests/test_gemini_delivery.py

# Test Google Sheets
python tests/test_sheets_delivery.py

# Test Google Drive upload
python tests/test_drive_upload.py

# Test full pipeline
python tests/test_full_pipeline.py
```

### 11. Run the Bot
**Development Mode (Polling):**
```bash
python src/main.py
```

**Production Mode (Webhook):**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Docker:**
```bash
docker-compose up -d
```

## 📱 Cara Penggunaan

### Basic Flow
1. Start chat dengan Telegram bot Anda
2. Kirim `/start` untuk inisialisasi
3. Kirim foto bukti penimbangan
4. Bot akan memproses dan menampilkan data yang diekstrak:
   - Nomor Nota
   - Waktu Timbang
   - Nomor Kendaraan
   - Material
   - Berat (Isi, Kosong, Bersih)
5. Approve untuk menyimpan ke Google Sheets
6. Data otomatis muncul di Google Sheets
7. Foto tersimpan di Google Drive (folder per tanggal)

### Perintah Bot
- `/start` - Inisialisasi bot
- `/help` - Tampilkan bantuan
- `/upload` - Upload bukti penimbangan
- `/cek_pengiriman` - Lihat 5 pengiriman terbaru

## 📊 Struktur Google Sheets

Bot akan membuat/update sheet "Pengiriman" dengan kolom:

| Kolom | Deskripsi | Format | Contoh |
|-------|-----------|--------|--------|
| No | Nomor urut | Integer | 1 |
| Tanggal | Tanggal penimbangan | Date | 2025-12-24 |
| No Nota | Nomor bukti penimbangan | Text | A125BD00183725122415O1 |
| Waktu | Waktu penimbangan | Time | 15:23:34 |
| No Timbangan | Nomor timbangan | Text | T21 |
| No Kendaraan | Nomor polisi | Text | B9683TVX |
| Nama Material | Nama material lengkap | Text | BATU PECAH 1/2 石子 |
| Jenis Material | Kategori material | Dropdown | Crushed Stone 1/2 |
| Berat Isi (t) | Berat kotor | Number | 23.29 |
| Berat Kosong (t) | Berat kendaraan kosong | Number | 8.05 |
| Berat Bersih (t) | Berat material bersih | Number | 15.24 |
| Status | Status pengiriman | Text | Delivered |
| Catatan | Catatan tambahan | Text | - |
| URL Bukti | Link foto di Drive | URL | https://drive.google.com/... |
| Ditambahkan | Timestamp entry | DateTime | 2025-12-24 16:00:00 |

## 📂 Google Drive Organization

Foto bukti disimpan dengan struktur:
```
[Base Folder]/
├── 2025-12-24/
│   ├── A125BD00183725122415O1.jpg
│   ├── A125BD00183725122415O2.jpg
│   └── ...
├── 2025-12-25/
│   ├── A125BD00183725122515O1.jpg
│   └── ...
└── ...
```

Setiap hari otomatis membuat folder baru dengan format `YYYY-MM-DD`.

## ⚙️ Configuration

### Kategori Material
Default categories (dapat disesuaikan di `src/models/expense.py`):
- Crushed Stone 1/2
- Crushed Stone 2/3
- Crushed Stone 3/5
- River Stone
- Boulder
- Gravel
- Sand
- Other

### Rate Limits
- **Gemini API**: 15 requests/min (free tier)
- **Google Sheets**: 60 write requests/min
- **Google Drive**: 1000 requests/100 seconds
- **Telegram**: No strict limits

Aplikasi otomatis menangani rate limiting dengan exponential backoff.

## 🧪 Development

### Running Tests
```bash
# Test individual components
python tests/test_gemini_delivery.py
python tests/test_sheets_delivery.py
python tests/test_drive_upload.py

# Test full pipeline
python tests/test_full_pipeline.py
```

### Code Quality
```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/
```

## 🐳 Deployment

### Docker Deployment
```bash
docker build -t delivery-tracker .
docker run -d \
  --name delivery-tracker \
  --env-file .env \
  -p 8000:8000 \
  delivery-tracker
```

### Cloud Deployment Options
- **Google Cloud Run**: Serverless container deployment
- **AWS Lambda**: Serverless function (requires adapter)
- **Heroku**: Platform-as-a-Service
- **DigitalOcean App Platform**: Managed container platform

## 💰 API Costs (Estimasi)

### Free Tier Usage
- **Telegram**: Gratis (unlimited)
- **Gemini 2.5 Flash**: 1,500 requests/hari gratis
- **Google Sheets**: Gratis (within quota)
- **Google Drive**: Gratis (15GB storage)

### Paid Usage (jika scaling)
- **Gemini 2.5 Flash**: $0.039 per gambar
- **Estimasi bulanan**: ~$12 untuk 10 bukti/hari (~300/bulan)

## 🐛 Troubleshooting

### Bot tidak merespons
- Periksa `TELEGRAM_BOT_TOKEN` benar
- Verifikasi bot sedang berjalan (`docker ps` atau cek logs)
- Test dengan `/start` command

### OCR accuracy issues
- Pastikan foto bukti jelas dan terang
- Coba sudut/pencahayaan berbeda
- Periksa apakah gambar tidak terbalik

### Google Sheets errors
- Verifikasi service account punya akses edit ke sheet
- Periksa `GOOGLE_SHEETS_ID` benar
- Pastikan path credentials file benar
- Pastikan sheet bernama "Pengiriman" ada

### Google Drive errors
- Verifikasi folder sudah di-share dengan service account
- Periksa `GOOGLE_DRIVE_FOLDER_ID` benar
- Pastikan Drive API sudah di-enable

### Rate limiting errors
- Kurangi frekuensi request
- Periksa error logs untuk limit spesifik
- Tunggu 60 detik dan retry

## 🤝 Contributing

Contributions welcome! Please:
1. Fork repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Google Gemini API untuk vision capabilities
- Telegram Bot API untuk messaging platform
- Google Sheets & Drive API untuk data storage
- Open source community

---

**Built with ❤️ using AI and automation**
