"""Central orchestrator for all resilience features."""

from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Locator, Page

from src.constants import Resilience
from src.core.exceptions import SelectorNotFoundError
from src.resilience.ai_repair_v2 import AIRepairV2
from src.resilience.forensic_logger import ForensicLogger
from src.resilience.hot_reload import HotReloadableSelectorManager
from src.resilience.smart_wait import SmartWait


class ResilienceManager:
    """Central orchestrator for unified resilience system."""

    def __init__(
        self,
        selectors_file: str = "config/selectors.yaml",
        country_code: str = "default",
        logs_dir: str = "logs/errors",
        enable_ai_repair: bool = True,
        enable_hot_reload: bool = True,
        hot_reload_interval: float = Resilience.HOT_RELOAD_INTERVAL,
    ):
        """
        Initialize resilience manager.

        Args:
            selectors_file: Path to selectors YAML file
            country_code: Country code for country-aware operations
            logs_dir: Base directory for forensic logs
            enable_ai_repair: Enable AI-powered selector repair
            enable_hot_reload: Enable hot-reload for selectors
            hot_reload_interval: Hot-reload polling interval in seconds
        """
        self.selectors_file = selectors_file
        self.country_code = country_code.lower()
        self.logs_dir = logs_dir
        self.enable_ai_repair = enable_ai_repair
        self.enable_hot_reload = enable_hot_reload
        self.hot_reload_interval = hot_reload_interval

        # Initialize components
        logger.info(
            f"🛡️ Initializing ResilienceManager for country: {country_code} "
            f"(AI repair: {enable_ai_repair}, hot-reload: {enable_hot_reload})"
        )

        # 1. Hot-reloadable selector manager (country-aware)
        self.selector_manager = HotReloadableSelectorManager(
            country_code=country_code,
            selectors_file=selectors_file,
            poll_interval=hot_reload_interval,
        )

        # 2. AI repair (if enabled)
        self.ai_repair: Optional[AIRepairV2] = None
        if enable_ai_repair:
            self.ai_repair = AIRepairV2(selectors_file=selectors_file)

        # 3. Forensic logger (country-aware)
        self.forensic_logger = ForensicLogger(
            base_dir=logs_dir,
            country_code=country_code,
        )

        # 4. Smart wait pipeline
        self.smart_wait = SmartWait(
            selector_manager=self.selector_manager,
            ai_repair=self.ai_repair,
        )

        logger.info("✅ ResilienceManager initialized successfully")

    async def start(self) -> None:
        """Start resilience manager (lifecycle method)."""
        logger.info("🚀 Starting ResilienceManager...")

        # Start hot-reload watcher if enabled
        if self.enable_hot_reload:
            await self.selector_manager.start_watching()
            logger.info("🔄 Hot-reload watcher started")

        logger.info("✅ ResilienceManager started")

    async def stop(self) -> None:
        """Stop resilience manager (lifecycle method)."""
        logger.info("🛑 Stopping ResilienceManager...")

        # Stop hot-reload watcher if running
        if self.enable_hot_reload and self.selector_manager.is_watching:
            await self.selector_manager.stop_watching()
            logger.info("🔄 Hot-reload watcher stopped")

        logger.info("✅ ResilienceManager stopped")

    async def find_element(
        self,
        page: Page,
        selector_path: str,
        timeout: int = 10000,
        action_context: Optional[str] = None,
    ) -> Locator:
        """
        Find element using full resilience pipeline.

        This is the main entry point for element discovery with full resilience:
        - 3-stage pipeline (semantic → CSS → AI)
        - Forensic logging on failure
        - Learning-based optimization

        Args:
            page: Playwright page object
            selector_path: Dot-separated selector path (e.g., "login.email_input")
            timeout: Timeout in milliseconds (default: 10000)
            action_context: Optional context for error reporting

        Returns:
            Element locator

        Raises:
            SelectorNotFoundError: If element cannot be found after all stages
        """
        try:
            locator = await self.smart_wait.find_element(
                page, selector_path, timeout, action_context
            )
            return locator

        except SelectorNotFoundError as e:
            # Capture forensic incident
            context = {
                "selector_path": selector_path,
                "action_context": action_context,
                "timeout": timeout,
            }

            await self.forensic_logger.capture_incident(
                page=page,
                error=e,
                context=context,
                tried_selectors=e.tried_selectors,
            )

            # Re-raise the exception
            raise

    async def safe_click(
        self,
        page: Page,
        selector_path: str,
        timeout: int = 10000,
        action_context: Optional[str] = None,
    ) -> None:
        """
        Safely click an element with full resilience.

        Args:
            page: Playwright page object
            selector_path: Selector path
            timeout: Timeout in milliseconds
            action_context: Optional context for error reporting
        """
        locator = await self.find_element(page, selector_path, timeout, action_context)
        await locator.click()
        logger.debug(f"✅ Clicked: {selector_path}")

    async def safe_fill(
        self,
        page: Page,
        selector_path: str,
        value: str,
        timeout: int = 10000,
        action_context: Optional[str] = None,
    ) -> None:
        """
        Safely fill an input field with full resilience.

        Args:
            page: Playwright page object
            selector_path: Selector path
            value: Value to fill
            timeout: Timeout in milliseconds
            action_context: Optional context for error reporting
        """
        locator = await self.find_element(page, selector_path, timeout, action_context)
        await locator.fill(value)
        logger.debug(f"✅ Filled: {selector_path}")

    async def safe_select(
        self,
        page: Page,
        selector_path: str,
        value: str,
        timeout: int = 10000,
        action_context: Optional[str] = None,
    ) -> None:
        """
        Safely select an option with full resilience.

        Args:
            page: Playwright page object
            selector_path: Selector path
            value: Value to select
            timeout: Timeout in milliseconds
            action_context: Optional context for error reporting
        """
        locator = await self.find_element(page, selector_path, timeout, action_context)
        await locator.select_option(value)
        logger.debug(f"✅ Selected: {selector_path} = {value}")

    def reload_selectors(self) -> None:
        """Manually trigger selector reload."""
        logger.info("🔄 Manually reloading selectors...")
        self.selector_manager.reload()
        logger.info("✅ Selectors reloaded")

    def get_status(self) -> Dict[str, Any]:
        """
        Get resilience manager status.

        Returns:
            Status dictionary with all component metrics
        """
        return {
            "country_code": self.country_code,
            "enable_ai_repair": self.enable_ai_repair,
            "enable_hot_reload": self.enable_hot_reload,
            "selector_manager": self.selector_manager.get_status(),
            "forensic_logger": self.forensic_logger.get_status(),
            "ai_repair_enabled": self.ai_repair.enabled if self.ai_repair else False,
        }
