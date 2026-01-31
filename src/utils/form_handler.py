"""Standardized form handling utilities to eliminate code duplication."""

import asyncio
import logging
from typing import Optional, List, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.constants import Delays, Timeouts
from src.core.exceptions import SelectorNotFoundError

logger = logging.getLogger(__name__)


class FormHandler:
    """Handles common form interactions with human-like behavior."""

    def __init__(self, human_simulator: Optional[Any] = None):
        """
        Initialize form handler.

        Args:
            human_simulator: Optional human simulation instance for realistic interactions
        """
        self.human_sim = human_simulator

    async def select_dropdown(
        self,
        page: Page,
        selector: str,
        value: str,
        wait_after: float = Delays.DROPDOWN_WAIT,
        timeout: float = Timeouts.SELECTOR_WAIT,
    ) -> bool:
        """
        Select dropdown option with proper waiting.

        Args:
            page: Playwright page object
            selector: CSS selector for dropdown
            value: Option label or value to select
            wait_after: Time to wait after selection (seconds)
            timeout: Timeout for waiting for selector (milliseconds)

        Returns:
            True if successful

        Raises:
            SelectorNotFoundError: If selector not found
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)

            # Add human-like delay before interaction
            if self.human_sim:
                await self.human_sim.random_delay()

            await page.select_option(selector, label=value)

            # Wait for any dynamic updates after selection
            await asyncio.sleep(wait_after)

            logger.debug(f"Selected '{value}' from dropdown '{selector}'")
            return True

        except PlaywrightTimeout:
            logger.error(f"Timeout waiting for dropdown selector: {selector}")
            raise SelectorNotFoundError(selector)
        except Exception as e:
            logger.error(f"Failed to select '{value}' from '{selector}': {e}")
            raise SelectorNotFoundError(selector) from e

    async def fill_input(
        self,
        page: Page,
        selector: str,
        value: str,
        clear_first: bool = True,
        human_typing: bool = False,
        timeout: float = Timeouts.SELECTOR_WAIT,
    ) -> bool:
        """
        Fill input field with optional human simulation.

        Args:
            page: Playwright page object
            selector: CSS selector for input field
            value: Value to fill
            clear_first: Whether to clear field first
            human_typing: Use human-like typing if human_sim is available
            timeout: Timeout for waiting for selector (milliseconds)

        Returns:
            True if successful

        Raises:
            SelectorNotFoundError: If selector not found
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)

            # Add human-like delay before interaction
            if self.human_sim:
                await self.human_sim.random_delay()

            # Clear field if requested
            if clear_first:
                await page.fill(selector, "")
                await asyncio.sleep(0.1)

            # Fill with human-like typing or instant fill
            if human_typing and self.human_sim:
                await self.human_sim.human_type(page, selector, value)
            else:
                await page.fill(selector, value)

            logger.debug(f"Filled input '{selector}' with value (length: {len(value)})")
            return True

        except PlaywrightTimeout:
            logger.error(f"Timeout waiting for input selector: {selector}")
            raise SelectorNotFoundError(selector)
        except Exception as e:
            logger.error(f"Failed to fill input '{selector}': {e}")
            raise SelectorNotFoundError(selector) from e

    async def click_button(
        self,
        page: Page,
        selector: str,
        wait_for_navigation: bool = False,
        wait_after: float = 0.5,
        timeout: float = Timeouts.SELECTOR_WAIT,
    ) -> bool:
        """
        Click button with proper waiting.

        Args:
            page: Playwright page object
            selector: CSS selector for button
            wait_for_navigation: Whether to wait for navigation after click
            wait_after: Time to wait after click (seconds)
            timeout: Timeout for waiting for selector (milliseconds)

        Returns:
            True if successful

        Raises:
            SelectorNotFoundError: If selector not found
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)

            # Add human-like delay before interaction
            if self.human_sim:
                await self.human_sim.random_delay()

            if wait_for_navigation:
                async with page.expect_navigation(timeout=timeout):
                    await page.click(selector)
            else:
                await page.click(selector)
                await asyncio.sleep(wait_after)

            logger.debug(f"Clicked button '{selector}'")
            return True

        except PlaywrightTimeout:
            logger.error(f"Timeout waiting for button selector: {selector}")
            raise SelectorNotFoundError(selector)
        except Exception as e:
            logger.error(f"Failed to click button '{selector}': {e}")
            raise SelectorNotFoundError(selector) from e

    async def check_checkbox(
        self,
        page: Page,
        selector: str,
        checked: bool = True,
        timeout: float = Timeouts.SELECTOR_WAIT,
    ) -> bool:
        """
        Check or uncheck a checkbox.

        Args:
            page: Playwright page object
            selector: CSS selector for checkbox
            checked: Whether to check (True) or uncheck (False)
            timeout: Timeout for waiting for selector (milliseconds)

        Returns:
            True if successful

        Raises:
            SelectorNotFoundError: If selector not found
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)

            # Add human-like delay before interaction
            if self.human_sim:
                await self.human_sim.random_delay()

            await page.set_checked(selector, checked)

            logger.debug(f"Set checkbox '{selector}' to {checked}")
            return True

        except PlaywrightTimeout:
            logger.error(f"Timeout waiting for checkbox selector: {selector}")
            raise SelectorNotFoundError(selector)
        except Exception as e:
            logger.error(f"Failed to set checkbox '{selector}': {e}")
            raise SelectorNotFoundError(selector) from e

    async def fill_form(
        self,
        page: Page,
        fields: List[dict],
        submit_selector: Optional[str] = None,
    ) -> bool:
        """
        Fill multiple form fields in sequence.

        Args:
            page: Playwright page object
            fields: List of field dictionaries with 'selector', 'value', and optional 'type'
                   Example: [
                       {'selector': '#name', 'value': 'John', 'type': 'input'},
                       {'selector': '#country', 'value': 'USA', 'type': 'dropdown'}
                   ]
            submit_selector: Optional submit button selector to click after filling

        Returns:
            True if successful

        Raises:
            SelectorNotFoundError: If any selector not found
        """
        try:
            for field in fields:
                selector = field["selector"]
                value = field["value"]
                field_type = field.get("type", "input")

                if field_type == "input":
                    await self.fill_input(page, selector, value)
                elif field_type == "dropdown":
                    await self.select_dropdown(page, selector, value)
                elif field_type == "checkbox":
                    checked = value in [True, "true", "True", "1", 1]
                    await self.check_checkbox(page, selector, checked)
                else:
                    logger.warning(f"Unknown field type: {field_type}, using fill_input")
                    await self.fill_input(page, selector, value)

                # Small delay between fields for realistic interaction
                if self.human_sim:
                    await self.human_sim.random_delay()

            # Submit form if selector provided
            if submit_selector:
                await self.click_button(page, submit_selector)

            logger.info(f"Form filled successfully ({len(fields)} fields)")
            return True

        except Exception as e:
            logger.error(f"Failed to fill form: {e}")
            raise

    async def wait_for_element(
        self,
        page: Page,
        selector: str,
        state: str = "visible",
        timeout: float = Timeouts.SELECTOR_WAIT,
    ) -> bool:
        """
        Wait for element to reach desired state.

        Args:
            page: Playwright page object
            selector: CSS selector
            state: Element state to wait for (visible, hidden, attached, detached)
            timeout: Timeout in milliseconds

        Returns:
            True if element reached state

        Raises:
            SelectorNotFoundError: If timeout reached
        """
        try:
            from typing import Literal, cast

            # Cast state to proper Literal type for type checking
            valid_state = cast(Literal["attached", "detached", "hidden", "visible"], state)
            await page.wait_for_selector(selector, state=valid_state, timeout=timeout)
            logger.debug(f"Element '{selector}' reached state: {state}")
            return True

        except PlaywrightTimeout:
            logger.error(f"Timeout waiting for element '{selector}' to be {state}")
            raise SelectorNotFoundError(selector)
        except Exception as e:
            logger.error(f"Failed waiting for element '{selector}': {e}")
            raise SelectorNotFoundError(selector) from e

    async def get_element_text(
        self,
        page: Page,
        selector: str,
        timeout: float = Timeouts.SELECTOR_WAIT,
    ) -> Optional[str]:
        """
        Get text content of an element.

        Args:
            page: Playwright page object
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            Element text or None if not found
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            text = await page.text_content(selector)
            # text_content returns str | None
            if isinstance(text, str):
                return text
            return None

        except PlaywrightTimeout:
            logger.error(f"Timeout waiting for element: {selector}")
            return None
        except Exception as e:
            logger.error(f"Failed to get text from '{selector}': {e}")
            return None

    async def is_element_visible(
        self,
        page: Page,
        selector: str,
        timeout: float = 2000,
    ) -> bool:
        """
        Check if element is visible on page.

        Args:
            page: Playwright page object
            selector: CSS selector
            timeout: Timeout in milliseconds (short default for checking)

        Returns:
            True if element is visible, False otherwise
        """
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except (PlaywrightTimeout, Exception):
            return False
