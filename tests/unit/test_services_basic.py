"""Basic tests for service modules to boost coverage."""

import pytest

from src.services.captcha_solver import CaptchaSolver
from src.services.centre_fetcher import CentreFetcher
from src.services.payment_service import PaymentMethod, PaymentService


def test_captcha_solver_initialization():
    """Test CaptchaSolver initialization."""
    solver = CaptchaSolver(api_key="test_key")
    assert solver is not None
    assert solver.api_key == "test_key"


def test_captcha_solver_no_api_key():
    """Test CaptchaSolver raises ValueError without API key."""
    with pytest.raises(ValueError, match="2Captcha API key is required"):
        CaptchaSolver(api_key="")


def test_captcha_solver_2captcha_provider():
    """Test 2captcha provider initialization."""
    solver = CaptchaSolver(api_key="test_key")
    assert solver.api_key == "test_key"


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


def test_payment_method_enum():
    """Test PaymentMethod enum values."""
    assert PaymentMethod.MANUAL.value == "manual"


def test_payment_method_enum_from_string():
    """Test creating PaymentMethod from string."""
    method = PaymentMethod("manual")
    assert method == PaymentMethod.MANUAL
