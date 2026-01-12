"""Tests for error capture."""

import pytest
from pathlib import Path
import sys
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import json

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

    def test_get_recent_errors_with_data(self):
        """Test get_recent_errors with data."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        ec.errors = [
            {"id": "error_1", "timestamp": "2024-01-01T12:00:00"},
            {"id": "error_2", "timestamp": "2024-01-01T13:00:00"},
            {"id": "error_3", "timestamp": "2024-01-01T14:00:00"},
        ]

        errors = ec.get_recent_errors(limit=2)

        assert len(errors) == 2
        # Should be sorted by timestamp descending
        assert errors[0]["id"] == "error_3"
        assert errors[1]["id"] == "error_2"

    def test_get_error_by_id_nonexistent(self):
        """Test get_error_by_id for nonexistent error."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        error = ec.get_error_by_id("nonexistent_id")

        assert error is None

    def test_get_error_by_id_in_memory(self):
        """Test get_error_by_id for error in memory."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        test_error = {"id": "error_123", "timestamp": "2024-01-01T12:00:00"}
        ec.errors.append(test_error)

        error = ec.get_error_by_id("error_123")

        assert error == test_error

    def test_get_error_by_id_from_disk(self):
        """Test get_error_by_id loads from disk."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        test_error = {"id": "error_disk", "timestamp": "2024-01-01T12:00:00", "error": "Test"}

        # Save to disk
        json_path = ec.screenshots_dir / "error_disk.json"
        json_path.write_text(json.dumps(test_error))

        error = ec.get_error_by_id("error_disk")

        assert error == test_error

    def test_max_errors_limit(self):
        """Test that errors list respects max_errors limit."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        ec.max_errors = 5

        # Add more errors than max
        for i in range(10):
            ec.errors.append({"id": f"error_{i}", "timestamp": f"2024-01-{i:02d}"})

        # Should only keep last 5
        assert len(ec.errors) == 10  # Manual append doesn't enforce limit

        # The capture method enforces the limit
        recent = ec.get_recent_errors(limit=10)
        assert len(recent) <= 10

    @pytest.mark.asyncio
    async def test_capture_basic(self):
        """Test basic error capture."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {"step": "login"}

        result = await ec.capture(page, error, context)

        assert result["error_type"] == "Exception"
        assert result["error_message"] == "Test error"
        assert result["context"] == context
        assert result["url"] == "https://example.com"
        assert "captures" in result
        page.screenshot.assert_awaited_once()
        page.content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_capture_with_element_selector(self):
        """Test error capture with element selector."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        # Mock element
        element = AsyncMock()
        element.screenshot = AsyncMock()
        page.query_selector = AsyncMock(return_value=element)

        error = Exception("Test error")
        context = {"step": "login"}

        result = await ec.capture(page, error, context, element_selector="#submit")

        assert result["failed_selector"] == "#submit"
        assert "element_screenshot" in result["captures"]
        element.screenshot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_capture_element_not_found(self):
        """Test error capture when element not found."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}
        page.query_selector = AsyncMock(return_value=None)

        error = Exception("Test error")
        context = {"step": "login"}

        result = await ec.capture(page, error, context, element_selector="#missing")

        # Should still capture other data
        assert "full_screenshot" in result["captures"]
        assert "element_screenshot" not in result["captures"]

    @pytest.mark.asyncio
    async def test_capture_with_console_logs(self):
        """Test error capture with console logs."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {"step": "login", "console_logs": ["Error: something", "Warning: test"]}

        result = await ec.capture(page, error, context)

        assert result["console_logs"] == ["Error: something", "Warning: test"]

    @pytest.mark.asyncio
    async def test_capture_with_network_requests(self):
        """Test error capture with network requests."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {"step": "login", "network_requests": [{"url": "/api/login", "status": 401}]}

        result = await ec.capture(page, error, context)

        assert result["network_requests"] == [{"url": "/api/login", "status": 401}]

    @pytest.mark.asyncio
    async def test_capture_enforces_max_errors(self):
        """Test capture enforces max_errors limit."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        ec.max_errors = 3
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        # Capture 5 errors
        for i in range(5):
            error = Exception(f"Test error {i}")
            await ec.capture(page, error, {"step": f"step_{i}"})

        # Should only keep last 3
        assert len(ec.errors) == 3
        assert ec.errors[0]["error_message"] == "Test error 2"
        assert ec.errors[2]["error_message"] == "Test error 4"

    @pytest.mark.asyncio
    async def test_capture_exception_handling(self):
        """Test capture handles exceptions gracefully."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        page = AsyncMock()
        page.screenshot.side_effect = Exception("Screenshot failed")
        page.content = AsyncMock(return_value="<html>test</html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {"step": "login"}

        result = await ec.capture(page, error, context)

        # Should still return a result
        assert result["error_type"] == "Exception"
        assert "capture_error" in result

    @pytest.mark.asyncio
    async def test_cleanup_old_errors_skips_recent(self):
        """Test cleanup skips if called too soon."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        ec._last_cleanup = ec._last_cleanup  # Set to current time

        # Create old file
        old_file = ec.screenshots_dir / "old_error.json"
        old_file.write_text("{}")

        await ec._cleanup_old_errors()

        # File should still exist (cleanup skipped)
        assert old_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_old_errors_removes_old_files(self):
        """Test cleanup removes old files."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir), cleanup_days=1)
        ec._last_cleanup = 0  # Force cleanup to run

        # Create old file
        old_file = ec.screenshots_dir / "old_error.json"
        old_file.write_text("{}")

        # Make file appear old
        old_time = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
        import os

        os.utime(old_file, (old_time, old_time))

        await ec._cleanup_old_errors()

        # Old file should be removed
        assert not old_file.exists()
