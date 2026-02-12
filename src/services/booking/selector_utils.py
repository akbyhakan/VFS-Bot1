"""Selector resolution utilities for VFS booking system."""

from typing import List

from loguru import logger
from playwright.async_api import Page

from src.constants import DOUBLE_MATCH_PATTERNS, TURKISH_MONTHS
from src.selector import get_selector_manager

from ...core.exceptions import SelectorNotFoundError


def resolve_selector(selector_key: str) -> List[str]:
    """
    Resolve a selector key to a list of selectors via CountryAwareSelectorManager.

    Args:
        selector_key: Dot-path like "booking.first_name" or flat key like "first_name"

    Returns:
        List of selector strings (primary + fallbacks)
    """
    manager = get_selector_manager()

    # Support both flat keys ("first_name") and dot-path ("booking.first_name")
    path = f"booking.{selector_key}" if "." not in selector_key else selector_key

    try:
        all_selectors = manager.get_all(path)
        if all_selectors:
            return all_selectors
    except Exception:
        pass

    # Fallback: try the key as-is (direct CSS/XPath selector)
    return [selector_key]


def get_selector(selector_key: str) -> str:
    """
    Get a single selector string.
    Returns the primary selector from CountryAwareSelectorManager.

    Args:
        selector_key: Selector key (e.g., "first_name" or "booking.first_name")

    Returns:
        First selector string
    """
    selectors = resolve_selector(selector_key)
    return selectors[0]


def get_selector_with_fallback(selector_name: str) -> List[str]:
    """
    Get selector(s) for a given name, ensuring it's always a list for fallback support.

    Args:
        selector_name: Name of the selector (e.g., "first_name" or "booking.first_name")

    Returns:
        List of selector strings to try in order
    """
    selectors = resolve_selector(selector_name)
    if not selectors or selectors == [selector_name]:
        # Check if this was a valid key
        manager = get_selector_manager()
        path = f"booking.{selector_name}" if "." not in selector_name else selector_name
        result = manager.get(path)
        if result is None:
            raise ValueError(f"Unknown selector name: {selector_name}")
    return selectors


async def try_selectors(
    page: Page,
    selectors: List[str],
    action: str = "click",
    text: str | None = None,
    timeout: int = 5000,
) -> bool:
    """
    Try multiple selectors in order until one works.

    Args:
        page: Playwright page
        selectors: List of CSS/XPath selectors to try
        action: 'click', 'fill', 'wait', 'count'
        text: Text to fill (for 'fill' action)
        timeout: Timeout per selector in ms

    Returns:
        True if action succeeded, False otherwise

    Raises:
        SelectorNotFoundError: If no selector works
    """
    for selector in selectors:
        try:
            element = page.locator(selector)

            if action == "click":
                await element.click(timeout=timeout)
                return True
            elif action == "fill":
                await element.fill(text or "", timeout=timeout)
                return True
            elif action == "wait":
                await element.wait_for(timeout=timeout)
                return True
            elif action == "count":
                count = await element.count()
                return bool(count > 0)
            elif action == "wait_hidden":
                await element.wait_for(state="hidden", timeout=timeout)
                return True

        except Exception:
            continue

    # No selector worked
    raise SelectorNotFoundError(
        selector_name=str(selectors[0]) if selectors else "unknown", tried_selectors=selectors
    )
