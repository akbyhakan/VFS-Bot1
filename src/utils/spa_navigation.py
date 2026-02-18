"""SPA-aware navigation utilities for VFS browser automation.

VFS Global is an Angular-based Single Page Application (SPA).
URL-based navigation (page.goto) breaks Angular router state and causes session loss.

RULE: page.goto() is ONLY allowed for the initial login page load.
All other navigation MUST use DOM element clicks + PageStateDetector.
"""

import asyncio
from typing import Any, FrozenSet, Optional

from loguru import logger
from playwright.async_api import Page


async def navigate_to_appointment_page(
    page: Page,
    page_state_detector: Any,
    human_sim: Optional[Any] = None,
    max_wait: float = 15.0,
) -> bool:
    """
    Navigate to appointment page using SPA-safe DOM clicks.

    NEVER uses page.goto() — always clicks navigation elements within the SPA.

    Args:
        page: Playwright page object
        page_state_detector: PageStateDetector instance
        human_sim: Optional HumanSimulator for realistic clicks
        max_wait: Maximum wait time for state stabilization

    Returns:
        True if successfully on appointment page

    Raises:
        VFSBotError: If navigation fails and recovery is needed
    """
    from ..core.exceptions import VFSBotError
    from ..services.bot.page_state_detector import PageState

    # Step 1: Detect current state
    state = await page_state_detector.detect(page)

    # Step 2: Already on appointment page
    if state.is_on_appointment_page and state.confidence >= 0.70:
        logger.debug("SPA nav: already on appointment page")
        return True

    # Step 3: Recovery needed — don't try to navigate, let caller re-login
    if state.needs_recovery:
        raise VFSBotError(
            f"Page recovery needed: {state.state.name}",
            recoverable=True,
        )

    # Step 4: On dashboard — click appointment link
    if state.state == PageState.DASHBOARD:
        logger.info("SPA nav: navigating from dashboard to appointment page via click")

        # Try multiple selectors for appointment navigation
        nav_selectors = [
            'a[href*="appointment"]',
            'a[routerlink*="appointment"]',
            "text=/Randevu|Appointment/i",
            "mat-list-item >> text=/Randevu|Appointment/i",
            ".sidebar a >> text=/Randevu|Appointment/i",
        ]

        clicked = False
        for selector in nav_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() > 0:
                    if human_sim and hasattr(human_sim, "human_click"):
                        await human_sim.human_click(page, selector)
                    else:
                        await locator.click(timeout=5000)
                    clicked = True
                    logger.debug(f"SPA nav: clicked '{selector}'")
                    break
            except Exception:
                continue

        if not clicked:
            raise VFSBotError(
                "Could not find appointment navigation link on dashboard",
                recoverable=True,
            )

        # Wait for appointment page to load
        result = await page_state_detector.wait_for_stable_state(
            page,
            expected_states=frozenset({PageState.APPOINTMENT_PAGE}),
            max_wait=max_wait,
        )

        if result.is_on_appointment_page:
            logger.info("SPA nav: successfully navigated to appointment page")
            return True
        else:
            raise VFSBotError(
                f"Failed to navigate to appointment page, got: {result.state.name}",
                recoverable=True,
            )

    # Step 5: Unknown or other state — can't navigate safely
    raise VFSBotError(
        f"Cannot navigate to appointment page from state: {state.state.name} "
        f"(confidence: {state.confidence:.0%}). Re-login required.",
        recoverable=True,
    )
