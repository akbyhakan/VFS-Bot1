"""Playwright stealth configuration to hide automation detection."""

import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class StealthConfig:
    """Apply stealth scripts to hide automation detection."""
    
    @staticmethod
    async def apply_stealth(page: Page) -> None:
        """
        Apply all stealth configurations to a page.
        
        Args:
            page: Playwright page object
        """
        try:
            await StealthConfig._override_webdriver(page)
            await StealthConfig._spoof_plugins(page)
            await StealthConfig._spoof_languages(page)
            await StealthConfig._add_chrome_runtime(page)
            await StealthConfig._override_permissions(page)
            logger.info("Stealth configurations applied successfully")
        except Exception as e:
            logger.error(f"Error applying stealth config: {e}")
    
    @staticmethod
    async def _override_webdriver(page: Page) -> None:
        """Override navigator.webdriver flag."""
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
        """)
    
    @staticmethod
    async def _spoof_plugins(page: Page) -> None:
        """Spoof navigator.plugins to appear as a real browser."""
        await page.add_init_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    },
                    {
                        0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                        1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                        description: "",
                        filename: "internal-nacl-plugin",
                        length: 2,
                        name: "Native Client"
                    }
                ],
                configurable: true
            });
        """)
    
    @staticmethod
    async def _spoof_languages(page: Page) -> None:
        """Spoof navigator.languages."""
        await page.add_init_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
        """)
    
    @staticmethod
    async def _add_chrome_runtime(page: Page) -> None:
        """Add chrome runtime object."""
        await page.add_init_script("""
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        """)
    
    @staticmethod
    async def _override_permissions(page: Page) -> None:
        """Override permissions query."""
        await page.add_init_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
