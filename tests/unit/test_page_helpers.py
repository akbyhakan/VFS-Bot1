"""Tests for page_helpers module."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import Page

from src.utils.page_helpers import wait_for_overlay_hidden


@pytest.mark.asyncio
async def test_wait_for_overlay_hidden_single_selector():
    """Test waiting for a single overlay to be hidden."""
    # Create mock page
    page = AsyncMock(spec=Page)
    
    # Create mock locator with overlay present
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.wait_for = AsyncMock()
    page.locator.return_value = mock_locator
    
    # Call the function
    selectors = [".loading-overlay"]
    await wait_for_overlay_hidden(page, selectors, timeout=5000)
    
    # Verify locator was called with correct selector
    page.locator.assert_called_once_with(".loading-overlay")
    
    # Verify wait_for was called with hidden state
    mock_locator.wait_for.assert_called_once_with(state="hidden", timeout=5000)


@pytest.mark.asyncio
async def test_wait_for_overlay_hidden_multiple_selectors():
    """Test waiting for overlay with multiple selectors tries each."""
    # Create mock page
    page = AsyncMock(spec=Page)
    
    # First selector: no overlay
    mock_locator1 = AsyncMock()
    mock_locator1.count = AsyncMock(return_value=0)
    
    # Second selector: overlay present
    mock_locator2 = AsyncMock()
    mock_locator2.count = AsyncMock(return_value=1)
    mock_locator2.wait_for = AsyncMock()
    
    # Setup page.locator to return different mocks
    page.locator.side_effect = [mock_locator1, mock_locator2]
    
    # Call the function
    selectors = [".spinner", ".loading-overlay"]
    await wait_for_overlay_hidden(page, selectors, timeout=5000)
    
    # Verify both locators were created
    assert page.locator.call_count == 2
    
    # Verify wait_for was called on second locator
    mock_locator2.wait_for.assert_called_once_with(state="hidden", timeout=5000)


@pytest.mark.asyncio
async def test_wait_for_overlay_hidden_no_overlay():
    """Test that function completes successfully when no overlay is present."""
    # Create mock page
    page = AsyncMock(spec=Page)
    
    # Create mock locator with no overlay
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=0)
    page.locator.return_value = mock_locator
    
    # Call the function - should not raise exception
    selectors = [".loading-overlay"]
    await wait_for_overlay_hidden(page, selectors, timeout=5000)
    
    # Verify wait_for was NOT called since no overlay
    mock_locator.wait_for.assert_not_called()


@pytest.mark.asyncio
async def test_wait_for_overlay_hidden_timeout_exception():
    """Test that timeout exceptions are handled gracefully."""
    # Create mock page
    page = AsyncMock(spec=Page)
    
    # Create mock locator that times out
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.wait_for = AsyncMock(side_effect=Exception("Timeout"))
    page.locator.return_value = mock_locator
    
    # Call the function - should not raise exception
    selectors = [".loading-overlay"]
    await wait_for_overlay_hidden(page, selectors, timeout=5000)
    
    # Function should complete without raising


@pytest.mark.asyncio
async def test_wait_for_overlay_hidden_empty_selectors():
    """Test that function handles empty selector list gracefully."""
    # Create mock page
    page = AsyncMock(spec=Page)
    
    # Call the function with empty selectors
    selectors = []
    await wait_for_overlay_hidden(page, selectors, timeout=5000)
    
    # Should not call locator at all
    page.locator.assert_not_called()
