"""Auto-fetch available centres, categories, and subcategories from VFS website."""

import logging
from typing import List, Dict, Optional
from playwright.async_api import Page
import asyncio

logger = logging.getLogger(__name__)


class CentreFetcher:
    """Fetch available centres and categories from VFS website."""
    
    def __init__(self, base_url: str, country: str, mission: str):
        """
        Initialize centre fetcher.
        
        Args:
            base_url: VFS base URL
            country: Country code (e.g., 'tur')
            mission: Mission code (e.g., 'deu')
        """
        self.base_url = base_url
        self.country = country
        self.mission = mission
        self.cache: Dict[str, any] = {}
        logger.info(f"CentreFetcher initialized for {country}/{mission}")
    
    async def get_available_centres(self, page: Page) -> List[str]:
        """
        Fetch available VFS centres from the website.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of centre names
        """
        cache_key = "centres"
        if cache_key in self.cache:
            logger.info("Returning cached centres")
            return self.cache[cache_key]
        
        try:
            # Navigate to appointment page
            url = f"{self.base_url}/{self.country}/{self.mission}/en/appointment"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for centre dropdown to load
            await page.wait_for_selector('select#centres', timeout=10000)
            
            # Extract centre options
            centres = await page.evaluate("""
                () => {
                    const select = document.querySelector('select#centres');
                    if (!select) return [];
                    return Array.from(select.options)
                        .map(opt => opt.text.trim())
                        .filter(text => text && text !== 'Select Centre');
                }
            """)
            
            self.cache[cache_key] = centres
            logger.info(f"Fetched {len(centres)} centres: {centres}")
            return centres
        except Exception as e:
            logger.error(f"Failed to fetch centres: {e}")
            return []
    
    async def get_categories(self, page: Page, centre: str) -> List[str]:
        """
        Fetch available categories for a specific centre.
        
        Args:
            page: Playwright page object
            centre: Centre name
            
        Returns:
            List of category names
        """
        cache_key = f"categories_{centre}"
        if cache_key in self.cache:
            logger.info(f"Returning cached categories for {centre}")
            return self.cache[cache_key]
        
        try:
            # Select the centre
            await page.select_option('select#centres', label=centre)
            await asyncio.sleep(2)  # Wait for categories to load
            
            # Wait for category dropdown
            await page.wait_for_selector('select#categories', timeout=10000)
            
            # Extract category options
            categories = await page.evaluate("""
                () => {
                    const select = document.querySelector('select#categories');
                    if (!select) return [];
                    return Array.from(select.options)
                        .map(opt => opt.text.trim())
                        .filter(text => text && text !== 'Select Category');
                }
            """)
            
            self.cache[cache_key] = categories
            logger.info(f"Fetched {len(categories)} categories for {centre}: {categories}")
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch categories for {centre}: {e}")
            return []
    
    async def get_subcategories(self, page: Page, centre: str, category: str) -> List[str]:
        """
        Fetch available subcategories for a centre and category.
        
        Args:
            page: Playwright page object
            centre: Centre name
            category: Category name
            
        Returns:
            List of subcategory names
        """
        cache_key = f"subcategories_{centre}_{category}"
        if cache_key in self.cache:
            logger.info(f"Returning cached subcategories for {centre}/{category}")
            return self.cache[cache_key]
        
        try:
            # Select the centre and category
            await page.select_option('select#centres', label=centre)
            await asyncio.sleep(2)
            await page.select_option('select#categories', label=category)
            await asyncio.sleep(2)  # Wait for subcategories to load
            
            # Wait for subcategory dropdown
            await page.wait_for_selector('select#subcategories', timeout=10000)
            
            # Extract subcategory options
            subcategories = await page.evaluate("""
                () => {
                    const select = document.querySelector('select#subcategories');
                    if (!select) return [];
                    return Array.from(select.options)
                        .map(opt => opt.text.trim())
                        .filter(text => text && text !== 'Select Subcategory');
                }
            """)
            
            self.cache[cache_key] = subcategories
            logger.info(f"Fetched {len(subcategories)} subcategories: {subcategories}")
            return subcategories
        except Exception as e:
            logger.error(f"Failed to fetch subcategories: {e}")
            return []
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    async def fetch_all_data(self, page: Page) -> Dict[str, any]:
        """
        Fetch all available centres, categories, and subcategories.
        
        Args:
            page: Playwright page object
            
        Returns:
            Dictionary with complete data structure
        """
        data = {}
        
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
