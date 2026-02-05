"""Type definitions for VFS-Bot.

This module exports TypedDict definitions for configuration objects
to improve type safety across the application.
"""

from .config import (
    AntiDetectionConfig,
    AppConfig,
    BotConfig,
    CaptchaConfig,
    NotificationConfig,
    VFSConfig,
)

__all__ = [
    "VFSConfig",
    "BotConfig",
    "CaptchaConfig",
    "AntiDetectionConfig",
    "NotificationConfig",
    "AppConfig",
]
