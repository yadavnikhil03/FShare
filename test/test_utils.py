#!/usr/bin/env python3
"""
Test Suite for Utils Module
Tests utility functions and helpers
"""

import unittest
import sys
import os
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.utils import (
        format_file_size, 
        format_transfer_speed,
        safe_filename,
        calculate_file_hash,
        is_port_available,
        get_local_ip,
        TransferProgress
    )
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False

@unittest.skipUnless(HAS_UTILS, "Utils module not available")
class TestUtils(unittest.TestCase):
    
    def test_format_file_size(self):
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1536), "1.5 KB")
        self.assertEqual(format_file_size(1048576), "1.0 MB")
        self.assertEqual(format_file_size(1073741824), "1.0 GB")
    
    def test_format_transfer_speed(self):
        self.assertEqual(format_transfer_speed(1048576), "1.0 MB/s")
        self.assertEqual(format_transfer_speed(1024), "1.0 KB/s")
    
    def test_safe_filename(self):
        unsafe = "file<>:|with*invalid?chars.txt"
        safe = safe_filename(unsafe)
        self.assertNotIn("<", safe)
        self.assertNotIn(">", safe)
        self.assertNotIn(":", safe)
        self.assertNotIn("|", safe)
        self.assertNotIn("*", safe)
        self.assertNotIn("?", safe)
    
    def test_calculate_file_hash(self):
        test_data = b"Test file content for hashing"
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_data)
            temp_path = temp_file.name
        
        try:
            hash1 = calculate_file_hash(temp_path)
            hash2 = calculate_file_hash(temp_path)
            
            self.assertEqual(hash1, hash2)
            self.assertEqual(len(hash1), 64)  # SHA256 hex digest
        
        finally:
            os.unlink(temp_path)
    
    def test_port_availability(self):
        result = is_port_available(12345)
        self.assertIsInstance(result, bool)
    
    def test_get_local_ip(self):
        ip = get_local_ip()
        self.assertIsInstance(ip, str)
        self.assertIn(".", ip)
    
    def test_transfer_progress(self):
        progress = TransferProgress(1000)
        
        self.assertEqual(progress.total_size, 1000)
        self.assertEqual(progress.transferred, 0)
        self.assertEqual(progress.get_percentage(), 0)
        
        progress.update(500)
        self.assertEqual(progress.get_percentage(), 50)
        
        progress.update(1000)
        self.assertEqual(progress.get_percentage(), 100)

if __name__ == '__main__':
    unittest.main()
