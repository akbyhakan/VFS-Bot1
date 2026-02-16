"""Tests for runtime configuration system."""

import os
from unittest.mock import patch

import pytest

from src.core.config.runtime_config import RuntimeConfig


@pytest.fixture(autouse=True)
def reset_runtime_config():
    """Reset RuntimeConfig before each test."""
    RuntimeConfig.reset()
    yield
    RuntimeConfig.reset()


def test_runtime_config_singleton():
    """Test RuntimeConfig is a singleton."""
    instance1 = RuntimeConfig()
    instance2 = RuntimeConfig()
    assert instance1 is instance2


def test_runtime_config_defaults():
    """Test RuntimeConfig loads defaults from constants."""
    # Verify retry defaults
    assert RuntimeConfig.get("retries.max_process_user") == 3
    assert RuntimeConfig.get("retries.max_login") == 3
    assert RuntimeConfig.get("retries.max_booking") == 2
    assert RuntimeConfig.get("retries.max_network") == 3
    assert RuntimeConfig.get("retries.backoff_multiplier") == 1
    assert RuntimeConfig.get("retries.backoff_min_seconds") == 4
    assert RuntimeConfig.get("retries.backoff_max_seconds") == 10

    # Verify circuit breaker defaults
    assert RuntimeConfig.get("circuit_breaker.fail_threshold") == 5
    assert RuntimeConfig.get("circuit_breaker.timeout_seconds") == 60.0
    assert RuntimeConfig.get("circuit_breaker.half_open_success_threshold") == 3
    assert RuntimeConfig.get("circuit_breaker.max_errors_per_hour") == 20


def test_runtime_config_get_with_default():
    """Test get method with default value."""
    value = RuntimeConfig.get("nonexistent.key", default=999)
    assert value == 999


def test_runtime_config_update():
    """Test updating configuration value."""
    # Update retry max_login
    RuntimeConfig.update("retries.max_login", 5)
    assert RuntimeConfig.get("retries.max_login") == 5

    # Update circuit breaker timeout
    RuntimeConfig.update("circuit_breaker.timeout_seconds", 120.0)
    assert RuntimeConfig.get("circuit_breaker.timeout_seconds") == 120.0


def test_runtime_config_update_invalid_key():
    """Test updating with invalid key raises ValueError."""
    with pytest.raises(ValueError, match="Invalid configuration key"):
        RuntimeConfig.update("invalid.nonexistent.key", 10)


def test_runtime_config_update_invalid_type():
    """Test updating with invalid type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid value type"):
        RuntimeConfig.update("retries.max_login", "not_an_integer")


def test_runtime_config_update_negative_value():
    """Test updating with negative value raises ValueError."""
    with pytest.raises(ValueError, match="must be non-negative"):
        RuntimeConfig.update("retries.max_login", -5)


def test_runtime_config_to_dict():
    """Test to_dict returns all configuration values."""
    config_dict = RuntimeConfig.to_dict()

    assert isinstance(config_dict, dict)
    assert "retries.max_login" in config_dict
    assert "circuit_breaker.fail_threshold" in config_dict
    assert len(config_dict) > 0


def test_runtime_config_reset():
    """Test reset restores defaults."""
    # Update some values
    RuntimeConfig.update("retries.max_login", 10)
    RuntimeConfig.update("circuit_breaker.fail_threshold", 20)

    assert RuntimeConfig.get("retries.max_login") == 10
    assert RuntimeConfig.get("circuit_breaker.fail_threshold") == 20

    # Reset
    RuntimeConfig.reset()

    # Verify defaults are restored
    assert RuntimeConfig.get("retries.max_login") == 3
    assert RuntimeConfig.get("circuit_breaker.fail_threshold") == 5


def test_runtime_config_env_override():
    """Test environment variables override defaults."""
    with patch.dict(
        os.environ,
        {
            "RETRIES_MAX_LOGIN": "7",
            "CIRCUIT_BREAKER_FAIL_THRESHOLD": "15",
        },
    ):
        # Create new instance with env vars
        RuntimeConfig.reset()

        assert RuntimeConfig.get("retries.max_login") == 7
        assert RuntimeConfig.get("circuit_breaker.fail_threshold") == 15


def test_runtime_config_thread_safety():
    """Test RuntimeConfig is thread-safe."""
    import threading

    errors = []

    def update_config(value):
        try:
            RuntimeConfig.update("retries.max_login", value)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update_config, args=(i,)) for i in range(1, 6)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # No errors should occur
    assert len(errors) == 0

    # Final value should be one of the updates
    final_value = RuntimeConfig.get("retries.max_login")
    assert final_value in range(1, 6)


def test_runtime_config_persistence_across_gets():
    """Test updated values persist across multiple get calls."""
    RuntimeConfig.update("retries.max_login", 8)

    # Multiple get calls should return same value
    assert RuntimeConfig.get("retries.max_login") == 8
    assert RuntimeConfig.get("retries.max_login") == 8
    assert RuntimeConfig.get("retries.max_login") == 8
