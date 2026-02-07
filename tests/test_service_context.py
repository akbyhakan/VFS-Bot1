"""Tests for VFSBot service context and factory classes."""

import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.services.bot.service_context import (
    AntiDetectionContext,
    AutomationServicesContext,
    BotServiceContext,
    BotServiceFactory,
    CoreServicesContext,
    WorkflowServicesContext,
)
from src.services.captcha_solver import CaptchaSolver
from src.services.centre_fetcher import CentreFetcher


@pytest.fixture
def minimal_config():
    """Minimal valid configuration for testing."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
            "language": "tr",
        },
        "captcha": {
            "api_key": "test_key",
            "manual_timeout": 120,
        },
        "anti_detection": {
            "enabled": True,
        },
        "human_behavior": {},
        "session": {
            "save_file": "data/session.json",
            "token_refresh_buffer": 5,
        },
        "cloudflare": {},
        "proxy": {},
        "payment": {},
        "alerts": {
            "enabled_channels": ["log"],
        },
    }


@pytest.fixture
def disabled_anti_detection_config():
    """Configuration with anti-detection disabled."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        },
        "captcha": {},
        "anti_detection": {
            "enabled": False,
        },
    }


class TestAntiDetectionContext:
    """Test AntiDetectionContext dataclass."""

    def test_anti_detection_context_creation(self):
        """Test creating an AntiDetectionContext instance."""
        context = AntiDetectionContext(
            enabled=True,
            human_sim=None,
            header_manager=None,
            session_manager=None,
            cloudflare_handler=None,
            proxy_manager=None,
        )

        assert context.enabled is True
        assert context.human_sim is None
        assert context.header_manager is None
        assert context.session_manager is None
        assert context.cloudflare_handler is None
        assert context.proxy_manager is None

    def test_anti_detection_context_immutable(self):
        """Test that AntiDetectionContext is immutable (frozen)."""
        context = AntiDetectionContext(
            enabled=True,
            human_sim=None,
            header_manager=None,
            session_manager=None,
            cloudflare_handler=None,
            proxy_manager=None,
        )

        # Frozen dataclass should not allow attribute modification
        with pytest.raises(AttributeError):
            context.enabled = False


class TestCoreServicesContext:
    """Test CoreServicesContext dataclass."""

    def test_core_services_context_creation(self):
        """Test creating a CoreServicesContext instance."""
        mock_captcha = Mock()
        mock_centre = Mock()
        mock_otp = Mock()
        mock_rate_limiter = Mock()
        mock_error_capture = Mock()
        mock_semaphore = asyncio.Semaphore(5)

        context = CoreServicesContext(
            captcha_solver=mock_captcha,
            centre_fetcher=mock_centre,
            otp_service=mock_otp,
            rate_limiter=mock_rate_limiter,
            error_capture=mock_error_capture,
            user_semaphore=mock_semaphore,
        )

        assert context.captcha_solver is mock_captcha
        assert context.centre_fetcher is mock_centre
        assert context.otp_service is mock_otp
        assert context.rate_limiter is mock_rate_limiter
        assert context.error_capture is mock_error_capture
        assert context.user_semaphore is mock_semaphore

    def test_core_services_context_immutable(self):
        """Test that CoreServicesContext is immutable (frozen)."""
        context = CoreServicesContext(
            captcha_solver=Mock(),
            centre_fetcher=Mock(),
            otp_service=Mock(),
            rate_limiter=Mock(),
            error_capture=Mock(),
            user_semaphore=asyncio.Semaphore(5),
        )

        # Frozen dataclass should not allow attribute modification
        with pytest.raises(AttributeError):
            context.captcha_solver = Mock()


class TestWorkflowServicesContext:
    """Test WorkflowServicesContext dataclass."""

    def test_workflow_services_context_creation(self):
        """Test creating a WorkflowServicesContext instance."""
        context = WorkflowServicesContext(
            auth_service=Mock(),
            slot_checker=Mock(),
            booking_service=Mock(),
            waitlist_handler=Mock(),
            error_handler=Mock(),
            payment_service=Mock(),
            alert_service=Mock(),
        )

        assert context.auth_service is not None
        assert context.slot_checker is not None
        assert context.booking_service is not None
        assert context.waitlist_handler is not None
        assert context.error_handler is not None
        assert context.payment_service is not None
        assert context.alert_service is not None

    def test_workflow_services_context_mutable(self):
        """Test that WorkflowServicesContext is mutable (not frozen)."""
        context = WorkflowServicesContext(
            auth_service=Mock(),
            slot_checker=Mock(),
            booking_service=Mock(),
            waitlist_handler=Mock(),
            error_handler=Mock(),
        )

        # Should be able to modify attributes (not frozen)
        new_auth = Mock()
        context.auth_service = new_auth
        assert context.auth_service is new_auth


