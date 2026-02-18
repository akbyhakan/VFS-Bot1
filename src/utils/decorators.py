"""Common decorators for VFS-Bot."""

import asyncio
import functools
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional, Tuple, Type, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def handle_errors(
    operation_name: Optional[str] = None,
    reraise: bool = True,
    log_level: str = "error",
    wrap_error: bool = True,
    default_return: Any = None,
) -> Callable[[F], F]:
    """
    Decorator for consistent error handling across async and sync operations.

    Unified error handler that can both wrap exceptions in VFSBotError or simply log them.
    Replaces both the old handle_errors and log_errors decorators.

    Args:
        operation_name: Name of the operation for logging. If None, defaults to module.function_name
        reraise: Whether to reraise the exception after logging
        log_level: Logging level for errors (error, warning, info)
        wrap_error: If True, wraps exceptions in VFSBotError (default).
            If False, reraised original exception
        default_return: Value to return if not reraising (default: None)

    Examples:
        @handle_errors("fetch_data")  # Wraps in VFSBotError
        async def fetch_data():
            ...

        @handle_errors(wrap_error=False, reraise=False, default_return=[])  # Simple logging
        async def get_items():
            ...
    """

    def decorator(func: F) -> F:
        # Determine operation name
        op_name = (
            operation_name if operation_name is not None else f"{func.__module__}.{func.__name__}"
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Import here to avoid circular dependency
                from ..core.exceptions import VFSBotError

                # VFSBotError always passes through
                if isinstance(e, VFSBotError):
                    raise

                # CancelledError always passes through
                if isinstance(e, asyncio.CancelledError):
                    logger.info(f"{op_name} was cancelled")
                    raise

                # Log the error
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{op_name} failed: {e}", exc_info=True)

                if reraise:
                    if wrap_error:
                        raise VFSBotError(f"{op_name} failed: {str(e)}") from e
                    else:
                        raise
                return default_return

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Import here to avoid circular dependency
                from ..core.exceptions import VFSBotError

                # VFSBotError always passes through
                if isinstance(e, VFSBotError):
                    raise

                # Log the error
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{op_name} failed: {e}", exc_info=True)

                if reraise:
                    if wrap_error:
                        raise VFSBotError(f"{op_name} failed: {str(e)}") from e
                    else:
                        raise
                return default_return

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (ConnectionError, TimeoutError, OSError),
) -> Callable[[F], F]:
    """
    Decorator to retry async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch and retry (default: network/IO errors)

    Example:
        @retry_async(max_retries=3, delay=1.0)
        async def flaky_operation():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[BaseException] = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed "
                            f"(attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected error in retry logic")

        return wrapper  # type: ignore[return-value]

    return decorator


def timed_async(func: F) -> F:
    """
    Decorator to measure and log execution time of async functions.

    Example:
        @timed_async
        async def slow_operation():
            ...
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = datetime.now(timezone.utc)
        try:
            result = await func(*args, **kwargs)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            logger.debug(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            logger.debug(f"{func.__name__} failed after {elapsed:.3f}s")
            raise

    return wrapper  # type: ignore[return-value]
