"""
Fshare Backend - Utilities Module
Common utilities for hashing, logging, and file operations
"""

import os
import hashlib
import logging
import logging.handlers
import time
from datetime import datetime
import socket
import platform


def calculate_file_hash(file_path, algorithm='sha256', chunk_size=8192):
    """
    Calculate hash of a file
    
    Args:
        file_path (str): Path to the file
        algorithm (str): Hash algorithm to use (sha256, md5, sha1)
        chunk_size (int): Size of chunks to read
    
    Returns:
        str: Hexadecimal hash string
    """
    try:
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    except Exception as e:
        logging.error(f"Error calculating hash for {file_path}: {e}")
        return None


def verify_file_integrity(file_path, expected_hash, algorithm='sha256'):
    """
    Verify file integrity by comparing hashes
    
    Args:
        file_path (str): Path to the file
        expected_hash (str): Expected hash value
        algorithm (str): Hash algorithm used
    
    Returns:
        bool: True if hashes match, False otherwise
    """
    actual_hash = calculate_file_hash(file_path, algorithm)
    if actual_hash is None:
        return False
    
    return actual_hash.lower() == expected_hash.lower()


def format_file_size(size_bytes):
    """
    Format file size in human-readable format
    
    Args:
        size_bytes (int): Size in bytes
    
    Returns:
        str: Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_transfer_speed(bytes_per_second):
    """
    Format transfer speed in human-readable format
    
    Args:
        bytes_per_second (float): Transfer speed in bytes per second
    
    Returns:
        str: Formatted speed string
    """
    return f"{format_file_size(bytes_per_second)}/s"


def estimate_transfer_time(file_size, bytes_per_second):
    """
    Estimate remaining transfer time
    
    Args:
        file_size (int): Total file size in bytes
        bytes_per_second (float): Current transfer speed
    
    Returns:
        str: Formatted time estimate
    """
    if bytes_per_second <= 0:
        return "Unknown"
    
    seconds_remaining = file_size / bytes_per_second
    
    if seconds_remaining < 60:
        return f"{int(seconds_remaining)} seconds"
    elif seconds_remaining < 3600:
        minutes = int(seconds_remaining // 60)
        seconds = int(seconds_remaining % 60)
        return f"{minutes}m {seconds}s"
    else:
        hours = int(seconds_remaining // 3600)
        minutes = int((seconds_remaining % 3600) // 60)
        return f"{hours}h {minutes}m"


def get_local_ip():
    """
    Get the local IP address
    
    Returns:
        str: Local IP address
    """
    try:
        # Create a socket and connect to a remote server to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        # Fallback to localhost
        return "127.0.0.1"


def get_network_interfaces():
    """
    Get available network interfaces
    
    Returns:
        list: List of network interface IPs
    """
    interfaces = []
    try:
        hostname = socket.gethostname()
        # Get all IP addresses for the hostname
        addresses = socket.getaddrinfo(hostname, None)
        
        for addr in addresses:
            ip = addr[4][0]
            if ip not in interfaces and not ip.startswith('127.'):
                interfaces.append(ip)
    except Exception:
        pass
    
    # Add the primary local IP
    local_ip = get_local_ip()
    if local_ip not in interfaces:
        interfaces.append(local_ip)
    
    return interfaces


def get_device_name():
    """
    Get a friendly device name
    
    Returns:
        str: Device name
    """
    try:
        return f"{platform.node()}-{platform.system()}"
    except Exception:
        return "Unknown Device"


def is_port_available(port, host='localhost'):
    """
    Check if a port is available
    
    Args:
        port (int): Port number to check
        host (str): Host to check on
    
    Returns:
        bool: True if port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # Port is available if connection failed
    except Exception:
        return False


