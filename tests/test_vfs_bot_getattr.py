"""Tests for VFSBot __getattr__ refactoring and deprecation warnings."""

import warnings
from unittest.mock import MagicMock

import pytest

from src.services.bot.vfs_bot import VFSBot


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return {
        "captcha": {
            "api_key": "test_key",
            "manual_timeout": 120,
        },
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "Turkiye",
        },
        "centre": "Istanbul",
        "visa_category": "Schengen Visa",
        "visa_subcategory": "Tourism",
        "anti_detection_enabled": True,
        "scheduling": {
            "enabled": False,
        },
    }


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_notifier():
    """Create a mock notifier."""
    return MagicMock()


class TestVFSBotGetAttr:
    """Test suite for VFSBot __getattr__ implementation."""

    def test_legacy_workflow_service_access_with_warning(self, mock_config, mock_db, mock_notifier):
        """Test that legacy workflow service access emits deprecation warning."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        # Test auth_service access
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bot.auth_service
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "Direct access to 'auth_service' is deprecated since v2.0" in str(w[0].message)
            assert "bot.services.workflow.auth_service" in str(w[0].message)
            assert "This will be removed in v3.0" in str(w[0].message)

    def test_legacy_core_service_access_with_warning(self, mock_config, mock_db, mock_notifier):
        """Test that legacy core service access emits deprecation warning."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        # Test captcha_solver access
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bot.captcha_solver
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "Direct access to 'captcha_solver' is deprecated since v2.0" in str(w[0].message)
            assert "bot.services.core.captcha_solver" in str(w[0].message)

    def test_legacy_anti_detection_service_access_with_warning(self, mock_config, mock_db, mock_notifier):
        """Test that legacy anti-detection service access emits deprecation warning."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        # Test human_sim access
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bot.human_sim
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "Direct access to 'human_sim' is deprecated since v2.0" in str(w[0].message)
            assert "bot.services.anti_detection.human_sim" in str(w[0].message)

    def test_legacy_automation_service_access_with_warning(self, mock_config, mock_db, mock_notifier):
        """Test that legacy automation service access emits deprecation warning."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        # Test scheduler access
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bot.scheduler
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "Direct access to 'scheduler' is deprecated since v2.0" in str(w[0].message)
            assert "bot.services.automation.scheduler" in str(w[0].message)

    def test_legacy_special_attr_access_with_warning(self, mock_config, mock_db, mock_notifier):
        """Test that legacy special attribute access emits deprecation warning."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        # Test anti_detection_enabled access
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bot.anti_detection_enabled
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "Direct access to 'anti_detection_enabled' is deprecated since v2.0" in str(w[0].message)
            assert "bot.services.anti_detection.enabled" in str(w[0].message)

    def test_all_legacy_attrs_accessible(self, mock_config, mock_db, mock_notifier):
        """Test that all 25 legacy attributes are accessible via __getattr__."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        legacy_attrs = [
            # Workflow services
            "auth_service", "slot_checker", "booking_service", "error_handler",
            "waitlist_handler", "alert_service", "payment_service",
            # Core services
            "captcha_solver", "centre_fetcher", "otp_service", "rate_limiter",
            "error_capture", "user_semaphore",
            # Anti-detection services
            "human_sim", "header_manager", "session_manager", "token_sync",
            "cloudflare_handler", "proxy_manager",
            # Automation services
            "scheduler", "slot_analyzer", "self_healing", "session_recovery",
            "country_profiles",
        ]
        
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            for attr in legacy_attrs:
                # Each attribute should be accessible without raising AttributeError
                result = getattr(bot, attr)
                assert result is not None, f"Attribute {attr} should not be None"

    def test_invalid_attribute_raises_error(self, mock_config, mock_db, mock_notifier):
        """Test that accessing invalid attribute raises AttributeError."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        with pytest.raises(AttributeError) as exc_info:
            _ = bot.nonexistent_attribute
        
        assert "'VFSBot' has no attribute 'nonexistent_attribute'" in str(exc_info.value)

    def test_legacy_access_returns_correct_service(self, mock_config, mock_db, mock_notifier):
        """Test that legacy access returns the same object as new access."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            
            # Test a few examples
            assert bot.auth_service is bot.services.workflow.auth_service
            assert bot.captcha_solver is bot.services.core.captcha_solver
            assert bot.human_sim is bot.services.anti_detection.human_sim
            assert bot.scheduler is bot.services.automation.scheduler

    def test_stacklevel_correct_in_warning(self, mock_config, mock_db, mock_notifier):
        """Test that deprecation warning points to the caller, not __getattr__."""
        bot = VFSBot(mock_config, mock_db, mock_notifier)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = bot.auth_service
            
            # stacklevel=2 should point to this test function, not __getattr__
            assert len(w) == 1
            # The warning should be emitted from this test file
            assert "test_vfs_bot_getattr.py" in w[0].filename or "test_" in w[0].filename
