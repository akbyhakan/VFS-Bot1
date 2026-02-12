"""Learned state store for persistent page state knowledge."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


@dataclass
class LearnedAction:
    """A learned action for a specific page state."""

    state_name: str
    action_type: str
    target_selector: str
    fill_value: str
    indicators: Dict[str, Any]
    match_score: float = 0.0


class LearnedStateStore:
    """Manages persistent storage of learned page states."""

    def __init__(
        self,
        storage_path: str = "config/learned_states.yaml",
        match_threshold: float = 0.6,
    ):
        """
        Initialize learned state store.

        Args:
            storage_path: Path to YAML file for persistent storage
            match_threshold: Minimum match score to consider a state matched (default: 0.6)
        """
        self.storage_path = Path(storage_path)
        self.match_threshold = match_threshold
        self.learned_states: Dict[str, Dict[str, Any]] = {}

        # Load existing learned states
        self._load_states()

    def _load_states(self) -> None:
        """Load learned states from YAML file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    self.learned_states = yaml.safe_load(f) or {}
                logger.info(
                    f"📚 Loaded {len(self.learned_states)} learned states from {self.storage_path}"
                )
            except Exception as e:
                logger.error(f"Failed to load learned states: {e}")
                self.learned_states = {}
        else:
            logger.debug(f"No learned states file found at {self.storage_path}")
            self.learned_states = {}

    def _save_states(self) -> bool:
        """
        Save learned states to YAML file.

        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.storage_path, "w") as f:
                yaml.dump(
                    self.learned_states,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            logger.info(
                f"💾 Saved {len(self.learned_states)} learned states to {self.storage_path}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save learned states: {e}")
            return False

    def _calculate_match_score(
        self, url: str, html: str, indicators: Dict[str, Any]
    ) -> float:
        """
        Calculate how well a page matches the given indicators.

        Args:
            url: Current page URL
            html: Page HTML content
            indicators: Dictionary with url_patterns, text_indicators, css_selectors

        Returns:
            Match score between 0.0 and 1.0
        """
        score = 0.0
        checks = 0

        # Check URL patterns
        url_patterns = indicators.get("url_patterns", [])
        if url_patterns:
            checks += 1
            for pattern in url_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    score += 1.0
                    break

        # Check text indicators
        text_indicators = indicators.get("text_indicators", [])
        if text_indicators:
            checks += 1
            text_matches = sum(
                1 for text in text_indicators if text.lower() in html.lower()
            )
            if text_matches > 0:
                # Partial credit: percentage of text indicators found
                score += min(text_matches / len(text_indicators), 1.0)

        # Check CSS selectors (presence check only - we don't have page access here)
        css_selectors = indicators.get("css_selectors", [])
        if css_selectors:
            checks += 1
            # Simple heuristic: check if selector patterns appear in HTML
            selector_matches = 0
            for selector in css_selectors:
                # Extract ID or class from selector for simple matching
                if "#" in selector:
                    id_match = re.search(r'#([\w-]+)', selector)
                    if id_match:
                        id_value = id_match.group(1)
                        # Match various HTML attribute formats
                        if re.search(
                            rf'id\s*=\s*["\']?{re.escape(id_value)}["\']?',
                            html,
                            re.IGNORECASE,
                        ):
                            selector_matches += 1
                elif "." in selector:
                    class_match = re.search(r'\.([\w-]+)', selector)
                    if class_match:
                        class_value = class_match.group(1)
                        # Match class value anywhere in class attribute
                        if re.search(
                            rf'class\s*=\s*["\'][^"\']*\b{re.escape(class_value)}\b[^"\']*["\']',
                            html,
                            re.IGNORECASE,
                        ):
                            selector_matches += 1
            if selector_matches > 0:
                score += min(selector_matches / len(css_selectors), 1.0)

        # Normalize score
        if checks > 0:
            return score / checks
        return 0.0

    def get_learned_action(
        self, page_url: str, page_html: str
    ) -> Optional[LearnedAction]:
        """
        Check if we've seen this page before by matching indicators.

        Args:
            page_url: Current page URL
            page_html: Current page HTML content

        Returns:
            LearnedAction if a match is found, None otherwise
        """
        best_match: Optional[LearnedAction] = None
        best_score = 0.0

        for state_name, state_data in self.learned_states.items():
            indicators = state_data.get("indicators", {})
            action = state_data.get("action", {})

            # Calculate match score
            match_score = self._calculate_match_score(page_url, page_html, indicators)

            if match_score > best_score and match_score >= self.match_threshold:
                best_score = match_score
                best_match = LearnedAction(
                    state_name=state_name,
                    action_type=action.get("action", ""),
                    target_selector=action.get("selector", ""),
                    fill_value=action.get("fill_value", ""),
                    indicators=indicators,
                    match_score=match_score,
                )

        if best_match:
            logger.info(
                f"🧠 Found learned state: {best_match.state_name} "
                f"(match score: {best_match.match_score:.2f})"
            )
            return best_match

        logger.debug("No learned state matched the current page")
        return None

    def save_learned_state(
        self, state_name: str, indicators: Dict[str, Any], action: Dict[str, Any]
    ) -> bool:
        """
        Save a successfully learned state.

        Args:
            state_name: Name of the state (e.g., "sms_verification")
            indicators: Dictionary with url_patterns, text_indicators, css_selectors
            action: Dictionary with action type, selector, and fill_value

        Returns:
            True if save was successful, False otherwise
        """
        # Check if state already exists
        if state_name in self.learned_states:
            logger.warning(f"⚠️ Learned state '{state_name}' already exists, updating...")

        # Store the state
        self.learned_states[state_name] = {
            "indicators": indicators,
            "action": action,
        }

        logger.info(
            f"🧠 Learned new state: {state_name} → {action.get('action', 'unknown')}"
        )

        # Persist to file
        return self._save_states()

    def get_all_learned_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Return all learned states.

        Returns:
            Dictionary of all learned states
        """
        return self.learned_states.copy()

    def remove_learned_state(self, state_name: str) -> bool:
        """
        Remove a learned state.

        Args:
            state_name: Name of the state to remove

        Returns:
            True if removal was successful, False otherwise
        """
        if state_name in self.learned_states:
            del self.learned_states[state_name]
            logger.info(f"🗑️ Removed learned state: {state_name}")
            return self._save_states()
        else:
            logger.warning(f"⚠️ Learned state '{state_name}' not found")
            return False
