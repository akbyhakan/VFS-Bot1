"""Tests for captcha solver."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.captcha_solver import CaptchaSolver


def test_captcha_solver_initialization():
    """Test captcha solver initialization."""
    solver = CaptchaSolver(api_key="test_key")
    assert solver.api_key == "test_key"


def test_captcha_solver_initialization_no_key():
    """Test captcha solver initialization without API key raises ValueError."""
    with pytest.raises(ValueError, match="2Captcha API key is required"):
        CaptchaSolver(api_key="")


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

