"""Captcha solving module using 2Captcha service."""

import asyncio
import logging
from typing import Any, Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CaptchaSolver:
    """2Captcha-based captcha solving service."""

    def __init__(self, api_key: str = "", manual_timeout: int = 120):
        """
        Initialize 2Captcha solver.

        Args:
            api_key: 2Captcha API key (empty string for manual-only mode)
            manual_timeout: Timeout for fallback manual solving in seconds
        """
        self.api_key = api_key
        self.manual_timeout = manual_timeout

        if api_key:
            logger.info("CaptchaSolver initialized with 2Captcha")
        else:
            logger.warning("CaptchaSolver initialized without API key - manual mode only")

    async def solve_recaptcha(self, page: Page, site_key: str, url: str) -> Optional[str]:
        """
        Solve reCAPTCHA v2/v3 using 2Captcha or manual fallback.

        Args:
            page: Playwright page object
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token or None
        """
        if not self.api_key:
            logger.warning("No 2Captcha API key, using manual solving")
            return await self._solve_manually(page)

        logger.info("Solving reCAPTCHA with 2Captcha...")

        try:
            return await self._solve_with_2captcha(site_key, url)
        except Exception as e:
            logger.error(f"2Captcha failed: {e}, falling back to manual solving")
            return await self._solve_manually(page)

    async def _solve_with_2captcha(self, site_key: str, url: str) -> Optional[str]:
        """
        Solve captcha using 2Captcha service.

        Args:
            site_key: reCAPTCHA site key
            url: Page URL

        Returns:
            Captcha solution token
        """
        from twocaptcha import TwoCaptcha

        solver = TwoCaptcha(self.api_key)

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result: Any = await loop.run_in_executor(
            None, lambda: solver.recaptcha(sitekey=site_key, url=url)
        )

        logger.info("2Captcha solved successfully")
        solution: str = result["code"]
        return solution

    async def _solve_manually(self, page: Page) -> Optional[str]:
        """
        Fallback: Wait for manual captcha solving.

        Args:
            page: Playwright page object

        Returns:
            Captcha solution token
        """
        logger.info(f"Waiting {self.manual_timeout}s for manual captcha solving...")

        for _ in range(self.manual_timeout):
            token_result = await page.evaluate(
                """
                () => {
                    const response = document.querySelector('[name="g-recaptcha-response"]');
                    return response ? response.value : null;
                }
            """
            )

            token: Optional[str] = token_result if isinstance(token_result, str) else None
            if token:
                logger.info("Manual captcha solved")
                return token

            await asyncio.sleep(1)

        logger.warning("Manual captcha solving timeout")
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
            Turnstile token or None
        """
        if not self.api_key:
            logger.warning("No 2Captcha API key for Turnstile")
            return None

        try:
            from twocaptcha import TwoCaptcha

            solver = TwoCaptcha(self.api_key)

            logger.info(f"Solving Turnstile captcha for {page_url}")

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: solver.turnstile(
                    sitekey=site_key,
                    url=page_url,
                ),
            )

            token = result.get("code")
            logger.info("Turnstile solved successfully")
            return token

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
                        el.innerHTML = token;
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
