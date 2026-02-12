"""Tests for SmartWait - 3-stage selector resolution pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import Locator, Page

from src.core.exceptions import SelectorNotFoundError
from src.resilience import SmartWait


class TestSmartWaitInitialization:
    """Tests for SmartWait initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        selector_manager = MagicMock()
        ai_repair = MagicMock()

        smart_wait = SmartWait(selector_manager, ai_repair)

        assert smart_wait.selector_manager == selector_manager
        assert smart_wait.ai_repair == ai_repair
        assert smart_wait.max_retries == 3
        assert smart_wait.backoff_factor == 1.5

    def test_init_without_ai_repair(self):
        """Test initialization without AI repair."""
        selector_manager = MagicMock()

        smart_wait = SmartWait(selector_manager, ai_repair=None)

        assert smart_wait.ai_repair is None


class TestStage1Semantic:
    """Tests for Stage 1: Semantic locator resolution."""

    @pytest.mark.asyncio
    async def test_stage1_success_skips_other_stages(self):
        """Test that Stage 1 success skips CSS and AI stages."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        # Stage 1 succeeds
        selector_manager._get_semantic = MagicMock(
            return_value={"role": "button", "text": "Submit"}
        )
        selector_manager._try_semantic_locator = AsyncMock(
            return_value=expected_locator
        )

        smart_wait = SmartWait(selector_manager)
        result = await smart_wait.find_element(page, "login.submit_button")

        assert result == expected_locator
        # CSS stage should not be called
        selector_manager.get_with_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_stage1_no_semantic_proceeds_to_stage2(self):
        """Test that no semantic locators proceeds to Stage 2."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        # No semantic locators
        selector_manager._get_semantic = MagicMock(return_value=None)

        # Stage 2 succeeds
        selector_manager.get_with_fallback = MagicMock(return_value=["#submit"])
        selector_manager.learner = None
        page.wait_for_selector = AsyncMock()
        page.locator = MagicMock(return_value=expected_locator)

        smart_wait = SmartWait(selector_manager)
        result = await smart_wait.find_element(page, "login.submit_button")

        assert result == expected_locator


