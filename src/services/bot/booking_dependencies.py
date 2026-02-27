"""Dependency containers for BookingWorkflow to fix God Object anti-pattern."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...repositories import AppointmentRepository, AppointmentRequestRepository
    from ...repositories.payment_repository import PaymentRepository
    from ...utils.anti_detection.human_simulator import HumanSimulator
    from ...utils.error_capture import ErrorCapture
    from ...utils.security.header_manager import HeaderManager
    from ...utils.security.proxy_manager import ProxyManager
    from ..booking import BookingOrchestrator
    from ..notification.alert_service import AlertService
    from ..notification.notification import NotificationService  # noqa: F401
    from ..session.session_recovery import SessionRecovery
    from ..slot_analyzer import SlotPatternAnalyzer
    from .auth_service import AuthService
    from .browser_manager import BrowserManager
    from .error_handler import ErrorHandler
    from .page_state_detector import PageStateDetector
    from .slot_checker import SlotChecker
    from .waitlist_handler import WaitlistHandler


@dataclass
class WorkflowServices:
    """Core workflow services (auth, slots, booking)."""

    auth_service: "AuthService"
    slot_checker: "SlotChecker"
    booking_service: "BookingOrchestrator"
    waitlist_handler: "WaitlistHandler"
    error_handler: "ErrorHandler"
    page_state_detector: "PageStateDetector"
    slot_analyzer: "SlotPatternAnalyzer"
    session_recovery: "SessionRecovery"
    alert_service: Optional["AlertService"] = None


@dataclass
class InfraServices:
    """Infrastructure services (browser, proxy, headers, anti-detection)."""

    browser_manager: Optional["BrowserManager"] = None
    header_manager: Optional["HeaderManager"] = None
    proxy_manager: Optional["ProxyManager"] = None
    human_sim: Optional["HumanSimulator"] = None
    error_capture: Optional["ErrorCapture"] = None


@dataclass
class RepositoryServices:
    """Repository dependencies for data access."""

    appointment_repo: "AppointmentRepository"
    appointment_request_repo: "AppointmentRequestRepository"
    payment_repo: Optional["PaymentRepository"] = None


@dataclass
class BookingDependencies:
    """All dependencies for BookingWorkflow, grouped by responsibility."""

    workflow: WorkflowServices
    infra: InfraServices
    repositories: RepositoryServices
