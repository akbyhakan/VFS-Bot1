"""Dynamic CSS selector management system."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from functools import lru_cache

import yaml
from playwright.async_api import Locator, Page

from src.core.exceptions import SelectorNotFoundError

logger = logging.getLogger(__name__)


class SelectorManager:
    """Manage CSS selectors from external configuration."""

    def __init__(self, selectors_file: str = "config/selectors.yaml"):
        """
        Initialize selector manager.

        Args:
            selectors_file: Path to selectors YAML file
        """
        self.selectors_file = Path(selectors_file)
        self._selectors: Dict[str, Any] = {}
        self.learner: Optional[Any] = None  # Type hint for SelectorLearner
        self.ai_repair: Optional[Any] = None  # Type hint for AISelectorRepair
        self._load_selectors()

        # Import and initialize learning system
        try:
            from src.utils.selector_learning import SelectorLearner

            self.learner = SelectorLearner()
            logger.info("♻️ Adaptive selector learning enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize selector learning: {e}")
            self.learner = None

        # Import and initialize AI repair system
        try:
            from src.utils.ai_selector_repair import AISelectorRepair

            self.ai_repair = AISelectorRepair(selectors_file)
        except Exception as e:
            logger.warning(f"Failed to initialize AI repair: {e}")
            self.ai_repair = None

    def _load_selectors(self) -> None:
        """Load selectors from YAML file."""
        try:
            if not self.selectors_file.exists():
                logger.warning(f"Selectors file not found: {self.selectors_file}")
                logger.info("Using default selectors")
                self._selectors = self._get_default_selectors()
                return

            with open(self.selectors_file, "r", encoding="utf-8") as f:
                self._selectors = yaml.safe_load(f)

            version = self._selectors.get("version", "unknown")
            logger.info(f"Selectors loaded (version: {version})")

        except Exception as e:
            logger.error(f"Failed to load selectors: {e}")
            logger.info("Falling back to default selectors")
            self._selectors = self._get_default_selectors()

    def get(self, path: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get selector by dot-notation path with caching.

        Args:
            path: Dot-separated path (e.g., "login.email_input")
            default: Default value if not found

        Returns:
            Selector string or default
        """
        # Use cached version for better performance
        return self._get_cached(path, default)

    @lru_cache(maxsize=256)
    def _get_cached(self, path: str, default: Optional[str] = None) -> Optional[str]:
        """
        Cached version of selector lookup.

        Args:
            path: Dot-separated path
            default: Default value if not found

        Returns:
            Selector string or default
        """
        keys = path.split(".")
        value = self._selectors

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.warning(f"Selector not found: {path}, using default: {default}")
                return default

        # Handle new structure: if value is a dict with 'primary' key, return primary
        if isinstance(value, dict) and "primary" in value:
            primary = value["primary"]
            return primary if isinstance(primary, str) else default

        return value if isinstance(value, str) else default

    def get_fallbacks(self, path: str) -> List[str]:
        """
        Get fallback selectors for a given path.

        Args:
            path: Dot-separated path

        Returns:
            List of fallback selectors (without primary)
        """
        keys = path.split(".")
        value = self._selectors

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return []

        # Handle new structure: if value is a dict with 'fallbacks' key
        if isinstance(value, dict) and "fallbacks" in value:
            fallbacks = value["fallbacks"]
            if isinstance(fallbacks, list):
                return fallbacks
            else:
                return [fallbacks]

        return []

    def get_with_fallback(self, path: str) -> List[str]:
        """
        Get selector with fallback options.

        Args:
            path: Dot-separated path

        Returns:
            List of selectors to try
        """
        primary = self.get(path)
        fallbacks = self.get_fallbacks(path)

        selectors = []
        if primary:
            selectors.append(primary)
        selectors.extend(fallbacks)

        return selectors

    def _get_semantic(self, path: str) -> Optional[Dict[str, str]]:
        """
        Get semantic locator information for a path.

        Args:
            path: Dot-separated path

        Returns:
            Semantic locator dict or None
        """
        keys = path.split(".")
        value = self._selectors

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        # Extract semantic field if it exists
        if isinstance(value, dict) and "semantic" in value:
            return dict(value["semantic"])

        return None

    async def _try_semantic_locator(
        self, page: Page, semantic: Dict[str, str], timeout: int = 10000
    ) -> Optional[Locator]:
        """
        Try to find element using Playwright's semantic locators.

        Args:
            page: Playwright page object
            semantic: Semantic locator information
            timeout: Timeout in milliseconds

        Returns:
            Element locator or None
        """
        try:
            # Try role-based locator
            if "role" in semantic:
                role = semantic["role"]
                name = (
                    semantic.get("text")
                    or semantic.get("text_en")
                    or semantic.get("label")
                    or semantic.get("label_en")
                )

                from typing import cast, Literal

                # Cast role to proper Literal type
                valid_role = cast(Literal["button", "link", "textbox"], role)
                locator = (
                    page.get_by_role(valid_role, name=name)
                    if name
                    else page.get_by_role(valid_role)
                )

                # Check if element exists and is visible
                try:
                    await locator.wait_for(state="visible", timeout=timeout)
                    logger.debug(f"Found element with semantic role: {role}, name: {name}")
                    return locator
                except Exception:
                    pass

            # Try label-based locator (for form inputs)
            for label_key in ["label", "label_en"]:
                if label_key in semantic:
                    label = semantic[label_key]
                    locator = page.get_by_label(label)
                    try:
                        await locator.wait_for(state="visible", timeout=timeout)
                        logger.debug(f"Found element with label: {label}")
                        return locator
                    except Exception:
                        pass

            # Try text-based locator
            for text_key in ["text", "text_en"]:
                if text_key in semantic:
                    text = semantic[text_key]
                    locator = page.get_by_text(text, exact=True)
                    try:
                        await locator.wait_for(state="visible", timeout=timeout)
                        logger.debug(f"Found element with text: {text}")
                        return locator
                    except Exception:
                        pass

            # Try placeholder-based locator
            if "placeholder" in semantic:
                placeholder = semantic["placeholder"]
                locator = page.get_by_placeholder(placeholder)
                try:
                    await locator.wait_for(state="visible", timeout=timeout)
                    logger.debug(f"Found element with placeholder: {placeholder}")
                    return locator
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Semantic locator failed: {e}")

        return None

    async def wait_for_selector(
        self, page: Page, path: str, timeout: int = 10000
    ) -> Optional[Locator]:
        """
        Wait for selector with fallback support.

        Args:
            page: Playwright page object
            path: Selector path
            timeout: Timeout in milliseconds

        Returns:
            Element locator or None

        Raises:
            SelectorNotFoundError: If all selectors fail
        """
        # Priority 1: Try semantic locators first (most resilient)
        semantic = self._get_semantic(path)
        if semantic:
            logger.debug(f"Trying semantic locators for: {path}")
            locator = await self._try_semantic_locator(page, semantic, timeout)
            if locator:
                logger.info(f"✅ Found element using semantic locator for: {path}")
                if self.learner:
                    # Record semantic success (index -1 indicates semantic)
                    pass  # We don't track semantic in learning metrics
                return locator

        # Priority 2: Try CSS selectors with optimized order (learning-based)
        selectors = self.get_with_fallback(path)

        # Keep track of original indices before reordering
        # This maps selector string to its original index
        original_indices = {selector: i for i, selector in enumerate(selectors)}

        # Apply learning-based reordering if learner is available
        if self.learner:
            selectors = self.learner.get_optimized_order(path, selectors)

        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=timeout, state="visible")
                logger.debug(f"Found element with selector: {selector}")

                # Record success in learning system with original index
                if self.learner:
                    original_idx = original_indices.get(selector, 0)
                    self.learner.record_success(path, original_idx)

                return page.locator(selector)
            except Exception:
                logger.debug(f"Selector failed: {selector}")

                # Record failure in learning system with original index
                if self.learner:
                    original_idx = original_indices.get(selector, 0)
                    self.learner.record_failure(path, original_idx)

                continue

        # Priority 3: Try AI repair as last resort
        if self.ai_repair and self.ai_repair.enabled:
            logger.warning(f"🤖 All selectors failed, trying AI repair for: {path}")

            # Generate element description from path
            element_description = self._generate_element_description(path)

            suggested_selector = await self.ai_repair.suggest_selector(
                page, path, element_description
            )

            if suggested_selector:
                try:
                    await page.wait_for_selector(
                        suggested_selector, timeout=timeout, state="visible"
                    )
                    logger.info(f"✅ AI repair succeeded for: {path}")

                    # Reload selectors to pick up AI changes
                    self.reload()

                    return page.locator(suggested_selector)
                except Exception as e:
                    logger.error(f"AI-suggested selector also failed: {e}")

        # All selectors failed - raise exception with detailed info
        logger.error(f"All selectors failed for path: {path}. Tried: {', '.join(selectors)}")
        raise SelectorNotFoundError(selector_name=path, tried_selectors=selectors)

    def _generate_element_description(self, path: str) -> str:
        """
        Generate human-readable element description from path.

        Args:
            path: Selector path

        Returns:
            Element description
        """
        parts = path.split(".")
        if len(parts) >= 2:
            section = parts[0].replace("_", " ").title()
            element = parts[1].replace("_", " ").title()
            return f"{element} in {section} section"
        return path.replace("_", " ").title()

    def reload(self) -> None:
        """Reload selectors from file and clear cache."""
        logger.info("Reloading selectors...")
        self._load_selectors()
        # Clear LRU cache when reloading selectors
        self._get_cached.cache_clear()

    def _get_default_selectors(self) -> Dict[str, Any]:
        """Get default selectors as fallback."""
        return {
            "version": "default",
            "login": {
                "email_input": "input#mat-input-0",
                "password_input": "input#mat-input-1",
                "submit_button": "button[type='submit']",
            },
            "appointment": {
                "centre_dropdown": "select#SelectLoc",
                "category_dropdown": "select#SelectVisaCategory",
            },
        }


# Global selector manager instance
_selector_manager: Optional[SelectorManager] = None


def get_selector_manager() -> SelectorManager:
    """Get global selector manager instance."""
    global _selector_manager
    if _selector_manager is None:
        _selector_manager = SelectorManager()
    return _selector_manager
