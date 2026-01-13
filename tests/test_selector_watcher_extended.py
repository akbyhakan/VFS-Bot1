"""Tests for selector health check (selector watcher)."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.selector_watcher import SelectorHealthCheck


@pytest.fixture
def mock_selector_manager():
    """Mock SelectorManager."""
    manager = MagicMock()
    manager.get = MagicMock(return_value="button.submit")
    manager.get_fallbacks = MagicMock(return_value=["button#submit", "input[type='submit']"])
    return manager


@pytest.fixture
def mock_notifier():
    """Mock NotificationService."""
    notifier = AsyncMock()
    notifier.notify_error = AsyncMock()
    return notifier


@pytest.fixture
def mock_page():
    """Mock Playwright page object."""
    page = AsyncMock()
    page.wait_for_selector = AsyncMock()
    return page


def test_selector_health_check_initialization(mock_selector_manager):
    """Test selector health check initialization."""
    checker = SelectorHealthCheck(mock_selector_manager)
    assert checker.selector_manager == mock_selector_manager
    assert checker.check_interval == 3600
    assert checker.health_status == {}
    assert checker.last_check is None


def test_selector_health_check_custom_interval(mock_selector_manager, mock_notifier):
    """Test selector health check with custom interval."""
    checker = SelectorHealthCheck(mock_selector_manager, mock_notifier, check_interval=1800)
    assert checker.check_interval == 1800
    assert checker.notifier == mock_notifier


@pytest.mark.asyncio
async def test_validate_selector_success(mock_selector_manager, mock_page):
    """Test successful selector validation."""
    mock_element = MagicMock()
    mock_page.wait_for_selector = AsyncMock(return_value=mock_element)

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["valid"] is True
    assert result["found"] is True
    assert result["fallback_used"] is False
    assert result["error"] is None
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_validate_selector_not_in_config(mock_selector_manager, mock_page):
    """Test validation when selector not in config."""
    mock_selector_manager.get = MagicMock(return_value=None)

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "nonexistent.selector")

    assert result["valid"] is False
    assert result["found"] is False
    assert result["error"] == "Selector not found in config"


@pytest.mark.asyncio
async def test_validate_selector_fallback_used(mock_selector_manager, mock_page, mock_notifier):
    """Test validation using fallback selector."""
    # Primary selector fails, fallback succeeds
    mock_page.wait_for_selector = AsyncMock(
        side_effect=[Exception("Primary failed"), MagicMock()]
    )

    checker = SelectorHealthCheck(mock_selector_manager, mock_notifier)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["valid"] is True
    assert result["found"] is True
    assert result["fallback_used"] is True
    assert result["fallback_index"] == 0


@pytest.mark.asyncio
async def test_validate_selector_all_fail(mock_selector_manager, mock_page):
    """Test validation when all selectors fail."""
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["valid"] is False
    assert result["found"] is False
    assert "All selectors failed" in result["error"]


@pytest.mark.asyncio
async def test_validate_selector_custom_timeout(mock_selector_manager, mock_page):
    """Test validation with custom timeout."""
    mock_element = MagicMock()
    mock_page.wait_for_selector = AsyncMock(return_value=mock_element)

    checker = SelectorHealthCheck(mock_selector_manager)
    await checker.validate_selector(mock_page, "login.email_input", timeout=10000)

    # Verify timeout was passed to wait_for_selector
    call_kwargs = mock_page.wait_for_selector.call_args[1]
    assert call_kwargs["timeout"] == 10000


@pytest.mark.asyncio
async def test_validate_selector_includes_timestamp(mock_selector_manager, mock_page):
    """Test that validation result includes timestamp."""
    mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert "timestamp" in result
    # Verify it's a valid ISO format timestamp
    datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_selector_manager_get_called(mock_selector_manager, mock_page):
    """Test that selector manager get is called."""
    mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())

    checker = SelectorHealthCheck(mock_selector_manager)
    await checker.validate_selector(mock_page, "login.email_input")

    mock_selector_manager.get.assert_called_once_with("login.email_input")


@pytest.mark.asyncio
async def test_fallback_retrieval_on_primary_failure(mock_selector_manager, mock_page):
    """Test that fallbacks are retrieved when primary fails."""
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

    checker = SelectorHealthCheck(mock_selector_manager)
    await checker.validate_selector(mock_page, "login.email_input")

    mock_selector_manager.get_fallbacks.assert_called_once_with("login.email_input")


@pytest.mark.asyncio
async def test_multiple_fallback_attempts(mock_selector_manager, mock_page):
    """Test that multiple fallbacks are tried."""
    # First two calls fail (primary + first fallback), third succeeds
    mock_page.wait_for_selector = AsyncMock(
        side_effect=[Exception("Primary failed"), Exception("First fallback failed"), MagicMock()]
    )

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["valid"] is True
    assert result["fallback_used"] is True
    assert result["fallback_index"] == 1


@pytest.mark.asyncio
async def test_health_status_tracking(mock_selector_manager, mock_page):
    """Test that health status can be tracked."""
    mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    # Health status should be accessible
    assert isinstance(checker.health_status, dict)


@pytest.mark.asyncio
async def test_no_fallbacks_available(mock_selector_manager, mock_page):
    """Test behavior when no fallbacks are available."""
    mock_selector_manager.get_fallbacks = MagicMock(return_value=[])
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["valid"] is False
    assert result["fallback_used"] is False


@pytest.mark.asyncio
async def test_fallback_none_handling(mock_selector_manager, mock_page):
    """Test handling when get_fallbacks returns None."""
    mock_selector_manager.get_fallbacks = MagicMock(return_value=None)
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["valid"] is False


@pytest.mark.asyncio
async def test_selector_path_in_result(mock_selector_manager, mock_page):
    """Test that selector path is included in result."""
    mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())

    checker = SelectorHealthCheck(mock_selector_manager)
    result = await checker.validate_selector(mock_page, "login.email_input")

    assert result["selector_path"] == "login.email_input"


@pytest.mark.asyncio
async def test_wait_for_selector_state_attached(mock_selector_manager, mock_page):
    """Test that wait_for_selector uses 'attached' state."""
    mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())

    checker = SelectorHealthCheck(mock_selector_manager)
    await checker.validate_selector(mock_page, "login.email_input")

    call_kwargs = mock_page.wait_for_selector.call_args[1]
    assert call_kwargs["state"] == "attached"
