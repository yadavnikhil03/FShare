# 🚀 FSHARE - ADVANCED FILE SHARING SYSTEM

## � **OVERVIEW**
Fshare is a comprehensive file sharing solution that combines desktop GUI application with web-based mobile access. It enables secure file transfers across local networks and globally via internet tunneling.

## 🛠️ **DUAL MODE ARCHITECTURE**

### 🖥️ **Desktop Mode (main.py)**
Full-featured PyQt5 GUI application for local network file sharing

### 📱 **Web/Mobile Mode (start.py + web_api.py)**  
FastAPI web server with mobile-optimized interface and global access via ngrok

## �📁 **CLEAN PROJECT STRUCTURE**

```
Fshare/
├── 🖥️ main.py                    # Desktop GUI Application Entry Point
├── 📱 start.py                   # Mobile/Web Access Server Launcher
├── 🌐 web_api.py                 # FastAPI Web Server & API Endpoints
├── 📋 requirements.txt           # Python Dependencies
├── 📱 Start_Mobile_Access.bat    # Easy Mobile Server Startup Script
├── 🖥️ Start_Fshare.bat          # Desktop Application Launcher
├── 📖 README.md                  # This Documentation
├── backend/                      # Core Backend Architecture
│   ├── config.py                 # Application Configuration
│   ├── sender.py                 # File Sender Module
│   ├── receiver.py               # File Receiver Module  
│   ├── discover.py               # Network Device Discovery
│   ├── encryption.py             # Cryptographic Security
│   └── utils.py                  # Utility Functions
├── frontend/                     # PyQt5 GUI Interface
│   ├── ui_main.py                # Main Window & UI Components
│   └── theme.qss                 # UI Styling & Themes
├── test/                         # Unit Tests & Validation
│   ├── test_encryption.py        # Security Testing
│   └── test_transfer.py          # Transfer Testing  
├── logs/                         # Application Logs & Monitoring
├── mobile_uploads/               # Mobile Upload Storage
└── mobile_downloads/             # Mobile Download Storage
```

## 🚀 **QUICK START GUIDE**

### 🖥️ **Desktop Application Mode:**
```bash
python main.py
```
**Features:**
- ✅ Full PyQt5 GUI interface with dark theme
- ✅ Local network file sharing (same WiFi)
- ✅ Auto device discovery & manual IP connection
- ✅ Multi-device transfers (1-to-4 devices simultaneously)  
- ✅ Real-time transfer progress monitoring
- ✅ 6-digit connection codes & shareable links
- ✅ Drag-and-drop file selection
- ✅ Encrypted file transfers (AES-256)
- ✅ No internet access required

### 📱 **Mobile/Web Access Mode:**
```bash
python start.py
```
**Features:**
- ✅ FastAPI web server with responsive mobile UI
- ✅ Global internet access via ngrok tunneling
- ✅ Mobile file upload with 6-digit verification codes
- ✅ QR code generation for instant file downloads
- ✅ Cross-platform browser compatibility
- ✅ Automatic file cleanup & security
- ✅ Real-time transfer monitoring dashboard
- ✅ CORS enabled for cross-network access

## 🔧 **DESKTOP APPLICATION FEATURES**

### 🎯 **Core Functionality:**
- **Multi-Tab Interface:** Send, Receive, Settings, Logs
- **Device Discovery:** Auto-scan for nearby Fshare devices
- **Connection Methods:** 
  - 🔍 Auto-discovery scanning
  - 🔢 6-digit connection codes  
  - 🔗 Shareable connection links
  - 📍 Manual IP address entry
- **File Management:** Add/remove files, batch transfers
- **Real-time Monitoring:** Connected devices, transfer progress
- **Security:** AES-256 encryption, secure authentication

### 🌐 **Network Capabilities:**
- **Local Network:** Same WiFi network transfers
- **Port Configuration:** Customizable receiver & discovery ports
- **Connection Sharing:** Generate codes/links for other devices
- **Device Status:** Real-time connection monitoring
- **Multi-device Support:** Send to up to 4 devices simultaneously

### 🛡️ **Security Features:**
- **Encryption:** AES-256 bit encryption for all transfers
- **Authentication:** 6-digit codes & connection verification
- **Network Security:** Local network isolation by default
- **Automatic Cleanup:** Temporary files auto-deletion