class TestStage2CSS:
    """Tests for Stage 2: CSS selector resolution with learning."""

    @pytest.mark.asyncio
    async def test_stage2_first_selector_success(self):
        """Test Stage 2 succeeds with first selector."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        # No semantic
        selector_manager._get_semantic = MagicMock(return_value=None)

        # CSS selectors
        selector_manager.get_with_fallback = MagicMock(
            return_value=["#email", ".email-input"]
        )
        selector_manager.learner = None

        page.wait_for_selector = AsyncMock()
        page.locator = MagicMock(return_value=expected_locator)

        smart_wait = SmartWait(selector_manager)
        result = await smart_wait.find_element(page, "login.email")

        assert result == expected_locator
        page.wait_for_selector.assert_called()

    @pytest.mark.asyncio
    async def test_stage2_fallback_to_second_selector(self):
        """Test Stage 2 fallback when first selector fails."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(
            return_value=["#email", ".email-input"]
        )
        selector_manager.learner = None

        # First selector fails, second succeeds
        page.wait_for_selector = AsyncMock(
            side_effect=[Exception("First failed"), None]
        )
        page.locator = MagicMock(return_value=expected_locator)

        smart_wait = SmartWait(selector_manager)
        result = await smart_wait.find_element(page, "login.email")

        assert result == expected_locator
        assert page.wait_for_selector.call_count >= 2

    @pytest.mark.asyncio
    async def test_stage2_exponential_backoff_retries(self):
        """Test Stage 2 uses exponential backoff for retries."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(return_value=["#email"])
        selector_manager.learner = None

        # Fail twice, succeed on third
        page.wait_for_selector = AsyncMock(
            side_effect=[Exception("1"), Exception("2"), None]
        )
        page.locator = MagicMock(return_value=expected_locator)

        smart_wait = SmartWait(selector_manager, max_retries=3, backoff_factor=1.5)
        result = await smart_wait._try_css_selectors(page, "login.email", 10000)

        assert result == expected_locator
        # Should have tried 3 times on the selector
        assert page.wait_for_selector.call_count == 3

    @pytest.mark.asyncio
    async def test_stage2_learning_integration_success(self):
        """Test Stage 2 records success in learning system."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(return_value=["#email"])

        # Mock learner
        learner = MagicMock()
        learner.get_optimized_order = MagicMock(return_value=["#email"])
        learner.record_success = MagicMock()
        learner.record_failure = MagicMock()
        selector_manager.learner = learner

        page.wait_for_selector = AsyncMock()
        page.locator = MagicMock(return_value=expected_locator)

        smart_wait = SmartWait(selector_manager)
        await smart_wait.find_element(page, "login.email")

        # Should record success
        learner.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage2_learning_integration_failure(self):
        """Test Stage 2 records failure in learning system."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)

        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(return_value=["#email"])

        learner = MagicMock()
        learner.get_optimized_order = MagicMock(return_value=["#email"])
        learner.record_failure = MagicMock()
        selector_manager.learner = learner

        # All retries fail
        page.wait_for_selector = AsyncMock(side_effect=Exception("Failed"))

        smart_wait = SmartWait(selector_manager)
        result = await smart_wait._try_css_selectors(page, "login.email", 10000)

        assert result is None
        # Should record failure
        assert learner.record_failure.call_count >= 1


class TestStage3AI:
    """Tests for Stage 3: AI-powered repair."""

    @pytest.mark.asyncio
    async def test_stage3_triggers_when_css_fails(self):
        """Test Stage 3 triggers when all CSS selectors fail."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)
        expected_locator = MagicMock(spec=Locator)

        # Stage 1 & 2 fail
        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(return_value=["#email"])
        selector_manager.learner = None
        selector_manager.get = MagicMock(return_value="#email")
        selector_manager._generate_element_description = MagicMock(
            return_value="Email input"
        )

        # CSS fails
        page.wait_for_selector = AsyncMock(side_effect=Exception("Failed"))
        page.content = AsyncMock(return_value="<html></html>")

        # Stage 3 succeeds
        ai_repair = MagicMock()
        ai_repair.enabled = True
        ai_repair.repair_selector = AsyncMock(
            return_value=MagicMock(
                is_found=True, new_selector="#new-email", confidence=0.9
            )
        )
        ai_repair.persist_to_yaml = MagicMock(return_value=True)

        # Validate AI suggestion
        page.locator = MagicMock(return_value=expected_locator)

        smart_wait = SmartWait(selector_manager, ai_repair)

        # Mock wait_for_selector for validation (called after repair)
        validation_calls = []

        async def mock_wait(*args, **kwargs):
            validation_calls.append(args)
            if len(validation_calls) > 3:  # After CSS retries
                return  # Validation succeeds

            raise Exception("CSS failed")

        page.wait_for_selector = AsyncMock(side_effect=mock_wait)

        result = await smart_wait.find_element(page, "login.email")

        assert result == expected_locator
        ai_repair.repair_selector.assert_called_once()

    @pytest.mark.asyncio
    async def test_stage3_not_triggered_when_ai_disabled(self):
        """Test Stage 3 not triggered when AI repair is disabled."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)

        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(return_value=["#email"])
        selector_manager.learner = None

        page.wait_for_selector = AsyncMock(side_effect=Exception("Failed"))

        # AI disabled
        ai_repair = None

        smart_wait = SmartWait(selector_manager, ai_repair)

        with pytest.raises(SelectorNotFoundError):
            await smart_wait.find_element(page, "login.email")


class TestTotalFailure:
    """Tests for total failure across all stages."""

    @pytest.mark.asyncio
    async def test_total_failure_raises_exception(self):
        """Test that total failure raises SelectorNotFoundError."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)

        # All stages fail
        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(
            return_value=["#email", ".email-input"]
        )
        selector_manager.learner = None

        page.wait_for_selector = AsyncMock(side_effect=Exception("Failed"))

        smart_wait = SmartWait(selector_manager, ai_repair=None)

        with pytest.raises(SelectorNotFoundError) as exc_info:
            await smart_wait.find_element(page, "login.email")

        assert exc_info.value.selector_name == "login.email"
        assert "#email" in exc_info.value.tried_selectors

    @pytest.mark.asyncio
    async def test_total_failure_includes_action_context(self):
        """Test that error includes action context when provided."""
        selector_manager = MagicMock()
        page = MagicMock(spec=Page)

        selector_manager._get_semantic = MagicMock(return_value=None)
        selector_manager.get_with_fallback = MagicMock(return_value=["#email"])
        selector_manager.learner = None

        page.wait_for_selector = AsyncMock(side_effect=Exception("Failed"))

        smart_wait = SmartWait(selector_manager)

        with pytest.raises(SelectorNotFoundError):
            await smart_wait.find_element(
                page, "login.email", action_context="filling email field"
            )
