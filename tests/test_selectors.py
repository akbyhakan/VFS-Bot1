"""Tests for selector loading and fallback functionality."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from src.core.exceptions import SelectorNotFoundError
from src.utils.selectors import SelectorManager, get_selector_manager


@pytest.fixture
def temp_selectors_file(tmp_path):
    """Create a temporary selectors file."""
    selectors_content = {
        "version": "test-1.0",
        "login": {
            "email_input": {
                "primary": "input#email",
                "fallbacks": ["input[type='email']", "input[name='email']"],
            },
            "password_input": {
                "primary": "input#password",
                "fallbacks": ["input[type='password']"],
            },
            "submit_button": "button[type='submit']",
        },
        "appointment": {
            "centre_dropdown": {
                "primary": "select#centres",
                "fallbacks": ["select[name='centre']"],
            },
        },
    }

    selectors_file = tmp_path / "selectors.yaml"
    with open(selectors_file, "w") as f:
        yaml.dump(selectors_content, f)

    return selectors_file


def test_selector_manager_load_file(temp_selectors_file):
    """Test loading selectors from YAML file."""
    manager = SelectorManager(str(temp_selectors_file))

    assert manager._selectors["version"] == "test-1.0"
    assert "login" in manager._selectors
    assert "appointment" in manager._selectors


def test_selector_manager_get_primary(temp_selectors_file):
    """Test getting primary selector."""
    manager = SelectorManager(str(temp_selectors_file))

    # Test selector with primary/fallbacks structure
    selector = manager.get("login.email_input")
    assert selector == "input#email"

    # Test simple string selector
    selector = manager.get("login.submit_button")
    assert selector == "button[type='submit']"


def test_selector_manager_get_fallbacks(temp_selectors_file):
    """Test getting fallback selectors."""
    manager = SelectorManager(str(temp_selectors_file))

    fallbacks = manager.get_fallbacks("login.email_input")
    assert len(fallbacks) == 2
    assert "input[type='email']" in fallbacks
    assert "input[name='email']" in fallbacks


def test_selector_manager_get_with_fallback(temp_selectors_file):
    """Test getting selector with fallbacks."""
    manager = SelectorManager(str(temp_selectors_file))

    selectors = manager.get_with_fallback("login.email_input")
    assert len(selectors) == 3
    assert selectors[0] == "input#email"  # Primary first
    assert "input[type='email']" in selectors
    assert "input[name='email']" in selectors


def test_selector_manager_get_nonexistent(temp_selectors_file):
    """Test getting non-existent selector."""
    manager = SelectorManager(str(temp_selectors_file))

    selector = manager.get("nonexistent.selector", default="default-value")
    assert selector == "default-value"


def test_selector_manager_get_fallbacks_nonexistent(temp_selectors_file):
    """Test getting fallbacks for non-existent selector."""
    manager = SelectorManager(str(temp_selectors_file))

    fallbacks = manager.get_fallbacks("nonexistent.selector")
    assert fallbacks == []


@pytest.mark.asyncio
async def test_wait_for_selector_success(temp_selectors_file):
    """Test wait_for_selector with successful match."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.locator = lambda x: f"locator({x})"

    locator = await manager.wait_for_selector(mock_page, "login.email_input")

    assert locator is not None
    # Should try primary selector first
    mock_page.wait_for_selector.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_selector_fallback(temp_selectors_file):
    """Test wait_for_selector uses fallback when primary fails."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()

    # Primary fails, fallback succeeds
    call_count = 0

    async def mock_wait(selector, timeout=10000):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Primary selector failed")
        # Second call succeeds
        return None

    mock_page.wait_for_selector = mock_wait
    mock_page.locator = lambda x: f"locator({x})"

    locator = await manager.wait_for_selector(mock_page, "login.email_input")

    assert locator is not None
    assert call_count == 2  # Primary + first fallback


@pytest.mark.asyncio
async def test_wait_for_selector_all_fail(temp_selectors_file):
    """Test wait_for_selector raises exception when all selectors fail."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Selector not found"))

    with pytest.raises(SelectorNotFoundError) as exc_info:
        await manager.wait_for_selector(mock_page, "login.email_input")

    assert exc_info.value.selector_name == "login.email_input"
    assert len(exc_info.value.tried_selectors) == 3  # Primary + 2 fallbacks


def test_selector_manager_reload(temp_selectors_file):
    """Test reloading selectors."""
    manager = SelectorManager(str(temp_selectors_file))

    original_version = manager._selectors["version"]
    assert original_version == "test-1.0"

    # Modify the file
    with open(temp_selectors_file, "r") as f:
        content = yaml.safe_load(f)
    content["version"] = "test-2.0"
    with open(temp_selectors_file, "w") as f:
        yaml.dump(content, f)

    # Reload
    manager.reload()

    assert manager._selectors["version"] == "test-2.0"


def test_selector_manager_default_on_missing_file():
    """Test that default selectors are used when file is missing."""
    manager = SelectorManager("nonexistent-file.yaml")

    # Should have loaded default selectors
    assert "login" in manager._selectors
    assert manager._selectors["version"] == "default"


def test_get_selector_manager_singleton():
    """Test that get_selector_manager returns singleton instance."""
    manager1 = get_selector_manager()
    manager2 = get_selector_manager()

    assert manager1 is manager2


@pytest.mark.asyncio
async def test_wait_for_selector_uses_visible_state(temp_selectors_file):
    """Test that wait_for_selector passes the correct timeout parameter to page.wait_for_selector."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.locator = lambda x: f"locator({x})"

    await manager.wait_for_selector(mock_page, "login.email_input", timeout=5000)

    # Verify wait_for_selector was called with timeout
    call_args = mock_page.wait_for_selector.call_args
    assert call_args is not None
    # Check keyword arguments
    assert call_args.kwargs["timeout"] == 5000
