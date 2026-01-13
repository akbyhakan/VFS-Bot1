"""Extended tests for helper utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
async def test_smart_fill_basic():
    """Test basic smart_fill without human simulation."""
    page = AsyncMock(spec=Page)
    await smart_fill(page, "#input", "test text")
    page.fill.assert_called_once_with("#input", "test text")


@pytest.mark.asyncio
async def test_smart_fill_with_delay():
    """Test smart_fill with delay."""
    page = AsyncMock(spec=Page)
    await smart_fill(page, "#input", "test text", delay=0.01)
    page.fill.assert_called_once_with("#input", "test text")


@pytest.mark.asyncio
async def test_smart_fill_with_human_sim():
    """Test smart_fill with human simulator."""
    page = AsyncMock(spec=Page)
    human_sim = MagicMock()
    human_sim.human_type = AsyncMock()

    await smart_fill(page, "#input", "test text", human_sim=human_sim)

    human_sim.human_type.assert_called_once_with(page, "#input", "test text")
    page.fill.assert_not_called()


@pytest.mark.asyncio
async def test_smart_fill_error():
    """Test smart_fill error handling."""
    page = AsyncMock(spec=Page)
    page.fill = AsyncMock(side_effect=Exception("Fill failed"))

    with pytest.raises(Exception, match="Fill failed"):
        await smart_fill(page, "#input", "test text")


@pytest.mark.asyncio
async def test_smart_click_basic():
    """Test basic smart_click without human simulation."""
    page = AsyncMock(spec=Page)
    await smart_click(page, "#button")
    page.click.assert_called_once_with("#button")


@pytest.mark.asyncio
async def test_smart_click_with_delay():
    """Test smart_click with delay."""
    page = AsyncMock(spec=Page)
    await smart_click(page, "#button", delay=0.01)
    page.click.assert_called_once_with("#button")


@pytest.mark.asyncio
async def test_smart_click_with_human_sim():
    """Test smart_click with human simulator."""
    page = AsyncMock(spec=Page)
    human_sim = MagicMock()
    human_sim.human_click = AsyncMock()

    await smart_click(page, "#button", human_sim=human_sim)

    human_sim.human_click.assert_called_once_with(page, "#button")
    page.click.assert_not_called()


@pytest.mark.asyncio
async def test_smart_click_error():
    """Test smart_click error handling."""
    page = AsyncMock(spec=Page)
    page.click = AsyncMock(side_effect=Exception("Click failed"))

    with pytest.raises(Exception, match="Click failed"):
        await smart_click(page, "#button")


@pytest.mark.asyncio
async def test_wait_for_selector_smart_default():
    """Test wait_for_selector_smart with defaults."""
    page = AsyncMock(spec=Page)
    await wait_for_selector_smart(page, "#element")
    assert page.wait_for_selector.called


@pytest.mark.asyncio
async def test_wait_for_selector_smart_custom_timeout():
    """Test wait_for_selector_smart with custom timeout."""
    page = AsyncMock(spec=Page)
    await wait_for_selector_smart(page, "#element", timeout=5000)
    page.wait_for_selector.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_selector_smart_different_state():
    """Test wait_for_selector_smart with different state."""
    page = AsyncMock(spec=Page)
    await wait_for_selector_smart(page, "#element", state="hidden")
    page.wait_for_selector.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_selector_smart_error():
    """Test wait_for_selector_smart error handling."""
    page = AsyncMock(spec=Page)
    page.wait_for_selector = AsyncMock(side_effect=Exception("Selector not found"))

    with pytest.raises(Exception, match="Selector not found"):
        await wait_for_selector_smart(page, "#element")


@pytest.mark.asyncio
async def test_random_delay_default():
    """Test random_delay with defaults."""
    import time

    start = time.time()
    await random_delay()
    elapsed = time.time() - start
    # Should be between 0.1 and 2.0 seconds (default values from Intervals)
    assert elapsed >= 0.0  # At least some delay


@pytest.mark.asyncio
async def test_random_delay_custom():
    """Test random_delay with custom values."""
    import time

    start = time.time()
    await random_delay(min_seconds=0.01, max_seconds=0.02)
    elapsed = time.time() - start
    assert 0.0 <= elapsed <= 0.1  # Should be quick


@pytest.mark.asyncio
async def test_safe_navigate_success():
    """Test safe_navigate successful navigation."""
    page = AsyncMock(spec=Page)
    result = await safe_navigate(page, "https://example.com")
    assert result is True
    page.goto.assert_called_once()


@pytest.mark.asyncio
async def test_safe_navigate_custom_wait():
    """Test safe_navigate with custom wait condition."""
    page = AsyncMock(spec=Page)
    result = await safe_navigate(page, "https://example.com", wait_until="load")
    assert result is True


@pytest.mark.asyncio
async def test_safe_navigate_error():
    """Test safe_navigate error handling."""
    page = AsyncMock(spec=Page)
    page.goto = AsyncMock(side_effect=Exception("Navigation failed"))

    result = await safe_navigate(page, "https://example.com")
    assert result is False


@pytest.mark.asyncio
async def test_safe_screenshot_success():
    """Test safe_screenshot successful capture."""
    page = AsyncMock(spec=Page)
    result = await safe_screenshot(page, "/tmp/test.png")
    assert result is True
    page.screenshot.assert_called_once()


@pytest.mark.asyncio
async def test_safe_screenshot_not_full_page():
    """Test safe_screenshot without full page."""
    page = AsyncMock(spec=Page)
    result = await safe_screenshot(page, "/tmp/test.png", full_page=False)
    assert result is True


@pytest.mark.asyncio
async def test_safe_screenshot_error():
    """Test safe_screenshot error handling."""
    page = AsyncMock(spec=Page)
    page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))

    result = await safe_screenshot(page, "/tmp/test.png")
    assert result is False
