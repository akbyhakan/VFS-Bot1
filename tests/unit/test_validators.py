"""Tests for environment and configuration validators."""

import pytest
from cryptography.fernet import Fernet

from src.core.config.env_validator import EnvValidator


def test_validate_email_valid():
    """Test email validation with valid emails."""
    valid_emails = [
        "test@example.com",
        "user.name@domain.co.uk",
        "user+tag@example.com",
        "user_name@example-domain.com",
    ]

    for email in valid_emails:
        assert EnvValidator._validate_email(email), f"Should accept {email}"


def test_validate_email_invalid():
    """Test email validation with invalid emails."""
    invalid_emails = [
        "not-an-email",
        "@example.com",
        "user@",
        "user@@example.com",
        "user@.com",
        "",
    ]

    for email in invalid_emails:
        assert not EnvValidator._validate_email(email), f"Should reject {email}"


def test_validate_encryption_key_valid():
    """Test encryption key validation with valid keys."""
    # Generate valid Fernet key
    valid_key = Fernet.generate_key().decode()
    assert EnvValidator._validate_encryption_key(valid_key)


def test_validate_encryption_key_invalid():
    """Test encryption key validation with invalid keys."""
    invalid_keys = [
        "not-a-valid-key",
        "tooshort",
        "a" * 43,  # Wrong length
        "a" * 45,  # Wrong length
        "",
    ]

    for key in invalid_keys:
        assert not EnvValidator._validate_encryption_key(key), f"Should reject {key}"


def test_validate_with_missing_required_vars(monkeypatch):
    """Test validation fails when required vars are missing."""
    # Clear all required vars
    for var in EnvValidator.REQUIRED_VARS:
        monkeypatch.delenv(var, raising=False)

    # Should fail validation
    result = EnvValidator.validate(strict=False)
    assert result is False


def test_validate_with_all_required_vars(monkeypatch):
    """Test validation passes when all required vars are present."""
    # Set all required vars with non-placeholder values
    monkeypatch.setenv("VFS_EMAIL", "user@vfsbot.local")
    monkeypatch.setenv("VFS_PASSWORD", "secure_password_123")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

    # Should pass validation
    result = EnvValidator.validate(strict=False)
    assert result is True


def test_validate_with_invalid_email(monkeypatch):
    """Test validation fails with invalid email."""
    monkeypatch.setenv("VFS_EMAIL", "invalid-email")
    monkeypatch.setenv("VFS_PASSWORD", "secure_password_123")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

    # Should fail validation
    result = EnvValidator.validate(strict=False)
    assert result is False


def test_validate_with_invalid_encryption_key(monkeypatch):
    """Test validation fails with invalid encryption key."""
    monkeypatch.setenv("VFS_EMAIL", "user@vfsbot.local")
    monkeypatch.setenv("VFS_PASSWORD", "secure_password_123")
    monkeypatch.setenv("ENCRYPTION_KEY", "invalid-key")

    # Should fail validation
    result = EnvValidator.validate(strict=False)
    assert result is False


def test_validate_strict_mode_exits(monkeypatch):
    """Test that strict mode exits on validation failure."""
    # Clear required vars
    for var in EnvValidator.REQUIRED_VARS:
        monkeypatch.delenv(var, raising=False)

    # Should exit in strict mode
    with pytest.raises(SystemExit):
        EnvValidator.validate(strict=True)


def test_get_masked_summary(monkeypatch):
    """Test getting masked summary of env vars."""
    monkeypatch.setenv("VFS_EMAIL", "user@vfsbot.local")
    monkeypatch.setenv("VFS_PASSWORD", "verylongpassword123")

    summary = EnvValidator.get_masked_summary()

    # Should mask values - shows first 4 and last 4 characters
    assert summary["VFS_EMAIL"].startswith("user")
    assert summary["VFS_EMAIL"].endswith("ocal")
    assert "..." in summary["VFS_EMAIL"]

    assert summary["VFS_PASSWORD"].startswith("very")
    assert summary["VFS_PASSWORD"].endswith("d123")
    assert "..." in summary["VFS_PASSWORD"]


def test_get_masked_summary_short_value(monkeypatch):
    """Test masked summary with short values."""
    monkeypatch.setenv("VFS_PASSWORD", "short")

    summary = EnvValidator.get_masked_summary()

    # Short values should be fully masked
    assert summary["VFS_PASSWORD"] == "***"


def test_get_masked_summary_missing_vars(monkeypatch):
    """Test masked summary with missing vars."""
    for var in list(EnvValidator.REQUIRED_VARS.keys()) + list(EnvValidator.OPTIONAL_VARS.keys()):
        monkeypatch.delenv(var, raising=False)

    summary = EnvValidator.get_masked_summary()

    # All should show as NOT SET
    for value in summary.values():
        assert value == "NOT SET"


def test_captcha_api_key_length_validation(monkeypatch):
    """Test that captcha API key length is validated."""
    monkeypatch.setenv("VFS_EMAIL", "test@example.com")
    monkeypatch.setenv("VFS_PASSWORD", "password")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("CAPTCHA_API_KEY", "short")  # Too short

    # Should fail validation
    result = EnvValidator.validate(strict=False)
    assert result is False


def test_optional_vars_warning(monkeypatch):
    """Test that missing optional vars produce warnings but validation passes."""
    # Set required vars with non-placeholder values
    monkeypatch.setenv("VFS_EMAIL", "user@vfsbot.local")
    monkeypatch.setenv("VFS_PASSWORD", "secure_password_123")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

    # Clear optional vars
    for var in EnvValidator.OPTIONAL_VARS:
        monkeypatch.delenv(var, raising=False)

    # Should pass validation despite missing optional vars
    result = EnvValidator.validate(strict=False)
    assert result is True
