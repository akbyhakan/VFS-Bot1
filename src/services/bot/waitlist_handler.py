"""Waitlist handling service for VFS appointments."""

import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from ...constants import Delays
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.helpers import smart_click

logger = logging.getLogger(__name__)


class WaitlistHandler:
    """Handles waitlist flow for VFS appointments."""

    def __init__(
        self,
        config: Dict[str, Any],
        human_sim: Optional[HumanSimulator] = None,
    ):
        """
        Initialize waitlist handler.

        Args:
            config: Bot configuration dictionary
            human_sim: Optional HumanSimulator for realistic interactions
        """
        self.config = config
        self.human_sim = human_sim
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)

    async def detect_waitlist_mode(self, page: Page) -> bool:
        """
        Detect if waitlist mode is active on the current page.

        Args:
            page: Playwright page object

        Returns:
            True if waitlist is detected, False otherwise
        """
        try:
            # Check for waitlist text on page
            waitlist_indicators = [
                "Bekleme Listesi",
                "Waitlist",
                "bekleme listesi",
                "waitlist",
            ]

            for indicator in waitlist_indicators:
                try:
                    # Try to find the text with a short timeout
                    locator = page.locator(f"text={indicator}").first
                    await locator.wait_for(timeout=2000, state="visible")
                    logger.info(f"Waitlist mode detected: found '{indicator}'")
                    return True
                except Exception:
                    continue

            logger.info("Waitlist mode not detected")
            return False

        except Exception as e:
            logger.error(f"Error detecting waitlist mode: {e}")
            return False

    async def join_waitlist(self, page: Page) -> bool:
        """
        Check the waitlist checkbox on Application Details screen.

        Args:
            page: Playwright page object

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find waitlist checkbox
            waitlist_selectors = [
                "//mat-checkbox[.//span[contains(text(), 'Waitlist')]]",
                "//mat-checkbox[.//span[contains(text(), 'Bekleme Listesi')]]",
                "mat-checkbox:has-text('Waitlist')",
                "mat-checkbox:has-text('Bekleme Listesi')",
            ]

            checkbox = None
            for selector in waitlist_selectors:
                try:
                    locator = page.locator(selector).first
                    await locator.wait_for(timeout=5000, state="visible")
                    checkbox = locator
                    logger.info(f"Found waitlist checkbox with selector: {selector}")
                    break
                except Exception:
                    continue

            if not checkbox:
                logger.error("Waitlist checkbox not found")
                return False

            # Check if already selected
            class_attr = await checkbox.get_attribute("class")
            if class_attr and "mat-mdc-checkbox-checked" in class_attr:
                logger.info("Waitlist checkbox already selected")
                return True

            # Click the checkbox input
            input_element = checkbox.locator("input").first
            await input_element.click()
            logger.info("Waitlist checkbox checked successfully")

            # Wait a bit for UI to update
            await asyncio.sleep(random.uniform(*Delays.AFTER_CLICK_CHECK))

            return True

        except Exception as e:
            logger.error(f"Error joining waitlist: {e}")
            return False

    async def accept_review_checkboxes(self, page: Page) -> bool:
        """
        Check all three checkboxes on Review and Pay screen.

        Args:
            page: Playwright page object

        Returns:
            True if successful, False otherwise
        """
        try:
            # Checkbox 1: Terms and Conditions
            terms_checked = await self._check_checkbox(
                page,
                ['input[value="consent.checkbox_value.vas_term_condition"]'],
                "Terms and Conditions",
            )

            # Checkbox 2: Marketing
            marketing_checked = await self._check_checkbox(
                page,
                ['input[value="consent.checkbox_value.receive_mkt_info"]'],
                "Marketing",
            )

            # Checkbox 3: Waitlist Consent
            waitlist_consent_checked = await self._check_checkbox(
                page,
                [
                    "mat-checkbox:has-text('bekleme listesi') input",
                    "mat-checkbox:has-text('waitlist') input",
                ],
                "Waitlist Consent",
            )

            success = terms_checked and marketing_checked and waitlist_consent_checked
            if success:
                logger.info("All review checkboxes checked successfully")
            else:
                logger.warning(
                    f"Some checkboxes failed: terms={terms_checked}, "
                    f"marketing={marketing_checked}, waitlist={waitlist_consent_checked}"
                )

            return success

        except Exception as e:
            logger.error(f"Error accepting review checkboxes: {e}")
            return False

    async def _check_checkbox(self, page: Page, selectors: List[str], name: str) -> bool:
        """
        Helper method to check a single checkbox.

        Args:
            page: Playwright page object
            selectors: List of selectors to try
            name: Name of the checkbox for logging

        Returns:
            True if successful, False otherwise
        """
        try:
            checkbox = None
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    await locator.wait_for(timeout=5000, state="visible")
                    checkbox = locator
                    logger.info(f"Found {name} checkbox with selector: {selector}")
                    break
                except Exception:
                    continue

            if not checkbox:
                logger.warning(f"{name} checkbox not found")
                return False

            # Check if already selected
            is_checked = await checkbox.is_checked()
            if is_checked:
                logger.info(f"{name} checkbox already checked")
                return True

            # Click the checkbox
            await checkbox.click()
            logger.info(f"{name} checkbox checked")

            # Wait a bit for UI to update
            await asyncio.sleep(random.uniform(0.3, 0.7))

            return True

        except Exception as e:
            logger.error(f"Error checking {name} checkbox: {e}")
            return False

    async def click_confirm_button(self, page: Page) -> bool:
        """
        Click the Confirm button on Review and Pay screen.

        Args:
            page: Playwright page object

        Returns:
            True if successful, False otherwise
        """
        try:
            confirm_selectors = [
                'button:has(span.mdc-button__label:text("Onayla"))',
                'button:has-text("Onayla")',
                'button:has-text("Confirm")',
            ]

            button = None
            working_selector = None
            for selector in confirm_selectors:
                try:
                    locator = page.locator(selector).first
                    await locator.wait_for(timeout=5000, state="visible")
                    button = locator
                    working_selector = selector
                    logger.info(f"Found confirm button with selector: {selector}")
                    break
                except Exception:
                    continue

            if not button:
                logger.error("Confirm button not found")
                return False

            # Click with human simulation if available
            if self.human_sim and working_selector:
                await smart_click(page, working_selector, self.human_sim)
            else:
                await button.click()

            logger.info("Confirm button clicked successfully")

            # Wait for navigation/processing
            await asyncio.sleep(random.uniform(2.0, 3.0))

            return True

        except Exception as e:
            logger.error(f"Error clicking confirm button: {e}")
            return False

    async def handle_waitlist_success(
        self, page: Page, login_email: str
    ) -> Optional[Dict[str, Any]]:
        """
        Handle waitlist success screen: take screenshot and extract details.

        Args:
            page: Playwright page object
            login_email: Email used for login

        Returns:
            Dictionary with waitlist details or None if failed
        """
        try:
            # Detect success screen
            if not await self._detect_success_screen(page):
                logger.error("Success screen not detected")
                return None

            # Take full page screenshot
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.screenshots_dir / f"waitlist_success_{timestamp}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")

            # Extract details from page
            details = await self.extract_waitlist_details(page)
            details["login_email"] = login_email
            details["screenshot_path"] = str(screenshot_path)
            details["timestamp"] = timestamp

            logger.info(f"Waitlist success handled: {details}")
            return details

        except Exception as e:
            logger.error(f"Error handling waitlist success: {e}")
            return None

    async def _detect_success_screen(self, page: Page) -> bool:
        """
        Detect if we're on the success screen.

        Args:
            page: Playwright page object

        Returns:
            True if success screen detected, False otherwise
        """
        try:
            success_indicators = [
                "Bekleme Listesinde",
                "İşlem Özeti",
                "Waitlist",
            ]

            for indicator in success_indicators:
                try:
                    locator = page.locator(f"text={indicator}").first
                    await locator.wait_for(timeout=5000, state="visible")
                    logger.info(f"Success screen detected: found '{indicator}'")
                    return True
                except Exception as e:
                    logger.debug(f"Success indicator '{indicator}' not found: {e}")
                    continue

            return False

        except Exception as e:
            logger.error(f"Error detecting success screen: {e}")
            return False

    async def extract_waitlist_details(self, page: Page) -> Dict[str, Any]:
        """
        Extract waitlist details from success page.

        Args:
            page: Playwright page object

        Returns:
            Dictionary with extracted details
        """
        details: Dict[str, Any] = {
            "reference_number": "",
            "people": [],
            "country": "",
            "centre": "",
            "category": "",
            "subcategory": "",
            "total_amount": "",
        }

        try:
            # Get page content for extraction
            content = await page.content()

            # Extract reference number
            # Try common patterns for reference number
            ref_patterns = [
                r"Referans(?:\s*Numarası)?[:\s]+([A-Z0-9-]+)",
                r"Reference(?:\s*Number)?[:\s]+([A-Z0-9-]+)",
                r"Başvuru(?:\s*Numarası)?[:\s]+([A-Z0-9-]+)",
            ]
            import re

            for pattern in ref_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    details["reference_number"] = match.group(1)
                    break

            # Try to extract person names from visible text
            # This is a best-effort extraction with limitations:
            # - Assumes Western naming conventions (Capitalized First Last)
            # - May not work for names with prefixes, suffixes, or multiple capitals
            # - May not work for non-Western naming patterns
            try:
                # Look for name patterns in the page
                name_elements = await page.locator("text=/[A-Z][a-z]+\\s+[A-Z][a-z]+/").all()
                for element in name_elements[:5]:  # Limit to first 5 matches
                    try:
                        text = await element.text_content()
                        if text and len(text.strip().split()) >= 2:
                            details["people"].append(text.strip())
                    except Exception as e:
                        logger.debug(f"Could not extract text from name element: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Could not extract person names: {e}")

            # Extract other details from page text
            # These are best-effort extractions
            try:
                page_text = await page.text_content("body")
                if page_text:
                    # Try to extract country
                    country_match = re.search(
                        r"(?:Ülke|Country)[:\s]+([^\n]+)", page_text, re.IGNORECASE
                    )
                    if country_match:
                        details["country"] = country_match.group(1).strip()

                    # Try to extract centre
                    centre_match = re.search(
                        r"(?:Merkez|Centre|Center)[:\s]+([^\n]+)", page_text, re.IGNORECASE
                    )
                    if centre_match:
                        details["centre"] = centre_match.group(1).strip()

                    # Try to extract category
                    category_match = re.search(
                        r"(?:Kategori|Category)[:\s]+([^\n]+)", page_text, re.IGNORECASE
                    )
                    if category_match:
                        details["category"] = category_match.group(1).strip()

                    # Try to extract subcategory
                    subcategory_match = re.search(
                        r"(?:Alt Kategori|Subcategory)[:\s]+([^\n]+)",
                        page_text,
                        re.IGNORECASE,
                    )
                    if subcategory_match:
                        details["subcategory"] = subcategory_match.group(1).strip()

                    # Try to extract total amount
                    amount_match = re.search(
                        r"(?:Toplam|Total)[^\n]*[:\s]+([0-9.,]+\s*[A-Z]{3})",
                        page_text,
                        re.IGNORECASE,
                    )
                    if amount_match:
                        details["total_amount"] = amount_match.group(1).strip()

            except Exception as e:
                logger.warning(f"Could not extract page details: {e}")

            logger.info(f"Extracted waitlist details: {details}")

        except Exception as e:
            logger.error(f"Error extracting waitlist details: {e}")

        return details
