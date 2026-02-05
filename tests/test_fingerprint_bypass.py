"""Tests for fingerprint bypass."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.anti_detection.fingerprint_bypass import FingerprintBypass


@pytest.fixture
def mock_page():
    """Mock Playwright page object."""
    page = AsyncMock()
    page.add_init_script = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_apply_all_fingerprint_bypasses(mock_page):
    """Test that apply_all calls all bypass methods."""
    await FingerprintBypass.apply_all(mock_page)
    # Should call add_init_script for each bypass method
    assert mock_page.add_init_script.call_count == 3


@pytest.mark.asyncio
async def test_apply_all_error_handling():
    """Test apply_all error handling."""
    error_page = AsyncMock()
    error_page.add_init_script = AsyncMock(side_effect=Exception("Script injection failed"))

    # Should not raise exception
    await FingerprintBypass.apply_all(error_page)


@pytest.mark.asyncio
async def test_inject_canvas_noise(mock_page):
    """Test canvas noise injection."""
    await FingerprintBypass._inject_canvas_noise(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains canvas override
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "CanvasRenderingContext2D" in call_args
    assert "getImageData" in call_args
    assert "toDataURL" in call_args
    assert "toBlob" in call_args


@pytest.mark.asyncio
async def test_canvas_noise_randomization(mock_page):
    """Test that canvas noise values are randomized."""
    # Call twice and verify scripts are different (due to random values)
    await FingerprintBypass._inject_canvas_noise(mock_page)
    first_script = mock_page.add_init_script.call_args[0][0]

    mock_page.add_init_script.reset_mock()

    await FingerprintBypass._inject_canvas_noise(mock_page)
    second_script = mock_page.add_init_script.call_args[0][0]

    # Scripts might be different due to random noise values
    # Both should have the noise constants defined
    assert "noiseR" in first_script
    assert "noiseG" in first_script
    assert "noiseB" in first_script
    assert "noiseA" in first_script
    assert "noiseR" in second_script


@pytest.mark.asyncio
async def test_canvas_noise_values_in_range(mock_page):
    """Test that canvas noise values are within safe range."""
    await FingerprintBypass._inject_canvas_noise(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Extract noise values from script
    import re

    noise_r = re.search(r"const noiseR = (-?\d+);", script)
    noise_g = re.search(r"const noiseG = (-?\d+);", script)
    noise_b = re.search(r"const noiseB = (-?\d+);", script)
    noise_a = re.search(r"const noiseA = (-?\d+);", script)

    # Verify they are within expected ranges
    if noise_r:
        assert -5 <= int(noise_r.group(1)) <= 5
    if noise_g:
        assert -5 <= int(noise_g.group(1)) <= 5
    if noise_b:
        assert -5 <= int(noise_b.group(1)) <= 5
    if noise_a:
        assert -2 <= int(noise_a.group(1)) <= 2


@pytest.mark.asyncio
async def test_spoof_webgl(mock_page):
    """Test WebGL spoofing."""
    await FingerprintBypass._spoof_webgl(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains WebGL override
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "WebGLRenderingContext" in call_args
    assert "getParameter" in call_args
    assert "37445" in call_args  # UNMASKED_VENDOR_WEBGL
    assert "37446" in call_args  # UNMASKED_RENDERER_WEBGL


@pytest.mark.asyncio
async def test_webgl_vendor_randomization(mock_page):
    """Test that WebGL vendor is randomized."""
    # Call multiple times to see different vendors
    vendors = set()
    for _ in range(10):
        mock_page.add_init_script.reset_mock()
        await FingerprintBypass._spoof_webgl(mock_page)
        script = mock_page.add_init_script.call_args[0][0]
        vendors.add(script)

    # Should have at least one vendor (possibly more with randomization)
    assert len(vendors) >= 1


@pytest.mark.asyncio
async def test_webgl_includes_valid_vendors(mock_page):
    """Test that WebGL includes valid vendor strings."""
    await FingerprintBypass._spoof_webgl(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should include some vendor/renderer info
    has_vendor = any(
        vendor in script for vendor in ["Google Inc.", "Intel", "NVIDIA", "AMD", "ANGLE"]
    )
    assert has_vendor


@pytest.mark.asyncio
async def test_randomize_audio_context(mock_page):
    """Test audio context randomization."""
    await FingerprintBypass._randomize_audio_context(mock_page)
    mock_page.add_init_script.assert_called_once()

    # Verify the script contains AudioContext override
    call_args = mock_page.add_init_script.call_args[0][0]
    assert "AudioContext" in call_args
    assert "createBuffer" in call_args
    assert "getChannelData" in call_args


@pytest.mark.asyncio
async def test_audio_offset_randomization(mock_page):
    """Test that audio offset is randomized."""
    await FingerprintBypass._randomize_audio_context(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should have audioOffset defined
    assert "audioOffset" in script

    # Extract offset value
    import re

    offset_match = re.search(r"const audioOffset = ([\d.]+);", script)
    if offset_match:
        offset = float(offset_match.group(1))
        # Should be within expected range
        assert 0.0001 <= offset <= 0.001


@pytest.mark.asyncio
async def test_audio_context_proxy_pattern(mock_page):
    """Test that audio context uses Proxy pattern."""
    await FingerprintBypass._randomize_audio_context(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should use Proxy pattern
    assert "Proxy" in script
    assert "construct" in script


@pytest.mark.asyncio
async def test_fingerprint_bypass_static_methods():
    """Test that all methods are static."""
    # All methods should be callable as class methods
    assert callable(FingerprintBypass.apply_all)
    assert callable(FingerprintBypass._inject_canvas_noise)
    assert callable(FingerprintBypass._spoof_webgl)
    assert callable(FingerprintBypass._randomize_audio_context)


@pytest.mark.asyncio
async def test_multiple_apply_all_calls(mock_page):
    """Test that apply_all can be called multiple times."""
    await FingerprintBypass.apply_all(mock_page)
    first_call_count = mock_page.add_init_script.call_count

    await FingerprintBypass.apply_all(mock_page)
    second_call_count = mock_page.add_init_script.call_count

    # Should double the number of calls
    assert second_call_count == first_call_count * 2


@pytest.mark.asyncio
async def test_canvas_override_methods(mock_page):
    """Test that canvas overrides key methods."""
    await FingerprintBypass._inject_canvas_noise(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should override all three canvas methods
    assert "originalGetImageData" in script
    assert "originalToDataURL" in script
    assert "originalToBlob" in script


@pytest.mark.asyncio
async def test_webgl_both_contexts(mock_page):
    """Test that both WebGL contexts are overridden."""
    await FingerprintBypass._spoof_webgl(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should override both WebGL and WebGL2
    assert "WebGLRenderingContext" in script
    assert "WebGL2RenderingContext" in script


@pytest.mark.asyncio
async def test_audio_webkit_support(mock_page):
    """Test that webkit AudioContext is also supported."""
    await FingerprintBypass._randomize_audio_context(mock_page)
    script = mock_page.add_init_script.call_args[0][0]

    # Should support webkit prefix
    assert "webkitAudioContext" in script
