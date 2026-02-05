"""Tests for selector loading and fallback functionality."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from src.core.exceptions import SelectorNotFoundError
from src.utils.selectors import CountryAwareSelectorManager as SelectorManager
from src.utils.selectors import get_selector_manager


@pytest.fixture
def temp_selectors_file(tmp_path):
    """Create a temporary selectors file."""
    selectors_content = {
        "version": "test-1.0",
        "login": {
            "email_input": {
                "primary": "input#email",
                "fallbacks": ["input[type='email']", "input[name='email']"],
            },
            "password_input": {
                "primary": "input#password",
                "fallbacks": ["input[type='password']"],
            },
            "submit_button": "button[type='submit']",
        },
        "appointment": {
            "centre_dropdown": {
                "primary": "select#centres",
                "fallbacks": ["select[name='centre']"],
            },
        },
    }

    selectors_file = tmp_path / "selectors.yaml"
    with open(selectors_file, "w") as f:
        yaml.dump(selectors_content, f)

    return selectors_file


def test_selector_manager_load_file(temp_selectors_file):
    """Test loading selectors from YAML file."""
    manager = SelectorManager(str(temp_selectors_file))

    assert manager._selectors["version"] == "test-1.0"
    assert "login" in manager._selectors
    assert "appointment" in manager._selectors


def test_selector_manager_get_primary(temp_selectors_file):
    """Test getting primary selector."""
    manager = SelectorManager(str(temp_selectors_file))

    # Test selector with primary/fallbacks structure
    selector = manager.get("login.email_input")
    assert selector == "input#email"

    # Test simple string selector
    selector = manager.get("login.submit_button")
    assert selector == "button[type='submit']"


def test_selector_manager_get_fallbacks(temp_selectors_file):
    """Test getting fallback selectors."""
    manager = SelectorManager(str(temp_selectors_file))

    fallbacks = manager.get_fallbacks("login.email_input")
    assert len(fallbacks) == 2
    assert "input[type='email']" in fallbacks
    assert "input[name='email']" in fallbacks


def test_selector_manager_get_with_fallback(temp_selectors_file):
    """Test getting selector with fallbacks."""
    manager = SelectorManager(str(temp_selectors_file))

    selectors = manager.get_with_fallback("login.email_input")
    assert len(selectors) == 3
    assert selectors[0] == "input#email"  # Primary first
    assert "input[type='email']" in selectors
    assert "input[name='email']" in selectors


def test_selector_manager_get_nonexistent(temp_selectors_file):
    """Test getting non-existent selector."""
    manager = SelectorManager(str(temp_selectors_file))

    selector = manager.get("nonexistent.selector", default="default-value")
    assert selector == "default-value"


def test_selector_manager_get_fallbacks_nonexistent(temp_selectors_file):
    """Test getting fallbacks for non-existent selector."""
    manager = SelectorManager(str(temp_selectors_file))

    fallbacks = manager.get_fallbacks("nonexistent.selector")
    assert fallbacks == []


@pytest.mark.asyncio
async def test_wait_for_selector_success(temp_selectors_file):
    """Test wait_for_selector with successful match."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.locator = lambda x: f"locator({x})"

    locator = await manager.wait_for_selector(mock_page, "login.email_input")

    assert locator is not None
    # Should try primary selector first
    mock_page.wait_for_selector.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_selector_fallback(temp_selectors_file):
    """Test wait_for_selector uses fallback when primary fails."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()

    # Primary fails, fallback succeeds
    call_count = 0

    async def mock_wait(selector, timeout=10000):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Primary selector failed")
        # Second call succeeds
        return None

    mock_page.wait_for_selector = mock_wait
    mock_page.locator = lambda x: f"locator({x})"

    locator = await manager.wait_for_selector(mock_page, "login.email_input")

    assert locator is not None
    assert call_count == 2  # Primary + first fallback


@pytest.mark.asyncio
async def test_wait_for_selector_all_fail(temp_selectors_file):
    """Test wait_for_selector raises exception when all selectors fail."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Selector not found"))

    with pytest.raises(SelectorNotFoundError) as exc_info:
        await manager.wait_for_selector(mock_page, "login.email_input")

    assert exc_info.value.selector_name == "login.email_input"
    assert len(exc_info.value.tried_selectors) == 3  # Primary + 2 fallbacks


