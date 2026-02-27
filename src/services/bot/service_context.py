"""
Service context and factory for VFSBot dependency management.

This module implements the Context Object Pattern to group and manage VFSBot dependencies,
reducing complexity and improving testability by organizing related services into contexts.
"""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from loguru import logger

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict

from src.core.rate_limiting import get_rate_limiter
from src.selector import SelectorSelfHealing

from ...constants import RateLimits
from ...utils.anti_detection.cloudflare_handler import CloudflareHandler
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.error_capture import ErrorCapture
from ...utils.security.header_manager import HeaderManager
from ...utils.security.proxy_manager import ProxyManager
from ...utils.security.session_manager import SessionManager
from ..account.token_sync_service import TokenSyncService
from ..booking import BookingOrchestrator
from ..captcha_solver import CaptchaSolver
from ..data_sync.centre_fetcher import CentreFetcher
from ..data_sync.country_profile_loader import CountryProfileLoader
from ..notification.alert_service import AlertChannel, AlertConfig, AlertService
from ..otp_manager.otp_webhook import get_otp_service
from ..scheduling.adaptive_scheduler import AdaptiveScheduler
from ..session.session_recovery import SessionRecovery
from ..slot_analyzer import SlotPatternAnalyzer
from .auth_service import AuthService
from .error_handler import ErrorHandler
from .page_state_detector import PageStateDetector
from .slot_checker import SlotChecker
from .waitlist_handler import WaitlistHandler


@dataclass(frozen=True)
class AntiDetectionContext:
    """
    Anti-detection services context.

    Groups all anti-detection related services including human simulation,
    header management, session management, cloudflare handling, and proxy management.

    Attributes:
        enabled: Whether anti-detection features are enabled
        human_sim: Human behavior simulator for realistic interactions
        header_manager: HTTP header randomization and management
        session_manager: Session token and cookie management
        token_sync: Token synchronization between VFSApiClient and SessionManager
        cloudflare_handler: Cloudflare challenge bypass handler
        proxy_manager: Proxy rotation and management
    """

    enabled: bool
    human_sim: Optional[HumanSimulator]
    header_manager: Optional[HeaderManager]
    session_manager: Optional[SessionManager]
    token_sync: Optional[TokenSyncService]
    cloudflare_handler: Optional[CloudflareHandler]
    proxy_manager: Optional[ProxyManager]


@dataclass(frozen=True)
class CoreServicesContext:
    """
    Core bot services context.

    Groups fundamental services needed for bot operation including captcha solving,
    centre fetching, OTP handling, rate limiting, and error capture.

    Attributes:
        captcha_solver: CAPTCHA solving service
        centre_fetcher: VFS centre information fetcher
        otp_service: One-time password service for 2FA
        rate_limiter: API rate limiting service
        error_capture: Error capture and screenshot service
        user_semaphore: Concurrency control for user processing
    """

    captcha_solver: CaptchaSolver
    centre_fetcher: CentreFetcher
    otp_service: Any  # OTPService type (dynamic import)
    rate_limiter: Any  # RateLimiter type
    error_capture: ErrorCapture
    user_semaphore: asyncio.Semaphore


@dataclass
class WorkflowServicesContext:
    """
    Workflow services context.

    Groups high-level workflow orchestration services including authentication,
    slot checking, booking, waitlist handling, error handling, payment, and alerts.

    Attributes:
        auth_service: Authentication and login service
        slot_checker: Slot availability checker
        booking_service: Appointment booking service
        waitlist_handler: Waitlist management service
        error_handler: Error handling and checkpoint service
        page_state_detector: Page state detection service
        payment_service: Payment processing service (optional)
        alert_service: Alert and notification service (optional)
    """

    auth_service: AuthService
    slot_checker: SlotChecker
    booking_service: BookingOrchestrator
    waitlist_handler: WaitlistHandler
    error_handler: ErrorHandler
    page_state_detector: PageStateDetector
    payment_service: Optional[Any] = None  # PaymentService type (optional import)
    alert_service: Optional[AlertService] = None


@dataclass
class AutomationServicesContext:
    """
    Automation services context.

    Groups intelligent automation services including scheduling, slot analysis,
    self-healing, session recovery, and country-specific profiles.

    Attributes:
        scheduler: Adaptive scheduling based on time and patterns
        slot_analyzer: Slot pattern analysis and prediction
        self_healing: Selector self-healing for DOM changes
        session_recovery: Session state recovery
        country_profiles: Country-specific configuration profiles
    """

    scheduler: AdaptiveScheduler
    slot_analyzer: SlotPatternAnalyzer
    self_healing: SelectorSelfHealing
    session_recovery: SessionRecovery
    country_profiles: CountryProfileLoader


@dataclass
class BotServiceContext:
    """
    Top-level bot service context container.

    Aggregates all service contexts (anti-detection, core, workflow, automation)
    into a single unified container for dependency injection.

    Attributes:
        anti_detection: Anti-detection services context
        core: Core services context
        workflow: Workflow services context
        automation: Automation services context
    """

    anti_detection: AntiDetectionContext
    core: CoreServicesContext
    workflow: WorkflowServicesContext
    automation: AutomationServicesContext


