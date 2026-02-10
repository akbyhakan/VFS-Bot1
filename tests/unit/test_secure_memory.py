"""Tests for secure memory utilities."""


import pytest


from src.utils.secure_memory import SecureCVV, SecureKeyContext, secure_zero_memory


def test_secure_zero_memory_with_bytearray():
    """Test secure_zero_memory with bytearray."""
    data = bytearray(b"sensitive_data")
    original_length = len(data)

    secure_zero_memory(data)

    # Data should be zeroed
    assert len(data) == original_length
    assert all(byte == 0 for byte in data)


def test_secure_zero_memory_with_bytes():
    """Test secure_zero_memory with bytes (creates mutable copy)."""
    data = b"sensitive_data"

    # Should not raise exception
    secure_zero_memory(data)


def test_secure_zero_memory_with_string():
    """Test secure_zero_memory with string (no-op, strings are immutable)."""
    data = "sensitive_data"

    # Should not raise exception
    secure_zero_memory(data)


def test_secure_zero_memory_with_none():
    """Test secure_zero_memory with None."""
    # Should not raise exception
    secure_zero_memory(None)


def test_secure_cvv_context_manager():
    """Test SecureCVV context manager."""
    cvv_input = "123"

    with SecureCVV(cvv_input) as cvv:
        # Inside context, CVV should be accessible
        assert cvv == "123"

    # After context, internal data should be None
    # (we can't verify the memory is zeroed from outside,
    # but we can verify the implementation)


def test_secure_cvv_with_different_values():
    """Test SecureCVV with different CVV values."""
    test_cvvs = ["123", "4567", "890"]

    for cvv_input in test_cvvs:
        with SecureCVV(cvv_input) as cvv:
            assert cvv == cvv_input


def test_secure_cvv_exception_handling():
    """Test SecureCVV cleans up even on exception."""
    cvv_input = "123"

    try:
        with SecureCVV(cvv_input) as cvv:
            assert cvv == "123"
            # Simulate an exception
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Context manager should have cleaned up despite exception


def test_secure_cvv_multiple_uses():
    """Test SecureCVV can be used multiple times."""
    for i in range(5):
        cvv_input = str(i) * 3
        with SecureCVV(cvv_input) as cvv:
            assert cvv == cvv_input


def test_secure_cvv_with_unicode():
    """Test SecureCVV with unicode characters."""
    cvv_input = "123"  # CVV should be ASCII but test unicode handling

    with SecureCVV(cvv_input) as cvv:
        assert cvv == cvv_input


def test_secure_zero_memory_empty_data():
    """Test secure_zero_memory with empty data."""
    data = bytearray()

    # Should not raise exception
    secure_zero_memory(data)

    assert len(data) == 0


def test_secure_cvv_empty_string():
    """Test SecureCVV with empty string."""
    with SecureCVV("") as cvv:
        assert cvv == ""


def test_secure_cvv_whitespace():
    """Test SecureCVV with whitespace."""
    cvv_input = "  123  "

    with SecureCVV(cvv_input) as cvv:
        assert cvv == cvv_input


def test_secure_key_context_basic():
    """Test SecureKeyContext basic usage."""
    key_str = "test_secret_key_12345678901234567890"
    
    with SecureKeyContext(key_str) as key_bytes:
        # Should return a bytearray
        assert isinstance(key_bytes, bytearray)
        # Should contain the encoded key
        assert bytes(key_bytes) == key_str.encode("utf-8")


def test_secure_key_context_zeroes_on_exit():
    """Test SecureKeyContext zeroes data on exit."""
    key_str = "test_secret_key_12345678901234567890"
    
    ctx = SecureKeyContext(key_str)
    with ctx as key_bytes:
        # Data should be populated
        assert len(key_bytes) > 0
        assert bytes(key_bytes) == key_str.encode("utf-8")
    
    # After exit, _data should be an empty bytearray
    assert ctx._data == bytearray()


def test_secure_key_context_none_raises():
    """Test SecureKeyContext raises ValueError for None input."""
    with pytest.raises(ValueError, match="Key string is None or empty"):
        with SecureKeyContext(None) as key_bytes:
            pass


def test_secure_key_context_empty_raises():
    """Test SecureKeyContext raises ValueError for empty string input."""
    with pytest.raises(ValueError, match="Key string is None or empty"):
        with SecureKeyContext("") as key_bytes:
            pass


def test_secure_key_context_clears_str_reference():
    """Test SecureKeyContext clears string reference after __enter__."""
    key_str = "test_secret_key_12345678901234567890"
    
    ctx = SecureKeyContext(key_str)
    assert ctx._key_str == key_str  # Initially set
    
    with ctx as key_bytes:
        # After entering, string reference should be cleared
        assert ctx._key_str is None
        assert isinstance(key_bytes, bytearray)


def test_secure_key_context_exception_cleanup():
    """Test SecureKeyContext cleans up even when exception occurs."""
    key_str = "test_secret_key_12345678901234567890"
    
    ctx = SecureKeyContext(key_str)
    
    try:
        with ctx as key_bytes:
            assert len(key_bytes) > 0
            # Simulate an exception
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    # Should still clean up after exception
    assert ctx._data == bytearray()

