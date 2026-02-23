"""Runtime configuration system for dynamic parameter updates.

This module provides a RuntimeConfig singleton that allows runtime updates
to retry and circuit breaker parameters without requiring application restart.

Environment variables take precedence, followed by the Final constants from
src/constants.py as defaults.

Example:
    ```python
    from src.core.config.runtime_config import RuntimeConfig

    # Get a value (with automatic fallback to constants)
    max_login_retries = RuntimeConfig.get("retries.max_login", default=3)

    # Update a value at runtime
    RuntimeConfig.update("retries.max_login", 5)

    # Get all config as dict
    config_dict = RuntimeConfig.to_dict()
    ```
"""

import os
import threading
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")

from loguru import logger

from src.constants import CircuitBreakerConfig, Retries


class RuntimeConfig:
    """
    Singleton class for runtime configuration management.

    Provides thread-safe access to configuration values that can be updated
    at runtime without application restart.
    """

    _instance: Optional["RuntimeConfig"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure singleton pattern with thread-safe instantiation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize runtime configuration with defaults from environment or constants."""
        if hasattr(self, "_initialized"):
            return

        self._config: Dict[str, Any] = {}
        self._config_lock = threading.RLock()

        # Initialize with defaults from environment or constants
        self._load_defaults()
        self._initialized = True
        logger.info("RuntimeConfig initialized with defaults")

    def _load_defaults(self) -> None:
        """Load default values from environment variables or Final constants."""

        def _get_typed_env(key: str, default: T, cast: Callable[[Any], T]) -> T:
            """Get typed value from environment with error handling."""
            try:
                return cast(os.getenv(key, default))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid value for {key}, using default {default}: {e}")
                return default

        # Retry configuration
        self._config["retries.max_process_user"] = _get_typed_env(
            "RETRIES_MAX_PROCESS_USER", Retries.MAX_PROCESS_USER, int
        )
        self._config["retries.max_login"] = _get_typed_env(
            "RETRIES_MAX_LOGIN", Retries.MAX_LOGIN, int
        )
        self._config["retries.max_booking"] = _get_typed_env(
            "RETRIES_MAX_BOOKING", Retries.MAX_BOOKING, int
        )
        self._config["retries.max_network"] = _get_typed_env(
            "RETRIES_MAX_NETWORK", Retries.MAX_NETWORK, int
        )
        self._config["retries.backoff_multiplier"] = _get_typed_env(
            "RETRIES_BACKOFF_MULTIPLIER", Retries.BACKOFF_MULTIPLIER, int
        )
        self._config["retries.backoff_min_seconds"] = _get_typed_env(
            "RETRIES_BACKOFF_MIN_SECONDS", Retries.BACKOFF_MIN_SECONDS, int
        )
        self._config["retries.backoff_max_seconds"] = _get_typed_env(
            "RETRIES_BACKOFF_MAX_SECONDS", Retries.BACKOFF_MAX_SECONDS, int
        )

        # Circuit breaker configuration
        self._config["circuit_breaker.fail_threshold"] = _get_typed_env(
            "CIRCUIT_BREAKER_FAIL_THRESHOLD", CircuitBreakerConfig.FAIL_THRESHOLD, int
        )
        self._config["circuit_breaker.timeout_seconds"] = _get_typed_env(
            "CIRCUIT_BREAKER_TIMEOUT_SECONDS", CircuitBreakerConfig.TIMEOUT_SECONDS, float
        )
        self._config["circuit_breaker.half_open_success_threshold"] = _get_typed_env(
            "CIRCUIT_BREAKER_HALF_OPEN_SUCCESS_THRESHOLD",
            CircuitBreakerConfig.HALF_OPEN_SUCCESS_THRESHOLD,
            int,
        )
        self._config["circuit_breaker.max_errors_per_hour"] = _get_typed_env(
            "CIRCUIT_BREAKER_MAX_ERRORS_PER_HOUR", CircuitBreakerConfig.MAX_ERRORS_PER_HOUR, int
        )
        self._config["circuit_breaker.error_window_seconds"] = _get_typed_env(
            "CIRCUIT_BREAKER_ERROR_WINDOW_SECONDS", CircuitBreakerConfig.ERROR_WINDOW_SECONDS, int
        )
        self._config["circuit_breaker.backoff_base_seconds"] = _get_typed_env(
            "CIRCUIT_BREAKER_BACKOFF_BASE_SECONDS", CircuitBreakerConfig.BACKOFF_BASE_SECONDS, int
        )
        self._config["circuit_breaker.backoff_max_seconds"] = _get_typed_env(
            "CIRCUIT_BREAKER_BACKOFF_MAX_SECONDS", CircuitBreakerConfig.BACKOFF_MAX_SECONDS, int
        )

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration key (e.g., "retries.max_login")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        instance = cls()
        with instance._config_lock:
            return instance._config.get(key, default)

    @classmethod
    def update(cls, key: str, value: Any) -> None:
        """
        Update a configuration value at runtime.

        Args:
            key: Configuration key (e.g., "retries.max_login")
            value: New value to set

        Raises:
            ValueError: If key is invalid or value is invalid type
        """
        instance = cls()

        # Validate key exists
        if key not in instance._config:
            raise ValueError(f"Invalid configuration key: {key}")

        # Validate value type matches expected type
        current_value = instance._config[key]
        expected_type = type(current_value)

        if not isinstance(value, expected_type):
            raise ValueError(
                f"Invalid value type for {key}: expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

        # Validate value ranges
        if isinstance(value, (int, float)):
            if value < 0:
                raise ValueError(f"Invalid value for {key}: must be non-negative")

        with instance._config_lock:
            old_value = instance._config[key]
            instance._config[key] = value
            logger.info(f"RuntimeConfig updated: {key} = {value} (was {old_value})")

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """
        Get all configuration values as a dictionary.

        Returns:
            Dictionary of all configuration values
        """
        instance = cls()
        with instance._config_lock:
            return dict(instance._config)

    @classmethod
    def reset(cls) -> None:
        """
        Reset configuration to defaults.

        This is primarily for testing purposes.
        """
        instance = cls()
        with instance._config_lock:
            instance._config.clear()
            instance._load_defaults()
            logger.info("RuntimeConfig reset to defaults")
