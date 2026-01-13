"""Simple tests for captcha solver to increase coverage."""

import pytest
from src.captcha_solver import CaptchaSolver, CaptchaProvider
from unittest.mock import AsyncMock
from playwright.async_api import Page


class TestCaptchaSolverBasics:
    """Test basic captcha solver functionality."""

    def test_init_manual(self):
        """Test manual solver initialization."""
        solver = CaptchaSolver(provider="manual", manual_timeout=60)
        assert solver.provider == "manual"
        assert solver.manual_timeout == 60

    def test_init_2captcha(self):
        """Test 2captcha solver initialization."""
        solver = CaptchaSolver(provider="2captcha", api_key="test_key")
        assert solver.provider == "2captcha"
        assert solver.api_key == "test_key"

    def test_init_anticaptcha(self):
        """Test anticaptcha solver initialization."""
        solver = CaptchaSolver(provider="anticaptcha", api_key="test_key")
        assert solver.provider == "anticaptcha"

    def test_init_nopecha(self):
        """Test nopecha solver initialization."""
        solver = CaptchaSolver(provider="nopecha", api_key="test_key")
        assert solver.provider == "nopecha"

    def test_provider_enum(self):
        """Test CaptchaProvider enum."""
        assert CaptchaProvider.MANUAL.value == "manual"
        assert CaptchaProvider.TWOCAPTCHA.value == "2captcha"
        assert CaptchaProvider.ANTICAPTCHA.value == "anticaptcha"
        assert CaptchaProvider.NOPECHA.value == "nopecha"


@pytest.mark.asyncio
class TestCaptchaSolverMethods:
    """Test captcha solver methods."""

    async def test_is_captcha_present_method_exists(self):
        """Test is_captcha_present method exists."""
        solver = CaptchaSolver(provider="manual")
        page = AsyncMock(spec=Page)
        page.query_selector = AsyncMock(return_value=None)

        # Method should exist and be callable
        assert hasattr(solver, "is_captcha_present")

    async def test_solve_recaptcha_unsupported_provider(self):
        """Test solving with unsupported provider."""
        solver = CaptchaSolver(provider="unknown")
        page = AsyncMock(spec=Page)

        result = await solver.solve_recaptcha(page, "test_key", "https://example.com")
        assert result is None
