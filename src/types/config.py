"""Type definitions for configuration dictionaries.

This module provides TypedDict definitions for configuration objects
used throughout the application, enhancing type safety and IDE support.
"""

from typing import TypedDict, List, Optional, Dict, Any


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


class NotificationConfig(TypedDict, total=False):
    """Notification services configuration."""
    
    telegram: Dict[str, Any]
    email: Dict[str, Any]


class AppConfig(TypedDict, total=False):
    """Complete application configuration.
    
    This is the main configuration structure that combines all
    configuration sections. Using total=False allows for optional fields.
    """
    
    vfs: VFSConfig
    bot: BotConfig
    captcha: CaptchaConfig
    anti_detection: AntiDetectionConfig
    notifications: NotificationConfig
    # Additional sections
    credentials: Dict[str, Any]
    appointments: Dict[str, Any]
    human_behavior: Dict[str, Any]
    session: Dict[str, Any]
    cloudflare: Dict[str, Any]
    proxy: Dict[str, Any]
    selector_health_check: Dict[str, Any]
