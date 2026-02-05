"""Advanced selector self-healing system."""
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

import yaml

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


class SelectorSelfHealing:
    """Automatically detect and repair broken selectors."""

    CONFIDENCE_THRESHOLD = 0.80  # 80% confidence score required

    def __init__(
        self,
        selectors_file: str = "config/selectors.yaml",
        healing_log_file: str = "data/selector_healing_log.json",
    ):
        self.selectors_file = Path(selectors_file)
        self.healing_log_file = Path(healing_log_file)
        self.healing_log_file.parent.mkdir(parents=True, exist_ok=True)
        self._healing_history: List[Dict] = []

    async def attempt_heal(
        self, page: "Page", selector_path: str, failed_selector: str, element_description: str
    ) -> Optional[str]:
        """Attempt to repair broken selector."""
        logger.info(f"🔧 Self-healing started: {selector_path}")

        # 1. Try alternative strategies
        candidates = await self._find_candidates(page, element_description)

        if not candidates:
            logger.warning(f"No candidate selectors found: {selector_path}")
            return None

        # 2. Calculate confidence score for each candidate
        for candidate in candidates:
            score = await self._calculate_confidence(page, candidate, element_description)

            if score >= self.CONFIDENCE_THRESHOLD:
                logger.info(f"✅ High-confidence candidate found: {candidate} (score: {score:.2f})")

                # 3. Update YAML
                await self._update_selectors_yaml(selector_path, candidate)

                # 4. Log to healing log
                self._log_healing(selector_path, failed_selector, candidate, score)

                return candidate

        logger.warning(f"No sufficiently confident candidate found: {selector_path}")
        return None

    async def _find_candidates(self, page: "Page", description: str) -> List[str]:
        """Find candidate selectors based on element description."""
        candidates = []

        # Strategy 1: Search by text content
        keywords = description.lower().split()
        for keyword in keywords:
            if len(keyword) > 2:
                candidates.append(f"text={keyword}")
                candidates.append(f"*:has-text('{keyword}')")

        # Strategy 2: Common input patterns
        if "email" in description.lower():
            candidates.extend(
                [
                    "input[type='email']",
                    "input[name*='email']",
                    "input[id*='email']",
                    "input[placeholder*='mail']",
                ]
            )
        elif "password" in description.lower():
            candidates.extend(
                ["input[type='password']", "input[name*='password']", "input[id*='password']"]
            )
        elif "button" in description.lower() or "submit" in description.lower():
            candidates.extend(
                [
                    "button[type='submit']",
                    "button:has-text('Submit')",
                    "button:has-text('Gönder')",
                    "input[type='submit']",
                ]
            )

        return candidates

    async def _calculate_confidence(self, page: "Page", selector: str, description: str) -> float:
        """Calculate confidence score for selector (0.0 - 1.0)."""
        score = 0.0

        try:
            # Does element exist?
            element = page.locator(selector)
            count = await element.count()

            if count == 0:
                return 0.0

            # Single element = higher score
            if count == 1:
                score += 0.4
            elif count <= 3:
                score += 0.2

            # Is it visible?
            try:
                is_visible = await element.first.is_visible()
                if is_visible:
                    score += 0.3
            except (TimeoutError, Exception) as e:
                logger.debug(f"Visibility check failed for selector: {e}")

            # Is it interactable?
            try:
                is_enabled = await element.first.is_enabled()
                if is_enabled:
                    score += 0.2
            except (TimeoutError, Exception) as e:
                logger.debug(f"Enabled check failed for selector: {e}")

            # Does text content match?
            try:
                text = await element.first.text_content() or ""
                for keyword in description.lower().split():
                    if keyword in text.lower():
                        score += 0.1
                        break
            except (TimeoutError, Exception) as e:
                logger.debug(f"Text content check failed for selector: {e}")

        except (TimeoutError, Exception) as e:
            logger.debug(f"Confidence calculation error: {e}")
            return 0.0

        return min(score, 1.0)

    async def _update_selectors_yaml(self, selector_path: str, new_selector: str) -> None:
        """Update selectors YAML file."""
        try:
            if not self.selectors_file.exists():
                logger.warning("Selectors file not found")
                return

            with open(self.selectors_file, "r", encoding="utf-8") as f:
                selectors = yaml.safe_load(f)

            # Parse path (e.g., "login.email_input")
            parts = selector_path.split(".")

            # Add to existing fallbacks
            current = selectors
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            last_key = parts[-1]
            if last_key in current:
                existing = current[last_key]
                if isinstance(existing, dict):
                    # Add to fallback list
                    if "fallbacks" not in existing:
                        existing["fallbacks"] = []
                    if new_selector not in existing["fallbacks"]:
                        existing["fallbacks"].insert(0, new_selector)  # Add to front
                        logger.info(f"Fallback added: {selector_path} -> {new_selector}")

            with open(self.selectors_file, "w", encoding="utf-8") as f:
                yaml.dump(selectors, f, allow_unicode=True, default_flow_style=False)

        except Exception as e:
            logger.error(f"YAML update error: {e}")

    def _log_healing(
        self, selector_path: str, old_selector: str, new_selector: str, confidence: float
    ) -> None:
        """Log healing operation."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "selector_path": selector_path,
            "old_selector": old_selector,
            "new_selector": new_selector,
            "confidence": confidence,
        }
        self._healing_history.append(record)

        # Save to file
        try:
            import json

            existing = []
            if self.healing_log_file.exists():
                with open(self.healing_log_file, "r") as f:
                    existing = json.load(f)
            existing.append(record)
            with open(self.healing_log_file, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.error(f"Healing log save error: {e}")
