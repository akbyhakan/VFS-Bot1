"""Additional coverage tests for utils/secure_memory module."""

import ctypes
from unittest.mock import patch

import pytest

from src.utils.secure_memory import SecureCVV, SecureKeyContext, secure_zero_memory


# ---------------------------------------------------------------------------
# secure_zero_memory edge cases
# ---------------------------------------------------------------------------


class TestSecureZeroMemoryEdgeCases:
    """Tests for secure_zero_memory covering missing paths."""

    def test_empty_bytearray_does_not_raise(self):
        """secure_zero_memory with empty bytearray is a no-op and does not raise."""
        data = bytearray()
        secure_zero_memory(data)  # should not raise
        assert len(data) == 0

    def test_ctypes_failure_falls_back_to_manual_zeroing(self):
        """If ctypes.memset raises, manual zeroing fallback is used."""
        data = bytearray(b"sensitive")

        with patch("ctypes.memset", side_effect=Exception("ctypes failed")):
            secure_zero_memory(data)

        assert all(b == 0 for b in data)

    def test_large_bytearray_zeroed(self):
        """Large bytearray is fully zeroed."""
        data = bytearray(b"x" * 1024)
        secure_zero_memory(data)
        assert all(b == 0 for b in data)


# ---------------------------------------------------------------------------
# SecureCVV internal state after exit
# ---------------------------------------------------------------------------


class TestSecureCVVInternalState:
    """Tests verifying SecureCVV internal memory is zeroed after context exit."""

    def test_internal_data_zeroed_after_exit(self):
        """All bytes in _data bytearray are 0 after exiting context."""
        cvv = SecureCVV("456")
        with cvv:
            pass  # just enter and exit

        assert all(b == 0 for b in cvv._data)

    def test_internal_data_zeroed_even_on_exception(self):
        """_data is zeroed even when exception occurs inside context."""
        cvv = SecureCVV("789")

        try:
            with cvv:
                raise RuntimeError("forced error")
        except RuntimeError:
            pass

        assert all(b == 0 for b in cvv._data)

    def test_data_is_bytearray_after_exit(self):
        """_data remains a bytearray (empty) after exiting context."""
        cvv = SecureCVV("123")
        with cvv:
            pass

        assert isinstance(cvv._data, bytearray)

    def test_cvv_value_accessible_inside_context(self):
        """CVV string is available inside the with block."""
        with SecureCVV("999") as val:
            assert val == "999"


# ---------------------------------------------------------------------------
# SecureKeyContext.__enter__ – None / empty string
# ---------------------------------------------------------------------------


class TestSecureKeyContextEnter:
    """Tests for SecureKeyContext.__enter__ validation."""

    def test_none_key_raises_value_error(self):
        """None key raises ValueError on enter."""
        with pytest.raises(ValueError, match="None or empty"):
            with SecureKeyContext(None):
                pass

    def test_empty_string_raises_value_error(self):
        """Empty string raises ValueError on enter."""
        with pytest.raises(ValueError, match="None or empty"):
            with SecureKeyContext(""):
                pass

    def test_valid_key_returns_bytearray(self):
        """Valid key returns a bytearray in the context."""
        with SecureKeyContext("secret_key_value") as key_bytes:
            assert isinstance(key_bytes, bytearray)
            assert len(key_bytes) > 0

    def test_key_str_reference_cleared_after_enter(self):
        """_key_str is set to None after entering context."""
        ctx = SecureKeyContext("some_key_12345678")
        with ctx:
            assert ctx._key_str is None


# ---------------------------------------------------------------------------
# SecureKeyContext.__exit__ – zeroing and None data
# ---------------------------------------------------------------------------


class TestSecureKeyContextExit:
    """Tests for SecureKeyContext.__exit__ behaviour."""

    def test_data_zeroed_after_exit(self):
        """_data bytearray is empty (zeroed) after exiting context."""
        ctx = SecureKeyContext("key_to_be_zeroed_123")
        with ctx:
            pass

        assert ctx._data == bytearray()

    def test_exit_with_none_data_does_not_raise(self):
        """__exit__ handles _data=None gracefully."""
        ctx = SecureKeyContext.__new__(SecureKeyContext)
        ctx._key_str = None
        ctx._data = None

        # Directly call __exit__ – should not raise
        ctx.__exit__(None, None, None)

    def test_data_zeroed_on_exception(self):
        """_data is zeroed even when exception propagates out of context."""
        ctx = SecureKeyContext("key_exception_test_123")

        try:
            with ctx:
                raise ValueError("test exception")
        except ValueError:
            pass

        assert ctx._data == bytearray()

    def test_returns_false_to_propagate_exception(self):
        """__exit__ returns False so exceptions are not suppressed."""
        ctx = SecureKeyContext.__new__(SecureKeyContext)
        ctx._key_str = None
        ctx._data = bytearray(b"data")

        result = ctx.__exit__(Exception, Exception("err"), None)
        assert result is False


# ---------------------------------------------------------------------------
# SecureKeyContext as full context manager with valid key
# ---------------------------------------------------------------------------


class TestSecureKeyContextFull:
    """Integration-style tests for SecureKeyContext."""

    def test_key_bytes_match_encoded_key(self):
        """Content of bytearray matches UTF-8 encoding of the key."""
        key = "my_super_secret_key_1234"
        with SecureKeyContext(key) as key_bytes:
            assert bytes(key_bytes) == key.encode("utf-8")

    def test_multiple_uses_of_different_keys(self):
        """Independent contexts do not interfere."""
        keys = ["key_alpha_000", "key_beta_111", "key_gamma_222"]
        for key in keys:
            with SecureKeyContext(key) as kb:
                assert bytes(kb) == key.encode("utf-8")

    def test_context_manager_can_be_reused_after_manual_reset(self):
        """A new SecureKeyContext instance works after previous one is exited."""
        ctx1 = SecureKeyContext("first_key_abcdef")
        with ctx1 as kb1:
            data1 = bytes(kb1)

        ctx2 = SecureKeyContext("second_key_xyz123")
        with ctx2 as kb2:
            data2 = bytes(kb2)

        assert data1 != data2
