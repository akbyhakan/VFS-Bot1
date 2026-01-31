"""Tests for utils/request_context module."""

import pytest
import logging
from src.utils.request_context import (
    get_request_id,
    set_request_id,
    clear_request_id,
    _generate_request_id,
    RequestIdFilter,
)


class TestGenerateRequestId:
    """Tests for _generate_request_id function."""

    def test_generate_request_id_format(self):
        """Test that generated request ID has correct format."""
        request_id = _generate_request_id()
        assert isinstance(request_id, str)
        assert len(request_id) == 12

    def test_generate_request_id_unique(self):
        """Test that generated IDs are unique."""
        ids = [_generate_request_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestGetRequestId:
    """Tests for get_request_id function."""

    def setup_method(self):
        """Clear request ID before each test."""
        clear_request_id()

    def test_get_request_id_generates_if_empty(self):
        """Test that get_request_id generates ID if none exists."""
        request_id = get_request_id()
        assert isinstance(request_id, str)
        assert len(request_id) == 12

    def test_get_request_id_returns_same(self):
        """Test that multiple calls return the same ID."""
        id1 = get_request_id()
        id2 = get_request_id()
        assert id1 == id2

    def test_get_request_id_after_set(self):
        """Test getting request ID after setting it."""
        set_request_id("custom-id")
        request_id = get_request_id()
        assert request_id == "custom-id"


class TestSetRequestId:
    """Tests for set_request_id function."""

    def setup_method(self):
        """Clear request ID before each test."""
        clear_request_id()

    def test_set_request_id_custom(self):
        """Test setting a custom request ID."""
        result = set_request_id("my-custom-id")
        assert result == "my-custom-id"
        assert get_request_id() == "my-custom-id"

    def test_set_request_id_none_generates(self):
        """Test that set_request_id with None generates a new ID."""
        result = set_request_id(None)
        assert isinstance(result, str)
        assert len(result) == 12
        assert get_request_id() == result

    def test_set_request_id_overwrites(self):
        """Test that set_request_id overwrites existing ID."""
        set_request_id("first-id")
        set_request_id("second-id")
        assert get_request_id() == "second-id"


class TestClearRequestId:
    """Tests for clear_request_id function."""

    def test_clear_request_id(self):
        """Test clearing request ID."""
        set_request_id("test-id")
        clear_request_id()
        # After clearing, get should generate a new one
        new_id = get_request_id()
        assert new_id != "test-id"

    def test_clear_request_id_when_empty(self):
        """Test clearing when no request ID is set."""
        clear_request_id()
        clear_request_id()  # Should not raise


class TestRequestIdFilter:
    """Tests for RequestIdFilter logging filter."""

    def setup_method(self):
        """Clear request ID before each test."""
        clear_request_id()

    def test_filter_initialization(self):
        """Test RequestIdFilter can be instantiated."""
        filter_obj = RequestIdFilter()
        assert filter_obj is not None

    def test_filter_adds_request_id(self):
        """Test that filter adds request_id to log record."""
        set_request_id("test-123")
        filter_obj = RequestIdFilter()

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Apply filter
        filter_obj.filter(record)

        # Check that request_id was added
        assert hasattr(record, "request_id")
        assert record.request_id == "test-123"

    def test_filter_with_generated_id(self):
        """Test filter with auto-generated request ID."""
        filter_obj = RequestIdFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert hasattr(record, "request_id")
        assert isinstance(record.request_id, str)
        assert len(record.request_id) == 12

    def test_filter_preserves_existing_request_id(self):
        """Test that filter uses the same request ID for multiple records."""
        set_request_id("consistent-id")
        filter_obj = RequestIdFilter()

        record1 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Msg1", args=(), exc_info=None
        )
        record2 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=2, msg="Msg2", args=(), exc_info=None
        )

        filter_obj.filter(record1)
        filter_obj.filter(record2)

        assert record1.request_id == record2.request_id == "consistent-id"
