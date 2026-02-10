"""Tests for core/result module."""

import pytest

from src.core.result import Failure, Result, Success


class TestSuccess:
    """Tests for Success result type."""

    def test_success_creation(self):
        """Test creating a Success result."""
        result = Success(42)
        assert result.value == 42
        assert result.is_success()
        assert not result.is_failure()

    def test_success_unwrap(self):
        """Test unwrapping a Success result."""
        result = Success("test")
        assert result.unwrap() == "test"

    def test_success_unwrap_or(self):
        """Test unwrap_or returns the value."""
        result = Success(100)
        assert result.unwrap_or(0) == 100

    def test_success_map(self):
        """Test mapping a function over Success."""
        result = Success(5)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_success()
        assert mapped.unwrap() == 10

    def test_success_map_with_exception(self):
        """Test map with function that raises exception."""
        result = Success(5)
        mapped = result.map(lambda x: 1 / 0)
        assert mapped.is_failure()

    def test_success_repr(self):
        """Test Success string representation."""
        result = Success("value")
        assert repr(result) == "Success('value')"


class TestFailure:
    """Tests for Failure result type."""

    def test_failure_creation(self):
        """Test creating a Failure result."""
        result = Failure("error message")
        assert result.error == "error message"
        assert not result.is_success()
        assert result.is_failure()

    def test_failure_with_exception(self):
        """Test Failure with exception object."""
        exc = ValueError("test error")
        result = Failure("error", exc)
        assert result.error == "error"
        assert result.exception == exc

    def test_failure_unwrap_raises(self):
        """Test unwrap raises on Failure."""
        result = Failure("error")
        with pytest.raises(RuntimeError):
            result.unwrap()

    def test_failure_unwrap_or_returns_default(self):
        """Test unwrap_or returns default on Failure."""
        result = Failure("error")
        assert result.unwrap_or(100) == 100

    def test_failure_map_does_nothing(self):
        """Test map on Failure returns Failure."""
        result = Failure("error")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_failure()
        assert mapped.error == "error"

    def test_failure_repr(self):
        """Test Failure string representation."""
        result = Failure("test error")
        assert repr(result) == "Failure(error='test error')"

    def test_failure_repr_with_exception(self):
        """Test Failure repr with exception."""
        exc = ValueError("test")
        result = Failure("error", exc)
        assert "Failure(error='error'" in repr(result)
        assert "ValueError" in repr(result)


class TestResultPatterns:
    """Tests for Result pattern usage."""

    def test_result_type_alias(self):
        """Test Result type alias works."""
        success: Result[int, str] = Success(42)
        failure: Result[int, str] = Failure("error")
        assert success.is_success()
        assert failure.is_failure()

    def test_chaining_map_success(self):
        """Test chaining map operations on Success."""
        result = Success(10).map(lambda x: x + 5).map(lambda x: x * 2)
        assert result.is_success()
        assert result.unwrap() == 30

    def test_chaining_map_failure(self):
        """Test chaining map operations on Failure."""
        result = Failure("error").map(lambda x: x + 5).map(lambda x: x * 2)
        assert result.is_failure()
        assert result.error == "error"

    def test_success_with_none(self):
        """Test Success can hold None value."""
        result = Success(None)
        assert result.is_success()
        assert result.unwrap() is None

    def test_success_with_dict(self):
        """Test Success with dictionary value."""
        data = {"key": "value"}
        result = Success(data)
        assert result.is_success()
        assert result.unwrap() == data

    def test_success_with_list(self):
        """Test Success with list value."""
        data = [1, 2, 3]
        result = Success(data)
        assert result.is_success()
        assert result.unwrap() == data

    def test_failure_error_message_only(self):
        """Test Failure with only error message."""
        result = Failure("simple error")
        assert result.error == "simple error"
        assert result.exception is None
