"""Slot availability checking service for VFS appointments."""

import asyncio
import logging
import random
from typing import Any, Dict, Optional, TypedDict

from playwright.async_api import Page

from ...constants import Delays, Timeouts
from ...utils.anti_detection.cloudflare_handler import CloudflareHandler
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.error_capture import ErrorCapture
from ...utils.helpers import safe_navigate, smart_click
from ...utils.security.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SlotInfo(TypedDict):
    """Available appointment slot information."""

    date: str
    time: str


class SlotChecker:
    """Checks for available VFS appointment slots with rate limiting."""

    def __init__(
        self,
        config: Dict[str, Any],
        rate_limiter: RateLimiter,
        human_sim: Optional[HumanSimulator] = None,
        cloudflare_handler: Optional[CloudflareHandler] = None,
        error_capture: Optional[ErrorCapture] = None,
        selectors: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize slot checker.

        Args:
            config: Bot configuration dictionary
            rate_limiter: RateLimiter instance for rate limiting
            human_sim: Optional HumanSimulator for realistic interactions
            cloudflare_handler: Optional CloudflareHandler for bypassing challenges
            error_capture: Optional ErrorCapture for capturing errors
            selectors: Optional selector configuration (uses hardcoded fallbacks if not provided)
        """
        self.config = config
        self.rate_limiter = rate_limiter
        self.human_sim = human_sim
        self.cloudflare_handler = cloudflare_handler
        self.error_capture = error_capture or ErrorCapture()

        # Initialize SelectorManager for country-aware selectors
        from src.selector import get_selector_manager

        country = config.get("vfs", {}).get("mission", "default")
        self._selector_manager = get_selector_manager(country)

    def _get_selector(self, selector_path: str, fallback: str) -> str:
        """
        Get selector from SelectorManager or return fallback.

        Args:
            selector_path: Dot-notation path to selector (e.g., "appointment.slot_date")
            fallback: Default selector to use if not found

        Returns:
            Selector string
        """
        return self._selector_manager.get(selector_path, fallback)

    async def check_slots(
        self, page: Page, centre: str, category: str, subcategory: str
    ) -> Optional[SlotInfo]:
        """
        Check for available appointment slots.

        Args:
            page: Playwright page object
            centre: VFS centre name
            category: Visa category
            subcategory: Visa subcategory

        Returns:
            Slot information if available, None otherwise
        """
        try:
            # Apply rate limiting before making requests
            await self.rate_limiter.acquire()

            # Navigate to appointment page
            base = self.config["vfs"]["base_url"]
            country = self.config["vfs"]["country"]
            language = self.config["vfs"].get("language", "tr")
            mission = self.config["vfs"]["mission"]
            appointment_url = f"{base}/{country}/{language}/{mission}/appointment"

            if not await safe_navigate(page, appointment_url, timeout=Timeouts.NAVIGATION):
                logger.error("Failed to navigate to appointment page")
                return None

            # Check for Cloudflare challenge
            if self.cloudflare_handler:
                await self.cloudflare_handler.handle_challenge(page)

            # Select centre, category, subcategory using configured selectors
            await page.select_option(
                self._get_selector("appointment.centre_dropdown", "select#centres"), label=centre
            )
            await asyncio.sleep(random.uniform(*Delays.AFTER_SELECT_OPTION))

            await page.select_option(
                self._get_selector("appointment.category_dropdown", "select#categories"),
                label=category,
            )
            await asyncio.sleep(random.uniform(*Delays.AFTER_SELECT_OPTION))

            await page.select_option(
                self._get_selector("appointment.subcategory_dropdown", "select#subcategories"),
                label=subcategory,
            )
            await asyncio.sleep(random.uniform(*Delays.AFTER_SELECT_OPTION))

            # Click to check slots with human simulation using configured selector
            await smart_click(
                page,
                self._get_selector("appointment.check_slots_button", "button#check-slots"),
                self.human_sim,
            )
            await asyncio.sleep(random.uniform(*Delays.AFTER_CLICK_CHECK))

            # Check if slots are available using configured selector
            slots_available = (
                await page.locator(
                    self._get_selector("appointment.available_slot", ".available-slot")
                ).count()
                > 0
            )

            if slots_available:
                # Get slot selectors from SelectorManager
                date_selector = self._get_selector("appointment.slot_date", ".slot-date")
                time_selector = self._get_selector("appointment.slot_time", ".slot-time")

                # Get first available slot
                date_content = await page.locator(date_selector).first.text_content()
                time_content = await page.locator(time_selector).first.text_content()

                date = date_content.strip() if date_content else ""
                time = time_content.strip() if time_content else ""

                # Validate that date and time are not empty strings
                if date and time:
                    logger.info(f"Slot found! Date: {date}, Time: {time}")
                    return {"date": date, "time": time}
                else:
                    logger.warning(
                        f"Slot element found but date/time empty: date='{date}', time='{time}'"
                    )
                    return None
            else:
                logger.info(f"No slots available for {centre}/{category}/{subcategory}")
                return None

        except Exception as e:
            logger.error(f"Error checking slots: {e}")
            # Capture error with context
            await self.error_capture.capture(
                page,
                e,
                context={
                    "step": "check_slots",
                    "centre": centre,
                    "category": category,
                    "subcategory": subcategory,
                    "action": "checking availability",
                },
            )
            return None
