"""Tests for environment validator module."""

import pytest

from src.env_validator import EnvValidator


class TestEnvValidator:
    """Tests for EnvValidator class."""

    def test_validate_with_all_required_vars(self, monkeypatch):
        """Test validation passes with all required vars set."""
        monkeypatch.setenv("VFS_EMAIL", "test@example.com")
        monkeypatch.setenv("VFS_PASSWORD", "password123")

        result = EnvValidator.validate(strict=False)

        assert result is True

    def test_validate_with_missing_required_vars(self, monkeypatch):
        """Test validation fails with missing required vars."""
        # Clear environment variables
        monkeypatch.delenv("VFS_EMAIL", raising=False)
        monkeypatch.delenv("VFS_PASSWORD", raising=False)

        result = EnvValidator.validate(strict=False)

        assert result is False

    def test_validate_strict_mode_exits(self, monkeypatch):
        """Test strict mode exits on missing required vars."""
        monkeypatch.delenv("VFS_EMAIL", raising=False)
        monkeypatch.delenv("VFS_PASSWORD", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            EnvValidator.validate(strict=True)

        assert exc_info.value.code == 1

    def test_validate_with_optional_vars_missing(self, monkeypatch, caplog):
        """Test validation warns about missing optional vars."""
        monkeypatch.setenv("VFS_EMAIL", "test@example.com")
        monkeypatch.setenv("VFS_PASSWORD", "password123")
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("EMAIL_SENDER", raising=False)

        result = EnvValidator.validate(strict=False)

        assert result is True
        assert "Missing optional environment variables" in caplog.text

    def test_get_masked_summary_masks_values(self, monkeypatch):
        """Test that sensitive values are masked in summary."""
        monkeypatch.setenv("VFS_EMAIL", "test@example.com")
        monkeypatch.setenv("VFS_PASSWORD", "verylongpassword123")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")

        summary = EnvValidator.get_masked_summary()

        # Long values should be masked with first 4 and last 4 chars
        assert summary["VFS_PASSWORD"] == "very...d123"
        assert summary["TELEGRAM_BOT_TOKEN"].startswith("1234")
        assert summary["TELEGRAM_BOT_TOKEN"].endswith("xyz")
        assert "..." in summary["TELEGRAM_BOT_TOKEN"]

    def test_get_masked_summary_short_values(self, monkeypatch):
        """Test that short values are fully masked."""
        monkeypatch.setenv("VFS_EMAIL", "short")

        summary = EnvValidator.get_masked_summary()

        assert summary["VFS_EMAIL"] == "***"

    def test_get_masked_summary_unset_values(self, monkeypatch):
        """Test that unset values show as NOT SET."""
        monkeypatch.delenv("VFS_EMAIL", raising=False)

        summary = EnvValidator.get_masked_summary()

        assert summary["VFS_EMAIL"] == "NOT SET"

    def test_required_vars_defined(self):
        """Test that required vars are properly defined."""
        assert "VFS_EMAIL" in EnvValidator.REQUIRED_VARS
        assert "VFS_PASSWORD" in EnvValidator.REQUIRED_VARS

    def test_optional_vars_defined(self):
        """Test that optional vars are properly defined."""
        assert "TELEGRAM_BOT_TOKEN" in EnvValidator.OPTIONAL_VARS
        assert "EMAIL_SENDER" in EnvValidator.OPTIONAL_VARS
        assert "CAPTCHA_API_KEY" in EnvValidator.OPTIONAL_VARS
