"""Basic tests for service modules to boost coverage."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.captcha_solver import CaptchaSolver
from src.services.centre_fetcher import CentreFetcher
from src.services.payment_service import PaymentService, PaymentMethod


def test_captcha_solver_initialization():
    """Test CaptchaSolver initialization."""
    solver = CaptchaSolver(provider="manual", api_key="", manual_timeout=120)
    assert solver is not None
    assert solver.provider == "manual"


def test_captcha_solver_manual_provider():
    """Test manual captcha provider."""
    solver = CaptchaSolver(provider="manual", api_key="", manual_timeout=60)
    assert solver.provider == "manual"
    assert solver.manual_timeout == 60


def test_captcha_solver_2captcha_provider():
    """Test 2captcha provider initialization."""
    solver = CaptchaSolver(provider="2captcha", api_key="test_key", manual_timeout=120)
    assert solver.provider == "2captcha"


def test_captcha_solver_nopecha_provider():
    """Test nopecha provider initialization."""
    solver = CaptchaSolver(provider="nopecha", api_key="test_key", manual_timeout=120)
    assert solver.provider == "nopecha"


def test_centre_fetcher_initialization():
    """Test CentreFetcher initialization."""
    fetcher = CentreFetcher(base_url="https://visa.vfsglobal.com", country="tur", mission="deu")
    assert fetcher is not None
    assert fetcher.base_url == "https://visa.vfsglobal.com"
    assert fetcher.country == "tur"
    assert fetcher.mission == "deu"


def test_payment_service_initialization_manual():
    """Test PaymentService initialization with manual payment."""
    config = {"method": "manual", "timeout": 300}
    service = PaymentService(config)

    assert service is not None
    assert service.method == PaymentMethod.MANUAL
    assert service.timeout == 300


def test_payment_service_initialization_defaults():
    """Test PaymentService initialization with defaults."""
    config = {}
    service = PaymentService(config)

    assert service.method == PaymentMethod.MANUAL
    assert service.timeout == 300


def test_payment_service_initialization_automated():
    """Test PaymentService initialization with automated payment."""
    config = {"method": "automated_card", "timeout": 600}
    service = PaymentService(config)

    assert service.method == PaymentMethod.AUTOMATED_CARD
    assert service.timeout == 600


def test_payment_method_enum():
    """Test PaymentMethod enum values."""
    assert PaymentMethod.MANUAL.value == "manual"
    assert PaymentMethod.AUTOMATED_CARD.value == "automated_card"


def test_payment_method_enum_from_string():
    """Test creating PaymentMethod from string."""
    method = PaymentMethod("manual")
    assert method == PaymentMethod.MANUAL

    method2 = PaymentMethod("automated_card")
    assert method2 == PaymentMethod.AUTOMATED_CARD
