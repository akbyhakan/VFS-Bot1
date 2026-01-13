"""Extended tests for captcha solver and centre fetcher - Target 50%+ coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.captcha_solver import CaptchaSolver, CaptchaProvider
from src.services.centre_fetcher import CentreFetcher


# CaptchaSolver tests
def test_captcha_solver_initialization_manual():
    """Test CaptchaSolver with manual provider."""
    solver = CaptchaSolver(provider="manual", manual_timeout=60)
    assert solver.provider == "manual"
    assert solver.manual_timeout == 60


def test_captcha_solver_initialization_2captcha():
    """Test CaptchaSolver with 2captcha provider."""
    solver = CaptchaSolver(provider="2captcha", api_key="test_key_123")
    assert solver.provider == "2captcha"
    assert solver.api_key == "test_key_123"


def test_captcha_provider_enum():
    """Test CaptchaProvider enum values."""
    assert CaptchaProvider.MANUAL.value == "manual"
    assert CaptchaProvider.TWOCAPTCHA.value == "2captcha"
    assert CaptchaProvider.ANTICAPTCHA.value == "anticaptcha"
    assert CaptchaProvider.NOPECHA.value == "nopecha"


@pytest.mark.asyncio
async def test_solve_recaptcha_manual():
    """Test solving reCAPTCHA with manual provider."""
    solver = CaptchaSolver(provider="manual", manual_timeout=5)
    page = AsyncMock()

    with patch.object(solver, "_solve_manually", new_callable=AsyncMock) as mock_manual:
        mock_manual.return_value = "manual_token_123"
        result = await solver.solve_recaptcha(page, "site_key", "https://example.com")
        assert result == "manual_token_123"
        mock_manual.assert_called_once()


@pytest.mark.asyncio
async def test_solve_recaptcha_2captcha():
    """Test solving reCAPTCHA with 2captcha."""
    solver = CaptchaSolver(provider="2captcha", api_key="test_key")
    page = AsyncMock()

    with patch.object(solver, "_solve_with_2captcha", new_callable=AsyncMock) as mock_2cap:
        mock_2cap.return_value = "2captcha_token"
        result = await solver.solve_recaptcha(page, "site_key", "https://example.com")
        assert result == "2captcha_token"
        mock_2cap.assert_called_once_with("site_key", "https://example.com")


@pytest.mark.asyncio
async def test_solve_recaptcha_anticaptcha():
    """Test solving reCAPTCHA with anticaptcha."""
    solver = CaptchaSolver(provider="anticaptcha", api_key="test_key")
    page = AsyncMock()

    with patch.object(solver, "_solve_with_anticaptcha", new_callable=AsyncMock) as mock_anti:
        mock_anti.return_value = "anticaptcha_token"
        result = await solver.solve_recaptcha(page, "site_key", "https://example.com")
        assert result == "anticaptcha_token"


@pytest.mark.asyncio
async def test_solve_recaptcha_nopecha():
    """Test solving reCAPTCHA with nopecha."""
    solver = CaptchaSolver(provider="nopecha", api_key="test_key")
    page = AsyncMock()

    with patch.object(solver, "_solve_with_nopecha", new_callable=AsyncMock) as mock_nopecha:
        mock_nopecha.return_value = "nopecha_token"
        result = await solver.solve_recaptcha(page, "site_key", "https://example.com")
        assert result == "nopecha_token"


@pytest.mark.asyncio
async def test_solve_recaptcha_unknown_provider():
    """Test solving reCAPTCHA with unknown provider falls back to manual."""
    solver = CaptchaSolver(provider="unknown_provider")
    page = AsyncMock()

    with patch.object(solver, "_solve_manually", new_callable=AsyncMock) as mock_manual:
        mock_manual.return_value = "fallback_token"
        result = await solver.solve_recaptcha(page, "site_key", "https://example.com")
        assert result == "fallback_token"


@pytest.mark.asyncio
async def test_solve_with_2captcha_error():
    """Test 2captcha error handling."""
    solver = CaptchaSolver(provider="2captcha", api_key="bad_key")

    with patch("twocaptcha.TwoCaptcha") as mock_class:
        mock_class.side_effect = Exception("API Error")
        result = await solver._solve_with_2captcha("site_key", "https://example.com")
        assert result is None


@pytest.mark.asyncio
async def test_solve_manually_timeout():
    """Test manual solving with timeout."""
    solver = CaptchaSolver(provider="manual", manual_timeout=1)
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))

    result = await solver._solve_manually(page)
    assert result is None


# CentreFetcher tests
def test_centre_fetcher_initialization():
    """Test CentreFetcher initialization."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    assert fetcher.base_url == "https://visa.vfsglobal.com"
    assert fetcher.country == "tur"
    assert fetcher.mission == "deu"
    assert fetcher.cache == {}


