"""Tests for structured logging module."""

import json
import logging

from src.core.logger import JSONFormatter, setup_structured_logging


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_basic_log(self):
        """Test formatting a basic log record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
            func="test_func",
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        assert data["function"] == "test_func"
        assert data["line"] == 10
        assert "timestamp" in data

    def test_format_with_custom_fields(self):
        """Test formatting log record with custom fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
            func="test_func",
        )
        record.user_id = "user123"
        record.centre = "Istanbul"
        record.action = "check_slot"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["user_id"] == "user123"
        assert data["centre"] == "Istanbul"
        assert data["action"] == "check_slot"

    def test_format_with_exception(self):
        """Test formatting log record with exception info."""
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
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
                func="test_func",
            )

            result = formatter.format(record)
            data = json.loads(result)

            assert "exception" in data
            assert "ValueError" in data["exception"]
            assert "Test error" in data["exception"]


class TestSetupStructuredLogging:
    """Tests for setup_structured_logging function."""

    def test_setup_creates_logs_directory(self, tmp_path, monkeypatch):
        """Test that setup creates logs directory."""
        monkeypatch.chdir(tmp_path)

        setup_structured_logging(level="INFO", json_format=True)

        logs_dir = tmp_path / "logs"
        assert logs_dir.exists()
        assert logs_dir.is_dir()

    def test_setup_creates_log_file(self, tmp_path, monkeypatch):
        """Test that setup creates log file."""
        monkeypatch.chdir(tmp_path)

        setup_structured_logging(level="INFO", json_format=True)

        log_file = tmp_path / "logs" / "vfs_bot.jsonl"
        assert log_file.exists()

    def test_setup_with_json_format(self, tmp_path, monkeypatch):
        """Test setup with JSON format enabled."""
        monkeypatch.chdir(tmp_path)

        # Clear handlers from previous tests
        logging.root.handlers = []

        setup_structured_logging(level="INFO", json_format=True)
        logger = logging.getLogger("test")
        logger.info("Test message")

        # Force flush
        for handler in logging.root.handlers:
            handler.flush()

        log_file = tmp_path / "logs" / "vfs_bot.jsonl"
        content = log_file.read_text()

        # Should contain JSON formatted logs
        assert "{" in content
        assert "timestamp" in content

    def test_setup_without_json_format(self, tmp_path, monkeypatch):
        """Test setup with JSON format disabled."""
        monkeypatch.chdir(tmp_path)

        # Clear handlers from previous tests
        logging.root.handlers = []

        setup_structured_logging(level="INFO", json_format=False)
        logger = logging.getLogger("test")
        logger.info("Test message")

        # Force flush
        for handler in logging.root.handlers:
            handler.flush()

        log_file = tmp_path / "logs" / "vfs_bot.jsonl"
        content = log_file.read_text()

        # Should contain human-readable logs
        assert "Test message" in content

    def test_setup_log_level(self, tmp_path, monkeypatch):
        """Test that log level is set correctly."""
        monkeypatch.chdir(tmp_path)

        # Clear handlers and reset log level from previous tests
        logging.root.handlers = []
        logging.root.setLevel(logging.NOTSET)

        setup_structured_logging(level="WARNING", json_format=False)

        assert logging.root.level == logging.WARNING

    def test_correlation_id_patcher_integration(self, tmp_path, monkeypatch):
        """Test that correlation_id is automatically added to Loguru logs via patcher."""
        monkeypatch.chdir(tmp_path)

        from loguru import logger as loguru_logger

        from src.core.logger import correlation_id_ctx

        # Setup logging
        setup_structured_logging(level="INFO", json_format=True)

        # Set a correlation ID
        test_correlation_id = "test-correlation-123"
        correlation_id_ctx.set(test_correlation_id)

        # Log a message
        loguru_logger.info("Test message with correlation_id")

        # Force flush
        for handler in logging.root.handlers:
            handler.flush()

        # Read the log file
        log_file = tmp_path / "logs" / "vfs_bot.jsonl"
        content = log_file.read_text()

        # Should contain the correlation_id in the JSON log
        assert test_correlation_id in content
        assert "correlation_id" in content

    def test_correlation_id_patcher_no_id_set(self, tmp_path, monkeypatch):
        """Test that patcher handles case when correlation_id is not set."""
        monkeypatch.chdir(tmp_path)

        from loguru import logger as loguru_logger

        from src.core.logger import correlation_id_ctx

        # Setup logging
        setup_structured_logging(level="INFO", json_format=True)

        # Ensure no correlation ID is set
        correlation_id_ctx.set(None)

        # Log a message
        loguru_logger.info("Test message without correlation_id")

        # Should not crash - patcher should handle None gracefully
        # Force flush
        for handler in logging.root.handlers:
            handler.flush()

        log_file = tmp_path / "logs" / "vfs_bot.jsonl"
        assert log_file.exists()
