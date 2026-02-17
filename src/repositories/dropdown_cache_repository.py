"""Repository for VFS dropdown cache operations."""

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from src.repositories.base import BaseRepository

if TYPE_CHECKING:
    from src.models.database import Database


class DropdownCacheRepository(BaseRepository):
    """Repository for VFS dropdown cache CRUD operations."""

    def __init__(self, database: "Database"):
        """
        Initialize dropdown cache repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    async def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Get dropdown cache entry by ID (not applicable - use get_dropdown_data)."""
        return None

    async def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all cached countries."""
        countries = await self.get_all_cached_countries()
        return [{"country_code": c} for c in countries[:limit]]

    async def create(self, data: Dict[str, Any]) -> int:
        """Create/upsert dropdown data."""
        await self.upsert_dropdown_data(
            country_code=data["country_code"],
            dropdown_data=data.get("dropdown_data", {}),
        )
        return 0

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """Update dropdown data (use upsert_dropdown_data instead)."""
        if "country_code" in data:
            await self.upsert_dropdown_data(
                country_code=data["country_code"],
                dropdown_data=data.get("dropdown_data", {}),
            )
            return True
        return False

    async def delete(self, id: int) -> bool:
        """Delete dropdown data (not applicable by ID)."""
        return False

    async def get_dropdown_data(self, country_code: str) -> Optional[Dict[str, Any]]:
        """
        Get cached dropdown data for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')

        Returns:
            Dropdown data dictionary or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT dropdown_data, last_synced_at, sync_status, error_message
                FROM vfs_dropdown_cache
                WHERE country_code = $1
                """,
                country_code,
            )

            if row is None:
                return None

            return {
                "dropdown_data": row["dropdown_data"],
                "last_synced_at": row["last_synced_at"].isoformat() if row["last_synced_at"] else None,
                "sync_status": row["sync_status"],
                "error_message": row["error_message"],
            }

    async def upsert_dropdown_data(
        self, country_code: str, dropdown_data: Dict[str, Any], sync_status: str = "completed", error_message: Optional[str] = None
    ) -> bool:
        """
        Insert or update dropdown data for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')
            dropdown_data: Dropdown data dictionary
            sync_status: Sync status (default: 'completed')
            error_message: Error message if sync failed (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO vfs_dropdown_cache (country_code, dropdown_data, sync_status, last_synced_at, error_message, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (country_code)
                    DO UPDATE SET
                        dropdown_data = EXCLUDED.dropdown_data,
                        sync_status = EXCLUDED.sync_status,
                        last_synced_at = EXCLUDED.last_synced_at,
                        error_message = EXCLUDED.error_message,
                        updated_at = EXCLUDED.updated_at
                    """,
                    country_code,
                    json.dumps(dropdown_data),
                    sync_status,
                    datetime.now(timezone.utc),
                    error_message,
                    datetime.now(timezone.utc),
                )
            logger.info(f"Upserted dropdown data for country: {country_code} with status: {sync_status}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert dropdown data for {country_code}: {e}")
            return False

    async def get_centres(self, country_code: str) -> List[str]:
        """
        Get list of centres for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')

        Returns:
            List of centre names
        """
        data = await self.get_dropdown_data(country_code)
        if data is None or data.get("dropdown_data") is None:
            return []

        dropdown_data = data["dropdown_data"]
        return list(dropdown_data.keys()) if isinstance(dropdown_data, dict) else []

    async def get_categories(self, country_code: str, centre_name: str) -> List[str]:
        """
        Get list of categories for a centre.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')
            centre_name: Centre name

        Returns:
            List of category names
        """
        data = await self.get_dropdown_data(country_code)
        if data is None or data.get("dropdown_data") is None:
            return []

        dropdown_data = data["dropdown_data"]
        if not isinstance(dropdown_data, dict):
            return []

        centre_data = dropdown_data.get(centre_name, {})
        return list(centre_data.keys()) if isinstance(centre_data, dict) else []

    async def get_subcategories(
        self, country_code: str, centre_name: str, category_name: str
    ) -> List[str]:
        """
        Get list of subcategories for a centre and category.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')
            centre_name: Centre name
            category_name: Category name

        Returns:
            List of subcategory names
        """
        data = await self.get_dropdown_data(country_code)
        if data is None or data.get("dropdown_data") is None:
            return []

        dropdown_data = data["dropdown_data"]
        if not isinstance(dropdown_data, dict):
            return []

        centre_data = dropdown_data.get(centre_name, {})
        if not isinstance(centre_data, dict):
            return []

        subcategories = centre_data.get(category_name, [])
        return subcategories if isinstance(subcategories, list) else []

    async def delete_dropdown_data(self, country_code: str) -> bool:
        """
        Delete cached dropdown data for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    DELETE FROM vfs_dropdown_cache
                    WHERE country_code = $1
                    """,
                    country_code,
                )
            logger.info(f"Deleted dropdown data for country: {country_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete dropdown data for {country_code}: {e}")
            return False

    async def get_all_cached_countries(self) -> List[str]:
        """
        Get list of all countries with cached dropdown data.

        Returns:
            List of country codes
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT country_code
                FROM vfs_dropdown_cache
                ORDER BY country_code
                """
            )

            return [row["country_code"] for row in rows]

    async def get_stale_countries(self, hours: int = 24) -> List[str]:
        """
        Get list of countries with stale dropdown data.

        Args:
            hours: Number of hours to consider data stale (default: 24)

        Returns:
            List of country codes
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT country_code
                FROM vfs_dropdown_cache
                WHERE last_synced_at < NOW() - make_interval(hours => $1)
                ORDER BY last_synced_at ASC
                """,
                hours,
            )

            return [row["country_code"] for row in rows]

    async def get_sync_status(self, country_code: str) -> Optional[Dict[str, Any]]:
        """
        Get sync status for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')

        Returns:
            Dictionary with sync status information or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT sync_status, last_synced_at, error_message
                FROM vfs_dropdown_cache
                WHERE country_code = $1
                """,
                country_code,
            )

            if row is None:
                return None

            return {
                "country_code": country_code,
                "sync_status": row["sync_status"],
                "last_synced_at": row["last_synced_at"].isoformat() if row["last_synced_at"] else None,
                "error_message": row["error_message"],
            }

    async def update_sync_status(
        self, country_code: str, status: str, error_message: Optional[str] = None
    ) -> bool:
        """
        Update sync status for a country.

        Args:
            country_code: Country code (e.g., 'fra', 'nld')
            status: New sync status ('pending', 'syncing', 'completed', 'failed')
            error_message: Error message if status is 'failed' (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO vfs_dropdown_cache (country_code, sync_status, error_message, updated_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (country_code)
                    DO UPDATE SET
                        sync_status = EXCLUDED.sync_status,
                        error_message = EXCLUDED.error_message,
                        updated_at = EXCLUDED.updated_at
                    """,
                    country_code,
                    status,
                    error_message,
                    datetime.now(timezone.utc),
                )
            logger.info(f"Updated sync status for {country_code} to {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update sync status for {country_code}: {e}")
            return False

    async def get_all_sync_statuses(self) -> List[Dict[str, Any]]:
        """
        Get sync statuses for all countries.

        Returns:
            List of dictionaries with sync status information for each country
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT country_code, sync_status, last_synced_at, error_message
                FROM vfs_dropdown_cache
                ORDER BY country_code
                """
            )

            return [
                {
                    "country_code": row["country_code"],
                    "sync_status": row["sync_status"],
                    "last_synced_at": row["last_synced_at"].isoformat() if row["last_synced_at"] else None,
                    "error_message": row["error_message"],
                }
                for row in rows
            ]
