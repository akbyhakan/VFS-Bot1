"""Tests for stealth configuration."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.stealth_config import StealthConfig


@pytest.fixture
def mock_page():
    """Mock Playwright page object."""
    page = AsyncMock()
    page.add_init_script = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_apply_stealth_all_methods(mock_page):
    """Test that apply_stealth calls all stealth methods."""
    await StealthConfig.apply_stealth(mock_page)
    # Should call add_init_script for each stealth method
    assert mock_page.add_init_script.call_count >= 5


@pytest.mark.asyncio
async def test_apply_stealth_error_handling():
    """Test apply_stealth error handling."""
    error_page = AsyncMock()
    error_page.add_init_script = AsyncMock(side_effect=Exception("Script injection failed"))

    # Should not raise exception
    await StealthConfig.apply_stealth(error_page)


@pytest.mark.asyncio
async def test_override_webdriver(mock_page):
    """Test webdriver override."""
    await StealthConfig._override_webdriver(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains webdriver override
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "navigator" in call_args
    assert "webdriver" in call_args
    assert "undefined" in call_args


@pytest.mark.asyncio
async def test_spoof_plugins(mock_page):
    """Test plugin spoofing."""
    await StealthConfig._spoof_plugins(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains plugin definitions
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "navigator" in call_args
    assert "plugins" in call_args
    assert "Chrome PDF Plugin" in call_args
    assert "Native Client" in call_args


@pytest.mark.asyncio
async def test_spoof_languages(mock_page):
    """Test language spoofing."""
    await StealthConfig._spoof_languages(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains language settings
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "navigator" in call_args
    assert "languages" in call_args
    assert "en-US" in call_args
    assert "en" in call_args


@pytest.mark.asyncio
async def test_add_chrome_runtime(mock_page):
    """Test Chrome runtime addition."""
    await StealthConfig._add_chrome_runtime(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains chrome object
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "window.chrome" in call_args
    assert "runtime" in call_args
    assert "loadTimes" in call_args
    assert "csi" in call_args


@pytest.mark.asyncio
async def test_override_permissions(mock_page):
    """Test permissions override."""
    await StealthConfig._override_permissions(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains permissions override
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "navigator.permissions" in call_args
    assert "query" in call_args
    assert "notifications" in call_args


@pytest.mark.asyncio
async def test_stealth_scripts_are_valid_javascript(mock_page):
    """Test that all stealth scripts are valid JavaScript syntax."""
    await StealthConfig.apply_stealth(mock_page)

    # All calls should complete without syntax errors
    for call in mock_page.add_init_script.call_args_list:
        script = call[0][0]
        # Basic validation that it looks like JavaScript
        assert "{" in script or "(" in script
        assert ";" in script or "}" in script


@pytest.mark.asyncio
async def test_multiple_apply_stealth_calls(mock_page):
    """Test that apply_stealth can be called multiple times."""
    await StealthConfig.apply_stealth(mock_page)
    first_call_count = mock_page.add_init_script.call_count

    await StealthConfig.apply_stealth(mock_page)
    second_call_count = mock_page.add_init_script.call_count

    # Should double the number of calls
    assert second_call_count == first_call_count * 2


@pytest.mark.asyncio
async def test_stealth_config_static_methods():
    """Test that all stealth methods are static."""
    # All methods should be callable as class methods
    assert callable(StealthConfig.apply_stealth)
    assert callable(StealthConfig._override_webdriver)
    assert callable(StealthConfig._spoof_plugins)
    assert callable(StealthConfig._spoof_languages)
    assert callable(StealthConfig._add_chrome_runtime)
    assert callable(StealthConfig._override_permissions)


@pytest.mark.asyncio
async def test_webdriver_override_script_syntax(mock_page):
    """Test webdriver override script syntax."""
    await StealthConfig._override_webdriver(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should use Object.defineProperty
    assert "Object.defineProperty" in script
    assert "configurable: true" in script


@pytest.mark.asyncio
async def test_plugins_array_structure(mock_page):
    """Test plugins array has correct structure."""
    await StealthConfig._spoof_plugins(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should define plugins as array
    assert "[" in script
    assert "]" in script
    assert "get:" in script or "get :" in script


@pytest.mark.asyncio
async def test_chrome_runtime_object_properties(mock_page):
    """Test chrome runtime has all required properties."""
    await StealthConfig._add_chrome_runtime(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # All chrome properties should be present
    required_props = ["runtime", "loadTimes", "csi", "app"]
    for prop in required_props:
        assert prop in script
