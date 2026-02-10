"""Tests for core/retry module."""

import pytest

from src.core.exceptions import (
    CaptchaError,
    LoginError,
    NetworkError,
    RateLimitError,
    SlotCheckError,
)
from src.core.retry import (
    get_captcha_retry,
    get_login_retry,
    get_network_retry,
    get_rate_limit_retry,
    get_slot_check_retry,
)


class TestRetryStrategies:
    """Tests for retry strategy functions."""

    def test_get_login_retry_returns_decorator(self):
        """Test that get_login_retry returns a retry decorator."""
        retry_decorator = get_login_retry()
        assert retry_decorator is not None
        assert callable(retry_decorator)

    def test_get_captcha_retry_returns_decorator(self):
        """Test that get_captcha_retry returns a retry decorator."""
        retry_decorator = get_captcha_retry()
        assert retry_decorator is not None
        assert callable(retry_decorator)

    def test_get_slot_check_retry_returns_decorator(self):
        """Test that get_slot_check_retry returns a retry decorator."""
        retry_decorator = get_slot_check_retry()
        assert retry_decorator is not None
        assert callable(retry_decorator)

    def test_get_network_retry_returns_decorator(self):
        """Test that get_network_retry returns a retry decorator."""
        retry_decorator = get_network_retry()
        assert retry_decorator is not None
        assert callable(retry_decorator)

    def test_get_rate_limit_retry_returns_decorator(self):
        """Test that get_rate_limit_retry returns a retry decorator."""
        retry_decorator = get_rate_limit_retry()
        assert retry_decorator is not None
        assert callable(retry_decorator)

    def test_login_retry_decorator_usage(self):
        """Test using login retry decorator."""
        retry_decorator = get_login_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise LoginError("Login failed")
            return "success"

        result = test_func()
        assert result == "success"
        assert counter["calls"] == 2

    def test_captcha_retry_decorator_usage(self):
        """Test using captcha retry decorator."""
        retry_decorator = get_captcha_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise CaptchaError("Captcha failed")
            return "solved"

        result = test_func()
        assert result == "solved"
        assert counter["calls"] == 2

    def test_slot_check_retry_decorator_usage(self):
        """Test using slot check retry decorator."""
        retry_decorator = get_slot_check_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise SlotCheckError("Slot check failed")
            return "checked"

        result = test_func()
        assert result == "checked"
        assert counter["calls"] == 2

    def test_network_retry_decorator_usage(self):
        """Test using network retry decorator."""
        retry_decorator = get_network_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise NetworkError("Network failed")
            return "connected"

        result = test_func()
        assert result == "connected"
        assert counter["calls"] == 2

    def test_rate_limit_retry_max_attempts(self):
        """Test that rate limit retry stops after max attempts."""
        retry_decorator = get_rate_limit_retry()

        @retry_decorator
        def always_fails():
            raise RateLimitError("Rate limited")

        with pytest.raises(RateLimitError):
            always_fails()

    def test_login_retry_with_network_error(self):
        """Test login retry also retries on NetworkError."""
        retry_decorator = get_login_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise NetworkError("Network error")
            return "success"

        result = test_func()
        assert result == "success"
        assert counter["calls"] == 2

    def test_slot_check_retry_with_network_error(self):
        """Test slot check retry also retries on NetworkError."""
        retry_decorator = get_slot_check_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise NetworkError("Network error")
            return "checked"

        result = test_func()
        assert result == "checked"
        assert counter["calls"] == 2

    def test_retry_success_on_first_try(self):
        """Test that retry doesn't retry on success."""
        retry_decorator = get_login_retry()
        counter = {"calls": 0}

        @retry_decorator
        def test_func():
            counter["calls"] += 1
            return "success"

        result = test_func()
        assert result == "success"
        assert counter["calls"] == 1