class BotServiceFactory:
    """
    Factory for creating bot service contexts from configuration.

    Centralizes service instantiation logic that was previously scattered across
    VFSBot._init_* methods, making it easier to test and maintain.
    """

    @staticmethod
    def create_anti_detection(config: "BotConfigDict") -> AntiDetectionContext:
        """
        Create anti-detection context from configuration.

        Args:
            config: Bot configuration dictionary

        Returns:
            AntiDetectionContext with initialized services or None placeholders
        """
        # Cast to Dict[str, Any] for flexible key access
        config_dict = cast(Dict[str, Any], config)
        anti_detection_config = config_dict.get("anti_detection", {})
        enabled = anti_detection_config.get("enabled", True)

        if enabled:
            human_sim = HumanSimulator(config_dict.get("human_behavior", {}))
            header_manager = HeaderManager()

            session_config = config_dict.get("session", {})
            session_manager = SessionManager(
                session_file=session_config.get("save_file", "data/session.json"),
                token_refresh_buffer=session_config.get("token_refresh_buffer", 5),
            )

            # Initialize TokenSyncService with SessionManager
            token_sync = TokenSyncService(
                session_manager=session_manager,
                token_refresh_buffer_minutes=session_config.get("token_refresh_buffer", 5),
            )

            cloudflare_handler = CloudflareHandler(config_dict.get("cloudflare", {}))
            proxy_manager = ProxyManager(config_dict.get("proxy", {}))

            logger.info("Anti-detection features initialized")
        else:
            human_sim = None
            header_manager = None
            session_manager = None
            token_sync = None
            cloudflare_handler = None
            proxy_manager = None
            logger.info("Anti-detection features disabled")

        return AntiDetectionContext(
            enabled=enabled,
            human_sim=human_sim,
            header_manager=header_manager,
            session_manager=session_manager,
            token_sync=token_sync,
            cloudflare_handler=cloudflare_handler,
            proxy_manager=proxy_manager,
        )

    @staticmethod
    def create_core_services(
        config: "BotConfigDict",
        captcha_solver: Optional[CaptchaSolver] = None,
        centre_fetcher: Optional[CentreFetcher] = None,
    ) -> CoreServicesContext:
        """
        Create core services context from configuration.

        Args:
            config: Bot configuration dictionary
            captcha_solver: Optional pre-created CaptchaSolver (for dependency injection)
            centre_fetcher: Optional pre-created CentreFetcher (for dependency injection)

        Returns:
            CoreServicesContext with all core services

        Raises:
            ValueError: If required VFS configuration fields are missing
        """
        # Cast to Dict[str, Any] for flexible key access
        config_dict = cast(Dict[str, Any], config)
        user_semaphore = asyncio.Semaphore(RateLimits.CONCURRENT_USERS)
        rate_limiter = get_rate_limiter()
        error_capture = ErrorCapture()
        otp_service = get_otp_service()

        # Create or use provided captcha solver
        captcha_config = config_dict.get("captcha", {})
        if captcha_solver is None:
            api_key = captcha_config.get("api_key", "")
            # CaptchaSolver handles empty keys in test mode internally
            captcha_solver = CaptchaSolver(api_key=api_key or "")

        # Create or use provided centre fetcher
        vfs_config = config_dict.get("vfs", {})
        if centre_fetcher is None:
            # Validate required VFS configuration fields
            required_fields = ["base_url", "country", "mission"]
            missing_fields = [f for f in required_fields if not vfs_config.get(f)]
            if missing_fields:
                raise ValueError(
                    f"Missing required VFS configuration fields: "
                    f"{', '.join(missing_fields)}. "
                    f"Please ensure config is validated with ConfigValidator "
                    f"before initializing VFSBot."
                )

            centre_fetcher = CentreFetcher(
                base_url=vfs_config["base_url"],
                country=vfs_config["country"],
                mission=vfs_config["mission"],
                language=vfs_config.get("language", "tr"),
            )

        return CoreServicesContext(
            captcha_solver=captcha_solver,
            centre_fetcher=centre_fetcher,
            otp_service=otp_service,
            rate_limiter=rate_limiter,
            error_capture=error_capture,
            user_semaphore=user_semaphore,
        )

    @staticmethod
    def create_workflow_services(
        config: "BotConfigDict",
        anti_detection: AntiDetectionContext,
        core: CoreServicesContext,
    ) -> WorkflowServicesContext:
        """
        Create workflow services context from configuration and dependencies.

        Args:
            config: Bot configuration dictionary
            anti_detection: Anti-detection context
            core: Core services context

        Returns:
            WorkflowServicesContext with all workflow services
        """
        # Cast to Dict[str, Any] for flexible key access
        config_dict = cast(Dict[str, Any], config)
        # Initialize PaymentService
        payment_config = config_dict.get("payment", {})
        payment_service = None
        try:
            from ..payment_service import PaymentService

            payment_service = PaymentService(payment_config)
            logger.info("PaymentService initialized")
        except (ImportError, ValueError) as e:
            # PaymentService is optional - bot can work without it (manual payment mode)
            logger.warning(f"PaymentService not available: {e}")

        # Initialize AlertService for critical notifications
        alert_config_dict = config_dict.get("alerts", {})
        alert_service = None
        try:
            # Parse enabled channels from config
            enabled_channels_str = alert_config_dict.get("enabled_channels", ["log"])
            enabled_channels = [
                AlertChannel(ch) if isinstance(ch, str) else ch for ch in enabled_channels_str
            ]

            alert_config = AlertConfig(
                enabled_channels=enabled_channels,
                telegram_bot_token=alert_config_dict.get("telegram_bot_token"),
                telegram_chat_id=alert_config_dict.get("telegram_chat_id"),
                webhook_url=alert_config_dict.get("webhook_url"),
            )
            alert_service = AlertService(alert_config)
            logger.info(f"AlertService initialized with channels: {enabled_channels}")
        except (ImportError, ValueError) as e:
            # AlertService is optional - bot can work without it (logs only)
            logger.warning(f"AlertService not available: {e}")

        # Create booking service
        booking_service = BookingOrchestrator(
            config_dict, core.captcha_solver, anti_detection.human_sim, payment_service
        )

        # Create waitlist handler
        waitlist_handler = WaitlistHandler(config_dict, anti_detection.human_sim)

        # Create error handler
        error_handler = ErrorHandler()

        # Create auth service
        auth_service = AuthService(
            config_dict,
            core.captcha_solver,
            anti_detection.human_sim,
            anti_detection.cloudflare_handler,
            core.error_capture,
            core.otp_service,
        )

        # Create page state detector
        page_state_detector = PageStateDetector(
            config=config_dict,
            cloudflare_handler=anti_detection.cloudflare_handler,
        )

        # Get selector manager for country-aware selectors
        from src.selector import get_selector_manager

        country = config_dict.get("vfs", {}).get("mission", "default")
        selector_manager = get_selector_manager(country)

        # Create slot checker with selector manager injection
        slot_checker = SlotChecker(
            config_dict,
            core.rate_limiter,
            anti_detection.human_sim,
            anti_detection.cloudflare_handler,
            core.error_capture,
            page_state_detector,
            selector_manager,
        )

        return WorkflowServicesContext(
            auth_service=auth_service,
            slot_checker=slot_checker,
            booking_service=booking_service,
            waitlist_handler=waitlist_handler,
            error_handler=error_handler,
            page_state_detector=page_state_detector,
            payment_service=payment_service,
            alert_service=alert_service,
        )

    @staticmethod
    def create_automation_services(config: "BotConfigDict") -> AutomationServicesContext:
        """
        Create automation services context from configuration.

        Args:
            config: Bot configuration dictionary

        Returns:
            AutomationServicesContext with all automation services
        """
        # Cast to Dict[str, Any] for flexible key access
        config_dict = cast(Dict[str, Any], config)
        # Country profile loader
        country_profiles = CountryProfileLoader()

        # Get country from config
        vfs_config = config_dict.get("vfs", {})
        country_code = vfs_config.get("country", "tur")

        # Adaptive scheduler with country-specific multiplier
        country_multiplier = country_profiles.get_retry_multiplier(country_code)
        timezone = country_profiles.get_timezone(country_code)
        scheduler = AdaptiveScheduler(timezone=timezone, country_multiplier=country_multiplier)

        # Slot pattern analyzer
        slot_analyzer = SlotPatternAnalyzer()

        # Selector self-healing
        self_healing = SelectorSelfHealing()

        # Session recovery
        session_recovery = SessionRecovery()

        logger.info(
            f"Automation services initialized - "
            f"Country: {country_code}, Timezone: {timezone}, "
            f"Multiplier: {country_multiplier}"
        )

        return AutomationServicesContext(
            scheduler=scheduler,
            slot_analyzer=slot_analyzer,
            self_healing=self_healing,
            session_recovery=session_recovery,
            country_profiles=country_profiles,
        )

    @staticmethod
    def create(
        config: "BotConfigDict",
        captcha_solver: Optional[CaptchaSolver] = None,
        centre_fetcher: Optional[CentreFetcher] = None,
    ) -> BotServiceContext:
        """
        Create complete bot service context from configuration.

        This is the main factory method that creates all service contexts
        and combines them into a single BotServiceContext.

        Args:
            config: Bot configuration dictionary
            captcha_solver: Optional pre-created CaptchaSolver
            centre_fetcher: Optional pre-created CentreFetcher

        Returns:
            Complete BotServiceContext with all services initialized
        """
        # Create contexts in dependency order
        anti_detection = BotServiceFactory.create_anti_detection(config)
        core = BotServiceFactory.create_core_services(config, captcha_solver, centre_fetcher)
        automation = BotServiceFactory.create_automation_services(config)
        workflow = BotServiceFactory.create_workflow_services(config, anti_detection, core)

        return BotServiceContext(
            anti_detection=anti_detection,
            core=core,
            workflow=workflow,
            automation=automation,
        )
