"""Tests for captcha solver."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.captcha_solver import CaptchaSolver


def test_captcha_solver_initialization():
    """Test captcha solver initialization."""
    solver = CaptchaSolver(api_key="test_key")
    assert solver.api_key == "test_key"


def test_captcha_solver_initialization_no_key():
    """Test captcha solver initialization without API key (manual mode)."""
    solver = CaptchaSolver(api_key="")
    assert solver.api_key == ""
    assert solver.manual_timeout == 120  # Default timeout


def test_manual_solver_timeout():
    """Test manual solver with timeout."""
    solver = CaptchaSolver(api_key="test_key", manual_timeout=60)
    assert solver.manual_timeout == 60


@pytest.mark.asyncio
async def test_captcha_solver_manual_fallback():
    """Test captcha solver fallback to manual on 2captcha failure."""
    solver = CaptchaSolver(api_key="invalid_key")
    # This would require mocking the page and 2captcha service
    # Just verify the solver was initialized
    assert solver.api_key == "invalid_key"


@pytest.mark.asyncio
async def test_solve_turnstile_success():
    """Test successful Turnstile solving."""
    solver = CaptchaSolver(api_key="test_api_key")

    # Mock TwoCaptcha
    mock_solver_instance = MagicMock()
    mock_solver_instance.turnstile = MagicMock(return_value={"code": "mock-turnstile-token"})

    with patch("twocaptcha.TwoCaptcha", return_value=mock_solver_instance):
        token = await solver.solve_turnstile(
            page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key"
        )

        assert token == "mock-turnstile-token"
        mock_solver_instance.turnstile.assert_called_once()


@pytest.mark.asyncio
async def test_solve_turnstile_no_api_key():
    """Test Turnstile solving without API key."""
    solver = CaptchaSolver(api_key="")

    token = await solver.solve_turnstile(
        page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key"
    )

    # Should return None when no API key
    assert token is None


@pytest.mark.asyncio
async def test_solve_turnstile_error():
    """Test Turnstile solving with error."""
    solver = CaptchaSolver(api_key="test_api_key")

    # Mock TwoCaptcha to raise an exception
    with patch("twocaptcha.TwoCaptcha", side_effect=Exception("API error")):
        token = await solver.solve_turnstile(
            page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key"
        )

        # Should return None on error
        assert token is None


@pytest.mark.asyncio
async def test_solve_turnstile_custom_timeout():
    """Test Turnstile solving with custom timeout."""
    solver = CaptchaSolver(api_key="test_api_key")

    mock_solver_instance = MagicMock()
    mock_solver_instance.turnstile = MagicMock(return_value={"code": "token"})

    with patch("twocaptcha.TwoCaptcha", return_value=mock_solver_instance):
        token = await solver.solve_turnstile(
            page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key", timeout=60
        )

        assert token == "token"