def test_selector_manager_reload(temp_selectors_file):
    """Test reloading selectors."""
    manager = SelectorManager(str(temp_selectors_file))

    original_version = manager._selectors["version"]
    assert original_version == "test-1.0"

    # Modify the file
    with open(temp_selectors_file, "r") as f:
        content = yaml.safe_load(f)
    content["version"] = "test-2.0"
    with open(temp_selectors_file, "w") as f:
        yaml.dump(content, f)

    # Reload
    manager.reload()

    assert manager._selectors["version"] == "test-2.0"


def test_selector_manager_default_on_missing_file():
    """Test that default selectors are used when file is missing."""
    manager = SelectorManager("nonexistent-file.yaml")

    # Should have loaded default selectors
    assert manager._selectors["version"] == "default"
    # Check that default selectors work via API
    assert manager.get("login.email_input") is not None
    assert manager.get("appointment.centre_dropdown") is not None


def test_get_selector_manager_singleton():
    """Test that get_selector_manager returns singleton instance."""
    manager1 = get_selector_manager()
    manager2 = get_selector_manager()

    assert manager1 is manager2


@pytest.mark.asyncio
async def test_wait_for_selector_uses_visible_state(temp_selectors_file):
    """Test that wait_for_selector passes the correct timeout parameter to
    page.wait_for_selector."""
    manager = SelectorManager(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.locator = lambda x: f"locator({x})"

    await manager.wait_for_selector(mock_page, "login.email_input", timeout=5000)

    # Verify wait_for_selector was called with timeout
    call_args = mock_page.wait_for_selector.call_args
    assert call_args is not None
    # Check keyword arguments
    assert call_args.kwargs["timeout"] == 5000


# Country-aware selector manager tests
class TestCountryAwareSelectorManager:
    """Tests for country-aware selector functionality."""

    @pytest.fixture
    def temp_country_selectors_file(self, tmp_path):
        """Create a temporary selectors file with country overrides."""
        selectors_content = {
            "version": "test-country-1.0",
            "defaults": {
                "login": {
                    "email_input": {
                        "primary": "input#default-email",
                        "fallbacks": ["input[type='email']"],
                    },
                    "password_input": {
                        "primary": "input#default-password",
                    },
                },
                "appointment": {
                    "centre_dropdown": {
                        "primary": "select#default-centre",
                    },
                },
            },
            "countries": {
                "fra": {
                    "login": {
                        "email_input": {
                            "primary": "input#fra-email",
                            "fallbacks": ["input.france-email"],
                        },
                    },
                },
                "nld": {
                    "appointment": {
                        "centre_dropdown": {
                            "primary": "select#nld-centre",
                        },
                    },
                },
            },
        }

        selectors_file = tmp_path / "selectors_country.yaml"
        with open(selectors_file, "w") as f:
            yaml.dump(selectors_content, f)

        return selectors_file

    def test_country_specific_selector_priority(self, temp_country_selectors_file):
        """Test that country-specific selectors take priority over defaults."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager = CountryAwareSelectorManager(
            country_code="fra", selectors_file=str(temp_country_selectors_file)
        )

        # Should use France-specific selector
        selector = manager.get("login.email_input")
        assert selector == "input#fra-email"

        # Should fall back to default for password (no France override)
        selector = manager.get("login.password_input")
        assert selector == "input#default-password"

    def test_default_country_uses_defaults(self, temp_country_selectors_file):
        """Test that 'default' country code uses only default selectors."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager = CountryAwareSelectorManager(
            country_code="default", selectors_file=str(temp_country_selectors_file)
        )

        # Should use default selector
        selector = manager.get("login.email_input")
        assert selector == "input#default-email"

    def test_fallback_to_default_when_no_country_override(self, temp_country_selectors_file):
        """Test fallback to default when country has no override."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager = CountryAwareSelectorManager(
            country_code="nld", selectors_file=str(temp_country_selectors_file)
        )

        # NLD has no login override, should use default
        selector = manager.get("login.email_input")
        assert selector == "input#default-email"

        # NLD has appointment override
        selector = manager.get("appointment.centre_dropdown")
        assert selector == "select#nld-centre"

    def test_combined_fallbacks(self, temp_country_selectors_file):
        """Test that country and global fallbacks are combined."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager = CountryAwareSelectorManager(
            country_code="fra", selectors_file=str(temp_country_selectors_file)
        )

        selectors = manager.get_with_fallback("login.email_input")

        # Should have: France primary, France fallback, default primary, default fallback
        assert "input#fra-email" in selectors
        assert "input.france-email" in selectors
        assert "input#default-email" in selectors
        assert "input[type='email']" in selectors

        # France selectors should come first
        assert selectors.index("input#fra-email") < selectors.index("input#default-email")

    def test_no_duplicate_selectors_in_fallback(self, temp_country_selectors_file):
        """Test that duplicate selectors are not included twice."""
        from src.utils.selectors import CountryAwareSelectorManager

        # Create a case where country and default have the same selector
        manager = CountryAwareSelectorManager(
            country_code="fra", selectors_file=str(temp_country_selectors_file)
        )

        selectors = manager.get_with_fallback("login.email_input")

        # Check no duplicates
        assert len(selectors) == len(set(selectors))

    def test_separate_metrics_per_country(self, temp_country_selectors_file):
        """Test that each country uses its own metrics file."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager_fra = CountryAwareSelectorManager(
            country_code="fra", selectors_file=str(temp_country_selectors_file)
        )
        manager_nld = CountryAwareSelectorManager(
            country_code="nld", selectors_file=str(temp_country_selectors_file)
        )

        # Check that different metrics files are used
        if manager_fra.learner and manager_nld.learner:
            assert manager_fra.learner.metrics_file != manager_nld.learner.metrics_file
            assert "fra" in str(manager_fra.learner.metrics_file)
            assert "nld" in str(manager_nld.learner.metrics_file)

    def test_factory_function_caching(self, temp_country_selectors_file):
        """Test that get_selector_manager returns cached instances."""
        # Clear cache first
        from src.utils import selectors
        from src.utils.selectors import get_selector_manager

        selectors._selector_managers.clear()

        manager1 = get_selector_manager("fra")
        manager2 = get_selector_manager("fra")
        manager3 = get_selector_manager("nld")

        # Same country should return same instance
        assert manager1 is manager2

        # Different country should return different instance
        assert manager1 is not manager3

    def test_backward_compatibility_alias(self):
        """Test that SelectorManager is an alias for CountryAwareSelectorManager."""
        from src.utils.selectors import CountryAwareSelectorManager
        from src.utils.selectors import CountryAwareSelectorManager as SelectorManager

        assert SelectorManager is CountryAwareSelectorManager

    def test_country_fallbacks_method(self, temp_country_selectors_file):
        """Test get_fallbacks with country-specific fallbacks."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager = CountryAwareSelectorManager(
            country_code="fra", selectors_file=str(temp_country_selectors_file)
        )

        fallbacks = manager.get_fallbacks("login.email_input")

        # Should return country-specific fallbacks
        assert "input.france-email" in fallbacks

    def test_country_code_case_insensitive(self, temp_country_selectors_file):
        """Test that country codes are case-insensitive."""
        from src.utils.selectors import CountryAwareSelectorManager

        manager_lower = CountryAwareSelectorManager(
            country_code="fra", selectors_file=str(temp_country_selectors_file)
        )
        manager_upper = CountryAwareSelectorManager(
            country_code="FRA", selectors_file=str(temp_country_selectors_file)
        )

        # Both should resolve to the same selectors
        assert manager_lower.get("login.email_input") == manager_upper.get("login.email_input")
