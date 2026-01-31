"""Tests for security enhancements."""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.security import _get_api_key_salt, hash_api_key
from src.utils.security.session_manager import SessionManager
from src.utils.encryption import encrypt_password, decrypt_password
from src.core.exceptions import ConfigurationError


class TestAPIKeySaltSecurity:
    """Test API key salt security improvements."""

    def test_api_key_salt_required_in_production(self, monkeypatch):
        """Test that API_KEY_SALT is required in production."""
        # Clear the global salt
        from src.core import security

        security._API_KEY_SALT = None

        # Set production environment
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("API_KEY_SALT", raising=False)

        # Should raise ValueError in production
        with pytest.raises(ValueError, match="API_KEY_SALT environment variable MUST be set"):
            _get_api_key_salt()

    def test_api_key_salt_warning_in_development(self, monkeypatch, caplog):
        """Test that API_KEY_SALT shows warning in development."""
        import logging

        # Set caplog to capture WARNING level logs
        caplog.set_level(logging.WARNING)

        # Clear the global salt
        from src.core import security

        security._API_KEY_SALT = None

        # Set development environment
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("API_KEY_SALT", raising=False)

        # Should work but log warning
        salt = _get_api_key_salt()
        assert salt == b"dev-only-insecure-salt-do-not-use-in-prod"
        assert "SECURITY WARNING" in caplog.text

    def test_api_key_salt_minimum_length(self, monkeypatch):
        """Test that API_KEY_SALT must be at least 32 characters."""
        # Clear the global salt
        from src.core import security

        security._API_KEY_SALT = None

        monkeypatch.setenv("API_KEY_SALT", "short")

        with pytest.raises(ValueError, match="must be at least 32 characters"):
            _get_api_key_salt()

    def test_api_key_salt_valid_length(self, monkeypatch):
        """Test that valid API_KEY_SALT is accepted."""
        # Clear the global salt
        from src.core import security

        security._API_KEY_SALT = None

        valid_salt = "a" * 32  # 32 character salt
        monkeypatch.setenv("API_KEY_SALT", valid_salt)

        salt = _get_api_key_salt()
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

    def test_session_backward_compatibility(self, tmp_path, monkeypatch, caplog):
        """Test that old unencrypted sessions can still be loaded."""
        import logging

        # Set caplog to capture WARNING level logs
        caplog.set_level(logging.WARNING)

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
        manager = SessionManager(str(session_file))
        assert manager.access_token == "old_token"
        assert "unencrypted session" in caplog.text.lower()


class TestEnvironmentValidation:
    """Test environment validation at startup."""

    def test_validate_environment_missing_encryption_key(self, monkeypatch):
        """Test that ENCRYPTION_KEY is always required."""
        from main import validate_environment

        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="ENCRYPTION_KEY"):
            validate_environment()

    def test_validate_environment_production_requirements(self, monkeypatch):
        """Test that production requires all security variables."""
        from main import validate_environment
        from cryptography.fernet import Fernet

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.delenv("API_SECRET_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="API_SECRET_KEY"):
            validate_environment()

    def test_validate_environment_api_secret_min_length(self, monkeypatch):
        """Test that API_SECRET_KEY must be at least 64 characters."""
        from main import validate_environment
        from cryptography.fernet import Fernet
        import secrets

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.setenv("API_SECRET_KEY", "short_key")

        with pytest.raises(ConfigurationError, match="at least 64 characters"):
            validate_environment()

    def test_validate_environment_api_key_salt_min_length(self, monkeypatch):
        """Test that API_KEY_SALT must be at least 32 characters."""
        from main import validate_environment
        from cryptography.fernet import Fernet

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.setenv("API_SECRET_KEY", "a" * 64)
        monkeypatch.setenv("API_KEY_SALT", "short")

        with pytest.raises(ConfigurationError, match="at least 32 characters"):
            validate_environment()

    def test_validate_environment_success_development(self, monkeypatch):
        """Test successful validation in development."""
        from main import validate_environment
        from cryptography.fernet import Fernet
        import logging

        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

        # Should succeed in development without all variables
        # No exception should be raised
        validate_environment()

    def test_validate_environment_success_production(self, monkeypatch):
        """Test successful validation in production with all variables."""
        from main import validate_environment
        from cryptography.fernet import Fernet
        import secrets
        import logging

        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        # token_urlsafe(48) generates 64 chars (48 bytes * 4/3 for base64 encoding)
        monkeypatch.setenv("API_SECRET_KEY", secrets.token_urlsafe(48))
        monkeypatch.setenv("API_KEY_SALT", secrets.token_urlsafe(32))
        monkeypatch.setenv("VFS_ENCRYPTION_KEY", secrets.token_urlsafe(32))

        # Should succeed without raising an exception
        validate_environment()


class TestDatabaseWALMode:
    """Test database WAL mode configuration."""

    @pytest.mark.asyncio
    async def test_database_wal_mode_enabled(self, tmp_path):
        """Test that WAL mode is enabled on database."""
        from src.models.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        try:
            # Check WAL mode is enabled
            async with db.conn.execute("PRAGMA journal_mode") as cursor:
                result = await cursor.fetchone()
                assert result[0].lower() == "wal"

            # Check busy timeout is set
            async with db.conn.execute("PRAGMA busy_timeout") as cursor:
                result = await cursor.fetchone()
                assert result[0] == 30000

            # Check foreign keys are enabled
            async with db.conn.execute("PRAGMA foreign_keys") as cursor:
                result = await cursor.fetchone()
                assert result[0] == 1
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


class TestCorrelationIDLogging:
    """Test correlation ID support in logging."""

    def test_correlation_id_context_variable(self):
        """Test that correlation ID context variable exists."""
        from src.core.logger import correlation_id_ctx

        # Should start as None
        assert correlation_id_ctx.get() is None

        # Should be settable
        correlation_id_ctx.set("test-correlation-id")
        assert correlation_id_ctx.get() == "test-correlation-id"

    def test_correlation_id_filter(self):
        """Test CorrelationIdFilter adds correlation ID to records."""
        from src.core.logger import CorrelationIdFilter, correlation_id_ctx
        import logging

        filter_obj = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        # Without correlation ID
        correlation_id_ctx.set(None)
        filter_obj.filter(record)
        assert record.correlation_id == "N/A"

        # With correlation ID
        correlation_id_ctx.set("test-id-123")
        filter_obj.filter(record)
        assert record.correlation_id == "test-id-123"

    def test_json_formatter_includes_correlation_id(self):
        """Test that JSONFormatter includes correlation ID in output."""
        from src.core.logger import JSONFormatter, correlation_id_ctx
        import logging

        formatter = JSONFormatter()
        correlation_id_ctx.set("test-corr-id")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = correlation_id_ctx.get()

        output = formatter.format(record)
        data = json.loads(output)

        assert "correlation_id" in data
        assert data["correlation_id"] == "test-corr-id"
