"""Service to sync VFS dropdown data from website to database cache."""

import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Browser, Page

from src.core.countries import SUPPORTED_COUNTRIES
from src.models.database import Database
from src.repositories.dropdown_cache_repository import DropdownCacheRepository
from .centre_fetcher import CentreFetcher


class DropdownSyncService:
    """Service to fetch and sync VFS dropdown data."""

    def __init__(
        self,
        database: Database,
        base_url: str = "https://visa.vfsglobal.com",
        source_country: str = "tur",
        language: str = "tr",
    ):
        """
        Initialize dropdown sync service.

        Args:
            database: Database instance
            base_url: VFS base URL
            source_country: Source country code (default: 'tur' for Turkey)
            language: Language code (default: 'tr')
        """
        self.db = database
        self.base_url = base_url
        self.source_country = source_country
        self.language = language
        self.dropdown_cache_repo = DropdownCacheRepository(database)

    async def sync_country_dropdowns(
        self, page: Page, country_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Sync dropdown data for a specific country.

        Args:
            page: Playwright page object (must be on appointment page)
            country_code: Country code (e.g., 'fra', 'nld')

        Returns:
            Dropdown data dictionary or None if failed
        """
        try:
            logger.info(f"Syncing dropdown data for {country_code}...")
            
            # Update status to 'syncing'
            await self.dropdown_cache_repo.update_sync_status(country_code, 'syncing')

            # Initialize CentreFetcher for this country
            fetcher = CentreFetcher(
                base_url=self.base_url,
                country=self.source_country,
                mission=country_code,
                language=self.language,
            )

            # Fetch all data from VFS website
            # The page must already be on the appointment page (SPA constraint)
            dropdown_data = await fetcher.fetch_all_data(page)

            if not dropdown_data:
                logger.warning(f"No dropdown data fetched for {country_code}")
                await self.dropdown_cache_repo.update_sync_status(
                    country_code, 'failed', 'No dropdown data returned from VFS website'
                )
                return None

            # Store in database with 'completed' status
            success = await self.dropdown_cache_repo.upsert_dropdown_data(
                country_code, dropdown_data, 'completed', None
            )

            if success:
                logger.info(
                    f"Successfully synced dropdown data for {country_code}: "
                    f"{len(dropdown_data)} centres"
                )
                return dropdown_data
            else:
                logger.error(f"Failed to store dropdown data for {country_code}")
                await self.dropdown_cache_repo.update_sync_status(
                    country_code, 'failed', 'Failed to store data in database'
                )
                return None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error syncing dropdown data for {country_code}: {error_msg}")
            await self.dropdown_cache_repo.update_sync_status(country_code, 'failed', error_msg)
            return None

    async def sync_all_countries(
        self, browser: Browser, account_email: str, account_password: str
    ) -> Dict[str, bool]:
        """
        Sync dropdown data for all supported countries.

        Note: This is a long-running operation that will:
        1. Login to VFS for each country
        2. Navigate to appointment page
        3. Fetch dropdown data
        4. Store in database

        Args:
            browser: Playwright browser instance
            account_email: VFS account email
            account_password: VFS account password

        Returns:
            Dictionary mapping country codes to sync success status
        """
        results: Dict[str, bool] = {}

        for country_code in SUPPORTED_COUNTRIES.keys():
            try:
                logger.info(f"Starting sync for {country_code}...")

                # Create a new page for this country
                page = await browser.new_page()

                try:
                    # Navigate to VFS login page for this country
                    login_url = (
                        f"{self.base_url}/online-services/login?"
                        f"country={self.source_country}&language={self.language}&mission={country_code}"
                    )
                    await page.goto(login_url)

                    # Wait for login form
                    await page.wait_for_selector('input[name="username"]', timeout=10000)

                    # Fill login form
                    await page.fill('input[name="username"]', account_email)
                    await page.fill('input[name="password"]', account_password)

                    # Click login button
                    await page.click('button[type="submit"]')

                    # Wait for navigation to complete
                    await page.wait_for_load_state("networkidle", timeout=30000)

                    # Navigate to appointment page
                    appointment_url = (
                        f"{self.base_url}/online-services/appointment?"
                        f"country={self.source_country}&language={self.language}&mission={country_code}"
                    )
                    
                    # Use Angular-safe navigation (wait for route change, not page reload)
                    await page.evaluate(
                        f"window.location.hash = '#/appointment?country={self.source_country}&language={self.language}&mission={country_code}'"
                    )
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_selector("select#centres", timeout=10000)

                    # Sync dropdown data for this country
                    dropdown_data = await self.sync_country_dropdowns(page, country_code)
                    results[country_code] = dropdown_data is not None

                    # Add a small delay between countries to avoid rate limiting
                    await asyncio.sleep(2)

                finally:
                    # Always close the page
                    await page.close()

            except Exception as e:
                logger.error(f"Failed to sync {country_code}: {e}")
                results[country_code] = False

        success_count = sum(1 for success in results.values() if success)
        logger.info(
            f"Sync completed: {success_count}/{len(results)} countries synced successfully"
        )

        return results

    async def get_cached_centres(self, country_code: str) -> List[str]:
        """
        Get cached centres for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')

        Returns:
            List of centre names
        """
        return await self.dropdown_cache_repo.get_centres(country_code)

    async def get_cached_categories(
        self, country_code: str, centre_name: str
    ) -> List[str]:
        """
        Get cached categories for a centre.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')
            centre_name: Centre name

        Returns:
            List of category names
        """
        return await self.dropdown_cache_repo.get_categories(country_code, centre_name)

    async def get_cached_subcategories(
        self, country_code: str, centre_name: str, category_name: str
    ) -> List[str]:
        """
        Get cached subcategories for a centre and category.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')
            centre_name: Centre name
            category_name: Category name

        Returns:
            List of subcategory names
        """
        return await self.dropdown_cache_repo.get_subcategories(
            country_code, centre_name, category_name
        )
