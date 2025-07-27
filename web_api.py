
"""
Fshare Web API - Complete Mobile Implementation
Features: QR code auto-download, 6-digit mobile codes, automatic cleanup
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
import sys
import qrcode
import io
import secrets
import string
import socket
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any

class FshareWebAPI:
    def __init__(self):
        self.app = FastAPI(
            title="Fshare Mobile API", 
            version="2.1.0"
        )
        
        # Configure CORS for cross-network access
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],  
        )
        
        
        self.mobile_connections: Dict[str, Dict[str, Any]] = {}
        self.active_qr_codes: Dict[str, Dict[str, Any]] = {}
        self._current_port = 8001
        
       
        self.active_transfers: Dict[str, Dict[str, Any]] = {}
        self.recent_transfers: list = []
        self.server_status = "online"  
        self.server_stats = {
            "total_uploads": 0,
            "total_downloads": 0,
            "active_connections": 0,
            "uptime_start": datetime.now()
        }
        
        
        os.makedirs("mobile_uploads", exist_ok=True)
        os.makedirs("mobile_downloads", exist_ok=True)
        
       
        self._start_cleanup_thread()
        
        self.setup_routes()
    
    def _start_cleanup_thread(self):
        """Start background thread for file cleanup"""
        def cleanup_files():
            while True:
                try:
                    current_time = datetime.now()
                    
                    # Cleanup expired mobile connections
                    expired_connections = []
                    for code, info in self.mobile_connections.items():
                        created_time = info.get('created_at')
                        if isinstance(created_time, datetime):
                            if current_time - created_time > timedelta(minutes=30):
                                expired_connections.append(code)
                    
                    for code in expired_connections:
                        print(f"🧹 Cleaning up expired mobile connection: {code}")
                        del self.mobile_connections[code]
                    
                    # Cleanup expired QR codes and their files
                    expired_qr_codes = []
                    for file_id, info in self.active_qr_codes.items():
                        created_time = info.get('created_at')
                        if isinstance(created_time, datetime):
                            if current_time - created_time > timedelta(minutes=30):
                                expired_qr_codes.append(file_id)
                    
                    for file_id in expired_qr_codes:
                        try:
                            file_info = self.active_qr_codes[file_id]
                            if os.path.exists(file_info['file_path']):
                                os.remove(file_info['file_path'])
                                print(f"🗑️  Deleted expired file: {file_info['filename']}")
                            del self.active_qr_codes[file_id]
                        except Exception as e:
                            print(f"❌ Error cleaning file {file_id}: {e}")
                    
                    # Cleanup old files in upload/download directories
                    for directory in ["mobile_uploads", "mobile_downloads"]:
                        if os.path.exists(directory):
                            for filename in os.listdir(directory):
                                file_path = os.path.join(directory, filename)
                                try:
                                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                                    if current_time - file_time > timedelta(minutes=30):
                                        os.remove(file_path)
                                        print(f"🧹 Cleaned old file: {filename}")
                                except Exception as e:
                                    print(f"❌ Error cleaning {filename}: {e}")
                    
                except Exception as e:
                    print(f"❌ Cleanup thread error: {e}")
                
                time.sleep(300)
        
        cleanup_thread = threading.Thread(target=cleanup_files, daemon=True)
        cleanup_thread.start()
        print("🧹 File cleanup thread started (30-minute auto-cleanup)")
    
    def add_transfer(self, transfer_id: str, transfer_type: str, filename: str, source: str = "unknown"):
        """Add a new transfer to tracking"""
        transfer_info = {
            "id": transfer_id,
            "type": transfer_type,  
            "filename": filename,
            "source": source,
            "status": "in_progress",
            "started_at": datetime.now(),
            "completed_at": None,
            "size": 0
        }
        self.active_transfers[transfer_id] = transfer_info
        
    def complete_transfer(self, transfer_id: str, size: int = 0):
        """Mark transfer as completed"""
        if transfer_id in self.active_transfers:
            transfer = self.active_transfers[transfer_id]
            transfer["status"] = "completed"
            transfer["completed_at"] = datetime.now()
            transfer["size"] = size
            
            
            self.recent_transfers.insert(0, transfer.copy())
            
           
            if len(self.recent_transfers) > 20:
                self.recent_transfers = self.recent_transfers[:20]
            
            
            del self.active_transfers[transfer_id]
            
            
            if transfer["type"] == "upload":
                self.server_stats["total_uploads"] += 1
            else:
                self.server_stats["total_downloads"] += 1
    
    def get_transfer_summary(self):
        """Get current transfer status"""
        return {
            "active_transfers": list(self.active_transfers.values()),
            "recent_transfers": self.recent_transfers[:10],  
            "server_stats": self.server_stats.copy(),
            "server_status": self.server_status
        }
    
    def toggle_server_status(self):
        """Toggle server between online/offline"""
        if self.server_status == "online":
            self.server_status = "offline"
        else:
            self.server_status = "online"
        return self.server_status

    def setup_routes(self):
        """Setup all API routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Main web dashboard"""
            local_ip = self.get_local_ip()
            current_port = self._current_port
            
            return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Fshare Mobile</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            background-attachment: fixed;
            min-height: 100vh;
            color: #333;
        }}
        .navbar {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            padding: 15px 0;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
        }}
        .navbar-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
        }}
        .logo {{
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .status-badge {{
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            padding: 8px 16px;
            border-radius: 25px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-badge.offline {{
            background: linear-gradient(45deg, #e74c3c, #c0392b);
        }}
        .server-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .toggle-btn {{
            background: linear-gradient(45deg, #f39c12, #e67e22);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .toggle-btn:hover {{
            transform: translateY(-2px);
        }}
        .transfer-monitor {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .transfer-item {{
            background: rgba(52, 152, 219, 0.1);
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .transfer-item.completed {{
            background: rgba(39, 174, 96, 0.1);
            border-left-color: #27ae60;
        }}
        .transfer-item.mobile {{
            background: rgba(155, 89, 182, 0.1);
            border-left-color: #9b59b6;
        }}
        .transfer-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-item {{
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .loading-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 20px;
        }}
        .hero {{
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }}
        .hero h1 {{
            font-size: clamp(28px, 5vw, 48px);
            margin-bottom: 15px;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}
        .connection-info {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .connection-url {{
            font-family: 'Courier New', monospace;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            border: 2px dashed #667eea;
            margin: 10px 0;
            word-break: break-all;
            font-size: 14px;
            color: #2c3e50;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(15px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }}
        .card:hover {{
            transform: translateY(-8px);
            box-shadow: 0 30px 60px rgba(0,0,0,0.15);
        }}
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 25px;
        }}
        .card-icon {{
            font-size: 28px;
            margin-right: 15px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            padding: 12px;
            border-radius: 12px;
            color: white;
        }}
        .btn {{
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 15px 25px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 10px 0;
            width: 100%;
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 25px rgba(102, 126, 234, 0.4);
        }}
        .btn-success {{
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            box-shadow: 0 8px 20px rgba(39, 174, 96, 0.3);
        }}
        .form-control {{
            width: 100%;
            padding: 15px;
            border: 2px solid #ecf0f1;
            border-radius: 12px;
            font-size: 16px;
            margin: 10px 0;
            background: #f8f9fa;
        }}
        .form-control:focus {{
            outline: none;
            border-color: #667eea;
            background: white;
        }}
        .mobile-code {{
            font-size: 32px;
            font-weight: 900;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-align: center;
            padding: 25px;
            margin: 20px 0;
            border: 3px dashed #667eea;
            border-radius: 15px;
            letter-spacing: 6px;
            font-family: 'Courier New', monospace;
        }}
        .qr-container {{
            text-align: center;
            margin: 20px 0;
            padding: 25px;
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 15px;
        }}
        .qr-container img {{
            max-width: 200px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}
        .notification {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transform: translateX(400px);
            transition: transform 0.3s ease;
            z-index: 10000;
            max-width: 300px;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: normal;
            line-height: 1.4;
        }}
        .notification.show {{
            transform: translateX(0);
        }}
        .notification.success {{ border-left: 4px solid #27ae60; }}
        .notification.error {{ border-left: 4px solid #e74c3c; }}
        @media (max-width: 768px) {{
            .grid {{ grid-template-columns: 1fr; gap: 20px; }}
            .card {{ padding: 20px; }}
            .mobile-code {{ font-size: 24px; letter-spacing: 4px; }}
            .notification {{
                right: 10px;
                left: 10px;
                max-width: none;
                transform: translateY(-100px);
            }}
            .notification.show {{
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="navbar-content">
            <div class="logo">🚀 Fshare Mobile</div>
            <div class="server-controls">
                <div class="status-badge" id="serverStatus">🟢 Server Online</div>
                <button class="toggle-btn" onclick="toggleServer()" id="toggleBtn">
                    📴 Go Offline
                </button>
            </div>
        </div>
    </nav>
    
    <div class="container">
        <div class="hero">
            <h1>📱 Mobile File Sharing</h1>
            <p>Fast, secure file transfers with QR codes</p>
        </div>
        
        <div class="connection-info">
            <h3>📡 Connection URLs</h3>
            <div><strong>🖥️ Desktop (This Computer):</strong></div>
            <div class="connection-url">http://127.0.0.1:{current_port}</div>
            <div><strong>📱 Mobile A (Same WiFi):</strong></div>
            <div class="connection-url">http://{local_ip}:{current_port}/mobile/upload</div>
            <div><strong>📱 Mobile B (Any Network):</strong></div>
            <div class="connection-url" id="publicUrl">https://b3ee162fe3cb.ngrok-free.app/mobile/upload</div>
            <div style="margin-top: 15px;">
                <small style="color: #7f8c8d;">
                    <strong>💡 Note:</strong> Different URLs for different devices:<br>
                    • localhost = Same computer only<br>
                    • Local IP = Same WiFi only<br>
                    • Ngrok URL = Works from anywhere!
                </small>
            </div>
        </div>
        
        <div class="transfer-monitor">
            <h3>📊 Active File Transfers</h3>
            <div class="transfer-stats">
                <div class="stat-item">
                    <div class="stat-number" id="totalUploads">0</div>
                    <div>Total Uploads</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="totalDownloads">0</div>
                    <div>Total Downloads</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="activeTransfers">0</div>
                    <div>Active Now</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="serverUptime">0h 0m</div>
                    <div>Uptime</div>
                </div>
            </div>
            
            <h4>🔄 Current Transfers</h4>
            <div id="activeTransfersList">
                <div style="text-align: center; color: #7f8c8d; padding: 20px;">
                    No active transfers
                </div>
            </div>
            
            <h4>✅ Recent Transfers</h4>
            <div id="recentTransfersList">
                <div style="text-align: center; color: #7f8c8d; padding: 20px;">
                    No recent transfers
                </div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📤</div>
                    <div><h3>Send to Mobile</h3></div>
                </div>
                <input type="file" id="mobileFileInput" class="form-control" />
                <button class="btn" onclick="generateMobileQR()">
                    📱 Generate QR Code
                </button>
                <div id="mobileQRContainer"></div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📥</div>
                    <div><h3>Receive from Mobile</h3></div>
                </div>
                <button class="btn btn-success" onclick="generateMobileCode()">
                    🔢 Generate 6-Digit Code
                </button>
                <div id="mobileCode"></div>
                <div id="mobileInstructions"></div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📂</div>
                    <div><h3>Browse Mobile Downloads</h3></div>
                </div>
                <p style="color: #7f8c8d; margin-bottom: 20px;">
                    View and download files received from mobile devices
                </p>
                <a href="/mobile/downloads" class="btn" style="text-decoration: none; display: block; text-align: center;">
                    📁 Open Downloads Folder
                </a>
            </div>
        </div>
    </div>
    
    <script>
        function showNotification(message, type = 'info') {{
            const notification = document.createElement('div');
            notification.className = `notification ${{type}}`;
            notification.innerHTML = `<strong>${{type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}}</strong> ${{message}}`;
            document.body.appendChild(notification);
            
            setTimeout(() => notification.classList.add('show'), 100);
            setTimeout(() => {{
                notification.classList.remove('show');
                setTimeout(() => {{
                    if (document.body.contains(notification)) {{
                        document.body.removeChild(notification);
                    }}
                }}, 300);
            }}, 4000);
        }}
        
        async function generateMobileCode() {{
            try {{
                showNotification('Generating mobile code...', 'info');
                const response = await fetch('/api/mobile/generate-code', {{ method: 'POST' }});
                const result = await response.json();
                
                if (result.success) {{
                    document.getElementById('mobileCode').innerHTML = `<div class="mobile-code">${{result.code}}</div>`;
                    document.getElementById('mobileInstructions').innerHTML = `
                        <div style="text-align: center; color: #7f8c8d; margin-top: 15px;">
                            <strong>📋 Instructions:</strong><br>
                            1. Open mobile browser<br>
                            2. Go to: <strong>http://{local_ip}:{current_port}/mobile/upload</strong><br>
                            3. Enter code: <strong>${{result.code}}</strong><br>
                            4. Upload files!<br>
                            <small style="color: #e74c3c;">⏰ Expires in 30 minutes</small>
                        </div>
                    `;
                    showNotification('Mobile code generated!', 'success');
                }} else {{
                    throw new Error(result.message || 'Failed to generate code');
                }}
            }} catch (error) {{
                showNotification('Failed to generate mobile code', 'error');
            }}
        }}
        
        async function generateMobileQR() {{
            const fileInput = document.getElementById('mobileFileInput');
            
            if (!fileInput.files[0]) {{
                showNotification('Please select a file first', 'error');
                return;
            }}
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            try {{
                showNotification('Generating QR code...', 'info');
                const response = await fetch('/api/mobile/generate-download-qr', {{
                    method: 'POST',
                    body: formData
                }});
                const result = await response.json();
                
                if (result.success) {{
                    document.getElementById('mobileQRContainer').innerHTML = `
                        <div class="qr-container">
                            <h4>📱 Scan with Mobile</h4>
                            <img src="/api/mobile/download-qr?file_id=${{result.file_id}}" alt="QR Code" />
                            <p style="margin-top: 15px; color: #7f8c8d; font-size: 14px;">
                                📄 <strong>${{result.filename}}</strong><br>
                                ⏰ Auto-expires in 30 minutes<br>
                                📲 <strong>Scan → Auto-download!</strong>
                            </p>
                        </div>
                    `;
                    showNotification('QR code generated!', 'success');
                    fileInput.value = '';
                }} else {{
                    throw new Error(result.message || 'Failed to generate QR code');
                }}
            }} catch (error) {{
                showNotification('Failed to generate QR code', 'error');
            }}
        }}
        
        // Server control functions
        async function toggleServer() {{
            try {{
                const response = await fetch('/api/server/toggle', {{ method: 'POST' }});
                const result = await response.json();
                
                const statusBadge = document.getElementById('serverStatus');
                const toggleBtn = document.getElementById('toggleBtn');
                
                if (result.status === 'online') {{
                    statusBadge.innerHTML = '🟢 Server Online';
                    statusBadge.className = 'status-badge';
                    toggleBtn.innerHTML = '📴 Go Offline';
                    showNotification('Server is now online', 'success');
                }} else {{
                    statusBadge.innerHTML = '🔴 Server Offline';
                    statusBadge.className = 'status-badge offline';
                    toggleBtn.innerHTML = '🟢 Go Online';
                    showNotification('Server is now offline', 'info');
                }}
            }} catch (error) {{
                showNotification('Failed to toggle server status', 'error');
            }}
        }}
        
        // Transfer monitoring functions
        async function updateTransferStatus() {{
            try {{
                const response = await fetch('/api/transfers/status');
                const data = await response.json();
                
                // Update stats
                document.getElementById('totalUploads').textContent = data.server_stats.total_uploads;
                document.getElementById('totalDownloads').textContent = data.server_stats.total_downloads;
                document.getElementById('activeTransfers').textContent = data.active_transfers.length;
                
                // Update uptime
                const uptime = calculateUptime(data.server_stats.uptime_start);
                document.getElementById('serverUptime').textContent = uptime;
                
                // Update active transfers
                updateActiveTransfersList(data.active_transfers);
                
                // Update recent transfers
                updateRecentTransfersList(data.recent_transfers);
                
            }} catch (error) {{
                console.error('Error updating transfer status:', error);
            }}
        }}
        
        function updateActiveTransfersList(transfers) {{
            const container = document.getElementById('activeTransfersList');
            
            if (transfers.length === 0) {{
                container.innerHTML = '<div style="text-align: center; color: #7f8c8d; padding: 20px;">No active transfers</div>';
                return;
            }}
            
            let html = '';
            transfers.forEach(transfer => {{
                const duration = Math.floor((new Date() - new Date(transfer.started_at)) / 1000);
                html += `
                    <div class="transfer-item">
                        <div>
                            <div class="loading-indicator"></div>
                            <strong>${{transfer.filename}}</strong>
                            <small> (${{transfer.type}} from ${{transfer.source}})</small>
                        </div>
                        <div style="font-size: 12px; color: #7f8c8d;">
                            ${{duration}}s ago
                        </div>
                    </div>
                `;
            }});
            container.innerHTML = html;
        }}
        
        function updateRecentTransfersList(transfers) {{
            const container = document.getElementById('recentTransfersList');
            
            if (transfers.length === 0) {{
                container.innerHTML = '<div style="text-align: center; color: #7f8c8d; padding: 20px;">No recent transfers</div>';
                return;
            }}
            
            let html = '';
            transfers.forEach(transfer => {{
                const timeAgo = getTimeAgo(transfer.completed_at);
                const sizeStr = formatFileSize(transfer.size);
                html += `
                    <div class="transfer-item completed ${{transfer.source === 'mobile' ? 'mobile' : ''}}">
                        <div>
                            <strong>${{transfer.filename}}</strong>
                            <small> (${{transfer.type}} from ${{transfer.source}}) - ${{sizeStr}}</small>
                        </div>
                        <div style="font-size: 12px; color: #7f8c8d;">
                            ✅ ${{timeAgo}}
                        </div>
                    </div>
                `;
            }});
            container.innerHTML = html;
        }}
        
        function calculateUptime(startTime) {{
            const now = new Date();
            const start = new Date(startTime);
            const diffMs = now - start;
            const hours = Math.floor(diffMs / (1000 * 60 * 60));
            const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            return `${{hours}}h ${{minutes}}m`;
        }}
        
        function getTimeAgo(timestamp) {{
            const now = new Date();
            const time = new Date(timestamp);
            const diffMs = now - time;
            const minutes = Math.floor(diffMs / (1000 * 60));
            const hours = Math.floor(minutes / 60);
            
            if (hours > 0) {{
                return `${{hours}}h ago`;
            }} else if (minutes > 0) {{
                return `${{minutes}}m ago`;
            }} else {{
                return 'Just now';
            }}
        }}
        
        function formatFileSize(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }}
        
        // Start real-time updates
        setInterval(updateTransferStatus, 2000); // Update every 2 seconds
        updateTransferStatus(); // Initial update
        
        // Show initial instructions
        showNotification('📱 Mobile URL: http://{local_ip}:{current_port}/mobile/upload', 'info');
    </script>
</body>
</html>
            """
        
        @self.app.get("/mobile/upload", response_class=HTMLResponse)
        async def mobile_upload_page(request: Request):
            """Mobile upload interface - MOBILE ONLY ACCESS"""
            local_ip = self.get_local_ip()
            current_port = self._current_port
            
            user_agent = request.headers.get("user-agent", "").lower()
            is_mobile = any(device in user_agent for device in [
                'android', 'iphone', 'ipad', 'ipod', 'blackberry', 
                'windows phone', 'mobile', 'opera mini'
            ]) or 'mobi' in user_agent
            
            
            if not is_mobile:
                return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚫 Mobile Only - Fshare</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            min-height: 100vh;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(15px);
            color: #2c3e50;
            padding: 50px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            max-width: 600px;
            text-align: center;
        }}
        .icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
        .title {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #e74c3c;
        }}
        .message {{
            font-size: 18px;
            line-height: 1.6;
            margin-bottom: 30px;
            color: #7f8c8d;
        }}
        .btn {{
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 25px;
            cursor: pointer;
            margin: 10px;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }}
        .btn:hover {{ transform: translateY(-2px); }}
        .access-info {{
            background: rgba(52, 152, 219, 0.1);
            border: 2px solid #3498db;
            color: #3498db;
            padding: 20px;
            border-radius: 15px;
            margin: 20px 0;
            text-align: left;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🚫📱</div>
        <div class="title">Mobile Only Access</div>
        <div class="message">
            This page is only accessible on mobile devices.
            <br><br>
            You're currently accessing from a desktop/laptop browser.
        </div>
        
        <div class="access-info">
            <strong>📋 How to access from mobile:</strong><br><br>
            1. Open your mobile browser<br>
            2. Go to: <strong>http://{local_ip}:{current_port}/mobile/upload</strong><br>
            3. Upload files from your mobile device<br><br>
            <strong>💡 For desktop file sharing, use:</strong><br>
            <strong>http://{local_ip}:{current_port}/</strong>
        </div>
        
        <a href="/" class="btn">🖥️ Go to Desktop Dashboard</a>
    </div>
</body>
</html>
                """
            return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📱 Fshare Mobile Upload</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            background-attachment: fixed;
            min-height: 100vh;
            color: white;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(15px);
            color: #2c3e50;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            max-width: 400px;
            width: 100%;
            text-align: center;
        }}
        .logo {{
            font-size: 32px;
            margin-bottom: 20px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .form-control {{
            width: 100%;
            padding: 15px;
            border: 2px solid #ecf0f1;
            border-radius: 12px;
            font-size: 16px;
            margin: 15px 0;
            text-align: center;
            font-family: 'Courier New', monospace;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}
        .form-control:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 20px rgba(102, 126, 234, 0.3);
        }}
        .btn {{
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 50px;
            cursor: pointer;
            margin: 10px 0;
            width: 100%;
            transition: all 0.3s ease;
        }}
        .btn:hover {{
            transform: translateY(-2px);
        }}
        .btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        .status {{
            margin: 20px 0;
            padding: 15px;
            border-radius: 12px;
            font-weight: 500;
        }}
        .status.success {{ background: rgba(39, 174, 96, 0.1); border: 2px solid #27ae60; color: #27ae60; }}
        .status.error {{ background: rgba(231, 76, 60, 0.1); border: 2px solid #e74c3c; color: #e74c3c; }}
        .status.info {{ background: rgba(52, 152, 219, 0.1); border: 2px solid #3498db; color: #3498db; }}
        .file-upload {{ display: none; }}
        .instructions {{
            background: rgba(52, 152, 219, 0.1);
            border: 2px solid #3498db;
            color: #3498db;
            padding: 15px;
            border-radius: 12px;
            margin: 20px 0;
            font-size: 14px;
            text-align: left;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🚀 Fshare Mobile</div>
        <h2>📤 Upload Files</h2>
        
        <div class="instructions">
            <strong>📋 How to upload:</strong><br>
            1. Get a 6-digit code from desktop<br>
            2. Enter the code below<br>
            3. Select and upload your files
        </div>
        
        <div id="codeSection">
            <input type="text" id="codeInput" class="form-control" placeholder="Enter 6-digit code" maxlength="6" />
            <button class="btn" onclick="verifyCode()">🔓 Verify Code</button>
        </div>
        
        <div id="uploadSection" class="file-upload">
            <h3>📁 Select Files</h3>
            <input type="file" id="fileInput" class="form-control" multiple />
            <button class="btn" onclick="uploadFiles()">📤 Upload Files</button>
        </div>
        
        <div id="status" class="status" style="display: none;"></div>
    </div>
    
    <script>
        let currentCode = '';
        
        function showStatus(message, type = 'info') {{
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
            statusDiv.style.display = 'block';
        }}
        
        async function verifyCode() {{
            const codeInput = document.getElementById('codeInput');
            const code = codeInput.value.trim().toUpperCase();
            
            if (code.length !== 6) {{
                showStatus('❌ Please enter a 6-digit code', 'error');
                return;
            }}
            
            try {{
                showStatus('🔍 Verifying code...', 'info');
                
                const response = await fetch('/api/mobile/verify-code', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ code: code }})
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    currentCode = code;
                    document.getElementById('codeSection').style.display = 'none';
                    document.getElementById('uploadSection').style.display = 'block';
                    showStatus('✅ Code verified! You can now upload files.', 'success');
                }} else {{
                    showStatus('❌ Invalid or expired code', 'error');
                    codeInput.value = '';
                }}
            }} catch (error) {{
                showStatus('❌ Connection error. Please try again.', 'error');
            }}
        }}
        
        async function uploadFiles() {{
            const fileInput = document.getElementById('fileInput');
            
            if (!fileInput.files || fileInput.files.length === 0) {{
                showStatus('📁 Please select at least one file', 'error');
                return;
            }}
            
            for (let i = 0; i < fileInput.files.length; i++) {{
                const file = fileInput.files[i];
                await uploadSingleFile(file, i + 1, fileInput.files.length);
            }}
        }}
        
        async function uploadSingleFile(file, current, total) {{
            const formData = new FormData();
            formData.append('file', file);
            formData.append('code', currentCode);
            
            try {{
                showStatus(`📤 Uploading ${{current}}/${{total}}: ${{file.name}}...`, 'info');
                
                const response = await fetch('/api/mobile/upload', {{
                    method: 'POST',
                    body: formData
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    showStatus(`✅ ${{current}}/${{total}} uploaded: ${{file.name}}`, 'success');
                }} else {{
                    showStatus(`❌ Failed to upload: ${{file.name}}`, 'error');
                }}
            }} catch (error) {{
                showStatus(`❌ Upload failed: ${{file.name}}`, 'error');
            }}
            
            await new Promise(resolve => setTimeout(resolve, 500));
        }}
        
        // Auto-format code input
        document.getElementById('codeInput').addEventListener('input', function(e) {{
            e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
            if (e.target.value.length === 6) {{
                verifyCode();
            }}
        }});
        
        // Enter key support
        document.getElementById('codeInput').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                verifyCode();
            }}
        }});
    </script>
</body>
</html>
            """
        
        # API Endpoints
        @self.app.post("/api/mobile/generate-code")
        async def generate_mobile_code():
            """Generate 6-digit code for mobile upload"""
            try:
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                
                self.mobile_connections[code] = {
                    "created_at": datetime.now(),
                    "expires_in": 1800,  
                    "type": "receive",
                    "status": "active"
                }
                
                return {
                    "success": True,
                    "code": code,
                    "expires_in": 1800
                }
            except Exception as e:
                return {"success": False, "message": str(e)}
        
        @self.app.post("/api/mobile/verify-code")
        async def verify_mobile_code(request: Request):
            """Verify 6-digit mobile code"""
            try:
                body = await request.json()
                code = body.get('code', '').upper()
                
                if code in self.mobile_connections:
                    connection_info = self.mobile_connections[code]
                    created_time = connection_info.get('created_at')
                    
                    if isinstance(created_time, datetime):
                        if datetime.now() - created_time < timedelta(minutes=30):
                            return {"success": True, "message": "Code verified"}
                        else:
                            del self.mobile_connections[code]
                            return {"success": False, "message": "Code expired"}
                    
                return {"success": False, "message": "Invalid code"}
            except Exception as e:
                return {"success": False, "message": str(e)}
        
        @self.app.post("/api/mobile/upload")
        async def mobile_file_upload(file: UploadFile = File(...), code: str = Form(...)):
            """Handle mobile file upload - saves to Downloads folder"""
            try:
                code = code.upper()
                
                if code not in self.mobile_connections:
                    raise HTTPException(status_code=400, detail="Invalid or expired code")
                
                connection_info = self.mobile_connections[code]
                created_time = connection_info.get('created_at')
                
                if isinstance(created_time, datetime):
                    if datetime.now() - created_time >= timedelta(minutes=30):
                        del self.mobile_connections[code]
                        raise HTTPException(status_code=400, detail="Code expired")
                
               
                downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                if not os.path.exists(downloads_dir):
                    downloads_dir = os.getcwd() 
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"mobile_{timestamp}_{file.filename}"
                file_path = os.path.join(downloads_dir, safe_filename)
                
            
                upload_dir = "mobile_uploads"
                os.makedirs(upload_dir, exist_ok=True)
                backup_path = os.path.join(upload_dir, safe_filename)
                
                
                transfer_id = secrets.token_urlsafe(8)
                self.add_transfer(transfer_id, "upload", file.filename, "mobile")
                
                content = await file.read()
                
                
                with open(file_path, "wb") as buffer:
                    buffer.write(content)
                
               
                with open(backup_path, "wb") as buffer:
                    buffer.write(content)
                
                
                self.complete_transfer(transfer_id, len(content))
                
                print(f"📱 Mobile upload: {file.filename} ({len(content)} bytes) via code {code}")
                print(f"💾 Saved to Downloads: {file_path}")
                print(f"💾 Backup saved to: {backup_path}")
                
                return {
                    "success": True,
                    "message": f"File '{file.filename}' uploaded successfully to Downloads folder!",
                    "filename": file.filename,
                    "size": len(content),
                    "saved_to": "Downloads folder"
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/mobile/generate-download-qr")
        async def generate_download_qr(file: UploadFile = File(...)):
            """Generate QR code for mobile download"""
            try:
                download_dir = "mobile_downloads"
                
                file_id = secrets.token_urlsafe(16)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"{timestamp}_{file.filename}"
                file_path = os.path.join(download_dir, f"{file_id}_{safe_filename}")
                
                with open(file_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                self.active_qr_codes[file_id] = {
                    "filename": file.filename,
                    "file_path": file_path,
                    "created_at": datetime.now(),
                    "expires_in": 1800,  
                    "downloads": 0,
                    "max_downloads": 10
                }
                
                print(f"📱 Generated QR for: {file.filename} (ID: {file_id})")
                
                return {
                    "success": True,
                    "file_id": file_id,
                    "filename": file.filename,
                    "expires_in": 1800
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/mobile/download-qr")
        async def get_download_qr_code(file_id: str):
            """Generate QR code image"""
            try:
                if file_id not in self.active_qr_codes:
                    raise HTTPException(status_code=404, detail="File not found")
                
                file_info = self.active_qr_codes[file_id]
                created_time = file_info.get('created_at')
                if isinstance(created_time, datetime):
                    if datetime.now() - created_time >= timedelta(minutes=30):
                        if os.path.exists(file_info['file_path']):
                            os.remove(file_info['file_path'])
                        del self.active_qr_codes[file_id]
                        raise HTTPException(status_code=404, detail="File expired")
                
                local_ip = self.get_local_ip()
                download_url = f"http://{local_ip}:{self._current_port}/mobile/download/{file_id}"
                
                qr = qrcode.QRCode(version=1, box_size=12, border=4)
                qr.add_data(download_url)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                return StreamingResponse(img_buffer, media_type="image/png")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/mobile/download/{file_id}", response_class=HTMLResponse)
        async def mobile_download_page(file_id: str):
            """Mobile download page with auto-download"""
            try:
                if file_id not in self.active_qr_codes:
                    return """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>File Not Found</title>
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
                            .container { background: white; padding: 40px; border-radius: 20px; max-width: 400px; margin: 0 auto; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h2>❌ File Not Found</h2>
                            <p>This file has expired or been removed.</p>
                        </div>
                    </body>
                    </html>
                    """
                
                file_info = self.active_qr_codes[file_id]
                filename = file_info["filename"]
                
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Download {filename}</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <style>
                        body {{
                            font-family: 'Segoe UI', Arial, sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            background-attachment: fixed;
                            color: white;
                            margin: 0;
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            padding: 20px;
                        }}
                        .container {{
                            background: rgba(255, 255, 255, 0.95);
                            backdrop-filter: blur(10px);
                            color: #2c3e50;
                            padding: 50px 40px;
                            border-radius: 25px;
                            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
                            max-width: 450px;
                            width: 100%;
                            text-align: center;
                        }}
                        .file-icon {{
                            font-size: 80px;
                            margin-bottom: 25px;
                        }}
                        .filename {{
                            font-size: 20px;
                            font-weight: bold;
                            margin-bottom: 30px;
                            word-break: break-word;
                            color: #2c3e50;
                        }}
                        .download-btn {{
                            background: linear-gradient(45deg, #3498db, #2980b9);
                            color: white;
                            border: none;
                            padding: 18px 40px;
                            font-size: 18px;
                            font-weight: bold;
                            border-radius: 50px;
                            cursor: pointer;
                            margin: 15px;
                            transition: all 0.3s ease;
                        }}
                        .download-btn:hover {{
                            transform: translateY(-3px);
                        }}
                        .countdown {{
                            font-size: 24px;
                            font-weight: bold;
                            color: #e74c3c;
                            margin: 15px 0;
                        }}
                        .progress-bar {{
                            width: 100%;
                            height: 6px;
                            background: rgba(52, 152, 219, 0.2);
                            border-radius: 3px;
                            margin: 20px 0;
                            overflow: hidden;
                        }}
                        .progress-fill {{
                            height: 100%;
                            background: linear-gradient(45deg, #3498db, #2980b9);
                            border-radius: 3px;
                            width: 0%;
                            animation: progressFill 3s ease-out forwards;
                        }}
                        @keyframes progressFill {{
                            to {{ width: 100%; }}
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="file-icon">📁</div>
                        <div class="filename">{filename}</div>
                        
                        <div class="progress-bar">
                            <div class="progress-fill"></div>
                        </div>
                        
                        <div class="countdown" id="countdown">3</div>
                        
                        <button class="download-btn" onclick="downloadFile()" id="downloadBtn">
                            📥 Download File
                        </button>
                        
                        <div id="statusText">Download will start automatically...</div>
                    </div>
                    
                    <script>
                        let countdownValue = 3;
                        let downloadStarted = false;
                        
                        function updateCountdown() {{
                            const countdownEl = document.getElementById('countdown');
                            const statusEl = document.getElementById('statusText');
                            
                            if (countdownValue > 0) {{
                                countdownEl.textContent = countdownValue;
                                statusEl.textContent = `Download starts in ${{countdownValue}} seconds...`;
                                countdownValue--;
                            }} else {{
                                countdownEl.style.display = 'none';
                                downloadFile();
                            }}
                        }}
                        
                        function downloadFile() {{
                            if (downloadStarted) return;
                            downloadStarted = true;
                            
                            const btn = document.getElementById('downloadBtn');
                            const statusText = document.getElementById('statusText');
                            
                            btn.innerHTML = '⏳ Starting Download...';
                            btn.style.background = 'linear-gradient(45deg, #27ae60, #2ecc71)';
                            statusText.textContent = 'Preparing your download...';
                            
                            // Start download
                            window.location.href = '/api/mobile/download/{file_id}';
                            
                            // Show success message
                            setTimeout(() => {{
                                btn.innerHTML = '✅ Download Started!';
                                statusText.textContent = 'File is downloading to your device!';
                            }}, 1000);
                        }}
                        
                        // Start countdown
                        const countdownInterval = setInterval(updateCountdown, 1000);
                        
                        // Start download on any interaction
                        document.addEventListener('click', function() {{
                            if (!downloadStarted) {{
                                clearInterval(countdownInterval);
                                downloadFile();
                            }}
                        }});
                        
                        document.addEventListener('touchstart', function() {{
                            if (!downloadStarted) {{
                                clearInterval(countdownInterval);
                                downloadFile();
                            }}
                        }});
                    </script>
                </body>
                </html>
                """
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/mobile/download/{file_id}")
        async def mobile_file_download(file_id: str):
            """Download file endpoint"""
            try:
                if file_id not in self.active_qr_codes:
                    raise HTTPException(status_code=404, detail="File not found")
                
                file_info = self.active_qr_codes[file_id]
                
                if file_info["downloads"] >= file_info["max_downloads"]:
                    raise HTTPException(status_code=410, detail="Download limit exceeded")
                
                if not os.path.exists(file_info["file_path"]):
                    raise HTTPException(status_code=404, detail="File not found")
                
                
                transfer_id = secrets.token_urlsafe(8)
                self.add_transfer(transfer_id, "download", file_info["filename"], "mobile")
                
                file_info["downloads"] += 1
                
                # Get file size
                file_size = os.path.getsize(file_info["file_path"])
                self.complete_transfer(transfer_id, file_size)
                
                print(f"📥 Mobile download: {file_info['filename']} (Download #{file_info['downloads']})")
                
                return FileResponse(
                    path=file_info["file_path"],
                    filename=file_info["filename"],
                    media_type='application/octet-stream'
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
      
        @self.app.get("/mobile/downloads", response_class=HTMLResponse)
        async def browse_mobile_downloads():
            """Browse files in mobile_downloads folder"""
            try:
                downloads_dir = "mobile_downloads"
                
                if not os.path.exists(downloads_dir):
                    os.makedirs(downloads_dir, exist_ok=True)
                    files = []
                else:
                    files = [f for f in os.listdir(downloads_dir) if os.path.isfile(os.path.join(downloads_dir, f))]
                
                local_ip = self.get_local_ip()
                current_port = self._current_port
                
                files_html = ""
                if files:
                    for filename in sorted(files):
                        file_path = os.path.join(downloads_dir, filename)
                        file_size = os.path.getsize(file_path)
                        file_size_str = self.format_file_size(file_size)
                        
                        files_html += f"""
                        <div class="file-item">
                            <div class="file-info">
                                <div class="filename">📄 {filename}</div>
                                <div class="filesize">{file_size_str}</div>
                            </div>
                            <a href="/download/mobile/{filename}" class="download-btn">📥 Download</a>
                        </div>
                        """
                else:
                    files_html = '<div class="no-files">📭 No files in mobile downloads folder</div>'
                
                return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📂 Mobile Downloads - Fshare</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            background-attachment: fixed;
            min-height: 100vh;
            color: #333;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(15px);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .title {{
            font-size: 28px;
            font-weight: bold;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #7f8c8d;
            font-size: 16px;
        }}
        .file-item {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
        }}
        .file-item:hover {{
            background: #e9ecef;
            transform: translateY(-2px);
        }}
        .file-info {{
            flex: 1;
        }}
        .filename {{
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 5px;
        }}
        .filesize {{
            font-size: 14px;
            color: #7f8c8d;
        }}
        .download-btn {{
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
            border: none;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 25px;
            text-decoration: none;
            transition: all 0.3s ease;
        }}
        .download-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(39, 174, 96, 0.4);
        }}
        .no-files {{
            text-align: center;
            color: #7f8c8d;
            font-size: 18px;
            padding: 40px;
        }}
        .back-btn {{
            background: linear-gradient(45deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 25px;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }}
        .back-btn:hover {{
            transform: translateY(-2px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-btn">🏠 Back to Dashboard</a>
        
        <div class="header">
            <div class="title">📂 Mobile Downloads</div>
            <div class="subtitle">Files received from mobile devices</div>
        </div>
        
        <div class="files-list">
            {files_html}
        </div>
    </div>
</body>
</html>
                """
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/download/mobile/{filename}")
        async def download_mobile_file(filename: str):
            """Download file from mobile_downloads folder - triggers browser download"""
            try:
                downloads_dir = "mobile_downloads"
                file_path = os.path.join(downloads_dir, filename)
                
                if not os.path.exists(file_path):
                    raise HTTPException(status_code=404, detail="File not found")
                
               
                transfer_id = secrets.token_urlsafe(8)
                self.add_transfer(transfer_id, "download", filename, "browser")
              
                file_size = os.path.getsize(file_path)
                self.complete_transfer(transfer_id, file_size)
                
                print(f"💻 Browser download: {filename} ({file_size} bytes)")
                
             
                return FileResponse(
                    path=file_path,
                    filename=filename,
                    media_type='application/octet-stream'
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    
        @self.app.post("/api/server/toggle")
        async def toggle_server_status():
            """Toggle server online/offline status"""
            try:
                new_status = self.toggle_server_status()
                return {
                    "success": True,
                    "status": new_status,
                    "message": f"Server is now {new_status}"
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/server/status")
        async def get_server_status():
            """Get current server status"""
            try:
                return {
                    "status": self.server_status,
                    "stats": self.server_stats.copy(),
                    "uptime": (datetime.now() - self.server_stats["uptime_start"]).total_seconds()
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/transfers/status")
        async def get_transfer_status():
            """Get real-time transfer status"""
            try:
                summary = self.get_transfer_summary()
                
             
                uptime_seconds = (datetime.now() - self.server_stats["uptime_start"]).total_seconds()
                summary["server_stats"]["uptime_formatted"] = f"{int(uptime_seconds//3600)}h {int((uptime_seconds%3600)//60)}m"
                
                return summary
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/transfers/active")
        async def get_active_transfers():
            """Get only active transfers"""
            try:
                return {
                    "active_transfers": list(self.active_transfers.values()),
                    "count": len(self.active_transfers)
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/transfers/recent")
        async def get_recent_transfers():
            """Get recent completed transfers"""
            try:
                return {
                    "recent_transfers": self.recent_transfers[:10],
                    "count": len(self.recent_transfers)
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def format_file_size(self, bytes):
        """Format file size in human-readable format"""
        if bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(bytes, 1024)))
        p = math.pow(1024, i)
        s = round(bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def find_available_port(self, start_port=8001, max_attempts=10):
        """Find available port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", port))
                sock.close()
                return port
            except OSError:
                continue
        raise Exception(f"No available ports found between {start_port} and {start_port + max_attempts - 1}")
    
    def start_server(self, host="0.0.0.0", port=8001):
        """Start the server"""
        local_ip = self.get_local_ip()
        time.sleep(2)
        
        try:
            available_port = self.find_available_port(port)
            if available_port != port:
                print(f"⚠️  Port {port} busy, using port {available_port}")
                port = available_port
        except Exception as e:
            print(f"❌ Error finding port: {e}")
            return
        
        self._current_port = port
        
        # Get local IP for network info
        print("🔍 Detecting network configuration...")
        
        print(f"🌐 Starting Fshare Mobile API (CORS Enabled)")
        print(f"🔗 Desktop: http://127.0.0.1:{port}")
        print(f"🏠 Local Network: http://{local_ip}:{port}/mobile/upload")
        print(f"💡 For cross-network access, use ngrok tunnel")
        print(f"🧹 Auto-cleanup: 30 minutes")
        
        try:
            import logging
            
            uvicorn_logger = logging.getLogger("uvicorn")
            uvicorn_logger.setLevel(logging.WARNING)
            
            
            print(f"🚀 Starting server on all network interfaces")
            print(f"📍 Local access: http://127.0.0.1:{port}")
            print(f"🌐 Network access: http://{local_ip}:{port}")
            print(f"📱 Mobile upload: http://{local_ip}:{port}/mobile/upload")
            print(f"🔥 Server running successfully! (Press CTRL+C to quit)")
            
            uvicorn.run(
                self.app, 
                host=host, 
                port=port, 
                log_level="warning"
            )
        except KeyboardInterrupt:
            print("\n🔴 Server stopped by user")
        except Exception as e:
            print(f"❌ Server failed: {e}")
            raise

def main():
    """Main entry point"""
    web_api = FshareWebAPI()
    web_api.start_server()

if __name__ == "__main__":
    main()
