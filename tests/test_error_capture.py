"""Tests for error capture."""

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.error_capture import ErrorCapture


class TestErrorCapture:
    """Test error capture functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        # Setup - use a test-specific directory
        self.test_dir = Path("screenshots/test_errors")
        yield
        # Teardown - clean up test directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_init(self):
        """Test ErrorCapture initialization."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        assert ec.screenshots_dir == self.test_dir
        assert self.test_dir.exists()
        assert ec.errors == []
        assert ec.max_errors == 100

    def test_init_custom_cleanup_days(self):
        """Test ErrorCapture initialization with custom cleanup days."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir), cleanup_days=14)
        assert ec.cleanup_days == 14

    def test_get_recent_errors_empty(self):
        """Test get_recent_errors with no errors."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        errors = ec.get_recent_errors()

        assert errors == []

    def test_get_recent_errors_with_limit(self):
        """Test get_recent_errors with limit."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        # Add some errors
        for i in range(30):
            ec.errors.append({"id": f"error_{i}", "timestamp": f"2024-01-{i+1:02d}T10:00:00"})

        recent = ec.get_recent_errors(limit=10)
        assert len(recent) == 10

    def test_get_recent_errors_sorting(self):
        """Test that get_recent_errors returns sorted by timestamp."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        ec.errors.append({"id": "error_1", "timestamp": "2024-01-01T10:00:00"})
        ec.errors.append({"id": "error_2", "timestamp": "2024-01-03T10:00:00"})
        ec.errors.append({"id": "error_3", "timestamp": "2024-01-02T10:00:00"})

        recent = ec.get_recent_errors()
        assert recent[0]["id"] == "error_2"  # Most recent first
        assert recent[1]["id"] == "error_3"
        assert recent[2]["id"] == "error_1"

    def test_get_error_by_id_nonexistent(self):
        """Test get_error_by_id for nonexistent error."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        error = ec.get_error_by_id("nonexistent_id")

        assert error is None

    def test_get_error_by_id_from_memory(self):
        """Test get_error_by_id from memory."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        test_error = {
            "id": "test_error_123",
            "timestamp": "2024-01-15T10:00:00",
            "error_type": "TestError",
        }
        ec.errors.append(test_error)

        retrieved = ec.get_error_by_id("test_error_123")
        assert retrieved == test_error

    def test_get_error_by_id_from_disk(self):
        """Test get_error_by_id from disk."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        # Create a test error file on disk
        test_error = {
            "id": "disk_error_123",
            "timestamp": "2024-01-15T10:00:00",
            "error_type": "TestError",
        }

        error_file = self.test_dir / "disk_error_123.json"
        error_file.write_text(json.dumps(test_error))

        retrieved = ec.get_error_by_id("disk_error_123")
        assert retrieved["id"] == "disk_error_123"

    @pytest.mark.asyncio
    async def test_capture_basic(self):
        """Test basic error capture."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.query_selector = AsyncMock(return_value=None)

        error = Exception("Test error")
        context = {"step": "login", "action": "fill_email"}

        error_record = await ec.capture(mock_page, error, context)

        assert error_record["error_type"] == "Exception"
        assert error_record["error_message"] == "Test error"
        assert error_record["context"] == context
        assert error_record["url"] == "https://example.com"
        assert error_record["title"] == "Test Page"
        assert "captures" in error_record

        # Check that error was added to memory
        assert len(ec.errors) == 1

    @pytest.mark.asyncio
    async def test_capture_with_element_selector(self):
        """Test error capture with element selector."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        mock_element = AsyncMock()
        mock_element.screenshot = AsyncMock()

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        error = Exception("Test error")
        context = {"step": "login"}

        error_record = await ec.capture(mock_page, error, context, element_selector="#email")

        assert "failed_selector" in error_record
        assert error_record["failed_selector"] == "#email"
        mock_page.query_selector.assert_called_once_with("#email")

    @pytest.mark.asyncio
    async def test_capture_creates_files(self):
        """Test that capture creates files on disk."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.query_selector = AsyncMock(return_value=None)

        error = Exception("Test error")
        context = {}

        error_record = await ec.capture(mock_page, error, context)

        error_id = error_record["id"]

        # Check that JSON file was created
        json_file = self.test_dir / f"{error_id}.json"
        assert json_file.exists()

    @pytest.mark.asyncio
    async def test_capture_max_errors_enforcement(self):
        """Test that capture enforces max_errors limit."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        ec.max_errors = 5

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.query_selector = AsyncMock(return_value=None)

        # Capture more than max_errors
        for i in range(10):
            error = Exception(f"Test error {i}")
            await ec.capture(mock_page, error, {})

        # Should only keep last max_errors
        assert len(ec.errors) == 5

    @pytest.mark.asyncio
    async def test_capture_exception_handling(self):
        """Test capture handles its own exceptions."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.query_selector = AsyncMock(return_value=None)

        error = Exception("Original error")
        context = {}

        # Should not raise exception
        error_record = await ec.capture(mock_page, error, context)
        assert "capture_error" in error_record

    @pytest.mark.asyncio
    async def test_cleanup_old_errors_not_called_early(self):
        """Test that cleanup is not called before interval expires."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.query_selector = AsyncMock(return_value=None)

        # First capture
        await ec.capture(mock_page, Exception("Error 1"), {})

        initial_cleanup_time = ec._last_cleanup

        # Second capture immediately after
        await ec.capture(mock_page, Exception("Error 2"), {})

        # Cleanup time should not have changed
        assert ec._last_cleanup == initial_cleanup_time
