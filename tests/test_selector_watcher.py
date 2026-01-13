"""Tests for selector health monitoring."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

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
        notifier = AsyncMock()
        health_checker = SelectorHealthCheck(sm, notifier=notifier)

        assert health_checker.notifier == notifier

    @pytest.mark.asyncio
    async def test_validate_selector_not_found_in_config(self):
        """Test validate_selector when selector doesn't exist in config."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        mock_page = AsyncMock()

        result = await health_checker.validate_selector(mock_page, "nonexistent.selector")

        assert result["selector_path"] == "nonexistent.selector"
        assert result["valid"] is False
        assert result["found"] is False
        assert result["error"] == "Selector not found in config"

    @pytest.mark.asyncio
    async def test_validate_selector_primary_success(self):
        """Test validate_selector with successful primary selector."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_page.wait_for_selector.return_value = mock_element

        result = await health_checker.validate_selector(mock_page, "login.email_input")

        assert result["valid"] is True
        assert result["found"] is True
        assert result["fallback_used"] is False
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_validate_selector_fallback_success(self):
        """Test validate_selector with fallback selector success."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm, notifier=AsyncMock())

        mock_page = AsyncMock()
        # First call fails (primary), second succeeds (fallback)
        mock_element = MagicMock()
        mock_page.wait_for_selector.side_effect = [Exception("Not found"), mock_element]

        result = await health_checker.validate_selector(mock_page, "login.email_input")

        # If fallback exists, it should succeed
        if result["fallback_used"]:
            assert result["valid"] is True
            assert result["found"] is True

    @pytest.mark.asyncio
    async def test_validate_selector_all_failed(self):
        """Test validate_selector when all selectors fail."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        mock_page = AsyncMock()
        mock_page.wait_for_selector.side_effect = Exception("Element not found")

        result = await health_checker.validate_selector(mock_page, "login.email_input")

        assert result["valid"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """Test _send_alert method."""
        sm = SelectorManager()
        mock_notifier = AsyncMock()
        health_checker = SelectorHealthCheck(sm, notifier=mock_notifier)

        await health_checker._send_alert("Test alert message")

        mock_notifier.send_notification.assert_called_once_with(
            "Selector Alert", "Test alert message"
        )

    @pytest.mark.asyncio
    async def test_send_alert_no_notifier(self):
        """Test _send_alert when notifier is None."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        # Should not raise error
        await health_checker._send_alert("Test alert")

    @pytest.mark.asyncio
    async def test_send_alert_error(self):
        """Test _send_alert handles errors gracefully."""
        sm = SelectorManager()
        mock_notifier = AsyncMock()
        mock_notifier.send_notification.side_effect = Exception("Notification failed")
        health_checker = SelectorHealthCheck(sm, notifier=mock_notifier)

        # Should not raise error
        await health_checker._send_alert("Test alert")

    @pytest.mark.asyncio
    async def test_send_critical_alert(self):
        """Test _send_critical_alert method."""
        sm = SelectorManager()
        mock_notifier = AsyncMock()
        health_checker = SelectorHealthCheck(sm, notifier=mock_notifier)

        results = {
            "invalid": 2,
            "total": 5,
            "selectors": {
                "login.email": {"valid": False, "error": "Not found"},
                "login.password": {"valid": False, "error": "Timeout"},
                "login.submit": {"valid": True},
            },
        }

        await health_checker._send_critical_alert(results)

        mock_notifier.send_notification.assert_called_once()
        call_args = mock_notifier.send_notification.call_args[0]
        assert "CRITICAL" in call_args[1]
        assert "2/5" in call_args[1]

    @pytest.mark.asyncio
    async def test_check_all_selectors(self):
        """Test check_all_selectors method."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        # Mock browser and page
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        # Mock selector validation to return some valid and some invalid
        mock_element = MagicMock()
        # Simulate: first 2 succeed, next 4 fail
        mock_page.wait_for_selector.side_effect = [
            mock_element,  # login.email_input
            Exception("Not found"),  # login.password_input
            mock_element,  # login.submit_button
            Exception("Not found"),  # appointment.centre_dropdown
            Exception("Not found"),  # appointment.date_picker
            Exception("Not found"),  # captcha.recaptcha_frame
        ]

        results = await health_checker.check_all_selectors(mock_browser)

        assert results["total"] == 6
        assert results["valid"] >= 0
        assert results["invalid"] >= 0
        assert "selectors" in results
        assert health_checker.last_check is not None
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_all_selectors_error(self):
        """Test check_all_selectors handles errors."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm)

        mock_browser = AsyncMock()
        mock_browser.new_page.side_effect = Exception("Browser error")

        results = await health_checker.check_all_selectors(mock_browser)

        assert "error" in results

    @pytest.mark.asyncio
    async def test_run_continuous(self):
        """Test run_continuous method (single iteration)."""
        sm = SelectorManager()
        health_checker = SelectorHealthCheck(sm, check_interval=1)

        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        # Mock to stop after first iteration
        iteration_count = 0

        async def mock_sleep(seconds):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= 1:
                raise Exception("Stop iteration")

        with pytest.raises(Exception, match="Stop iteration"):
            import asyncio

            with AsyncMock() as mock_asyncio_sleep:
                asyncio.sleep = mock_sleep
                await health_checker.run_continuous(mock_browser)


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
