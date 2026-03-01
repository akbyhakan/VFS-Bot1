"""Tests for BotLoopManager circuit breaker recovery notification."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.infra.circuit_breaker import CircuitState
from src.services.bot.bot_loop_manager import BotLoopManager
from src.services.notification.alert_service import AlertSeverity


@pytest.fixture
def mock_circuit_breaker():
    """Mock CircuitBreaker."""
    cb = MagicMock()
    cb.can_execute = AsyncMock(return_value=True)
    cb.record_success = AsyncMock()
    cb.record_failure = AsyncMock()
    cb.get_wait_time = AsyncMock(return_value=30)
    cb.get_stats = MagicMock(return_value={"failure_count": 0})
    cb.state = CircuitState.CLOSED
    return cb


@pytest.fixture
def mock_services():
    """Mock BotServiceContext."""
    services = MagicMock()
    services.workflow.alert_service = MagicMock()
    return services


@pytest.fixture
def bot_loop_manager(mock_circuit_breaker, mock_services):
    """Create a BotLoopManager with mocked dependencies."""
    db = MagicMock()

    browser_manager = MagicMock()
    browser_manager.should_restart = AsyncMock(return_value=False)

    account_pool = MagicMock()
    account_pool.load_accounts = AsyncMock(return_value=1)
    account_pool.get_pool_status = AsyncMock(
        return_value={"available": 1, "in_cooldown": 0, "quarantined": 0}
    )

    session_orchestrator = MagicMock()
    session_orchestrator.run_session = AsyncMock(
        return_value={"session_number": 1, "missions_processed": 1}
    )

    notifier = AsyncMock()
    notifier.notify_error = AsyncMock()

    shutdown_event = asyncio.Event()
    trigger_event = asyncio.Event()

    return BotLoopManager(
        config={},
        db=db,
        services=mock_services,
        browser_manager=browser_manager,
        circuit_breaker=mock_circuit_breaker,
        account_pool=account_pool,
        session_orchestrator=session_orchestrator,
        notifier=notifier,
        shutdown_event=shutdown_event,
        trigger_event=trigger_event,
    )


@pytest.mark.asyncio
async def test_recovery_notification_sent_when_half_open_recovers(
    bot_loop_manager, mock_circuit_breaker, mock_services
):
    """Test recovery notification when circuit transitions HALF_OPEN → CLOSED."""
    mock_circuit_breaker.state = CircuitState.HALF_OPEN

    async def record_success_side_effect():
        mock_circuit_breaker.state = CircuitState.CLOSED

    mock_circuit_breaker.record_success = AsyncMock(side_effect=record_success_side_effect)
    bot_loop_manager._wait_adaptive_interval = AsyncMock(return_value=True)

    with patch("src.services.bot.bot_loop_manager.send_alert_safe") as mock_alert:
        mock_alert.return_value = None
        await bot_loop_manager.run_bot_loop()

    mock_alert.assert_any_call(
        alert_service=mock_services.workflow.alert_service,
        message="✅ Circuit breaker recovered — bot is operating normally again",
        severity=AlertSeverity.INFO,
        metadata={"previous_state": "recovering", "new_state": "closed"},
    )


@pytest.mark.asyncio
async def test_recovery_notification_sent_when_open_recovers(
    bot_loop_manager, mock_circuit_breaker, mock_services
):
    """Test recovery notification when circuit transitions OPEN → CLOSED."""
    mock_circuit_breaker.state = CircuitState.OPEN

    async def record_success_side_effect():
        mock_circuit_breaker.state = CircuitState.CLOSED

    mock_circuit_breaker.record_success = AsyncMock(side_effect=record_success_side_effect)
    bot_loop_manager._wait_adaptive_interval = AsyncMock(return_value=True)

    with patch("src.services.bot.bot_loop_manager.send_alert_safe") as mock_alert:
        mock_alert.return_value = None
        await bot_loop_manager.run_bot_loop()

    mock_alert.assert_any_call(
        alert_service=mock_services.workflow.alert_service,
        message="✅ Circuit breaker recovered — bot is operating normally again",
        severity=AlertSeverity.INFO,
        metadata={"previous_state": "recovering", "new_state": "closed"},
    )


@pytest.mark.asyncio
async def test_no_recovery_notification_when_already_closed(
    bot_loop_manager, mock_circuit_breaker
):
    """Test no recovery notification when circuit breaker was already CLOSED."""
    mock_circuit_breaker.state = CircuitState.CLOSED
    bot_loop_manager._wait_adaptive_interval = AsyncMock(return_value=True)

    with patch("src.services.bot.bot_loop_manager.send_alert_safe") as mock_alert:
        mock_alert.return_value = None
        await bot_loop_manager.run_bot_loop()

    for call in mock_alert.call_args_list:
        _, kwargs = call
        assert "recovered" not in kwargs.get("message", "")
