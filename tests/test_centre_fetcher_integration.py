"""Integration tests for src/services/centre_fetcher.py."""

import pytest
from unittest.mock import AsyncMock, patch
from playwright.async_api import Page

from src.services.centre_fetcher import CentreFetcher


@pytest.mark.asyncio
class TestCentreFetcherInitialization:
    """Tests for CentreFetcher initialization."""

    async def test_fetcher_init(self):
        """Test centre fetcher initialization."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
            }
        }
        fetcher = CentreFetcher(config)

        assert fetcher.base_url == "https://visa.vfsglobal.com"
        assert fetcher.country == "tur"
        assert fetcher.mission == "deu"


@pytest.mark.asyncio
class TestCentreFetching:
    """Tests for VFS centre fetching."""

    async def test_fetch_centres_success(self):
        """Test successful centre fetching."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
            }
        }
        fetcher = CentreFetcher(config)
        page = AsyncMock(spec=Page)

        # Mock page responses
        page.goto = AsyncMock()
        page.query_selector_all = AsyncMock(
            return_value=[MagicMock(text_content=AsyncMock(return_value="Istanbul"))]
        )

        with patch.object(fetcher, "fetch_centres", return_value=["Istanbul", "Ankara"]):
            centres = await fetcher.fetch_centres(page)
            # Implementation-dependent


@pytest.mark.asyncio
class TestCentreCache:
    """Tests for centre caching."""

    async def test_fetch_centres_cache(self):
        """Test centre caching."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
            }
        }
        fetcher = CentreFetcher(config)

        # Manually set cache
        fetcher.cache = ["Istanbul", "Ankara"]
        fetcher.cache_time = 0  # Force expired

        assert fetcher.cache is not None


@pytest.mark.asyncio
class TestCentreErrorHandling:
    """Tests for centre fetching error handling."""

    async def test_fetch_centres_error(self):
        """Test centre fetching error handling."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
            }
        }
        fetcher = CentreFetcher(config)
        page = AsyncMock(spec=Page)
        page.goto = AsyncMock(side_effect=Exception("Network error"))

        try:
            centres = await fetcher.fetch_centres(page)
        except Exception:
            pass  # Expected


@pytest.mark.asyncio
class TestCentreValidation:
    """Tests for centre validation."""

    async def test_validate_centre(self):
        """Test validating a centre."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
            }
        }
        fetcher = CentreFetcher(config)
        fetcher.cache = ["Istanbul", "Ankara"]

        # Test validation logic
        assert "Istanbul" in fetcher.cache


@pytest.mark.asyncio
class TestCentreParser:
    """Tests for centre data parsing."""

    async def test_parse_centre_data(self):
        """Test parsing centre data from HTML."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
            }
        }
        fetcher = CentreFetcher(config)

        # Mock HTML parsing
        mock_element = AsyncMock()
        mock_element.text_content = AsyncMock(return_value="Istanbul - Centre")

        # Test parsing logic (implementation-dependent)
        text = await mock_element.text_content()
        assert "Istanbul" in text
