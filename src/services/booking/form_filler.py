"""Form filling utilities for VFS booking system."""

import asyncio
import logging
import random
from typing import Any, Dict

from playwright.async_api import Page

from ...core.exceptions import SelectorNotFoundError
from .selector_utils import resolve_selector, try_selectors, get_selector

logger = logging.getLogger(__name__)


class FormFiller:
    """Handles form filling for VFS booking system."""

    def __init__(self, config: Dict[str, Any], human_sim: Any = None):
        """
        Initialize form filler.

        Args:
            config: Bot configuration
            human_sim: Human simulator instance
        """
        self.config = config
        self.human_sim = human_sim

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

    async def fill_applicant_form(self, page: Page, person: Dict[str, Any], index: int = 0) -> None:
        """
        Fill single applicant form with fallback selector support.

        Args:
            page: Playwright page
            person: Person data
            index: Person index (0-based)
        """
        logger.info(
            f"Filling form for person {index + 1}: {person['first_name']} {person['last_name']}"
        )

        # Wait for VFS requirement - optimized for subsequent forms
        if index == 0:
            vfs_wait = self.config.get("vfs", {}).get("form_wait_seconds", 21)
        else:
            vfs_wait = self.config.get("vfs", {}).get("subsequent_form_wait_seconds", 5)

        logger.info(f"Waiting {vfs_wait} seconds (VFS requirement)...")
        await asyncio.sleep(vfs_wait)

        # Child checkbox (if applicable)
        if person.get("is_child_with_parent", False):
            selectors = resolve_selector("child_checkbox")
            for selector in selectors:
                try:
                    checkbox = page.locator(selector)
                    if await checkbox.count() > 0 and not await checkbox.is_checked():
                        await checkbox.click()
                        logger.info("Child checkbox marked")
                        break
                except Exception:
                    continue

        # First name
        await self.human_type(page, "first_name", person["first_name"].upper())

        # Last name
        await self.human_type(page, "last_name", person["last_name"].upper())

        # Gender dropdown
        gender_dropdown_selectors = resolve_selector("gender_dropdown")
        await try_selectors(page, gender_dropdown_selectors, action="click")
        await asyncio.sleep(0.5)

        gender_option = "gender_female" if person["gender"].lower() == "female" else "gender_male"
        gender_selectors = resolve_selector(gender_option)
        await try_selectors(page, gender_selectors, action="click")

        # Birth date
        await self.human_type(page, "birth_date", person["birth_date"])

        # Nationality dropdown - Select Turkey
        nationality_selectors = resolve_selector("nationality_dropdown")
        await try_selectors(page, nationality_selectors, action="click")
        await asyncio.sleep(0.5)

        turkey_selectors = resolve_selector("nationality_turkey")
        await try_selectors(page, turkey_selectors, action="click")

        # Passport number
        await self.human_type(page, "passport_number", person["passport_number"].upper())

        # Passport expiry
        await self.human_type(page, "passport_expiry", person["passport_expiry_date"])

        # Phone code
        phone_code_selectors = resolve_selector("phone_code")
        for selector in phone_code_selectors:
            try:
                await page.fill(selector, person.get("phone_code", "90"))
                break
            except Exception as e:
                logger.debug(f"Phone code selector failed: {e}")
                continue

        # Phone number
        await self.human_type(page, "phone_number", person["phone_number"])

        # Email
        await self.human_type(page, "email", person["email"].upper())

        logger.info(f"Form filled for person {index + 1}")

    async def fill_all_applicants(self, page: Page, reservation: Dict[str, Any]) -> None:
        """
        Fill forms for all applicants.

        Args:
            page: Playwright page
            reservation: Reservation data with persons list
        """
        persons = reservation["persons"]
        total = len(persons)

        for index, person in enumerate(persons):
            current = index + 1
            logger.info(f"Processing applicant {current}/{total}...")

            # Fill form
            await self.fill_applicant_form(page, person, index)

            # Wait for overlay
            await self.wait_for_overlay(page)

            # Click Save
            await page.click(get_selector("save_button"))
            logger.info(f"Applicant {current}/{total} saved")

            # Wait for overlay
            await self.wait_for_overlay(page)

            # More persons to add?
            if current < total:
                # Click "Add Another Applicant"
                await page.click(get_selector("add_another_button"))
                await self.wait_for_overlay(page)
                logger.info("Opening form for next applicant...")
            else:
                # Last person - Click Continue
                await page.click(get_selector("continue_button"))
                await self.wait_for_overlay(page)
                logger.info("All applicants saved, continuing...")

        logger.info(f"✅ All {total} applicants processed successfully")
