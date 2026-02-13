"""Tests for critical bug fixes in security.py and settings.py."""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from src.core.security import APIKeyManager
from src.core.config.settings import VFSSettings, reset_settings


@pytest.fixture(autouse=True)
def reset_settings_singleton():
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


class TestBug1EnvironmentImport:
    """Test that Environment is correctly imported and used in security.py."""

    def test_environment_import_exists(self):
        """Verify that Environment can be imported."""
        from src.core.security import Environment

        assert Environment is not None
        assert hasattr(Environment, "current")
        assert hasattr(Environment, "_DEV_MODE")

    def test_api_key_manager_loads_salt_in_dev_mode(self):
        """Test that APIKeyManager can load salt in development mode using Environment."""
        with patch.dict(os.environ, {"ENV": "development"}, clear=False):
            # Clear the singleton instance to force re-initialization
            APIKeyManager.reset()
            manager = APIKeyManager()

            # This should not raise NameError about Environment not being defined
            salt = manager.get_salt()
            assert salt is not None
            assert isinstance(salt, bytes)

    def test_api_key_manager_requires_salt_in_production(self):
        """Test that APIKeyManager requires salt in production mode using Environment."""
        with patch.dict(os.environ, {"ENV": "production"}, clear=True):
            # Clear the singleton instance to force re-initialization
            APIKeyManager.reset()
            manager = APIKeyManager()

            # This should raise ValueError about missing salt, not NameError about Environment
            with pytest.raises(ValueError, match="API_KEY_SALT environment variable MUST be set"):
                manager.get_salt()



class TestBug2EncryptionKeyLength:
    """Test that encryption key must be exactly 32 bytes."""

    def test_encryption_key_too_short(self):
        """Test that encryption key shorter than 32 bytes is rejected."""
        import base64

        # Create a base64 key that decodes to less than 32 bytes
        short_key = base64.b64encode(b"short").decode()

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                VFSSettings(
                    encryption_key=short_key,
                    api_secret_key="a" * 64,
                )

            error_str = str(exc_info.value)
            assert "must decode to exactly 32 bytes" in error_str

    def test_encryption_key_too_long(self):
        """Test that encryption key longer than 32 bytes is rejected."""
        import base64

        # Create a base64 key that decodes to more than 32 bytes
        long_key = base64.b64encode(b"a" * 64).decode()

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                VFSSettings(
                    encryption_key=long_key,
                    api_secret_key="a" * 64,
                )

            error_str = str(exc_info.value)
            assert "must decode to exactly 32 bytes" in error_str

    def test_encryption_key_exactly_32_bytes(self):
        """Test that encryption key of exactly 32 bytes is accepted."""
        # Generate a valid Fernet key (32 bytes)
        valid_key = Fernet.generate_key().decode()

        with patch.dict(os.environ, {}, clear=True):
            # This should not raise an error
            settings = VFSSettings(
                encryption_key=valid_key,
                api_secret_key="a" * 64,
            )
            assert settings.encryption_key.get_secret_value() == valid_key

    def test_encryption_key_invalid_base64(self):
        """Test that invalid base64 is rejected."""
        invalid_key = "not_valid_base64!!!"

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                VFSSettings(
                    encryption_key=invalid_key,
                    api_secret_key="a" * 64,
                )

            error_str = str(exc_info.value)
            assert "base64" in error_str.lower()


class TestBug3DoubleEncode:
    """Test that Fernet works correctly without double encode."""

    def test_decrypt_vfs_password_works_correctly(self):
        """Test that VFS password decryption works without double encode."""
        # Generate a valid Fernet key
        fernet_key = Fernet.generate_key().decode()
        cipher = Fernet(fernet_key)

        # Encrypt a test password
        test_password = "my_test_password"
        encrypted_password = cipher.encrypt(test_password.encode()).decode()

        with patch.dict(os.environ, {}, clear=True):
            # Create settings with encrypted password
            settings = VFSSettings(
                encryption_key=fernet_key,
                api_secret_key="a" * 64,
                vfs_password=encrypted_password,
                vfs_password_encrypted=True,
            )

            # Password should be decrypted correctly
            decrypted = settings.vfs_password.get_secret_value()
            assert decrypted == test_password

    def test_fernet_accepts_string_directly(self):
        """Test that Fernet constructor accepts string without encoding."""
        # Generate a valid Fernet key
        fernet_key = Fernet.generate_key().decode()

        # This should work without .encode()
        cipher = Fernet(fernet_key)
        assert cipher is not None

        # Verify it can encrypt/decrypt
        test_data = b"test data"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == test_data


class TestDeadCodeRemoval:
    """Test that deprecated load_api_keys function is removed."""

    def test_load_api_keys_function_removed(self):
        """Verify that load_api_keys function no longer exists."""
        import src.core.security as security_module

        # The function should not exist
        assert not hasattr(security_module, "load_api_keys")

    def test_load_api_keys_not_in_exports(self):
        """Verify that load_api_keys is not exported from core.__init__."""
        from src.core import __all__

        # load_api_keys should not be in the exports
        assert "load_api_keys" not in __all__
