"""Background service for cleaning up old appointment requests."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.database import Database

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for cleaning up old completed appointment requests."""

    def __init__(self, db: "Database", cleanup_days: int = 30):
        """
        Initialize cleanup service.

        Args:
            db: Database instance
            cleanup_days: Age threshold in days for cleanup (default 30)
        """
        self.db = db
        self.cleanup_days = cleanup_days
        self._running = False

    async def cleanup_old_requests(self) -> int:
        """
        Delete completed requests older than specified days.

        Returns:
            Number of requests deleted
        """
        try:
            deleted_count = await self.db.cleanup_completed_requests(self.cleanup_days)
            return deleted_count
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            return 0

    async def run_periodic_cleanup(self, interval_hours: int = 24) -> None:
        """
        Run periodic cleanup task.

        Args:
            interval_hours: Interval between cleanups in hours (default 24)
        """
        self._running = True
        logger.info(
            f"Starting periodic cleanup service (interval: {interval_hours}h, age: {self.cleanup_days} days)"
        )

        while self._running:
            try:
                await self.cleanup_old_requests()
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)

            # Sleep for the specified interval
            await asyncio.sleep(interval_hours * 3600)

    def stop(self) -> None:
        """Stop the periodic cleanup service."""
        self._running = False
        logger.info("Cleanup service stopped")
