"""VFS Appointment Booking Package - Modular Structure.

This package provides a modular structure for VFS appointment booking,
split into specialized components for better maintainability.
"""

from .booking_orchestrator import BookingOrchestrator
from .booking_validator import BookingValidator
from .form_filler import FormFiller
from .payment_handler import PaymentHandler
from .selector_utils import (
    DOUBLE_MATCH_PATTERNS,
    TURKISH_MONTHS,
    get_selector,
    get_selector_with_fallback,
    resolve_selector,
    try_selectors,
)
from .slot_selector import SlotSelector

__all__ = [
    # Main service
    "BookingOrchestrator",
    # Components
    "FormFiller",
    "SlotSelector",
    "PaymentHandler",
    "BookingValidator",
    # Selector utilities
    "get_selector",
    "get_selector_with_fallback",
    "resolve_selector",
    "try_selectors",
    # Constants
    "TURKISH_MONTHS",
    "DOUBLE_MATCH_PATTERNS",
]
