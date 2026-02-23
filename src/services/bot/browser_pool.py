"""Browser pool for managing multiple concurrent browser sessions."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from loguru import logger

from .browser_manager import BrowserManager


class BrowserPool:
    """
    Manages a pool of browser instances for concurrent session support.

    Features:
    - Session-based browser isolation
    - Automatic browser lifecycle management
    - Max browser limit with waiting
    - Idle browser cleanup
    - Thread-safe pool operations
    """

    def __init__(
        self,
        config: Dict[str, Any],
        max_browsers: int = 5,
        idle_timeout_minutes: int = 10,
        header_manager: Any = None,
        proxy_manager: Any = None,
    ):
        """
        Initialize browser pool.

        Args:
            config: Bot configuration dictionary
            max_browsers: Maximum number of concurrent browsers (default: 5)
            idle_timeout_minutes: Minutes before idle browser is closed (default: 10)
            header_manager: Optional HeaderManager for custom headers
            proxy_manager: Optional ProxyManager for proxy configuration
        """
        self.config = config
        self.max_browsers = max_browsers
        self.idle_timeout_minutes = idle_timeout_minutes
        self.header_manager = header_manager
        self.proxy_manager = proxy_manager

        # Browser pool storage: session_id -> BrowserManager
        self._browsers: Dict[str, BrowserManager] = {}

        # Semaphore to limit concurrent browsers
        self._semaphore = asyncio.Semaphore(max_browsers)

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"BrowserPool initialized (max: {max_browsers}, idle timeout: {idle_timeout_minutes}m)"
        )

    async def acquire(self, session_id: str) -> BrowserManager:
        """
        Acquire a browser instance for a session.

        If browser doesn't exist, creates a new one.
        If max browsers reached, waits for available slot.

        Args:
            session_id: Unique session identifier

        Returns:
            BrowserManager instance for the session
        """
        async with self._lock:
            # Check if browser already exists for this session
            if session_id in self._browsers:
                browser = self._browsers[session_id]
                logger.debug(f"Reusing existing browser for session {session_id}")
                return browser

        # Wait for available slot
        await self._semaphore.acquire()

        try:
            async with self._lock:
                # Double-check after acquiring semaphore
                if session_id in self._browsers:
                    self._semaphore.release()
                    return self._browsers[session_id]

                # Create new browser
                browser = await self._create_browser(session_id)
                self._browsers[session_id] = browser

                logger.info(
                    f"Browser acquired for session {session_id} "
                    f"(active: {len(self._browsers)}/{self.max_browsers})"
                )

                # Start cleanup task if not running
                if self._cleanup_task is None or self._cleanup_task.done():
                    self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

                return browser

        except Exception as e:
            # Release semaphore on error
            self._semaphore.release()
            logger.error(f"Failed to acquire browser for session {session_id}: {e}")
            raise

    async def release(self, session_id: str, close_browser: bool = False) -> None:
        """
        Release a browser instance.

        Args:
            session_id: Session identifier
            close_browser: Whether to close the browser (default: False, just mark as idle)
        """
        async with self._lock:
            if session_id not in self._browsers:
                logger.warning(f"Attempted to release non-existent session {session_id}")
                return

            browser = self._browsers[session_id]

            if close_browser:
                # Close and remove browser
                try:
                    await browser.close()
                except Exception as e:
                    logger.error(f"Error closing browser for session {session_id}: {e}")

                del self._browsers[session_id]
                self._semaphore.release()

                logger.info(
                    f"Browser released and closed for session {session_id} "
                    f"(active: {len(self._browsers)}/{self.max_browsers})"
                )
            else:
                # Just mark as idle (will be cleaned up later if timeout reached)
                logger.debug(f"Browser marked as idle for session {session_id}")

    async def close_all(self) -> None:
        """Close all browsers in the pool."""
        async with self._lock:
            logger.info(f"Closing all browsers in pool ({len(self._browsers)} browsers)...")

            # Cancel cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

            # Close all browsers
            for session_id, browser in list(self._browsers.items()):
                try:
                    await browser.close()
                except Exception as e:
                    logger.error(f"Error closing browser for session {session_id}: {e}")
                finally:
                    self._semaphore.release()

            self._browsers.clear()
            logger.info("All browsers closed")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics.

        Returns:
            Dictionary with pool stats
        """
        idle_count = sum(1 for browser in self._browsers.values() if browser.is_idle)
        active_count = len(self._browsers) - idle_count

        return {
            "total_browsers": len(self._browsers),
            "active_browsers": active_count,
            "idle_browsers": idle_count,
            "max_browsers": self.max_browsers,
            "available_slots": self.max_browsers - len(self._browsers),
            "sessions": list(self._browsers.keys()),
        }

    async def _create_browser(self, session_id: str) -> BrowserManager:
        """
        Create and start a new BrowserManager instance.

        Args:
            session_id: Session identifier

        Returns:
            Started BrowserManager instance
        """
        browser = BrowserManager(
            config=self.config,
            header_manager=self.header_manager,
            proxy_manager=self.proxy_manager,
        )

        # Set session ID for tracking
        browser.session_id = session_id

        # Start the browser
        await browser.start()

        logger.debug(f"New browser created for session {session_id}")
        return browser

    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of idle browsers."""
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute

                # Collect idle sessions under the lock, then release outside to avoid deadlock
                # (release() also acquires self._lock and asyncio.Lock is not re-entrant)
                sessions_to_close = []
                async with self._lock:
                    idle_threshold = timedelta(minutes=self.idle_timeout_minutes)

                    for session_id, browser in self._browsers.items():
                        if browser.is_idle:
                            # Check if browser has been idle for too long
                            if browser.last_activity:
                                idle_duration = datetime.now(timezone.utc) - browser.last_activity
                                if idle_duration > idle_threshold:
                                    sessions_to_close.append(session_id)

                # Close idle browsers outside the lock to avoid deadlock with release()
                for session_id in sessions_to_close:
                    logger.info(
                        f"Closing idle browser for session {session_id} "
                        f"(idle > {self.idle_timeout_minutes}m)"
                    )
                    await self.release(session_id, close_browser=True)

        except asyncio.CancelledError:
            logger.debug("Periodic cleanup task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")

    async def __aenter__(self) -> "BrowserPool":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close_all()
