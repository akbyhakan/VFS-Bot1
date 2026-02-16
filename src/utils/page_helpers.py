"""Shared page interaction helpers for Playwright-based operations."""

import asyncio
from typing import List, Optional

from loguru import logger
from playwright.async_api import Page


async def wait_for_overlay_hidden(
    page: Page,
    selectors: List[str],
    timeout: int = 30000,
) -> None:
    """
    Wait for loading overlay to disappear.
    Tries multiple overlay selectors.

    Args:
        page: Playwright page
        selectors: List of CSS selectors to check for overlays
        timeout: Maximum wait time in ms
    """
    try:
        for selector in selectors:
            try:
                overlay = page.locator(selector)
                if await overlay.count() > 0:
                    await overlay.wait_for(state="hidden", timeout=timeout)
                    logger.debug(f"Overlay disappeared: {selector}")
                    return
            except Exception as e:
                logger.debug(f"Overlay selector '{selector}' not found or timed out: {e}")
                continue
    except Exception as e:
        logger.debug(f"Overlay not present or already hidden: {e}")
