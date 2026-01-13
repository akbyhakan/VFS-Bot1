"""Extended tests for error capture functionality."""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.utils.error_capture import ErrorCapture


@pytest.fixture
def test_error_dir(tmp_path):
    """Create a temporary directory for error captures."""
    error_dir = tmp_path / "error_captures"
    return str(error_dir)


@pytest.fixture
def error_capture(test_error_dir):
    """Create an ErrorCapture instance."""
    return ErrorCapture(screenshots_dir=test_error_dir, cleanup_days=7)


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Test page</body></html>")
    page.title = AsyncMock(return_value="Test Page")
    page.url = "https://example.com/test"
    page.viewport_size = {"width": 1920, "height": 1080}
    page.query_selector = AsyncMock(return_value=None)
    return page


@pytest.mark.asyncio
async def test_capture_basic_error(error_capture, mock_page):
    """Test capturing a basic error."""
    error = ValueError("Test error")
    context = {"step": "login", "action": "fill_form"}

    result = await error_capture.capture(mock_page, error, context)

    assert result["error_type"] == "ValueError"
    assert result["error_message"] == "Test error"
    assert result["context"] == context
    assert result["url"] == "https://example.com/test"
    assert result["title"] == "Test Page"


@pytest.mark.asyncio
async def test_capture_with_screenshots(error_capture, mock_page):
    """Test that screenshots are captured."""
    error = RuntimeError("Test error")
    context = {"step": "booking"}

    result = await error_capture.capture(mock_page, error, context)

    # Verify screenshot was called
    mock_page.screenshot.assert_called_once()
    # Verify captures contain screenshot path
    assert "full_screenshot" in result["captures"]
    assert result["captures"]["full_screenshot"].endswith(".png")


@pytest.mark.asyncio
async def test_capture_with_element_selector(error_capture, mock_page):
    """Test capturing with element selector."""
    mock_element = AsyncMock()
    mock_element.screenshot = AsyncMock()
    mock_page.query_selector = AsyncMock(return_value=mock_element)

    error = Exception("Element error")
    context = {"step": "click"}

    result = await error_capture.capture(mock_page, error, context, element_selector="#button")

    # Verify element screenshot was attempted
    mock_page.query_selector.assert_called_with("#button")
    mock_element.screenshot.assert_called_once()
    assert "failed_selector" in result
    assert result["failed_selector"] == "#button"


@pytest.mark.asyncio
async def test_capture_element_not_found(error_capture, mock_page):
    """Test element capture when element not found."""
    mock_page.query_selector = AsyncMock(return_value=None)

    error = Exception("Test error")
    context = {}

    result = await error_capture.capture(mock_page, error, context, element_selector="#missing")

    # Should not crash, just skip element screenshot
    assert "element_screenshot" not in result["captures"]


@pytest.mark.asyncio
async def test_capture_html_snapshot(error_capture, mock_page):
    """Test HTML snapshot capture."""
    error = Exception("Test error")
    context = {}

    result = await error_capture.capture(mock_page, error, context)

    # Verify HTML was captured
    mock_page.content.assert_called_once()
    assert "html_snapshot" in result["captures"]

    # Verify HTML file exists
    html_path = Path(result["captures"]["html_snapshot"])
    assert html_path.exists()
    assert html_path.read_text() == "<html><body>Test page</body></html>"


@pytest.mark.asyncio
async def test_capture_saves_json(error_capture, mock_page):
    """Test that error record is saved as JSON."""
    error = Exception("Test error")
    context = {"test": "data"}

    result = await error_capture.capture(mock_page, error, context)

    # Find JSON file
    error_id = result["id"]
    json_path = error_capture.screenshots_dir / f"{error_id}.json"
    assert json_path.exists()

    # Verify JSON content
    saved_data = json.loads(json_path.read_text())
    assert saved_data["error_type"] == "Exception"
    assert saved_data["error_message"] == "Test error"


@pytest.mark.asyncio
async def test_capture_adds_to_error_list(error_capture, mock_page):
    """Test that errors are added to in-memory list."""
    error = Exception("Test error")
    context = {}

    await error_capture.capture(mock_page, error, context)

    assert len(error_capture.errors) == 1
    assert error_capture.errors[0]["error_type"] == "Exception"


@pytest.mark.asyncio
async def test_max_errors_limit(error_capture, mock_page):
    """Test that error list respects max limit."""
    error_capture.max_errors = 3

    # Add more than max errors
    for i in range(5):
        error = Exception(f"Error {i}")
        await error_capture.capture(mock_page, error, {})

    # Should only keep last 3
    assert len(error_capture.errors) == 3
    # Should have most recent errors
    assert error_capture.errors[-1]["error_message"] == "Error 4"


