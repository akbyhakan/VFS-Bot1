"""Dynamic CSS selector management system."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from playwright.async_api import Locator, Page

from src.core.exceptions import SelectorNotFoundError

logger = logging.getLogger(__name__)


class CountryAwareSelectorManager:
    """Country-aware CSS selector management system."""

    def __init__(
        self, country_code: str = "default", selectors_file: str = "config/selectors.yaml"
    ):
        """
        Initialize country-aware selector manager.

        Args:
            country_code: Ülke kodu (fra, nld, deu, vb.) veya "default"
                         For backward compatibility, if this looks like a file path,
                         it will be treated as selectors_file instead.
            selectors_file: Path to selectors YAML file
        """
        # Backward compatibility: if country_code looks like a file path, swap the parameters
        if (
            "/" in country_code
            or "\\" in country_code
            or country_code.endswith(".yaml")
            or country_code.endswith(".yml")
        ):
            # Old API: SelectorManager(selectors_file)
            selectors_file = country_code
            country_code = "default"

        self.country_code = country_code.lower()
        self.selectors_file = Path(selectors_file)
        self._selectors: Dict[str, Any] = {}
        self.learner: Optional[Any] = None  # Type hint for SelectorLearner
        self.ai_repair: Optional[Any] = None  # Type hint for AISelectorRepair
        self._load_selectors()

        # Import and initialize learning system with country-specific metrics
        try:
            from src.utils.selector_learning import SelectorLearner

            metrics_file = f"data/selector_metrics_{self.country_code}.json"
            self.learner = SelectorLearner(metrics_file=metrics_file)
            logger.info(f"♻️ Adaptive selector learning enabled for country: {self.country_code}")
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
            logger.info(f"Selectors loaded (version: {version}) for country: {self.country_code}")

        except Exception as e:
            logger.error(f"Failed to load selectors: {e}")
            logger.info("Falling back to default selectors")
            self._selectors = self._get_default_selectors()

    def _get_country_selector(self, path: str) -> Optional[Any]:
        """
        Get country-specific selector.

        Args:
            path: Dot-separated path (e.g., "login.email_input")

        Returns:
            Selector value or None if not found
        """
        if self.country_code == "default":
            return None

        # Try to get from countries.{country_code}.{path}
        countries = self._selectors.get("countries", {})
        if not isinstance(countries, dict):
            return None

        country_data = countries.get(self.country_code, {})
        if not isinstance(country_data, dict):
            return None

        # Navigate through the path
        keys = path.split(".")
        value = country_data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _get_default_selector(self, path: str) -> Optional[Any]:
        """
        Get global default selector.

        Args:
            path: Dot-separated path (e.g., "login.email_input")

        Returns:
            Selector value or None if not found
        """
        # Try to get from defaults.{path} (new structure)
        defaults = self._selectors.get("defaults", {})
        if isinstance(defaults, dict):
            # Navigate through the path
            keys = path.split(".")
            result: Optional[Any] = defaults

            for key in keys:
                if isinstance(result, dict) and key in result:
                    result = result[key]
                else:
                    result = None
                    break

            if result is not None:
                return result

        # Backward compatibility: try to get directly from root (old structure)
        keys = path.split(".")
        result = self._selectors

        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return None

        return result

    def get(self, path: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get selector by dot-notation path with country-aware priority.

        Priority:
        1. Country-specific selector (countries.{country}.{path})
        2. Global default selector (defaults.{path})
        3. Provided default value

        Args:
            path: Dot-separated path (e.g., "login.email_input")
            default: Default value if not found

        Returns:
            Selector string or default
        """
        # Priority 1: Try country-specific selector
        country_value = self._get_country_selector(path)
        if country_value is not None:
            # Handle new structure: if value is a dict with 'primary' key, return primary
            if isinstance(country_value, dict) and "primary" in country_value:
                primary = country_value["primary"]
                if isinstance(primary, str):
                    logger.debug(f"Using country-specific selector for {self.country_code}: {path}")
                    return primary
            elif isinstance(country_value, str):
                logger.debug(f"Using country-specific selector for {self.country_code}: {path}")
                return country_value

        # Priority 2: Try global default selector
        default_value = self._get_default_selector(path)
        if default_value is not None:
            # Handle new structure: if value is a dict with 'primary' key, return primary
            if isinstance(default_value, dict) and "primary" in default_value:
                primary = default_value["primary"]
                if isinstance(primary, str):
                    logger.debug(f"Using default selector for: {path}")
                    return primary
            elif isinstance(default_value, str):
                logger.debug(f"Using default selector for: {path}")
                return default_value

        # Priority 3: Return provided default
        if default is not None:
            logger.warning(f"Selector not found: {path}, using default: {default}")
        return default

    def get_fallbacks(self, path: str) -> List[str]:
        """
        Get fallback selectors for a given path.

        Args:
            path: Dot-separated path

        Returns:
            List of fallback selectors (without primary)
        """
        # Try country-specific fallbacks first
        country_value = self._get_country_selector(path)
        if country_value is not None and isinstance(country_value, dict):
            if "fallbacks" in country_value:
                fallbacks = country_value["fallbacks"]
                if isinstance(fallbacks, list):
                    return fallbacks
                else:
                    return [fallbacks]

        # Fall back to default fallbacks
        default_value = self._get_default_selector(path)
        if default_value is not None and isinstance(default_value, dict):
            if "fallbacks" in default_value:
                fallbacks = default_value["fallbacks"]
                if isinstance(fallbacks, list):
                    return fallbacks
                else:
                    return [fallbacks]

        return []

    def get_with_fallback(self, path: str) -> List[str]:
        """
        Get selector with combined fallback options.

        Combines country-specific and global selectors in priority order:
        1. Country-specific primary
        2. Country-specific fallbacks
        3. Global primary (if not duplicate)
        4. Global fallbacks (if not duplicate)

        Args:
            path: Dot-separated path

        Returns:
            List of selectors to try (deduplicated)
        """
        selectors = []

        # Get country-specific selector and fallbacks
        country_value = self._get_country_selector(path)
        if country_value is not None:
            # Add country primary
            if isinstance(country_value, dict) and "primary" in country_value:
                country_primary = country_value["primary"]
                if isinstance(country_primary, str):
                    selectors.append(country_primary)

                # Add country fallbacks
                if "fallbacks" in country_value:
                    country_fallbacks = country_value["fallbacks"]
                    if isinstance(country_fallbacks, list):
                        selectors.extend(country_fallbacks)
                    else:
                        selectors.append(country_fallbacks)
            elif isinstance(country_value, str):
                selectors.append(country_value)

        # Get global default selector and fallbacks
        default_value = self._get_default_selector(path)
        if default_value is not None:
            # Add global primary (if not duplicate)
            if isinstance(default_value, dict) and "primary" in default_value:
                default_primary = default_value["primary"]
                if isinstance(default_primary, str) and default_primary not in selectors:
                    selectors.append(default_primary)

                # Add global fallbacks (if not duplicate)
                if "fallbacks" in default_value:
                    default_fallbacks = default_value["fallbacks"]
                    if isinstance(default_fallbacks, list):
                        for fb in default_fallbacks:
                            if fb not in selectors:
                                selectors.append(fb)
                    elif default_fallbacks not in selectors:
                        selectors.append(default_fallbacks)
            elif isinstance(default_value, str) and default_value not in selectors:
                selectors.append(default_value)

        return selectors

    def get_all(self, path: str) -> List[str]:
        """
        Get all selectors for a path (primary + fallbacks).

        Args:
            path: Dot-separated path (e.g., "booking.first_name")

        Returns:
            List of selector strings [primary, fallback1, fallback2, ...]
        """
        # Try country-specific first
        country_value = self._get_country_selector(path)
        if country_value is not None:
            return self._extract_all_selectors(country_value)

        # Fall back to defaults
        value = self._get_default_selector(path)
        if value is not None:
            return self._extract_all_selectors(value)

        return []

    def _extract_all_selectors(self, value: Any) -> List[str]:
        """Extract all selectors from a value (dict with primary/fallbacks, string, or list)."""
        if isinstance(value, dict):
            result = []
            if "primary" in value:
                result.append(str(value["primary"]))
            if "fallbacks" in value:
                fallbacks = value["fallbacks"]
                if isinstance(fallbacks, list):
                    result.extend([str(f) for f in fallbacks])
                else:
                    result.append(str(fallbacks))
            return result
        elif isinstance(value, list):
            return [str(v) for v in value]
        elif isinstance(value, str):
            return [value]
        return []

    def _get_semantic(self, path: str) -> Optional[Dict[str, str]]:
        """
        Get semantic locator information for a path.

        Priority:
        1. Country-specific semantic
        2. Global default semantic

        Args:
            path: Dot-separated path

        Returns:
            Semantic locator dict or None
        """
        # Try country-specific semantic first
        country_value = self._get_country_selector(path)
        if country_value is not None and isinstance(country_value, dict):
            if "semantic" in country_value:
                return dict(country_value["semantic"])

        # Fall back to default semantic
        default_value = self._get_default_selector(path)
        if default_value is not None and isinstance(default_value, dict):
            if "semantic" in default_value:
                return dict(default_value["semantic"])

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

                from typing import Literal, cast

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
                await page.wait_for_selector(selector, timeout=timeout)
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
                    await page.wait_for_selector(suggested_selector, timeout=timeout)
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
        """Reload selectors from file."""
        logger.info("Reloading selectors...")
        self._load_selectors()

    def _get_default_selectors(self) -> Dict[str, Any]:
        """Get default selectors as fallback."""
        return {
            "version": "default",
            "defaults": {
                "login": {
                    "email_input": "input#mat-input-0",
                    "password_input": "input#mat-input-1",
                    "submit_button": "button[type='submit']",
                },
                "appointment": {
                    "centre_dropdown": "select#SelectLoc",
                    "category_dropdown": "select#SelectVisaCategory",
                },
                "booking": {
                    "continue_button": {
                        "primary": '//button[contains(., "Devam et")]',
                        "fallbacks": ['//button[contains(., "Continue")]', "button.continue-btn"],
                    },
                    "save_button": {
                        "primary": '//button[contains(., "Kaydet")]',
                        "fallbacks": ['button[type="submit"]'],
                    },
                },
            },
            "countries": {},
        }


# Global selector manager instances (one per country)
_selector_managers: Dict[str, CountryAwareSelectorManager] = {}


def get_selector_manager(country_code: str = "default") -> CountryAwareSelectorManager:
    """
    Get or create a selector manager for a specific country.

    Args:
        country_code: Ülke kodu (fra, nld, vb.) veya "default"

    Returns:
        CountryAwareSelectorManager instance
    """
    country_code = country_code.lower()

    if country_code not in _selector_managers:
        _selector_managers[country_code] = CountryAwareSelectorManager(country_code)
        logger.info(f"Created selector manager for country: {country_code}")

    return _selector_managers[country_code]
