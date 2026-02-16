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
from typing import Any, Dict, Optional

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

        def get_int_env(key: str, default: int) -> int:
            """Get integer from environment with error handling."""
            try:
                return int(os.getenv(key, default))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid value for {key}, using default {default}: {e}")
                return default

        def get_float_env(key: str, default: float) -> float:
            """Get float from environment with error handling."""
            try:
                return float(os.getenv(key, default))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid value for {key}, using default {default}: {e}")
                return default

        # Retry configuration
        self._config["retries.max_process_user"] = get_int_env(
            "RETRIES_MAX_PROCESS_USER", Retries.MAX_PROCESS_USER
        )
        self._config["retries.max_login"] = get_int_env("RETRIES_MAX_LOGIN", Retries.MAX_LOGIN)
        self._config["retries.max_booking"] = get_int_env(
            "RETRIES_MAX_BOOKING", Retries.MAX_BOOKING
        )
        self._config["retries.max_network"] = get_int_env(
            "RETRIES_MAX_NETWORK", Retries.MAX_NETWORK
        )
        self._config["retries.backoff_multiplier"] = get_int_env(
            "RETRIES_BACKOFF_MULTIPLIER", Retries.BACKOFF_MULTIPLIER
        )
        self._config["retries.backoff_min_seconds"] = get_int_env(
            "RETRIES_BACKOFF_MIN_SECONDS", Retries.BACKOFF_MIN_SECONDS
        )
        self._config["retries.backoff_max_seconds"] = get_int_env(
            "RETRIES_BACKOFF_MAX_SECONDS", Retries.BACKOFF_MAX_SECONDS
        )

        # Circuit breaker configuration
        self._config["circuit_breaker.fail_threshold"] = get_int_env(
            "CIRCUIT_BREAKER_FAIL_THRESHOLD", CircuitBreakerConfig.FAIL_THRESHOLD
        )
        self._config["circuit_breaker.timeout_seconds"] = get_float_env(
            "CIRCUIT_BREAKER_TIMEOUT_SECONDS", CircuitBreakerConfig.TIMEOUT_SECONDS
        )
        self._config["circuit_breaker.half_open_success_threshold"] = get_int_env(
            "CIRCUIT_BREAKER_HALF_OPEN_SUCCESS_THRESHOLD",
            CircuitBreakerConfig.HALF_OPEN_SUCCESS_THRESHOLD,
        )
        self._config["circuit_breaker.max_errors_per_hour"] = get_int_env(
            "CIRCUIT_BREAKER_MAX_ERRORS_PER_HOUR", CircuitBreakerConfig.MAX_ERRORS_PER_HOUR
        )
        self._config["circuit_breaker.error_window_seconds"] = get_int_env(
            "CIRCUIT_BREAKER_ERROR_WINDOW_SECONDS", CircuitBreakerConfig.ERROR_WINDOW_SECONDS
        )
        self._config["circuit_breaker.backoff_base_seconds"] = get_int_env(
            "CIRCUIT_BREAKER_BACKOFF_BASE_SECONDS", CircuitBreakerConfig.BACKOFF_BASE_SECONDS
        )
        self._config["circuit_breaker.backoff_max_seconds"] = get_int_env(
            "CIRCUIT_BREAKER_BACKOFF_MAX_SECONDS", CircuitBreakerConfig.BACKOFF_MAX_SECONDS
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
