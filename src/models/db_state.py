"""Database state tracking and utilities."""

from enum import Enum


class DatabaseState(str, Enum):
    """
    Database connection state constants.

    Inherits from str for backward compatibility with existing string
    comparisons, f-strings, JSON serialization, and metadata logging.
    """

    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
