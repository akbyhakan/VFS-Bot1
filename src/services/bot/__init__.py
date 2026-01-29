"""VFS Bot - Modular bot components with Single Responsibility Principle.

This module provides a refactored, modular architecture for the VFS appointment
booking bot, separating concerns into focused components.

Public API:
- VFSBot: Main orchestrator class
- BrowserManager: Browser lifecycle management
- AuthService: Authentication and login handling
- SlotChecker: Slot availability checking
- CircuitBreakerService: Fault tolerance and error tracking
- ErrorHandler: Error capture and screenshot handling
- SlotInfo: Type definition for slot information
"""

from .vfs_bot import VFSBot
from .browser_manager import BrowserManager
from .auth_service import AuthService
from .slot_checker import SlotChecker, SlotInfo
from .circuit_breaker_service import CircuitBreakerService, CircuitBreakerStats
from .error_handler import ErrorHandler

__all__ = [
    "VFSBot",
    "BrowserManager",
    "AuthService",
    "SlotChecker",
    "SlotInfo",
    "CircuitBreakerService",
    "CircuitBreakerStats",
    "ErrorHandler",
]
