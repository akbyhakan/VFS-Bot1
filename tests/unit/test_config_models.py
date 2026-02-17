"""Tests for Pydantic config_models module."""

import pytest
from pydantic import SecretStr, ValidationError

from src.core.config.config_models import (
    AppConfig,
    BotConfig,
    CaptchaConfig,
    NotificationConfig,
    VFSConfig,
)


class TestCaptchaConfig:
    """Tests for CaptchaConfig."""

    def test_default_values(self):
        """Test default values."""
        config = CaptchaConfig()
        assert config.provider == "2captcha"
        assert config.api_key.get_secret_value() == ""

    def test_from_dict_empty(self):
        """Test from_dict with empty dict."""
        config = CaptchaConfig.from_dict({})
        assert config.provider == "2captcha"
        assert config.api_key.get_secret_value() == ""

    def test_from_dict_with_values(self):
        """Test from_dict with custom values."""
        data = {
            "provider": "2captcha",
            "api_key": "test_key_123",
        }
        config = CaptchaConfig.from_dict(data)
        assert config.provider == "2captcha"
        assert config.api_key.get_secret_value() == "test_key_123"

    def test_from_dict_partial(self):
        """Test from_dict with partial data."""
        data = {"api_key": "partial_key"}
        config = CaptchaConfig.from_dict(data)
        assert config.provider == "2captcha"
        assert config.api_key.get_secret_value() == "partial_key"

    def test_invalid_provider_raises_validation_error(self):
        """Test that invalid provider raises validation error."""
        with pytest.raises(ValidationError, match='provider must be: 2captcha'):
            CaptchaConfig(provider="invalid_provider")

    def test_manual_provider_raises_validation_error(self):
        """Test that 'manual' provider raises validation error."""
        with pytest.raises(ValidationError, match='provider must be: 2captcha'):
            CaptchaConfig(provider="manual")


class TestVFSConfig:
    """Tests for VFSConfig."""

    def test_default_values(self):
        """Test default values with at least one centre."""
        config = VFSConfig(centres=["Default Centre"])
        assert str(config.base_url) == "https://visa.vfsglobal.com"
        assert config.country == "tur"
        assert config.language == "tr"
        assert config.mission == "nld"
        assert config.centres == ["Default Centre"]
        assert config.category == "Schengen Visa"
        assert config.subcategory == "Tourism"

    def test_explicit_values(self):
        """Test with explicit values."""
        config = VFSConfig(base_url="https://test.com", centres=["Test Centre"])
        assert str(config.base_url) == "https://test.com"
        assert config.country == "tur"

    def test_from_dict_minimal(self):
        """Test from_dict with minimal data."""
        config = VFSConfig.from_dict({"centres": ["Minimal Centre"]})
        assert str(config.base_url) == "https://visa.vfsglobal.com"
        assert config.country == "tur"

    def test_from_dict_with_all_values(self):
        """Test from_dict with all values."""
        data = {
            "base_url": "https://custom.com",
            "country": "usa",
            "language": "en",
            "mission": "uk",
            "centres": ["Centre1", "Centre2"],
            "category": "Work Visa",
            "subcategory": "Professional",
        }
        config = VFSConfig.from_dict(data)
        assert str(config.base_url) == "https://custom.com"
        assert config.country == "usa"
        assert config.language == "en"
        assert config.mission == "uk"
        assert config.centres == ["Centre1", "Centre2"]
        assert config.category == "Work Visa"
        assert config.subcategory == "Professional"

    def test_empty_centres_raises_validation_error(self):
        """Test that empty centres list raises validation error."""
        with pytest.raises(ValidationError, match="List of VFS centres must contain at least one centre"):
            VFSConfig()

    def test_non_https_url_raises_validation_error(self):
        """Test that non-HTTPS URL raises validation error."""
        with pytest.raises(ValidationError, match="VFS base_url must use HTTPS"):
            VFSConfig(base_url="http://insecure.com", centres=["Centre"])

    def test_country_too_short_raises_validation_error(self):
        """Test that country code too short raises validation error."""
        with pytest.raises(ValidationError):
            VFSConfig(country="a", centres=["Centre"])

    def test_country_too_long_raises_validation_error(self):
        """Test that country code too long raises validation error."""
        with pytest.raises(ValidationError):
            VFSConfig(country="abcd", centres=["Centre"])

    def test_mission_too_short_raises_validation_error(self):
        """Test that mission code too short raises validation error."""
        with pytest.raises(ValidationError):
            VFSConfig(mission="a", centres=["Centre"])

    def test_mission_too_long_raises_validation_error(self):
        """Test that mission code too long raises validation error."""
        with pytest.raises(ValidationError):
            VFSConfig(mission="abcd", centres=["Centre"])


