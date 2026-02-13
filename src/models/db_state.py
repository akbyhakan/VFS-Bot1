"""Database state tracking and utilities."""


class DatabaseState:
    """Database connection state constants."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
