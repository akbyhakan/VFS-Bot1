"""Background service for cleaning up old appointment requests and screenshots."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.database import Database

logger = logging.getLogger(__name__)

# Exponential backoff constants
BASE_BACKOFF_SECONDS = 300  # 5 minutes
MAX_BACKOFF_SECONDS = 5400  # 90 minutes (1.5 hours)


class CleanupService:
    """Service for cleaning up old completed appointment requests and screenshots."""

    def __init__(
        self,
        db: "Database",
        cleanup_days: int = 30,
        screenshot_cleanup_days: int = 7,
        screenshot_dir: str = "screenshots",
    ):
        """
        Initialize cleanup service.

        Args:
            db: Database instance
            cleanup_days: Age threshold in days for appointment cleanup (default 30)
            screenshot_cleanup_days: Age threshold in days for screenshot cleanup (default 7)
            screenshot_dir: Directory containing screenshots (default "screenshots")
        """
        self.db = db
        self.cleanup_days = cleanup_days
        self.screenshot_cleanup_days = screenshot_cleanup_days
        self.screenshot_dir = Path(screenshot_dir)
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

    async def cleanup_old_screenshots(self) -> int:
        """
        Delete screenshots older than specified days.

        Returns:
            Number of screenshots deleted
        """
        try:
            if not self.screenshot_dir.exists():
                logger.info(
                    f"Screenshot directory {self.screenshot_dir} does not exist, skipping cleanup"
                )
                return 0

            deleted_count = await asyncio.to_thread(self._cleanup_screenshots_sync)

            if deleted_count > 0:
                logger.info(
                    f"✅ Deleted {deleted_count} old screenshots "
                    f"(older than {self.screenshot_cleanup_days} days)"
                )

            return deleted_count

        except Exception as e:
            logger.error(f"Error during screenshot cleanup: {e}", exc_info=True)
            return 0

    def _cleanup_screenshots_sync(self) -> int:
        """Synchronous screenshot cleanup logic."""
        deleted_count = 0
        cutoff_time = datetime.now(timezone.utc).timestamp() - (
            self.screenshot_cleanup_days * 24 * 3600
        )

        # Iterate through all files in screenshot directory
        for screenshot_file in self.screenshot_dir.glob("*.png"):
            try:
                # Check file modification time
                file_mtime = screenshot_file.stat().st_mtime

                if file_mtime < cutoff_time:
                    screenshot_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old screenshot: {screenshot_file.name}")

            except Exception as e:
                logger.warning(f"Failed to delete screenshot {screenshot_file.name}: {e}")
                continue

        return deleted_count

    async def _send_critical_alert(self, message: str) -> None:
        """
        Send critical alert to administrators.

        Args:
            message: Alert message
        """
        try:
            from src.services.alert_service import send_critical_alert

            await send_critical_alert(message, metadata={"service": "cleanup"})
        except Exception as e:
            # Fallback to logging if alert service fails
            logger.critical(f"🚨 CRITICAL ALERT: {message}")
            logger.error(f"Alert service failed: {e}")

    async def run_periodic_cleanup(self, interval_hours: int = 24, max_retries: int = 5) -> None:
        """
        Run periodic cleanup with exponential backoff on errors.
        Cleans both appointment requests and screenshots.

        Args:
            interval_hours: Interval between cleanups in hours (default 24)
            max_retries: Maximum consecutive errors before stopping (default 5)
        """
        self._running = True
        self._consecutive_errors = 0

        logger.info(
            f"Starting periodic cleanup service "
            f"(interval: {interval_hours}h, "
            f"appointment age: {self.cleanup_days} days, "
            f"screenshot age: {self.screenshot_cleanup_days} days, "
            f"max_retries: {max_retries})"
        )

        while self._running:
            try:
                # Clean up old appointment requests
                deleted_requests = await self.cleanup_old_requests()
                logger.info(
                    f"✅ Cleanup completed - deleted {deleted_requests} old appointment requests"
                )

                # Clean up old screenshots
                deleted_screenshots = await self.cleanup_old_screenshots()
                logger.info(f"✅ Cleanup completed - deleted {deleted_screenshots} old screenshots")

                self._consecutive_errors = 0  # Reset on success

            except Exception as e:
                self._consecutive_errors += 1
                logger.error(
                    f"❌ Cleanup error (attempt {self._consecutive_errors}/{max_retries}): {e}",
                    exc_info=True,
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
                backoff_seconds = min(
                    BASE_BACKOFF_SECONDS * (2 ** (self._consecutive_errors - 1)),
                    MAX_BACKOFF_SECONDS,
                )
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
            "screenshot_cleanup_days": self.screenshot_cleanup_days,
            "screenshot_dir": str(self.screenshot_dir),
        }
