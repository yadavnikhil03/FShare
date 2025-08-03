"""
Fshare Backend - File Receiver Module
Handles receiving files from other devices
"""

import os
import socket
import json
import threading
import time
import logging
import secrets
import base64
from .config import get_config
from .encryption import FileEncryption
from .utils import verify_file_integrity, format_file_size, ensure_unique_filename, safe_filename, get_local_ip


class FileReceiver:
    """Handles receiving files from other devices"""
    
    def __init__(self, config=None, download_path=None):
        """
        Initialize file receiver
        
        Args:
            config: Configuration object
            download_path: Override default download path
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.encryption = FileEncryption() if self.config.ENCRYPTION_ENABLED else None
        
        # Server settings
        self.host = '0.0.0.0'  # Listen on all interfaces
        self.port = self.config.RECEIVER_PORT
        self.download_path = download_path or self.config.DEFAULT_DOWNLOAD_DIR
        
        # Ensure download directory exists
        os.makedirs(self.download_path, exist_ok=True)
        
        # Server state
        self.running = False
        self.server_socket = None
        self.server_thread = None
        
        # Active connections
        self.active_connections = {}
        self.connection_lock = threading.Lock()
        
        # Statistics
        self.received_files = []
        self.total_bytes_received = 0
        
        # Connection code/link system
        self.connection_code = None
        self.connection_link = None
        
        # Ensure download directory exists
        os.makedirs(self.download_path, exist_ok=True)
    
    def start(self):
        """Start the receiver service"""
        if self.running:
            self.logger.warning("Receiver is already running")
            return
        
        try:
            self.running = True
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            
            # Generate connection code and link
            self._generate_connection_info()
            
            self.logger.info(f"File receiver started on {self.host}:{self.port}")
            print(f"🟢 File Receiver started successfully!")
            print(f"📡 Listening on {self.host}:{self.port}")
            print(f"📁 Download path: {self.download_path}")
            print(f"🔒 Encryption: {'Enabled' if self.encryption else 'Disabled'}")
            print(f"🔗 Connection Code: {self.connection_code}")
            print(f"🌐 Connection Link: {self.connection_link}")
            print("🚀 Ready to receive files!")
            print("=" * 60)
            
        except Exception as e:
            self.logger.error(f"Error starting receiver: {e}")
            print(f"❌ Failed to start receiver: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Stop the receiver service"""
        self.running = False
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Close active connections
        with self.connection_lock:
            for conn_id, conn_info in list(self.active_connections.items()):
                try:
                    conn_info['socket'].close()
                except:
                    pass
            self.active_connections.clear()
        
        # Wait for server thread to finish
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
        
        self.logger.info("File receiver stopped")
        print("🔴 File Receiver stopped")
        print("=" * 60)
    
    def _generate_connection_info(self):
        """Generate connection code and link for easy sharing"""
        try:
            # Get local IP address
            local_ip = get_local_ip()
            
            # Generate a short random code (6 characters)
            random_bytes = secrets.token_bytes(4)
            self.connection_code = base64.b32encode(random_bytes).decode('ascii')[:6]
            
            # Create connection data
            connection_data = {
                'ip': local_ip,
                'port': self.port,
                'code': self.connection_code,
                'device_name': f"{os.environ.get('COMPUTERNAME', 'Unknown')}-{os.environ.get('USERNAME', 'User')}",
                'app': self.config.APP_NAME,
                'version': self.config.VERSION
            }
            
            # Encode connection data to base64 for link
            connection_json = json.dumps(connection_data)
            encoded_data = base64.b64encode(connection_json.encode('utf-8')).decode('ascii')
            
            # Create shareable link
            self.connection_link = f"fshare://connect/{encoded_data}"
            
            self.logger.info(f"Connection code generated: {self.connection_code}")
            self.logger.info(f"Connection link generated: {self.connection_link}")
            
        except Exception as e:
            self.logger.error(f"Error generating connection info: {e}")
            self.connection_code = "ERROR"
            self.connection_link = "Error generating link"
    
    def _server_loop(self):
        """Main server loop"""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Non-blocking with timeout
            
            self.logger.info(f"Listening for connections on {self.host}:{self.port}")
            
            while self.running:
                try:
                    # Accept connection
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Handle connection in separate thread
                    conn_id = f"{client_address[0]}_{int(time.time())}"
                    
                    with self.connection_lock:
                        self.active_connections[conn_id] = {
                            'socket': client_socket,
                            'address': client_address,
                            'start_time': time.time(),
                            'status': 'connected'
                        }
                    
                    # Start handler thread
                    handler_thread = threading.Thread(
                        target=self._handle_client,
                        args=(conn_id, client_socket, client_address),
                        daemon=True
                    )
                    handler_thread.start()
                    
                except socket.timeout:
                    # Timeout is normal, continue listening
                    continue
                
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        self.logger.error(f"Error accepting connection: {e}")
        
        except Exception as e:
            self.logger.error(f"Error in server loop: {e}")
        
        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
    
    def _handle_client(self, conn_id, client_socket, client_address):
        """
        Handle client connection
        
        Args:
            conn_id (str): Connection identifier
            client_socket: Client socket object
            client_address: Client address tuple
        """
        try:
            self.logger.info(f"Handling connection from {client_address[0]}")
            
            # Set socket timeout
            client_socket.settimeout(self.config.TIMEOUT)
            
            # Check if this is an INFO request
            client_socket.settimeout(1)  # Short timeout for INFO command
            try:
                first_data = client_socket.recv(10, socket.MSG_PEEK)
                if first_data.startswith(b'INFO'):
                    # Handle INFO command
                    info_command = client_socket.recv(10).decode('utf-8').strip()
                    if info_command == 'INFO':
                        # Send connection info as JSON
                        info_response = {
                            'code': self.connection_code,
                            'name': f"{os.environ.get('COMPUTERNAME', 'Unknown')}-{os.environ.get('USERNAME', 'User')}",
                            'app': self.config.APP_NAME,
                            'version': self.config.VERSION
                        }
                        response_json = json.dumps(info_response)
                        client_socket.send(response_json.encode('utf-8'))
                        client_socket.close()
                        return
            except socket.timeout:
                pass  # Not an INFO command, continue with file transfer
            except Exception:
                pass  # Not an INFO command, continue with file transfer
            
            # Reset timeout for file transfer
            client_socket.settimeout(self.config.TIMEOUT)
            
            # Receive metadata size
            metadata_size_bytes = client_socket.recv(4)
            if len(metadata_size_bytes) != 4:
                raise ValueError("Invalid metadata size")
            
            metadata_size = int.from_bytes(metadata_size_bytes, byteorder='big')
            
            # Receive metadata
            metadata_json = b''
            while len(metadata_json) < metadata_size:
                chunk = client_socket.recv(metadata_size - len(metadata_json))
                if not chunk:
                    raise ValueError("Connection closed while receiving metadata")
                metadata_json += chunk
            
            # Parse metadata
            metadata = json.loads(metadata_json.decode('utf-8'))
            
            # Validate metadata
            if not self._validate_metadata(metadata):
                client_socket.send(b'INVALID_METADATA')
                return
            
            # Update connection status
            with self.connection_lock:
                if conn_id in self.active_connections:
                    self.active_connections[conn_id].update({
                        'status': 'receiving',
                        'file_name': metadata['file_name'],
                        'file_size': metadata['file_size'],
                        'progress': 0
                    })
            
            # Prepare for file reception
            file_name = safe_filename(metadata['file_name'])
            file_path = os.path.join(self.download_path, file_name)
            file_path = ensure_unique_filename(file_path)
            
            # Send ready acknowledgment
            client_socket.send(b'READY')
            
            # Print transfer start message
            print(f"\n📥 Starting file transfer: '{file_name}' ({format_file_size(metadata['file_size'])}) from {client_address[0]}")
            print(f"⏳ Transfer in progress...")
            
            # Receive file
            success = self._receive_file(conn_id, client_socket, file_path, metadata)
            
            if success:
                try:
                    client_socket.send(b'COMPLETED')
                    # Give sender time to receive completion message before closing
                    time.sleep(0.5)  # 500ms delay to ensure message is received
                except:
                    pass  # Don't fail transfer if completion message fails to send
                
                self.logger.info(f"File received successfully: {file_name}")
                
                # Print success message
                print(f"✅ SUCCESS: File '{file_name}' received successfully!")
                print(f"📁 Saved to: {file_path}")
                print(f"📊 Size: {format_file_size(metadata['file_size'])}")
                print(f"👤 From: {client_address[0]}")
                print("-" * 60)
                
                # Add to received files list
                self.received_files.append({
                    'file_name': file_name,
                    'file_path': file_path,
                    'file_size': metadata['file_size'],
                    'sender_ip': client_address[0],
                    'received_time': time.time()
                })
                
                self.total_bytes_received += metadata['file_size']
                
            else:
                try:
                    client_socket.send(b'FAILED')
                    time.sleep(0.2)  # Brief delay for failed transfers too
                except:
                    pass
                
                self.logger.error(f"Failed to receive file: {file_name}")
                
                # Print failure message
                print(f"❌ FAILED: File transfer failed for '{file_name}'")
                print(f"💡 Check connection and try again")
                print("-" * 60)
                
                # Remove partial file
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            
        except socket.timeout:
            self.logger.warning(f"Connection timeout from {client_address[0]}")
        
        except Exception as e:
            self.logger.error(f"Error handling client {client_address[0]}: {e}")
        
        finally:
            # Clean up connection gracefully
            try:
                # Try to shutdown the socket gracefully before closing
                client_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            
            try:
                client_socket.close()
            except:
                pass
            
            with self.connection_lock:
                if conn_id in self.active_connections:
                    del self.active_connections[conn_id]
    
    def _validate_metadata(self, metadata):
        """
        Validate received metadata
        
        Args:
            metadata (dict): Metadata dictionary
        
        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = ['type', 'file_name', 'file_size', 'file_hash', 'app']
        
        # Check required fields
        for field in required_fields:
            if field not in metadata:
                self.logger.error(f"Missing required field in metadata: {field}")
                return False
        
        # Check type
        if metadata['type'] != 'file_transfer':
            self.logger.error(f"Invalid transfer type: {metadata['type']}")
            return False
        
        # Check app compatibility
        if metadata['app'] != self.config.APP_NAME:
            self.logger.error(f"Incompatible app: {metadata['app']}")
            return False
        
        # Check file size
        if metadata['file_size'] <= 0 or metadata['file_size'] > self.config.MAX_FILE_SIZE:
            self.logger.error(f"Invalid file size: {metadata['file_size']}")
            return False
        
        # Check file name
        if not metadata['file_name'] or len(metadata['file_name']) > 255:
            self.logger.error(f"Invalid file name: {metadata['file_name']}")
            return False
        
        return True
    
    def _receive_file(self, conn_id, client_socket, file_path, metadata):
        """
        Receive file data
        
        Args:
            conn_id (str): Connection identifier
            client_socket: Client socket
            file_path (str): Path to save file
            metadata (dict): File metadata
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_size = metadata['file_size']
            file_hash = metadata['file_hash']
            is_encrypted = metadata.get('encrypted', False)
            encryption_key = None
            
            if is_encrypted and metadata.get('encryption_key'):
                encryption_key = bytes.fromhex(metadata['encryption_key'])
            
            bytes_received = 0
            
            with open(file_path, 'wb') as f:
                while bytes_received < file_size:
                    # Receive chunk size
                    chunk_size_bytes = client_socket.recv(4)
                    if len(chunk_size_bytes) != 4:
                        raise ValueError("Invalid chunk size")
                    
                    chunk_size = int.from_bytes(chunk_size_bytes, byteorder='big')
                    
                    # Check for end marker
                    if chunk_size == 0:
                        break
                    
                    # Receive chunk data
                    chunk_data = b''
                    while len(chunk_data) < chunk_size:
                        remaining = chunk_size - len(chunk_data)
                        data = client_socket.recv(min(remaining, self.config.BUFFER_SIZE))
                        if not data:
                            raise ValueError("Connection closed while receiving data")
                        chunk_data += data
                    
                    # Decrypt chunk if encrypted
                    if is_encrypted and encryption_key:
                        try:
                            chunk_data = self.encryption.decrypt_data(chunk_data, encryption_key)
                        except Exception as e:
                            self.logger.error(f"Decryption error: {e}")
                            return False
                    
                    # Write chunk to file
                    f.write(chunk_data)
                    
                    # Update progress
                    actual_bytes = len(chunk_data) if not is_encrypted else min(len(chunk_data), file_size - bytes_received)
                    bytes_received += actual_bytes
                    
                    progress_percent = int((bytes_received / file_size) * 100)
                    
                    with self.connection_lock:
                        if conn_id in self.active_connections:
                            self.active_connections[conn_id]['progress'] = progress_percent
                    
                    # Print progress every 10%
                    if progress_percent % 10 == 0 and progress_percent > 0:
                        print(f"📊 Progress: {progress_percent}% ({format_file_size(bytes_received)}/{format_file_size(file_size)})")
                    
                    self.logger.debug(f"Received {format_file_size(bytes_received)}/{format_file_size(file_size)} ({progress_percent}%)")
            
            # Verify file integrity
            if not verify_file_integrity(file_path, file_hash):
                self.logger.error("File integrity verification failed")
                return False
            
            self.logger.info(f"File integrity verified: {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error receiving file: {e}")
            return False
    
    def get_received_files(self):
        """
        Get list of received files
        
        Returns:
            list: List of received file information
        """
        return list(self.received_files)
    
    def get_active_connections(self):
        """
        Get active connections
        
        Returns:
            dict: Dictionary of active connections
        """
        with self.connection_lock:
            return dict(self.active_connections)
    
    def get_statistics(self):
        """
        Get receiver statistics
        
        Returns:
            dict: Statistics dictionary
        """
        return {
            'total_files_received': len(self.received_files),
            'total_bytes_received': self.total_bytes_received,
            'active_connections': len(self.active_connections),
            'running': self.running,
            'download_path': self.download_path
        }
    
    def set_download_path(self, path):
        """
        Set download directory
        
        Args:
            path (str): New download directory path
        """
        if os.path.exists(path) and os.path.isdir(path):
            self.download_path = path
            self.logger.info(f"Download path changed to: {path}")
        else:
            # Create directory if it doesn't exist
            try:
                os.makedirs(path, exist_ok=True)
                self.download_path = path
                self.logger.info(f"Created and set download path: {path}")
            except Exception as e:
                self.logger.error(f"Failed to create download directory {path}: {e}")
                raise
    
    def clear_received_files_history(self):
        """Clear the received files history"""
        self.received_files.clear()
        self.total_bytes_received = 0
        self.logger.info("Received files history cleared")
    
    def get_connection_info(self):
        """Get connection code and link for sharing"""
        return {
            'code': self.connection_code,
            'link': self.connection_link,
            'ip': get_local_ip(),
            'port': self.port
        }
    
    def generate_connection_code(self):
        """Generate new connection code"""
        self.connection_code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(6))
        return self.connection_code
    
    def regenerate_connection_code(self):
        """Regenerate connection code and link"""
        self._generate_connection_info()
        return self.get_connection_info()


if __name__ == "__main__":
    # Test file receiver
    print("Testing file receiver...")
    
    receiver = None
    try:
        # Initialize receiver
        receiver = FileReceiver()
        
        print(f"Download path: {receiver.download_path}")
        print(f"Listening on port: {receiver.port}")
        
        # Start receiver
        receiver.start()
        
        print("Receiver started. Waiting for connections...")
        print("Press Ctrl+C to stop")
        
        # Keep running until interrupted
        while receiver.running:
            try:
                time.sleep(1)
                
                # Show statistics
                stats = receiver.get_statistics()
                connections = receiver.get_active_connections()
                
                print(f"\rFiles received: {stats['total_files_received']}, "
                      f"Bytes: {format_file_size(stats['total_bytes_received'])}, "
                      f"Active connections: {len(connections)}", end="", flush=True)
                      
            except KeyboardInterrupt:
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received...")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
    finally:
        if receiver:
            print("\n🔄 Stopping receiver...")
            receiver.stop()
            print("✅ Receiver stopped successfully")
    
    print("File receiver test completed.")
