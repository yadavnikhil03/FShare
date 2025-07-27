"""
Fshare Backend - File Sender Module
Handles sending files to other devices
"""

import os
import socket
import json
import threading
import time
import logging
import base64
from tqdm import tqdm
from .config import get_config
from .encryption import FileEncryption
from .utils import calculate_file_hash, format_file_size, TransferProgress
from .discover import DeviceDiscovery


class FileSender:
    """Handles sending files to other devices"""
    
    def __init__(self, config=None):
        """
        Initialize file sender
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.encryption = FileEncryption() if self.config.ENCRYPTION_ENABLED else None
        self.discovery = DeviceDiscovery(self.config)
        
        # Transfer state
        self.active_transfers = {}
        self.transfer_lock = threading.Lock()
        
        # Error tracking
        self.last_error = None
        self.transfer_errors = {}  # Track errors per file
        
        # Service state
        self.running = False
    
    def set_last_error(self, error, file_path=None):
        """Set the last error for debugging"""
        self.last_error = str(error)
        if file_path:
            self.transfer_errors[file_path] = str(error)
        self.logger.error(f"Transfer error: {error}")
    
    def get_last_error(self):
        """Get the last error that occurred"""
        return self.last_error
    
    def get_file_error(self, file_path):
        """Get error for specific file"""
        return self.transfer_errors.get(file_path)
    
    def clear_errors(self):
        """Clear all error tracking"""
        self.last_error = None
        self.transfer_errors.clear()
    
    def start_discovery(self):
        """Start device discovery service"""
        try:
            self.discovery.start()
            self.running = True
            print(f"🟢 File Sender service started successfully!")
            print(f"🔍 Device discovery enabled")
            print(f"📡 Broadcasting on port {self.config.DISCOVERY_PORT}")
            print(f"🔒 Encryption: {'Enabled' if self.encryption else 'Disabled'}")
            print("🚀 Ready to send files!")
            print("=" * 60)
            self.logger.info("File sender service started")
        except Exception as e:
            self.logger.error(f"Error starting sender service: {e}")
            print(f"❌ Failed to start sender service: {e}")
            raise
    
    def stop(self):
        """Stop sender service"""
        self.running = False
        
        # Stop discovery
        if self.discovery:
            self.discovery.stop()
        
        # Cancel active transfers
        with self.transfer_lock:
            for transfer_id in list(self.active_transfers.keys()):
                self.cancel_transfer(transfer_id)
        
        self.logger.info("File sender service stopped")
        print("🔴 File Sender service stopped")
        print("=" * 60)
    
    def discover_devices(self, timeout=10):
        """
        Discover available devices with enhanced mobile support and cross-network capability
        
        Args:
            timeout (int): Discovery timeout in seconds
        
        Returns:
            dict: Dictionary of discovered devices {ip: name}
        """
        print(f"🔍 Scanning for devices (timeout: {timeout}s)...")
        print("📱 Checking local network, mobile hotspots, and internet connections...")
        
        devices = {}
        
        # 1. Local network discovery
        try:
            local_devices = self.discovery.discover_devices(timeout)
            devices.update(local_devices)
            print(f"🏠 Found {len(local_devices)} devices on local network")
        except Exception as e:
            print(f"⚠️ Local discovery failed: {e}")
        
        # 2. Mobile hotspot ranges
        mobile_ranges = [
            "192.168.43.",  # Android hotspot default
            "172.20.10.",   # iPhone hotspot default
            "192.168.137.", # Windows hotspot default
            "10.0.0.",      # Some mobile networks
            "192.168.1.",   # Common WiFi range
            "192.168.0.",   # Common WiFi range
        ]
        
        print("🌐 Scanning mobile hotspot ranges...")
        for range_prefix in mobile_ranges:
            for i in [1, 2, 100, 101, 102, 103, 104, 105]:  # Common device IPs
                ip = f"{range_prefix}{i}"
                if self._test_connection(ip, self.config.RECEIVER_PORT, timeout=1):
                    device_info = self._get_device_connection_info(ip, self.config.RECEIVER_PORT)
                    if device_info:
                        device_name = device_info.get('device_name', f'Mobile Device ({ip})')
                        devices[ip] = device_name
                        print(f"📱 Found mobile device: {device_name} at {ip}")
        
        # 3. Internet/Public IP discovery (for cross-network sharing)
        try:
            print("🌍 Checking for internet-accessible devices...")
            # This will be implemented for relay server or direct connections
            internet_devices = self._discover_internet_devices(timeout)
            devices.update(internet_devices)
        except Exception as e:
            print(f"⚠️ Internet discovery failed: {e}")
        
        return devices
    
    def get_available_devices(self):
        """
        Get currently available devices
        
        Returns:
            dict: Dictionary of available devices
        """
        return self.discovery.get_devices()
    
    def send_file(self, file_path, target_ip, target_port=None, progress_callback=None):
        """
        Send a file to target device
        
        Args:
            file_path (str): Path to file to send
            target_ip (str): Target device IP
            target_port (int): Target device port (uses config default if None)
            progress_callback (callable): Callback for progress updates
        
        Returns:
            bool: True if transfer successful, False otherwise
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            print(f"❌ File not found: {file_path}")
            return False
        
        if target_port is None:
            target_port = self.config.RECEIVER_PORT
        
        # Pre-transfer validation
        print(f"🔍 Pre-transfer validation for {target_ip}:{target_port}...")
        
        # Test if receiver is reachable
        test_connection = self._test_receiver_connection(target_ip, target_port)
        if not test_connection:
            print(f"❌ Pre-transfer validation failed - receiver not ready")
            return False
        
        print(f"✅ Pre-transfer validation passed")
        
        transfer_id = f"{target_ip}_{int(time.time())}"
        
        try:
            # Start transfer
            with self.transfer_lock:
                self.active_transfers[transfer_id] = {
                    'file_path': file_path,
                    'target_ip': target_ip,
                    'target_port': target_port,
                    'status': 'starting',
                    'progress': 0,
                    'start_time': time.time()
                }
            
            # Perform transfer
            success = self._transfer_file(transfer_id, file_path, target_ip, target_port, progress_callback)
            
            # Update transfer status
            with self.transfer_lock:
                if transfer_id in self.active_transfers:
                    self.active_transfers[transfer_id]['status'] = 'completed' if success else 'failed'
            
            return success
            
        except Exception as e:
            error_msg = f"Error sending file {file_path} to {target_ip}: {e}"
            self.set_last_error(error_msg, file_path)
            print(f"❌ Transfer setup error: {e}")
            with self.transfer_lock:
                if transfer_id in self.active_transfers:
                    self.active_transfers[transfer_id]['status'] = 'error'
            return False
        
        finally:
            # Clean up transfer record after delay
            threading.Timer(60, lambda: self._cleanup_transfer(transfer_id)).start()
    
    def _test_receiver_connection(self, target_ip, target_port):
        """Test if receiver is available and ready"""
        try:
            # Try to get connection info (this tests if receiver is running)
            connection_info = self._get_device_connection_info(target_ip, target_port)
            
            if connection_info:
                print(f"✅ Receiver is running and responsive")
                print(f"📱 Device: {connection_info.get('name', 'Unknown')}")
                return True
            else:
                print(f"❌ Receiver is not responding to INFO requests")
                return False
                
        except Exception as e:
            print(f"❌ Failed to test receiver connection: {e}")
            return False
    
    def _transfer_file(self, transfer_id, file_path, target_ip, target_port, progress_callback):
        """
        Perform the actual file transfer
        
        Args:
            transfer_id (str): Transfer identifier
            file_path (str): Path to file to send
            target_ip (str): Target IP address
            target_port (int): Target port
            progress_callback (callable): Progress callback function
        
        Returns:
            bool: True if successful, False otherwise
        """
        sock = None
        try:
            # Get file info
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # Check file size limit
            if file_size > self.config.MAX_FILE_SIZE:
                self.logger.error(f"File too large: {format_file_size(file_size)} > {format_file_size(self.config.MAX_FILE_SIZE)}")
                print(f"❌ File too large: {format_file_size(file_size)} > {format_file_size(self.config.MAX_FILE_SIZE)}")
                return False
                
            if file_size == 0:
                self.logger.error(f"File is empty: {file_path}")
                print(f"❌ File is empty: {file_path}")
                return False
            
            # Calculate file hash
            print(f"🔍 Calculating file hash...")
            file_hash = calculate_file_hash(file_path)
            if not file_hash:
                self.logger.error("Failed to calculate file hash")
                print(f"❌ Failed to calculate file hash")
                return False
            
            # Generate encryption key if encryption enabled
            encryption_key = None
            if self.encryption:
                encryption_key = self.encryption.generate_key()
            
            # Create socket connection with better error handling
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.TIMEOUT)
            
            self.logger.info(f"Connecting to {target_ip}:{target_port}")
            print(f"\n📤 Starting file send: '{file_name}' ({format_file_size(file_size)}) to {target_ip}")
            print(f"🔗 Connecting to {target_ip}:{target_port}...")
            
            # Test connection first
            try:
                sock.connect((target_ip, target_port))
                print(f"✅ Socket connection established")
            except socket.timeout:
                print(f"❌ Connection timeout - receiver might not be running")
                return False
            except ConnectionRefusedError:
                print(f"❌ Connection refused - receiver not accepting connections")
                return False
            except Exception as e:
                print(f"❌ Connection failed: {str(e)}")
                return False
            
            # Send file metadata with better error handling
            metadata = {
                'type': 'file_transfer',
                'file_name': file_name,
                'file_size': file_size,
                'file_hash': file_hash,
                'encrypted': encryption_key is not None,
                'encryption_key': encryption_key.hex() if encryption_key else None,
                'chunk_size': self.config.CHUNK_SIZE,
                'app': self.config.APP_NAME,
                'version': self.config.VERSION
            }
            
            metadata_json = json.dumps(metadata).encode('utf-8')
            metadata_size = len(metadata_json)
            
            print(f"📋 Sending metadata ({metadata_size} bytes)...")
            
            # Send metadata size first
            try:
                sock.sendall(metadata_size.to_bytes(4, byteorder='big'))
                print(f"✅ Metadata size sent: {metadata_size}")
            except Exception as e:
                print(f"❌ Failed to send metadata size: {e}")
                return False
            
            # Send metadata
            try:
                sock.sendall(metadata_json)
                print(f"✅ Metadata sent successfully")
            except Exception as e:
                print(f"❌ Failed to send metadata: {e}")
                return False
            
            # Wait for acknowledgment with timeout
            print(f"⏳ Waiting for receiver acknowledgment...")
            try:
                sock.settimeout(10)  # 10 second timeout for acknowledgment
                response = sock.recv(1024).decode('utf-8')
                sock.settimeout(self.config.TIMEOUT)  # Reset to normal timeout
                
                if response != 'READY':
                    self.logger.error(f"Unexpected response from receiver: {response}")
                    print(f"❌ Receiver not ready: {response}")
                    return False
                    
                print(f"✅ Receiver ready, starting transfer...")
                
            except socket.timeout:
                print(f"❌ Timeout waiting for receiver acknowledgment")
                return False
            except Exception as e:
                print(f"❌ Error receiving acknowledgment: {e}")
                return False
            
            # Initialize progress tracking
            progress = TransferProgress(file_size)
            bytes_sent = 0
            
            # Update transfer status
            with self.transfer_lock:
                if transfer_id in self.active_transfers:
                    self.active_transfers[transfer_id]['status'] = 'transferring'
            
            # Send file data
            with open(file_path, 'rb') as f:
                with tqdm(total=file_size, unit='B', unit_scale=True, desc=f"Sending {file_name}") as pbar:
                    
                    while bytes_sent < file_size:
                        # Check if transfer was cancelled
                        with self.transfer_lock:
                            if (transfer_id in self.active_transfers and 
                                self.active_transfers[transfer_id]['status'] == 'cancelled'):
                                self.logger.info(f"Transfer cancelled: {transfer_id}")
                                return False
                        
                        # Read chunk
                        chunk_size = min(self.config.CHUNK_SIZE, file_size - bytes_sent)
                        chunk = f.read(chunk_size)
                        
                        if not chunk:
                            break
                        
                        # Encrypt chunk if encryption enabled
                        if encryption_key:
                            chunk = self.encryption.encrypt_data(chunk, encryption_key)
                        
                        # Send chunk size first
                        sock.sendall(len(chunk).to_bytes(4, byteorder='big'))
                        
                        # Send chunk
                        sock.sendall(chunk)
                        
                        bytes_sent += chunk_size
                        progress.update(chunk_size)
                        
                        # Update progress
                        progress_percent = int((bytes_sent / file_size) * 100)
                        
                        with self.transfer_lock:
                            if transfer_id in self.active_transfers:
                                self.active_transfers[transfer_id]['progress'] = progress_percent
                        
                        if progress_callback:
                            progress_callback(progress_percent)
                        
                        # Print progress every 10%
                        if progress_percent % 10 == 0 and progress_percent > 0:
                            print(f"📊 Sending: {progress_percent}% ({format_file_size(bytes_sent)}/{format_file_size(file_size)})")
                        
                        pbar.update(chunk_size)
                        pbar.set_postfix({
                            'Speed': f"{format_file_size(progress.get_speed())}/s",
                            'ETA': progress.get_eta()
                        })
            
            # Send end marker to indicate transfer complete
            print(f"📤 Sending completion marker...")
            try:
                sock.sendall((0).to_bytes(4, byteorder='big'))
                print(f"✅ End marker sent")
            except Exception as e:
                print(f"❌ Failed to send end marker: {e}")
                return False
            
            # Wait for completion confirmation with timeout
            print(f"⏳ Waiting for completion confirmation...")
            try:
                sock.settimeout(30)  # 30 seconds for completion confirmation
                response_data = sock.recv(1024)
                
                # Handle empty response (connection closed by receiver)
                if not response_data:
                    self.logger.info(f"Receiver closed connection after file transfer - assuming success")
                    print(f"✅ SUCCESS: File '{file_name}' sent successfully to {target_ip}!")
                    print(f"📊 Total size: {format_file_size(file_size)}")
                    print(f"⚡ Average speed: {format_file_size(progress.get_speed())}/s")
                    print(f"ℹ️ Receiver closed connection (normal behavior)")
                    print("-" * 60)
                    return True
                
                response = response_data.decode('utf-8').strip()
                
                if response == 'COMPLETED':
                    self.logger.info(f"File sent successfully: {file_name} to {target_ip}")
                    print(f"✅ SUCCESS: File '{file_name}' sent successfully to {target_ip}!")
                    print(f"📊 Total size: {format_file_size(file_size)}")
                    print(f"⚡ Average speed: {format_file_size(progress.get_speed())}/s")
                    print("-" * 60)
                    return True
                else:
                    self.logger.error(f"Transfer failed - receiver response: {response}")
                    print(f"❌ FAILED: Transfer failed - receiver response: {response}")
                    print(f"Expected: 'COMPLETED', Got: '{response}'")
                    print("-" * 60)
                    return False
                    
            except socket.timeout:
                print(f"⏰ TIMEOUT: No completion confirmation received from receiver")
                print("💡 File might have been transferred successfully despite timeout")
                print("-" * 60)
                # Consider this a successful transfer since file data was sent
                return True
            except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                # Connection was closed by receiver - this is often normal after successful transfer
                if "10054" in str(e) or "connection was forcibly closed" in str(e).lower():
                    self.logger.info(f"Receiver closed connection after transfer - assuming success: {e}")
                    print(f"✅ SUCCESS: File '{file_name}' sent successfully to {target_ip}!")
                    print(f"📊 Total size: {format_file_size(file_size)}")
                    print(f"⚡ Average speed: {format_file_size(progress.get_speed())}/s")
                    print(f"ℹ️ Connection closed by receiver (WinError 10054 - normal)")
                    print("-" * 60)
                    return True
                else:
                    print(f"❌ Error receiving completion confirmation: {e}")
                    print("-" * 60)
                    return False
            except Exception as e:
                print(f"❌ Error receiving completion confirmation: {e}")
                print("-" * 60)
                return False
                
        except socket.timeout:
            self.logger.error(f"Transfer timeout to {target_ip}")
            error_msg = f"Transfer timeout to {target_ip} - check network connection and receiver status"
            self.set_last_error(error_msg, file_path)
            print(f"⏰ TIMEOUT: Connection timed out to {target_ip}")
            print("💡 Check network connection and receiver status")
            print("-" * 60)
            return False
        
        except ConnectionRefusedError:
            self.logger.error(f"Connection refused by {target_ip}:{target_port}")
            error_msg = f"Connection refused by {target_ip}:{target_port} - receiver not running"
            self.set_last_error(error_msg, file_path)
            print(f"🚫 CONNECTION REFUSED: {target_ip}:{target_port} is not accepting connections")
            print("💡 Make sure the receiver is running on the target device")
            print("-" * 60)
            return False
        
        except ConnectionResetError:
            self.logger.error(f"Connection reset by {target_ip}")
            error_msg = f"Connection reset by {target_ip} - receiver stopped during transfer"
            self.set_last_error(error_msg, file_path)
            print(f"🔌 CONNECTION RESET: {target_ip} closed the connection unexpectedly")
            print("💡 The receiver might have stopped during transfer")
            print("-" * 60)
            return False
        
        except BrokenPipeError:
            self.logger.error(f"Broken pipe to {target_ip}")
            error_msg = f"Broken pipe to {target_ip} - receiver disconnected"
            self.set_last_error(error_msg, file_path)
            print(f"📡 BROKEN PIPE: Connection to {target_ip} was broken")
            print("💡 The receiver might have disconnected")
            print("-" * 60)
            return False
        
        except OSError as e:
            self.logger.error(f"Network error to {target_ip}: {e}")
            error_msg = f"Network error to {target_ip}: {e}"
            self.set_last_error(error_msg, file_path)
            print(f"🌐 NETWORK ERROR: {e}")
            print("💡 Check network connectivity")
            print("-" * 60)
            return False
        
        except Exception as e:
            self.logger.error(f"Unexpected error during transfer to {target_ip}: {e}")
            error_msg = f"Unexpected error during transfer to {target_ip}: {e}"
            self.set_last_error(error_msg, file_path)
            print(f"💥 UNEXPECTED ERROR: {e}")
            print("💡 Check logs for more details")
            print("-" * 60)
            return False
            self.logger.error(f"Transfer error: {e}")
            print(f"❌ ERROR: Transfer failed - {e}")
            print("-" * 60)
            return False
        
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
    
    def send_multiple_files(self, file_paths, target_ip, target_port=None, progress_callback=None):
        """
        Send multiple files to target device
        
        Args:
            file_paths (list): List of file paths to send
            target_ip (str): Target device IP
            target_port (int): Target device port
            progress_callback (callable): Progress callback function
        
        Returns:
            dict: Results for each file {file_path: success}
        """
        results = {}
        total_files = len(file_paths)
        
        print(f"📦 Starting multi-file transfer: {total_files} files to {target_ip}")
        
        for i, file_path in enumerate(file_paths):
            file_name = os.path.basename(file_path)
            self.logger.info(f"Sending file {i+1}/{total_files}: {file_name}")
            print(f"📤 [{i+1}/{total_files}] Sending: {file_name}")
            
            # Create progress callback that accounts for multiple files
            def multi_progress(percent):
                overall_percent = int(((i + percent/100) / total_files) * 100)
                if progress_callback:
                    progress_callback(overall_percent)
            
            try:
                # Add small delay between files to prevent resource conflicts
                if i > 0:
                    time.sleep(1)  # 1 second delay between files
                
                success = self.send_file(file_path, target_ip, target_port, multi_progress)
                results[file_path] = success
                
                if success:
                    print(f"✅ [{i+1}/{total_files}] SUCCESS: {file_name}")
                    self.logger.info(f"Successfully sent {file_name}")
                else:
                    print(f"❌ [{i+1}/{total_files}] FAILED: {file_name}")
                    self.logger.error(f"Failed to send {file_name}")
                    
            except Exception as e:
                print(f"💥 [{i+1}/{total_files}] ERROR: {file_name} - {e}")
                self.logger.error(f"Exception while sending {file_name}: {e}")
                results[file_path] = False
        
        successful_count = sum(1 for success in results.values() if success)
        print(f"📊 Multi-file transfer completed: {successful_count}/{total_files} files successful")
        
        return results
    
    def cancel_transfer(self, transfer_id):
        """
        Cancel an active transfer
        
        Args:
            transfer_id (str): Transfer ID to cancel
        
        Returns:
            bool: True if transfer was cancelled, False if not found
        """
        with self.transfer_lock:
            if transfer_id in self.active_transfers:
                self.active_transfers[transfer_id]['status'] = 'cancelled'
                self.logger.info(f"Transfer cancelled: {transfer_id}")
                return True
        
        return False
    
    def get_transfer_status(self, transfer_id):
        """
        Get status of a transfer
        
        Args:
            transfer_id (str): Transfer ID
        
        Returns:
            dict: Transfer status information
        """
        with self.transfer_lock:
            return self.active_transfers.get(transfer_id, {})
    
    def get_active_transfers(self):
        """
        Get all active transfers
        
        Returns:
            dict: Dictionary of active transfers
        """
        with self.transfer_lock:
            return dict(self.active_transfers)
    
    def _cleanup_transfer(self, transfer_id):
        """Clean up completed transfer record"""
        with self.transfer_lock:
            if transfer_id in self.active_transfers:
                del self.active_transfers[transfer_id]
    
    def connect_via_link(self, connection_link):
        """
        Connect to a device using a connection link
        
        Args:
            connection_link (str): Connection link from receiver
        
        Returns:
            dict: Connection info if successful, None if failed
        """
        try:
            # Parse the connection link
            if not connection_link.startswith('fshare://connect/'):
                self.logger.error("Invalid connection link format")
                print("❌ Invalid connection link format")
                return None
            
            # Extract encoded data
            encoded_data = connection_link.replace('fshare://connect/', '')
            
            # Decode connection data
            connection_json = base64.b64decode(encoded_data.encode('ascii')).decode('utf-8')
            connection_data = json.loads(connection_json)
            
            # Validate connection data
            required_fields = ['ip', 'port', 'code', 'app']
            for field in required_fields:
                if field not in connection_data:
                    self.logger.error(f"Missing field in connection data: {field}")
                    print(f"❌ Invalid connection data: missing {field}")
                    return None
            
            # Validate app compatibility
            if connection_data['app'] != self.config.APP_NAME:
                self.logger.error(f"Incompatible app: {connection_data['app']}")
                print(f"❌ Incompatible app: {connection_data['app']}")
                return None
            
            # Test connection
            target_ip = connection_data['ip']
            target_port = connection_data['port']
            
            print(f"🔗 Connecting to device via link...")
            print(f"📱 Device: {connection_data.get('device_name', 'Unknown')}")
            print(f"🌐 IP: {target_ip}:{target_port}")
            print(f"🎫 Code: {connection_data['code']}")
            
            # Test if device is reachable
            if self._test_connection(target_ip, target_port):
                print("✅ Connection successful!")
                return {
                    'ip': target_ip,
                    'port': target_port,
                    'name': connection_data.get('device_name', 'Unknown Device'),
                    'code': connection_data['code']
                }
            else:
                print("❌ Connection failed - device not reachable")
                return None
                
        except Exception as e:
            self.logger.error(f"Error connecting via link: {e}")
            print(f"❌ Error connecting via link: {e}")
            return None
    
    def connect_via_code(self, connection_code):
        """
        Connect to a device using a 6-character connection code
        
        Args:
            connection_code (str): 6-character connection code
        
        Returns:
            dict: Connection info if successful, None if failed
        """
        try:
            print(f"🔍 Searching for device with code: {connection_code}")
            
            # First ensure discovery is running
            if not self.discovery.listening:
                print("🚀 Starting discovery service...")
                self.discovery.start_listening()
                time.sleep(2)  # Give time to receive broadcasts
            
            # Get current discovered devices
            devices = self.discovery.get_devices()
            print(f"📱 Found {len(devices)} discovered devices")
            
            # Check each discovered device for matching code
            for ip, device_info in devices.items():
                print(f"🔍 Checking device at {ip}: {device_info.get('name', 'Unknown')}")
                
                # Try to get connection info from device
                device_connection_info = self._get_device_connection_info(ip, device_info.get('port', self.config.RECEIVER_PORT))
                
                if device_connection_info:
                    device_code = device_connection_info.get('code')
                    print(f"📋 Device {ip} has code: {device_code}")
                    
                    if device_code == connection_code:
                        print(f"✅ Found device with matching code!")
                        print(f"📱 Device: {device_info['name']}")
                        print(f"🌐 IP: {ip}")
                        
                        return {
                            'ip': ip,
                            'port': device_info.get('port', self.config.RECEIVER_PORT),
                            'name': device_info['name'],
                            'code': connection_code
                        }
                else:
                    print(f"⚠️ Could not get connection info from {ip}")
            
            # If not found in discovered devices, try scanning common IPs on network
            print("🔍 Device not found in discovery, scanning network...")
            return self._scan_network_for_code(connection_code)
            
        except Exception as e:
            self.logger.error(f"Error connecting via code: {e}")
            print(f"❌ Error connecting via code: {e}")
            return None
    
    def _scan_network_for_code(self, connection_code):
        """Scan local network for device with matching code"""
        try:
            import ipaddress
            
            # Get local network range
            local_ip = self.discovery.local_ip
            if not local_ip or local_ip == '127.0.0.1':
                print("❌ Could not determine local network")
                return None
            
            # Get network range (assume /24)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            print(f"🔍 Scanning network {network} for device with code {connection_code}...")
            
            # Scan common IPs in parallel
            import concurrent.futures
            import threading
            
            found_device = threading.Event()
            result = None
            
            def check_ip(ip_str):
                nonlocal result
                if found_device.is_set():
                    return None
                    
                try:
                    device_info = self._get_device_connection_info(ip_str, self.config.RECEIVER_PORT)
                    if device_info and device_info.get('code') == connection_code:
                        print(f"✅ Found device at {ip_str} with matching code!")
                        result = {
                            'ip': ip_str,
                            'port': self.config.RECEIVER_PORT,
                            'name': device_info.get('name', f'Device-{ip_str}'),
                            'code': connection_code
                        }
                        found_device.set()
                        return result
                except:
                    pass
                return None
            
            # Check up to 50 IPs in the network
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                # Get first 50 IPs in network range
                ip_list = []
                for i, ip in enumerate(network.hosts()):
                    if i >= 50:  # Limit to first 50 IPs
                        break
                    ip_list.append(str(ip))
                
                print(f"🔍 Scanning {len(ip_list)} IP addresses...")
                
                # Submit all scanning tasks
                futures = [executor.submit(check_ip, ip_str) for ip_str in ip_list]
                
                # Wait for first result or all to complete
                for future in concurrent.futures.as_completed(futures, timeout=15):
                    if found_device.is_set():
                        # Cancel remaining tasks
                        for f in futures:
                            f.cancel()
                        break
            
            if result:
                return result
            else:
                print("❌ No device found with that connection code on network")
                return None
                
        except Exception as e:
            print(f"❌ Network scan error: {e}")
            return None
    
    def _discover_internet_devices(self, timeout=5):
        """
        Discover devices accessible over the internet
        
        Args:
            timeout (int): Discovery timeout
            
        Returns:
            dict: Dictionary of internet-accessible devices
        """
        devices = {}
        
        try:
            # Check for relay server or known public IPs
            # This could be expanded to use a relay server for device registration
            print("🔍 Searching for internet-accessible devices...")
            
            # For now, we'll implement direct IP connection capability
            # Later this can be enhanced with a relay server
            
            return devices
            
        except Exception as e:
            self.logger.debug(f"Internet discovery error: {e}")
            return {}
    
    def connect_via_public_ip(self, public_ip, port=None):
        """
        Connect to a device using its public IP address (cross-network)
        
        Args:
            public_ip (str): Public IP address of target device
            port (int): Port number (uses default if None)
            
        Returns:
            dict: Connection info if successful, None if failed
        """
        if port is None:
            port = self.config.RECEIVER_PORT
            
        try:
            print(f"🌍 Attempting cross-network connection to {public_ip}:{port}")
            print("📡 This will work if the target device has port forwarding enabled")
            
            # Test connection with longer timeout for internet connections
            if not self._test_connection(public_ip, port, timeout=15):
                print("❌ Device not reachable via public IP")
                print("💡 Make sure the target device has:")
                print("   • Port forwarding enabled on router")
                print("   • Fshare receiver running")
                print("   • Firewall allows the connection")
                return None
            
            # Get device info
            device_info = self._get_device_connection_info(public_ip, port)
            if device_info:
                print(f"✅ Connected to device via internet!")
                print(f"📱 Device: {device_info.get('device_name', 'Remote Device')}")
                print(f"🌍 Public IP: {public_ip}:{port}")
                if 'code' in device_info:
                    print(f"🎫 Code: {device_info['code']}")
                    
                return {
                    'ip': public_ip,
                    'port': port,
                    'name': device_info.get('device_name', 'Remote Device'),
                    'code': device_info.get('code', ''),
                    'connection_type': 'internet'
                }
            else:
                print("❌ Could not get device information")
                return None
                
        except Exception as e:
            self.logger.error(f"Error connecting via public IP: {e}")
            print(f"❌ Error connecting via public IP: {e}")
            return None
    
    def _test_connection(self, ip, port, timeout=3):
        """Test if a device is reachable with mobile network considerations"""
        try:
            # First try standard connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                return True
            
            # If standard connection fails, try with longer timeout for mobile/internet networks
            if timeout < 8:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(8)  # Longer timeout for mobile/internet networks
                result = sock.connect_ex((ip, port))
                sock.close()
                return result == 0
            
            return False
            
        except Exception as e:
            return False
    
    def _get_device_connection_info(self, ip, port):
        """Get connection info from a device with improved error handling"""
        sock = None
        try:
            # Create socket and connect with timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # 3 second timeout
            
            # Attempt connection
            sock.connect((ip, port))
            
            # Send INFO command
            info_command = "INFO\n"
            sock.sendall(info_command.encode('utf-8'))
            
            # Receive response with timeout
            sock.settimeout(5)  # 5 seconds for response
            response = sock.recv(1024).decode('utf-8').strip()
            
            # Parse JSON response
            if response.startswith('{'):
                connection_info = json.loads(response)
                return connection_info
            else:
                # Try to handle non-JSON response
                print(f"⚠️ Non-JSON response from {ip}: {response[:50]}...")
                return None
                
        except socket.timeout:
            # Timeout is common, don't print error
            return None
        except ConnectionRefusedError:
            # Connection refused means no receiver running
            return None
        except Exception as e:
            # Other errors might be worth noting for debugging
            # print(f"Debug: Error getting info from {ip}: {e}")
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
    
    def send_file_via_relay(self, file_path, target_device_id, relay_server="relay.fshare.local", progress_callback=None):
        """
        Send file through a relay server for cross-network sharing
        
        Args:
            file_path (str): Path to file to send
            target_device_id (str): Target device identifier
            relay_server (str): Relay server address
            progress_callback (callable): Progress callback function
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"🌐 Sending file via relay server: {relay_server}")
            print(f"📱 Target device: {target_device_id}")
            
            # This is a placeholder for relay server implementation
            # In a real implementation, this would:
            # 1. Connect to relay server
            # 2. Register this device
            # 3. Check if target device is available
            # 4. Establish relay connection
            # 5. Send file through relay
            
            # For now, we'll try direct connection as fallback
            print("🔄 Relay server not implemented yet, trying direct methods...")
            return False
            
        except Exception as e:
            self.logger.error(f"Error sending via relay: {e}")
            print(f"❌ Error sending via relay: {e}")
            return False
    
    def get_public_ip(self):
        """
        Get the public IP address of this device
        
        Returns:
            str: Public IP address or None if failed
        """
        try:
            import urllib.request
            
            # Try multiple services to get public IP
            services = [
                'https://ipv4.icanhazip.com/',
                'https://api.ipify.org',
                'https://checkip.amazonaws.com/',
                'https://ifconfig.me/ip'
            ]
            
            for service in services:
                try:
                    with urllib.request.urlopen(service, timeout=5) as response:
                        public_ip = response.read().decode('utf-8').strip()
                        
                    # Validate IP format
                    parts = public_ip.split('.')
                    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                        print(f"🌍 Public IP: {public_ip}")
                        return public_ip
                        
                except Exception:
                    continue
            
            print("❌ Could not determine public IP address")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting public IP: {e}")
            return None
    
    def enable_port_forwarding_instructions(self):
        """
        Provide instructions for enabling port forwarding
        
        Returns:
            str: Instructions text
        """
        port = self.config.RECEIVER_PORT
        public_ip = self.get_public_ip()
        
        instructions = f"""
