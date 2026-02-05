"""Typed configuration models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CaptchaConfig:
    """Captcha configuration."""

    provider: str = "2captcha"
    api_key: str = ""
    manual_timeout: int = 120

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaptchaConfig":
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", "2captcha"),
            api_key=data.get("api_key", ""),
            manual_timeout=data.get("manual_timeout", 120),
        )


@dataclass
class VFSConfig:
    """VFS configuration."""

    base_url: str
    country: str = "tur"
    language: str = "tr"
    mission: str = "nld"
    centres: List[str] = field(default_factory=list)
    category: str = "Schengen Visa"
    subcategory: str = "Tourism"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VFSConfig":
        """Create from dictionary."""
        return cls(
            base_url=data.get("base_url", "https://visa.vfsglobal.com"),
            country=data.get("country", "tur"),
            language=data.get("language", "tr"),
            mission=data.get("mission", "nld"),
            centres=data.get("centres", []),
            category=data.get("category", "Schengen Visa"),
            subcategory=data.get("subcategory", "Tourism"),
        )


@dataclass
class BotConfig:
    """Bot runtime configuration."""

    check_interval: int = 30
    headless: bool = False
    screenshot_on_error: bool = True
    max_retries: int = 3

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfig":
        """Create from dictionary."""
        return cls(
            check_interval=data.get("check_interval", 30),
            headless=data.get("headless", False),
            screenshot_on_error=data.get("screenshot_on_error", True),
            max_retries=data.get("max_retries", 3),
        )


@dataclass
class NotificationConfig:
    """Notification configuration."""

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_enabled: bool = False
    email_sender: str = ""
    email_password: str = ""
    email_receiver: str = ""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationConfig":
        """Create from dictionary."""
        telegram = data.get("telegram", {})
        email = data.get("email", {})
        return cls(
            telegram_enabled=telegram.get("enabled", False),
            telegram_bot_token=telegram.get("bot_token", ""),
            telegram_chat_id=telegram.get("chat_id", ""),
            email_enabled=email.get("enabled", False),
            email_sender=email.get("sender", ""),
            email_password=email.get("password", ""),
            email_receiver=email.get("receiver", ""),
            smtp_server=email.get("smtp_server", "smtp.gmail.com"),
            smtp_port=email.get("smtp_port", 587),
        )


@dataclass
class AppConfig:
    """Complete application configuration."""

    vfs: VFSConfig
    bot: BotConfig
    captcha: CaptchaConfig
    notifications: NotificationConfig

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create from dictionary."""
        return cls(
            vfs=VFSConfig.from_dict(data.get("vfs", {})),
            bot=BotConfig.from_dict(data.get("bot", {})),
            captcha=CaptchaConfig.from_dict(data.get("captcha", {})),
            notifications=NotificationConfig.from_dict(data.get("notifications", {})),
        )
