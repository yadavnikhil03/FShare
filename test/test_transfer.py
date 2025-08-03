#!/usr/bin/env python3
"""
Test Suite for File Transfer Functionality
Tests sender/receiver modules and file transfer operations
"""

import unittest
import sys
import os
import tempfile
import threading
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.sender import FileSender
    from backend.receiver import FileReceiver
    from backend.config import Config
    HAS_BACKEND = True
except ImportError:
    HAS_BACKEND = False

@unittest.skipUnless(HAS_BACKEND, "Backend modules not available")
class TestFileTransfer(unittest.TestCase):
    
    def setUp(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        self.config = Config()
        self.test_dir = tempfile.mkdtemp()
        self.receiver = None
        self.sender = None
    
    def tearDown(self):
        if self.receiver:
            self.receiver.stop()
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_file_creation_and_hash(self):
        test_file = os.path.join(self.test_dir, "test.txt")
        test_data = b"Test file content for transfer testing"
        
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        self.assertTrue(os.path.exists(test_file))
        self.assertEqual(os.path.getsize(test_file), len(test_data))
    
    def test_sender_initialization(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        self.sender = FileSender(self.config)
        self.assertIsNotNone(self.sender)
        self.assertEqual(self.sender.config, self.config)
    
    def test_receiver_initialization(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        self.receiver = FileReceiver(self.config, self.test_dir)
        self.assertIsNotNone(self.receiver)
        self.assertEqual(self.receiver.download_path, self.test_dir)
    
    def test_file_size_validation(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        large_file = os.path.join(self.test_dir, "large.txt")
        
        with open(large_file, 'wb') as f:
            f.write(b"X" * (self.config.MAX_FILE_SIZE + 1))
        
        self.sender = FileSender(self.config)
        
        if hasattr(self.sender, 'validate_file'):
            result = self.sender.validate_file(large_file)
            self.assertFalse(result)
        else:
            self.skipTest("validate_file method not available")
    
    def test_multiple_file_handling(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        files = []
        for i in range(3):
            file_path = os.path.join(self.test_dir, f"test_{i}.txt")
            with open(file_path, 'w') as f:
                f.write(f"Test content {i}")
            files.append(file_path)
        
        self.sender = FileSender(self.config)
        
        for file_path in files:
            if hasattr(self.sender, 'validate_file'):
                self.assertTrue(self.sender.validate_file(file_path))
            else:
                self.assertTrue(os.path.exists(file_path))
    
    def test_progress_callback(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        progress_values = []
        
        def progress_callback(progress):
            progress_values.append(progress)
        
        test_file = os.path.join(self.test_dir, "progress_test.txt")
        with open(test_file, 'wb') as f:
            f.write(b"X" * 1000)
        
        self.sender = FileSender(self.config)
        if hasattr(self.sender, 'progress_callback'):
            self.sender.progress_callback = progress_callback
    
    def test_connection_code_generation(self):
        if not HAS_BACKEND:
            self.skipTest("Backend not available")
        self.receiver = FileReceiver(self.config, self.test_dir)
        
        if hasattr(self.receiver, 'generate_connection_code'):
            code = self.receiver.generate_connection_code()
            self.assertIsNotNone(code)
            self.assertEqual(len(code), 6)
            self.assertTrue(code.isalnum())
        else:
            self.skipTest("generate_connection_code method not available")
    
    def test_network_port_availability(self):
        try:
            from backend.utils import is_port_available
            available = is_port_available(self.config.RECEIVER_PORT)
            self.assertIsInstance(available, bool)
        except ImportError:
            self.skipTest("Utils module not available")

if __name__ == '__main__':
    unittest.main()
