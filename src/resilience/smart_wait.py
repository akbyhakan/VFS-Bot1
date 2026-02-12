"""3-stage selector resolution pipeline with semantic, CSS, and AI repair."""

import asyncio
from typing import List, Optional

from loguru import logger
from playwright.async_api import Locator, Page

from src.constants import Resilience
from src.core.exceptions import SelectorNotFoundError


class SmartWait:
    """
    3-stage selector resolution pipeline:
    1. Semantic locators (role, label, text, placeholder)
    2. CSS selectors with exponential backoff retry and learning-based ordering
    3. AI-powered repair (if enabled)
    """

    def __init__(
        self,
        selector_manager: any,
        ai_repair: Optional[any] = None,
        max_retries: int = Resilience.SMART_WAIT_MAX_RETRIES,
        backoff_factor: float = Resilience.SMART_WAIT_BACKOFF_FACTOR,
    ):
        """
        Initialize SmartWait.

        Args:
            selector_manager: HotReloadableSelectorManager instance
            ai_repair: Optional AIRepairV2 instance
            max_retries: Maximum retry attempts per selector
            backoff_factor: Exponential backoff multiplier
        """
        self.selector_manager = selector_manager
        self.ai_repair = ai_repair
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def find_element(
        self,
        page: Page,
        selector_path: str,
        timeout: int = 10000,
        action_context: Optional[str] = None,
    ) -> Locator:
        """
        Find element using 3-stage pipeline.

        Args:
            page: Playwright page object
            selector_path: Dot-separated selector path
            timeout: Timeout in milliseconds
            action_context: Optional context for error reporting

        Returns:
            Element locator

        Raises:
            SelectorNotFoundError: If all stages fail
        """
        logger.debug(f"🔍 SmartWait: Finding element for path: {selector_path}")

        # Stage 1: Try semantic locators first (most resilient)
        semantic_locator = await self._try_semantic_locator(page, selector_path, timeout)
        if semantic_locator:
            logger.info(f"✅ Stage 1 (Semantic): Found element for {selector_path}")
            return semantic_locator

        # Stage 2: Try CSS selectors with exponential backoff
        css_locator = await self._try_css_selectors(page, selector_path, timeout)
        if css_locator:
            logger.info(f"✅ Stage 2 (CSS): Found element for {selector_path}")
            return css_locator

        # Stage 3: Try AI repair (if enabled)
        if self.ai_repair and self.ai_repair.enabled:
            ai_locator = await self._try_ai_repair(page, selector_path, timeout)
            if ai_locator:
                logger.info(f"✅ Stage 3 (AI): Found element for {selector_path}")
                return ai_locator

        # All stages failed - raise exception
        tried_selectors = self.selector_manager.get_with_fallback(selector_path)
        error_message = f"All stages failed for path: {selector_path}"
        if action_context:
            error_message += f" (context: {action_context})"

        logger.error(error_message)
        raise SelectorNotFoundError(selector_name=selector_path, tried_selectors=tried_selectors)

    async def _try_semantic_locator(
        self, page: Page, selector_path: str, timeout: int
    ) -> Optional[Locator]:
        """
        Stage 1: Try semantic locators.

        Args:
            page: Playwright page object
            selector_path: Selector path
            timeout: Timeout in milliseconds

        Returns:
            Locator or None
        """
        try:
            semantic = self.selector_manager._get_semantic(selector_path)
            if semantic:
                logger.debug(f"🎯 Stage 1: Trying semantic locators for {selector_path}")
                locator = await self.selector_manager._try_semantic_locator(
                    page, semantic, timeout
                )
                if locator:
                    return locator
        except Exception as e:
            logger.debug(f"Stage 1 (Semantic) failed: {e}")

        return None

    async def _try_css_selectors(
        self, page: Page, selector_path: str, timeout: int
    ) -> Optional[Locator]:
        """
        Stage 2: Try CSS selectors with exponential backoff retry.

        Args:
            page: Playwright page object
            selector_path: Selector path
            timeout: Timeout in milliseconds

        Returns:
            Locator or None
        """
        logger.debug(f"🎯 Stage 2: Trying CSS selectors for {selector_path}")

        # Get selectors with learning-based ordering
        selectors = self.selector_manager.get_with_fallback(selector_path)

        if not selectors:
            logger.debug(f"No CSS selectors found for {selector_path}")
            return None

        # Track original indices for learning
        original_indices = {selector: i for i, selector in enumerate(selectors)}

        # Apply learning-based reordering if learner is available
        if self.selector_manager.learner:
            selectors = self.selector_manager.learner.get_optimized_order(
                selector_path, selectors
            )

        # Try each selector with exponential backoff
        for selector in selectors:
            locator = await self._try_selector_with_backoff(page, selector, timeout)

            if locator:
                # Record success in learning system
                if self.selector_manager.learner:
                    original_idx = original_indices.get(selector, 0)
                    self.selector_manager.learner.record_success(selector_path, original_idx)

                return locator
            else:
                # Record failure in learning system
                if self.selector_manager.learner:
                    original_idx = original_indices.get(selector, 0)
                    self.selector_manager.learner.record_failure(selector_path, original_idx)

        return None

    async def _try_selector_with_backoff(
        self, page: Page, selector: str, timeout: int
    ) -> Optional[Locator]:
        """
        Try a single selector with exponential backoff retry.

        Args:
            page: Playwright page object
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            Locator or None
        """
        for attempt in range(self.max_retries):
            try:
                # Calculate timeout for this attempt with exponential backoff
                attempt_timeout = int(timeout * (self.backoff_factor**attempt))

                await page.wait_for_selector(selector, timeout=attempt_timeout, state="visible")
                logger.debug(
                    f"✅ Selector found on attempt {attempt + 1}/{self.max_retries}: {selector}"
                )
                return page.locator(selector)

            except Exception as e:
                logger.debug(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for {selector}: {e}"
                )

                # Wait before retry with exponential backoff
                if attempt < self.max_retries - 1:
                    backoff_delay = 0.5 * (self.backoff_factor**attempt)
                    await asyncio.sleep(backoff_delay)

        return None

    async def _try_ai_repair(
        self, page: Page, selector_path: str, timeout: int
    ) -> Optional[Locator]:
        """
        Stage 3: Try AI-powered repair.

        Args:
            page: Playwright page object
            selector_path: Selector path
            timeout: Timeout in milliseconds

        Returns:
            Locator or None
        """
        logger.warning(f"🤖 Stage 3: Trying AI repair for {selector_path}")

        try:
            # Get HTML content for AI analysis
            html_content = await page.content()

            # Generate element description
            element_description = self.selector_manager._generate_element_description(
                selector_path
            )

            # Get broken selector (primary)
            broken_selector = self.selector_manager.get(selector_path) or selector_path

            # Ask AI for repair
            repair_result = await self.ai_repair.repair_selector(
                html_content, broken_selector, element_description
            )

            if repair_result and repair_result.is_found:
                new_selector = repair_result.new_selector

                # Validate the suggestion
                try:
                    await page.wait_for_selector(new_selector, timeout=timeout, state="visible")
                    logger.info(f"✅ AI-suggested selector validated: {new_selector}")

                    # Persist to YAML
                    if self.ai_repair.persist_to_yaml(selector_path, new_selector):
                        # Reload selectors to pick up the change
                        self.selector_manager.reload()

                    return page.locator(new_selector)

                except Exception as e:
                    logger.warning(f"AI-suggested selector failed validation: {e}")
                    return None

        except Exception as e:
            logger.error(f"Stage 3 (AI) error: {e}")

        return None