@pytest.mark.asyncio
async def test_get_available_centres_success():
    """Test fetching available centres."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock(return_value=["Istanbul", "Ankara", "Izmir"])

    centres = await fetcher.get_available_centres(page)
    assert centres == ["Istanbul", "Ankara", "Izmir"]
    assert "centres" in fetcher.cache


@pytest.mark.asyncio
async def test_get_available_centres_cached():
    """Test that centres are cached."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    fetcher.cache["centres"] = ["Cached Centre 1", "Cached Centre 2"]

    page = AsyncMock()
    centres = await fetcher.get_available_centres(page)

    assert centres == ["Cached Centre 1", "Cached Centre 2"]
    # page.goto should not be called when using cache
    page.goto.assert_not_called()


@pytest.mark.asyncio
async def test_get_available_centres_error():
    """Test error handling when fetching centres."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=Exception("Network error"))

    centres = await fetcher.get_available_centres(page)
    assert centres == []


@pytest.mark.asyncio
async def test_get_categories_success():
    """Test fetching categories for a centre."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    page = AsyncMock()
    page.select_option = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock(return_value=["Tourism", "Business", "Student"])

    categories = await fetcher.get_categories(page, "Istanbul")
    assert categories == ["Tourism", "Business", "Student"]


@pytest.mark.asyncio
async def test_get_categories_cached():
    """Test that categories are cached."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    cache_key = "categories_Istanbul"
    fetcher.cache[cache_key] = ["Cached Category"]

    page = AsyncMock()
    categories = await fetcher.get_categories(page, "Istanbul")

    assert categories == ["Cached Category"]
    page.select_option.assert_not_called()


@pytest.mark.asyncio
async def test_get_categories_error():
    """Test error handling when fetching categories."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    page = AsyncMock()
    page.select_option = AsyncMock(side_effect=Exception("Selector not found"))

    categories = await fetcher.get_categories(page, "Istanbul")
    assert categories == []


@pytest.mark.asyncio
async def test_get_subcategories_success():
    """Test fetching subcategories."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    page = AsyncMock()
    page.select_option = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock(return_value=["Short Stay", "Long Stay"])

    subcategories = await fetcher.get_subcategories(page, "Istanbul", "Tourism")
    assert subcategories == ["Short Stay", "Long Stay"]


@pytest.mark.asyncio
async def test_get_subcategories_cached():
    """Test that subcategories are cached."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    cache_key = "subcategories_Istanbul_Tourism"
    fetcher.cache[cache_key] = ["Cached Subcategory"]

    page = AsyncMock()
    subcategories = await fetcher.get_subcategories(page, "Istanbul", "Tourism")

    assert subcategories == ["Cached Subcategory"]
    page.select_option.assert_not_called()


@pytest.mark.asyncio
async def test_get_subcategories_error():
    """Test error handling when fetching subcategories."""
    fetcher = CentreFetcher(
        base_url="https://visa.vfsglobal.com", country="tur", mission="deu"
    )
    page = AsyncMock()
    page.select_option = AsyncMock(side_effect=Exception("Page error"))

    subcategories = await fetcher.get_subcategories(page, "Istanbul", "Tourism")
    assert subcategories == []
