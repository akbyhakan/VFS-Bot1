"""Common decorators for VFS-Bot."""

import asyncio
import functools
import logging
from typing import Callable, TypeVar, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def log_errors(
    reraise: bool = True,
    default_return: Any = None,
    log_level: int = logging.ERROR
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
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    f"{func.__module__}.{func.__name__} failed: {e}",
                    exc_info=True
                )
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    Decorator to retry async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch and retry
    
    Example:
        @retry_async(max_retries=3, delay=1.0)
        async def flaky_operation():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
            
            raise last_exception
        return wrapper
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
    async def wrapper(*args, **kwargs):
        start = datetime.now()
        try:
            result = await func(*args, **kwargs)
            elapsed = (datetime.now() - start).total_seconds()
            logger.debug(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds()
            logger.debug(f"{func.__name__} failed after {elapsed:.3f}s")
            raise
    return wrapper
