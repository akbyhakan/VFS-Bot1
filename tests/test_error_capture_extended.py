"""Extended tests for src/utils/error_capture.py - aiming for 93% coverage."""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from src.utils.error_capture import ErrorCapture


@pytest.mark.asyncio
class TestCaptureBasicError:
    """Tests for basic error capture."""

    async def test_capture_basic_error(self, tmp_path):
        """Test capturing a basic error."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {"step": "login", "action": "fill_username"}

        error_record = await error_capture.capture(page, error, context)

        assert error_record["error_type"] == "Exception"
        assert error_record["error_message"] == "Test error"
        assert error_record["context"] == context
        assert error_record["url"] == "https://example.com"
        assert "captures" in error_record


@pytest.mark.asyncio
class TestCaptureWithScreenshots:
    """Tests for error capture with screenshots."""

    async def test_capture_with_screenshots(self, tmp_path):
        """Test that screenshots are captured."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {}

        error_record = await error_capture.capture(page, error, context)

        assert "full_screenshot" in error_record["captures"]
        page.screenshot.assert_called_once()


@pytest.mark.asyncio
class TestCaptureWithElementSelector:
    """Tests for error capture with element selector."""

    async def test_capture_with_element_selector(self, tmp_path):
        """Test capturing with element selector."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        element = AsyncMock()
        element.screenshot = AsyncMock()
        page.query_selector = AsyncMock(return_value=element)

        error = Exception("Test error")
        context = {}

        error_record = await error_capture.capture(
            page, error, context, element_selector="#test-element"
        )

        assert "element_screenshot" in error_record["captures"]
        assert error_record["failed_selector"] == "#test-element"
        element.screenshot.assert_called_once()

    async def test_capture_element_not_found(self, tmp_path):
        """Test capturing when element is not found."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}
        page.query_selector = AsyncMock(return_value=None)

        error = Exception("Test error")
        context = {}

        error_record = await error_capture.capture(
            page, error, context, element_selector="#missing-element"
        )

        # Should not crash, just skip element screenshot
        assert "element_screenshot" not in error_record["captures"]


@pytest.mark.asyncio
class TestCaptureHtmlSnapshot:
    """Tests for HTML snapshot capture."""

    async def test_capture_html_snapshot(self, tmp_path):
        """Test that HTML snapshot is captured."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {}

        error_record = await error_capture.capture(page, error, context)

        assert "html_snapshot" in error_record["captures"]
        html_file = Path(error_record["captures"]["html_snapshot"])
        assert html_file.exists()
        assert "<html>" in html_file.read_text()


@pytest.mark.asyncio
class TestCaptureSavesJson:
    """Tests for saving error record as JSON."""

    async def test_capture_saves_json(self, tmp_path):
        """Test that error record is saved as JSON."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {}

        error_record = await error_capture.capture(page, error, context)

        json_file = tmp_path / "errors" / f"{error_record['id']}.json"
        assert json_file.exists()
        loaded_data = json.loads(json_file.read_text())
        assert loaded_data["error_type"] == "Exception"


@pytest.mark.asyncio
class TestCaptureAddsToErrorList:
    """Tests for adding errors to in-memory list."""

    async def test_capture_adds_to_error_list(self, tmp_path):
        """Test that captured errors are added to in-memory list."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        context = {}

        await error_capture.capture(page, error, context)

        assert len(error_capture.errors) == 1
        assert error_capture.errors[0]["error_type"] == "Exception"


@pytest.mark.asyncio
class TestMaxErrorsLimit:
    """Tests for max errors limit."""

    async def test_max_errors_limit(self, tmp_path):
        """Test that error list respects max_errors limit."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        error_capture.max_errors = 5
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        # Capture 10 errors
        for i in range(10):
            error = Exception(f"Error {i}")
            await error_capture.capture(page, error, {})

        # Should only keep last 5
        assert len(error_capture.errors) == 5


@pytest.mark.asyncio
class TestGetRecentErrors:
    """Tests for get_recent_errors method."""

    async def test_get_recent_errors(self, tmp_path):
        """Test getting recent errors."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        # Capture 5 errors
        for i in range(5):
            error = Exception(f"Error {i}")
            await error_capture.capture(page, error, {})

        recent = error_capture.get_recent_errors(limit=3)

        assert len(recent) == 3
        # Should be sorted by timestamp, most recent first


@pytest.mark.asyncio
class TestGetErrorById:
    """Tests for get_error_by_id method."""

    async def test_get_error_by_id_from_memory(self, tmp_path):
        """Test getting error by ID from memory."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        error_record = await error_capture.capture(page, error, {})

        found_error = error_capture.get_error_by_id(error_record["id"])

        assert found_error is not None
        assert found_error["id"] == error_record["id"]

    async def test_get_error_by_id_from_disk(self, tmp_path):
        """Test getting error by ID from disk."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        error_record = await error_capture.capture(page, error, {})

        # Clear memory
        error_capture.errors = []

        # Should load from disk
        found_error = error_capture.get_error_by_id(error_record["id"])

        assert found_error is not None
        assert found_error["id"] == error_record["id"]

    async def test_get_error_by_id_not_found(self, tmp_path):
        """Test getting non-existent error by ID."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))

        found_error = error_capture.get_error_by_id("nonexistent")

        assert found_error is None


@pytest.mark.asyncio
class TestCleanupOldErrors:
    """Tests for cleanup of old errors."""

    async def test_cleanup_old_errors(self, tmp_path):
        """Test cleanup of old error files."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"), cleanup_days=1)
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        # Create an error
        error = Exception("Old error")
        error_record = await error_capture.capture(page, error, {})

        # Manually age the files
        old_time = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
        for file_path in error_capture.screenshots_dir.glob("*"):
            import os

            os.utime(file_path, (old_time, old_time))

        # Force cleanup
        error_capture._last_cleanup = 0
        await error_capture._cleanup_old_errors()

        # Files should be deleted
        assert len(list(error_capture.screenshots_dir.glob("*"))) == 0

    async def test_cleanup_respects_interval(self, tmp_path):
        """Test that cleanup respects interval."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        # Capture an error (triggers cleanup)
        error = Exception("Test error")
        await error_capture.capture(page, error, {})

        initial_cleanup_time = error_capture._last_cleanup

        # Capture another error immediately (should skip cleanup)
        error2 = Exception("Test error 2")
        await error_capture.capture(page, error2, {})

        # Cleanup time should not have changed
        assert error_capture._last_cleanup == initial_cleanup_time


@pytest.mark.asyncio
class TestViewportInfoCaptured:
    """Tests for viewport info capture."""

    async def test_viewport_info_captured(self, tmp_path):
        """Test that viewport info is captured."""
        error_capture = ErrorCapture(screenshots_dir=str(tmp_path / "errors"))
        page = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        page.viewport_size = {"width": 1920, "height": 1080}

        error = Exception("Test error")
        error_record = await error_capture.capture(page, error, {})

        assert "viewport" in error_record
        assert error_record["viewport"]["width"] == 1920
        assert error_record["viewport"]["height"] == 1080
