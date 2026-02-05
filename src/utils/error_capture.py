"""Error capture with screenshots and context."""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class ErrorCapture:
    """Capture comprehensive error context."""

    def __init__(self, screenshots_dir: str = "screenshots/errors", cleanup_days: int = 7):
        """
        Initialize error capture.

        Args:
            screenshots_dir: Directory for error screenshots
            cleanup_days: Days to keep error files before cleanup
        """
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.errors: List[Dict[str, Any]] = []
        self.max_errors = 100  # Keep last 100 errors
        self.cleanup_days = cleanup_days
        self._last_cleanup = time.time()

    async def capture(
        self,
        page: Page,
        error: Exception,
        context: Dict[str, Any],
        element_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Capture error with full context.

        Args:
            page: Playwright page object
            error: Exception that occurred
            context: Additional context (step, action, etc.)
            element_selector: Optional selector of failed element

        Returns:
            Error record with all captured data
        """
        timestamp = datetime.now(timezone.utc)
        error_id = timestamp.strftime("%Y%m%d_%H%M%S_%f")

        captures: Dict[str, str] = {}
        error_record: Dict[str, Any] = {
            "id": error_id,
            "timestamp": timestamp.isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "captures": captures,
        }

        try:
            # 1. Full page screenshot
            screenshot_path = self.screenshots_dir / f"{error_id}_full.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            captures["full_screenshot"] = str(screenshot_path)
            logger.info(f"Captured full screenshot: {screenshot_path}")

            # 2. Element screenshot (if selector provided)
            if element_selector:
                try:
                    element = await page.query_selector(element_selector)
                    if element:
                        element_path = self.screenshots_dir / f"{error_id}_element.png"
                        await element.screenshot(path=str(element_path))
                        captures["element_screenshot"] = str(element_path)
                        error_record["failed_selector"] = element_selector
                except Exception as e:
                    logger.warning(f"Could not capture element screenshot: {e}")

            # 3. HTML snapshot
            html_path = self.screenshots_dir / f"{error_id}.html"
            try:
                html_content = await page.content()
                html_path.write_text(html_content, encoding="utf-8", errors="replace")
                captures["html_snapshot"] = str(html_path)
            except Exception as e:
                logger.warning(f"Could not capture HTML snapshot: {e}")

            # 4. Console logs
            # Note: Console logs should be collected during page lifecycle
            # This is just a placeholder - implement console log collection in bot
            error_record["console_logs"] = context.get("console_logs", [])

            # 5. Network activity
            error_record["network_requests"] = context.get("network_requests", [])

            # 6. Page URL and title
            error_record["url"] = page.url
            error_record["title"] = await page.title()

            # 7. Viewport info
            viewport = page.viewport_size
            error_record["viewport"] = viewport

            # Save error record to JSON
            json_path = self.screenshots_dir / f"{error_id}.json"
            json_path.write_text(json.dumps(error_record, indent=2, default=str), encoding="utf-8")

            # Add to in-memory list (for dashboard)
            self.errors.append(error_record)
            if len(self.errors) > self.max_errors:
                self.errors.pop(0)

            logger.info(f"Error captured successfully: {error_id}")

        except Exception as e:
            logger.error(f"Failed to capture error context: {e}")
            error_record["capture_error"] = str(e)

        # Periodic cleanup (outside try-except to not block error return)
        try:
            await self._cleanup_old_errors()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        return error_record

    async def _cleanup_old_errors(self) -> None:
        """Clean up error files older than cleanup_days."""
        from ..constants import ErrorCapture as ErrorCaptureConstants

        current_time = time.time()

        # Only cleanup once per interval (default: 1 hour)
        cleanup_interval = ErrorCaptureConstants.CLEANUP_INTERVAL_SECONDS
        if current_time - self._last_cleanup < cleanup_interval:
            return

        self._last_cleanup = current_time
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.cleanup_days)

        deleted_count = 0
        for file_path in self.screenshots_dir.glob("*"):
            if file_path.is_file():
                # Check file modification time
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if file_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old error files (>{self.cleanup_days} days)")

    def get_recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent errors for dashboard."""
        return sorted(self.errors, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_error_by_id(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get specific error details."""
        for error in self.errors:
            if error["id"] == error_id:
                return error

        # Try loading from disk
        json_path = self.screenshots_dir / f"{error_id}.json"
        if json_path.exists():
            loaded_data: Any = json.loads(json_path.read_text(encoding="utf-8"))
            return loaded_data if isinstance(loaded_data, dict) else None

        return None
