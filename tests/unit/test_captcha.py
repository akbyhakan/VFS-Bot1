"""Tests for captcha solver."""

import asyncio
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


def test_captcha_solver_repr_masks_api_key():
    """Test that __repr__ masks the API key."""
    solver = CaptchaSolver(api_key="very_secret_key_12345")
    repr_str = repr(solver)
    assert "very_secret_key_12345" not in repr_str
    assert "***" in repr_str
    assert "CaptchaSolver" in repr_str


def test_captcha_solver_str_masks_api_key():
    """Test that __str__ masks the API key."""
    solver = CaptchaSolver(api_key="very_secret_key_12345")
    str_repr = str(solver)
    assert "very_secret_key_12345" not in str_repr
    assert "***" in str_repr


def test_captcha_solver_short_key_masking():
    """Test that short API keys are also fully masked."""
    solver = CaptchaSolver(api_key="short")
    repr_str = repr(solver)
    assert "short" not in repr_str
    assert "***" in repr_str


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

    # Mock slow solving that exceeds timeout
    mock_solver_instance = MagicMock()

    # Make the synchronous call slow
    def blocking_slow_solve(*args, **kwargs):
        import time

        time.sleep(2)  # Simulate slow 2Captcha API call
        return {"code": "token"}

    mock_solver_instance.turnstile = MagicMock(side_effect=blocking_slow_solve)

    with patch("twocaptcha.TwoCaptcha", return_value=mock_solver_instance):
        # Test with 1 second timeout - should timeout
        token = await solver.solve_turnstile(
            page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key", timeout=1
        )

        # Should return None due to timeout
        assert token is None


@pytest.mark.asyncio
async def test_solve_turnstile_executor_shutdown():
    """Test Turnstile solving after executor shutdown - executor is auto-recreated."""
    solver = CaptchaSolver(api_key="test_api_key")

    # Shutdown the executor
    CaptchaSolver.shutdown(wait=False)
    assert CaptchaSolver._executor is None

    # Mock TwoCaptcha
    mock_solver_instance = MagicMock()
    mock_solver_instance.turnstile = MagicMock(return_value={"code": "token-after-shutdown"})

    with patch("twocaptcha.TwoCaptcha", return_value=mock_solver_instance):
        # Should still work - executor is auto-recreated by _get_or_create_executor()
        token = await solver.solve_turnstile(
            page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key", timeout=120
        )

        # Should succeed with auto-recreated executor
        assert token == "token-after-shutdown"

    # Verify executor was re-created
    assert CaptchaSolver._executor is not None


@pytest.mark.asyncio
async def test_solve_recaptcha_executor_shutdown():
    """Test reCAPTCHA solving after executor shutdown - executor is auto-recreated."""
    solver = CaptchaSolver(api_key="test_api_key")

    # Shutdown the executor
    CaptchaSolver.shutdown(wait=False)
    assert CaptchaSolver._executor is None

    # Mock TwoCaptcha
    mock_solver_instance = MagicMock()
    mock_solver_instance.recaptcha = MagicMock(return_value={"code": "recaptcha-token"})

    with patch("twocaptcha.TwoCaptcha", return_value=mock_solver_instance):
        mock_page = MagicMock()
        # Should still work - executor is auto-recreated by _get_or_create_executor()
        token = await solver.solve_recaptcha(
            page=mock_page, site_key="mock-site-key", url="https://example.com"
        )

        # Should succeed with auto-recreated executor
        assert token == "recaptcha-token"

    # Verify executor was re-created
    assert CaptchaSolver._executor is not None
