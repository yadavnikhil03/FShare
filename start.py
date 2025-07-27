#!/usr/bin/env python3
"""
🚀 Fshare Mobile & Remote Access Server
Starts FastAPI web server with ngrok tunnel for mobile/remote device access
This is DIFFERENT from main.py (desktop software)
"""

import subprocess
import sys
import time
import os
import shutil

def check_ngrok():
    if os.path.exists("ngrok.exe"):
        print("✅ Found local ngrok.exe")
        return "ngrok.exe"
    
    # Check common installation paths
    common_paths = [
        "C:\\Program Files\\ngrok\\ngrok.exe",
        "C:\\Program Files (x86)\\ngrok\\ngrok.exe", 
        "C:\\Windows\\System32\\ngrok.exe",
        "C:\\ngrok\\ngrok.exe",
        os.path.expanduser("~/AppData/Local/ngrok/ngrok.exe"),
        os.path.expanduser("~/Downloads/ngrok.exe")
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"✅ Found system ngrok: {path}")
            return path
    
    # Check system ngrok
    if shutil.which("ngrok"):
        ngrok_path = shutil.which("ngrok")
        print(f"✅ Found ngrok in PATH: {ngrok_path}")
        return "ngrok"
    
    return None

def fix_antivirus_instructions():
    """Show how to fix Windows Defender blocking ngrok"""
    print("\n" + "🛡️" * 30)
    print("WINDOWS DEFENDER IS BLOCKING NGROK!")
    print("🛡️" * 30)
    print("\n📋 QUICK FIX STEPS:")
    print("1. Open Windows Security (Win + I)")
    print("2. Go to 'Virus & threat protection'")
    print("3. Click 'Manage settings'")
    print("4. Click 'Add or remove exclusions'")
    print("5. Add this folder as exclusion:")
    print(f"   📁 {os.getcwd()}")
    print("\n🔄 Then restart this script!")
    print("🛡️" * 30)

def fix_ngrok_installation():
    """Show how to properly install ngrok when config exists but exe is missing"""
    print("\n" + "�" * 40)
    print("NGROK CONFIG FOUND BUT EXECUTABLE MISSING!")
    print("�" * 40)
    print(f"✅ Found ngrok config: {os.getcwd()}/ngrok.yml")
    print("❌ But ngrok.exe is missing")
    print("\n� DOWNLOAD & INSTALL STEPS:")
    print("1. Go to: https://ngrok.com/download")
    print("2. Download Windows version (zip file)")
    print("3. Extract ngrok.exe")
    print("4. Choose ONE option:")
    print(f"   A) Copy ngrok.exe to: {os.getcwd()}")
    print("   B) Copy to C:\\Windows\\System32\\ (requires admin)")
    print("   C) Add ngrok folder to Windows PATH")
    print("\n🔄 Then restart this script!")
    print("�" * 40)

def start_ngrok_safely(ngrok_cmd):
    """Start ngrok with proper error handling and config support"""
    try:
        print("2. Starting ngrok tunnel...")
        
        # Use config file if it exists
        if os.path.exists("ngrok.yml"):
            print("📋 Using ngrok.yml configuration...")
            tunnel_process = subprocess.Popen([ngrok_cmd, "start", "fshare", "--config", "ngrok.yml"])
        else:
            # Fallback to direct HTTP tunnel
            tunnel_process = subprocess.Popen([ngrok_cmd, "http", "8001"])
            
        return tunnel_process
    except OSError as e:
        if "225" in str(e) or "virus" in str(e).lower():
            print("❌ ANTIVIRUS/WINDOWS DEFENDER BLOCKED NGROK!")
            fix_antivirus_instructions()
            return None
        else:
            print(f"❌ Error starting ngrok: {e}")
            return None

def main():
    print("🚀 Starting Fshare Mobile & Remote Access Server")
    print("📱 This enables mobile and internet access to Fshare")
    print("🖥️  For desktop software, use: python main.py")
    print("=" * 60)
    

    if not os.path.exists("web_api.py"):
        print("❌ web_api.py not found!")
        print("   This script needs the web API server file")
        return False
    
  
    ngrok_cmd = check_ngrok()
    if not ngrok_cmd:
        # Check if config exists (means ngrok was installed before)
        if os.path.exists("ngrok.yml"):
            fix_ngrok_installation()
        else:
            print("❌ ngrok not found!")
            print("📥 Download from: https://ngrok.com/download")
            print("📁 Place ngrok.exe in this folder:")
            print(f"   {os.getcwd()}")
        return False
    
    print(f"✅ Found ngrok: {ngrok_cmd}")
    print("📋 Starting mobile access services...")
    
    # Start FastAPI server
    print("1. Starting FastAPI web server...")
    server_process = subprocess.Popen([sys.executable, "web_api.py"])
    
    time.sleep(5)
    
    
    tunnel_process = start_ngrok_safely(ngrok_cmd)
    
    if tunnel_process is None:
        print("❌ Failed to start ngrok tunnel")
        print("🔄 Server is still running locally")
        print("🌐 Local access only: http://127.0.0.1:8001")
        server_process.terminate()
        return False
    
    print("\n" + "=" * 60)
    print("✅ FSHARE MOBILE & REMOTE ACCESS STARTED!")
    print("=" * 60)
    print("🖥️  Local Desktop: http://127.0.0.1:8001")
    print("📱 Local Mobile: http://192.168.1.XXX:8001/mobile/upload")
    print("🌐 Remote/Internet: Check ngrok terminal for public URL")
    print("   Example: https://abc123.ngrok.io/mobile/upload")
    print("\n📋 MOBILE FEATURES:")
    print("   • Upload files from phone browser")
    print("   • Download files to phone")
    print("   • Works from anywhere with internet")
    print("   • Share ngrok URL with others")
    print("\n💡 Keep BOTH terminals open!")
    print("   Press Ctrl+C in each terminal to stop")
    print("🖥️  For desktop software: python main.py")
    print("=" * 60)
    
    try:
       
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        server_process.terminate()
        tunnel_process.terminate()
        print("✅ Services stopped")
    
    return True

if __name__ == "__main__":
    main()
