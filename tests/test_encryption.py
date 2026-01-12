"""Tests for password encryption utilities."""

import os
import pytest
from cryptography.fernet import Fernet

from src.utils.encryption import (
    PasswordEncryption,
    encrypt_password,
    decrypt_password,
)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def encryption_instance(encryption_key):
    """Create a test encryption instance."""
    return PasswordEncryption(encryption_key)


def test_password_encryption_init_with_key(encryption_key):
    """Test initialization with explicit key."""
    enc = PasswordEncryption(encryption_key)
    assert enc.cipher is not None


def test_password_encryption_init_from_env(encryption_key, monkeypatch):
    """Test initialization from environment variable."""
    monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)
    enc = PasswordEncryption()
    assert enc.cipher is not None


def test_password_encryption_init_no_key():
    """Test initialization without key raises error."""
    # Temporarily clear env var
    old_key = os.environ.get("ENCRYPTION_KEY")
    if "ENCRYPTION_KEY" in os.environ:
        del os.environ["ENCRYPTION_KEY"]
    
    try:
        with pytest.raises(ValueError, match="ENCRYPTION_KEY must be set"):
            PasswordEncryption()
    finally:
        # Restore env var
        if old_key:
            os.environ["ENCRYPTION_KEY"] = old_key


def test_password_encryption_init_invalid_key():
    """Test initialization with invalid key raises error."""
    with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY"):
        PasswordEncryption("invalid-key-not-base64")


def test_encrypt_decrypt_roundtrip(encryption_instance):
    """Test encrypting and decrypting password."""
    original_password = "MyS3cur3P@ssw0rd!"
    
    # Encrypt
    encrypted = encryption_instance.encrypt_password(original_password)
    
    # Should be different from original
    assert encrypted != original_password
    
    # Should be base64-encoded (no special chars except allowed ones)
    assert all(c.isalnum() or c in "=-_" for c in encrypted)
    
    # Decrypt
    decrypted = encryption_instance.decrypt_password(encrypted)
    
    # Should match original
    assert decrypted == original_password


def test_encrypt_different_passwords_different_output(encryption_instance):
    """Test that different passwords produce different encrypted values."""
    password1 = "password1"
    password2 = "password2"
    
    encrypted1 = encryption_instance.encrypt_password(password1)
    encrypted2 = encryption_instance.encrypt_password(password2)
    
    assert encrypted1 != encrypted2


def test_encrypt_same_password_different_output(encryption_instance):
    """Test that same password encrypted twice produces different output (nonce)."""
    password = "test_password"
    
    encrypted1 = encryption_instance.encrypt_password(password)
    encrypted2 = encryption_instance.encrypt_password(password)
    
    # Fernet includes a timestamp, so same password encrypted twice is different
    assert encrypted1 != encrypted2
    
    # But both should decrypt to same value
    decrypted1 = encryption_instance.decrypt_password(encrypted1)
    decrypted2 = encryption_instance.decrypt_password(encrypted2)
    assert decrypted1 == decrypted2 == password


def test_decrypt_with_wrong_key():
    """Test that decrypting with wrong key fails."""
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    
    enc1 = PasswordEncryption(key1)
    enc2 = PasswordEncryption(key2)
    
    password = "test_password"
    encrypted = enc1.encrypt_password(password)
    
    # Should fail with wrong key
    with pytest.raises(ValueError, match="Invalid encryption key or corrupted password"):
        enc2.decrypt_password(encrypted)


def test_decrypt_invalid_data(encryption_instance):
    """Test that decrypting invalid data fails."""
    with pytest.raises(ValueError, match="Invalid encryption key or corrupted password"):
        encryption_instance.decrypt_password("not-valid-encrypted-data")


def test_encrypt_empty_password(encryption_instance):
    """Test encrypting empty password."""
    encrypted = encryption_instance.encrypt_password("")
    decrypted = encryption_instance.decrypt_password(encrypted)
    assert decrypted == ""


def test_encrypt_unicode_password(encryption_instance):
    """Test encrypting password with unicode characters."""
    password = "пароль密码🔐"
    encrypted = encryption_instance.encrypt_password(password)
    decrypted = encryption_instance.decrypt_password(encrypted)
    assert decrypted == password


def test_encrypt_long_password(encryption_instance):
    """Test encrypting very long password."""
    password = "a" * 1000
    encrypted = encryption_instance.encrypt_password(password)
    decrypted = encryption_instance.decrypt_password(encrypted)
    assert decrypted == password


def test_global_functions(encryption_key, monkeypatch):
    """Test global encrypt/decrypt functions."""
    monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)
    
    password = "test_password"
    encrypted = encrypt_password(password)
    decrypted = decrypt_password(encrypted)
    
    assert decrypted == password
