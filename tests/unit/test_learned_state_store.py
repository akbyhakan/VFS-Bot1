"""Tests for LearnedStateStore - persistent page state knowledge."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.resilience.learned_state_store import LearnedAction, LearnedStateStore


class TestLearnedStateStoreInitialization:
    """Tests for LearnedStateStore initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            assert store.storage_path == store_path
            assert store.match_threshold == 0.6
            assert store.learned_states == {}

    def test_init_loads_existing_file(self):
        """Test initialization loads existing learned states file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"

            # Create a file with existing states
            existing_states = {
                "sms_verification": {
                    "indicators": {
                        "url_patterns": [".*sms.*"],
                        "text_indicators": ["Enter code"],
                        "css_selectors": ["#sms-code"],
                    },
                    "action": {
                        "action": "fill",
                        "selector": "#sms-code",
                        "fill_value": "",
                    },
                }
            }
            with open(store_path, "w") as f:
                yaml.dump(existing_states, f)

            store = LearnedStateStore(storage_path=str(store_path))

            assert len(store.learned_states) == 1
            assert "sms_verification" in store.learned_states

    def test_init_handles_missing_file(self):
        """Test initialization handles missing file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "nonexistent.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            assert store.learned_states == {}


class TestSaveAndLoadStates:
    """Tests for saving and loading learned states."""

    def test_save_learned_state(self):
        """Test saving a learned state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [".*verify.*"],
                "text_indicators": ["Enter code"],
                "css_selectors": ["#code-input"],
            }
            action = {
                "action": "fill",
                "selector": "#code-input",
                "fill_value": "",
            }

            result = store.save_learned_state("verification", indicators, action)

            assert result is True
            assert "verification" in store.learned_states
            assert store.learned_states["verification"]["indicators"] == indicators
            assert store.learned_states["verification"]["action"] == action

    def test_save_learned_state_persists_to_file(self):
        """Test saving a learned state persists to YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {"url_patterns": [".*test.*"], "text_indicators": [], "css_selectors": []}
            action = {"action": "click", "selector": "#button", "fill_value": ""}

            store.save_learned_state("test_state", indicators, action)

            # Load the file and verify
            with open(store_path, "r") as f:
                loaded = yaml.safe_load(f)

            assert "test_state" in loaded
            assert loaded["test_state"]["action"]["action"] == "click"

    def test_save_updates_existing_state(self):
        """Test saving updates an existing state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            # Save initial state
            indicators1 = {"url_patterns": [".*old.*"], "text_indicators": [], "css_selectors": []}
            action1 = {"action": "click", "selector": "#old", "fill_value": ""}
            store.save_learned_state("my_state", indicators1, action1)

            # Update the state
            indicators2 = {"url_patterns": [".*new.*"], "text_indicators": [], "css_selectors": []}
            action2 = {"action": "fill", "selector": "#new", "fill_value": ""}
            store.save_learned_state("my_state", indicators2, action2)

            assert store.learned_states["my_state"]["action"]["action"] == "fill"
            assert store.learned_states["my_state"]["indicators"]["url_patterns"] == [".*new.*"]

    def test_get_all_learned_states(self):
        """Test getting all learned states."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            # Add multiple states
            store.save_learned_state(
                "state1",
                {"url_patterns": [], "text_indicators": [], "css_selectors": []},
                {"action": "click", "selector": "#a", "fill_value": ""},
            )
            store.save_learned_state(
                "state2",
                {"url_patterns": [], "text_indicators": [], "css_selectors": []},
                {"action": "wait", "selector": "", "fill_value": ""},
            )

            all_states = store.get_all_learned_states()

            assert len(all_states) == 2
            assert "state1" in all_states
            assert "state2" in all_states

    def test_remove_learned_state(self):
        """Test removing a learned state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            # Add a state
            store.save_learned_state(
                "to_remove",
                {"url_patterns": [], "text_indicators": [], "css_selectors": []},
                {"action": "click", "selector": "#x", "fill_value": ""},
            )

            assert "to_remove" in store.learned_states

            # Remove it
            result = store.remove_learned_state("to_remove")

            assert result is True
            assert "to_remove" not in store.learned_states

    def test_remove_nonexistent_state(self):
        """Test removing a nonexistent state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            result = store.remove_learned_state("nonexistent")

            assert result is False


