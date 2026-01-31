"""Tests for config_models module."""

import pytest
from src.core.config_models import (
    CaptchaConfig,
    VFSConfig,
    BotConfig,
    NotificationConfig,
    AppConfig,
)


class TestCaptchaConfig:
    """Tests for CaptchaConfig."""

    def test_default_values(self):
        """Test default values."""
        config = CaptchaConfig()
        assert config.provider == "2captcha"
        assert config.api_key == ""
        assert config.manual_timeout == 120

    def test_from_dict_empty(self):
        """Test from_dict with empty dict."""
        config = CaptchaConfig.from_dict({})
        assert config.provider == "2captcha"
        assert config.api_key == ""
        assert config.manual_timeout == 120

    def test_from_dict_with_values(self):
        """Test from_dict with custom values."""
        data = {
            "provider": "anticaptcha",
            "api_key": "test_key_123",
            "manual_timeout": 180,
        }
        config = CaptchaConfig.from_dict(data)
        assert config.provider == "anticaptcha"
        assert config.api_key == "test_key_123"
        assert config.manual_timeout == 180

    def test_from_dict_partial(self):
        """Test from_dict with partial data."""
        data = {"api_key": "partial_key"}
        config = CaptchaConfig.from_dict(data)
        assert config.provider == "2captcha"
        assert config.api_key == "partial_key"
        assert config.manual_timeout == 120


class TestVFSConfig:
    """Tests for VFSConfig."""

    def test_default_values(self):
        """Test default values."""
        config = VFSConfig(base_url="https://test.com")
        assert config.base_url == "https://test.com"
        assert config.country == "tur"
        assert config.language == "tr"
        assert config.mission == "nld"
        assert config.centres == []
        assert config.category == "Schengen Visa"
        assert config.subcategory == "Tourism"

    def test_from_dict_minimal(self):
        """Test from_dict with minimal data."""
        config = VFSConfig.from_dict({})
        assert config.base_url == "https://visa.vfsglobal.com"
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
        assert config.base_url == "https://custom.com"
        assert config.country == "usa"
        assert config.language == "en"
        assert config.mission == "uk"
        assert config.centres == ["Centre1", "Centre2"]
        assert config.category == "Work Visa"
        assert config.subcategory == "Professional"


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


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_default_values(self):
        """Test default values."""
        config = NotificationConfig()
        assert config.telegram_enabled is False
        assert config.telegram_bot_token == ""
        assert config.telegram_chat_id == ""
        assert config.email_enabled is False
        assert config.email_sender == ""
        assert config.email_password == ""
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
        assert config.telegram_bot_token == "test_token"
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
        assert config.email_password == "pass123"
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
        assert config.telegram_bot_token == "token"
        assert config.email_sender == "test@test.com"


class TestAppConfig:
    """Tests for AppConfig."""

    def test_from_dict_minimal(self):
        """Test from_dict with minimal data."""
        config = AppConfig.from_dict({})
        assert isinstance(config.vfs, VFSConfig)
        assert isinstance(config.bot, BotConfig)
        assert isinstance(config.captcha, CaptchaConfig)
        assert isinstance(config.notifications, NotificationConfig)

    def test_from_dict_with_all_configs(self):
        """Test from_dict with all configuration sections."""
        data = {
            "vfs": {
                "base_url": "https://test.com",
                "country": "test",
            },
            "bot": {
                "check_interval": 45,
                "headless": True,
            },
            "captcha": {
                "provider": "test_provider",
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
        assert config.vfs.base_url == "https://test.com"
        assert config.vfs.country == "test"
        assert config.bot.check_interval == 45
        assert config.bot.headless is True
        assert config.captcha.provider == "test_provider"
        assert config.captcha.api_key == "test_key"
        assert config.notifications.telegram_enabled is True
