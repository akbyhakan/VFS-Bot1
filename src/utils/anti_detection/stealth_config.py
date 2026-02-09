"""Playwright stealth configuration to hide automation detection."""

import logging

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class StealthConfig:
    """Apply stealth scripts to hide automation detection."""

    @staticmethod
    async def apply_stealth(page: Page, languages: list | None = None) -> None:
        """
        Apply all stealth configurations to a page.

        Args:
            page: Playwright page object
            languages: Optional list of language codes for navigator.languages spoofing.
                       Defaults to ['tr-TR', 'tr', 'en-US', 'en'] for VFS Turkey.
        """
        try:
            await StealthConfig._override_webdriver(page)
            await StealthConfig._spoof_plugins(page)
            await StealthConfig._spoof_languages(page, languages=languages)
            await StealthConfig._add_chrome_runtime(page)
            await StealthConfig._override_permissions(page)
            logger.info("Stealth configurations applied successfully")
        except Exception as e:
            logger.error(f"Error applying stealth config: {e}")

    @staticmethod
    async def _override_webdriver(page: Page) -> None:
        """Override navigator.webdriver flag."""
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
        """
        )

    @staticmethod
    async def _spoof_plugins(page: Page) -> None:
        """Spoof navigator.plugins to appear as a real browser."""
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {
                            type: "application/x-google-chrome-pdf",
                            suffixes: "pdf",
                            description: "Portable Document Format"
                        },
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {
                            type: "application/pdf",
                            suffixes: "pdf",
                            description: "Portable Document Format"
                        },
                        description: "Portable Document Format",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    },
                    {
                        0: {
                            type: "application/x-nacl",
                            suffixes: "",
                            description: "Native Client Executable"
                        },
                        1: {
                            type: "application/x-pnacl",
                            suffixes: "",
                            description: "Portable Native Client Executable"
                        },
                        description: "",
                        filename: "internal-nacl-plugin",
                        length: 2,
                        name: "Native Client"
                    }
                ],
                configurable: true
            });
        """
        )

    @staticmethod
    async def _spoof_languages(page: Page, languages: list | None = None) -> None:
        """Spoof navigator.languages.

        Args:
            page: Playwright page object
            languages: List of language codes to spoof. Defaults to Turkish locale
                       for VFS Turkey compatibility: ['tr-TR', 'tr', 'en-US', 'en']
        
        Raises:
            ValueError: If language codes contain invalid characters
        """
        if languages is None:
            languages = ['tr-TR', 'tr', 'en-US', 'en']

        # Validate language codes to prevent JavaScript injection
        import re
        lang_pattern = re.compile(r'^[a-zA-Z]{2}(-[a-zA-Z]{2,4})?$')
        for lang in languages:
            if not lang_pattern.match(lang):
                raise ValueError(f"Invalid language code: {lang}. Must match pattern 'xx' or 'xx-YY'")

        languages_js = ', '.join(f"'{lang}'" for lang in languages)
        await page.add_init_script(f"""
            Object.defineProperty(navigator, 'languages', {{
                get: () => [{languages_js}],
                configurable: true
            }});
        """)

    @staticmethod
    async def _add_chrome_runtime(page: Page) -> None:
        """Add chrome runtime object."""
        await page.add_init_script(
            """
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """
        )

    @staticmethod
    async def _override_permissions(page: Page) -> None:
        """Override permissions query."""
        await page.add_init_script(
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """
        )
