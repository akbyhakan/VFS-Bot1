"""Tests for BrowserManager.close() cascade failure handling (Bug #3)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.bot.browser_manager import BrowserManager


@pytest.fixture
def test_config():
    """Minimal test configuration."""
    return {
        "bot": {
            "headless": True,
            "browser_restart_after_pages": 100,
        },
        "anti_detection": {
            "enabled": False,
        },
    }


class TestBrowserManagerClose:
    """Tests for BrowserManager.close() cascade failure handling."""

    @pytest.mark.asyncio
    async def test_close_normal(self, test_config):
        """Test normal close() with no errors."""
        manager = BrowserManager(test_config)
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        manager.context = mock_context
        manager.browser = mock_browser
        manager.playwright = mock_playwright

        await manager.close()

        mock_context.close.assert_awaited_once()
        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

    @pytest.mark.asyncio
    async def test_close_context_raises_still_cleans_browser_and_playwright(self, test_config):
        """When context.close() raises, browser and playwright must still be cleaned up."""
        manager = BrowserManager(test_config)

        mock_context = AsyncMock()
        mock_context.close.side_effect = RuntimeError("context error")
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()

        manager.context = mock_context
        manager.browser = mock_browser
        manager.playwright = mock_playwright

        await manager.close()

        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

    @pytest.mark.asyncio
    async def test_close_browser_raises_still_cleans_playwright(self, test_config):
        """When browser.close() raises, playwright must still be cleaned up."""
        manager = BrowserManager(test_config)

        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.close.side_effect = RuntimeError("browser error")
        mock_playwright = AsyncMock()

        manager.context = mock_context
        manager.browser = mock_browser
        manager.playwright = mock_playwright

        await manager.close()

        mock_context.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

    @pytest.mark.asyncio
    async def test_close_all_raise_all_refs_set_to_none(self, test_config):
        """When all three raise exceptions, all references must still be set to None."""
        manager = BrowserManager(test_config)

        mock_context = AsyncMock()
        mock_context.close.side_effect = RuntimeError("context error")
        mock_browser = AsyncMock()
        mock_browser.close.side_effect = RuntimeError("browser error")
        mock_playwright = AsyncMock()
        mock_playwright.stop.side_effect = RuntimeError("playwright error")

        manager.context = mock_context
        manager.browser = mock_browser
        manager.playwright = mock_playwright

        await manager.close()

        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

    @pytest.mark.asyncio
    async def test_close_when_already_none(self, test_config):
        """close() on a manager with no resources should not raise."""
        manager = BrowserManager(test_config)
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

        await manager.close()  # should not raise
