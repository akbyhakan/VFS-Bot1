"""Tests for web/dependencies.py modular structure."""

import pytest


class TestWebDependenciesModularStructure:
    """Test suite for web/dependencies.py modular refactoring."""

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
        from web.models.appointments import (
            AppointmentPersonRequest,
            AppointmentRequestCreate,
        )
        from web.models.auth import LoginRequest, TokenResponse
        from web.models.bot import BotCommand, StatusUpdate
        from web.models.common import CountryResponse, WebhookUrlsResponse
        from web.models.payment import PaymentCardRequest, PaymentCardResponse
        from web.models.proxy import ProxyCreateRequest, ProxyResponse
        from web.models.users import UserCreateRequest, UserModel, UserUpdateRequest

        assert all(
            [
                LoginRequest,
                TokenResponse,
                BotCommand,
                StatusUpdate,
                UserCreateRequest,
                UserModel,
                PaymentCardRequest,
                ProxyCreateRequest,
                CountryResponse,
            ]
        )

    def test_import_state_classes_from_web_state(self):
        """Test that state classes can be imported from web.state package."""
        from web.state import ThreadSafeBotState, ThreadSafeMetrics
        from web.state.bot_state import ThreadSafeBotState as BotState
        from web.state.metrics import ThreadSafeMetrics as Metrics

        assert ThreadSafeBotState is BotState
        assert ThreadSafeMetrics is Metrics

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
                cvv="123",
            )
