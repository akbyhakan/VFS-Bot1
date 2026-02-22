"""Additional coverage tests for utils/safe_logging module."""

import logging

import pytest

from src.utils.safe_logging import (
    SafeException,
    mask_credit_card,
    mask_email,
    mask_phone,
    mask_sensitive_url,
)


class TestSafeExceptionSafeDict:
    """Tests for SafeException.safe_dict covering missing paths."""

    def test_safe_dict_non_dict_string_returned_as_is(self):
        """Non-dict input is returned unchanged."""
        result = SafeException.safe_dict("plain string")
        assert result == "plain string"

    def test_safe_dict_non_dict_int_returned_as_is(self):
        """Integer input is returned unchanged."""
        result = SafeException.safe_dict(42)
        assert result == 42

    def test_safe_dict_non_dict_none_returned_as_is(self):
        """None input is returned unchanged."""
        result = SafeException.safe_dict(None)
        assert result is None

    def test_safe_dict_nested_dict_sanitized_recursively(self):
        """Nested dict values are sanitized recursively."""
        data = {"outer": {"inner": {"password": "secret", "name": "user"}}}
        result = SafeException.safe_dict(data)
        assert result["outer"]["inner"]["password"] == "[REDACTED]"
        assert result["outer"]["inner"]["name"] == "user"

    def test_safe_dict_list_of_dicts_sanitized(self):
        """List items that are dicts are sanitized."""
        data = {"users": [{"name": "alice", "token": "tok1"}, {"name": "bob", "token": "tok2"}]}
        result = SafeException.safe_dict(data)
        assert result["users"][0]["token"] == "[REDACTED]"
        assert result["users"][1]["token"] == "[REDACTED]"
        assert result["users"][0]["name"] == "alice"

    def test_safe_dict_list_of_scalars_preserved(self):
        """Lists of non-dict items are preserved as-is."""
        data = {"tags": ["a", "b", "c"]}
        result = SafeException.safe_dict(data)
        assert result["tags"] == ["a", "b", "c"]

    def test_safe_dict_does_not_mutate_original(self):
        """Original dict is not mutated."""
        data = {"password": "secret"}
        original_value = data["password"]
        SafeException.safe_dict(data)
        assert data["password"] == original_value

    def test_safe_dict_empty_dict(self):
        """Empty dict returns empty dict."""
        result = SafeException.safe_dict({})
        assert result == {}


class TestSafeExceptionSafeLog:
    """Tests for SafeException.safe_log method."""

    def test_safe_log_redacts_sensitive_message(self):
        """safe_log should redact sensitive data in message."""
        logger = logging.getLogger("test_safe_log")

        records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = CapturingHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            SafeException.safe_log(logger, logging.INFO, "token=my_secret_value")
            assert len(records) == 1
            assert "my_secret_value" not in records[0].getMessage()
            assert "[REDACTED]" in records[0].getMessage()
        finally:
            logger.removeHandler(handler)

    def test_safe_log_with_exc_info_exception_sanitized(self):
        """safe_log sanitizes Exception passed as exc_info."""
        logger = logging.getLogger("test_safe_log_exc")

        records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = CapturingHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            exc = Exception("password=supersecret")
            SafeException.safe_log(logger, logging.ERROR, "Something failed", exc_info=exc)
            assert len(records) == 1
        finally:
            logger.removeHandler(handler)

    def test_safe_log_with_none_exc_info(self):
        """safe_log with None exc_info works without error."""
        logger = logging.getLogger("test_safe_log_none")

        records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = CapturingHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            SafeException.safe_log(logger, logging.WARNING, "plain message", exc_info=None)
            assert len(records) == 1
            assert "plain message" in records[0].getMessage()
        finally:
            logger.removeHandler(handler)


