"""
Fshare Backend - Encryption Module
File encryption and decryption functionality
"""

import os
import hashlib
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import secrets


class EncryptionManager:
    """Wrapper class for encryption operations - used by tests"""
    
    def __init__(self):
        self.file_encryption = FileEncryption()
    
    def generate_key(self):
        """Generate encryption key"""
        return self.file_encryption.generate_key()
    
    def encrypt_data(self, data, key):
        """Encrypt data"""
        return self.file_encryption.encrypt_data(data, key)
    
    def decrypt_data(self, encrypted_data, key):
        """Decrypt data"""
        return self.file_encryption.decrypt_data(encrypted_data, key)
    
    def encrypt_file(self, input_file, output_file, key):
        """Encrypt file"""
        return self.file_encryption.encrypt_file(input_file, output_file, key)
    
    def decrypt_file(self, input_file, output_file, key):
        """Decrypt file"""
        return self.file_encryption.decrypt_file(input_file, output_file, key)


class FileEncryption:
    """Handles file encryption and decryption operations"""
    
    def __init__(self, key_size=32):
        """
        Initialize encryption handler
        
        Args:
            key_size (int): Size of encryption key in bytes (32 for AES-256)
        """
        self.key_size = key_size
        self.backend = default_backend()
        self.logger = logging.getLogger(__name__)
    
    def generate_key(self):
        """
        Generate a random encryption key
        
        Returns:
            bytes: Random encryption key
        """
        return secrets.token_bytes(self.key_size)
    
    def derive_key_from_password(self, password, salt=None):
        """
        Derive encryption key from password using PBKDF2
        
        Args:
            password (str): Password to derive key from
            salt (bytes): Salt for key derivation (generated if None)
        
        Returns:
            tuple: (key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.key_size,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        
        key = kdf.derive(password.encode())
        return key, salt
    
    def encrypt_data(self, data, key):
        """
        Encrypt data using AES-256-CBC
        
        Args:
            data (bytes): Data to encrypt
            key (bytes): Encryption key
        
        Returns:
            bytes: Encrypted data with IV prepended
        """
        try:
            # Generate random IV
            iv = secrets.token_bytes(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self.backend
            )
            
            # Pad data to block size
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            # Encrypt
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # Return IV + encrypted data
            return iv + encrypted_data
            
        except Exception as e:
            self.logger.error(f"Error encrypting data: {e}")
            raise
    
    def decrypt_data(self, encrypted_data, key):
        """
        Decrypt data using AES-256-CBC
        
        Args:
            encrypted_data (bytes): Encrypted data with IV prepended
            key (bytes): Decryption key
        
        Returns:
            bytes: Decrypted data
        """
        try:
            # Extract IV and encrypted data
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self.backend
            )
            
            # Decrypt
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove padding
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error decrypting data: {e}")
            raise
    
    def encrypt_file(self, input_file_path, output_file_path, key, chunk_size=8192):
        """
        Encrypt a file
        
        Args:
            input_file_path (str): Path to input file
            output_file_path (str): Path to output encrypted file
            key (bytes): Encryption key
            chunk_size (int): Size of chunks to process
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate random IV
            iv = secrets.token_bytes(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # Create padder
            padder = padding.PKCS7(128).padder()
            
            with open(input_file_path, 'rb') as infile, \
                 open(output_file_path, 'wb') as outfile:
                
                # Write IV to beginning of file
                outfile.write(iv)
                
                # Process file in chunks
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        # Handle final padding
                        padded_chunk = padder.finalize()
                        if padded_chunk:
                            encrypted_chunk = encryptor.update(padded_chunk)
                            outfile.write(encrypted_chunk)
                        
                        # Finalize encryption
                        final_chunk = encryptor.finalize()
                        if final_chunk:
                            outfile.write(final_chunk)
                        break
                    
                    # Pad chunk if it's the last one and not aligned
                    if len(chunk) < chunk_size:
                        padded_chunk = padder.update(chunk) + padder.finalize()
                        encrypted_chunk = encryptor.update(padded_chunk)
                        outfile.write(encrypted_chunk)
                        
                        # Finalize encryption
                        final_chunk = encryptor.finalize()
                        if final_chunk:
                            outfile.write(final_chunk)
                        break
                    else:
                        padded_chunk = padder.update(chunk)
                        encrypted_chunk = encryptor.update(padded_chunk)
                        outfile.write(encrypted_chunk)
            
            self.logger.info(f"File encrypted successfully: {input_file_path} -> {output_file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error encrypting file {input_file_path}: {e}")
            return False
    
    def decrypt_file(self, input_file_path, output_file_path, key, chunk_size=8192):
        """
        Decrypt a file
        
        Args:
            input_file_path (str): Path to encrypted input file
            output_file_path (str): Path to output decrypted file
            key (bytes): Decryption key
            chunk_size (int): Size of chunks to process
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(input_file_path, 'rb') as infile:
                # Read IV from beginning of file
                iv = infile.read(16)
                
                # Create cipher
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.CBC(iv),
                    backend=self.backend
                )
                decryptor = cipher.decryptor()
                
                # Create unpadder
                unpadder = padding.PKCS7(128).unpadder()
                
                with open(output_file_path, 'wb') as outfile:
                    # Read remaining encrypted data
                    encrypted_data = infile.read()
                    
                    # Decrypt all data
                    padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
                    
                    # Remove padding
                    data = unpadder.update(padded_data) + unpadder.finalize()
                    
                    # Write decrypted data
                    outfile.write(data)
            
            self.logger.info(f"File decrypted successfully: {input_file_path} -> {output_file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error decrypting file {input_file_path}: {e}")
            return False
    
    def encrypt_file_in_memory(self, file_path, key):
        """
        Encrypt file and return encrypted data in memory
        
        Args:
            file_path (str): Path to file to encrypt
            key (bytes): Encryption key
        
        Returns:
            bytes: Encrypted file data
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            return self.encrypt_data(data, key)
            
        except Exception as e:
            self.logger.error(f"Error encrypting file in memory {file_path}: {e}")
            raise
    
    def decrypt_file_in_memory(self, encrypted_data, key):
        """
        Decrypt data and return decrypted file data
        
        Args:
            encrypted_data (bytes): Encrypted file data
            key (bytes): Decryption key
        
        Returns:
            bytes: Decrypted file data
        """
        try:
            return self.decrypt_data(encrypted_data, key)
            
        except Exception as e:
            self.logger.error(f"Error decrypting data in memory: {e}")
            raise
    
    def generate_file_hash(self, file_path, algorithm='sha256'):
        """
        Generate hash of a file for integrity verification
        
        Args:
            file_path (str): Path to file
            algorithm (str): Hash algorithm to use
        
        Returns:
            str: Hexadecimal hash string
        """
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Error generating hash for {file_path}: {e}")
            return None
    
    def verify_file_integrity(self, file_path, expected_hash, algorithm='sha256'):
        """
        Verify file integrity using hash comparison
        
        Args:
            file_path (str): Path to file to verify
            expected_hash (str): Expected hash value
            algorithm (str): Hash algorithm used
        
        Returns:
            bool: True if hashes match, False otherwise
        """
        actual_hash = self.generate_file_hash(file_path, algorithm)
        if actual_hash is None:
            return False
        
        return actual_hash.lower() == expected_hash.lower()


# Convenience functions
def create_encryption_handler(key_size=32):
    """Create a new FileEncryption instance"""
    return FileEncryption(key_size)


def generate_random_key(size=32):
    """Generate a random encryption key"""
    return secrets.token_bytes(size)


def quick_encrypt_file(input_path, output_path, password=None, key=None):
    """
    Quick file encryption with password or key
    
    Args:
        input_path (str): Input file path
        output_path (str): Output file path
        password (str): Password for encryption (if no key provided)
        key (bytes): Encryption key (if no password provided)
    
    Returns:
        tuple: (success, key_or_salt)
    """
    encryption = FileEncryption()
    
    if key is None:
        if password is None:
            # Generate random key
            key = encryption.generate_key()
            success = encryption.encrypt_file(input_path, output_path, key)
            return success, key
        else:
            # Derive key from password
            key, salt = encryption.derive_key_from_password(password)
            success = encryption.encrypt_file(input_path, output_path, key)
            return success, salt
    else:
        # Use provided key
        success = encryption.encrypt_file(input_path, output_path, key)
        return success, key


def quick_decrypt_file(input_path, output_path, password=None, key=None, salt=None):
    """
    Quick file decryption with password or key
    
    Args:
        input_path (str): Input encrypted file path
        output_path (str): Output decrypted file path
        password (str): Password for decryption (if no key provided)
        key (bytes): Decryption key (if no password provided)
        salt (bytes): Salt for password-based decryption
    
    Returns:
        bool: True if successful, False otherwise
    """
    encryption = FileEncryption()
    
    if key is None and password is not None and salt is not None:
        # Derive key from password and salt
        key, _ = encryption.derive_key_from_password(password, salt)
    
    if key is not None:
        return encryption.decrypt_file(input_path, output_path, key)
    
    return False


if __name__ == "__main__":
    # Test encryption functionality
    print("Testing file encryption...")
    
    # Create test file
    test_file = "test_encrypt.txt"
    encrypted_file = "test_encrypt.enc"
    decrypted_file = "test_decrypt.txt"
    
    # Write test data
    with open(test_file, 'w') as f:
        f.write("This is a test file for encryption.\nHello, World!")
    
    # Test encryption
    encryption = FileEncryption()
    
    # Test with random key
    key = encryption.generate_key()
    print(f"Generated key: {key.hex()}")
    
    success = encryption.encrypt_file(test_file, encrypted_file, key)
    print(f"Encryption success: {success}")
    
    success = encryption.decrypt_file(encrypted_file, decrypted_file, key)
    print(f"Decryption success: {success}")
    
    # Verify decrypted content
    with open(decrypted_file, 'r') as f:
        decrypted_content = f.read()
    
    with open(test_file, 'r') as f:
        original_content = f.read()
    
    print(f"Content matches: {original_content == decrypted_content}")
    
    # Test password-based encryption
    password = "test_password_123"
    key, salt = encryption.derive_key_from_password(password)
    print(f"Password-derived key: {key.hex()}")
    print(f"Salt: {salt.hex()}")
    
    # Test integrity verification
    original_hash = encryption.generate_file_hash(test_file)
    decrypted_hash = encryption.generate_file_hash(decrypted_file)
    print(f"Hash verification: {original_hash == decrypted_hash}")
    
    # Clean up test files
    for file_path in [test_file, encrypted_file, decrypted_file]:
        if os.path.exists(file_path):
            os.remove(file_path)
    
    print("Encryption test completed.")
