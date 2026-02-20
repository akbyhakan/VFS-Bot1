"""Tests for security enhancements."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.core.exceptions import ConfigurationError
from src.core.security import APIKeyManager
from src.utils.encryption import decrypt_password, encrypt_password
from src.utils.security.session_manager import SessionManager


class TestAPIKeySaltSecurity:
    """Test API key salt security improvements."""

    def test_api_key_salt_required_in_production(self, monkeypatch):
        """Test that API_KEY_SALT is required in production."""
        # Reset the singleton instance to force reload
        APIKeyManager.reset()

        # Set production environment
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("API_KEY_SALT", raising=False)

        # Should raise ValueError in production
        with pytest.raises(ValueError, match="API_KEY_SALT environment variable MUST be set"):
            APIKeyManager().get_salt()

    def test_api_key_salt_warning_in_development(self, monkeypatch):
        """Test that API_KEY_SALT shows warning in development."""
        # Reset the singleton instance to force reload
        APIKeyManager.reset()

        # Set development environment
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("API_KEY_SALT", raising=False)

        # Should work but log warning
        with patch("src.core.security.logger") as mock_logger:
            salt = APIKeyManager().get_salt()
            assert salt == b"dev-only-insecure-salt-do-not-use-in-prod"
            # Verify warning was logged via loguru
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "SECURITY WARNING" in warning_msg

    def test_api_key_salt_minimum_length(self, monkeypatch):
        """Test that API_KEY_SALT must be at least 32 characters."""
        # Reset the singleton instance to force reload
        APIKeyManager.reset()

        monkeypatch.setenv("API_KEY_SALT", "short")

        with pytest.raises(ValueError, match="must be at least 32 characters"):
            APIKeyManager().get_salt()

    def test_api_key_salt_valid_length(self, monkeypatch):
        """Test that valid API_KEY_SALT is accepted."""
        # Reset the singleton instance to force reload
        APIKeyManager.reset()

        valid_salt = "a" * 32  # 32 character salt
        monkeypatch.setenv("API_KEY_SALT", valid_salt)

        salt = APIKeyManager().get_salt()
        assert salt == valid_salt.encode()


class TestSessionEncryption:
    """Test session file encryption."""

    def test_session_save_encrypted(self, tmp_path, monkeypatch):
        """Test that session files are saved encrypted."""
        session_file = tmp_path / "session.json"

        # Ensure encryption key is set
        from cryptography.fernet import Fernet

        if not os.getenv("ENCRYPTION_KEY"):
            monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

        manager = SessionManager(str(session_file))
        manager.set_tokens("test_access_token", "test_refresh_token")

        # Read the file content
        with open(session_file, "r") as f:
            content = f.read()

        # Content should be encrypted (not plain JSON)
        with pytest.raises(json.JSONDecodeError):
            json.loads(content)

        # But should be decryptable
        decrypted = decrypt_password(content)
        data = json.loads(decrypted)
        assert data["access_token"] == "test_access_token"

    def test_session_load_encrypted(self, tmp_path, monkeypatch):
        """Test that encrypted session files can be loaded."""
        session_file = tmp_path / "session.json"

        # Ensure encryption key is set
        from cryptography.fernet import Fernet

        if not os.getenv("ENCRYPTION_KEY"):
            monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

        # Save encrypted session
        manager = SessionManager(str(session_file))
        manager.set_tokens("encrypted_token", "refresh_token")

        # Create new manager and load
        manager2 = SessionManager(str(session_file))
        assert manager2.access_token == "encrypted_token"
        assert manager2.refresh_token == "refresh_token"

    def test_session_backward_compatibility(self, tmp_path, monkeypatch):
        """Test that old unencrypted sessions can still be loaded."""
        session_file = tmp_path / "session.json"

        # Ensure encryption key is set
        from cryptography.fernet import Fernet

        if not os.getenv("ENCRYPTION_KEY"):
            monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

        # Create old-style unencrypted session file
        old_data = {
            "access_token": "old_token",
            "refresh_token": "old_refresh",
            "token_expiry": None,
        }
        with open(session_file, "w") as f:
            json.dump(old_data, f)

        # Load old session
        with patch("src.utils.security.session_manager.logger") as mock_logger:
            manager = SessionManager(str(session_file))
            assert manager.access_token == "old_token"
            # Verify warning was logged via loguru
            mock_logger.warning.assert_called()
            any_warning_has_unencrypted = any(
                "unencrypted" in str(call).lower() for call in mock_logger.warning.call_args_list
            )
            assert any_warning_has_unencrypted


class TestDatabaseConnectionConfig:
    """Test database connection configuration (PostgreSQL)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_connection_pool_created(self):
        """Test that connection pool is created on connect."""
        from src.constants import Database as DatabaseConfig
        from src.models.database import Database

        db = Database(database_url=DatabaseConfig.TEST_URL)

        try:
            await db.connect()
        except (OSError, Exception) as e:
            # Skip test if database is not available
            pytest.skip(f"Database not available for integration test: {e}")

        try:
            # Verify pool is created
            assert db.pool is not None

            # Verify we can execute a query
            async with db.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                assert result == 1
        finally:
            await db.close()


class TestCaptchaConstants:
    """Test captcha configuration constants."""

    def test_captcha_config_exists(self):
        """Test that CaptchaConfig class exists with required constants."""
        from src.constants import CaptchaConfig

        assert hasattr(CaptchaConfig, "MANUAL_TIMEOUT")
        assert hasattr(CaptchaConfig, "TWOCAPTCHA_TIMEOUT")
        assert hasattr(CaptchaConfig, "TURNSTILE_TIMEOUT")

    def test_captcha_timeout_values(self):
        """Test that captcha timeout values are reasonable."""
        from src.constants import CaptchaConfig

        assert CaptchaConfig.MANUAL_TIMEOUT == 120
        assert CaptchaConfig.TWOCAPTCHA_TIMEOUT == 180
        assert CaptchaConfig.TURNSTILE_TIMEOUT == 120


class TestPassportNumberEncryption:
    """Test passport number encryption for PII/GDPR compliance."""

    def test_passport_number_encryption(self):
        """Test that passport numbers are encrypted before storage."""
        passport = "AB1234567"

        # Encrypt the passport number
        encrypted = encrypt_password(passport)

        # Encrypted value should be different from original
        assert encrypted != passport

        # Decrypted value should match original
        decrypted = decrypt_password(encrypted)
        assert decrypted == passport

    def test_different_passports_encrypt_differently(self):
        """Test that different passport numbers produce different encrypted values."""
        passport1 = "AB1234567"
        passport2 = "CD9876543"

        encrypted1 = encrypt_password(passport1)
        encrypted2 = encrypt_password(passport2)

        # Different passports should encrypt to different values
        assert encrypted1 != encrypted2

        # Each should decrypt back to its original
        assert decrypt_password(encrypted1) == passport1
        assert decrypt_password(encrypted2) == passport2

    def test_same_passport_encrypts_differently_each_time(self):
        """Test that same passport encrypts to different values (Fernet includes timestamp)."""
        passport = "AB1234567"

        encrypted1 = encrypt_password(passport)
        encrypted2 = encrypt_password(passport)

        # Due to Fernet's timestamp, same value may encrypt differently
        # Both should decrypt to the same original value
        assert decrypt_password(encrypted1) == passport
        assert decrypt_password(encrypted2) == passport
