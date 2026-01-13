"""Extended tests for error_capture.py - Target 93% coverage."""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from src.utils.error_capture import ErrorCapture


@pytest.fixture
def temp_screenshots_dir(tmp_path):
    """Create temporary screenshots directory."""
    return str(tmp_path / "test_screenshots")


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Test Page</body></html>")
    page.url = "https://example.com/test"
    page.title = AsyncMock(return_value="Test Page Title")
    page.viewport_size = {"width": 1920, "height": 1080}
    page.query_selector = AsyncMock(return_value=None)
    return page


def test_error_capture_initialization(temp_screenshots_dir):
    """Test ErrorCapture initialization."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir, cleanup_days=5)
    assert capture.screenshots_dir == Path(temp_screenshots_dir)
    assert capture.screenshots_dir.exists()
    assert capture.cleanup_days == 5
    assert capture.max_errors == 100
    assert len(capture.errors) == 0


def test_error_capture_default_initialization():
    """Test ErrorCapture with default parameters."""
    capture = ErrorCapture()
    assert capture.screenshots_dir == Path("screenshots/errors")
    assert capture.cleanup_days == 7


@pytest.mark.asyncio
async def test_capture_basic_error(mock_page, temp_screenshots_dir):
    """Test basic error capture."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")
    context = {"step": "login", "action": "fill_form"}

    result = await capture.capture(mock_page, error, context)

    assert result["error_type"] == "Exception"
    assert result["error_message"] == "Test error"
    assert result["context"] == context
    assert "id" in result
    assert "timestamp" in result
    assert "captures" in result
    assert "url" in result
    assert result["url"] == "https://example.com/test"
    assert result["title"] == "Test Page Title"


@pytest.mark.asyncio
async def test_capture_creates_screenshot(mock_page, temp_screenshots_dir):
    """Test that capture creates screenshot file."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    result = await capture.capture(mock_page, error, {})

    assert "full_screenshot" in result["captures"]
    screenshot_path = Path(result["captures"]["full_screenshot"])
    # Mock doesn't actually create file, but path should be valid
    assert screenshot_path.parent == capture.screenshots_dir
    mock_page.screenshot.assert_called_once()


@pytest.mark.asyncio
async def test_capture_with_element_selector(mock_page, temp_screenshots_dir):
    """Test error capture with element selector."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Element error")

    # Create a mock element
    mock_element = AsyncMock()
    mock_element.screenshot = AsyncMock()
    mock_page.query_selector.return_value = mock_element

    result = await capture.capture(mock_page, error, {}, element_selector="#test-button")

    assert "failed_selector" in result
    assert result["failed_selector"] == "#test-button"
    assert "element_screenshot" in result["captures"]
    mock_element.screenshot.assert_called_once()


@pytest.mark.asyncio
async def test_capture_element_selector_not_found(mock_page, temp_screenshots_dir):
    """Test error capture when element selector not found."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Element error")

    # Element not found
    mock_page.query_selector.return_value = None

    result = await capture.capture(mock_page, error, {}, element_selector="#missing")

    # Should continue without element screenshot
    assert "element_screenshot" not in result["captures"]


@pytest.mark.asyncio
async def test_capture_element_screenshot_fails(mock_page, temp_screenshots_dir):
    """Test error capture when element screenshot fails."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Element error")

    # Element exists but screenshot fails
    mock_element = AsyncMock()
    mock_element.screenshot.side_effect = Exception("Screenshot failed")
    mock_page.query_selector.return_value = mock_element

    result = await capture.capture(mock_page, error, {}, element_selector="#test")

    # Should continue without element screenshot
    assert "element_screenshot" not in result["captures"]


