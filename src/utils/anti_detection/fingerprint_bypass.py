"""Bypass Canvas, WebGL, and Audio Context fingerprinting."""

import logging
import random

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class FingerprintBypass:
    """Bypass browser fingerprinting techniques."""

    @staticmethod
    async def apply_all(page: Page) -> None:
        """
        Apply all fingerprint bypass scripts to a page.

        Args:
            page: Playwright page object
        """
        try:
            await FingerprintBypass._inject_canvas_noise(page)
            await FingerprintBypass._spoof_webgl(page)
            await FingerprintBypass._randomize_audio_context(page)
            logger.info("Fingerprint bypass scripts applied successfully")
        except Exception as e:
            logger.error(f"Error applying fingerprint bypass: {e}")

    @staticmethod
    async def _inject_canvas_noise(page: Page) -> None:
        """Inject noise into Canvas to randomize fingerprint."""
        # Generate random noise shift values (-5 to +5)
        # These are safe integer values that cannot cause injection
        r_shift = random.randint(-5, 5)
        g_shift = random.randint(-5, 5)
        b_shift = random.randint(-5, 5)
        a_shift = random.randint(-2, 2)

        # Validate values are within safe range
        assert -5 <= r_shift <= 5
        assert -5 <= g_shift <= 5
        assert -5 <= b_shift <= 5
        assert -2 <= a_shift <= 2

        await page.add_init_script(
            f"""
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
        """
        )

    @staticmethod
    async def _spoof_webgl(page: Page) -> None:
        """Spoof WebGL vendor and renderer."""
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
            ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0)"),
        ]
        vendor, renderer = random.choice(vendors)

        await page.add_init_script(
            f"""
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
        """
        )

    @staticmethod
    async def _randomize_audio_context(page: Page) -> None:
        """Randomize Audio Context timing to prevent fingerprinting."""
        # Generate random offset for audio timing
        offset = random.uniform(0.0001, 0.001)

        await page.add_init_script(
            f"""
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
        """
        )
