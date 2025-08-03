#!/usr/bin/env python3
"""
Test Suite for Configuration Module
Tests configuration validation and settings
"""

import unittest
import sys
import os
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.config import Config
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False

@unittest.skipUnless(HAS_CONFIG, "Config module not available")
class TestConfig(unittest.TestCase):
    
    def setUp(self):
        if not HAS_CONFIG:
            self.skipTest("Config not available")
        self.config = Config()
    
    def test_default_values(self):
        self.assertEqual(self.config.RECEIVER_PORT, 8888)
        self.assertEqual(self.config.DISCOVERY_PORT, 8889)
        self.assertTrue(self.config.ENCRYPTION_ENABLED)
        self.assertEqual(self.config.KEY_SIZE, 32)
    
    def test_port_validation(self):
        self.config.RECEIVER_PORT = 80
        errors = self.config.validate()
        self.assertIn("RECEIVER_PORT must be between 1024 and 65535", errors)
    
    def test_duplicate_ports(self):
        self.config.RECEIVER_PORT = 8888
        self.config.DISCOVERY_PORT = 8888
        errors = self.config.validate()
        self.assertIn("RECEIVER_PORT and DISCOVERY_PORT must be different", errors)
    
    def test_buffer_size_validation(self):
        self.config.BUFFER_SIZE = 0
        errors = self.config.validate()
        self.assertIn("BUFFER_SIZE must be positive", errors)
    
    def test_valid_configuration(self):
        errors = self.config.validate()
        self.assertEqual(len(errors), 0)
    
    def test_directory_creation(self):
        self.config.ensure_directories()
        self.assertTrue(os.path.exists(self.config.DEFAULT_DOWNLOAD_DIR))
    
    def test_config_file_operations(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_file = f.name
        
        try:
            self.config.save_config(config_file)
            self.assertTrue(os.path.exists(config_file))
            
            new_config = Config()
            new_config.load_config(config_file)
            
            self.assertEqual(new_config.RECEIVER_PORT, self.config.RECEIVER_PORT)
            self.assertEqual(new_config.ENCRYPTION_ENABLED, self.config.ENCRYPTION_ENABLED)
        
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)

if __name__ == '__main__':
    unittest.main()
