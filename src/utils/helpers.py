"""Helper utilities for common bot operations."""

import asyncio
import random
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

from loguru import logger
from playwright.async_api import Page, TimeoutError

from ..constants import Intervals, Timeouts
from ..utils.masking import mask_email

__all__ = [
    "mask_sensitive_data",
    "smart_fill",
    "smart_click",
    "wait_for_selector_smart",
    "wait_for_element_with_retry",
    "random_delay",
    "safe_navigate",
    "safe_screenshot",
    "format_local_datetime",
]


def mask_sensitive_data(text: str) -> str:
    """
    Mask potentially sensitive data in log messages.

    Args:
        text: Text that may contain sensitive data

    Returns:
        Text with sensitive data masked
    """
    # Mask email addresses - more restrictive pattern to avoid false positives
    text = re.sub(
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        lambda m: mask_email(m.group()),
        text,
    )
    # Mask potential tokens/keys (long alphanumeric strings with word boundaries)
    text = re.sub(r"\b[A-Za-z0-9_-]{32,}\b", "***REDACTED***", text)
    return text


async def smart_fill(
    page: Page,
    selector: str,
    text: str,
    human_sim: Any = None,
    delay: Optional[float] = None,
    self_healing: Any = None,
    selector_path: Optional[str] = None,
    element_description: Optional[str] = None,
) -> None:
    """
    Fill input field with optional human simulation and self-healing.

    Args:
        page: Playwright page object
        selector: Element selector
        text: Text to fill
        human_sim: Optional HumanSimulator instance
        delay: Optional delay before filling (seconds)
        self_healing: Optional SelectorSelfHealing instance
        selector_path: Optional selector path for self-healing (e.g., "login.email")
        element_description: Optional description for self-healing (e.g., "email input field")
    """
    if delay:
        await asyncio.sleep(delay)

    try:
        if human_sim and hasattr(human_sim, "human_type"):
            await human_sim.human_type(page, selector, text)
        else:
            await page.fill(selector, text)
    except Exception as e:
        # Try self-healing if available
        if self_healing and selector_path and element_description:
            logger.info(f"Selector failed: {selector}, attempting self-healing...")
            try:
                new_selector = await self_healing.attempt_heal(
                    page=page,
                    selector_path=selector_path,
                    failed_selector=selector,
                    element_description=element_description,
                )

                if new_selector:
                    logger.info(f"Self-healing found new selector: {new_selector}")
                    # Retry with healed selector
                    if human_sim and hasattr(human_sim, "human_type"):
                        await human_sim.human_type(page, new_selector, text)
                    else:
                        await page.fill(new_selector, text)
                    return
            except Exception as heal_error:
                logger.warning(f"Self-healing failed: {heal_error}")

        # Re-raise original error if healing didn't work
        logger.error(f"Failed to fill selector '{selector}': {e}")
        raise


async def smart_click(
    page: Page,
    selector: str,
    human_sim: Any = None,
    delay: Optional[float] = None,
    self_healing: Any = None,
    selector_path: Optional[str] = None,
    element_description: Optional[str] = None,
) -> None:
    """
    Click element with optional human simulation and self-healing.

    Args:
        page: Playwright page object
        selector: Element selector
        human_sim: Optional HumanSimulator instance
        delay: Optional delay before clicking (seconds)
        self_healing: Optional SelectorSelfHealing instance
        selector_path: Optional selector path for self-healing (e.g., "login.submit_button")
        element_description: Optional description for self-healing (e.g., "submit button")
    """
    if delay:
        await asyncio.sleep(delay)

    try:
        if human_sim and hasattr(human_sim, "human_click"):
            await human_sim.human_click(page, selector)
        else:
            await page.click(selector)
    except Exception as e:
        # Try self-healing if available
        if self_healing and selector_path and element_description:
            logger.info(f"Selector failed: {selector}, attempting self-healing...")
            try:
                new_selector = await self_healing.attempt_heal(
                    page=page,
                    selector_path=selector_path,
                    failed_selector=selector,
                    element_description=element_description,
                )

                if new_selector:
                    logger.info(f"Self-healing found new selector: {new_selector}")
                    # Retry with healed selector
                    if human_sim and hasattr(human_sim, "human_click"):
                        await human_sim.human_click(page, new_selector)
                    else:
                        await page.click(new_selector)
                    return
            except Exception as heal_error:
                logger.warning(f"Self-healing failed: {heal_error}")

        # Re-raise original error if healing didn't work
        logger.error(f"Failed to click selector '{selector}': {e}")
        raise


