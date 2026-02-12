"""Singleton registry for centralized singleton pattern management.

This module provides thread-safe and async-safe singleton registry helpers
to eliminate boilerplate code across the codebase.
"""

import asyncio
import threading
from typing import Any, Callable, Dict, Optional, TypeVar

from loguru import logger

T = TypeVar("T")

# Global singleton registry
_instances: Dict[str, Any] = {}
_sync_locks: Dict[str, threading.Lock] = {}
_async_locks: Dict[str, asyncio.Lock] = {}
_registry_lock = threading.Lock()


def get_or_create_sync(
    key: str, factory: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """
    Get or create a singleton instance using thread-safe double-checked locking.

    Args:
        key: Unique key for the singleton instance
        factory: Factory function to create the instance
        *args: Positional arguments for factory
        **kwargs: Keyword arguments for factory

    Returns:
        Singleton instance

    Example:
        def create_service(config):
            return MyService(config)

        service = get_or_create_sync("my_service", create_service, config=my_config)
    """
    # Fast path: instance already exists
    if key in _instances:
        return _instances[key]

    # Ensure lock exists for this key
    with _registry_lock:
        if key not in _sync_locks:
            _sync_locks[key] = threading.Lock()
        lock = _sync_locks[key]

    # Double-checked locking
    with lock:
        if key not in _instances:
            instance = factory(*args, **kwargs)
            _instances[key] = instance
            logger.debug(f"Created singleton instance: {key}")
        return _instances[key]


async def get_or_create_async(
    key: str, factory: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """
    Get or create a singleton instance using async-safe double-checked locking.

    Args:
        key: Unique key for the singleton instance
        factory: Factory function to create the instance (can be async or sync)
        *args: Positional arguments for factory
        **kwargs: Keyword arguments for factory

    Returns:
        Singleton instance

    Example:
        async def create_service(config):
            return MyAsyncService(config)

        service = await get_or_create_async("my_async_service", create_service, config=my_config)
    """
    # Fast path: instance already exists
    if key in _instances:
        return _instances[key]

    # Ensure lock exists for this key
    # Use threading lock for the lock creation to avoid async issues
    with _registry_lock:
        if key not in _async_locks:
            _async_locks[key] = asyncio.Lock()
        lock = _async_locks[key]

    # Double-checked locking
    async with lock:
        if key not in _instances:
            # Support both async and sync factories
            if asyncio.iscoroutinefunction(factory):
                instance = await factory(*args, **kwargs)
            else:
                instance = factory(*args, **kwargs)
            _instances[key] = instance
            logger.debug(f"Created async singleton instance: {key}")
        return _instances[key]


def reset(key: Optional[str] = None) -> None:
    """
    Reset singleton instances (primarily for testing).

    Args:
        key: Specific key to reset, or None to reset all instances

    Example:
        # Reset a specific singleton
        reset("my_service")

        # Reset all singletons (useful in test teardown)
        reset()
    """
    with _registry_lock:
        if key is None:
            # Reset all instances
            count = len(_instances)
            _instances.clear()
            _sync_locks.clear()
            _async_locks.clear()
            logger.debug(f"Reset all {count} singleton instances")
        elif key in _instances:
            # Reset specific instance
            del _instances[key]
            _sync_locks.pop(key, None)
            _async_locks.pop(key, None)
            logger.debug(f"Reset singleton instance: {key}")


def get_instance(key: str) -> Optional[Any]:
    """
    Get an existing singleton instance without creating it.

    Args:
        key: Singleton key

    Returns:
        Singleton instance or None if not created yet

    Example:
        service = get_instance("my_service")
        if service is None:
            print("Service not initialized yet")
    """
    return _instances.get(key)


def list_instances() -> Dict[str, Any]:
    """
    Get all singleton instances (for debugging/inspection).

    Returns:
        Dictionary of all singleton instances

    Example:
        instances = list_instances()
        print(f"Active singletons: {list(instances.keys())}")
    """
    return _instances.copy()
