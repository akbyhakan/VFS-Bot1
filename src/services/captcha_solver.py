"""Captcha solving module using 2Captcha service."""

import asyncio
import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from loguru import logger
from playwright.async_api import Page


class CaptchaSolver:
    """2Captcha-based captcha solving service."""

    _executor = ThreadPoolExecutor(max_workers=2)

    def __init__(self, api_key: str):
        """
        Initialize 2Captcha solver.

        Args:
            api_key: 2Captcha API key (required)

        Raises:
            ValueError: If api_key is empty or missing
        """
        if not api_key:
            raise ValueError("2Captcha API key is required. Manual solving mode is not supported.")

        self._api_key = api_key
        logger.info("CaptchaSolver initialized with 2Captcha")

    @property
    def api_key(self) -> str:
        """Get API key (property for backward compatibility)."""
        return self._api_key

    def __repr__(self) -> str:
        """Return repr with masked API key."""
        masked_key = f"{self._api_key[:8]}..." if len(self._api_key) > 8 else "***"
        return f"CaptchaSolver(api_key='{masked_key}')"

    def __str__(self) -> str:
        """Return string representation with masked API key."""
        return self.__repr__()

    async def solve_recaptcha(self, page: Page, site_key: str, url: str) -> Optional[str]:
        """
        Solve reCAPTCHA v2/v3 using 2Captcha.

        Args:
            page: Playwright page object
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token or None if solving failed
        """
        logger.info("Solving reCAPTCHA with 2Captcha...")

        try:
            return await self._solve_with_2captcha(site_key, url)
        except Exception as e:
            logger.error(f"2Captcha failed: {e}")
            return None

    async def _solve_with_2captcha(self, site_key: str, url: str) -> Optional[str]:
        """
        Solve captcha using 2Captcha service.

        Args:
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token or None if solving failed
        """
        try:
            from twocaptcha import TwoCaptcha

            solver = TwoCaptcha(self.api_key)

            # Run in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result: Any = await loop.run_in_executor(
                self._executor, lambda: solver.recaptcha(sitekey=site_key, url=url)
            )

            # Safe key access - KeyError fix
            if result and isinstance(result, dict) and "code" in result:
                logger.info("2Captcha solved successfully")
                return str(result["code"])

            logger.warning(f"2Captcha returned unexpected result: {result}")
            return None

        except Exception as e:
            logger.error(f"2Captcha error: {e}")
            return None

    async def solve_turnstile(
        self, page_url: str, site_key: str, timeout: int = 120
    ) -> Optional[str]:
        """
        Solve Cloudflare Turnstile captcha using 2Captcha.

        VFS Global uses Cloudflare Turnstile instead of reCAPTCHA.

        Args:
            page_url: Page URL where Turnstile is displayed
            site_key: Turnstile site key
            timeout: Solving timeout in seconds

        Returns:
            Turnstile token or None if solving failed
        """

        try:
            from twocaptcha import TwoCaptcha

            solver = TwoCaptcha(self.api_key)

            logger.info(f"Solving Turnstile captcha for {page_url}")

            # Run in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: solver.turnstile(
                    sitekey=site_key,
                    url=page_url,
                ),
            )

            # Safe key access - consistent with _solve_with_2captcha
            if result and isinstance(result, dict) and "code" in result:
                token = str(result["code"])
                logger.info("Turnstile solved successfully")
                return token
            
            logger.warning(f"Turnstile returned unexpected result: {result}")
            return None

        except Exception as e:
            logger.error(f"Turnstile solving error: {e}")
            return None

    async def inject_captcha_solution(self, page: Page, token: str) -> bool:
        """
        Inject captcha solution token into page.

        Args:
            page: Playwright page object
            token: Captcha solution token

        Returns:
            True if successful
        """
        try:
            await page.evaluate(
                """(token) => {
                    const el = document.querySelector('[name="g-recaptcha-response"]');
                    if (el) {
                        el.value = token;
                        el.textContent = token;
                    }
                    // Trigger callback if exists
                    if (typeof ___grecaptcha_cfg !== 'undefined') {
                        Object.keys(___grecaptcha_cfg.clients).forEach(key => {
                            const client = ___grecaptcha_cfg.clients[key];
                            if (client.callback) {
                                client.callback(token);
                            }
                        });
                    }
                }""",
                token,
            )
            logger.info("Captcha solution injected")
            return True
        except Exception as e:
            logger.error(f"Failed to inject captcha solution: {e}")
            return False

    @classmethod
    def shutdown(cls, wait: bool = True) -> None:
        """
        Shutdown the thread pool executor.

        Args:
            wait: If True, wait for pending tasks to complete before shutdown
        """
        cls._executor.shutdown(wait=wait)
        logger.info(f"CaptchaSolver executor shutdown (wait={wait})")


# Register automatic cleanup on module exit
# Note: Using wait=False to avoid blocking process termination.
# Captcha solving tasks are API calls that can be safely interrupted during shutdown.
atexit.register(CaptchaSolver.shutdown, wait=False)
