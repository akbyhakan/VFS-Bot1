"""Tests for web/dependencies.py modular structure and backward compatibility."""

import pytest


class TestWebDependenciesModularStructure:
    """Test suite for web/dependencies.py modular refactoring."""

    def test_import_models_from_dependencies(self):
        """Test that all models can be imported from web.dependencies (backward compat)."""
        from web.dependencies import (
            AppointmentPersonRequest,
            AppointmentPersonResponse,
            AppointmentRequestCreate,
            AppointmentRequestResponse,
            BotCommand,
            CountryResponse,
            LoginRequest,
            PaymentCardRequest,
            PaymentCardResponse,
            PaymentInitiateRequest,
            ProxyCreateRequest,
            ProxyResponse,
            ProxyUpdateRequest,
            StatusUpdate,
            TokenResponse,
            UserCreateRequest,
            UserModel,
            UserUpdateRequest,
            WebhookUrlsResponse,
        )
        
        # Just verify they're importable - actual functionality tested elsewhere
        assert LoginRequest is not None
        assert TokenResponse is not None
        assert BotCommand is not None
        assert StatusUpdate is not None
        assert UserCreateRequest is not None
        assert PaymentCardRequest is not None
        assert ProxyCreateRequest is not None

    def test_import_models_from_web_models(self):
        """Test that all models can be imported from web.models package."""
        from web.models import (
            AppointmentPersonRequest,
            AppointmentPersonResponse,
            AppointmentRequestCreate,
            AppointmentRequestResponse,
            BotCommand,
            CountryResponse,
            LoginRequest,
            PaymentCardRequest,
            PaymentCardResponse,
            PaymentInitiateRequest,
            ProxyCreateRequest,
            ProxyResponse,
            ProxyUpdateRequest,
            StatusUpdate,
            TokenResponse,
            UserCreateRequest,
            UserModel,
            UserUpdateRequest,
            WebhookUrlsResponse,
        )
        
        assert LoginRequest is not None
        assert BotCommand is not None

    def test_import_models_from_submodules(self):
        """Test that models can be imported from their specific submodules."""
        from web.models.auth import LoginRequest, TokenResponse
        from web.models.bot import BotCommand, StatusUpdate
        from web.models.users import UserCreateRequest, UserModel, UserUpdateRequest
        from web.models.appointments import (
            AppointmentPersonRequest,
            AppointmentRequestCreate,
        )
        from web.models.payment import PaymentCardRequest, PaymentCardResponse
        from web.models.proxy import ProxyCreateRequest, ProxyResponse
        from web.models.common import CountryResponse, WebhookUrlsResponse
        
        assert all([
            LoginRequest, TokenResponse, BotCommand, StatusUpdate,
            UserCreateRequest, UserModel, PaymentCardRequest, ProxyCreateRequest,
            CountryResponse
        ])

    def test_import_state_classes_from_dependencies(self):
        """Test that state classes can be imported from web.dependencies (backward compat)."""
        from web.dependencies import ThreadSafeBotState, ThreadSafeMetrics
        
        # Create instances to verify they work
        state = ThreadSafeBotState()
        metrics = ThreadSafeMetrics()
        
        assert state is not None
        assert metrics is not None
        
        # Test basic functionality
        state.set("test_key", "test_value")
        assert state.get("test_key") == "test_value"
        
        # Test with an existing metric key
        metrics.increment("requests_total", 1)
        assert metrics.get("requests_total") == 1

    def test_import_state_classes_from_web_state(self):
        """Test that state classes can be imported from web.state package."""
        from web.state import ThreadSafeBotState, ThreadSafeMetrics
        from web.state.bot_state import ThreadSafeBotState as BotState
        from web.state.metrics import ThreadSafeMetrics as Metrics
        
        assert ThreadSafeBotState is BotState
        assert ThreadSafeMetrics is Metrics

    def test_import_websocket_manager_from_dependencies(self):
        """Test that ConnectionManager can be imported from web.dependencies (backward compat)."""
        from web.dependencies import ConnectionManager
        
        manager = ConnectionManager()
        assert manager is not None
        assert hasattr(manager, "connect")
        assert hasattr(manager, "disconnect")
        assert hasattr(manager, "broadcast")

    def test_import_websocket_manager_from_web_websocket(self):
        """Test that ConnectionManager can be imported from web.websocket package."""
        from web.websocket import ConnectionManager
        from web.websocket.manager import ConnectionManager as Manager
        
        assert ConnectionManager is Manager

    def test_global_state_instances_accessible(self):
        """Test that global state instances are accessible from web.dependencies."""
        from web.dependencies import bot_state, manager, metrics
        
        assert bot_state is not None
        assert manager is not None
        assert metrics is not None
        
        # Verify they're the right types
        assert hasattr(bot_state, "get")
        assert hasattr(bot_state, "set")
        assert hasattr(manager, "broadcast")
        assert hasattr(metrics, "increment")

    def test_dependency_functions_accessible(self):
        """Test that dependency functions are accessible from web.dependencies."""
        from web.dependencies import broadcast_message, get_db, verify_jwt_token
        
        assert callable(verify_jwt_token)
        assert callable(get_db)
        assert callable(broadcast_message)

    def test_model_validation_still_works(self):
        """Test that Pydantic model validation still works after refactoring."""
        from web.models.auth import LoginRequest
        from web.models.payment import PaymentCardRequest
        
        # Test LoginRequest
        login = LoginRequest(username="test@example.com", password="password123")
        assert login.username == "test@example.com"
        
        # Test PaymentCardRequest with Luhn validation
        with pytest.raises(ValueError, match="Invalid card number"):
            PaymentCardRequest(
                card_holder_name="John Doe",
                card_number="1234567890123456",  # Invalid Luhn
                expiry_month="12",
                expiry_year="25",
                cvv="123"
            )

    def test_same_objects_from_different_imports(self):
        """Test that the same classes are accessible from both old and new import paths."""
        from web.dependencies import LoginRequest as OldLoginRequest
        from web.models.auth import LoginRequest as NewLoginRequest
        
        from web.dependencies import ConnectionManager as OldManager
        from web.websocket import ConnectionManager as NewManager
        
        from web.dependencies import ThreadSafeBotState as OldState
        from web.state import ThreadSafeBotState as NewState
        
        # All should be the exact same class
        assert OldLoginRequest is NewLoginRequest
        assert OldManager is NewManager
        assert OldState is NewState