## 📱 **WEB API & MOBILE FEATURES**

### 🔗 **API Endpoints:**
```
GET  /                           # Main Dashboard & Control Panel
GET  /mobile/upload             # Mobile Upload Interface  
GET  /mobile/download/{file_id} # Mobile Download Interface
POST /api/generate-code         # Generate 6-Digit Upload Code
POST /api/verify-code           # Verify Upload Code
POST /api/upload                # File Upload Endpoint
POST /api/generate-qr           # Generate Download QR Code
GET  /api/qr/{file_id}          # Get QR Code Image
GET  /api/download/{file_id}    # Direct File Download
GET  /api/status                # Server Status & Statistics
```

### 📊 **Dashboard Features:**
- **Real-time Statistics:** Active transfers, total uploads/downloads
- **Server Control:** Start/stop server, toggle status
- **File Management:** View recent transfers, cleanup controls
- **Mobile Code Generation:** Create secure 6-digit codes
- **QR Code System:** Generate instant download links
- **Network Information:** Local & public access URLs

### 🔐 **Mobile Security System:**
- **6-Digit Codes:** Secure upload authentication
- **Time-based Expiry:** Codes expire after set duration
- **Single-use Validation:** Each code works once only
- **IP Tracking:** Monitor upload sources
- **Automatic Cleanup:** Remove expired codes & files

### 🌍 **Global Access via Ngrok:**
- **Internet Tunneling:** Access from anywhere globally
- **HTTPS Support:** Secure connections via ngrok
- **Dynamic URLs:** Auto-generated public URLs
- **Cross-platform:** Works on any device with browser
- **No Port Forwarding:** Bypass network restrictions

## 🛠️ **BACKEND ARCHITECTURE**

### 📦 **Core Modules:**

#### 🔧 **config.py - Application Configuration**
- Network settings (ports, timeouts, buffer sizes)
- Security configuration (encryption, key management)
- File transfer settings (chunk sizes, max file limits)
- Default paths and application behavior

#### 📤 **sender.py - File Sender Module**  
- Multi-file transfer capability
- Progress tracking and callbacks
- Network connection management
- Error handling and retry logic

#### 📥 **receiver.py - File Receiver Module**
- Incoming file processing
- Download path management  
- Connection code generation
- Real-time status updates

#### 🔍 **discover.py - Network Discovery**
- Device auto-discovery on local network
- Broadcasting and listening services
- Device information collection
- Connection establishment

#### 🔒 **encryption.py - Security Layer**
- AES-256 encryption implementation
- Key generation and management
- Secure data transmission
- Cryptographic utilities

#### 🛠️ **utils.py - Utility Functions**
- File size formatting
- Logging configuration
- Network utilities
- Helper functions

### 2. Start the System
## 🚀 **DEPLOYMENT & SETUP**

### 📋 **System Requirements:**
```
Python 3.7+
PyQt5 (for desktop GUI)
FastAPI + Uvicorn (for web server)
Cryptography library (for encryption)
QRCode library (for mobile downloads)
Ngrok (for global access)
```

### ⚡ **Quick Installation:**
```bash
# Install Python dependencies
pip install -r requirements.txt

# For desktop mode only
python main.py

# For mobile/web mode only  
python start.py
```

### 🌐 **Manual Web Server Setup:**
```bash
# Start FastAPI server manually
python web_api.py

# Start ngrok tunnel (separate terminal)
ngrok http 8001
```

### 3. Access URLs

## 🌐 **ACCESS URLS & ENDPOINTS**

**Local Desktop Dashboard:**
- 🖥️ http://127.0.0.1:8001 - Main control panel
- 📊 http://127.0.0.1:8001/api/status - Server status API

**Mobile Upload (Same WiFi Network):**
- 📱 http://[YOUR-LOCAL-IP]:8001/mobile/upload
- 📱 http://192.168.1.XXX:8001/mobile/upload

**Mobile Upload (Global Internet Access):**
- 🌍 https://[your-ngrok-url].ngrok-free.app/mobile/upload
- 🌍 https://[random-id].ngrok-free.app/mobile/upload