class TestMatchingLogic:
    """Tests for matching page to learned states."""

    def test_get_learned_action_by_url_pattern(self):
        """Test matching a page by URL pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [".*verify.*phone.*"],
                "text_indicators": [],
                "css_selectors": [],
            }
            action = {"action": "fill", "selector": "#phone", "fill_value": ""}
            store.save_learned_state("phone_verification", indicators, action)

            learned = store.get_learned_action(
                "https://example.com/verify/phone", "<html></html>"
            )

            assert learned is not None
            assert learned.state_name == "phone_verification"
            assert learned.action_type == "fill"

    def test_get_learned_action_by_text_indicator(self):
        """Test matching a page by text indicator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [],
                "text_indicators": ["Enter verification code"],
                "css_selectors": [],
            }
            action = {"action": "fill", "selector": "#code", "fill_value": ""}
            store.save_learned_state("code_entry", indicators, action)

            html = "<div>Enter verification code: <input id='code'></div>"
            learned = store.get_learned_action("https://example.com/page", html)

            assert learned is not None
            assert learned.state_name == "code_entry"

    def test_get_learned_action_by_css_selector(self):
        """Test matching a page by CSS selector."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [],
                "text_indicators": [],
                "css_selectors": ["#unique-element"],
            }
            action = {"action": "click", "selector": "#button", "fill_value": ""}
            store.save_learned_state("unique_page", indicators, action)

            html = '<div><input id="unique-element"></div>'
            learned = store.get_learned_action("https://example.com/page", html)

            assert learned is not None
            assert learned.state_name == "unique_page"

    def test_get_learned_action_no_match(self):
        """Test no match returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [".*different.*"],
                "text_indicators": ["Different text"],
                "css_selectors": ["#different"],
            }
            action = {"action": "click", "selector": "#x", "fill_value": ""}
            store.save_learned_state("different_page", indicators, action)

            learned = store.get_learned_action("https://example.com/page", "<html></html>")

            assert learned is None

    def test_get_learned_action_best_match(self):
        """Test returns the best matching state when multiple matches exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            # State with partial match
            indicators1 = {
                "url_patterns": [".*verify.*"],
                "text_indicators": [],
                "css_selectors": [],
            }
            action1 = {"action": "click", "selector": "#a", "fill_value": ""}
            store.save_learned_state("partial_match", indicators1, action1)

            # State with better match
            indicators2 = {
                "url_patterns": [".*verify.*"],
                "text_indicators": ["Enter code"],
                "css_selectors": [],
            }
            action2 = {"action": "fill", "selector": "#code", "fill_value": ""}
            store.save_learned_state("better_match", indicators2, action2)

            html = "<div>Enter code: <input id='code'></div>"
            learned = store.get_learned_action("https://example.com/verify/page", html)

            assert learned is not None
            assert learned.state_name == "better_match"
            assert learned.match_score > 0.6

    def test_match_score_threshold(self):
        """Test match score threshold filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path), match_threshold=0.8)

            # State with weak indicators
            indicators = {
                "url_patterns": [],
                "text_indicators": ["might match"],
                "css_selectors": [],
            }
            action = {"action": "click", "selector": "#x", "fill_value": ""}
            store.save_learned_state("weak_state", indicators, action)

            # Page doesn't match well enough
            learned = store.get_learned_action(
                "https://example.com/page", "<html>different content</html>"
            )

            assert learned is None


class TestMatchScoreCalculation:
    """Tests for match score calculation logic."""

    def test_calculate_match_score_all_match(self):
        """Test match score when all indicators match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [".*test.*"],
                "text_indicators": ["Test content"],
                "css_selectors": ["#test-id"],
            }

            score = store._calculate_match_score(
                "https://example.com/test",
                '<div>Test content</div><input id="test-id">',
                indicators,
            )

            assert score == 1.0

    def test_calculate_match_score_partial_match(self):
        """Test match score with partial matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [".*test.*"],
                "text_indicators": ["Test", "Missing"],
                "css_selectors": [],
            }

            score = store._calculate_match_score(
                "https://example.com/test", "<div>Test content</div>", indicators
            )

            # URL matches (1.0), text partially matches (0.5)
            assert 0.5 < score < 1.0

    def test_calculate_match_score_no_match(self):
        """Test match score when nothing matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {
                "url_patterns": [".*different.*"],
                "text_indicators": ["Different"],
                "css_selectors": ["#different"],
            }

            score = store._calculate_match_score(
                "https://example.com/test", "<div>Test content</div>", indicators
            )

            assert score == 0.0

    def test_calculate_match_score_empty_indicators(self):
        """Test match score with empty indicators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "learned_states.yaml"
            store = LearnedStateStore(storage_path=str(store_path))

            indicators = {"url_patterns": [], "text_indicators": [], "css_selectors": []}

            score = store._calculate_match_score(
                "https://example.com/test", "<div>Test</div>", indicators
            )

            assert score == 0.0
