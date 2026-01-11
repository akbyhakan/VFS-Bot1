"""Dynamic CSS selector management system."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

from playwright.async_api import Page, Locator

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
        self._load_selectors()

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
        Get selector by dot-notation path.

        Args:
            path: Dot-separated path (e.g., "login.email_input")
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
            return value["primary"]

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
        selectors = self.get_with_fallback(path)

        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=timeout)
                logger.debug(f"Found element with selector: {selector}")
                return page.locator(selector)
            except Exception:
                logger.debug(f"Selector failed: {selector}")
                continue

        # All selectors failed - raise exception with detailed info
        logger.error(f"All selectors failed for path: {path}. Tried: {', '.join(selectors)}")
        raise SelectorNotFoundError(selector_name=path, tried_selectors=selectors)

    def reload(self) -> None:
        """Reload selectors from file."""
        logger.info("Reloading selectors...")
        self._load_selectors()

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
