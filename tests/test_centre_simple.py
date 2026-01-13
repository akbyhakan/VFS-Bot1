"""Simple tests for centre fetcher to increase coverage."""

import pytest
from src.centre_fetcher import CentreFetcher
from unittest.mock import AsyncMock
from playwright.async_api import Page


class TestCentreFetcherBasics:
    """Test basic centre fetcher functionality."""

    def test_init(self):
        """Test centre fetcher initialization."""
        fetcher = CentreFetcher(base_url="https://visa.vfsglobal.com", country="tur", mission="deu")
        assert fetcher.base_url == "https://visa.vfsglobal.com"
        assert fetcher.country == "tur"
        assert fetcher.mission == "deu"
        assert fetcher.cache == {}

    def test_cache_initialized(self):
        """Test cache is properly initialized."""
        fetcher = CentreFetcher(base_url="https://visa.vfsglobal.com", country="tur", mission="deu")
        assert isinstance(fetcher.cache, dict)


@pytest.mark.asyncio
class TestCentreFetcherMethods:
    """Test centre fetcher methods."""

    async def test_get_available_centres_cache(self):
        """Test getting centres from cache."""
        fetcher = CentreFetcher(base_url="https://visa.vfsglobal.com", country="tur", mission="deu")
        page = AsyncMock(spec=Page)

        # Pre-populate cache
        fetcher.cache["centres"] = ["Istanbul", "Ankara"]

        centres = await fetcher.get_available_centres(page)

        assert centres == ["Istanbul", "Ankara"]
        # Page should not be used when cache hits
        page.goto.assert_not_called()