def test_get_recent_errors(error_capture):
    """Test getting recent errors."""
    # Add some errors manually
    for i in range(5):
        error_capture.errors.append(
            {"id": f"error_{i}", "timestamp": f"2024-01-{i:02d}T00:00:00Z", "error_type": "Test"}
        )

    recent = error_capture.get_recent_errors(limit=3)

    assert len(recent) == 3
    # Should be sorted by timestamp descending
    assert recent[0]["timestamp"] > recent[-1]["timestamp"]


def test_get_recent_errors_empty(error_capture):
    """Test getting recent errors when list is empty."""
    recent = error_capture.get_recent_errors()
    assert recent == []


def test_get_error_by_id_from_memory(error_capture):
    """Test getting error by ID from memory."""
    error_capture.errors.append({"id": "test_123", "error_type": "Test"})

    error = error_capture.get_error_by_id("test_123")

    assert error is not None
    assert error["id"] == "test_123"


def test_get_error_by_id_from_disk(error_capture):
    """Test getting error by ID from disk."""
    # Create a JSON file
    error_id = "test_disk_123"
    json_path = error_capture.screenshots_dir / f"{error_id}.json"
    json_path.write_text(json.dumps({"id": error_id, "error_type": "DiskError"}))

    error = error_capture.get_error_by_id(error_id)

    assert error is not None
    assert error["id"] == error_id
    assert error["error_type"] == "DiskError"


def test_get_error_by_id_not_found(error_capture):
    """Test getting non-existent error."""
    error = error_capture.get_error_by_id("nonexistent")
    assert error is None


@pytest.mark.asyncio
async def test_cleanup_old_errors(error_capture):
    """Test cleanup of old error files."""
    # Create old files
    old_time = time.time() - (8 * 24 * 60 * 60)  # 8 days ago

    for i in range(3):
        file_path = error_capture.screenshots_dir / f"old_{i}.png"
        file_path.write_text("old")
        # Set modification time to old
        import os

        os.utime(file_path, (old_time, old_time))

    # Create recent file
    recent_file = error_capture.screenshots_dir / "recent.png"
    recent_file.write_text("recent")

    # Force cleanup by setting last cleanup to long ago
    error_capture._last_cleanup = 0

    # Run cleanup
    await error_capture._cleanup_old_errors()

    # Old files should be deleted, recent should remain
    assert not (error_capture.screenshots_dir / "old_0.png").exists()
    assert recent_file.exists()


@pytest.mark.asyncio
async def test_cleanup_respects_interval(error_capture):
    """Test that cleanup respects interval."""
    # Set last cleanup to recent time
    error_capture._last_cleanup = time.time()

    # Create an old file
    old_time = time.time() - (8 * 24 * 60 * 60)
    file_path = error_capture.screenshots_dir / "old.png"
    file_path.write_text("old")
    import os

    os.utime(file_path, (old_time, old_time))

    # Run cleanup - should skip due to interval
    await error_capture._cleanup_old_errors()

    # File should still exist (cleanup was skipped)
    assert file_path.exists()


@pytest.mark.asyncio
async def test_capture_handles_screenshot_error(error_capture, mock_page):
    """Test that capture handles screenshot errors gracefully."""
    mock_page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))

    error = Exception("Test error")
    context = {}

    # Should not crash
    result = await error_capture.capture(mock_page, error, context)

    assert "capture_error" in result


@pytest.mark.asyncio
async def test_capture_with_console_logs(error_capture, mock_page):
    """Test capturing with console logs in context."""
    error = Exception("Test error")
    context = {"console_logs": ["Error: Test", "Warning: Something"]}

    result = await error_capture.capture(mock_page, error, context)

    assert result["console_logs"] == ["Error: Test", "Warning: Something"]


@pytest.mark.asyncio
async def test_capture_with_network_requests(error_capture, mock_page):
    """Test capturing with network requests in context."""
    error = Exception("Test error")
    context = {"network_requests": [{"url": "https://api.example.com", "status": 500}]}

    result = await error_capture.capture(mock_page, error, context)

    assert len(result["network_requests"]) == 1
    assert result["network_requests"][0]["url"] == "https://api.example.com"


@pytest.mark.asyncio
async def test_viewport_info_captured(error_capture, mock_page):
    """Test that viewport information is captured."""
    error = Exception("Test error")
    context = {}

    result = await error_capture.capture(mock_page, error, context)

    assert "viewport" in result
    assert result["viewport"] == {"width": 1920, "height": 1080}
