"""Database state tracking and utilities."""

from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from src.core.exceptions import DatabaseNotConnectedError

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


class DatabaseState:
    """Database connection state constants."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


def require_connection(func: F) -> F:
    """
    Decorator to ensure database connection exists before method execution.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that checks for connection

    Raises:
        DatabaseNotConnectedError: If database connection is not established
    """

    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if self.pool is None:
            raise DatabaseNotConnectedError()
        return await func(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