async def wait_for_selector_smart(
    page: Page,
    selector: str,
    timeout: Optional[int] = None,
    state: Optional[Literal["attached", "detached", "hidden", "visible"]] = "visible",
) -> None:
    """
    Wait for selector with smart timeout.

    Args:
        page: Playwright page object
        selector: Element selector
        timeout: Optional timeout in milliseconds (defaults to Timeouts.SELECTOR_WAIT)
        state: Element state to wait for
    """
    timeout = timeout or Timeouts.SELECTOR_WAIT
    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
    except Exception as e:
        logger.error(f"Selector '{selector}' not found within {timeout}ms: {e}")
        raise


async def wait_for_element_with_retry(
    page: Page,
    selector: str,
    max_retries: int = 3,
    initial_timeout: int = 5000,
    backoff_factor: float = 1.5,
) -> bool:
    """
    Wait for element with exponential backoff retry.

    Args:
        page: Playwright page
        selector: CSS selector
        max_retries: Maximum retry attempts
        initial_timeout: Initial timeout in ms
        backoff_factor: Multiplier for each retry

    Returns:
        True if element found, False otherwise
    """
    timeout = initial_timeout

    for attempt in range(max_retries):
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            return True
        except TimeoutError:
            if attempt < max_retries - 1:
                logger.debug(f"Selector '{selector}' not found, retry {attempt + 1}/{max_retries}")
                timeout = int(timeout * backoff_factor)
            else:
                logger.warning(f"Selector '{selector}' not found after {max_retries} attempts")

    return False


async def random_delay(
    min_seconds: Optional[float] = None, max_seconds: Optional[float] = None
) -> None:
    """
    Add a random delay to simulate human behavior.

    Args:
        min_seconds: Minimum delay (defaults to Intervals.HUMAN_DELAY_MIN)
        max_seconds: Maximum delay (defaults to Intervals.HUMAN_DELAY_MAX)
    """
    min_val = min_seconds or Intervals.HUMAN_DELAY_MIN
    max_val = max_seconds or Intervals.HUMAN_DELAY_MAX
    delay = random.uniform(min_val, max_val)
    await asyncio.sleep(delay)


async def safe_navigate(
    page: Page,
    url: str,
    wait_until: Optional[
        Literal["commit", "domcontentloaded", "load", "networkidle"]
    ] = "networkidle",
    timeout: Optional[int] = None,
) -> bool:
    """
    Safely navigate to URL with error handling.

    ⚠️ SPA WARNING: This function should ONLY be used for initial page loads
    (e.g., login page). VFS Global is an Angular-based Single Page Application (SPA),
    and using page.goto() after login breaks the Angular router state and causes
    session loss.

    For navigation after login, use DOM element clicks + PageStateDetector instead.
    See src/utils/spa_navigation.py for SPA-safe navigation utilities.

    Args:
        page: Playwright page object
        url: URL to navigate to
        wait_until: Wait condition
        timeout: Optional timeout in milliseconds

    Returns:
        True if navigation successful
    """
    timeout = timeout or Timeouts.NAVIGATION
    try:
        await page.goto(url, wait_until=wait_until, timeout=timeout)
        return True
    except Exception as e:
        logger.error(f"Failed to navigate to {url}: {e}")
        return False


async def safe_screenshot(page: Page, filepath: str, full_page: bool = True) -> bool:
    """
    Safely take screenshot with error handling.

    Args:
        page: Playwright page object
        filepath: Path to save screenshot
        full_page: Whether to capture full page

    Returns:
        True if screenshot saved successfully
    """
    try:
        await page.screenshot(path=filepath, full_page=full_page)
        logger.info(f"Screenshot saved: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save screenshot to {filepath}: {e}")
        return False


def format_local_datetime(
    utc_dt: Optional[datetime] = None,
    tz_name: str = "Europe/Istanbul",
    fmt: str = "%d.%m.%Y %H:%M:%S",
) -> str:
    """
    Convert UTC datetime to local timezone and format it for display.

    Args:
        utc_dt: UTC datetime to convert. If None, uses current UTC time.
        tz_name: Timezone name (default: "Europe/Istanbul")
        fmt: strftime format string (default: "%d.%m.%Y %H:%M:%S")

    Returns:
        Formatted datetime string in local timezone
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)

    # Ensure UTC datetime is timezone-aware
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    try:
        # Convert to local timezone
        local_tz = ZoneInfo(tz_name)
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime(fmt)
    except Exception as e:
        logger.error(f"Error converting timezone: {e}, falling back to UTC")
        return utc_dt.strftime(fmt)
