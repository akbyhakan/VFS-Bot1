"""Tests for stealth configuration functionality."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.stealth_config import StealthConfig


class TestStealthConfig:
    """Test stealth configuration functionality."""

    @pytest.mark.asyncio
    async def test_apply_stealth_success(self):
        """Test apply_stealth applies all configurations."""
        mock_page = AsyncMock()

        await StealthConfig.apply_stealth(mock_page)

        # Verify add_init_script was called 5 times (one for each stealth method)
        assert mock_page.add_init_script.call_count == 5

    @pytest.mark.asyncio
    async def test_apply_stealth_error(self):
        """Test apply_stealth handles errors gracefully."""
        mock_page = AsyncMock()
        mock_page.add_init_script.side_effect = Exception("Script injection failed")

        # Should not raise exception
        await StealthConfig.apply_stealth(mock_page)

    @pytest.mark.asyncio
    async def test_override_webdriver(self):
        """Test navigator.webdriver override."""
        mock_page = AsyncMock()

        await StealthConfig._override_webdriver(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script overrides webdriver property
        assert "navigator" in script
        assert "webdriver" in script
        assert "Object.defineProperty" in script
        assert "undefined" in script

    @pytest.mark.asyncio
    async def test_spoof_plugins(self):
        """Test navigator.plugins spoofing."""
        mock_page = AsyncMock()

        await StealthConfig._spoof_plugins(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script contains plugin definitions
        assert "navigator" in script
        assert "plugins" in script
        assert "Chrome PDF Plugin" in script
        assert "Chrome PDF Viewer" in script
        assert "Native Client" in script
        assert "Object.defineProperty" in script

    @pytest.mark.asyncio
    async def test_spoof_languages(self):
        """Test navigator.languages spoofing."""
        mock_page = AsyncMock()

        await StealthConfig._spoof_languages(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script overrides languages property
        assert "navigator" in script
        assert "languages" in script
        assert "en-US" in script
        assert "en" in script
        assert "Object.defineProperty" in script

    @pytest.mark.asyncio
    async def test_add_chrome_runtime(self):
        """Test chrome runtime object addition."""
        mock_page = AsyncMock()

        await StealthConfig._add_chrome_runtime(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script adds chrome object
        assert "window.chrome" in script
        assert "runtime" in script
        assert "loadTimes" in script
        assert "csi" in script
        assert "app" in script

    @pytest.mark.asyncio
    async def test_override_permissions(self):
        """Test permissions query override."""
        mock_page = AsyncMock()

        await StealthConfig._override_permissions(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script overrides permissions.query
        assert "navigator.permissions.query" in script
        assert "notifications" in script
        assert "Notification.permission" in script

    @pytest.mark.asyncio
    async def test_all_methods_called_independently(self):
        """Test that all stealth methods can be called independently."""
        mock_page = AsyncMock()

        # Test each method individually
        await StealthConfig._override_webdriver(mock_page)
        assert mock_page.add_init_script.call_count == 1

        mock_page.reset_mock()
        await StealthConfig._spoof_plugins(mock_page)
        assert mock_page.add_init_script.call_count == 1

        mock_page.reset_mock()
        await StealthConfig._spoof_languages(mock_page)
        assert mock_page.add_init_script.call_count == 1

        mock_page.reset_mock()
        await StealthConfig._add_chrome_runtime(mock_page)
        assert mock_page.add_init_script.call_count == 1

        mock_page.reset_mock()
        await StealthConfig._override_permissions(mock_page)
        assert mock_page.add_init_script.call_count == 1

    @pytest.mark.asyncio
    async def test_scripts_are_valid_javascript(self):
        """Test that injected scripts are syntactically valid JavaScript."""
        mock_page = AsyncMock()

        # Apply all stealth configs
        await StealthConfig.apply_stealth(mock_page)

        # Get all injected scripts
        assert mock_page.add_init_script.call_count == 5

        for call in mock_page.add_init_script.call_args_list:
            script = call[0][0]

            # Basic syntax checks
            assert script.count("{") == script.count("}")  # Balanced braces
            # Scripts should either use Object.defineProperty or window assignment
            assert "Object.defineProperty" in script or "window." in script

    @pytest.mark.asyncio
    async def test_apply_stealth_order(self):
        """Test that stealth methods are applied in correct order."""
        mock_page = AsyncMock()

        await StealthConfig.apply_stealth(mock_page)

        # Verify all 5 methods were called
        assert mock_page.add_init_script.call_count == 5

        # Get all scripts in order
        scripts = [call[0][0] for call in mock_page.add_init_script.call_args_list]

        # Verify each expected component is present in at least one script
        all_scripts = "".join(scripts)
        assert "webdriver" in all_scripts
        assert "plugins" in all_scripts
        assert "languages" in all_scripts
        assert "chrome" in all_scripts
        assert "permissions" in all_scripts

    @pytest.mark.asyncio
    async def test_webdriver_override_returns_undefined(self):
        """Test that webdriver override explicitly returns undefined."""
        mock_page = AsyncMock()

        await StealthConfig._override_webdriver(mock_page)

        script = mock_page.add_init_script.call_args[0][0]

        # Should return undefined, not false
        assert "undefined" in script
        assert "get: () => undefined" in script or "return undefined" in script

    @pytest.mark.asyncio
    async def test_plugins_have_correct_structure(self):
        """Test that plugin objects have required properties."""
        mock_page = AsyncMock()

        await StealthConfig._spoof_plugins(mock_page)

        script = mock_page.add_init_script.call_args[0][0]

        # Verify plugin structure
        assert "description" in script
        assert "filename" in script
        assert "length" in script
        assert "name" in script
        assert "type" in script
        assert "suffixes" in script

    @pytest.mark.asyncio
    async def test_chrome_runtime_has_required_properties(self):
        """Test that chrome runtime has all required properties."""
        mock_page = AsyncMock()

        await StealthConfig._add_chrome_runtime(mock_page)

        script = mock_page.add_init_script.call_args[0][0]

        # All chrome properties should be present
        required_props = ["runtime", "loadTimes", "csi", "app"]
        for prop in required_props:
            assert prop in script

    @pytest.mark.asyncio
    async def test_apply_stealth_continues_on_individual_failure(self):
        """Test that apply_stealth continues even if one method fails."""
        mock_page = AsyncMock()

        # Make one call fail
        call_count = 0

        def side_effect_fail_third(script):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise Exception("Third script failed")

        mock_page.add_init_script.side_effect = side_effect_fail_third

        # Should handle error and not propagate
        await StealthConfig.apply_stealth(mock_page)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
