"""Tests for circuit breaker implementations."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
from collections import deque

from src.services.bot_service import VFSBot
from src.models.database import Database
from src.services.notification import NotificationService
from src.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerError
from src.services.circuit_breaker import (
    CircuitBreakerService,
    CircuitState as ServiceCircuitState,
    CircuitBreakerStats,
)


@pytest.mark.asyncio
async def test_circuit_breaker_thread_safety():
    """Test that circuit breaker error recording is thread-safe."""
    # Create a mock config
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
    }

    # Create mocks
    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)

    # Create bot instance
    bot = VFSBot(config, db, notifier)

    # Verify _error_lock exists
    assert hasattr(bot, "_error_lock")
    assert isinstance(bot._error_lock, asyncio.Lock)

    # Test concurrent error recording
    async def record_errors(count: int):
        """Record multiple errors concurrently."""
        for _ in range(count):
            await bot._record_error()

    # Run concurrent error recordings
    await asyncio.gather(
        record_errors(5),
        record_errors(5),
        record_errors(5),
    )

    # Verify consecutive errors are correct (15 total)
    assert bot.consecutive_errors == 15
    assert len(bot.total_errors) == 15


@pytest.mark.asyncio
async def test_circuit_breaker_async_signature():
    """Test that _record_error is async and returns None."""
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
    }

    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    bot = VFSBot(config, db, notifier)

    # Verify _record_error is a coroutine function
    assert asyncio.iscoroutinefunction(bot._record_error)

    # Test that it can be awaited
    result = await bot._record_error()
    assert result is None


@pytest.mark.asyncio
async def test_circuit_breaker_opens_with_concurrent_errors():
    """Test that circuit breaker opens correctly under concurrent load."""
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
    }

    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    bot = VFSBot(config, db, notifier)

    # Record enough errors to trigger circuit breaker
    # Default MAX_CONSECUTIVE_ERRORS is typically 5
    for _ in range(10):
        await bot._record_error()

    # Circuit breaker should be open
    assert bot.circuit_breaker_open is True
    assert bot.circuit_breaker_open_time is not None


# New tests for generic circuit breaker


@pytest.mark.asyncio
async def test_generic_circuit_breaker_initial_state():
    """Test circuit breaker starts in closed state."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_generic_circuit_breaker_opens_after_threshold():
    """Test circuit breaker opens after reaching failure threshold."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

    async def failing_function():
        raise Exception("Test failure")

    # Record failures up to threshold
    for _ in range(3):
        with pytest.raises(Exception):
            await cb.call(failing_function)

    # Circuit should now be open
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 3


@pytest.mark.asyncio
async def test_generic_circuit_breaker_rejects_when_open():
    """Test circuit breaker rejects calls when open."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)

    async def failing_function():
        raise Exception("Test failure")

    # Trigger circuit to open
    for _ in range(2):
        with pytest.raises(Exception):
            await cb.call(failing_function)

    # Should now reject with CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        await cb.call(failing_function)


