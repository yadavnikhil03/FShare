#!/usr/bin/env python3
"""
Test Suite for Encryption Module
Tests AES-256 encryption/decryption functionality
"""

import unittest
import sys
import os
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.encryption import EncryptionManager
    HAS_ENCRYPTION = True
except ImportError:
    HAS_ENCRYPTION = False

@unittest.skipUnless(HAS_ENCRYPTION, "Encryption module not available")
class TestEncryption(unittest.TestCase):
    
    def setUp(self):
        if HAS_ENCRYPTION:
            self.encryption = EncryptionManager()
        else:
            self.skipTest("Encryption not available")
    
    def test_key_generation(self):
        if not HAS_ENCRYPTION:
            self.skipTest("Encryption not available")
        key1 = self.encryption.generate_key()
        key2 = self.encryption.generate_key()
        self.assertNotEqual(key1, key2)
        self.assertEqual(len(key1), 32)
    
    def test_text_encryption_decryption(self):
        if not HAS_ENCRYPTION:
            self.skipTest("Encryption not available")
        original_text = "Hello, FShare!"
        key = self.encryption.generate_key()
        
        encrypted = self.encryption.encrypt_data(original_text.encode(), key)
        decrypted = self.encryption.decrypt_data(encrypted, key)
        
        self.assertEqual(original_text, decrypted.decode())
    
    def test_file_encryption_decryption(self):
        if not HAS_ENCRYPTION:
            self.skipTest("Encryption not available")
        test_data = b"This is test file content for encryption testing."
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_data)
            temp_path = temp_file.name
        
        key = self.encryption.generate_key()
        
        encrypted_path = temp_path + ".enc"
        decrypted_path = temp_path + ".dec"
        
        try:
            self.encryption.encrypt_file(temp_path, encrypted_path, key)
            self.encryption.decrypt_file(encrypted_path, decrypted_path, key)
            
            with open(decrypted_path, 'rb') as f:
                decrypted_data = f.read()
            
            self.assertEqual(test_data, decrypted_data)
        
        finally:
            for path in [temp_path, encrypted_path, decrypted_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    def test_large_data_encryption(self):
        if not HAS_ENCRYPTION:
            self.skipTest("Encryption not available")
        large_data = b"X" * 10000
        key = self.encryption.generate_key()
        
        encrypted = self.encryption.encrypt_data(large_data, key)
        decrypted = self.encryption.decrypt_data(encrypted, key)
        
        self.assertEqual(large_data, decrypted)
    
    def test_invalid_key_size(self):
        if not HAS_ENCRYPTION:
            self.skipTest("Encryption not available")
        invalid_key = b"short"
        data = b"test data"
        
        with self.assertRaises(Exception):
            self.encryption.encrypt_data(data, invalid_key)

if __name__ == '__main__':
    unittest.main()
