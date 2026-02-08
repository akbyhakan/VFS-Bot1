"""Type definitions for configuration dictionaries.

This module provides TypedDict definitions for configuration objects
used throughout the application, enhancing type safety and IDE support.
"""

from typing import Any, Dict, List, Optional, TypedDict


class VFSConfig(TypedDict, total=False):
    """VFS-specific configuration."""

    base_url: str
    country: str
    mission: str
    centres: List[str]
    category: str
    subcategory: str
    language: Optional[str]


class BotConfig(TypedDict, total=False):
    """Bot behavior configuration."""

    check_interval: int
    headless: bool
    screenshot_on_error: bool
    max_retries: int
    browser_restart_after_pages: int


class CaptchaConfig(TypedDict, total=False):
    """Captcha solver configuration."""

    provider: str
    api_key: str
    manual_timeout: int


class AntiDetectionConfig(TypedDict, total=False):
    """Anti-detection features configuration."""

    enabled: bool
    tls_bypass: Optional[bool]
    fingerprint_bypass: Optional[bool]
    human_simulation: Optional[bool]
    stealth_mode: Optional[bool]


class TelegramConfig(TypedDict, total=False):
    """Telegram notification configuration."""

    bot_token: str
    chat_id: str


class EmailConfig(TypedDict, total=False):
    """Email notification configuration."""

    smtp_host: str
    smtp_port: int
    from_addr: str
    to_addr: str


class NotificationConfig(TypedDict, total=False):
    """Notification services configuration."""

    telegram: TelegramConfig
    email: EmailConfig


class CredentialsConfig(TypedDict, total=False):
    """Admin credentials configuration."""

    admin_username: str
    admin_password: str


class ProxyConfig(TypedDict, total=False):
    """Proxy configuration."""

    enabled: bool
    rotation_interval: int


class SessionConfig(TypedDict, total=False):
    """Session configuration."""

    timeout: int
    max_retries: int


class CloudflareConfig(TypedDict, total=False):
    """Cloudflare handling configuration."""

    enabled: bool
    solver: str
    timeout: int


class HumanBehaviorConfig(TypedDict, total=False):
    """Human behavior simulation configuration."""

    enabled: bool
    min_delay: float
    max_delay: float


class PaymentConfig(TypedDict, total=False):
    """Payment configuration."""

    method: str
    timeout: int


class AlertsConfig(TypedDict, total=False):
    """Alert service configuration."""

    enabled_channels: List[str]
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    webhook_url: Optional[str]


class SelectorHealthCheckConfig(TypedDict, total=False):
    """Selector health check configuration."""

    enabled: bool
    interval: int


class AppointmentsConfig(TypedDict, total=False):
    """Appointments configuration."""

    max_concurrent: int
    retry_delay: int


class AppConfig(TypedDict, total=False):
    """Complete application configuration.

    This is the main configuration structure that combines all
    configuration sections.

    Note: total=False allows fields to be omitted at dictionary creation
    time but doesn't affect the type system. Fields that may be missing
    at runtime should be accessed with .get() method.

    Important: Callers should validate that required configuration sections
    (vfs, bot, captcha, etc.) are present and contain necessary values before
    passing to components that depend on them. Use ConfigValidator.validate()
    to ensure configuration completeness.
    """

    vfs: VFSConfig
    bot: BotConfig
    captcha: CaptchaConfig
    anti_detection: AntiDetectionConfig
    notifications: NotificationConfig
    credentials: CredentialsConfig
    appointments: AppointmentsConfig
    human_behavior: HumanBehaviorConfig
    session: SessionConfig
    cloudflare: CloudflareConfig
    proxy: ProxyConfig
    selector_health_check: SelectorHealthCheckConfig
    payment: PaymentConfig
    alerts: AlertsConfig