class TestBotConfig:
    """Tests for BotConfig."""

    def test_default_values(self):
        """Test default values."""
        config = BotConfig()
        assert config.check_interval == 30
        assert config.headless is False
        assert config.screenshot_on_error is True
        assert config.max_retries == 3

    def test_from_dict_empty(self):
        """Test from_dict with empty dict."""
        config = BotConfig.from_dict({})
        assert config.check_interval == 30
        assert config.headless is False

    def test_from_dict_with_values(self):
        """Test from_dict with custom values."""
        data = {
            "check_interval": 60,
            "headless": True,
            "screenshot_on_error": False,
            "max_retries": 5,
        }
        config = BotConfig.from_dict(data)
        assert config.check_interval == 60
        assert config.headless is True
        assert config.screenshot_on_error is False
        assert config.max_retries == 5

    def test_validation_check_interval(self):
        """Test check_interval validation constraints."""
        # Too low
        with pytest.raises(ValidationError):
            BotConfig(check_interval=5)  # Less than 10

        # Too high
        with pytest.raises(ValidationError):
            BotConfig(check_interval=5000)  # Greater than 3600

    def test_validation_max_retries(self):
        """Test max_retries validation constraints."""
        # Too low
        with pytest.raises(ValidationError):
            BotConfig(max_retries=0)  # Less than 1

        # Too high
        with pytest.raises(ValidationError):
            BotConfig(max_retries=15)  # Greater than 10


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_default_values(self):
        """Test default values."""
        config = NotificationConfig()
        assert config.telegram_enabled is False
        assert config.telegram_bot_token.get_secret_value() == ""
        assert config.telegram_chat_id == ""
        assert config.email_enabled is False
        assert config.email_sender == ""
        assert config.email_password.get_secret_value() == ""
        assert config.email_receiver == ""
        assert config.smtp_server == "smtp.gmail.com"
        assert config.smtp_port == 587

    def test_from_dict_empty(self):
        """Test from_dict with empty dict."""
        config = NotificationConfig.from_dict({})
        assert config.telegram_enabled is False
        assert config.email_enabled is False

    def test_from_dict_with_telegram(self):
        """Test from_dict with telegram config."""
        data = {
            "telegram": {
                "enabled": True,
                "bot_token": "test_token",
                "chat_id": "123456",
            }
        }
        config = NotificationConfig.from_dict(data)
        assert config.telegram_enabled is True
        assert config.telegram_bot_token.get_secret_value() == "test_token"
        assert config.telegram_chat_id == "123456"
        assert config.email_enabled is False

    def test_from_dict_with_email(self):
        """Test from_dict with email config."""
        data = {
            "email": {
                "enabled": True,
                "sender": "sender@test.com",
                "password": "pass123",
                "receiver": "receiver@test.com",
                "smtp_server": "smtp.test.com",
                "smtp_port": 465,
            }
        }
        config = NotificationConfig.from_dict(data)
        assert config.email_enabled is True
        assert config.email_sender == "sender@test.com"
        assert config.email_password.get_secret_value() == "pass123"
        assert config.email_receiver == "receiver@test.com"
        assert config.smtp_server == "smtp.test.com"
        assert config.smtp_port == 465

    def test_from_dict_with_both(self):
        """Test from_dict with both telegram and email."""
        data = {
            "telegram": {
                "enabled": True,
                "bot_token": "token",
                "chat_id": "123",
            },
            "email": {
                "enabled": True,
                "sender": "test@test.com",
                "password": "pass",
                "receiver": "recv@test.com",
            },
        }
        config = NotificationConfig.from_dict(data)
        assert config.telegram_enabled is True
        assert config.email_enabled is True
        assert config.telegram_bot_token.get_secret_value() == "token"
        assert config.email_sender == "test@test.com"


class TestAppConfig:
    """Tests for AppConfig."""

    def test_from_dict_minimal(self):
        """Test from_dict with minimal data and required centres."""
        config = AppConfig.from_dict({"vfs": {"centres": ["Test Centre"]}})
        assert isinstance(config.vfs, VFSConfig)
        assert isinstance(config.bot, BotConfig)
        assert isinstance(config.captcha, CaptchaConfig)
        assert isinstance(config.notifications, NotificationConfig)

    def test_from_dict_with_all_configs(self):
        """Test from_dict with all configuration sections."""
        data = {
            "vfs": {
                "base_url": "https://test.com",
                "country": "tst",
                "centres": ["Test Centre"],
            },
            "bot": {
                "check_interval": 45,
                "headless": True,
            },
            "captcha": {
                "provider": "2captcha",
                "api_key": "test_key",
            },
            "notifications": {
                "telegram": {
                    "enabled": True,
                    "bot_token": "token",
                },
            },
        }
        config = AppConfig.from_dict(data)
        assert str(config.vfs.base_url) == "https://test.com"
        assert config.vfs.country == "tst"
        assert config.bot.check_interval == 45
        assert config.bot.headless is True
        assert config.captcha.provider == "2captcha"
        assert config.captcha.api_key.get_secret_value() == "test_key"
        assert config.notifications.telegram_enabled is True


class TestSecretStrMasking:
    """Tests for SecretStr masking behavior."""

    def test_captcha_config_repr_masks_api_key(self):
        """Test that repr masks the API key via SecretStr."""
        config = CaptchaConfig(api_key="secret_key_12345")
        repr_str = repr(config)

        # SecretStr automatically masks secrets
        assert "secret_key_12345" not in repr_str
        assert "**********" in repr_str or "SecretStr" in repr_str

    def test_captcha_config_empty_key(self):
        """Test repr when no API key is set."""
        config = CaptchaConfig()
        repr_str = repr(config)

        # Should show masked empty value
        assert "SecretStr" in repr_str

    def test_notification_config_masks_bot_token(self):
        """Test that repr masks telegram bot token."""
        config = NotificationConfig(telegram_bot_token="secret_token_123")
        repr_str = repr(config)

        assert "secret_token_123" not in repr_str
        assert "**********" in repr_str or "SecretStr" in repr_str

    def test_notification_config_masks_email_password(self):
        """Test that repr masks email password."""
        config = NotificationConfig(email_password="secret_pass_123")
        repr_str = repr(config)

        assert "secret_pass_123" not in repr_str
        assert "**********" in repr_str or "SecretStr" in repr_str

    def test_notification_config_does_not_mask_non_sensitive_fields(self):
        """Test that repr does not mask non-sensitive fields."""
        config = NotificationConfig(
            telegram_chat_id="123456",
            email_sender="sender@test.com",
            email_receiver="receiver@test.com",
        )
        repr_str = repr(config)

        assert "123456" in repr_str
        assert "sender@test.com" in repr_str
        assert "receiver@test.com" in repr_str
