"""Tests for logging_config module."""

import json
import logging
from io import StringIO
from unittest.mock import patch

import pytest

from src.core.logger import setup_structured_logging


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
