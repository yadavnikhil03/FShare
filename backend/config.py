"""
Fshare Backend - Configuration Module
App-wide settings and configuration
"""

import os
import json
from pathlib import Path


class Config:
    """Application configuration class"""
    
    def __init__(self, config_file=None):
        """Initialize configuration with default values"""
        
        # Network settings
        self.RECEIVER_PORT = 8888
        self.DISCOVERY_PORT = 8889
        self.BUFFER_SIZE = 4096
        self.TIMEOUT = 30
        
        # Security settings
        self.ENCRYPTION_ENABLED = True
        self.KEY_SIZE = 32  # 256-bit key
        
        # File transfer settings
        self.CHUNK_SIZE = 8192
        self.MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
        
        # Application settings
        self.APP_NAME = "Fshare"
        self.VERSION = "1.0.0"
        self.DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "Fshare")
        
        # Logging settings
        self.LOG_LEVEL = "INFO"
        self.LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "transfer.log")
        self.MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
        self.LOG_BACKUP_COUNT = 5
        
        # Discovery settings
        self.BROADCAST_INTERVAL = 5  # seconds
        self.DEVICE_TIMEOUT = 30  # seconds
        
                # Ensure required directories exist
        self.ensure_directories()
        
        # Validate configuration
        errors = self.validate()
        if errors:
            print(f"Configuration validation errors: {errors}")
        
        # Load config file if provided
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
    
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
                
            # Update configuration with loaded values
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    def save_config(self, config_file):
        """Save current configuration to JSON file"""
        try:
            config_data = {
                'RECEIVER_PORT': self.RECEIVER_PORT,
                'DISCOVERY_PORT': self.DISCOVERY_PORT,
                'BUFFER_SIZE': self.BUFFER_SIZE,
                'TIMEOUT': self.TIMEOUT,
                'ENCRYPTION_ENABLED': self.ENCRYPTION_ENABLED,
                'CHUNK_SIZE': self.CHUNK_SIZE,
                'MAX_FILE_SIZE': self.MAX_FILE_SIZE,
                'DEFAULT_DOWNLOAD_DIR': self.DEFAULT_DOWNLOAD_DIR,
                'LOG_LEVEL': self.LOG_LEVEL,
                'BROADCAST_INTERVAL': self.BROADCAST_INTERVAL,
                'DEVICE_TIMEOUT': self.DEVICE_TIMEOUT
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
                
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def get_config_dir(self):
        """Get application configuration directory"""
        if os.name == 'nt':  # Windows
            config_dir = os.path.join(os.environ.get('APPDATA', ''), self.APP_NAME)
        else:  # Unix-like systems
            config_dir = os.path.join(os.path.expanduser('~'), f'.{self.APP_NAME.lower()}')
        
        os.makedirs(config_dir, exist_ok=True)
        return config_dir
    
    def get_default_config_file(self):
        """Get default configuration file path"""
        return os.path.join(self.get_config_dir(), 'config.json')
    
    def ensure_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.DEFAULT_DOWNLOAD_DIR,
            os.path.dirname(self.LOG_FILE),
            self.get_config_dir()
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def validate(self):
        """Validate configuration settings"""
        errors = []
        
        # Validate ports
        if not (1024 <= self.RECEIVER_PORT <= 65535):
            errors.append("RECEIVER_PORT must be between 1024 and 65535")
        
        if not (1024 <= self.DISCOVERY_PORT <= 65535):
            errors.append("DISCOVERY_PORT must be between 1024 and 65535")
        
        if self.RECEIVER_PORT == self.DISCOVERY_PORT:
            errors.append("RECEIVER_PORT and DISCOVERY_PORT must be different")
        
        # Validate sizes
        if self.BUFFER_SIZE <= 0:
            errors.append("BUFFER_SIZE must be positive")
        
        if self.CHUNK_SIZE <= 0:
            errors.append("CHUNK_SIZE must be positive")
        
        if self.MAX_FILE_SIZE <= 0:
            errors.append("MAX_FILE_SIZE must be positive")
        
        # Validate timeouts
        if self.TIMEOUT <= 0:
            errors.append("TIMEOUT must be positive")
        
        if self.BROADCAST_INTERVAL <= 0:
            errors.append("BROADCAST_INTERVAL must be positive")
        
        if self.DEVICE_TIMEOUT <= 0:
            errors.append("DEVICE_TIMEOUT must be positive")
        
        return errors
    
    def __str__(self):
        """String representation of configuration"""
        return f"Config(port={self.RECEIVER_PORT}, discovery={self.DISCOVERY_PORT}, encryption={self.ENCRYPTION_ENABLED})"
    
    def __repr__(self):
        """Detailed string representation of configuration"""
        return (f"Config(RECEIVER_PORT={self.RECEIVER_PORT}, "
                f"DISCOVERY_PORT={self.DISCOVERY_PORT}, "
                f"ENCRYPTION_ENABLED={self.ENCRYPTION_ENABLED}, "
                f"BUFFER_SIZE={self.BUFFER_SIZE}, "
                f"TIMEOUT={self.TIMEOUT})")


# Global configuration instance
_config = None

def get_config():
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config):
    """Set global configuration instance"""
    global _config
    _config = config


if __name__ == "__main__":
    # Test configuration
    config = Config()
    print("Default configuration:")
    print(config)
    
    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Configuration is valid")
    
    # Ensure directories
    config.ensure_directories()
    print(f"Default download directory: {config.DEFAULT_DOWNLOAD_DIR}")
    print(f"Log file: {config.LOG_FILE}")
    print(f"Config directory: {config.get_config_dir()}")