@pytest.mark.asyncio
async def test_capture_saves_html_snapshot(mock_page, temp_screenshots_dir):
    """Test that HTML snapshot is saved."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    result = await capture.capture(mock_page, error, {})

    assert "html_snapshot" in result["captures"]
    html_path = Path(result["captures"]["html_snapshot"])
    assert html_path.exists()
    content = html_path.read_text()
    assert "Test Page" in content


@pytest.mark.asyncio
async def test_capture_with_console_logs(mock_page, temp_screenshots_dir):
    """Test error capture with console logs."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")
    context = {"console_logs": ["Error: API failed", "Warning: Timeout"]}

    result = await capture.capture(mock_page, error, context)

    assert result["console_logs"] == ["Error: API failed", "Warning: Timeout"]


@pytest.mark.asyncio
async def test_capture_with_network_requests(mock_page, temp_screenshots_dir):
    """Test error capture with network requests."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Network error")
    context = {"network_requests": [{"url": "/api/login", "status": 500}]}

    result = await capture.capture(mock_page, error, context)

    assert result["network_requests"] == [{"url": "/api/login", "status": 500}]


@pytest.mark.asyncio
async def test_capture_viewport_info(mock_page, temp_screenshots_dir):
    """Test that viewport info is captured."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    result = await capture.capture(mock_page, error, {})

    assert "viewport" in result
    assert result["viewport"]["width"] == 1920
    assert result["viewport"]["height"] == 1080


@pytest.mark.asyncio
async def test_capture_saves_json_record(mock_page, temp_screenshots_dir):
    """Test that error record is saved as JSON."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    result = await capture.capture(mock_page, error, {})

    json_path = capture.screenshots_dir / f"{result['id']}.json"
    assert json_path.exists()
    loaded_data = json.loads(json_path.read_text())
    assert loaded_data["error_message"] == "Test error"


@pytest.mark.asyncio
async def test_capture_adds_to_errors_list(mock_page, temp_screenshots_dir):
    """Test that error is added to in-memory list."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    assert len(capture.errors) == 0
    await capture.capture(mock_page, error, {})
    assert len(capture.errors) == 1


@pytest.mark.asyncio
async def test_capture_respects_max_errors(mock_page, temp_screenshots_dir):
    """Test that errors list respects max_errors limit."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    capture.max_errors = 3

    # Add 5 errors
    for i in range(5):
        error = Exception(f"Error {i}")
        await capture.capture(mock_page, error, {})

    # Should only keep last 3
    assert len(capture.errors) == 3
    # Verify it's the most recent ones
    assert capture.errors[2]["error_message"] == "Error 4"


@pytest.mark.asyncio
async def test_capture_handles_screenshot_failure(mock_page, temp_screenshots_dir):
    """Test that capture handles screenshot failure gracefully."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")
    mock_page.screenshot.side_effect = Exception("Screenshot failed")

    result = await capture.capture(mock_page, error, {})

    # Should still return result with capture_error
    assert "capture_error" in result


@pytest.mark.asyncio
async def test_capture_handles_html_failure(mock_page, temp_screenshots_dir):
    """Test that capture handles HTML snapshot failure gracefully."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")
    mock_page.content.side_effect = Exception("Content failed")

    result = await capture.capture(mock_page, error, {})

    # Should continue without HTML snapshot
    assert "html_snapshot" not in result["captures"] or result.get("capture_error")


def test_get_recent_errors(temp_screenshots_dir):
    """Test get_recent_errors method."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)

    # Add some errors manually
    for i in range(5):
        capture.errors.append(
            {
                "id": f"error_{i}",
                "timestamp": f"2024-01-{i+1:02d}T00:00:00Z",
                "error_message": f"Error {i}",
            }
        )

    recent = capture.get_recent_errors(limit=3)
    assert len(recent) == 3
    # Should be sorted by timestamp (most recent first)
    assert recent[0]["timestamp"] > recent[1]["timestamp"]


def test_get_recent_errors_empty(temp_screenshots_dir):
    """Test get_recent_errors with no errors."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    recent = capture.get_recent_errors()
    assert recent == []


def test_get_error_by_id_from_memory(temp_screenshots_dir):
    """Test get_error_by_id from in-memory list."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error_record = {
        "id": "test_error_123",
        "timestamp": "2024-01-01T00:00:00Z",
        "error_message": "Test error",
    }
    capture.errors.append(error_record)

    result = capture.get_error_by_id("test_error_123")
    assert result == error_record


