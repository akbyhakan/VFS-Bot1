"""Bypass Canvas, WebGL, and Audio Context fingerprinting."""

import random
from dataclasses import dataclass
from typing import Optional

from loguru import logger
from playwright.async_api import Page

# Import FingerprintProfile if needed
try:
    from .fingerprint_rotator import FingerprintProfile
except ImportError:
    FingerprintProfile = None  # type: ignore


@dataclass
class CanvasNoiseConfig:
    """Configuration for canvas noise injection."""

    # RGB shift ranges - small values to avoid visual artifacts
    RGB_SHIFT_MIN: int = -5
    RGB_SHIFT_MAX: int = 5

    # Alpha shift range - smaller to maintain transparency accuracy
    ALPHA_SHIFT_MIN: int = -2
    ALPHA_SHIFT_MAX: int = 2


class FingerprintBypass:
    """Bypass browser fingerprinting techniques."""

    # Default configuration
    DEFAULT_CONFIG = CanvasNoiseConfig()

    @staticmethod
    async def apply_all(page: Page, profile: Optional["FingerprintProfile"] = None) -> None:
        """
        Apply all fingerprint bypass scripts to a page.

        Args:
            page: Playwright page object
            profile: Optional FingerprintProfile for consistent parameters
        """
        try:
            await FingerprintBypass._inject_canvas_noise(page, profile=profile)
            await FingerprintBypass._spoof_webgl(page, profile=profile)
            await FingerprintBypass._randomize_audio_context(page)
            logger.info("Fingerprint bypass scripts applied successfully")
        except Exception as e:
            logger.error(f"Error applying fingerprint bypass: {e}")

    @staticmethod
    async def _inject_canvas_noise(
        page: Page,
        config: Optional[CanvasNoiseConfig] = None,
        profile: Optional["FingerprintProfile"] = None,
    ) -> None:
        """
        Inject noise into Canvas to randomize fingerprint.

        Args:
            page: Playwright page object
            config: Optional noise configuration (uses DEFAULT_CONFIG if None)
            profile: Optional FingerprintProfile with predefined noise values
        """
        config = config or FingerprintBypass.DEFAULT_CONFIG

        # Use profile values if provided, otherwise generate random
        if profile is not None:
            r_shift = profile.canvas_noise_r
            g_shift = profile.canvas_noise_g
            b_shift = profile.canvas_noise_b
            a_shift = profile.canvas_noise_a
        else:
            # Generate random noise shift values using configuration
            r_shift = random.randint(config.RGB_SHIFT_MIN, config.RGB_SHIFT_MAX)
            g_shift = random.randint(config.RGB_SHIFT_MIN, config.RGB_SHIFT_MAX)
            b_shift = random.randint(config.RGB_SHIFT_MIN, config.RGB_SHIFT_MAX)
            a_shift = random.randint(config.ALPHA_SHIFT_MIN, config.ALPHA_SHIFT_MAX)

        # Validate values are within safe range
        assert config.RGB_SHIFT_MIN <= r_shift <= config.RGB_SHIFT_MAX
        assert config.RGB_SHIFT_MIN <= g_shift <= config.RGB_SHIFT_MAX
        assert config.RGB_SHIFT_MIN <= b_shift <= config.RGB_SHIFT_MAX
        assert config.ALPHA_SHIFT_MIN <= a_shift <= config.ALPHA_SHIFT_MAX

        await page.add_init_script(f"""
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;

            const noiseR = {r_shift};
            const noiseG = {g_shift};
            const noiseB = {b_shift};
            const noiseA = {a_shift};

            // Override getImageData to add noise
            CanvasRenderingContext2D.prototype.getImageData = function() {{
                const imageData = originalGetImageData.apply(this, arguments);
                const data = imageData.data;

                for (let i = 0; i < data.length; i += 4) {{
                    data[i] = Math.min(255, Math.max(0, data[i] + noiseR));     // R
                    data[i + 1] = Math.min(255, Math.max(0, data[i + 1] + noiseG)); // G
                    data[i + 2] = Math.min(255, Math.max(0, data[i + 2] + noiseB)); // B
                    data[i + 3] = Math.min(255, Math.max(0, data[i + 3] + noiseA)); // A
                }}

                return imageData;
            }};

            // Override toDataURL
            HTMLCanvasElement.prototype.toDataURL = function() {{
                const context = this.getContext('2d');
                if (context) {{
                    // Trigger noise injection by getting and putting image data
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    context.putImageData(imageData, 0, 0);
                }}
                return originalToDataURL.apply(this, arguments);
            }};

            // Override toBlob
            HTMLCanvasElement.prototype.toBlob = function() {{
                const context = this.getContext('2d');
                if (context) {{
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    context.putImageData(imageData, 0, 0);
                }}
                return originalToBlob.apply(this, arguments);
            }};
        """)

    @staticmethod
    async def _spoof_webgl(page: Page, profile: Optional["FingerprintProfile"] = None) -> None:
        """
        Spoof WebGL vendor and renderer.

        Args:
            page: Playwright page object
            profile: Optional FingerprintProfile with predefined vendor/renderer
        """
        # Use profile values if provided, otherwise use random defaults
        if profile is not None:
            vendor = profile.webgl_vendor
            renderer = profile.webgl_renderer
        else:
            # Random vendor/renderer combinations
            vendors = [
                (
                    "Google Inc. (Intel)",
                    "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
                ),
                (
                    "Google Inc. (NVIDIA)",
                    "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 vs_5_0 ps_5_0)",
                ),
                (
                    "Google Inc. (AMD)",
                    "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0)",
                ),
            ]
            vendor, renderer = random.choice(vendors)

        await page.add_init_script(f"""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{
                    return '{vendor}';
                }}
                if (parameter === 37446) {{
                    return '{renderer}';
                }}
                return getParameter.apply(this, arguments);
            }};

            const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{
                    return '{vendor}';
                }}
                if (parameter === 37446) {{
                    return '{renderer}';
                }}
                return getParameter2.apply(this, arguments);
            }};
        """)

    @staticmethod
    async def _randomize_audio_context(page: Page) -> None:
        """Randomize Audio Context timing to prevent fingerprinting."""
        # Generate random offset for audio timing
        offset = random.uniform(0.0001, 0.001)

        await page.add_init_script(f"""
            const audioOffset = {offset};

            const OriginalAudioContext = window.AudioContext || window.webkitAudioContext;

            if (OriginalAudioContext) {{
                const AudioContextProxy = new Proxy(OriginalAudioContext, {{
                    construct(target, args) {{
                        const context = new target(...args);
                        const originalGetChannelData = context.createBuffer.bind(context);

                        context.createBuffer = function() {{
                            const buffer = originalGetChannelData.apply(this, arguments);
                            const getChannelData = buffer.getChannelData.bind(buffer);

                            buffer.getChannelData = function(channel) {{
                                const data = getChannelData.call(this, channel);
                                for (let i = 0; i < data.length; i++) {{
                                    data[i] += audioOffset * (Math.random() - 0.5);
                                }}
                                return data;
                            }};

                            return buffer;
                        }};

                        return context;
                    }}
                }});

                window.AudioContext = AudioContextProxy;
                if (window.webkitAudioContext) {{
                    window.webkitAudioContext = AudioContextProxy;
                }}
            }}
        """)
