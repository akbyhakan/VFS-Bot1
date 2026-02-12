"""File-polling based hot-reload selector manager."""

import asyncio
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from src.constants import Resilience
from src.selector.manager import CountryAwareSelectorManager


class HotReloadableSelectorManager(CountryAwareSelectorManager):
    """Selector manager with file-polling based hot-reload capability."""

    def __init__(
        self,
        country_code: str = "default",
        selectors_file: str = "config/selectors.yaml",
        poll_interval: float = Resilience.HOT_RELOAD_INTERVAL,
    ):
        """
        Initialize hot-reloadable selector manager.

        Args:
            country_code: Country code (fra, nld, deu, etc.) or "default"
            selectors_file: Path to selectors YAML file
            poll_interval: File polling interval in seconds (default: 5.0)
        """
        super().__init__(country_code=country_code, selectors_file=selectors_file)

        self.poll_interval = poll_interval
        self._watch_task: Optional[asyncio.Task] = None
        self._is_watching = False
        self._reload_count = 0
        self._last_mtime: Optional[float] = None
        self._last_size: Optional[int] = None

        # Initialize file stats
        self._update_file_stats()

        logger.info(
            f"🔄 Hot-reload selector manager initialized "
            f"(country: {country_code}, poll interval: {poll_interval}s)"
        )

    def _update_file_stats(self) -> None:
        """Update cached file modification time and size."""
        try:
            if self.selectors_file.exists():
                stat = self.selectors_file.stat()
                self._last_mtime = stat.st_mtime
                self._last_size = stat.st_size
            else:
                self._last_mtime = None
                self._last_size = None
        except Exception as e:
            logger.warning(f"Failed to get file stats: {e}")
            self._last_mtime = None
            self._last_size = None

    def _has_file_changed(self) -> bool:
        """
        Check if selectors file has changed.

        Returns:
            True if file has been modified or size changed
        """
        try:
            if not self.selectors_file.exists():
                return False

            stat = self.selectors_file.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size

            # Check if mtime or size changed
            if self._last_mtime is None or self._last_size is None:
                return True

            if current_mtime != self._last_mtime or current_size != self._last_size:
                logger.debug(
                    f"File changed detected: "
                    f"mtime {self._last_mtime} -> {current_mtime}, "
                    f"size {self._last_size} -> {current_size}"
                )
                return True

            return False

        except Exception as e:
            logger.warning(f"Failed to check file changes: {e}")
            return False

    async def _watch_file(self) -> None:
        """Background task to watch for file changes."""
        logger.info(f"🔄 Starting file watcher (polling every {self.poll_interval}s)")

        while self._is_watching:
            try:
                await asyncio.sleep(self.poll_interval)

                if self._has_file_changed():
                    logger.info(f"🔄 Selectors file changed, reloading...")
                    self.reload()
                    self._update_file_stats()
                    self._reload_count += 1
                    logger.info(
                        f"✅ Selectors reloaded successfully "
                        f"(reload count: {self._reload_count})"
                    )

            except asyncio.CancelledError:
                logger.info("🔄 File watcher cancelled")
                break
            except Exception as e:
                logger.error(f"Error in file watcher: {e}")
                # Continue watching even if error occurs
                await asyncio.sleep(self.poll_interval)

        logger.info("🔄 File watcher stopped")

    async def start_watching(self) -> None:
        """Start file watching background task."""
        if self._is_watching:
            logger.warning("File watcher already running")
            return

        self._is_watching = True
        self._watch_task = asyncio.create_task(self._watch_file())
        logger.info("🔄 File watcher started")

    async def stop_watching(self) -> None:
        """Stop file watching background task."""
        if not self._is_watching:
            logger.warning("File watcher not running")
            return

        self._is_watching = False

        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

        logger.info("🔄 File watcher stopped")

    @property
    def is_watching(self) -> bool:
        """Check if file watcher is active."""
        return self._is_watching

    @property
    def reload_count(self) -> int:
        """Get number of times selectors have been reloaded."""
        return self._reload_count

    def get_status(self) -> Dict[str, any]:
        """
        Get hot-reload manager status.

        Returns:
            Status dictionary with metrics
        """
        return {
            "country_code": self.country_code,
            "selectors_file": str(self.selectors_file),
            "is_watching": self._is_watching,
            "poll_interval": self.poll_interval,
            "reload_count": self._reload_count,
            "file_exists": self.selectors_file.exists(),
            "last_mtime": self._last_mtime,
            "last_size": self._last_size,
        }
