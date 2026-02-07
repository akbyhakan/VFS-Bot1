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
- Service contexts: AntiDetectionContext, CoreServicesContext, WorkflowServicesContext,
  AutomationServicesContext, BotServiceContext, BotServiceFactory
"""

from .auth_service import AuthService
from .booking_workflow import BookingWorkflow
from .browser_manager import BrowserManager
from .circuit_breaker_service import CircuitBreakerService, CircuitBreakerStats
from .error_handler import ErrorHandler
from .service_context import (
    AntiDetectionContext,
    AutomationServicesContext,
    BotServiceContext,
    BotServiceFactory,
    CoreServicesContext,
    WorkflowServicesContext,
)
from .slot_checker import SlotChecker, SlotInfo
from .vfs_bot import VFSBot

__all__ = [
    "VFSBot",
    "BrowserManager",
    "AuthService",
    "BookingWorkflow",
    "SlotChecker",
    "SlotInfo",
    "CircuitBreakerService",
    "CircuitBreakerStats",
    "ErrorHandler",
    "AntiDetectionContext",
    "CoreServicesContext",
    "WorkflowServicesContext",
    "AutomationServicesContext",
    "BotServiceContext",
    "BotServiceFactory",
]
