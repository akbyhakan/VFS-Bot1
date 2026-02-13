"""Browser lifecycle and context management for VFS automation."""

from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from ...utils.anti_detection.fingerprint_bypass import FingerprintBypass
from ...utils.anti_detection.fingerprint_rotator import FingerprintRotator
from ...utils.anti_detection.stealth_config import StealthConfig
from ...utils.security.header_manager import HeaderManager
from ...utils.security.proxy_manager import ProxyManager


class BrowserManager:
    """Manages browser lifecycle and context creation with anti-detection features."""

    def __init__(
        self,
        config: Dict[str, Any],
        header_manager: Optional[HeaderManager] = None,
        proxy_manager: Optional[ProxyManager] = None,
    ):
        """
        Initialize browser manager.

        Args:
            config: Bot configuration dictionary
            header_manager: Optional HeaderManager instance for custom headers
            proxy_manager: Optional ProxyManager instance for proxy configuration
        """
        self.config = config
        self.header_manager = header_manager
        self.proxy_manager = proxy_manager
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright: Optional[Playwright] = None
        self._anti_detection_enabled = config.get("anti_detection", {}).get("enabled", True)
        self._page_count: int = 0
        self._max_pages_before_restart: int = config.get("bot", {}).get(
            "browser_restart_after_pages", 100
        )
        
        # Initialize fingerprint rotator
        self._fingerprint_rotator: Optional[FingerprintRotator] = None
        if self._anti_detection_enabled:
            rotation_pages = config.get("anti_detection", {}).get("fingerprint_rotation_pages", 50)
            rotation_minutes = config.get("anti_detection", {}).get("fingerprint_rotation_minutes", 30)
            self._fingerprint_rotator = FingerprintRotator(
                rotation_interval_pages=rotation_pages,
                rotation_interval_minutes=rotation_minutes,
            )
            logger.info(
                f"FingerprintRotator enabled (rotation: {rotation_pages} pages or {rotation_minutes} minutes)"
            )
        
        # Optional session ID for browser pool support
        self.session_id: Optional[str] = None
        self._last_activity = None

    async def start(self) -> None:
        """Launch browser and create context with anti-detection features."""
        if self.browser is not None:
            logger.warning("Browser already started")
            return

        # Start Playwright
        self.playwright = await async_playwright().start()

        # Get proxy configuration if enabled
        proxy_config = None
        if self._anti_detection_enabled and self.proxy_manager and self.proxy_manager.enabled:
            proxy_config = self.proxy_manager.get_playwright_proxy()
            if proxy_config:
                logger.info(f"Using proxy: {proxy_config['server']}")

        # Get User-Agent from fingerprint rotator or header manager or use default
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        )
        
        if self._anti_detection_enabled and self._fingerprint_rotator:
            # Use user agent from current fingerprint profile
            profile = self._fingerprint_rotator.get_current_profile()
            user_agent = profile.user_agent
        elif self._anti_detection_enabled and self.header_manager:
            user_agent = self.header_manager.get_user_agent()

        # Launch browser with anti-automation flags
        launch_options = {
            "headless": self.config["bot"].get("headless", False),
            "args": ["--disable-blink-features=AutomationControlled"],
        }

        self.browser = await self.playwright.chromium.launch(**launch_options)

        # Create context with stealth settings
        context_options: Dict[str, Any] = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": user_agent,
        }
        
        # Use viewport from fingerprint profile if available
        if self._anti_detection_enabled and self._fingerprint_rotator:
            profile = self._fingerprint_rotator.get_current_profile()
            context_options["viewport"] = {
                "width": profile.viewport_width,
                "height": profile.viewport_height,
            }

        if proxy_config:
            context_options["proxy"] = proxy_config

        self.context = await self.browser.new_context(**context_options)

        # Apply stealth configuration if enabled
        if self._anti_detection_enabled and self.config.get("anti_detection", {}).get(
            "stealth_mode", True
        ):
            # Stealth will be applied per-page via StealthConfig
            pass
        else:
            # Add basic stealth script for backwards compatibility
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

        logger.info("Browser started successfully")

    async def close(self) -> None:
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
            self.context = None
            logger.debug("Browser context closed")

        if self.browser:
            await self.browser.close()
            self.browser = None
            logger.debug("Browser closed")

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        logger.info("Browser resources cleaned up")

    async def new_page(
        self, apply_stealth: bool = True, apply_fingerprint_bypass: bool = True
    ) -> Page:
        """
        Create a new page with optional anti-detection features.

        Args:
            apply_stealth: Whether to apply stealth configuration
            apply_fingerprint_bypass: Whether to apply fingerprint bypass

        Returns:
            New Page instance

        Raises:
            RuntimeError: If browser context is not initialized
        """
        if self.context is None:
            raise RuntimeError("Browser context is not initialized. Call start() first.")

        # Check if fingerprint should be rotated
        if self._anti_detection_enabled and self._fingerprint_rotator:
            if self._fingerprint_rotator.should_rotate(increment_page_count=True):
                logger.info("Rotating fingerprint profile...")
                profile = self._fingerprint_rotator.rotate()
                
                # Restart browser with new profile
                logger.info("Restarting browser with new fingerprint profile...")
                await self.close()
                await self.start()

        page = await self.context.new_page()
        
        # Track activity
        from datetime import datetime, timezone
        self._last_activity = datetime.now(timezone.utc)

        # Apply anti-detection features if enabled
        if self._anti_detection_enabled:
            anti_config = self.config.get("anti_detection", {})

            if apply_stealth and anti_config.get("stealth_mode", True):
                stealth_languages = anti_config.get("stealth_languages", None)
                await StealthConfig.apply_stealth(page, languages=stealth_languages)

            if apply_fingerprint_bypass and anti_config.get("fingerprint_bypass", True):
                # Pass current profile to fingerprint bypass if rotator is enabled
                profile = self._fingerprint_rotator.get_current_profile() if self._fingerprint_rotator else None
                await FingerprintBypass.apply_all(page, profile=profile)

        return page

    async def clear_session_data(self) -> None:
        """Clear all cookies, local storage, and session storage."""
        if not self.context:
            return

        try:
            # Clear cookies
            await self.context.clear_cookies()
            logger.debug("Cleared cookies")

            # Clear storage for all pages
            for page in self.context.pages:
                try:
                    await page.evaluate("""
                        () => {
                            localStorage.clear();
                            sessionStorage.clear();
                        }
                    """)
                except Exception:
                    pass

            logger.info("Session data cleared")

        except Exception as e:
            logger.warning(f"Failed to clear session data: {e}")

    async def restart_with_new_proxy(self, proxy_config: Optional[Dict[str, Any]] = None) -> None:
        """Restart browser with a new proxy configuration."""
        # Close existing browser
        await self.close()

        # Update proxy config
        if proxy_config:
            self.config["proxy"] = proxy_config
            if self.proxy_manager:
                # Update proxy manager with specific proxy
                pass

        # Start fresh
        await self.start()
        logger.info("Browser restarted with new proxy")

    async def should_restart(self) -> bool:
        """
        Check if browser should be restarted for memory management.

        Note: This method increments the page count as part of the check.
        Call this once per page creation to track usage and determine restart needs.

        Returns:
            True if browser should be restarted, False otherwise
        """
        self._page_count += 1
        if self._page_count >= self._max_pages_before_restart:
            logger.info(
                f"Browser restart threshold reached ({self._page_count} pages created). "
                "Restarting to prevent memory leaks."
            )
            return True
        return False

    async def restart_fresh(self) -> None:
        """Restart browser with clean state for memory management."""
        logger.info("Restarting browser for memory management...")
        await self.close()
        
        # Rotate fingerprint on restart if rotator is enabled
        if self._anti_detection_enabled and self._fingerprint_rotator:
            logger.info("Rotating to new fingerprint profile on restart...")
            self._fingerprint_rotator.rotate()
        
        await self.start()
        self._page_count = 0
        logger.info("Browser restarted successfully for memory management")
    
    @property
    def is_idle(self) -> bool:
        """
        Check if browser has been idle (for browser pool management).

        Returns:
            True if browser hasn't been used recently, False otherwise
        """
        if self._last_activity is None:
            return False
        
        from datetime import datetime, timedelta, timezone
        idle_threshold = timedelta(minutes=10)
        return datetime.now(timezone.utc) - self._last_activity > idle_threshold
    
    @property
    def last_activity(self) -> Optional[Any]:
        """
        Get the timestamp of last activity.

        Returns:
            Datetime of last activity or None if never active
        """
        return self._last_activity

    async def __aenter__(self) -> "BrowserManager":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
