"""Tests for logging_config module."""

import logging
import pytest
import json
from io import StringIO
from unittest.mock import patch
from src.core.logging_config import JSONFormatter, setup_logging


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
        """Test formatting with request_id attribute."""
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
        record.request_id = "req-123"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["request_id"] == "req-123"

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


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self):
        """Test setup_logging with default parameters."""
        with patch.dict("os.environ", {}, clear=True):
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO
            assert len(root_logger.handlers) > 0

    def test_setup_logging_with_level(self):
        """Test setup_logging with custom level."""
        setup_logging(level="DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_with_json_format(self):
        """Test setup_logging with JSON format."""
        setup_logging(level="INFO", json_format=True)
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logging_with_text_format(self):
        """Test setup_logging with text format."""
        setup_logging(level="INFO", json_format=False)
        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)

    def test_setup_logging_removes_existing_handlers(self):
        """Test that setup_logging removes existing handlers."""
        root_logger = logging.getLogger()
        initial_handler_count = len(root_logger.handlers)

        setup_logging(level="INFO")
        # Should have exactly one handler after setup
        assert len(root_logger.handlers) == 1

    def test_setup_logging_from_env_level(self):
        """Test setup_logging reads level from environment."""
        with patch.dict("os.environ", {"LOG_LEVEL": "WARNING"}):
            setup_logging()
            root_logger = logging.getLogger()
            assert root_logger.level == logging.WARNING

    def test_setup_logging_from_env_json_format(self):
        """Test setup_logging reads format from environment."""
        with patch.dict("os.environ", {"LOG_FORMAT": "json"}):
            setup_logging()
            root_logger = logging.getLogger()
            handler = root_logger.handlers[0]
            assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logging_third_party_loggers(self):
        """Test that third-party loggers are set to WARNING level."""
        setup_logging(level="DEBUG")

        urllib3_logger = logging.getLogger("urllib3")
        aiohttp_logger = logging.getLogger("aiohttp")
        playwright_logger = logging.getLogger("playwright")

        assert urllib3_logger.level == logging.WARNING
        assert aiohttp_logger.level == logging.WARNING
        assert playwright_logger.level == logging.WARNING

    def test_setup_logging_error_level(self):
        """Test setup_logging with ERROR level."""
        setup_logging(level="ERROR")
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

        # Check timestamp ends with Z (UTC indicator)
        assert data["timestamp"].endswith("Z")
        # Check it contains ISO format separators
        assert "T" in data["timestamp"]
