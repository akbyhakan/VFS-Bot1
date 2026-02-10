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

    def test_sensitive_dict_iter(self):
        """Test that iteration works over keys."""
        data = {"a": 1, "b": 2}
        sensitive = SensitiveDict(data)
        assert set(sensitive) == {"a", "b"}

    def test_sensitive_dict_len(self):
        """Test that len() returns correct count."""
        data = {"a": 1, "b": 2, "c": 3}
        sensitive = SensitiveDict(data)
        assert len(sensitive) == 3

    def test_sensitive_dict_items(self):
        """Test that items() returns key-value pairs."""
        data = {"number": "1234", "cvv": "123"}
        sensitive = SensitiveDict(data)
        items = dict(sensitive.items())
        assert items == data

    def test_sensitive_dict_values(self):
        """Test that values() returns all values."""
        data = {"a": 1, "b": 2}
        sensitive = SensitiveDict(data)
        assert set(sensitive.values()) == {1, 2}

    def test_sensitive_dict_setitem(self):
        """Test that __setitem__ works correctly."""
        sensitive = SensitiveDict({"a": 1})
        sensitive["b"] = 2
        assert sensitive["b"] == 2

    def test_sensitive_dict_delitem(self):
        """Test that __delitem__ works correctly."""
        sensitive = SensitiveDict({"a": 1, "b": 2})
        del sensitive["a"]
        assert "a" not in sensitive

    def test_sensitive_dict_update(self):
        """Test that update() works correctly."""
        sensitive = SensitiveDict({"a": 1})
        sensitive.update({"b": 2, "c": 3})
        assert sensitive["b"] == 2
        assert sensitive["c"] == 3

    def test_sensitive_dict_update_kwargs(self):
        """Test that update() works with kwargs."""
        sensitive = SensitiveDict({"a": 1})
        sensitive.update(b=2, c=3)
        assert sensitive["b"] == 2
        assert sensitive["c"] == 3

    def test_sensitive_dict_pop(self):
        """Test that pop() removes and returns value."""
        sensitive = SensitiveDict({"a": 1, "b": 2})
        val = sensitive.pop("a")
        assert val == 1
        assert "a" not in sensitive

    def test_sensitive_dict_pop_default(self):
        """Test that pop() returns default for missing key."""
        sensitive = SensitiveDict({"a": 1})
        val = sensitive.pop("missing", "default")
        assert val == "default"

    def test_sensitive_dict_eq(self):
        """Test that equality comparison works."""
        s1 = SensitiveDict({"a": 1})
        s2 = SensitiveDict({"a": 1})
        assert s1 == s2
        assert s1 == {"a": 1}

    def test_sensitive_dict_not_eq(self):
        """Test that inequality comparison works."""
        s1 = SensitiveDict({"a": 1})
        s2 = SensitiveDict({"a": 2})
        assert s1 != s2
        assert s1 != {"a": 2}

    def test_sensitive_dict_copy(self):
        """Test that copy() creates independent copy."""
        original = SensitiveDict({"a": 1, "b": 2})
        copied = original.copy()
        assert copied == original
        copied["c"] = 3
        assert "c" not in original
