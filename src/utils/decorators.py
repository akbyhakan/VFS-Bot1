"""Common decorators for VFS-Bot."""

import asyncio
import functools
import logging
from typing import Callable, TypeVar, Any, Optional, Awaitable, Tuple, Type
from datetime import datetime

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def handle_errors(
    operation_name: str, reraise: bool = True, log_level: str = "error"
) -> Callable[[F], F]:
    """
    Decorator for consistent error handling across async operations.

    Args:
        operation_name: Name of the operation for logging
        reraise: Whether to reraise the exception
        log_level: Logging level for errors (error, warning, info)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Import here to avoid circular dependency
                from ..core.exceptions import VFSBotError

                if isinstance(e, VFSBotError):
                    raise  # Already handled, reraise as-is
                if isinstance(e, asyncio.CancelledError):
                    logger.info(f"{operation_name} was cancelled")
                    raise

                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{operation_name} failed: {e}", exc_info=True)
                if reraise:
                    raise VFSBotError(f"{operation_name} failed: {str(e)}") from e
                return None

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Import here to avoid circular dependency
                from ..core.exceptions import VFSBotError

                if isinstance(e, VFSBotError):
                    raise

                log_func = getattr(logger, log_level, logger.error)
                log_func(f"{operation_name} failed: {e}", exc_info=True)
                if reraise:
                    raise VFSBotError(f"{operation_name} failed: {str(e)}") from e
                return None

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def log_errors(
    reraise: bool = True, default_return: Any = None, log_level: int = logging.ERROR
) -> Callable[[F], F]:
    """
    Decorator to log errors from async functions.

    Args:
        reraise: Whether to reraise the exception after logging
        default_return: Value to return if not reraising
        log_level: Logging level for errors

    Example:
        @log_errors(reraise=False, default_return=[])
        async def get_items():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level, f"{func.__module__}.{func.__name__} failed: {e}", exc_info=True
                )
                if reraise:
                    raise
                return default_return

        return wrapper  # type: ignore[return-value]

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
        start = datetime.now()
        try:
            result = await func(*args, **kwargs)
            elapsed = (datetime.now() - start).total_seconds()
            logger.debug(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception:
            elapsed = (datetime.now() - start).total_seconds()
            logger.debug(f"{func.__name__} failed after {elapsed:.3f}s")
            raise

    return wrapper  # type: ignore[return-value]
