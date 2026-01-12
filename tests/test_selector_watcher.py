"""Tests for selector health monitoring."""

import pytest
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.selector_watcher import SelectorHealthCheck
from src.utils.selectors import SelectorManager


class TestSelectorHealthCheck:
    """Test selector health check functionality."""

    def test_init(self):
        """Test SelectorHealthCheck initialization."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        assert health_checker.selector_manager == sm
        assert health_checker.notifier is None
        assert health_checker.check_interval == 3600
        assert health_checker.health_status == {}
        assert health_checker.last_check is None

    def test_init_with_custom_interval(self):
        """Test SelectorHealthCheck with custom interval."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm, check_interval=1800)

        assert health_checker.check_interval == 1800

    def test_init_with_notifier(self):
        """Test SelectorHealthCheck initialization with notifier."""
        sm = SelectorManager()
        notifier = MagicMock()
        health_checker = SelectorHealthCheck(sm, notifier=notifier)

        assert health_checker.notifier == notifier

    @pytest.mark.asyncio
    async def test_validate_selector_not_found_in_config(self):
        """Test validate_selector when selector not in config."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)
        page = AsyncMock()

        result = await health_checker.validate_selector(page, "nonexistent.selector")

        assert result["valid"] is False
        assert result["found"] is False
        assert result["fallback_used"] is False
        assert result["error"] == "Selector not found in config"

    @pytest.mark.asyncio
    async def test_validate_selector_success(self):
        """Test validate_selector with successful primary selector."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)
        page = AsyncMock()
        mock_element = MagicMock()
        page.wait_for_selector.return_value = mock_element

        result = await health_checker.validate_selector(page, "login.email_input")

        assert result["valid"] is True
        assert result["found"] is True
        assert result["fallback_used"] is False
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_validate_selector_fallback_used(self):
        """Test validate_selector when primary fails but fallback works."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)
        page = AsyncMock()

        # First call fails (primary), second succeeds (fallback)
        mock_element = MagicMock()
        page.wait_for_selector.side_effect = [
            Exception("Primary failed"),
            mock_element,
        ]

        # Mock get_fallbacks to return a fallback
        sm.get_fallbacks = MagicMock(return_value=["#fallback-selector"])

        result = await health_checker.validate_selector(page, "login.email_input")

        assert result["valid"] is True
        assert result["found"] is True
        assert result["fallback_used"] is True
        assert result["fallback_index"] == 0

    @pytest.mark.asyncio
    async def test_validate_selector_all_fail(self):
        """Test validate_selector when all selectors fail."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)
        page = AsyncMock()
        page.wait_for_selector.side_effect = Exception("Selector not found")

        sm.get_fallbacks = MagicMock(return_value=["#fallback1", "#fallback2"])

        result = await health_checker.validate_selector(page, "login.email_input")

        assert result["valid"] is False
        assert result["found"] is False
        assert result["fallback_used"] is False
        assert "All selectors failed" in result["error"]

    @pytest.mark.asyncio
    async def test_send_alert_with_notifier(self):
        """Test _send_alert sends notification."""
        sm = SelectorManager()
        notifier = AsyncMock()
        health_checker = SelectorHealthCheck(sm, notifier=notifier)

        await health_checker._send_alert("Test message")

        notifier.send_notification.assert_awaited_once_with("Selector Alert", "Test message")

    @pytest.mark.asyncio
    async def test_send_alert_without_notifier(self):
        """Test _send_alert without notifier."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        # Should not raise exception
        await health_checker._send_alert("Test message")

    @pytest.mark.asyncio
    async def test_send_alert_exception(self):
        """Test _send_alert handles exceptions."""
        sm = SelectorManager()
        notifier = AsyncMock()
        notifier.send_notification.side_effect = Exception("Notification failed")
        health_checker = SelectorHealthCheck(sm, notifier=notifier)

        # Should not raise exception
        await health_checker._send_alert("Test message")

    @pytest.mark.asyncio
    async def test_send_critical_alert(self):
        """Test _send_critical_alert."""
        sm = SelectorManager()
        notifier = AsyncMock()
        health_checker = SelectorHealthCheck(sm, notifier=notifier)

        results = {
            "invalid": 2,
            "total": 5,
            "selectors": {
                "selector1": {"valid": False, "error": "Not found"},
                "selector2": {"valid": True},
                "selector3": {"valid": False, "error": "Timeout"},
            },
        }

        await health_checker._send_critical_alert(results)

        notifier.send_notification.assert_awaited_once()
        call_args = notifier.send_notification.call_args[0]
        assert "CRITICAL" in call_args[1]
        assert "2/5" in call_args[1]

    @pytest.mark.asyncio
    async def test_check_all_selectors(self):
        """Test check_all_selectors."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        browser = AsyncMock()
        page = AsyncMock()
        browser.new_page.return_value = page

        # Mock selector validation
        page.wait_for_selector.return_value = MagicMock()

        results = await health_checker.check_all_selectors(browser)

        assert "timestamp" in results
        assert "total" in results
        assert "valid" in results
        assert "invalid" in results
        assert "selectors" in results
        page.goto.assert_awaited_once()
        page.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_all_selectors_with_failures(self):
        """Test check_all_selectors with some failures."""
        sm = SelectorManager()
        notifier = AsyncMock()
        health_checker = SelectorHealthCheck(sm, notifier=notifier)

        browser = AsyncMock()
        page = AsyncMock()
        browser.new_page.return_value = page

        # Mock selector validation - some fail
        page.wait_for_selector.side_effect = [
            MagicMock(),  # First succeeds
            Exception("Failed"),  # Second fails
        ]

        sm.get_fallbacks = MagicMock(return_value=[])

        results = await health_checker.check_all_selectors(browser)

        assert results["invalid"] > 0
        # Critical alert should be sent
        assert notifier.send_notification.call_count >= 1

    @pytest.mark.asyncio
    async def test_check_all_selectors_exception(self):
        """Test check_all_selectors handles exceptions."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        browser = AsyncMock()
        page = AsyncMock()
        browser.new_page.return_value = page
        page.goto.side_effect = Exception("Navigation failed")

        results = await health_checker.check_all_selectors(browser)

        assert "error" in results
        page.close.assert_awaited_once()


class TestSelectorManager:
    """Test SelectorManager get_fallbacks method."""

    def test_get_fallbacks_with_list(self):
        """Test get_fallbacks returns fallback selectors."""
        sm = SelectorManager()
        fallbacks = sm.get_fallbacks("login.email_input")

        # Should return a list (may be empty or contain fallbacks)
        assert isinstance(fallbacks, list)

    def test_get_fallbacks_nonexistent(self):
        """Test get_fallbacks for nonexistent selector."""
        sm = SelectorManager()
        fallbacks = sm.get_fallbacks("nonexistent.selector")

        # Should return empty list for nonexistent selectors
        assert fallbacks == []