def test_get_error_by_id_from_disk(temp_screenshots_dir):
    """Test get_error_by_id from disk."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error_record = {
        "id": "disk_error_456",
        "timestamp": "2024-01-01T00:00:00Z",
        "error_message": "Disk error",
    }

    # Save to disk
    json_path = capture.screenshots_dir / "disk_error_456.json"
    json_path.write_text(json.dumps(error_record))

    result = capture.get_error_by_id("disk_error_456")
    assert result["error_message"] == "Disk error"


def test_get_error_by_id_not_found(temp_screenshots_dir):
    """Test get_error_by_id when error not found."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    result = capture.get_error_by_id("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_cleanup_old_errors_not_triggered(mock_page, temp_screenshots_dir):
    """Test that cleanup doesn't run on every capture."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir, cleanup_days=1)
    error = Exception("Test error")

    # First capture
    await capture.capture(mock_page, error, {})
    first_cleanup_time = capture._last_cleanup

    # Immediate second capture (within cleanup interval)
    await capture.capture(mock_page, error, {})
    second_cleanup_time = capture._last_cleanup

    # Cleanup time should not have changed
    assert first_cleanup_time == second_cleanup_time


@pytest.mark.asyncio
async def test_cleanup_old_errors_triggered(mock_page, temp_screenshots_dir):
    """Test that cleanup runs after interval."""
    from src.constants import ErrorCapture as ErrorCaptureConstants

    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir, cleanup_days=1)
    error = Exception("Test error")

    # Create old file
    old_file = capture.screenshots_dir / "old_error.json"
    old_file.write_text("{}")
    # Set file modification time to 2 days ago
    old_time = time.time() - (2 * 24 * 60 * 60)
    old_file.touch()
    import os

    os.utime(old_file, (old_time, old_time))

    # Force cleanup by setting last cleanup time to past
    capture._last_cleanup = time.time() - ErrorCaptureConstants.CLEANUP_INTERVAL_SECONDS - 1

    await capture.capture(mock_page, error, {})

    # Old file should be deleted
    assert not old_file.exists()


@pytest.mark.asyncio
async def test_cleanup_preserves_recent_files(mock_page, temp_screenshots_dir):
    """Test that cleanup preserves recent files."""
    from src.constants import ErrorCapture as ErrorCaptureConstants

    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir, cleanup_days=7)
    error = Exception("Test error")

    # Create recent file
    recent_file = capture.screenshots_dir / "recent_error.json"
    recent_file.write_text("{}")

    # Force cleanup
    capture._last_cleanup = time.time() - ErrorCaptureConstants.CLEANUP_INTERVAL_SECONDS - 1

    await capture.capture(mock_page, error, {})

    # Recent file should still exist
    assert recent_file.exists()


@pytest.mark.asyncio
async def test_cleanup_handles_errors(mock_page, temp_screenshots_dir):
    """Test that cleanup errors don't break capture."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    # Force cleanup and make it fail
    from src.constants import ErrorCapture as ErrorCaptureConstants

    capture._last_cleanup = time.time() - ErrorCaptureConstants.CLEANUP_INTERVAL_SECONDS - 1

    with patch.object(Path, "glob", side_effect=Exception("Glob failed")):
        # Should not raise exception
        result = await capture.capture(mock_page, error, {})
        assert result is not None


@pytest.mark.asyncio
async def test_capture_error_timestamp_format(mock_page, temp_screenshots_dir):
    """Test that timestamp is in correct ISO format."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    result = await capture.capture(mock_page, error, {})

    # Verify timestamp is ISO format
    timestamp = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_capture_error_id_uniqueness(mock_page, temp_screenshots_dir):
    """Test that error IDs are unique."""
    capture = ErrorCapture(screenshots_dir=temp_screenshots_dir)
    error = Exception("Test error")

    result1 = await capture.capture(mock_page, error, {})
    result2 = await capture.capture(mock_page, error, {})

    assert result1["id"] != result2["id"]
