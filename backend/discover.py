"""
Fshare Backend - Device Discovery Module
UDP-based device discovery on local network
"""

import socket
import json
import threading
import time
import logging
from datetime import datetime, timedelta
from .config import get_config
from .utils import get_local_ip, get_device_name


class DeviceDiscovery:
    """Handles device discovery via UDP broadcast"""
    
    def __init__(self, config=None):
        """
        Initialize device discovery
        
        Args:
            config: Configuration object
        """
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # Discovery settings
        self.discovery_port = self.config.DISCOVERY_PORT
        self.broadcast_interval = self.config.BROADCAST_INTERVAL
        self.device_timeout = self.config.DEVICE_TIMEOUT
        
        # Device information
        self.device_name = get_device_name()
        self.local_ip = get_local_ip()
        
        # Discovered devices {ip: {'name': name, 'last_seen': datetime, 'port': port}}
        self.devices = {}
        self.devices_lock = threading.Lock()
        
        # Broadcasting state
        self.broadcasting = False
        self.listening = False
        self.broadcast_thread = None
        self.listen_thread = None
        
        # Sockets
        self.broadcast_socket = None
        self.listen_socket = None
    
    def start_broadcasting(self):
        """Start broadcasting device presence"""
        if self.broadcasting:
            return
        
        try:
            self.broadcasting = True
            self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
            self.broadcast_thread.start()
            self.logger.info(f"Started broadcasting on port {self.discovery_port}")
            
        except Exception as e:
            self.logger.error(f"Error starting broadcast: {e}")
            self.broadcasting = False
    
    def start_listening(self):
        """Start listening for device broadcasts"""
        if self.listening:
            return
        
        try:
            self.listening = True
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            self.logger.info(f"Started listening on port {self.discovery_port}")
            
        except Exception as e:
            self.logger.error(f"Error starting listener: {e}")
            self.listening = False
    
    def start(self):
        """Start both broadcasting and listening"""
        self.start_listening()
        self.start_broadcasting()
    
    def stop(self):
        """Stop discovery service"""
        self.broadcasting = False
        self.listening = False
        
        # Close sockets
        if self.broadcast_socket:
            try:
                self.broadcast_socket.close()
            except:
                pass
        
        if self.listen_socket:
            try:
                self.listen_socket.close()
            except:
                pass
        
        # Wait for threads to finish
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.broadcast_thread.join(timeout=2)
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2)
        
        self.logger.info("Device discovery stopped")
    
    def _broadcast_loop(self):
        """Main broadcasting loop"""
        try:
            # Create broadcast socket
            self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            while self.broadcasting:
                try:
                    # Create discovery message
                    message = {
                        'type': 'discovery',
                        'device_name': self.device_name,
                        'ip': self.local_ip,
                        'port': self.config.RECEIVER_PORT,
                        'timestamp': datetime.now().isoformat(),
                        'app': self.config.APP_NAME,
                        'version': self.config.VERSION
                    }
                    
                    # Send broadcast
                    data = json.dumps(message).encode('utf-8')
                    self.broadcast_socket.sendto(data, ('<broadcast>', self.discovery_port))
                    
                    # Wait before next broadcast
                    time.sleep(self.broadcast_interval)
                    
                except Exception as e:
                    if self.broadcasting:  # Only log if we're still supposed to be broadcasting
                        self.logger.error(f"Error in broadcast loop: {e}")
                    time.sleep(1)
        
        except Exception as e:
            self.logger.error(f"Error setting up broadcast socket: {e}")
        
        finally:
            if self.broadcast_socket:
                try:
                    self.broadcast_socket.close()
                except:
                    pass
    
    def _listen_loop(self):
        """Main listening loop"""
        try:
            # Create listening socket
            self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listen_socket.bind(('', self.discovery_port))
            self.listen_socket.settimeout(1.0)  # Non-blocking with timeout
            
            while self.listening:
                try:
                    # Receive discovery message
                    data, addr = self.listen_socket.recvfrom(1024)
                    
                    # Don't process our own broadcasts
                    if addr[0] == self.local_ip:
                        continue
                    
                    # Parse message
                    message = json.loads(data.decode('utf-8'))
                    
                    # Validate message
                    if (message.get('type') == 'discovery' and 
                        message.get('app') == self.config.APP_NAME):
                        
                        # Add/update device
                        self._add_device(
                            message.get('ip', addr[0]),
                            message.get('device_name', 'Unknown Device'),
                            message.get('port', self.config.RECEIVER_PORT)
                        )
                
                except socket.timeout:
                    # Timeout is normal, continue listening
                    continue
                
                except Exception as e:
                    if self.listening:  # Only log if we're still supposed to be listening
                        self.logger.error(f"Error in listen loop: {e}")
        
        except Exception as e:
            self.logger.error(f"Error setting up listen socket: {e}")
        
        finally:
            if self.listen_socket:
                try:
                    self.listen_socket.close()
                except:
                    pass
    
    def _add_device(self, ip, name, port):
        """Add or update a discovered device"""
        with self.devices_lock:
            self.devices[ip] = {
                'name': name,
                'port': port,
                'last_seen': datetime.now()
            }
            self.logger.debug(f"Discovered device: {name} ({ip}:{port})")
    
    def get_devices(self):
        """
        Get list of currently discovered devices
        
        Returns:
            dict: Dictionary of devices {ip: {'name': name, 'port': port, 'last_seen': datetime}}
        """
        current_time = datetime.now()
        timeout_delta = timedelta(seconds=self.device_timeout)
        
        with self.devices_lock:
            # Remove expired devices
            expired_devices = []
            for ip, info in self.devices.items():
                if current_time - info['last_seen'] > timeout_delta:
                    expired_devices.append(ip)
            
            for ip in expired_devices:
                del self.devices[ip]
                self.logger.debug(f"Removed expired device: {ip}")
            
            # Return copy of current devices
            return dict(self.devices)
    
    def discover_devices(self, timeout=5):
        """
        Perform one-time device discovery
        
        Args:
            timeout (int): Discovery timeout in seconds
        
        Returns:
            dict: Dictionary of discovered devices {ip: name}
        """
        if not self.listening:
            self.start_listening()
            time.sleep(0.5)  # Give listener time to start
        
        if not self.broadcasting:
            self.start_broadcasting()
        
        # Wait for discovery
        time.sleep(timeout)
        
        # Get discovered devices
        devices = self.get_devices()
        
        # Return simplified format
        return {ip: info['name'] for ip, info in devices.items()}
    
    def find_device_by_name(self, name):
        """
        Find device by name
        
        Args:
            name (str): Device name to search for
        
        Returns:
            tuple: (ip, port) if found, (None, None) otherwise
        """
        devices = self.get_devices()
        
        for ip, info in devices.items():
            if info['name'].lower() == name.lower():
                return ip, info['port']
        
        return None, None
    
    def is_device_available(self, ip):
        """
        Check if a device is currently available
        
        Args:
            ip (str): Device IP address
        
        Returns:
            bool: True if device is available, False otherwise
        """
        devices = self.get_devices()
        return ip in devices
    
    def get_device_info(self, ip):
        """
        Get information about a specific device
        
        Args:
            ip (str): Device IP address
        
        Returns:
            dict: Device information or None if not found
        """
        devices = self.get_devices()
        return devices.get(ip)
    
    def send_direct_discovery(self, target_ip):
        """
        Send direct discovery message to specific IP
        
        Args:
            target_ip (str): Target IP address
        
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            message = {
                'type': 'discovery',
                'device_name': self.device_name,
                'ip': self.local_ip,
                'port': self.config.RECEIVER_PORT,
                'timestamp': datetime.now().isoformat(),
                'app': self.config.APP_NAME,
                'version': self.config.VERSION
            }
            
            data = json.dumps(message).encode('utf-8')
            sock.sendto(data, (target_ip, self.discovery_port))
            sock.close()
            
            self.logger.debug(f"Sent direct discovery to {target_ip}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending direct discovery to {target_ip}: {e}")
            return False


def scan_network_range(base_ip="192.168.1", start=1, end=254, port=8889, timeout=1):
    """
    Scan IP range for Fshare devices
    
    Args:
        base_ip (str): Base IP address (e.g., "192.168.1")
        start (int): Start of range
        end (int): End of range
        port (int): Discovery port
        timeout (int): Socket timeout
    
    Returns:
        list: List of responsive IP addresses
    """
    responsive_ips = []
    
    for i in range(start, end + 1):
        ip = f"{base_ip}.{i}"
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            # Send simple ping
            sock.sendto(b"ping", (ip, port))
            sock.close()
            
            responsive_ips.append(ip)
            
        except:
            pass
    
    return responsive_ips


if __name__ == "__main__":
    # Test device discovery
    print("Testing device discovery...")
    
    discovery = DeviceDiscovery()
    
    print(f"Local device: {discovery.device_name} ({discovery.local_ip})")
    print(f"Discovery port: {discovery.discovery_port}")
    
    # Start discovery
    discovery.start()
    
    try:
        # Run discovery for 10 seconds
        for i in range(10):
            time.sleep(1)
            devices = discovery.get_devices()
            
            print(f"\rDiscovered devices ({len(devices)}): ", end="")
            for ip, info in devices.items():
                print(f"{info['name']}({ip}) ", end="")
            
            if not devices:
                print("None", end="")
        
        print()  # New line
        
        # Test one-time discovery
        print("\nPerforming one-time discovery...")
        devices = discovery.discover_devices(timeout=3)
        
        if devices:
            print("Final discovered devices:")
            for ip, name in devices.items():
                print(f"  - {name} ({ip})")
        else:
            print("No devices discovered")
    
    finally:
        discovery.stop()
    
    print("Discovery test completed.")
