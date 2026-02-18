"""Appointment slot selection utilities for VFS booking system."""

import asyncio
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from src.constants import TURKISH_MONTHS, Delays
from src.utils.page_helpers import wait_for_overlay_hidden

from .selector_utils import get_selector, resolve_selector


class SlotSelector:
    """Handles appointment slot selection for VFS booking system."""

    def __init__(self, captcha_solver: Any = None):
        """
        Initialize slot selector.

        Args:
            captcha_solver: Captcha solver instance
        """
        self.captcha_solver = captcha_solver

    async def wait_for_overlay(self, page: Page, timeout: int = 30000) -> None:
        """Wait for loading overlay to disappear. Delegates to shared helper."""
        selectors = resolve_selector("overlay")
        await wait_for_overlay_hidden(page, selectors, timeout)

    def parse_aria_label_to_date(self, aria_label: str) -> Optional[str]:
        """
        Parse Turkish date from aria-label to DD/MM/YYYY format.

        Args:
            aria_label: Date string in format "23 Ocak 2026" (day month_name year)

        Returns:
            Date string in DD/MM/YYYY format, or None if parsing fails

        Examples:
            parse_aria_label_to_date("23 Ocak 2026") returns "23/01/2026"
            parse_aria_label_to_date("5 Şubat 2026") returns "05/02/2026"
        """
        try:
            # aria-label format: "23 Ocak 2026"
            parts = aria_label.strip().split()
            if len(parts) != 3:
                logger.warning(f"Unexpected aria-label format: {aria_label}")
                return None

            day, month_name, year = parts

            # Pad day to 2 digits
            day = day.zfill(2)

            # Convert Turkish month name to number
            month = TURKISH_MONTHS.get(month_name)
            if not month:
                logger.warning(f"Unknown Turkish month: {month_name}")
                return None

            # Return in DD/MM/YYYY format
            return f"{day}/{month}/{year}"

        except Exception as e:
            logger.error(f"Failed to parse aria-label '{aria_label}': {e}")
            return None

    async def select_appointment_slot(self, page: Page, reservation: Dict[str, Any]) -> bool:
        """
        Select appointment date and time from calendar.

        Args:
            page: Playwright page
            reservation: Reservation data with preferred_dates

        Returns:
            True if slot selected successfully
        """
        logger.info("Selecting appointment slot...")

        await self.wait_for_overlay(page)

        # Check for Captcha
        captcha_handled = await self.handle_captcha_if_present(page)
        if not captcha_handled:
            logger.error("Captcha could not be solved, aborting slot selection")
            return False

        # Get preferred dates from reservation
        preferred_dates = reservation.get("preferred_dates", [])
        logger.info(f"Looking for preferred dates: {preferred_dates}")

        # Find available dates (green bordered cells)
        available_dates = await page.locator("a.fc-daygrid-day-number").all()

        selected_date = None
        for date_elem in available_dates:
            aria_label = await date_elem.get_attribute("aria-label")
            if aria_label:
                # Check if this date is in preferred dates
                # aria-label format: "23 Ocak 2026"
                parsed_date = self.parse_aria_label_to_date(aria_label)

                if parsed_date:
                    logger.debug(f"Available date: {parsed_date} (aria-label: {aria_label})")

                    # Check if this date matches any preferred date
                    if not preferred_dates or parsed_date in preferred_dates:
                        await date_elem.click()
                        selected_date = aria_label
                        logger.info(f"Selected date: {aria_label} ({parsed_date})")
                        break
                    else:
                        logger.debug(f"Skipping date {parsed_date} - not in preferred list")

        if not selected_date:
            if preferred_dates:
                logger.error(f"No preferred date available. Preferred: {preferred_dates}")
            else:
                logger.error("No available date found")
            return False

        # Wait for time slots to load
        await asyncio.sleep(Delays.TIME_SLOTS_LOAD_WAIT)
        await self.wait_for_overlay(page)

        # Select time (preference: 09:00+)
        time_selected = await self.select_preferred_time(page)

        if not time_selected:
            logger.error("No time slot selected")
            return False

        # Click Continue
        await self.wait_for_overlay(page)
        await page.click(get_selector("continue_button"))
        await self.wait_for_overlay(page)

        logger.info("✅ Appointment slot selected")
        return True

    async def select_preferred_time(self, page: Page) -> bool:
        """
        Akıllı saat seçimi:
        - Öncelik 1: 09:00 ve sonrası slot (tercih edilen)
        - Öncelik 2: 08:00-08:59 arası slot (sadece 09:00+ yoksa)
        - 08:00 öncesi slotlar → alınmaz

        Args:
            page: Playwright page

        Returns:
            True if acceptable time selected
        """
        try:
            await page.wait_for_selector(get_selector("time_slot_button"), timeout=10000)
            time_buttons = await page.locator(get_selector("time_slot_button")).all()

            if not time_buttons:
                return False

            preferred_slots = []  # 09:00+
            fallback_slots = []  # 08:00-08:59

            for button in time_buttons:
                time_text = await button.text_content()
                if not time_text:
                    continue
                time_text = time_text.strip()

                try:
                    hour = int(time_text.split(":")[0])
                except (ValueError, IndexError):
                    continue

                if hour >= 9:
                    preferred_slots.append((button, time_text))
                elif hour >= 8:
                    fallback_slots.append((button, time_text))
                # hour < 8 → skip

            # Öncelik 1: 09:00+ slot
            if preferred_slots:
                button, time_text = preferred_slots[0]
                await button.click()
                logger.info(f"✅ Preferred time slot selected: {time_text} (09:00+)")
                return True

            # Öncelik 2: 08:00-09:00 arası (sadece 09:00+ yoksa)
            if fallback_slots:
                button, time_text = fallback_slots[0]
                await button.click()
                logger.info(
                    f"⚠️ Fallback time slot selected: {time_text} "
                    f"(08:00-09:00, no 09:00+ available)"
                )
                return True

            logger.warning("No acceptable time slots found (all before 08:00)")
            return False

        except Exception as e:
            logger.error(f"Error selecting time: {e}")
            return False

    async def handle_captcha_if_present(self, page: Page) -> bool:
        """
        Handle Captcha popup if present.

        Args:
            page: Playwright page

        Returns:
            True if handled or not present
        """
        try:
            captcha_modal = await page.locator(get_selector("captcha_modal")).count()

            if captcha_modal == 0:
                return True

            logger.warning("Captcha detected!")

            if self.captcha_solver:
                # Extract sitekey and solve
                sitekey = await page.evaluate(
                    """
                    () => {
                        const widget = document.querySelector('.cf-turnstile, [data-sitekey]');
                        return widget ? widget.getAttribute('data-sitekey') : null;
                    }
                """
                )

                if sitekey:
                    token = await self.captcha_solver.solve_turnstile(page.url, sitekey)
                    if token:
                        # Inject token
                        await page.evaluate(
                            """
                            (token) => {
                                const input = document.querySelector(
                                    '[name="cf-turnstile-response"]'
                                );
                                if (input) input.value = token;
                            }
                        """,
                            token,
                        )

                        # Click submit
                        await page.click(get_selector("captcha_submit"))
                        await self.wait_for_overlay(page)
                        logger.info("Captcha solved")
                        return True

            return False

        except Exception as e:
            logger.error(f"Captcha handling error: {e}")
            return False
