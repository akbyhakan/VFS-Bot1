"""DRY decorator for safe Telegram calls — handles ImportError and general exceptions."""

import functools
from typing import Any, Callable

from loguru import logger


def safe_telegram_call(operation_name: str) -> Callable:
    """
    Async decorator that wraps a Telegram operation with uniform error handling.

    Catches ImportError (python-telegram-bot not installed) and any other Exception,
    logs them and returns False. The decorated coroutine always returns bool.

    Args:
        operation_name: Human-readable label used in log messages.

    Usage::

        @safe_telegram_call("send message")
        async def send(self, ...) -> bool:
            ...  # may raise ImportError or Exception

    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> bool:
            try:
                return await func(*args, **kwargs)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
                return False
            except Exception as e:
                logger.error(f"Telegram {operation_name} failed: {e}")
                return False

        return wrapper

    return decorator
