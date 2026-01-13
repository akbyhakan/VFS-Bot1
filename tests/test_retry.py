"""Tests for retry strategies."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.retry import (
    get_login_retry,
    get_captcha_retry,
    get_slot_check_retry,
    get_network_retry,
    get_rate_limit_retry,
)
from src.core.exceptions import LoginError, CaptchaError, NetworkError, SlotCheckError, RateLimitError


def test_get_login_retry():
    """Test login retry decorator can be created."""
    retry_decorator = get_login_retry()
    assert retry_decorator is not None


def test_get_captcha_retry():
    """Test captcha retry decorator can be created."""
    retry_decorator = get_captcha_retry()
    assert retry_decorator is not None


def test_get_slot_check_retry():
    """Test slot check retry decorator can be created."""
    retry_decorator = get_slot_check_retry()
    assert retry_decorator is not None


def test_get_network_retry():
    """Test network retry decorator can be created."""
    retry_decorator = get_network_retry()
    assert retry_decorator is not None


def test_get_rate_limit_retry():
    """Test rate limit retry decorator can be created."""
    retry_decorator = get_rate_limit_retry()
    assert retry_decorator is not None


def test_login_retry_application():
    """Test that login retry decorator can be applied to a function."""
    retry_decorator = get_login_retry()
    
    attempt_count = [0]
    
    @retry_decorator
    def failing_function():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise LoginError("Test login error")
        return "success"
    
    result = failing_function()
    assert result == "success"
    assert attempt_count[0] == 3


def test_captcha_retry_application():
    """Test that captcha retry decorator can be applied to a function."""
    retry_decorator = get_captcha_retry()
    
    attempt_count = [0]
    
    @retry_decorator
    def failing_function():
        attempt_count[0] += 1
        if attempt_count[0] < 2:
            raise CaptchaError("Test captcha error")
        return "success"
    
    result = failing_function()
    assert result == "success"
    assert attempt_count[0] == 2


def test_network_retry_application():
    """Test that network retry decorator can be applied to a function."""
    retry_decorator = get_network_retry()
    
    attempt_count = [0]
    
    @retry_decorator
    def failing_function():
        attempt_count[0] += 1
        if attempt_count[0] < 2:
            raise NetworkError("Test network error")
        return "success"
    
    result = failing_function()
    assert result == "success"
    assert attempt_count[0] == 2


def test_slot_check_retry_application():
    """Test that slot check retry decorator can be applied to a function."""
    retry_decorator = get_slot_check_retry()
    
    attempt_count = [0]
    
    @retry_decorator
    def failing_function():
        attempt_count[0] += 1
        if attempt_count[0] < 2:
            raise SlotCheckError("Test slot check error")
        return "success"
    
    result = failing_function()
    assert result == "success"
    assert attempt_count[0] == 2


def test_rate_limit_retry_application():
    """Test that rate limit retry decorator can be applied to a function."""
    retry_decorator = get_rate_limit_retry()
    
    # For rate limit, we don't want to wait, just test it can be created
    attempt_count = [0]
    
    @retry_decorator
    def failing_function():
        attempt_count[0] += 1
        # Don't actually fail to avoid waiting
        return "success"
    
    result = failing_function()
    assert result == "success"
