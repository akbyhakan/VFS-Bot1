"""Tests for logging_config module."""

import json
import logging
from io import StringIO
from unittest.mock import patch

import pytest

from src.core.logger import JSONFormatter, setup_structured_logging


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_basic_message(self):
        """Test formatting a basic log message."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_func"
        record.module = "test_module"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["module"] == "test_module"
        assert data["function"] == "test_func"
        assert data["line"] == 10
        assert "timestamp" in data

    def test_format_with_request_id(self):
        """Test formatting with correlation_id attribute."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Message",
            args=(),
            exc_info=None,
        )
        record.funcName = "func"
        record.module = "mod"
        record.correlation_id = "req-123"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["correlation_id"] == "req-123"

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.funcName = "func"
        record.module = "mod"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "ERROR"
        assert data["message"] == "Error occurred"
        assert "exception" in data
        assert "ValueError: Test error" in data["exception"]


class TestSetupStructuredLogging:
    """Tests for setup_structured_logging function."""

    def test_setup_structured_logging_default(self, monkeypatch):
        """Test setup_structured_logging with default parameters."""
        monkeypatch.setenv("ENV", "testing")
        setup_structured_logging()
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_setup_structured_logging_with_level(self, monkeypatch):
        """Test setup_structured_logging with custom level."""
        monkeypatch.setenv("ENV", "testing")
        setup_structured_logging(level="DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_structured_logging_with_json_format(self, monkeypatch):
        """Test setup_structured_logging with JSON format."""
        monkeypatch.setenv("ENV", "testing")
        # Verify it doesn't crash and sets up logging
        setup_structured_logging(level="INFO", json_format=True)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_structured_logging_with_text_format(self, monkeypatch):
        """Test setup_structured_logging with text format."""
        monkeypatch.setenv("ENV", "testing")
        setup_structured_logging(level="INFO", json_format=False)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_structured_logging_removes_existing_handlers(self, monkeypatch):
        """Test that setup_structured_logging removes existing handlers."""
        monkeypatch.setenv("ENV", "testing")
        root_logger = logging.getLogger()
        _ = len(root_logger.handlers)

        setup_structured_logging(level="INFO")
        # Should have exactly one handler after setup
        assert len(root_logger.handlers) == 1

    def test_setup_structured_logging_error_level(self, monkeypatch):
        """Test setup_structured_logging with ERROR level."""
        monkeypatch.setenv("ENV", "testing")
        setup_structured_logging(level="ERROR")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

    def test_json_formatter_timestamp_format(self):
        """Test that JSONFormatter produces ISO format timestamps."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.funcName = "func"
        record.module = "mod"

        result = formatter.format(record)
        data = json.loads(result)

        # Check timestamp is in ISO format (can end with +00:00 or Z for UTC)
        assert "+00:00" in data["timestamp"] or data["timestamp"].endswith("Z")
        # Check it contains ISO format separators
        assert "T" in data["timestamp"]