@pytest.mark.asyncio
async def test_generic_circuit_breaker_half_open_state():
    """Test circuit breaker transitions to half-open after timeout."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

    async def failing_function():
        raise Exception("Test failure")

    # Open the circuit
    for _ in range(2):
        with pytest.raises(Exception):
            await cb.call(failing_function)

    assert cb.state == CircuitState.OPEN

    # Wait for timeout
    await asyncio.sleep(0.2)

    # Next call should transition to half-open (but still fail)
    with pytest.raises(Exception):
        await cb.call(failing_function)

    # State should have been half-open during the call
    assert cb.state == CircuitState.OPEN  # Back to open after failure


@pytest.mark.asyncio
async def test_generic_circuit_breaker_resets_on_success():
    """Test circuit breaker resets failure count on success."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=5)

    call_count = [0]

    async def sometimes_failing_function():
        call_count[0] += 1
        if call_count[0] < 3:
            raise Exception("Test failure")
        return "success"

    # First two calls fail
    for _ in range(2):
        with pytest.raises(Exception):
            await cb.call(sometimes_failing_function)

    assert cb.failure_count == 2

    # Third call succeeds
    result = await cb.call(sometimes_failing_function)

    assert result == "success"
    assert cb.failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_generic_circuit_breaker_decorator():
    """Test circuit breaker decorator."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)

    call_count = [0]

    @cb.protected
    async def decorated_function():
        call_count[0] += 1
        if call_count[0] < 2:
            raise Exception("Test failure")
        return "success"

    # First call fails
    with pytest.raises(Exception):
        await decorated_function()

    # Second call succeeds
    result = await decorated_function()
    assert result == "success"


@pytest.mark.asyncio
async def test_generic_circuit_breaker_stats():
    """Test circuit breaker statistics."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60, name="TestBreaker")

    stats = cb.get_stats()

    assert stats["name"] == "TestBreaker"
    assert stats["state"] == CircuitState.CLOSED.value
    assert stats["failure_count"] == 0
    assert stats["failure_threshold"] == 3
    assert stats["timeout_seconds"] == 60


@pytest.mark.asyncio
async def test_generic_circuit_breaker_manual_reset():
    """Test manual circuit breaker reset."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)

    async def failing_function():
        raise Exception("Test failure")

    # Open the circuit
    for _ in range(2):
        with pytest.raises(Exception):
            await cb.call(failing_function)

    assert cb.state == CircuitState.OPEN

    # Manually reset
    await cb.reset()

    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


# Tests for CircuitBreakerService


@pytest.mark.asyncio
async def test_circuit_breaker_service_initialization():
    """Test CircuitBreakerService initializes in CLOSED state."""
    cb = CircuitBreakerService()

    assert cb.state == ServiceCircuitState.CLOSED
    assert cb.consecutive_errors == 0
    assert await cb.is_available() is True


@pytest.mark.asyncio
async def test_circuit_breaker_service_opens_on_consecutive_failures():
    """Test CircuitBreakerService opens after consecutive failures."""
    cb = CircuitBreakerService(fail_threshold=3)

    # Record failures
    await cb.record_failure()
    await cb.record_failure()
    assert await cb.is_available() is True

    # Third failure should open circuit
    await cb.record_failure()
    assert await cb.is_available() is False
    assert cb.state == ServiceCircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_service_resets_on_success():
    """Test CircuitBreakerService resets consecutive errors on success."""
    cb = CircuitBreakerService(fail_threshold=3)

    await cb.record_failure()
    await cb.record_failure()
    assert cb.consecutive_errors == 2

    # Success should reset counter
    await cb.record_success()
    assert cb.consecutive_errors == 0
    assert cb.state == ServiceCircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_service_half_open_transition():
    """Test CircuitBreakerService transitions to HALF_OPEN after timeout."""
    cb = CircuitBreakerService(fail_threshold=2, reset_timeout=1)

    # Open circuit
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == ServiceCircuitState.OPEN

    # Wait for reset timeout
    await asyncio.sleep(1.1)

    # Should transition to HALF_OPEN on next check
    is_available = await cb.is_available()
    assert is_available is True
    assert cb.state == ServiceCircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_service_get_stats():
    """Test getting CircuitBreakerService statistics."""
    cb = CircuitBreakerService(fail_threshold=3)

    await cb.record_failure()
    await cb.record_failure()

    stats = await cb.get_stats()

    assert isinstance(stats, CircuitBreakerStats)
    assert stats.state == ServiceCircuitState.CLOSED
    assert stats.consecutive_errors == 2
    assert stats.total_errors_in_window == 2


@pytest.mark.asyncio
async def test_circuit_breaker_service_manual_reset():
    """Test manual reset of CircuitBreakerService."""
    cb = CircuitBreakerService(fail_threshold=2)

    # Open circuit
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == ServiceCircuitState.OPEN

    # Manual reset
    await cb.reset()
    assert cb.state == ServiceCircuitState.CLOSED
    assert cb.consecutive_errors == 0
    assert await cb.is_available() is True