class TestMaskSensitiveUrl:
    """Tests for mask_sensitive_url function."""

    def test_mask_token_query_param(self):
        """Token in query string is masked."""
        url = "https://example.com/api?token=abc123secret"
        result = mask_sensitive_url(url)
        assert "abc123secret" not in result
        assert "[REDACTED]" in result

    def test_mask_key_query_param(self):
        """API key in query string is masked."""
        url = "https://example.com/api?key=myapikey123"
        result = mask_sensitive_url(url)
        assert "myapikey123" not in result
        assert "[REDACTED]" in result

    def test_mask_password_query_param(self):
        """Password in query string is masked."""
        url = "https://example.com/login?password=secret"
        result = mask_sensitive_url(url)
        assert "secret" not in result
        assert "[REDACTED]" in result

    def test_mask_bearer_in_path(self):
        """Bearer token in path is masked."""
        url = "https://example.com/bearer/eyJtoken123"
        result = mask_sensitive_url(url)
        assert "eyJtoken123" not in result
        assert "[REDACTED]" in result

    def test_non_sensitive_url_unchanged(self):
        """URL without sensitive params is returned unchanged."""
        url = "https://example.com/api/users?page=1&limit=10"
        result = mask_sensitive_url(url)
        assert result == url

    def test_multiple_sensitive_params(self):
        """Multiple sensitive params are all masked."""
        url = "https://example.com/api?token=tok1&key=key1"
        result = mask_sensitive_url(url)
        assert "tok1" not in result
        assert "key1" not in result

    def test_empty_url_returned_as_is(self):
        """Empty URL is returned as-is."""
        result = mask_sensitive_url("")
        assert result == ""


class TestMaskEmail:
    """Tests for mask_email function."""

    def test_long_local_part_masked(self):
        """Long local part is masked after first 2 chars."""
        result = mask_email("username@example.com")
        assert result.startswith("us***@")
        assert "username" not in result

    def test_short_local_part_masked(self):
        """Short local part (<=2 chars) uses single asterisk."""
        result = mask_email("ab@example.com")
        assert result.startswith("a*@")

    def test_single_char_local_part(self):
        """Single char local part is handled."""
        result = mask_email("a@example.com")
        assert "@" in result
        assert result.startswith("a*@")

    def test_domain_masked(self):
        """Domain parts are partially masked (original domain name is not visible)."""
        result = mask_email("user@example.com")
        assert "example" not in result
        assert "ex***" in result

    def test_no_at_sign_returned_as_is(self):
        """Input without @ is returned unchanged."""
        result = mask_email("notanemail")
        assert result == "notanemail"

    def test_preserves_at_symbol(self):
        """Result always contains @."""
        result = mask_email("test@domain.org")
        assert "@" in result


class TestMaskPhone:
    """Tests for mask_phone function."""

    def test_standard_phone_shows_last_four(self):
        """Standard phone number shows only last 4 digits."""
        result = mask_phone("+1 (555) 123-4567")
        assert result.endswith("4567")
        assert "555" not in result

    def test_short_phone_number(self):
        """Short phone (<=4 digits) still masked."""
        result = mask_phone("1234")
        assert "***" in result
        assert result.endswith("1234")

    def test_phone_with_spaces_and_dashes(self):
        """Non-digit chars are stripped before masking."""
        result = mask_phone("123-456-7890")
        assert result.endswith("7890")
        assert "123" not in result

    def test_phone_returns_string(self):
        """Return value is always a string."""
        result = mask_phone("5551234")
        assert isinstance(result, str)


class TestMaskCreditCard:
    """Tests for mask_credit_card function."""

    def test_standard_card_shows_last_four(self):
        """Standard 16-digit card shows only last 4 digits."""
        result = mask_credit_card("4111 1111 1111 1234")
        assert result.endswith("1234")
        assert "4111" not in result

    def test_card_with_dashes(self):
        """Dashes are stripped before masking."""
        result = mask_credit_card("4111-1111-1111-5678")
        assert result.endswith("5678")

    def test_short_card_number(self):
        """Card number <=4 digits is handled."""
        result = mask_credit_card("1234")
        assert "****" in result
        assert result.endswith("1234")

    def test_result_starts_with_asterisks(self):
        """Result always starts with ****."""
        result = mask_credit_card("4111111111111111")
        assert result.startswith("****")

    def test_returns_string(self):
        """Return value is always a string."""
        result = mask_credit_card("1234567890123456")
        assert isinstance(result, str)
