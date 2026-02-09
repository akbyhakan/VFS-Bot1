"""VFS Appointment Booking Package - Modular Structure.

This package provides a modular structure for VFS appointment booking,
split into specialized components for better maintainability.
"""

from .selector_utils import (
    get_selector,
    get_selector_with_fallback,
    resolve_selector,
    try_selectors,
    TURKISH_MONTHS,
    DOUBLE_MATCH_PATTERNS,
)
from .form_filler import FormFiller
from .slot_selector import SlotSelector
from .payment_handler import PaymentHandler
from .booking_validator import BookingValidator
from .booking_orchestrator import BookingOrchestrator

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
