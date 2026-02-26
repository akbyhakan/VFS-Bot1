"""Database state tracking and utilities."""

from enum import Enum


class DatabaseState(Enum):
    """Database connection state constants."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
