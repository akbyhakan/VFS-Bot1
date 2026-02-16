"""Dropdown sync scheduler for periodic updates."""

import asyncio
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.constants.countries import SUPPORTED_COUNTRIES
from src.models.database import Database
from src.repositories.dropdown_cache_repository import DropdownCacheRepository


class DropdownSyncScheduler:
    """Scheduler for periodic dropdown data synchronization."""

    def __init__(self, database: Database):
        """
        Initialize dropdown sync scheduler.

        Args:
            database: Database instance
        """
        self.db = database
        self.dropdown_cache_repo = DropdownCacheRepository(database)
        self.scheduler: Optional[AsyncIOScheduler] = None

    def start(self):
        """
        Start the scheduler.

        Schedules dropdown sync for all countries every Saturday at 03:00 Turkey time (UTC+3).
        This translates to 00:00 UTC on Saturday.
        """
        if self.scheduler is not None:
            logger.warning("Dropdown sync scheduler already running")
            return

        self.scheduler = AsyncIOScheduler(timezone="UTC")

        # Schedule for every Saturday at 00:00 UTC (03:00 Turkey time)
        trigger = CronTrigger(
            day_of_week="sat",  # Saturday
            hour=0,  # 00:00 UTC = 03:00 Turkey (UTC+3)
            minute=0,
        )

        self.scheduler.add_job(
            self._sync_all_countries,
            trigger=trigger,
            id="dropdown_sync_weekly",
            name="Weekly VFS Dropdown Sync",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            "Dropdown sync scheduler started - will run every Saturday at 00:00 UTC (03:00 Turkey)"
        )

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            logger.info("Dropdown sync scheduler stopped")

    async def _sync_all_countries(self):
        """
        Internal method to sync all countries.

        This is called by the scheduler. It marks all countries as 'pending'
        so they can be picked up by a background worker.
        
        Note: Actual sync implementation (login, browser automation) would be
        handled by a separate background worker process to avoid blocking.
        """
        try:
            logger.info("Starting scheduled dropdown sync for all countries...")

            # Mark all countries as pending for sync
            pending_count = 0
            for country_code in SUPPORTED_COUNTRIES.keys():
                # Check current status
                status = await self.dropdown_cache_repo.get_sync_status(country_code)
                
                # Skip if already syncing
                if status and status["sync_status"] == "syncing":
                    logger.info(f"Skipping {country_code} - already syncing")
                    continue

                # Mark as pending
                await self.dropdown_cache_repo.update_sync_status(country_code, "pending")
                pending_count += 1

            logger.info(
                f"Scheduled dropdown sync completed - marked {pending_count} countries as pending"
            )

        except Exception as e:
            logger.error(f"Error in scheduled dropdown sync: {e}", exc_info=True)

    async def trigger_manual_sync(self, country_code: Optional[str] = None):
        """
        Manually trigger sync for one or all countries.

        Args:
            country_code: Country code to sync, or None for all countries
        """
        try:
            if country_code:
                # Sync single country
                status = await self.dropdown_cache_repo.get_sync_status(country_code)
                if status and status["sync_status"] == "syncing":
                    logger.info(f"Skipping {country_code} - already syncing")
                    return

                await self.dropdown_cache_repo.update_sync_status(country_code, "pending")
                logger.info(f"Manually triggered sync for {country_code}")
            else:
                # Sync all countries
                await self._sync_all_countries()

        except Exception as e:
            logger.error(f"Error triggering manual sync: {e}", exc_info=True)
