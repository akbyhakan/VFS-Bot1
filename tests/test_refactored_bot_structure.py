"""Tests for refactored bot structure."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_backward_compatibility_import():
    """Test that old imports still work."""
    # This should work for backward compatibility
    from src.services.bot_service import VFSBot, SlotInfo

    assert VFSBot is not None
    assert SlotInfo is not None


def test_new_modular_imports():
    """Test that new modular imports work."""
    from src.services.bot import (
        VFSBot,
        BrowserManager,
        AuthService,
        SlotChecker,
        CircuitBreakerService,
        ErrorHandler,
        SlotInfo,
    )

    assert VFSBot is not None
    assert BrowserManager is not None
    assert AuthService is not None
    assert SlotChecker is not None
    assert CircuitBreakerService is not None
    assert ErrorHandler is not None
    assert SlotInfo is not None


def test_individual_component_imports():
    """Test that individual components can be imported."""
    from src.services.bot.browser_manager import BrowserManager
    from src.services.bot.auth_service import AuthService
    from src.services.bot.slot_checker import SlotChecker
    from src.services.bot.circuit_breaker_service import CircuitBreakerService
    from src.services.bot.error_handler import ErrorHandler

    assert BrowserManager is not None
    assert AuthService is not None
    assert SlotChecker is not None
    assert CircuitBreakerService is not None
    assert ErrorHandler is not None


def test_slot_info_type():
    """Test SlotInfo TypedDict."""
    from src.services.bot import SlotInfo

    # Create a valid SlotInfo instance
    slot: SlotInfo = {"date": "2024-01-01", "time": "10:00"}

    assert slot["date"] == "2024-01-01"
    assert slot["time"] == "10:00"


def test_circuit_breaker_stats_type():
    """Test CircuitBreakerStats TypedDict."""
    from src.services.bot import CircuitBreakerStats

    # Create a valid CircuitBreakerStats instance
    stats: CircuitBreakerStats = {
        "consecutive_errors": 0,
        "total_errors_in_window": 0,
        "is_open": False,
        "open_time": None,
    }

    assert stats["consecutive_errors"] == 0
    assert stats["is_open"] is False
