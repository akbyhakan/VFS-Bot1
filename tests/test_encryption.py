"""Tests for password encryption utilities."""

import os
import pytest
import asyncio
from cryptography.fernet import Fernet

from src.utils.encryption import (
    PasswordEncryption,
    encrypt_password,
    decrypt_password,
    reset_encryption,
    get_encryption_async,
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


def test_reset_encryption(encryption_key, monkeypatch):
    """Test that reset_encryption clears the global instance."""
    monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)

    # Use global functions to create singleton
    password = "test_password"
    encrypted = encrypt_password(password)

    # Reset the singleton
    reset_encryption()

    # Should still work with same key
    decrypted = decrypt_password(encrypted)
    assert decrypted == password


def test_key_change_detection(monkeypatch):
    """Test that changing ENCRYPTION_KEY resets the singleton."""
    # Set first key and encrypt
    key1 = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key1)
    reset_encryption()

    password = "test_password"
    encrypted1 = encrypt_password(password)

    # Change to second key
    key2 = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key2)

    # Should use new key automatically
    encrypted2 = encrypt_password(password)

    # Encrypted values should be different (different keys)
    assert encrypted1 != encrypted2


def test_encryption_thread_safety():
    """Test that encryption singleton is thread-safe."""
    import threading
    from src.utils.encryption import get_encryption, reset_encryption

    key = Fernet.generate_key().decode()
    os.environ["ENCRYPTION_KEY"] = key
    reset_encryption()

    results = []
    errors = []

    def encrypt_in_thread():
        """Thread worker function."""
        try:
            enc = get_encryption()
            password = "test_password_" + threading.current_thread().name
            encrypted = enc.encrypt_password(password)
            decrypted = enc.decrypt_password(encrypted)
            results.append((password, decrypted))
        except Exception as e:
            errors.append(e)

    # Create multiple threads
    threads = []
    for i in range(10):
        thread = threading.Thread(target=encrypt_in_thread, name=f"Thread-{i}")
        threads.append(thread)

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check no errors occurred
    assert len(errors) == 0, f"Errors occurred in threads: {errors}"

    # Check all encryptions succeeded
    assert len(results) == 10

    # Each thread should have encrypted and decrypted its own password correctly
    for original, decrypted in results:
        assert original == decrypted


def test_encryption_with_bytes_key():
    """Test that PasswordEncryption works with bytes keys."""
    # Generate bytes key
    key_bytes = Fernet.generate_key()
    enc = PasswordEncryption(key_bytes)

    password = "test_password"
    encrypted = enc.encrypt_password(password)
    decrypted = enc.decrypt_password(encrypted)

    assert decrypted == password
    # Verify key is stored as string for comparison
    assert isinstance(enc._key, str)
    assert enc._key == key_bytes.decode()


@pytest.mark.asyncio
class TestAsyncEncryption:
    """Tests for async encryption functions."""

    async def test_async_encryption_in_event_loop(self, encryption_key, monkeypatch):
        """Test async encryption works within event loop."""
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)
        reset_encryption()

        instance = await get_encryption_async()
        assert instance is not None

        # Test encryption/decryption
        password = "test_async_password"
        encrypted = instance.encrypt_password(password)
        decrypted = instance.decrypt_password(encrypted)
        assert decrypted == password

    async def test_concurrent_encryption_access(self, encryption_key, monkeypatch):
        """Test concurrent access to encryption singleton."""
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)
        reset_encryption()

        async def encrypt_task(value: str):
            instance = await get_encryption_async()
            return instance.encrypt_password(value)

        # Run multiple concurrent encryptions
        tasks = [encrypt_task(f"password_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 10
        assert all(r is not None for r in results)

    async def test_async_lock_requires_event_loop(self):
        """Test that async lock creation requires an event loop."""
        from src.utils.encryption import _get_async_lock

        # We're already in an event loop (pytest-asyncio), so this should work
        lock = _get_async_lock()
        assert lock is not None


def test_async_lock_outside_event_loop():
    """Test that async lock raises error outside event loop."""
    from src.utils.encryption import _get_async_lock, _encryption_lock_async

    # Reset the async lock to ensure clean state
    import src.utils.encryption as enc_mod

    enc_mod._encryption_lock_async = None

    # This should raise RuntimeError when called outside event loop
    with pytest.raises(
        RuntimeError, match="Async encryption lock must be accessed within an event loop"
    ):
        _get_async_lock()
