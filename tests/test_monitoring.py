"""Tests for core/monitoring module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.core.monitoring import filter_sensitive_data, init_sentry


class TestInitSentry:
    """Tests for init_sentry function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_init_sentry_no_dsn(self):
        """Test init_sentry when SENTRY_DSN is not set."""
        # Should not raise, just log warning
        init_sentry()

    @patch.dict(os.environ, {"SENTRY_DSN": "https://test@sentry.io/123"})
    def test_init_sentry_with_dsn(self):
        """Test init_sentry with valid SENTRY_DSN."""
        # This will attempt to import sentry_sdk which might not be installed
        # Just verify it doesn't crash
        try:
            init_sentry()
        except ImportError:
            # Expected if sentry-sdk not installed
            pass

    @patch.dict(os.environ, {"SENTRY_DSN": "https://test@sentry.io/123", "ENV": "staging"})
    def test_init_sentry_with_env(self):
        """Test init_sentry with environment variable."""
        # Just verify it doesn't crash
        try:
            init_sentry()
        except ImportError:
            # Expected if sentry-sdk not installed
            pass

    @patch.dict(
        os.environ,
        {"SENTRY_DSN": "https://test@sentry.io/123", "SENTRY_TRACES_SAMPLE_RATE": "0.5"},
    )
    def test_init_sentry_with_sample_rate(self):
        """Test init_sentry with custom sample rate."""
        # Just verify it doesn't crash
        try:
            init_sentry()
        except ImportError:
            # Expected if sentry-sdk not installed
            pass

    @patch.dict(os.environ, {"SENTRY_DSN": "https://test@sentry.io/123"})
    def test_init_sentry_import_error(self):
        """Test init_sentry when sentry_sdk is not installed."""
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            # Should not raise, just log warning
            init_sentry()


class TestFilterSensitiveData:
    """Tests for filter_sensitive_data function."""

    def test_filter_cvv(self):
        """Test filtering CVV from event."""
        event = {"request": {"data": {"cvv": "123"}}}
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["cvv"] == "[FILTERED]"

    def test_filter_password(self):
        """Test filtering password from event."""
        event = {"request": {"data": {"password": "secret"}}}
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["password"] == "[FILTERED]"

    def test_filter_token(self):
        """Test filtering token from event."""
        event = {"request": {"data": {"token": "abc123"}}}
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["token"] == "[FILTERED]"

    def test_filter_api_key(self):
        """Test filtering API key from event."""
        event = {"request": {"data": {"api_key": "key123"}}}
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["api_key"] == "[FILTERED]"

    def test_filter_card_number(self):
        """Test filtering card number from event."""
        event = {"request": {"data": {"card_number": "1234567890123456"}}}
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["card_number"] == "[FILTERED]"

    def test_filter_multiple_fields(self):
        """Test filtering multiple sensitive fields."""
        event = {
            "request": {
                "data": {
                    "cvv": "123",
                    "password": "secret",
                    "token": "abc",
                    "safe_field": "visible",
                }
            }
        }
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["cvv"] == "[FILTERED]"
        assert result["request"]["data"]["password"] == "[FILTERED]"
        assert result["request"]["data"]["token"] == "[FILTERED]"
        assert result["request"]["data"]["safe_field"] == "visible"

    def test_filter_no_request(self):
        """Test filter with event without request."""
        event = {"other": "data"}
        result = filter_sensitive_data(event, {})
        assert result == event

    def test_filter_no_data(self):
        """Test filter with request but no data."""
        event = {"request": {"other": "field"}}
        result = filter_sensitive_data(event, {})
        assert result == event

    def test_filter_no_sensitive_data(self):
        """Test filter with no sensitive fields."""
        event = {"request": {"data": {"safe": "value"}}}
        result = filter_sensitive_data(event, {})
        assert result["request"]["data"]["safe"] == "value"

    def test_filter_returns_event(self):
        """Test that filter returns the event object."""
        event = {"request": {"data": {"password": "test"}}}
        result = filter_sensitive_data(event, {})
        assert result is not None
        assert isinstance(result, dict)
