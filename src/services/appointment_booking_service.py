"""DEPRECATED: Use src/services/booking/ package instead."""
import warnings

warnings.warn(
    "appointment_booking_service module is deprecated. "
    "Use src.services.booking package instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .booking import (
    AppointmentBookingService,
    get_selector,
    get_selector_with_fallback,
    resolve_selector,
    try_selectors,
)

__all__ = [
    "AppointmentBookingService",
    "get_selector",
    "get_selector_with_fallback",
    "resolve_selector",
    "try_selectors",
]
