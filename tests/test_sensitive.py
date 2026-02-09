"""Tests for SensitiveDict class."""

import pytest

from src.core.sensitive import SensitiveDict


class TestSensitiveDict:
    """Tests for sensitive data wrapper."""

    def test_sensitive_dict_repr_masks_values(self):
        """Test that repr does not contain actual values."""
        data = {
            "number": "1234567812345678",
            "cvv": "123",
            "expiry": "12/25"
        }
        sensitive = SensitiveDict(data)
        
        repr_str = repr(sensitive)
        
        # Should contain keys but not values
        assert "keys=" in repr_str
        assert "MASKED" in repr_str
        assert "1234567812345678" not in repr_str
        assert "123" not in repr_str
        assert "12/25" not in repr_str

    def test_sensitive_dict_str_masks_values(self):
        """Test that str does not contain actual values."""
        data = {
            "number": "1234567812345678",
            "cvv": "123",
            "expiry": "12/25"
        }
        sensitive = SensitiveDict(data)
        
        str_repr = str(sensitive)
        
        # Should contain keys but not values
        assert "keys=" in str_repr
        assert "MASKED" in str_repr
        assert "1234567812345678" not in str_repr
        assert "123" not in str_repr
        assert "12/25" not in str_repr

    def test_sensitive_dict_getitem(self):
        """Test that direct item access works normally."""
        data = {"number": "1234567812345678", "cvv": "123"}
        sensitive = SensitiveDict(data)
        
        assert sensitive["number"] == "1234567812345678"
        assert sensitive["cvv"] == "123"

    def test_sensitive_dict_get(self):
        """Test that .get() method works normally."""
        data = {"number": "1234567812345678"}
        sensitive = SensitiveDict(data)
        
        assert sensitive.get("number") == "1234567812345678"
        assert sensitive.get("cvv", "default") == "default"

    def test_sensitive_dict_contains(self):
        """Test that 'in' operator works."""
        data = {"number": "1234567812345678"}
        sensitive = SensitiveDict(data)
        
        assert "number" in sensitive
        assert "cvv" not in sensitive

    def test_sensitive_dict_wipe(self):
        """Test that wipe() clears internal data."""
        data = {"number": "1234567812345678", "cvv": "123"}
        sensitive = SensitiveDict(data)
        
        # Before wipe
        assert sensitive["number"] == "1234567812345678"
        
        # After wipe
        sensitive.wipe()
        
        with pytest.raises(KeyError):
            _ = sensitive["number"]

    def test_sensitive_dict_to_dict(self):
        """Test that to_dict() returns a regular dict."""
        data = {"number": "1234567812345678", "cvv": "123"}
        sensitive = SensitiveDict(data)
        
        unwrapped = sensitive.to_dict()
        
        assert isinstance(unwrapped, dict)
        assert unwrapped["number"] == "1234567812345678"
        assert unwrapped["cvv"] == "123"
        
        # Should be a copy, not a reference
        unwrapped["new_key"] = "value"
        assert "new_key" not in sensitive

    def test_sensitive_dict_bool(self):
        """Test that bool conversion works correctly."""
        # Non-empty should be truthy
        sensitive = SensitiveDict({"key": "value"})
        assert bool(sensitive) is True
        
        # Empty should be falsy
        empty = SensitiveDict()
        assert bool(empty) is False
        
        # After wipe should be falsy
        sensitive.wipe()
        assert bool(sensitive) is False

    def test_sensitive_dict_keys(self):
        """Test that keys() returns an iterator."""
        data = {"number": "1234567812345678", "cvv": "123", "expiry": "12/25"}
        sensitive = SensitiveDict(data)
        
        keys = list(sensitive.keys())
        
        assert set(keys) == {"number", "cvv", "expiry"}

    def test_sensitive_dict_empty_initialization(self):
        """Test creating SensitiveDict with no data."""
        sensitive = SensitiveDict()
        
        assert bool(sensitive) is False
        assert sensitive.to_dict() == {}

    def test_sensitive_dict_none_initialization(self):
        """Test creating SensitiveDict with None."""
        sensitive = SensitiveDict(None)
        
        assert bool(sensitive) is False
        assert sensitive.to_dict() == {}
