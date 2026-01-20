"""Tests for cache TTL functionality."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import Page

from src.services.centre_fetcher import CentreFetcher, CacheEntry


class TestCacheEntry:
    """Tests for CacheEntry class."""
    
    def test_cache_entry_not_expired(self):
        """Test cache entry is not expired immediately."""
        entry = CacheEntry(value="test", ttl_seconds=3600)
        assert not entry.is_expired()
    
    def test_cache_entry_expired(self):
        """Test cache entry expiration."""
        entry = CacheEntry(value="test", ttl_seconds=0)
        # Small sleep to ensure expiration
        import time
        time.sleep(0.01)
        assert entry.is_expired()
    
    def test_cache_entry_custom_ttl(self):
        """Test cache entry with custom TTL."""
        entry = CacheEntry(value=["item1", "item2"], ttl_seconds=7200)
        assert entry.value == ["item1", "item2"]
        assert not entry.is_expired()


class TestCentreFetcherCache:
    """Tests for CentreFetcher caching."""
    
    @pytest.fixture
    def fetcher(self):
        """Create CentreFetcher instance."""
        return CentreFetcher(
            base_url="https://visa.vfsglobal.com",
            country="tur",
            mission="nld",
            cache_ttl=3600
        )
    
    def test_cache_set_and_get(self, fetcher):
        """Test setting and getting cache values."""
        fetcher._set_cache("test_key", ["value1", "value2"])
        result = fetcher._get_from_cache("test_key")
        assert result == ["value1", "value2"]
    
    def test_cache_miss(self, fetcher):
        """Test cache miss returns None."""
        result = fetcher._get_from_cache("nonexistent")
        assert result is None
    
    def test_cache_expiration(self, fetcher):
        """Test cache expiration."""
        # Set cache with very short TTL (1 second)
        fetcher._set_cache("test_key", "value", ttl=1)
        
        # Sleep longer than TTL to ensure expiration
        import time
        time.sleep(1.1)
        
        # Should return None as entry expired
        result = fetcher._get_from_cache("test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, fetcher):
        """Test cache clearing."""
        fetcher._set_cache("key1", "value1")
        fetcher._set_cache("key2", "value2")
        
        cleared = await fetcher.clear_cache_async()
        assert cleared == 2
        assert fetcher._get_from_cache("key1") is None
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, fetcher):
        """Test cleanup of expired entries."""
        # Add one valid entry
        fetcher._set_cache("valid_key", "valid_value", ttl=3600)
        
        # Add two expired entries with 1 second TTL
        fetcher._set_cache("expired_key1", "value1", ttl=1)
        fetcher._set_cache("expired_key2", "value2", ttl=1)
        
        # Sleep longer than TTL to ensure expiration
        import time
        time.sleep(1.1)
        
        # Cleanup should remove 2 expired entries
        removed = await fetcher.cleanup_expired()
        assert removed == 2
        
        # Valid entry should still exist
        assert fetcher._get_from_cache("valid_key") == "valid_value"
    
    @pytest.mark.asyncio
    async def test_get_available_centres_uses_cache(self, fetcher):
        """Test that get_available_centres uses cache."""
        # Mock page
        mock_page = AsyncMock(spec=Page)
        
        # Set cache manually
        centres = ["Istanbul", "Ankara"]
        fetcher._set_cache(f"centres_{fetcher.mission}", centres)
        
        # Should return cached value without calling page methods
        result = await fetcher.get_available_centres(mock_page)
        
        assert result == centres
        mock_page.goto.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_ttl_configuration(self):
        """Test cache TTL configuration."""
        # Create fetcher with custom TTL
        custom_fetcher = CentreFetcher(
            base_url="https://visa.vfsglobal.com",
            country="tur",
            mission="nld",
            cache_ttl=7200
        )
        
        assert custom_fetcher.cache_ttl == 7200
        
        # Default TTL
        default_fetcher = CentreFetcher(
            base_url="https://visa.vfsglobal.com",
            country="tur",
            mission="nld"
        )
        
        assert default_fetcher.cache_ttl == CentreFetcher.DEFAULT_CACHE_TTL
