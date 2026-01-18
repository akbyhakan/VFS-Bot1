"""Background service for cleaning up old appointment requests."""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

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
        self._consecutive_errors = 0

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

    async def _send_critical_alert(self, message: str) -> None:
        """
        Send critical alert to administrators.

        Args:
            message: Alert message
        """
        # TODO: Implement actual alert mechanism (email, Telegram, etc.)
        logger.critical(f"🚨 CRITICAL ALERT: {message}")

    async def run_periodic_cleanup(
        self, interval_hours: int = 24, max_retries: int = 5
    ) -> None:
        """
        Run periodic cleanup with exponential backoff on errors.

        Args:
            interval_hours: Interval between cleanups in hours (default 24)
            max_retries: Maximum consecutive errors before stopping (default 5)
        """
        self._running = True
        self._consecutive_errors = 0
        
        logger.info(
            f"Starting periodic cleanup service "
            f"(interval: {interval_hours}h, age: {self.cleanup_days} days, "
            f"max_retries: {max_retries})"
        )

        while self._running:
            try:
                deleted = await self.cleanup_old_requests()
                logger.info(f"✅ Cleanup completed - deleted {deleted} old requests")
                self._consecutive_errors = 0  # Reset on success
                
            except Exception as e:
                self._consecutive_errors += 1
                logger.error(
                    f"❌ Cleanup error (attempt {self._consecutive_errors}/{max_retries}): {e}",
                    exc_info=True
                )
                
                if self._consecutive_errors >= max_retries:
                    logger.critical(
                        f"🚨 Max cleanup retries ({max_retries}) reached - stopping service"
                    )
                    self._running = False
                    # Alert admin
                    await self._send_critical_alert(
                        f"Cleanup service stopped due to {max_retries} consecutive failures"
                    )
                    break
                
                # Exponential backoff: 5min, 10min, 20min, 40min, 80min (max 1.5h)
                backoff_seconds = min(300 * (2 ** (self._consecutive_errors - 1)), 5400)
                logger.warning(
                    f"⏳ Waiting {backoff_seconds}s ({backoff_seconds // 60} minutes) "
                    f"before retry..."
                )
                await asyncio.sleep(backoff_seconds)
                continue
            
            # Normal interval sleep
            await asyncio.sleep(interval_hours * 3600)

    def stop(self) -> None:
        """Stop the periodic cleanup service."""
        self._running = False
        logger.info("Cleanup service stopped")

    def get_status(self) -> dict:
        """
        Get current status of cleanup service.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self._running,
            "consecutive_errors": self._consecutive_errors,
            "cleanup_days": self.cleanup_days,
        }
