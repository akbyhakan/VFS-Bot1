"""Extended tests for src/utils/helpers.py - aiming for 100% coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import Page

from src.utils.helpers import (
    smart_fill,
    smart_click,
    wait_for_selector_smart,
    random_delay,
    safe_navigate,
    safe_screenshot,
)


@pytest.mark.asyncio
class TestSmartFill:
    """Tests for smart_fill function."""

    async def test_smart_fill_basic(self):
        """Test basic fill without human simulation."""
        page = AsyncMock(spec=Page)
        page.fill = AsyncMock()

        await smart_fill(page, "#username", "testuser")

        page.fill.assert_called_once_with("#username", "testuser")

    async def test_smart_fill_with_delay(self):
        """Test fill with delay."""
        page = AsyncMock(spec=Page)
        page.fill = AsyncMock()

        await smart_fill(page, "#username", "testuser", delay=0.01)

        page.fill.assert_called_once_with("#username", "testuser")

    async def test_smart_fill_with_human_sim(self):
        """Test fill with human simulation."""
        page = AsyncMock(spec=Page)
        human_sim = MagicMock()
        human_sim.human_type = AsyncMock()

        await smart_fill(page, "#username", "testuser", human_sim=human_sim)

        human_sim.human_type.assert_called_once_with(page, "#username", "testuser")

    async def test_smart_fill_error(self):
        """Test fill with error handling."""
        page = AsyncMock(spec=Page)
        page.fill = AsyncMock(side_effect=Exception("Fill failed"))

        with pytest.raises(Exception, match="Fill failed"):
            await smart_fill(page, "#username", "testuser")


@pytest.mark.asyncio
class TestSmartClick:
    """Tests for smart_click function."""

    async def test_smart_click_basic(self):
        """Test basic click without human simulation."""
        page = AsyncMock(spec=Page)
        page.click = AsyncMock()

        await smart_click(page, "#login-button")

        page.click.assert_called_once_with("#login-button")

    async def test_smart_click_with_delay(self):
        """Test click with delay."""
        page = AsyncMock(spec=Page)
        page.click = AsyncMock()

        await smart_click(page, "#login-button", delay=0.01)

        page.click.assert_called_once_with("#login-button")

    async def test_smart_click_with_human_sim(self):
        """Test click with human simulation."""
        page = AsyncMock(spec=Page)
        human_sim = MagicMock()
        human_sim.human_click = AsyncMock()

        await smart_click(page, "#login-button", human_sim=human_sim)

        human_sim.human_click.assert_called_once_with(page, "#login-button")

    async def test_smart_click_error(self):
        """Test click with error handling."""
        page = AsyncMock(spec=Page)
        page.click = AsyncMock(side_effect=Exception("Click failed"))

        with pytest.raises(Exception, match="Click failed"):
            await smart_click(page, "#login-button")


@pytest.mark.asyncio
class TestWaitForSelectorSmart:
    """Tests for wait_for_selector_smart function."""

    async def test_wait_for_selector_smart_default(self):
        """Test wait for selector with default timeout."""
        page = AsyncMock(spec=Page)
        page.wait_for_selector = AsyncMock()

        await wait_for_selector_smart(page, "#element")

        assert page.wait_for_selector.called
        call_args = page.wait_for_selector.call_args
        assert call_args[0][0] == "#element"
        assert call_args[1]["state"] == "visible"

    async def test_wait_for_selector_smart_custom_timeout(self):
        """Test wait for selector with custom timeout."""
        page = AsyncMock(spec=Page)
        page.wait_for_selector = AsyncMock()

        await wait_for_selector_smart(page, "#element", timeout=5000, state="attached")

        assert page.wait_for_selector.called
        call_args = page.wait_for_selector.call_args
        assert call_args[0][0] == "#element"
        assert call_args[1]["timeout"] == 5000
        assert call_args[1]["state"] == "attached"

    async def test_wait_for_selector_smart_error(self):
        """Test wait for selector with error."""
        page = AsyncMock(spec=Page)
        page.wait_for_selector = AsyncMock(side_effect=Exception("Selector not found"))

        with pytest.raises(Exception, match="Selector not found"):
            await wait_for_selector_smart(page, "#element")


@pytest.mark.asyncio
class TestRandomDelay:
    """Tests for random_delay function."""

    async def test_random_delay_default(self):
        """Test random delay with default values."""
        # Should not raise any exceptions
        await random_delay()

    async def test_random_delay_custom(self):
        """Test random delay with custom values."""
        # Should not raise any exceptions
        await random_delay(min_seconds=0.01, max_seconds=0.02)


@pytest.mark.asyncio
class TestSafeNavigate:
    """Tests for safe_navigate function."""

    async def test_safe_navigate_success(self):
        """Test successful navigation."""
        page = AsyncMock(spec=Page)
        page.goto = AsyncMock()

        result = await safe_navigate(page, "https://example.com")

        assert result is True
        page.goto.assert_called_once()

    async def test_safe_navigate_error(self):
        """Test navigation with error."""
        page = AsyncMock(spec=Page)
        page.goto = AsyncMock(side_effect=Exception("Navigation failed"))

        result = await safe_navigate(page, "https://example.com")

        assert result is False

    async def test_safe_navigate_custom_wait(self):
        """Test navigation with custom wait condition."""
        page = AsyncMock(spec=Page)
        page.goto = AsyncMock()

        result = await safe_navigate(page, "https://example.com", wait_until="load", timeout=5000)

        assert result is True
        call_args = page.goto.call_args
        assert call_args[1]["wait_until"] == "load"
        assert call_args[1]["timeout"] == 5000


@pytest.mark.asyncio
class TestSafeScreenshot:
    """Tests for safe_screenshot function."""

    async def test_safe_screenshot_success(self):
        """Test successful screenshot."""
        page = AsyncMock(spec=Page)
        page.screenshot = AsyncMock()

        result = await safe_screenshot(page, "/tmp/test.png")

        assert result is True
        page.screenshot.assert_called_once()

    async def test_safe_screenshot_error(self):
        """Test screenshot with error."""
        page = AsyncMock(spec=Page)
        page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))

        result = await safe_screenshot(page, "/tmp/test.png")

        assert result is False

    async def test_safe_screenshot_custom_params(self):
        """Test screenshot with custom parameters."""
        page = AsyncMock(spec=Page)
        page.screenshot = AsyncMock()

        result = await safe_screenshot(page, "/tmp/test.png", full_page=False)

        assert result is True
        call_args = page.screenshot.call_args
        assert call_args[1]["full_page"] is False
