"""VFS Bot - Modular bot components with Single Responsibility Principle.

This module provides a refactored, modular architecture for the VFS appointment
booking bot, separating concerns into focused components.

Public API:
- VFSBot: Main orchestrator class
- BrowserManager: Browser lifecycle management
- AuthService: Authentication and login handling
- SlotChecker: Slot availability checking
- ErrorHandler: Error capture and screenshot handling
- SlotInfo: Type definition for slot information
- Service contexts: AntiDetectionContext, CoreServicesContext, WorkflowServicesContext,
  AutomationServicesContext, BotServiceContext, BotServiceFactory
- BookingWorkflow: Main booking workflow orchestrator
- ReservationBuilder: Reservation data structure builder
- BookingExecutor: Booking execution and confirmation
- MissionProcessor: Multi-mission appointment processing
"""

from .auth_service import AuthService
from .booking_executor import BookingExecutor
from .booking_workflow import BookingWorkflow
from .browser_manager import BrowserManager
from .error_handler import ErrorHandler
from .mission_processor import MissionProcessor
from .reservation_builder import ReservationBuilder
from .service_context import (
    AntiDetectionContext,
    AutomationServicesContext,
    BotServiceContext,
    BotServiceFactory,
    CoreServicesContext,
    WorkflowServicesContext,
)
from .slot_checker import SlotChecker, SlotInfo
from .types import PersonDict, ReservationDict
from .vfs_bot import VFSBot

__all__ = [
    "VFSBot",
    "BrowserManager",
    "AuthService",
    "BookingWorkflow",
    "ReservationBuilder",
    "BookingExecutor",
    "MissionProcessor",
    "SlotChecker",
    "SlotInfo",
    "ErrorHandler",
    "PersonDict",
    "ReservationDict",
    "AntiDetectionContext",
    "CoreServicesContext",
    "WorkflowServicesContext",
    "AutomationServicesContext",
    "BotServiceContext",
    "BotServiceFactory",
]
