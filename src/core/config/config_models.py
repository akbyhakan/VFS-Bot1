"""Pydantic configuration models - Single source of truth for all config structures.

This module consolidates all configuration models using Pydantic v2 BaseModel,
replacing the previous TypedDict and dataclass definitions scattered across
src/types/config.py, src/core/config_models.py, and src/models/schemas.py.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, SecretStr, model_validator

# VFS Configuration Models


class VFSConfig(BaseModel):
    """VFS-specific configuration."""

    base_url: str = Field(default="https://visa.vfsglobal.com")
    country: str = Field(default="tur")
    mission: str = Field(default="nld")
    centres: List[str] = Field(default_factory=list)
    category: str = Field(default="Schengen Visa")
    subcategory: str = Field(default="Tourism")
    language: Optional[str] = Field(default="tr")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VFSConfig":
        """Create from dictionary for backward compatibility."""
        return cls.model_validate(data)


# Bot Configuration Models


class BotConfig(BaseModel):
    """Bot behavior configuration."""

    check_interval: int = Field(default=30, ge=10, le=3600)
    headless: bool = Field(default=False)
    screenshot_on_error: bool = Field(default=True)
    max_retries: int = Field(default=3, ge=1, le=10)
    browser_restart_after_pages: Optional[int] = Field(default=None)
    auto_book: bool = Field(default=False)
    timeout: Optional[int] = Field(default=None)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfig":
        """Create from dictionary for backward compatibility."""
        return cls.model_validate(data)


# Captcha Configuration Models


class CaptchaConfig(BaseModel):
    """Captcha solver configuration."""

    provider: str = Field(default="2captcha")
    api_key: SecretStr = Field(default=SecretStr(""))
    manual_timeout: int = Field(default=120, ge=30, le=600)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaptchaConfig":
        """Create from dictionary for backward compatibility."""
        return cls.model_validate(data)


# Anti-Detection Configuration Models


class AntiDetectionConfig(BaseModel):
    """Anti-detection features configuration."""

    enabled: bool = Field(default=False)
    tls_bypass: Optional[bool] = Field(default=None)
    fingerprint_bypass: Optional[bool] = Field(default=None)
    human_simulation: Optional[bool] = Field(default=None)
    stealth_mode: Optional[bool] = Field(default=None)


# Notification Configuration Models


class TelegramConfig(BaseModel):
    """Telegram notification configuration."""

    enabled: bool = Field(default=False)
    bot_token: SecretStr = Field(default=SecretStr(""))
    chat_id: str = Field(default="")


class EmailConfig(BaseModel):
    """Email notification configuration."""

    enabled: bool = Field(default=False)
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    sender: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))
    receiver: str = Field(default="")


class NotificationConfig(BaseModel):
    """Notification services configuration."""

    telegram_enabled: bool = Field(default=False)
    telegram_bot_token: SecretStr = Field(default=SecretStr(""))
    telegram_chat_id: str = Field(default="")
    email_enabled: bool = Field(default=False)
    email_sender: str = Field(default="")
    email_password: SecretStr = Field(default=SecretStr(""))
    email_receiver: str = Field(default="")
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    webhook_enabled: bool = Field(default=False)
    webhook_url: Optional[str] = Field(default=None)
    # Nested structures for compatibility
    telegram: Optional[TelegramConfig] = Field(default=None)
    email: Optional[EmailConfig] = Field(default=None)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationConfig":
        """Create from dictionary with nested telegram/email support for backward compatibility."""
        # Handle nested structure
        if "telegram" in data and isinstance(data["telegram"], dict):
            telegram = data["telegram"]
            data["telegram_enabled"] = telegram.get("enabled", False)
            data["telegram_bot_token"] = telegram.get("bot_token", "")
            data["telegram_chat_id"] = telegram.get("chat_id", "")

        if "email" in data and isinstance(data["email"], dict):
            email_data = data["email"]
            data["email_enabled"] = email_data.get("enabled", False)
            data["email_sender"] = email_data.get("sender", "")
            data["email_password"] = email_data.get("password", "")
            data["email_receiver"] = email_data.get("receiver", "")
            data["smtp_server"] = email_data.get("smtp_server", "smtp.gmail.com")
            data["smtp_port"] = email_data.get("smtp_port", 587)

        return cls.model_validate(data)


# Additional Configuration Models


class CredentialsConfig(BaseModel):
    """Admin credentials configuration."""

    admin_username: str = Field(default="")
    admin_password: SecretStr = Field(default=SecretStr(""))


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    enabled: bool = Field(default=False)
    rotation_interval: Optional[int] = Field(default=None)
    server: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password: Optional[SecretStr] = Field(default=None)


class SessionConfig(BaseModel):
    """Session configuration."""

    timeout: int = Field(default=300)
    max_retries: int = Field(default=3)


class CloudflareConfig(BaseModel):
    """Cloudflare handling configuration."""

    enabled: bool = Field(default=False)
    solver: str = Field(default="auto")
    timeout: int = Field(default=30)


class HumanBehaviorConfig(BaseModel):
    """Human behavior simulation configuration."""

    enabled: bool = Field(default=False)
    min_delay: float = Field(default=0.5)
    max_delay: float = Field(default=2.0)


class PaymentConfig(BaseModel):
    """Payment configuration."""

    method: str = Field(default="manual")
    timeout: int = Field(default=300)


class AlertsConfig(BaseModel):
    """Alert service configuration."""

    enabled_channels: List[str] = Field(default_factory=list)
    telegram_bot_token: Optional[SecretStr] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)


class SelectorHealthCheckConfig(BaseModel):
    """Selector health check configuration."""

    enabled: bool = Field(default=False)
    interval: int = Field(default=60)


class AppointmentsConfig(BaseModel):
    """Appointments configuration."""

    max_concurrent: int = Field(default=1, ge=1)
    retry_delay: int = Field(default=60)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: Optional[str] = Field(default=None)
    pool_size: int = Field(default=10, ge=1)
    connection_timeout: float = Field(default=30.0, ge=1.0)


class SecurityConfig(BaseModel):
    """Security configuration."""

    api_secret_key: Optional[SecretStr] = Field(default=None)
    api_key_salt: Optional[SecretStr] = Field(default=None)
    encryption_key: Optional[SecretStr] = Field(default=None)
    jwt_algorithm: str = Field(default="HS384")

    @model_validator(mode='after')
    def validate_security_keys(self) -> 'SecurityConfig':
        """Warn if security keys are empty (actual enforcement is in VFSSettings)."""
        import os
        env = os.getenv("ENV", "production").lower()
        if env not in ("testing", "test", "development", "dev"):
            missing = []
            for field_name in ('api_secret_key', 'api_key_salt', 'encryption_key'):
                value = getattr(self, field_name)
                if value is None or value.get_secret_value() == "":
                    missing.append(field_name)
            if missing:
                import warnings
                warnings.warn(
                    f"SecurityConfig: Empty security keys detected: {missing}. "
                    "This is insecure for production use.",
                    stacklevel=2,
                )
        return self


# Complete Application Configuration


class AppConfig(BaseModel):
    """Complete application configuration.

    This is the main configuration structure that combines all
    configuration sections.
    """

    vfs: VFSConfig
    bot: BotConfig
    captcha: CaptchaConfig
    notifications: NotificationConfig
    anti_detection: Optional[AntiDetectionConfig] = Field(default=None)
    credentials: Optional[CredentialsConfig] = Field(default=None)
    appointments: Optional[AppointmentsConfig] = Field(default=None)
    human_behavior: Optional[HumanBehaviorConfig] = Field(default=None)
    session: Optional[SessionConfig] = Field(default=None)
    cloudflare: Optional[CloudflareConfig] = Field(default=None)
    proxy: Optional[ProxyConfig] = Field(default=None)
    selector_health_check: Optional[SelectorHealthCheckConfig] = Field(default=None)
    payment: Optional[PaymentConfig] = Field(default=None)
    alerts: Optional[AlertsConfig] = Field(default=None)
    database: Optional[DatabaseConfig] = Field(default=None)
    security: Optional[SecurityConfig] = Field(default=None)

    model_config = {"extra": "allow"}  # Allow extra fields for flexibility

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create from dictionary for backward compatibility."""
        # Create nested configs
        vfs = VFSConfig.from_dict(data.get("vfs", {}))
        bot = BotConfig.from_dict(data.get("bot", {}))
        captcha = CaptchaConfig.from_dict(data.get("captcha", {}))
        notifications = NotificationConfig.from_dict(data.get("notifications", {}))

        return cls(
            vfs=vfs,
            bot=bot,
            captcha=captcha,
            notifications=notifications,
            anti_detection=(
                AntiDetectionConfig(**data.get("anti_detection", {}))
                if "anti_detection" in data
                else None
            ),
            credentials=(
                CredentialsConfig(**data.get("credentials", {})) if "credentials" in data else None
            ),
            appointments=(
                AppointmentsConfig(**data.get("appointments", {}))
                if "appointments" in data
                else None
            ),
            human_behavior=(
                HumanBehaviorConfig(**data.get("human_behavior", {}))
                if "human_behavior" in data
                else None
            ),
            session=SessionConfig(**data.get("session", {})) if "session" in data else None,
            cloudflare=(
                CloudflareConfig(**data.get("cloudflare", {})) if "cloudflare" in data else None
            ),
            proxy=ProxyConfig(**data.get("proxy", {})) if "proxy" in data else None,
            selector_health_check=(
                SelectorHealthCheckConfig(**data.get("selector_health_check", {}))
                if "selector_health_check" in data
                else None
            ),
            payment=PaymentConfig(**data.get("payment", {})) if "payment" in data else None,
            alerts=AlertsConfig(**data.get("alerts", {})) if "alerts" in data else None,
            database=DatabaseConfig(**data.get("database", {})) if "database" in data else None,
            security=SecurityConfig(**data.get("security", {})) if "security" in data else None,
        )
