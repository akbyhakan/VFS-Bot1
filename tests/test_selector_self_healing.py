"""Tests for selector_self_healing module."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, mock_open
from src.services.selector_self_healing import SelectorSelfHealing


class TestSelectorSelfHealing:
    """Tests for SelectorSelfHealing class."""

    @pytest.fixture
    def temp_files(self, tmp_path):
        """Create temporary files for testing."""
        selectors_file = tmp_path / "selectors.yaml"
        healing_log_file = tmp_path / "healing_log.json"
        return {"selectors": selectors_file, "log": healing_log_file}

    @pytest.fixture
    def mock_page(self):
        """Create a mock Playwright page."""
        page = AsyncMock()
        return page

    def test_init_creates_directory(self, temp_files):
        """Test that initialization creates the data directory."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        assert temp_files["log"].parent.exists()

    @pytest.mark.asyncio
    async def test_find_candidates_email(self, temp_files, mock_page):
        """Test finding candidates for email input."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        candidates = await healing._find_candidates(mock_page, "email input")

        assert any("email" in c for c in candidates)
        assert any("type='email'" in c for c in candidates)

    @pytest.mark.asyncio
    async def test_find_candidates_password(self, temp_files, mock_page):
        """Test finding candidates for password input."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        candidates = await healing._find_candidates(mock_page, "password field")

        assert any("password" in c for c in candidates)
        assert any("type='password'" in c for c in candidates)

    @pytest.mark.asyncio
    async def test_find_candidates_button(self, temp_files, mock_page):
        """Test finding candidates for button."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        candidates = await healing._find_candidates(mock_page, "submit button")

        assert any("submit" in c.lower() for c in candidates)

    @pytest.mark.asyncio
    async def test_calculate_confidence_element_not_found(self, temp_files, mock_page):
        """Test confidence score when element is not found."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        mock_locator = AsyncMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        score = await healing._calculate_confidence(mock_page, "invalid_selector", "test element")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_calculate_confidence_single_element(self, temp_files, mock_page):
        """Test confidence score for single visible element."""
        from unittest.mock import MagicMock

        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        mock_locator = AsyncMock()
        mock_locator.count.return_value = 1
        mock_locator.first.is_visible.return_value = True
        mock_locator.first.is_enabled.return_value = True
        mock_locator.first.text_content.return_value = "Submit"
        mock_page.locator = MagicMock(return_value=mock_locator)

        score = await healing._calculate_confidence(
            mock_page, "button[type='submit']", "submit button"
        )

        # Should have high confidence: single element (0.4) + visible (0.3) + enabled (0.2) + text match (0.1)
        assert score >= 0.9

    @pytest.mark.asyncio
    async def test_calculate_confidence_multiple_elements(self, temp_files, mock_page):
        """Test confidence score for multiple elements."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        mock_locator = AsyncMock()
        mock_locator.count.return_value = 5
        mock_locator.first.is_visible.return_value = True
        mock_locator.first.is_enabled.return_value = True
        mock_page.locator.return_value = mock_locator

        score = await healing._calculate_confidence(mock_page, "button", "button")

        # Should have lower confidence due to multiple elements (0.0)
        assert score < 0.6

    @pytest.mark.asyncio
    async def test_attempt_heal_no_candidates(self, temp_files, mock_page):
        """Test healing when no candidates are found."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        # Mock to return empty candidates
        with patch.object(healing, "_find_candidates", return_value=[]):
            result = await healing.attempt_heal(
                mock_page, "login.email", "old_selector", "email input"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_attempt_heal_low_confidence(self, temp_files, mock_page):
        """Test healing when no candidate has sufficient confidence."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        # Mock candidates with low confidence
        with patch.object(healing, "_find_candidates", return_value=["candidate1"]):
            with patch.object(healing, "_calculate_confidence", return_value=0.5):
                result = await healing.attempt_heal(
                    mock_page, "login.email", "old_selector", "email input"
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_attempt_heal_success(self, temp_files, mock_page):
        """Test successful healing with high confidence candidate."""
        # Create a mock selectors.yaml file
        temp_files["selectors"].write_text(
            """
login:
  email:
    primary: "old_selector"
"""
        )

        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        # Mock candidates with high confidence
        with patch.object(healing, "_find_candidates", return_value=["new_selector"]):
            with patch.object(healing, "_calculate_confidence", return_value=0.95):
                result = await healing.attempt_heal(
                    mock_page, "login.email", "old_selector", "email input"
                )

        assert result == "new_selector"
        # Check that healing was logged
        assert temp_files["log"].exists()

    def test_log_healing(self, temp_files):
        """Test logging a healing operation."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        healing._log_healing(
            selector_path="login.email",
            old_selector="old_selector",
            new_selector="new_selector",
            confidence=0.95,
        )

        assert temp_files["log"].exists()
        with open(temp_files["log"], "r") as f:
            logs = json.load(f)

        assert len(logs) == 1
        assert logs[0]["selector_path"] == "login.email"
        assert logs[0]["old_selector"] == "old_selector"
        assert logs[0]["new_selector"] == "new_selector"
        assert logs[0]["confidence"] == 0.95

    def test_log_healing_appends(self, temp_files):
        """Test that logging appends to existing log."""
        healing = SelectorSelfHealing(
            selectors_file=str(temp_files["selectors"]), healing_log_file=str(temp_files["log"])
        )

        # Log first healing
        healing._log_healing(
            selector_path="login.email", old_selector="old1", new_selector="new1", confidence=0.95
        )

        # Log second healing
        healing._log_healing(
            selector_path="login.password",
            old_selector="old2",
            new_selector="new2",
            confidence=0.90,
        )

        with open(temp_files["log"], "r") as f:
            logs = json.load(f)

        assert len(logs) == 2
