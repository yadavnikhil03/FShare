# FShare

**Secure file sharing with desktop GUI and web interface**

Transfer files locally or globally with AES-256 encryption.

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Desktop GUI
python main.py

# Web Server (Mobile Access)
python start.py
```

---

## ✨ Features

- **Desktop Mode** - PyQt5 GUI for local network transfers
- **Web Mode** - FastAPI server with mobile interface + ngrok tunneling  
- **Security** - AES-256 encryption for all transfers
- **Multi-device** - Send to up to 4 devices simultaneously
- **Connection** - Auto-discovery, 6-digit codes, QR codes

---

## 🧪 Testing

```bash
python test/run_tests.py
```
*32 tests covering encryption, transfers, config, utils, and web API*

---

## 📁 Project Structure

```
FShare/
├── main.py                  # Desktop GUI
├── start.py                 # Web server launcher  
├── web_api.py              # FastAPI server
├── requirements.txt        # Dependencies
├── backend/                # Core modules
├── frontend/               # PyQt5 GUI
├── test/                   # Test suite
├── logs/                   # Application logs
├── mobile_uploads/         # Upload storage
└── mobile_downloads/       # Download storage
```

---

## ⚙️ Configuration

**Default ports:**
- Desktop: `12345`
- Web server: `8000`

**Directories:**
- Uploads: `mobile_uploads/`
- Downloads: `mobile_downloads/`

*Edit `backend/config.py` to customize*
