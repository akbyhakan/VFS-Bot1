"""Type definitions for VFS-Bot.

This module re-exports Pydantic configuration models from src.core.config.config_models
for backward compatibility. New code should import directly from src.core.config.config_models.
"""

from src.core.config.config_models import (
    AntiDetectionConfig,
    AppConfig,
    BotConfig,
    CaptchaConfig,
    NotificationConfig,
    VFSConfig,
)
from src.types.user import UserDict, UserDictWithOptionals

__all__ = [
    "VFSConfig",
    "BotConfig",
    "CaptchaConfig",
    "AntiDetectionConfig",
    "NotificationConfig",
    "AppConfig",
    "UserDict",
    "UserDictWithOptionals",
]
