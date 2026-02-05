"""Tests for utils/safe_logging module."""

import pytest

from src.utils.safe_logging import SafeException


class TestSafeException:
    """Tests for SafeException utility."""

    def test_safe_str_redacts_token(self):
        """Test that tokens are redacted."""
        exc = Exception("Error: token=abc123xyz")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg
        assert "abc123xyz" not in safe_msg

    def test_safe_str_redacts_password(self):
        """Test that passwords are redacted."""
        exc = Exception("Login failed: password='secret123'")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg
        assert "secret123" not in safe_msg

    def test_safe_str_redacts_api_key(self):
        """Test that API keys are redacted."""
        exc = Exception("API error: api_key: test_key_123")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg
        assert "test_key_123" not in safe_msg

    def test_safe_str_redacts_bearer_token(self):
        """Test that bearer tokens are redacted."""
        exc = Exception("Auth failed: bearer=eyJ0eXAi...")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg
        assert "eyJ0eXAi" not in safe_msg

    def test_safe_str_multiple_sensitive_fields(self):
        """Test redaction of multiple sensitive fields."""
        exc = Exception("Error: token=abc123 password=secret apikey=key123")
        safe_msg = SafeException.safe_str(exc)
        assert safe_msg.count("[REDACTED]") >= 2
        assert "abc123" not in safe_msg
        assert "secret" not in safe_msg

    def test_safe_str_case_insensitive(self):
        """Test that pattern matching is case-insensitive."""
        exc = Exception("TOKEN=abc PASSWORD=xyz")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg
        assert "abc" not in safe_msg

    def test_safe_str_preserves_safe_content(self):
        """Test that non-sensitive content is preserved."""
        exc = Exception("Database connection error on port 5432")
        safe_msg = SafeException.safe_str(exc)
        assert "Database connection error" in safe_msg
        assert "5432" in safe_msg

    def test_safe_str_redacts_cvv(self):
        """Test that CVV is redacted."""
        exc = Exception("Payment error: cvv=123")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg
        assert "123" not in safe_msg

    def test_safe_str_with_quoted_values(self):
        """Test redaction with quoted values."""
        exc = Exception('Error: secret: "my_secret_value"')
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg

    def test_safe_dict_redacts_password(self):
        """Test that safe_dict redacts password."""
        data = {"username": "john", "password": "secret123"}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["username"] == "john"
        assert safe_data["password"] == "[REDACTED]"

    def test_safe_dict_redacts_token(self):
        """Test that safe_dict redacts token."""
        data = {"id": 1, "auth_token": "abc123"}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["id"] == 1
        assert safe_data["auth_token"] == "[REDACTED]"

    def test_safe_dict_redacts_api_key(self):
        """Test that safe_dict redacts API key."""
        data = {"name": "test", "api_key": "key123"}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["name"] == "test"
        assert safe_data["api_key"] == "[REDACTED]"

    def test_safe_dict_multiple_sensitive_fields(self):
        """Test safe_dict with multiple sensitive fields."""
        data = {"password": "pass", "token": "tok", "username": "user"}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["password"] == "[REDACTED]"
        assert safe_data["token"] == "[REDACTED]"
        assert safe_data["username"] == "user"

    def test_safe_dict_nested_dict(self):
        """Test safe_dict with nested dictionaries."""
        data = {"user": {"name": "john", "password": "secret"}}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["user"]["name"] == "john"
        assert safe_data["user"]["password"] == "[REDACTED]"

    def test_safe_dict_with_list_values(self):
        """Test safe_dict with list values."""
        data = {"items": ["a", "b"], "key": "value"}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["items"] == ["a", "b"]
        assert safe_data["key"] == "value"

    def test_safe_dict_non_dict_input(self):
        """Test safe_dict with non-dict input."""
        result = SafeException.safe_dict("not a dict")
        assert result == "not a dict"

    def test_get_patterns_caching(self):
        """Test that patterns are cached."""
        patterns1 = SafeException._get_patterns()
        patterns2 = SafeException._get_patterns()
        assert patterns1 is patterns2

    def test_sensitive_patterns_defined(self):
        """Test that SENSITIVE_PATTERNS is defined."""
        assert hasattr(SafeException, "SENSITIVE_PATTERNS")
        assert isinstance(SafeException.SENSITIVE_PATTERNS, list)
        assert len(SafeException.SENSITIVE_PATTERNS) > 0

    def test_safe_str_with_colon_separator(self):
        """Test redaction with colon separator."""
        exc = Exception("secret: value123")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg

    def test_safe_str_with_equals_separator(self):
        """Test redaction with equals separator."""
        exc = Exception("token=xyz789")
        safe_msg = SafeException.safe_str(exc)
        assert "[REDACTED]" in safe_msg

    def test_safe_dict_case_insensitive_keys(self):
        """Test that safe_dict is case-insensitive for keys."""
        data = {"PASSWORD": "secret", "Token": "tok"}
        safe_data = SafeException.safe_dict(data)
        assert safe_data["PASSWORD"] == "[REDACTED]"
        assert safe_data["Token"] == "[REDACTED]"
