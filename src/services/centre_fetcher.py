"""Auto-fetch available centres, categories, and subcategories from VFS website."""

import logging
from typing import Any, List, Dict, Optional
from datetime import datetime, timedelta
from playwright.async_api import Page
import asyncio

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL support."""

    def __init__(self, value: Any, ttl_seconds: int = 3600):
        """
        Initialize cache entry.

        Args:
            value: Value to cache
            ttl_seconds: Time to live in seconds (default: 3600 = 1 hour)
        """
        self.value = value
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() >= self.expires_at


class CentreFetcher:
    """Fetch available centres and categories from VFS website."""

    DEFAULT_CACHE_TTL = 3600  # 1 hour

    def __init__(
        self, base_url: str, country: str, mission: str, language: str = "tr", cache_ttl: int = None
    ):
        """
        Initialize centre fetcher.

        Args:
            base_url: VFS base URL
            country: Country code (e.g., 'tur')
            mission: Mission code (e.g., 'deu')
            language: Language code (e.g., 'tr')
            cache_ttl: Cache TTL in seconds (default: 3600)
        """
        self.base_url = base_url
        self.country = country
        self.mission = mission
        self.language = language
        self.cache_ttl = cache_ttl or self.DEFAULT_CACHE_TTL
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_lock = asyncio.Lock()
        logger.info(
            "CentreFetcher initialized for %s/%s/%s (cache TTL: %ss)",
            country,
            language,
            mission,
            self.cache_ttl,
        )

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry.value
        elif entry:
            # Remove expired entry
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any, ttl: int = None) -> None:
        """
        Set cache value with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: use instance cache_ttl)
        """
        self._cache[key] = CacheEntry(value, ttl or self.cache_ttl)

    async def clear_cache(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        async with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared ({count} entries)")
            return count

    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        async with self._cache_lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.debug(f"Removed {len(expired_keys)} expired cache entries")
            return len(expired_keys)

    async def start_periodic_cleanup(self, interval_seconds: int = 300) -> asyncio.Task:
        """Start background task to periodically clean up expired cache entries."""

        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                removed = await self.cleanup_expired()
                if removed > 0:
                    logger.debug(f"Background cleanup removed {removed} expired cache entries")

        return asyncio.create_task(cleanup_loop())

    async def get_available_centres(self, page: Page) -> List[str]:
        """
        Fetch available VFS centres from the website with caching.

        Args:
            page: Playwright page object

        Returns:
            List of centre names
        """
        cache_key = f"centres_{self.mission}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.debug(f"Returning cached centres for {self.mission}")
            return cached

        try:
            # Navigate to appointment page
            url = f"{self.base_url}/{self.country}/{self.language}/{self.mission}/appointment"
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for centre dropdown to load
            await page.wait_for_selector("select#centres", timeout=10000)

            # Extract centre options
            centres_result = await page.evaluate("""
                () => {
                    const select = document.querySelector('select#centres');
                    if (!select) return [];
                    return Array.from(select.options)
                        .map(opt => opt.text.trim())
                        .filter(text => text && text !== 'Select Centre');
                }
            """)

            centres: List[str] = centres_result if isinstance(centres_result, list) else []

            # Cache the result
            self._set_cache(cache_key, centres)
            logger.info(f"Fetched and cached {len(centres)} centres: {centres}")
            return centres
        except Exception as e:
            logger.error(f"Failed to fetch centres: {e}")
            return []

    async def get_categories(self, page: Page, centre: str) -> List[str]:
        """
        Fetch available categories for a specific centre with caching.

        Args:
            page: Playwright page object
            centre: Centre name

        Returns:
            List of category names
        """
        cache_key = f"categories_{centre}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.debug(f"Returning cached categories for {centre}")
            return cached

        try:
            # Select the centre
            await page.select_option("select#centres", label=centre)
            
            # Use dynamic waiting instead of fixed sleep
            await asyncio.gather(
                page.wait_for_load_state("networkidle"),
                page.wait_for_selector("select#categories option:not([value=''])")
            )

            # Extract category options
            categories_result = await page.evaluate("""
                () => {
                    const select = document.querySelector('select#categories');
                    if (!select) return [];
                    return Array.from(select.options)
                        .map(opt => opt.text.trim())
                        .filter(text => text && text !== 'Select Category');
                }
            """)

            categories: List[str] = categories_result if isinstance(categories_result, list) else []

            # Cache the result
            self._set_cache(cache_key, categories)
            logger.info(
                f"Fetched and cached {len(categories)} categories for {centre}: {categories}"
            )
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch categories for {centre}: {e}")
            return []

    async def get_subcategories(self, page: Page, centre: str, category: str) -> List[str]:
        """
        Fetch available subcategories for a centre and category with caching.

        Args:
            page: Playwright page object
            centre: Centre name
            category: Category name

        Returns:
            List of subcategory names
        """
        cache_key = f"subcategories_{centre}_{category}"

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.debug(f"Returning cached subcategories for {centre}/{category}")
            return cached

        try:
            # Select the centre and category
            await page.select_option("select#centres", label=centre)
            await asyncio.gather(
                page.wait_for_load_state("networkidle"),
                page.wait_for_selector("select#categories option:not([value=''])")
            )
            await page.select_option("select#categories", label=category)
            
            # Use dynamic waiting instead of fixed sleep
            await asyncio.gather(
                page.wait_for_load_state("networkidle"),
                page.wait_for_selector("select#subcategories option:not([value=''])")
            )

            # Extract subcategory options
            subcategories_result = await page.evaluate("""
                () => {
                    const select = document.querySelector('select#subcategories');
                    if (!select) return [];
                    return Array.from(select.options)
                        .map(opt => opt.text.trim())
                        .filter(text => text && text !== 'Select Subcategory');
                }
            """)

            subcategories: List[str] = (
                subcategories_result if isinstance(subcategories_result, list) else []
            )

            # Cache the result
            self._set_cache(cache_key, subcategories)
            logger.info(f"Fetched and cached {len(subcategories)} subcategories: {subcategories}")
            return subcategories
        except Exception as e:
            logger.error(f"Failed to fetch subcategories: {e}")
            return []

    def clear_cache_sync(self) -> None:
        """
        Clear the cache synchronously (NOT THREAD-SAFE).

        WARNING: This method does not use the lock and should only be called
        from single-threaded contexts or when you're certain no other threads
        are accessing the cache. For safe async operation, use clear_cache().

        Note: This is provided for backward compatibility only.
        """
        self._cache.clear()
        logger.info("Cache cleared (sync, no lock)")

    async def clear_cache_async(self) -> int:
        """
        Clear all cache entries (async-compatible alias).

        Returns:
            Number of entries cleared
        """
        return await self.clear_cache()

    async def fetch_all_data(self, page: Page) -> Dict[str, Any]:
        """
        Fetch all available centres, categories, and subcategories.

        Args:
            page: Playwright page object

        Returns:
            Dictionary with complete data structure
        """
        data: Dict[str, Dict[str, List[str]]] = {}

        # Fetch centres
        centres = await self.get_available_centres(page)

        for centre in centres:
            data[centre] = {}

            # Fetch categories for this centre
            categories = await self.get_categories(page, centre)

            for category in categories:
                # Fetch subcategories
                subcategories = await self.get_subcategories(page, centre, category)
                data[centre][category] = subcategories

        logger.info(f"Fetched complete data structure for {len(centres)} centres")
        return data
