"""Centralized enum definitions for VFS-Bot."""

from enum import Enum


class AppointmentRequestStatus(str, Enum):
    """Status values for appointment requests."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def values(cls) -> list:
        """Return list of all enum values."""
        return [e.value for e in cls]


class AppointmentStatus(str, Enum):
    """Status values for booked appointments."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> list:
        """Return list of all enum values."""
        return [e.value for e in cls]


class AppointmentHistoryStatus(str, Enum):
    """Status values for appointment history records."""
    FOUND = "found"
    BOOKED = "booked"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> list:
        """Return list of all enum values."""
        return [e.value for e in cls]


class MetricsStatus(str, Enum):
    """Status values for Prometheus metrics."""
    SUCCESS = "success"
    FAILED = "failed"

    @classmethod
    def values(cls) -> list:
        """Return list of all enum values."""
        return [e.value for e in cls]


class SlotCheckStatus(str, Enum):
    """Status values for slot check results."""
    FOUND = "found"
    NOT_FOUND = "not_found"

    @classmethod
    def values(cls) -> list:
        """Return list of all enum values."""
        return [e.value for e in cls]


class LogLevel(str, Enum):
    """Log level values for database logs."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @classmethod
    def values(cls) -> list:
        """Return list of all enum values."""
        return [e.value for e in cls]
