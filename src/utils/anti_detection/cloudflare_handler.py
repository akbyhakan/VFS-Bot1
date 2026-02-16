"""Detect and bypass Cloudflare protections."""

import asyncio
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from ...constants import Delays


class CloudflareHandler:
    """Handle Cloudflare challenge detection and bypass."""

    CHALLENGE_TYPES = {
        "waiting_room": "Waiting Room",
        "turnstile": "Turnstile",
        "browser_check": "Browser Check",
        "blocked": "Blocked",
    }

    def __init__(self, config: Optional[Dict[Any, Any]] = None):
        """
        Initialize Cloudflare handler.

        Args:
            config: Configuration dictionary with Cloudflare settings
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_wait_time = self.config.get("max_wait_time", 30)
        self.max_retries = self.config.get("max_retries", 3)
        self.manual_captcha = self.config.get("manual_captcha", False)

    async def detect_cloudflare_challenge(self, page: Page) -> Optional[str]:
        """
        Identify Cloudflare challenge type.

        Returns:
            Challenge type or None if no challenge detected
        """
        try:
            # Get page title and content
            title = await page.title()
            content = await page.content()

            # Check for Waiting Room
            if "waiting room" in title.lower() or "waiting room" in content.lower():
                logger.info("Detected Cloudflare Waiting Room")
                return "waiting_room"

            # Check for "Just a moment"
            if "just a moment" in title.lower():
                logger.info("Detected Cloudflare Browser Check")
                return "browser_check"

            # Check for Turnstile challenge
            # Note: Cloudflare may use different challenge domains
            turnstile_selector = (
                'iframe[src*="challenges.cloudflare.com"], '
                'iframe[src*="cloudflare.com/cdn-cgi/challenge-platform"]'
            )
            turnstile = await page.locator(turnstile_selector).count()
            if turnstile > 0:
                logger.info("Detected Cloudflare Turnstile challenge")
                return "turnstile"

            # Check for blocked page
            if "403 forbidden" in content.lower() or "503 service unavailable" in content.lower():
                if "cloudflare" in content.lower():
                    logger.info("Detected Cloudflare block (403/503)")
                    return "blocked"

            # No challenge detected
            return None

        except Exception as e:
            logger.error(f"Error detecting Cloudflare challenge: {e}")
            return None

    async def handle_waiting_room(self, page: Page) -> bool:
        """
        Wait up to max_wait_time seconds for clearance.

        Args:
            page: Playwright page object

        Returns:
            True if cleared waiting room
        """
        logger.info(f"Handling Waiting Room (max wait: {self.max_wait_time}s)")

        try:
            # Use event-driven approach with fallback to polling
            try:
                # Wait for title to change (not contain "waiting room")
                await asyncio.wait_for(
                    page.wait_for_function(
                        "() => !document.title.toLowerCase().includes('waiting room')",
                        timeout=self.max_wait_time * 1000,  # Convert to milliseconds
                    ),
                    timeout=self.max_wait_time,
                )
                logger.info("Cleared Waiting Room (event-driven)")
                return True
            except asyncio.TimeoutError:
                # Fallback: Double-check with polling in case event-driven approach missed it
                title = await page.title()
                if "waiting room" not in title.lower():
                    logger.info("Cleared Waiting Room (fallback check)")
                    return True
                logger.warning("Waiting Room timeout")
                return False

        except Exception as e:
            logger.error(f"Error handling Waiting Room: {e}")
            return False

    async def handle_turnstile(self, page: Page) -> bool:
        """
        Handle Turnstile challenge (auto-solve or manual).

        Args:
            page: Playwright page object

        Returns:
            True if challenge passed
        """
        logger.info("Handling Turnstile challenge")

        try:
            if self.manual_captcha:
                # Wait for manual solving
                logger.info(f"Waiting for manual Turnstile solve ({self.max_wait_time}s)")
                await asyncio.sleep(self.max_wait_time)
                return True
            else:
                # Use event-driven approach: wait for iframe to disappear
                logger.info("Waiting for Turnstile auto-solve (event-driven)")
                turnstile_selector = 'iframe[src*="challenges.cloudflare.com"]'
                
                try:
                    # Wait for the iframe to be hidden or detached
                    await asyncio.wait_for(
                        page.wait_for_selector(
                            turnstile_selector,
                            state="hidden",
                            timeout=self.max_wait_time * 1000,  # Convert to milliseconds
                        ),
                        timeout=self.max_wait_time,
                    )
                    logger.info("Turnstile challenge passed (event-driven)")
                    return True
                except asyncio.TimeoutError:
                    # Fallback: check if iframe still exists
                    turnstile_count = await page.locator(turnstile_selector).count()
                    if turnstile_count == 0:
                        logger.info("Turnstile challenge passed (fallback check)")
                        return True
                    logger.warning("Turnstile timeout")
                    return False

        except Exception as e:
            logger.error(f"Error handling Turnstile: {e}")
            return False

    async def handle_browser_check(self, page: Page) -> bool:
        """
        Wait for auto-redirect from browser check.

        Args:
            page: Playwright page object

        Returns:
            True if check passed
        """
        logger.info("Handling Browser Check")

        try:
            # Use event-driven approach with fallback to polling
            try:
                # Wait for title to change (not contain "just a moment")
                await asyncio.wait_for(
                    page.wait_for_function(
                        "() => !document.title.toLowerCase().includes('just a moment')",
                        timeout=self.max_wait_time * 1000,  # Convert to milliseconds
                    ),
                    timeout=self.max_wait_time,
                )
                logger.info("Browser Check passed (event-driven)")
                return True
            except asyncio.TimeoutError:
                # Fallback: Double-check with polling in case event-driven approach missed it
                title = await page.title()
                if "just a moment" not in title.lower():
                    logger.info("Browser Check passed (fallback check)")
                    return True
                logger.warning("Browser Check timeout")
                return False

        except Exception as e:
            logger.error(f"Error handling Browser Check: {e}")
            return False

    async def handle_challenge(self, page: Page) -> bool:
        """
        Main dispatcher for all Cloudflare challenges.

        Args:
            page: Playwright page object

        Returns:
            True if challenge handled successfully
        """
        if not self.enabled:
            logger.debug("Cloudflare handler disabled")
            return True

        try:
            # Detect challenge type
            challenge_type = await self.detect_cloudflare_challenge(page)

            if not challenge_type:
                # No challenge detected
                return True

            challenge_name = self.CHALLENGE_TYPES.get(challenge_type, "Unknown")
            logger.info(f"Handling Cloudflare challenge: {challenge_name}")

            # Handle based on type
            if challenge_type == "waiting_room":
                return await self.handle_waiting_room(page)
            elif challenge_type == "turnstile":
                return await self.handle_turnstile(page)
            elif challenge_type == "browser_check":
                return await self.handle_browser_check(page)
            elif challenge_type == "blocked":
                logger.error("Page blocked by Cloudflare")
                return False

            return False

        except Exception as e:
            logger.error(f"Error handling Cloudflare challenge: {e}")
            return False
