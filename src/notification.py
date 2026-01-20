"""DEPRECATED: Use src.services.notification instead."""

import warnings

# Issue deprecation warning
warnings.warn(
    "src.notification is deprecated. Use src.services.notification instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from src.services.notification import NotificationService, NotificationPriority

__all__ = ["NotificationService", "NotificationPriority"]
