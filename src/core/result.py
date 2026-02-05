"""Result pattern for better error handling.

Provides a type-safe way to handle success and failure cases without exceptions.
"""

import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Generic, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass
class Success(Generic[T]):
    """Represents a successful result."""

    value: T

    def is_success(self) -> bool:
        """Check if result is successful."""
        return True

    def is_failure(self) -> bool:
        """Check if result is a failure."""
        return False

    def unwrap(self) -> T:
        """Get the success value."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the success value or a default."""
        return self.value

    def map(self, func: Callable[[T], U]) -> "Result[U, E]":
        """
        Apply a function to the success value.

        Args:
            func: Function to apply

        Returns:
            New Result with transformed value
        """
        try:
            return Success(func(self.value))
        except Exception as e:
            return Failure(str(e), e)

    def __repr__(self) -> str:
        """String representation."""
        return f"Success({self.value!r})"


@dataclass
class Failure(Generic[E]):
    """Represents a failed result."""

    error: str
    exception: Optional[Exception] = None

    def is_success(self) -> bool:
        """Check if result is successful."""
        return False

    def is_failure(self) -> bool:
        """Check if result is a failure."""
        return True

    def unwrap(self) -> Any:
        """
        Attempt to get value (raises exception).

        Raises:
            RuntimeError: Always, as this is a failure
        """
        raise RuntimeError(f"Called unwrap on Failure: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """
        Get the default value (success value is not available).

        Args:
            default: Default value to return

        Returns:
            The default value
        """
        return default

    def map(self, func: Callable[[Any], U]) -> "Result[U, E]":
        """
        Map operation on failure does nothing.

        Args:
            func: Function to apply (not called)

        Returns:
            Self (unchanged failure)
        """
        return self

    def __repr__(self) -> str:
        """String representation."""
        if self.exception:
            return f"Failure(error={self.error!r}, exception={type(self.exception).__name__})"
        return f"Failure(error={self.error!r})"


# Type alias for Result
Result = Union[Success[T], Failure[E]]


def try_result(func: Callable[..., T]) -> Callable[..., Result[T, str]]:
    """
    Decorator to wrap synchronous functions in Result pattern.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that returns Result

    Example:
        ```python
        @try_result
        def divide(a: int, b: int) -> float:
            return a / b

        result = divide(10, 2)  # Success(5.0)
        result = divide(10, 0)  # Failure("division by zero")
        ```
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Result[T, str]:
        try:
            value = func(*args, **kwargs)
            return Success(value)
        except Exception as e:
            logger.debug(f"{func.__name__} failed: {e}")
            return Failure(str(e), e)

    return wrapper


def try_async_result(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to wrap asynchronous functions in Result pattern.

    Args:
        func: Async function to wrap

    Returns:
        Wrapped async function that returns Result

    Example:
        ```python
        @try_async_result
        async def fetch_data(url: str) -> dict:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()

        result = await fetch_data("https://api.example.com/data")
        if result.is_success():
            data = result.unwrap()
        ```
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Result[Any, str]:
        try:
            value = await func(*args, **kwargs)
            return Success(value)
        except Exception as e:
            logger.debug(f"{func.__name__} failed: {e}")
            return Failure(str(e), e)

    return wrapper


# Convenience functions for creating Results
def ok(value: T) -> Success[T]:
    """
    Create a successful result.

    Args:
        value: Success value

    Returns:
        Success result
    """
    return Success(value)


def err(error: str, exception: Optional[Exception] = None) -> Failure[str]:
    """
    Create a failed result.

    Args:
        error: Error message
        exception: Optional exception object

    Returns:
        Failure result
    """
    return Failure(error, exception)