class TestAutomationServicesContext:
    """Test AutomationServicesContext dataclass."""

    def test_automation_services_context_creation(self):
        """Test creating an AutomationServicesContext instance."""
        context = AutomationServicesContext(
            scheduler=Mock(),
            slot_analyzer=Mock(),
            self_healing=Mock(),
            session_recovery=Mock(),
            country_profiles=Mock(),
        )

        assert context.scheduler is not None
        assert context.slot_analyzer is not None
        assert context.self_healing is not None
        assert context.session_recovery is not None
        assert context.country_profiles is not None


class TestBotServiceContext:
    """Test BotServiceContext dataclass."""

    def test_bot_service_context_creation(self):
        """Test creating a BotServiceContext instance."""
        anti_detection = AntiDetectionContext(
            enabled=False,
            human_sim=None,
            header_manager=None,
            session_manager=None,
            cloudflare_handler=None,
            proxy_manager=None,
        )
        core = CoreServicesContext(
            captcha_solver=Mock(),
            centre_fetcher=Mock(),
            otp_service=Mock(),
            rate_limiter=Mock(),
            error_capture=Mock(),
            user_semaphore=asyncio.Semaphore(5),
        )
        workflow = WorkflowServicesContext(
            auth_service=Mock(),
            slot_checker=Mock(),
            booking_service=Mock(),
            waitlist_handler=Mock(),
            error_handler=Mock(),
        )
        automation = AutomationServicesContext(
            scheduler=Mock(),
            slot_analyzer=Mock(),
            self_healing=Mock(),
            session_recovery=Mock(),
            country_profiles=Mock(),
        )

        context = BotServiceContext(
            anti_detection=anti_detection,
            core=core,
            workflow=workflow,
            automation=automation,
        )

        assert context.anti_detection is anti_detection
        assert context.core is core
        assert context.workflow is workflow
        assert context.automation is automation


class TestBotServiceFactoryAntiDetection:
    """Test BotServiceFactory.create_anti_detection method."""

    def test_create_anti_detection_enabled(self, minimal_config):
        """Test creating anti-detection context with features enabled."""
        context = BotServiceFactory.create_anti_detection(minimal_config)

        assert context.enabled is True
        assert context.human_sim is not None
        assert context.header_manager is not None
        assert context.session_manager is not None
        assert context.cloudflare_handler is not None
        assert context.proxy_manager is not None

    def test_create_anti_detection_disabled(self, disabled_anti_detection_config):
        """Test creating anti-detection context with features disabled."""
        context = BotServiceFactory.create_anti_detection(disabled_anti_detection_config)

        assert context.enabled is False
        assert context.human_sim is None
        assert context.header_manager is None
        assert context.session_manager is None
        assert context.cloudflare_handler is None
        assert context.proxy_manager is None

    def test_create_anti_detection_default_enabled(self):
        """Test that anti-detection is enabled by default when config is missing."""
        config = {}
        context = BotServiceFactory.create_anti_detection(config)

        # Should default to enabled=True
        assert context.enabled is True


class TestBotServiceFactoryCoreServices:
    """Test BotServiceFactory.create_core_services method."""

    def test_create_core_services_with_defaults(self, minimal_config):
        """Test creating core services with default instances."""
        context = BotServiceFactory.create_core_services(minimal_config)

        assert context.captcha_solver is not None
        assert isinstance(context.captcha_solver, CaptchaSolver)
        assert context.centre_fetcher is not None
        assert isinstance(context.centre_fetcher, CentreFetcher)
        assert context.otp_service is not None
        assert context.rate_limiter is not None
        assert context.error_capture is not None
        assert context.user_semaphore is not None
        assert isinstance(context.user_semaphore, asyncio.Semaphore)

    def test_create_core_services_with_injected_captcha(self, minimal_config):
        """Test creating core services with injected CaptchaSolver."""
        mock_captcha = MagicMock(spec=CaptchaSolver)
        context = BotServiceFactory.create_core_services(minimal_config, captcha_solver=mock_captcha)

        assert context.captcha_solver is mock_captcha

    def test_create_core_services_with_injected_centre_fetcher(self, minimal_config):
        """Test creating core services with injected CentreFetcher."""
        mock_centre = MagicMock(spec=CentreFetcher)
        context = BotServiceFactory.create_core_services(minimal_config, centre_fetcher=mock_centre)

        assert context.centre_fetcher is mock_centre

    def test_create_core_services_missing_vfs_config(self):
        """Test that missing VFS config raises ValueError."""
        config = {"captcha": {}}

        with pytest.raises(ValueError) as exc_info:
            BotServiceFactory.create_core_services(config)

        assert "Missing required VFS configuration fields" in str(exc_info.value)


class TestBotServiceFactoryWorkflowServices:
    """Test BotServiceFactory.create_workflow_services method."""

    def test_create_workflow_services(self, minimal_config):
        """Test creating workflow services context."""
        anti_detection = BotServiceFactory.create_anti_detection(minimal_config)
        core = BotServiceFactory.create_core_services(minimal_config)

        context = BotServiceFactory.create_workflow_services(minimal_config, anti_detection, core)

        assert context.auth_service is not None
        assert context.slot_checker is not None
        assert context.booking_service is not None
        assert context.waitlist_handler is not None
        assert context.error_handler is not None
        # payment_service and alert_service are optional but may be available
        # Just check they are either None or initialized
        assert context.alert_service is not None  # Should be created with log channel


