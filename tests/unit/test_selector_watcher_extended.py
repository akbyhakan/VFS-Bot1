"""Tests for selector health check (selector watcher)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest

from src.selector import SelectorHealthCheck


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
    assert checker.shutdown_event is None
    assert checker.critical_failure_threshold == 0.5


def test_selector_health_check_custom_interval(mock_selector_manager, mock_notifier):
    """Test selector health check with custom interval."""
    checker = SelectorHealthCheck(mock_selector_manager, mock_notifier, check_interval=1800)
    assert checker.check_interval == 1800
    assert checker.notifier == mock_notifier
    assert checker.shutdown_event is None
    assert checker.critical_failure_threshold == 0.5


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
    mock_page.wait_for_selector = AsyncMock(side_effect=[Exception("Primary failed"), MagicMock()])

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
    await checker.validate_selector(mock_page, "login.email_input")

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


def test_init_with_shutdown_event(mock_selector_manager):
    """Test that shutdown_event is stored correctly."""
    event = asyncio.Event()
    checker = SelectorHealthCheck(mock_selector_manager, shutdown_event=event)
    assert checker.shutdown_event is event


def test_init_with_custom_threshold(mock_selector_manager):
    """Test that custom critical_failure_threshold is stored correctly."""
    checker = SelectorHealthCheck(mock_selector_manager, critical_failure_threshold=0.75)
    assert checker.critical_failure_threshold == 0.75


@pytest.mark.asyncio
async def test_auto_stop_triggered_on_critical_failure(mock_selector_manager, mock_notifier):
    """Test that shutdown_event is set when failure ratio exceeds threshold."""
    event = asyncio.Event()
    checker = SelectorHealthCheck(
        mock_selector_manager,
        mock_notifier,
        shutdown_event=event,
        critical_failure_threshold=0.5,
    )

    # 4 invalid, 2 valid out of 6 critical selectors (67% > 50% threshold)
    invalid_result = {"valid": False, "fallback_used": False, "error": "Not found"}
    valid_result = {"valid": True, "fallback_used": False, "error": None}
    side_effects = [invalid_result] * 4 + [valid_result] * 2

    mock_page = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    with patch.object(checker, "validate_selector", new_callable=AsyncMock) as mock_validate:
        mock_validate.side_effect = [
            {**r, "selector_path": f"sel.{i}", "found": r["valid"], "timestamp": "2026-01-01T00:00:00+00:00"}
            for i, r in enumerate(side_effects)
        ]
        await checker.check_all_selectors(mock_browser)

    assert event.is_set()


@pytest.mark.asyncio
async def test_auto_stop_not_triggered_below_threshold(mock_selector_manager, mock_notifier):
    """Test that shutdown_event is NOT set when failure ratio is below threshold."""
    event = asyncio.Event()
    checker = SelectorHealthCheck(
        mock_selector_manager,
        mock_notifier,
        shutdown_event=event,
        critical_failure_threshold=0.5,
    )

    # 2 invalid, 4 valid out of 6 critical selectors (33% < 50% threshold)
    invalid_result = {"valid": False, "fallback_used": False, "error": "Not found"}
    valid_result = {"valid": True, "fallback_used": False, "error": None}
    side_effects = [invalid_result] * 2 + [valid_result] * 4

    mock_page = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    with patch.object(checker, "validate_selector", new_callable=AsyncMock) as mock_validate:
        mock_validate.side_effect = [
            {**r, "selector_path": f"sel.{i}", "found": r["valid"], "timestamp": "2026-01-01T00:00:00+00:00"}
            for i, r in enumerate(side_effects)
        ]
        await checker.check_all_selectors(mock_browser)

    assert not event.is_set()


@pytest.mark.asyncio
async def test_auto_stop_not_triggered_without_shutdown_event(mock_selector_manager, mock_notifier):
    """Test backward compat: no crash when shutdown_event is None."""
    checker = SelectorHealthCheck(
        mock_selector_manager,
        mock_notifier,
        shutdown_event=None,
        critical_failure_threshold=0.5,
    )

    # All 6 selectors invalid — would trigger stop if shutdown_event were set
    invalid_result = {"valid": False, "fallback_used": False, "error": "Not found"}

    mock_page = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    with patch.object(checker, "validate_selector", new_callable=AsyncMock) as mock_validate:
        mock_validate.side_effect = [
            {**invalid_result, "selector_path": f"sel.{i}", "found": False, "timestamp": "2026-01-01T00:00:00+00:00"}
            for i in range(6)
        ]
        # Should not raise even with no shutdown_event
        await checker.check_all_selectors(mock_browser)

    assert checker.shutdown_event is None


@pytest.mark.asyncio
async def test_auto_stop_sends_stop_alert(mock_selector_manager, mock_notifier):
    """Test that the AUTO-STOP alert message is sent via notifier when threshold exceeded."""
    event = asyncio.Event()
    checker = SelectorHealthCheck(
        mock_selector_manager,
        mock_notifier,
        shutdown_event=event,
        critical_failure_threshold=0.5,
    )

    # All 6 selectors invalid → triggers auto-stop alert
    invalid_result = {"valid": False, "fallback_used": False, "error": "Not found"}
    mock_page = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    with patch.object(checker, "validate_selector", new_callable=AsyncMock) as mock_validate:
        mock_validate.side_effect = [
            {**invalid_result, "selector_path": f"sel.{i}", "found": False, "timestamp": "2026-01-01T00:00:00+00:00"}
            for i in range(6)
        ]
        await checker.check_all_selectors(mock_browser)

    # Verify AUTO-STOP message was sent (among possibly multiple send_notification calls)
    all_messages = [
        call_args[0][1]
        for call_args in mock_notifier.send_notification.call_args_list
    ]
    assert any("AUTO-STOP" in msg for msg in all_messages)


@pytest.mark.asyncio
async def test_run_continuous_respects_shutdown_event(mock_selector_manager):
    """Test that run_continuous exits when shutdown_event is pre-set."""
    event = asyncio.Event()
    event.set()  # Pre-set to simulate already-triggered shutdown

    checker = SelectorHealthCheck(mock_selector_manager, shutdown_event=event)

    mock_browser = MagicMock()
    with patch.object(checker, "check_all_selectors", new_callable=AsyncMock) as mock_check:
        await checker.run_continuous(mock_browser)
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_auto_stop_with_custom_threshold(mock_selector_manager):
    """Test that only 100% failure triggers stop when threshold=1.0."""
    event = asyncio.Event()
    checker = SelectorHealthCheck(
        mock_selector_manager,
        shutdown_event=event,
        critical_failure_threshold=1.0,
    )

    invalid_result = {"valid": False, "fallback_used": False, "error": "Not found"}
    valid_result = {"valid": True, "fallback_used": False, "error": None}

    mock_page = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    # 50% failure — should NOT trigger stop (3 invalid, 3 valid)
    with patch.object(checker, "validate_selector", new_callable=AsyncMock) as mock_validate:
        mock_validate.side_effect = [
            {**r, "selector_path": f"sel.{i}", "found": r["valid"], "timestamp": "2026-01-01T00:00:00+00:00"}
            for i, r in enumerate([invalid_result] * 3 + [valid_result] * 3)
        ]
        await checker.check_all_selectors(mock_browser)
    assert not event.is_set()

    # 100% failure — SHOULD trigger stop (all 6 invalid)
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    with patch.object(checker, "validate_selector", new_callable=AsyncMock) as mock_validate:
        mock_validate.side_effect = [
            {**invalid_result, "selector_path": f"sel.{i}", "found": False, "timestamp": "2026-01-01T00:00:00+00:00"}
            for i in range(6)
        ]
        await checker.check_all_selectors(mock_browser)
    assert event.is_set()
