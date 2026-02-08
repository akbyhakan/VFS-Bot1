"""Payment handling utilities for VFS booking system."""

import asyncio
import logging
import random
from typing import Any, Dict

from playwright.async_api import Page

from .selector_utils import resolve_selector, try_selectors, get_selector
from ..otp_webhook import get_otp_service

logger = logging.getLogger(__name__)


class PaymentHandler:
    """Handles payment processing for VFS booking system."""

    def __init__(self, config: Dict[str, Any], payment_service: Any = None):
        """
        Initialize payment handler.

        Args:
            config: Bot configuration
            payment_service: Optional PaymentService instance for PCI-DSS compliant payment processing
        """
        self.config = config
        self.payment_service = payment_service
        self.otp_service = get_otp_service()

    async def wait_for_overlay(self, page: Page, timeout: int = 30000) -> None:
        """
        Wait for loading overlay to disappear.
        Tries multiple overlay selectors.

        Args:
            page: Playwright page
            timeout: Maximum wait time in ms
        """
        try:
            selectors = resolve_selector("overlay")
            for selector in selectors:
                try:
                    overlay = page.locator(selector)
                    if await overlay.count() > 0:
                        await overlay.wait_for(state="hidden", timeout=timeout)
                        logger.debug(f"Overlay disappeared: {selector}")
                        return
                except Exception as e:
                    logger.debug(f"Overlay selector '{selector}' not found: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Overlay not present or already hidden: {e}")

    async def human_type(self, page: Page, selector_key: str, text: str) -> None:
        """
        Type text with human-like delays and fallback selector support.

        Args:
            page: Playwright page
            selector_key: Selector key in VFS_SELECTORS or direct selector
            text: Text to type

        Raises:
            SelectorNotFoundError: If no selector works
        """
        from ...core.exceptions import SelectorNotFoundError

        selectors = resolve_selector(selector_key)

        for selector in selectors:
            try:
                await page.click(selector)
                await page.fill(selector, "")  # Clear first

                for char in text:
                    await page.type(selector, char, delay=random.randint(50, 150))
                    if random.random() < 0.1:  # 10% chance of small pause
                        await asyncio.sleep(random.uniform(0.1, 0.3))

                logger.debug(f"Successfully typed into: {selector}")
                return  # Success

            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}, trying next...")
                continue

        # No selector worked
        raise SelectorNotFoundError(selector_key, selectors)

    async def fill_payment_form(self, page: Page, card_info: Dict[str, str]) -> None:
        """
        Fill bank payment form.

        Args:
            page: Playwright page
            card_info: Card details (card_number, expiry_month, expiry_year, cvv)
        """
        logger.info("Filling payment form...")

        # Card number
        await self.human_type(page, "card_number", card_info["card_number"])
        logger.info("Card number entered")

        # Expiry month
        await page.select_option(get_selector("expiry_month"), card_info["expiry_month"])
        logger.info("Expiry month selected: **")

        # Expiry year
        await page.select_option(get_selector("expiry_year"), card_info["expiry_year"])
        logger.info("Expiry year selected: ****")

        # CVV
        await self.human_type(page, "cvv", card_info["cvv"])
        logger.info("CVV entered")

        # Random wait
        await asyncio.sleep(random.uniform(1, 3))

        # Submit
        await page.click(get_selector("payment_submit"))
        logger.info("Payment form submitted")

    async def handle_3d_secure(self, page: Page, phone_number: str) -> bool:
        """
        Handle 3D Secure OTP verification with optimized waiting.

        Args:
            page: Playwright page
            phone_number: Phone number to receive OTP

        Returns:
            True if verification successful
        """
        logger.info("3D Secure page detected, waiting for OTP...")

        try:
            # Wait for OTP input
            otp_selectors = resolve_selector("otp_input")
            await try_selectors(page, otp_selectors, action="wait", timeout=10000)

            # Wait for OTP from webhook
            otp_code = await self.otp_service.wait_for_payment_otp(
                phone_number=phone_number, timeout=120
            )

            if not otp_code:
                logger.error("OTP not received within timeout")
                return False

            # Enter OTP
            await try_selectors(page, otp_selectors, action="fill", text=otp_code)
            logger.info("OTP entered successfully")

            # Small delay
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Click Continue
            submit_selectors = resolve_selector("otp_submit")
            await try_selectors(page, submit_selectors, action="click")
            logger.info("OTP submitted")

            # Wait for payment confirmation with polling (not fixed sleep)
            confirmation_result = await self._wait_for_payment_confirmation(page)
            return confirmation_result

        except Exception as e:
            logger.error(f"3D Secure error: {e}")
            return False

    async def _wait_for_payment_confirmation(
        self, page: Page, max_wait: int = 60, check_interval: float = 2.0
    ) -> bool:
        """
        Wait for payment confirmation with early exit polling.

        Args:
            page: Playwright page
            max_wait: Maximum wait time in seconds
            check_interval: How often to check in seconds

        Returns:
            True if payment confirmed, False otherwise
        """
        import time

        start_time = time.time()

        while time.time() - start_time < max_wait:
            # Check 1: Redirected to VFS (verify it's a proper redirect, not just substring)
            current_url = page.url
            # Use proper URL validation to prevent security issues
            if current_url.startswith("https://vfsglobal.com") or current_url.startswith("http://vfsglobal.com"):
                logger.info("✅ Redirected to VFS - Payment successful")
                return True

            # Check 2: Success indicators on page
            success_indicators = [
                ".payment-success",
                ".confirmation-message",
                "text=/payment.*successful/i",
                "text=/ödeme.*başarılı/i",
            ]

            for indicator in success_indicators:
                try:
                    count = await page.locator(indicator).count()
                    if count > 0:
                        logger.info(f"✅ Payment success indicator found: {indicator}")
                        return True
                except Exception:
                    continue

            # Check 3: Error indicators
            error_indicators = [
                ".payment-error",
                ".payment-failed",
                "text=/payment.*failed/i",
                "text=/ödeme.*başarısız/i",
            ]

            for indicator in error_indicators:
                try:
                    count = await page.locator(indicator).count()
                    if count > 0:
                        logger.error(f"❌ Payment failed - error indicator: {indicator}")
                        return False
                except Exception:
                    continue

            await asyncio.sleep(check_interval)

        logger.warning(f"Payment confirmation timeout after {max_wait}s")
        return False
