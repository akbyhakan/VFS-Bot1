"""Helper utilities for common bot operations."""

import asyncio
import random
import logging
import re
from typing import Optional, Literal

from playwright.async_api import Page

from ..constants import Intervals, Timeouts

logger = logging.getLogger(__name__)


def mask_email(email: str) -> str:
    """
    Mask email for safe logging.

    Args:
        email: Email address to mask

    Returns:
        Masked email address
    """
    if not email or "@" not in email:
        return "***"
    parts = email.split("@")
    masked_local = parts[0][:2] + "***" if len(parts[0]) > 2 else "***"
    return f"{masked_local}@{parts[1]}"


def mask_sensitive_data(text: str) -> str:
    """
    Mask potentially sensitive data in log messages.

    Args:
        text: Text that may contain sensitive data

    Returns:
        Text with sensitive data masked
    """
    # Mask email addresses
    text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", lambda m: mask_email(m.group()), text)
    # Mask potential tokens/keys (long alphanumeric strings)
    text = re.sub(r"[A-Za-z0-9_-]{32,}", "***REDACTED***", text)
    return text


async def smart_fill(
    page: Page,
    selector: str,
    text: str,
    human_sim: Optional[object] = None,
    delay: Optional[float] = None,
) -> None:
    """
    Fill input field with optional human simulation.

    Args:
        page: Playwright page object
        selector: Element selector
        text: Text to fill
        human_sim: Optional HumanSimulator instance
        delay: Optional delay before filling (seconds)
    """
    if delay:
        await asyncio.sleep(delay)

    try:
        if human_sim and hasattr(human_sim, "human_type"):
            await human_sim.human_type(page, selector, text)
        else:
            await page.fill(selector, text)
    except Exception as e:
        logger.error(f"Failed to fill selector '{selector}': {e}")
        raise


async def smart_click(
    page: Page,
    selector: str,
    human_sim: Optional[object] = None,
    delay: Optional[float] = None,
) -> None:
    """
    Click element with optional human simulation.

    Args:
        page: Playwright page object
        selector: Element selector
        human_sim: Optional HumanSimulator instance
        delay: Optional delay before clicking (seconds)
    """
    if delay:
        await asyncio.sleep(delay)

    try:
        if human_sim and hasattr(human_sim, "human_click"):
            await human_sim.human_click(page, selector)
        else:
            await page.click(selector)
    except Exception as e:
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