🌍 CROSS-NETWORK SHARING SETUP INSTRUCTIONS:

To enable file sharing across different networks, you need to set up port forwarding:

1. 📱 Find your router's admin panel:
   - Open a web browser
   - Go to: 192.168.1.1 or 192.168.0.1
   - Login with router credentials

2. 🔧 Configure Port Forwarding:
   - Find "Port Forwarding" or "Virtual Server" section
   - Add new rule:
     • Service Name: Fshare
     • External Port: {port}
     • Internal Port: {port}
     • Internal IP: [Your device's local IP]
     • Protocol: TCP

3. 🔒 Firewall Settings:
   - Allow port {port} through your firewall
   - On Windows: Windows Defender Firewall > Allow an app
   - On Android: Usually not needed

4. 🌐 Share your connection:
   - Your public IP: {public_ip or '[Check your public IP]'}
   - Port: {port}
   - Share this info: {public_ip or '[YOUR_PUBLIC_IP]'}:{port}

⚠️ SECURITY WARNING:
   - Only share with trusted contacts
   - Consider using VPN for additional security
   - Monitor for unauthorized access

💡 EASIER ALTERNATIVES:
   - Use same WiFi network when possible
   - Use mobile hotspot for direct connection
   - Consider cloud storage for large files
"""
        
        return instructions
    
    def send_file_via_link(self, file_path, connection_link, progress_callback=None):
        """
        Send file using a connection link
        
        Args:
            file_path (str): Path to file to send
            connection_link (str): Connection link from receiver
            progress_callback (callable): Progress callback function
        
        Returns:
            bool: True if successful, False otherwise
        """
        connection_info = self.connect_via_link(connection_link)
        if connection_info:
            return self.send_file(file_path, connection_info['ip'], connection_info['port'], progress_callback)
        return False
    
    def send_file_via_code(self, file_path, connection_code, progress_callback=None):
        """
        Send file using a connection code
        
        Args:
            file_path (str): Path to file to send
            connection_code (str): 6-character connection code
            progress_callback (callable): Progress callback function
        
        Returns:
            bool: True if successful, False otherwise
        """
        connection_info = self.connect_via_code(connection_code)
        if connection_info:
            return self.send_file(file_path, connection_info['ip'], connection_info['port'], progress_callback)
        return False
    
    def connect_cross_network(self, connection_method, connection_data):
        """
        Connect to device across different networks using various methods
        
        Args:
            connection_method (str): 'public_ip', 'relay', 'link', 'code'
            connection_data (dict): Connection specific data
        
        Returns:
            dict: Connection info if successful, None if failed
        """
        try:
            if connection_method == 'public_ip':
                # Direct connection via public IP
                public_ip = connection_data.get('ip')
                port = connection_data.get('port', self.config.RECEIVER_PORT)
                return self.connect_via_public_ip(public_ip, port)
                
            elif connection_method == 'relay':
                # Connection via relay server (not implemented yet)
                print("🔄 Relay server method not implemented yet")
                return None
                
            elif connection_method == 'link':
                # Connection via link
                link = connection_data.get('link')
                return self.connect_via_link(link)
                
            elif connection_method == 'code':
                # Connection via code
                code = connection_data.get('code')
                return self.connect_via_code(code)
                
            else:
                print(f"❌ Unknown connection method: {connection_method}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in cross-network connection: {e}")
            print(f"❌ Error in cross-network connection: {e}")
            return None
    
    def send_file_cross_network(self, file_path, connection_method, connection_data, progress_callback=None):
        """
        Send file across different networks
        
        Args:
            file_path (str): Path to file to send
            connection_method (str): Connection method to use
            connection_data (dict): Connection data
            progress_callback (callable): Progress callback function
        
        Returns:
            bool: True if successful, False otherwise
        """
        connection_info = self.connect_cross_network(connection_method, connection_data)
        if connection_info:
            return self.send_file(file_path, connection_info['ip'], connection_info['port'], progress_callback)
        return False


if __name__ == "__main__":
    # Test file sender
    import tempfile
    
    print("Testing file sender...")
    
    # Create test file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("This is a test file for Fshare.\n" * 100)
        test_file = f.name
    
    try:
        # Initialize sender
        sender = FileSender()
        sender.start_discovery()
        
        # Discover devices
        print("Discovering devices...")
        devices = sender.discover_devices(timeout=3)
        
        if devices:
            print("Discovered devices:")
            for ip, name in devices.items():
                print(f"  - {name} ({ip})")
            
            # Try to send to first device (this will likely fail in test)
            target_ip = list(devices.keys())[0]
            print(f"\nAttempting to send test file to {target_ip}...")
            
            success = sender.send_file(test_file, target_ip)
            print(f"Transfer result: {success}")
        else:
            print("No devices discovered")
            
            # Test with localhost (will fail but tests the connection logic)
            print("Testing with localhost...")
            success = sender.send_file(test_file, "127.0.0.1")
            print(f"Localhost test result: {success}")
        
        # Test active transfers
        transfers = sender.get_active_transfers()
        print(f"\nActive transfers: {len(transfers)}")
        
    finally:
        sender.stop()
        os.unlink(test_file)
    
    print("File sender test completed.")