**API Endpoints:**
- � POST /api/generate-code - Create upload code
- ✅ POST /api/verify-code - Validate upload code  
- 📤 POST /api/upload - File upload endpoint
- 📄 POST /api/generate-qr - Create download QR
- 🖼️ GET /api/qr/{file_id} - Get QR code image
- ⬇️ GET /api/download/{file_id} - Download file

## 📱 **MOBILE USAGE WORKFLOWS**

### 📤 **Mobile File Upload Process:**
1. **Desktop:** Launch `python start.py` 
2. **Desktop:** Generate 6-digit code via dashboard
3. **Mobile:** Navigate to upload URL
4. **Mobile:** Enter 6-digit code for verification  
5. **Mobile:** Select and upload files
6. **Desktop:** Files appear in mobile_uploads/ folder

### 📥 **Mobile File Download Process:**
1. **Desktop:** Upload file via dashboard interface
2. **Desktop:** Generate QR code for the file
3. **Mobile:** Scan QR code with camera
4. **Mobile:** Automatically redirected to download page
5. **Mobile:** Download file directly to device

### � **Security Verification:**
- All upload codes expire after 15 minutes
- Each code can only be used once
- IP addresses are logged for security
- Files auto-delete after 24 hours
- All transfers use HTTPS via ngrok

## 💻 **DEVELOPMENT & TESTING**

### 🧪 **Running Tests:**
```bash
# Test encryption functionality
python test/test_encryption.py

# Test file transfer capabilities  
python test/test_transfer.py
```

### 🔧 **Configuration Options:**
```python
# Edit backend/config.py for customization
RECEIVER_PORT = 8888        # Desktop receiver port
DISCOVERY_PORT = 8889       # Device discovery port  
WEB_API_PORT = 8001        # Web server port
ENCRYPTION_ENABLED = True  # Enable/disable encryption
MAX_FILE_SIZE = 10GB       # Maximum file size limit
CLEANUP_INTERVAL = 3600    # Auto-cleanup interval (seconds)
```

## 💡 **ADVANCED FEATURES**

### 🔄 **Real-time Monitoring:**
- Live transfer progress bars
- Connection status indicators  
- Device discovery notifications
- Error logging and reporting
- Network performance metrics

### 🛡️ **Security & Privacy:**
- End-to-end AES-256 encryption
- No cloud storage - direct device transfers
- Local network isolation by default
- Automatic temporary file cleanup
- Secure connection authentication

### 🌍 **Cross-platform Compatibility:**
- Windows, macOS, Linux desktop support
- iOS, Android mobile browser access
- Chrome, Firefox, Safari, Edge compatibility
- Responsive design for all screen sizes
- Touch-optimized mobile interface

## 📁 Essential Files

## 📁 **KEY SYSTEM FILES**

### 🔑 **Core Application Files:**
- `main.py` - Desktop GUI application entry point
- `start.py` - Mobile/web server automatic launcher  
- `web_api.py` - FastAPI server with mobile interface
- `requirements.txt` - Python package dependencies

### 🛠️ **Backend Architecture:**
- `backend/config.py` - System configuration & settings
- `backend/sender.py` - File sending & transfer logic
- `backend/receiver.py` - File receiving & processing
- `backend/discover.py` - Network device discovery
- `backend/encryption.py` - Security & cryptography
- `backend/utils.py` - Shared utility functions

### 🎨 **Frontend Interface:**
- `frontend/ui_main.py` - PyQt5 GUI components & windows
- `frontend/theme.qss` - UI styling & visual themes

### 🧪 **Testing & Validation:**
- `test/test_encryption.py` - Security testing suite
- `test/test_transfer.py` - File transfer testing

### 📊 **Data & Logs:**
- `logs/` - Application logs & error tracking
- `mobile_uploads/` - Mobile uploaded files storage
- `mobile_downloads/` - Mobile download files storage

## 🚀 **PERFORMANCE SPECIFICATIONS**

### 📈 **Transfer Capabilities:**
- **File Size Limit:** 10GB per file (configurable)
- **Simultaneous Transfers:** Up to 4 devices at once
- **Transfer Speed:** Limited by network bandwidth
- **Chunk Size:** 8KB (optimized for reliability)
- **Concurrent Connections:** Multiple devices supported

