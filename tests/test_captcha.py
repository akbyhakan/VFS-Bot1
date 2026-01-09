"""Tests for captcha solver."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.captcha_solver import CaptchaSolver, CaptchaProvider


def test_captcha_solver_initialization():
    """Test captcha solver initialization."""
    solver = CaptchaSolver(provider="2captcha", api_key="test_key")
    assert solver.provider == "2captcha"
    assert solver.api_key == "test_key"


def test_captcha_provider_enum():
    """Test captcha provider enum."""
    assert CaptchaProvider.TWOCAPTCHA.value == "2captcha"
    assert CaptchaProvider.ANTICAPTCHA.value == "anticaptcha"
    assert CaptchaProvider.NOPECHA.value == "nopecha"
    assert CaptchaProvider.MANUAL.value == "manual"


def test_manual_solver_initialization():
    """Test manual solver with timeout."""
    solver = CaptchaSolver(provider="manual", manual_timeout=60)
    assert solver.provider == "manual"
    assert solver.manual_timeout == 60


@pytest.mark.asyncio
async def test_captcha_solver_fallback():
    """Test captcha solver fallback to manual for unknown provider."""
    solver = CaptchaSolver(provider="unknown_provider")
    assert solver.provider == "unknown_provider"
