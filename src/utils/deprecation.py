"""Deprecation utilities for clean module transitions."""

import warnings
import functools
from typing import Callable, TypeVar, Optional

F = TypeVar("F", bound=Callable)


def deprecated(reason: str, replacement: Optional[str] = None):
    """
    Decorator to mark functions/classes as deprecated.

    Args:
        reason: Reason for deprecation
        replacement: Optional replacement function/class name

    Returns:
        Decorator function

    Example:
        @deprecated("Old function", replacement="new_function")
        def old_function():
            pass
    """

    def decorator(func: F) -> F:
        message = f"{func.__name__} is deprecated. {reason}"
        if replacement:
            message += f" Use {replacement} instead."

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def deprecated_module(old_module: str, new_module: str) -> None:
    """
    Issue deprecation warning for module-level imports.

    Args:
        old_module: Old module path
        new_module: New module path

    Example:
        deprecated_module("src.notification", "src.services.notification")
    """
    warnings.warn(
        f"{old_module} is deprecated. Use {new_module} instead.", DeprecationWarning, stacklevel=3
    )