def find_available_port(start_port=8888, max_attempts=100):
    """
    Find an available port starting from start_port
    
    Args:
        start_port (int): Port to start searching from
        max_attempts (int): Maximum number of ports to try
    
    Returns:
        int: Available port number, or None if none found
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None


def safe_filename(filename):
    """
    Create a safe filename by removing invalid characters
    
    Args:
        filename (str): Original filename
    
    Returns:
        str: Safe filename
    """
    # Characters not allowed in filenames on Windows/Unix
    invalid_chars = '<>:"/\\|?*'
    
    safe_name = filename
    for char in invalid_chars:
        safe_name = safe_name.replace(char, '_')
    
    # Remove leading/trailing dots and spaces
    safe_name = safe_name.strip('. ')
    
    # Ensure filename is not empty
    if not safe_name:
        safe_name = "unnamed_file"
    
    return safe_name


def ensure_unique_filename(file_path):
    """
    Ensure filename is unique by adding a number if file exists
    
    Args:
        file_path (str): Original file path
    
    Returns:
        str: Unique file path
    """
    if not os.path.exists(file_path):
        return file_path
    
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    
    counter = 1
    while True:
        new_filename = f"{name}_{counter}{ext}"
        new_path = os.path.join(directory, new_filename)
        
        if not os.path.exists(new_path):
            return new_path
        
        counter += 1


def setup_logging(config=None):
    """
    Set up logging configuration with Unicode support
    
    Args:
        config: Configuration object with logging settings
    """
    if config is None:
        from .config import get_config
        config = get_config()
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    
    # Configure logging
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # File handler with rotation and UTF-8 encoding
    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.MAX_LOG_SIZE,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding='utf-8'  # Force UTF-8 encoding for Unicode support
    )
    
    # Console handler with UTF-8 encoding
    console_handler = logging.StreamHandler()
    
    # Try to set console encoding to UTF-8 for Windows compatibility
    try:
        if hasattr(console_handler.stream, 'reconfigure'):
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        elif hasattr(console_handler.stream, 'buffer'):
            # For older Python versions, wrap the stream
            import io
            console_handler.stream = io.TextIOWrapper(
                console_handler.stream.buffer, 
                encoding='utf-8', 
                errors='replace'
            )
    except Exception:
        # If console reconfiguration fails, use error handling in formatter
        pass
    
    # Custom formatter that handles Unicode safely
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            try:
                # Try normal formatting first
                return super().format(record)
            except UnicodeEncodeError:
                # If Unicode error, replace problematic characters
                record.msg = str(record.msg).encode('ascii', errors='replace').decode('ascii')
                if record.args:
                    safe_args = []
                    for arg in record.args:
                        safe_arg = str(arg).encode('ascii', errors='replace').decode('ascii')
                        safe_args.append(safe_arg)
                    record.args = tuple(safe_args)
                return super().format(record)
    
    # Use safe formatter
    formatter = SafeFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging initialized with Unicode support - Log file: {config.LOG_FILE}")


class TransferProgress:
    """Class to track transfer progress"""
    
    def __init__(self, total_size):
        self.total_size = total_size
        self.transferred = 0
        self.start_time = time.time()
        self.last_update = self.start_time
    
    def update(self, bytes_transferred):
        """Update progress with new bytes transferred"""
        self.transferred += bytes_transferred
        self.last_update = time.time()
    
    def get_percentage(self):
        """Get transfer percentage"""
        if self.total_size == 0:
            return 0
        return min(100, (self.transferred / self.total_size) * 100)
    
    def get_speed(self):
        """Get current transfer speed in bytes per second"""
        elapsed = self.last_update - self.start_time
        if elapsed <= 0:
            return 0
        return self.transferred / elapsed
    
    def get_eta(self):
        """Get estimated time of arrival"""
        speed = self.get_speed()
        if speed <= 0:
            return "Unknown"
        
        remaining_bytes = self.total_size - self.transferred
        return estimate_transfer_time(remaining_bytes, speed)
    
    def __str__(self):
        """String representation of progress"""
        percentage = self.get_percentage()
        speed = format_transfer_speed(self.get_speed())
        transferred = format_file_size(self.transferred)
        total = format_file_size(self.total_size)
        eta = self.get_eta()
        
        return f"{percentage:.1f}% ({transferred}/{total}) - {speed} - ETA: {eta}"


if __name__ == "__main__":
    # Test utilities
    print("Testing Fshare utilities...")
    
    # Test file size formatting
    print(f"File size formatting: {format_file_size(1536)} = 1.5 KB")
    print(f"Transfer speed: {format_transfer_speed(1048576)} = 1.0 MB/s")
    
    # Test network utilities
    print(f"Local IP: {get_local_ip()}")
    print(f"Device name: {get_device_name()}")
    print(f"Network interfaces: {get_network_interfaces()}")
    
    # Test port availability
    print(f"Port 8888 available: {is_port_available(8888)}")
    print(f"Next available port from 8888: {find_available_port(8888)}")
    
    # Test filename safety
    unsafe_name = 'file<>:|with*invalid?chars.txt'
    safe_name = safe_filename(unsafe_name)
    print(f"Safe filename: {unsafe_name} -> {safe_name}")
    
    # Test transfer progress
    progress = TransferProgress(1048576)  # 1MB
    progress.update(524288)  # 512KB transferred
    print(f"Transfer progress: {progress}")
    
    print("Utilities test completed.")
