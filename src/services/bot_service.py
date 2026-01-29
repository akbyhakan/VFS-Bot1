"""
Backward compatibility layer for bot_service module.

This module maintains backward compatibility with existing code that imports
from bot_service. New code should use the modular components from src.services.bot.

Example:
    # Old way (still works)
    from src.services.bot_service import VFSBot
    
    # New way (recommended)
    from src.services.bot import VFSBot
"""

import warnings
from typing import TypedDict

# Re-export all public components from new modular structure
from .bot import (
    VFSBot,
    BrowserManager,
    AuthService,
    SlotChecker,
    SlotInfo,
    CircuitBreakerService,
    CircuitBreakerStats,
    ErrorHandler,
)

# Emit deprecation warning when this module is imported directly
warnings.warn(
    "Importing from bot_service is deprecated. "
    "Use 'from src.services.bot import VFSBot' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "VFSBot",
    "SlotInfo",
    "UserInfo",
    "BrowserManager",
    "AuthService",
    "SlotChecker",
    "CircuitBreakerService",
    "CircuitBreakerStats",
    "ErrorHandler",
]


# Legacy TypedDict for backward compatibility
class UserInfo(TypedDict):
    """User information from database."""

    id: int
    email: str
    password: str
    centre: str
    category: str
    subcategory: str
    active: bool
