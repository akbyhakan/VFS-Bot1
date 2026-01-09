"""Database models module."""

# Lazy imports to avoid missing dependencies
__all__ = [
    "Database",
    "UserCreate",
    "UserResponse",
    "AppointmentCreate",
    "AppointmentResponse",
    "BotConfig",
    "NotificationConfig",
]


def __getattr__(name):
    """Lazy import of models."""
    if name == "Database":
        from .database import Database

        return Database
    elif name in [
        "UserCreate",
        "UserResponse",
        "AppointmentCreate",
        "AppointmentResponse",
        "BotConfig",
        "NotificationConfig",
    ]:
        from .schemas import (
            UserCreate,
            UserResponse,
            AppointmentCreate,
            AppointmentResponse,
            BotConfig,
            NotificationConfig,
        )

        return locals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
