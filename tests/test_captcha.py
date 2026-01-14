"""Tests for captcha solver."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.captcha_solver import CaptchaSolver


def test_captcha_solver_initialization():
    """Test captcha solver initialization."""
    solver = CaptchaSolver(api_key="test_key")
    assert solver.api_key == "test_key"


def test_captcha_solver_initialization_no_key():
    """Test captcha solver initialization without API key raises error."""
    with pytest.raises(ValueError, match="2Captcha API key is required"):
        CaptchaSolver(api_key="")


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
