"""Tests for MultiFernet key rotation functionality."""

import os

import pytest
from cryptography.fernet import Fernet

from src.utils.encryption import PasswordEncryption, reset_encryption


@pytest.fixture
def new_key():
    """Generate a new encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def old_key():
    """Generate an old encryption key."""
    return Fernet.generate_key().decode()


def test_multifernet_decrypt_with_old_key(new_key, old_key, monkeypatch):
    """Test that MultiFernet can decrypt data encrypted with old key."""
    # Encrypt with old key
    enc_old = PasswordEncryption(old_key)
    password = "test_password"
    encrypted_with_old = enc_old.encrypt_password(password)
    
    # Set up environment with new key and old key
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_OLD", old_key)
    
    # Create new instance with both keys
    enc_new = PasswordEncryption()
    
    # Should be able to decrypt data encrypted with old key
    decrypted = enc_new.decrypt_password(encrypted_with_old)
    assert decrypted == password


def test_multifernet_encrypt_uses_new_key(new_key, old_key, monkeypatch):
    """Test that MultiFernet encrypts with the new (first) key."""
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_OLD", old_key)
    
    # Create instance with both keys
    enc_multi = PasswordEncryption()
    
    # Encrypt data
    password = "test_password"
    encrypted = enc_multi.encrypt_password(password)
    
    # Should be able to decrypt with just new key
    enc_new_only = PasswordEncryption(new_key)
    decrypted = enc_new_only.decrypt_password(encrypted)
    assert decrypted == password
    
    # Should NOT be able to decrypt with just old key
    enc_old_only = PasswordEncryption(old_key)
    with pytest.raises(ValueError, match="Invalid encryption key or corrupted password"):
        enc_old_only.decrypt_password(encrypted)


def test_needs_migration_detects_old_key_data(new_key, old_key, monkeypatch):
    """Test that needs_migration correctly identifies data encrypted with old key."""
    # Encrypt with old key
    enc_old = PasswordEncryption(old_key)
    password = "test_password"
    encrypted_with_old = enc_old.encrypt_password(password)
    
    # Set up environment with new key and old key
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_OLD", old_key)
    
    # Create instance with both keys
    enc = PasswordEncryption()
    
    # Should detect that migration is needed
    assert enc.needs_migration(encrypted_with_old) is True


def test_needs_migration_new_key_data_no_migration(new_key, old_key, monkeypatch):
    """Test that needs_migration returns False for data encrypted with new key."""
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_OLD", old_key)
    
    # Create instance and encrypt with new key
    enc = PasswordEncryption()
    password = "test_password"
    encrypted_with_new = enc.encrypt_password(password)
    
    # Should NOT need migration
    assert enc.needs_migration(encrypted_with_new) is False


def test_migrate_to_new_key(new_key, old_key, monkeypatch):
    """Test that migrate_to_new_key re-encrypts data with new key."""
    # Encrypt with old key
    enc_old = PasswordEncryption(old_key)
    password = "test_password"
    encrypted_with_old = enc_old.encrypt_password(password)
    
    # Set up environment with new key and old key
    monkeypatch.setenv("ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("ENCRYPTION_KEY_OLD", old_key)
    
    # Create instance with both keys
    enc = PasswordEncryption()
    
    # Migrate the data
    migrated = enc.migrate_to_new_key(encrypted_with_old)
    
    # Migrated data should be decryptable with new key only
    enc_new_only = PasswordEncryption(new_key)
    decrypted = enc_new_only.decrypt_password(migrated)
    assert decrypted == password
    
    # Should NOT be able to decrypt with old key only
    enc_old_only = PasswordEncryption(old_key)
    with pytest.raises(ValueError, match="Invalid encryption key or corrupted password"):
        enc_old_only.decrypt_password(migrated)
