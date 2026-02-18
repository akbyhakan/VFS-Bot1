"""Tests for refactored bot structure."""


def test_new_modular_imports():
    """Test that new modular imports work."""
    from src.services.bot import (
        AuthService,
        BrowserManager,
        ErrorHandler,
        SlotChecker,
        SlotInfo,
        VFSBot,
    )

    assert VFSBot is not None
    assert BrowserManager is not None
    assert AuthService is not None
    assert SlotChecker is not None
    assert ErrorHandler is not None
    assert SlotInfo is not None


def test_individual_component_imports():
    """Test that individual components can be imported."""
    from src.services.bot.auth_service import AuthService
    from src.services.bot.browser_manager import BrowserManager
    from src.services.bot.error_handler import ErrorHandler
    from src.services.bot.slot_checker import SlotChecker

    assert BrowserManager is not None
    assert AuthService is not None
    assert SlotChecker is not None
    assert ErrorHandler is not None


def test_slot_info_type():
    """Test SlotInfo TypedDict."""
    from src.services.bot import SlotInfo

    # Create a valid SlotInfo instance
    slot: SlotInfo = {"date": "2024-01-01", "time": "10:00"}

    assert slot["date"] == "2024-01-01"
    assert slot["time"] == "10:00"


def test_circuit_breaker_imports():
    """Test that CircuitBreaker can be imported from core infrastructure."""
    from src.core.infra.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState

    assert CircuitBreaker is not None
    assert CircuitBreakerError is not None
    assert CircuitState is not None
