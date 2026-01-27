"""Tests for application settings with Pydantic validation."""

import os
import pytest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.settings import VFSSettings, get_settings, reset_settings
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def reset_settings_singleton():
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


def test_settings_validation_requires_encryption_key():
    """Test that encryption key is required."""
    with pytest.raises(ValidationError) as exc_info:
        VFSSettings(
            api_secret_key="a" * 64,  # Valid secret key
        )
    
    # Should fail due to missing encryption_key
    assert "encryption_key" in str(exc_info.value)


def test_settings_validation_encryption_key_format():
    """Test that encryption key must be valid base64."""
    with pytest.raises(ValidationError) as exc_info:
        VFSSettings(
            encryption_key="invalid-not-base64",
            api_secret_key="a" * 64,
        )
    
    assert "base64" in str(exc_info.value).lower()


def test_settings_validation_api_secret_key_length():
    """Test that API secret key must be at least 64 characters."""
    with pytest.raises(ValidationError) as exc_info:
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",  # Valid base64
            api_secret_key="too_short",
        )
    
    assert "64 characters" in str(exc_info.value)


def test_settings_validation_email_format():
    """Test email validation."""
    with pytest.raises(ValidationError) as exc_info:
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            vfs_email="invalid-email",  # No @ symbol
        )
    
    assert "email" in str(exc_info.value).lower()


def test_settings_validation_env():
    """Test environment validation."""
    with pytest.raises(ValidationError) as exc_info:
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            env="invalid_env",
        )
    
    # Should only allow production, development, testing, staging
    assert "env" in str(exc_info.value).lower()


def test_settings_validation_log_level():
    """Test log level validation."""
    with pytest.raises(ValidationError) as exc_info:
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            log_level="INVALID",
        )
    
    assert "log_level" in str(exc_info.value).lower()


def test_settings_valid_configuration():
    """Test valid settings configuration."""
    settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        vfs_email="test@example.com",
        env="development",
        log_level="INFO",
    )
    
    assert settings.vfs_email == "test@example.com"
    assert settings.env == "development"
    assert settings.log_level == "INFO"


def test_settings_default_values():
    """Test default values are set correctly."""
    settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
    )
    
    # Check defaults
    assert settings.env == "production"
    assert settings.database_path == "vfs_bot.db"
    assert settings.db_pool_size == 10
    assert settings.db_connection_timeout == 30.0
    assert settings.rate_limit_enabled is True
    assert settings.headless is True


def test_settings_db_pool_size_validation():
    """Test database pool size validation."""
    # Valid range
    settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        db_pool_size=50,
    )
    assert settings.db_pool_size == 50
    
    # Too small
    with pytest.raises(ValidationError):
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            db_pool_size=0,
        )
    
    # Too large
    with pytest.raises(ValidationError):
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            db_pool_size=101,
        )


def test_settings_get_cors_origins():
    """Test CORS origins parsing."""
    settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        cors_allowed_origins="http://localhost:3000,http://example.com,https://app.example.com",
    )
    
    origins = settings.get_cors_origins()
    
    assert len(origins) == 3
    assert "http://localhost:3000" in origins
    assert "http://example.com" in origins
    assert "https://app.example.com" in origins


def test_settings_is_development():
    """Test development mode detection."""
    dev_settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        env="development",
    )
    
    prod_settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        env="production",
    )
    
    assert dev_settings.is_development() is True
    assert dev_settings.is_production() is False
    
    assert prod_settings.is_development() is False
    assert prod_settings.is_production() is True


def test_settings_singleton():
    """Test settings singleton pattern."""
    # First call creates instance
    settings1 = get_settings()
    
    # Second call returns same instance
    settings2 = get_settings()
    
    assert settings1 is settings2


def test_settings_from_env():
    """Test loading settings from environment variables."""
    with patch.dict(os.environ, {
        "ENCRYPTION_KEY": "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        "API_SECRET_KEY": "a" * 64,
        "ENV": "testing",
        "VFS_EMAIL": "env@example.com",
        "DB_POOL_SIZE": "20",
    }):
        reset_settings()
        settings = get_settings()
        
        assert settings.env == "testing"
        assert settings.vfs_email == "env@example.com"
        assert settings.db_pool_size == 20


def test_settings_secret_str_fields():
    """Test that sensitive fields use SecretStr."""
    settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        vfs_password="mypassword",
    )
    
    # Password should be stored as SecretStr
    assert settings.vfs_password.get_secret_value() == "mypassword"
    
    # String representation should not reveal password
    settings_str = str(settings)
    assert "mypassword" not in settings_str


def test_settings_check_interval_validation():
    """Test check interval validation."""
    # Valid range
    settings = VFSSettings(
        encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
        api_secret_key="a" * 64,
        check_interval=120,
    )
    assert settings.check_interval == 120
    
    # Too small
    with pytest.raises(ValidationError):
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            check_interval=5,
        )
    
    # Too large
    with pytest.raises(ValidationError):
        VFSSettings(
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3RrZXk=",
            api_secret_key="a" * 64,
            check_interval=4000,
        )
