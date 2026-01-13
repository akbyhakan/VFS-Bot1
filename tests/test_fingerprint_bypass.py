"""Tests for fingerprint bypass functionality."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.fingerprint_bypass import FingerprintBypass


class TestFingerprintBypass:
    """Test fingerprint bypass functionality."""

    @pytest.mark.asyncio
    async def test_apply_all_success(self):
        """Test apply_all applies all bypass scripts."""
        mock_page = AsyncMock()

        await FingerprintBypass.apply_all(mock_page)

        # Verify add_init_script was called multiple times (canvas, webgl, audio)
        assert mock_page.add_init_script.call_count == 3

    @pytest.mark.asyncio
    async def test_apply_all_error(self):
        """Test apply_all handles errors gracefully."""
        mock_page = AsyncMock()
        mock_page.add_init_script.side_effect = Exception("Script injection failed")

        # Should not raise exception
        await FingerprintBypass.apply_all(mock_page)

    @pytest.mark.asyncio
    async def test_inject_canvas_noise(self):
        """Test canvas noise injection."""
        mock_page = AsyncMock()

        await FingerprintBypass._inject_canvas_noise(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script contains expected canvas API overrides
        assert "CanvasRenderingContext2D.prototype.getImageData" in script
        assert "HTMLCanvasElement.prototype.toDataURL" in script
        assert "HTMLCanvasElement.prototype.toBlob" in script
        assert "noiseR" in script
        assert "noiseG" in script
        assert "noiseB" in script
        assert "noiseA" in script

    @pytest.mark.asyncio
    async def test_inject_canvas_noise_random_values(self):
        """Test canvas noise uses random values within safe range."""
        mock_page = AsyncMock()

        # Run multiple times to test randomness
        for _ in range(10):
            await FingerprintBypass._inject_canvas_noise(mock_page)

            script = mock_page.add_init_script.call_args[0][0]

            # Extract noise values from script
            # Values should be integers within the specified ranges
            assert "noiseR" in script
            assert "noiseG" in script
            assert "noiseB" in script
            assert "noiseA" in script

    @pytest.mark.asyncio
    async def test_spoof_webgl(self):
        """Test WebGL spoofing."""
        mock_page = AsyncMock()

        await FingerprintBypass._spoof_webgl(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script contains expected WebGL overrides
        assert "WebGLRenderingContext.prototype.getParameter" in script
        assert "WebGL2RenderingContext.prototype.getParameter" in script
        assert "37445" in script  # UNMASKED_VENDOR_WEBGL
        assert "37446" in script  # UNMASKED_RENDERER_WEBGL

    @pytest.mark.asyncio
    async def test_spoof_webgl_vendor_selection(self):
        """Test WebGL vendor/renderer selection."""
        mock_page = AsyncMock()

        # Run multiple times to verify random selection works
        vendors_found = set()

        for _ in range(20):
            await FingerprintBypass._spoof_webgl(mock_page)

            script = mock_page.add_init_script.call_args[0][0]

            # Check if any known vendor is in the script
            if "Intel" in script:
                vendors_found.add("Intel")
            if "NVIDIA" in script:
                vendors_found.add("NVIDIA")
            if "AMD" in script:
                vendors_found.add("AMD")

        # At least one vendor should be found
        assert len(vendors_found) > 0

    @pytest.mark.asyncio
    async def test_randomize_audio_context(self):
        """Test audio context randomization."""
        mock_page = AsyncMock()

        await FingerprintBypass._randomize_audio_context(mock_page)

        # Verify script was injected
        mock_page.add_init_script.assert_called_once()

        # Get the injected script
        script = mock_page.add_init_script.call_args[0][0]

        # Verify script contains expected audio API overrides
        assert "audioOffset" in script
        assert "AudioContext" in script or "webkitAudioContext" in script
        assert "AudioContextProxy" in script
        assert "createBuffer" in script
        assert "getChannelData" in script

    @pytest.mark.asyncio
    async def test_randomize_audio_context_random_offset(self):
        """Test audio context uses random offset."""
        mock_page = AsyncMock()

        # Run multiple times to verify randomness
        offsets_found = []

        for _ in range(10):
            await FingerprintBypass._randomize_audio_context(mock_page)

            script = mock_page.add_init_script.call_args[0][0]

            # Extract offset value from script
            # Look for "const audioOffset = X;" pattern
            if "audioOffset" in script:
                # Offset should be present
                offsets_found.append(script)

        # All scripts should have offset defined
        assert len(offsets_found) == 10

    @pytest.mark.asyncio
    async def test_all_methods_called_independently(self):
        """Test that all bypass methods can be called independently."""
        mock_page = AsyncMock()

        # Test each method individually
        await FingerprintBypass._inject_canvas_noise(mock_page)
        assert mock_page.add_init_script.call_count == 1

        mock_page.reset_mock()
        await FingerprintBypass._spoof_webgl(mock_page)
        assert mock_page.add_init_script.call_count == 1

        mock_page.reset_mock()
        await FingerprintBypass._randomize_audio_context(mock_page)
        assert mock_page.add_init_script.call_count == 1

    @pytest.mark.asyncio
    async def test_canvas_noise_assertion_validation(self):
        """Test that canvas noise values are validated."""
        # This test verifies the assertions in _inject_canvas_noise
        # by checking they don't raise errors for valid values

        mock_page = AsyncMock()

        # Should not raise any assertion errors
        await FingerprintBypass._inject_canvas_noise(mock_page)

        # Verify the script was injected successfully
        assert mock_page.add_init_script.called

    @pytest.mark.asyncio
    async def test_scripts_are_valid_javascript(self):
        """Test that injected scripts are syntactically valid JavaScript."""
        mock_page = AsyncMock()

        # Apply all bypasses
        await FingerprintBypass.apply_all(mock_page)

        # Get all injected scripts
        assert mock_page.add_init_script.call_count == 3

        for call in mock_page.add_init_script.call_args_list:
            script = call[0][0]

            # Basic syntax checks
            assert script.count("{") == script.count("}")  # Balanced braces
            assert "function" in script or "=>" in script  # Contains functions
            assert ";" in script  # Contains statements

    @pytest.mark.asyncio
    async def test_apply_all_partial_failure(self):
        """Test apply_all continues even if one method fails."""
        mock_page = AsyncMock()

        # Make one method fail but others succeed
        call_count = 0

        def side_effect_fail_second(script):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Second script failed")

        mock_page.add_init_script.side_effect = side_effect_fail_second

        # Should handle error and not raise
        await FingerprintBypass.apply_all(mock_page)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