### 🔧 **Technical Specifications:**
- **Encryption:** AES-256 bit symmetric encryption
- **Network Protocols:** TCP/IP socket communication
- **Web Framework:** FastAPI with async support
- **GUI Framework:** PyQt5 with custom dark theme
- **Database:** In-memory storage with JSON logging
- **File Formats:** All file types supported

## 💡 Features

## ✨ **COMPREHENSIVE FEATURE LIST**

### 🖥️ **Desktop Application Features:**
- ✅ **Multi-tab Interface** - Send, Receive, Settings, Logs
- ✅ **Device Auto-discovery** - Automatic network scanning
- ✅ **Multi-device Transfers** - Send to 4 devices simultaneously  
- ✅ **Connection Methods** - Codes, links, IP, discovery
- ✅ **Real-time Progress** - Live transfer monitoring
- ✅ **Dark Theme UI** - Modern PyQt5 interface
- ✅ **Drag & Drop** - Easy file selection
- ✅ **Encrypted Transfers** - AES-256 security
- ✅ **Connection Sharing** - Generate codes & links
- ✅ **Network Configuration** - Custom ports & settings

### 📱 **Mobile/Web Features:**
- ✅ **6-digit Code System** - Secure mobile uploads
- ✅ **QR Code Downloads** - Instant file sharing
- ✅ **Global Internet Access** - Ngrok tunneling support
- ✅ **Responsive Design** - Mobile-optimized interface
- ✅ **Cross-platform Browser** - Works on all devices
- ✅ **Real-time Dashboard** - Transfer monitoring & control
- ✅ **Automatic File Cleanup** - Security & storage management
- ✅ **CORS Support** - Cross-network compatibility
- ✅ **HTTPS Encryption** - Secure global connections
- ✅ **Progress Tracking** - Upload/download progress bars

### 🔒 **Security & Privacy Features:**
- ✅ **End-to-end Encryption** - AES-256 bit protection
- ✅ **Local Network First** - No cloud dependency
- ✅ **Temporary File Cleanup** - Automatic deletion
- ✅ **Connection Authentication** - Code verification
- ✅ **IP Address Logging** - Security monitoring
- ✅ **Time-based Expiry** - Auto-expiring codes
- ✅ **Single-use Codes** - Enhanced security
- ✅ **Network Isolation** - Local transfer priority

### 🛠️ **Developer & Advanced Features:**
- ✅ **RESTful API** - Complete web API endpoints
- ✅ **FastAPI Framework** - Modern async web server
- ✅ **Comprehensive Testing** - Unit tests included
- ✅ **Configurable Settings** - Customizable parameters
- ✅ **Detailed Logging** - Error tracking & debugging
- ✅ **Cross-platform Support** - Windows, macOS, Linux
- ✅ **Modular Architecture** - Clean code structure
- ✅ **Performance Monitoring** - Transfer statistics

## 🔧 **TROUBLESHOOTING & SUPPORT**

### ❓ **Common Issues:**

**Desktop App Won't Start:**
- Ensure PyQt5 is installed: `pip install PyQt5`
- Check Python version: Requires 3.7+
- Run: `python -m pip install --upgrade pip`

**Mobile Access Not Working:**
- Verify ngrok is installed and accessible
- Check Windows Defender isn't blocking ngrok
- Ensure port 8001 is not in use by another app
- Try manual server start: `python web_api.py`

**File Transfer Fails:**
- Check both devices are on same WiFi network
- Verify firewall isn't blocking connections
- Try manual IP connection instead of auto-discovery
- Check available disk space on receiving device

**Code/QR Not Working:**
- Codes expire after 15 minutes - generate new one
- Each code works only once - create new for each upload
- Clear browser cache and cookies
- Try different browser or incognito mode

### 📞 **Getting Help:**
- Check logs in `logs/` directory for error details
- Run with debug mode for verbose output
- Test network connectivity between devices
- Verify all dependencies are correctly installed

---
**🎯 Keep terminals open while using the system for optimal performance!**

**🛡️ For best security, use local network mode when possible and global mode only when needed.**

---

## 💝 **CREDITS**

<div align="center">

**Made with ❤️ by Akash**

*Passionate about creating secure and user-friendly file sharing solutions*

🚀 *Building tomorrow's technology today* 🚀

</div>