class TestBotServiceFactoryAutomationServices:
    """Test BotServiceFactory.create_automation_services method."""

    def test_create_automation_services(self, minimal_config):
        """Test creating automation services context."""
        context = BotServiceFactory.create_automation_services(minimal_config)

        assert context.scheduler is not None
        assert context.slot_analyzer is not None
        assert context.self_healing is not None
        assert context.session_recovery is not None
        assert context.country_profiles is not None

    def test_create_automation_services_default_country(self):
        """Test automation services with default country code."""
        config = {"vfs": {}}
        context = BotServiceFactory.create_automation_services(config)

        # Should use default country code 'tur'
        assert context.scheduler is not None
        assert context.country_profiles is not None


class TestBotServiceFactoryCreate:
    """Test BotServiceFactory.create method (full context creation)."""

    def test_create_full_context(self, minimal_config):
        """Test creating complete bot service context."""
        context = BotServiceFactory.create(minimal_config)

        assert isinstance(context, BotServiceContext)
        assert isinstance(context.anti_detection, AntiDetectionContext)
        assert isinstance(context.core, CoreServicesContext)
        assert isinstance(context.workflow, WorkflowServicesContext)
        assert isinstance(context.automation, AutomationServicesContext)

    def test_create_with_injected_services(self, minimal_config):
        """Test creating context with injected captcha and centre fetcher."""
        mock_captcha = MagicMock(spec=CaptchaSolver)
        mock_centre = MagicMock(spec=CentreFetcher)

        context = BotServiceFactory.create(
            minimal_config,
            captcha_solver=mock_captcha,
            centre_fetcher=mock_centre,
        )

        assert context.core.captcha_solver is mock_captcha
        assert context.core.centre_fetcher is mock_centre

    def test_create_anti_detection_disabled(self, disabled_anti_detection_config):
        """Test creating context with anti-detection disabled."""
        context = BotServiceFactory.create(disabled_anti_detection_config)

        assert context.anti_detection.enabled is False
        assert context.anti_detection.human_sim is None
        assert context.anti_detection.header_manager is None


class TestServiceContextIntegration:
    """Integration tests for service contexts."""

    def test_context_structure_complete(self, minimal_config):
        """Test that created context has complete structure."""
        context = BotServiceFactory.create(minimal_config)

        # Anti-detection services
        assert hasattr(context.anti_detection, "enabled")
        assert hasattr(context.anti_detection, "human_sim")
        assert hasattr(context.anti_detection, "header_manager")
        assert hasattr(context.anti_detection, "session_manager")
        assert hasattr(context.anti_detection, "cloudflare_handler")
        assert hasattr(context.anti_detection, "proxy_manager")

        # Core services
        assert hasattr(context.core, "captcha_solver")
        assert hasattr(context.core, "centre_fetcher")
        assert hasattr(context.core, "otp_service")
        assert hasattr(context.core, "rate_limiter")
        assert hasattr(context.core, "error_capture")
        assert hasattr(context.core, "user_semaphore")

        # Workflow services
        assert hasattr(context.workflow, "auth_service")
        assert hasattr(context.workflow, "slot_checker")
        assert hasattr(context.workflow, "booking_service")
        assert hasattr(context.workflow, "waitlist_handler")
        assert hasattr(context.workflow, "error_handler")
        assert hasattr(context.workflow, "payment_service")
        assert hasattr(context.workflow, "alert_service")

        # Automation services
        assert hasattr(context.automation, "scheduler")
        assert hasattr(context.automation, "slot_analyzer")
        assert hasattr(context.automation, "self_healing")
        assert hasattr(context.automation, "session_recovery")
        assert hasattr(context.automation, "country_profiles")

    def test_services_are_properly_initialized(self, minimal_config):
        """Test that all services in context are properly initialized."""
        context = BotServiceFactory.create(minimal_config)

        # Core services should not be None
        assert context.core.captcha_solver is not None
        assert context.core.centre_fetcher is not None
        assert context.core.otp_service is not None
        assert context.core.rate_limiter is not None
        assert context.core.error_capture is not None
        assert context.core.user_semaphore is not None

        # Workflow services should not be None (except optional ones)
        assert context.workflow.auth_service is not None
        assert context.workflow.slot_checker is not None
        assert context.workflow.booking_service is not None
        assert context.workflow.waitlist_handler is not None
        assert context.workflow.error_handler is not None

        # Automation services should not be None
        assert context.automation.scheduler is not None
        assert context.automation.slot_analyzer is not None
        assert context.automation.self_healing is not None
        assert context.automation.session_recovery is not None
        assert context.automation.country_profiles is not None
