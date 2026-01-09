"""Dynamic CSS selector management system."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

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
            
            with open(self.selectors_file, 'r', encoding='utf-8') as f:
                self._selectors = yaml.safe_load(f)
            
            version = self._selectors.get('version', 'unknown')
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
        keys = path.split('.')
        value = self._selectors
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.warning(f"Selector not found: {path}, using default: {default}")
                return default
        
        return value if isinstance(value, str) else default
    
    def get_with_fallback(self, path: str) -> List[str]:
        """
        Get selector with fallback options.
        
        Args:
            path: Dot-separated path
            
        Returns:
            List of selectors to try
        """
        primary = self.get(path)
        fallback_path = f"fallback.{path.split('.')[-1]}"
        fallbacks = self.get(fallback_path)
        
        selectors = []
        if primary:
            selectors.append(primary)
        if fallbacks:
            if isinstance(fallbacks, list):
                selectors.extend(fallbacks)
            else:
                selectors.append(fallbacks)
        
        return selectors
    
    async def wait_for_selector(self, page, path: str, timeout: int = 10000):
        """
        Wait for selector with fallback support.
        
        Args:
            page: Playwright page object
            path: Selector path
            timeout: Timeout in milliseconds
            
        Returns:
            Element locator or None
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
        
        logger.error(f"All selectors failed for path: {path}")
        return None
    
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
                "submit_button": "button[type='submit']"
            },
            "appointment": {
                "centre_dropdown": "select#SelectLoc",
                "category_dropdown": "select#SelectVisaCategory"
            }
        }


# Global selector manager instance
_selector_manager: Optional[SelectorManager] = None


def get_selector_manager() -> SelectorManager:
    """Get global selector manager instance."""
    global _selector_manager
    if _selector_manager is None:
        _selector_manager = SelectorManager()
    return _selector_manager
