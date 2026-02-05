"""Tests for custom exceptions."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.exceptions import (
    AuthenticationError,
    BookingError,
    CaptchaError,
    ConfigurationError,
    LoginError,
    NetworkError,
    RateLimitError,
    SelectorNotFoundError,
    SlotCheckError,
    VFSBotError,
)


def test_vfsbot_error():
    """Test VFSBotError base exception."""
    error = VFSBotError("Test error")
    assert error.message == "Test error"
    assert error.recoverable is True
    assert str(error) == "Test error"


def test_vfsbot_error_not_recoverable():
    """Test VFSBotError with recoverable=False."""
    error = VFSBotError("Fatal error", recoverable=False)
    assert error.message == "Fatal error"
    assert error.recoverable is False


def test_login_error_default():
    """Test LoginError with default message."""
    error = LoginError()
    assert error.message == "Login failed"
    assert error.recoverable is True


def test_login_error_custom():
    """Test LoginError with custom message."""
    error = LoginError("Invalid credentials")
    assert error.message == "Invalid credentials"


def test_login_error_not_recoverable():
    """Test LoginError with recoverable=False."""
    error = LoginError(recoverable=False)
    assert error.recoverable is False


def test_captcha_error_default():
    """Test CaptchaError with default message."""
    error = CaptchaError()
    assert error.message == "Captcha verification failed"
    assert error.recoverable is True


def test_captcha_error_custom():
    """Test CaptchaError with custom message."""
    error = CaptchaError("Captcha timeout")
    assert error.message == "Captcha timeout"


def test_slot_check_error_default():
    """Test SlotCheckError with default message."""
    error = SlotCheckError()
    assert error.message == "Slot check failed"
    assert error.recoverable is True


def test_slot_check_error_custom():
    """Test SlotCheckError with custom message."""
    error = SlotCheckError("No slots available")
    assert error.message == "No slots available"


def test_booking_error_default():
    """Test BookingError with default message."""
    error = BookingError()
    assert error.message == "Booking failed"
    assert error.recoverable is False  # BookingError defaults to False


def test_booking_error_custom():
    """Test BookingError with custom message."""
    error = BookingError("Payment declined")
    assert error.message == "Payment declined"


def test_network_error_default():
    """Test NetworkError with default message."""
    error = NetworkError()
    assert error.message == "Network error occurred"
    assert error.recoverable is True


def test_network_error_custom():
    """Test NetworkError with custom message."""
    error = NetworkError("Connection timeout")
    assert error.message == "Connection timeout"


def test_selector_not_found_error():
    """Test SelectorNotFoundError."""
    error = SelectorNotFoundError("login_button")
    assert error.selector_name == "login_button"
    assert error.tried_selectors == []
    assert "Selector 'login_button' not found" in error.message
    assert error.recoverable is False


def test_selector_not_found_error_with_tried_selectors():
    """Test SelectorNotFoundError with tried selectors."""
    tried = ["#login", ".login-btn", "button[type='submit']"]
    error = SelectorNotFoundError("login_button", tried_selectors=tried)

    assert error.selector_name == "login_button"
    assert error.tried_selectors == tried
    assert "Tried:" in error.message
    assert "#login" in error.message


def test_rate_limit_error_default():
    """Test RateLimitError with default message."""
    error = RateLimitError()
    assert error.message == "Rate limit exceeded"
    assert error.wait_time is None
    assert error.recoverable is True


def test_rate_limit_error_with_wait_time():
    """Test RateLimitError with wait time."""
    error = RateLimitError(wait_time=60)
    assert error.wait_time == 60
    assert "wait 60 seconds" in error.message


def test_configuration_error_default():
    """Test ConfigurationError with default message."""
    error = ConfigurationError()
    assert error.message == "Configuration error"
    assert error.recoverable is False  # ConfigurationError defaults to False


def test_configuration_error_custom():
    """Test ConfigurationError with custom message."""
    error = ConfigurationError("Invalid API key")
    assert error.message == "Invalid API key"


def test_authentication_error_default():
    """Test AuthenticationError with default message."""
    error = AuthenticationError()
    assert error.message == "Authentication failed"
    assert error.recoverable is False  # AuthenticationError defaults to False


def test_authentication_error_custom():
    """Test AuthenticationError with custom message."""
    error = AuthenticationError("Invalid token")
    assert error.message == "Invalid token"


def test_exceptions_are_raisable():
    """Test that exceptions can be raised and caught."""
    with pytest.raises(VFSBotError) as exc_info:
        raise VFSBotError("Test")
    assert exc_info.value.message == "Test"

    with pytest.raises(LoginError):
        raise LoginError()

    with pytest.raises(CaptchaError):
        raise CaptchaError()

    with pytest.raises(SlotCheckError):
        raise SlotCheckError()

    with pytest.raises(BookingError):
        raise BookingError()

    with pytest.raises(NetworkError):
        raise NetworkError()

    with pytest.raises(SelectorNotFoundError):
        raise SelectorNotFoundError("test")

    with pytest.raises(RateLimitError):
        raise RateLimitError()

    with pytest.raises(ConfigurationError):
        raise ConfigurationError()

    with pytest.raises(AuthenticationError):
        raise AuthenticationError()


def test_exceptions_inherit_from_vfsbot_error():
    """Test that all custom exceptions inherit from VFSBotError."""
    assert issubclass(LoginError, VFSBotError)
    assert issubclass(CaptchaError, VFSBotError)
    assert issubclass(SlotCheckError, VFSBotError)
    assert issubclass(BookingError, VFSBotError)
    assert issubclass(NetworkError, VFSBotError)
    assert issubclass(SelectorNotFoundError, VFSBotError)
    assert issubclass(RateLimitError, VFSBotError)
    assert issubclass(ConfigurationError, VFSBotError)
    assert issubclass(AuthenticationError, VFSBotError)
