"""Tests for circuit breaker implementations."""

import asyncio
from collections import deque
from unittest.mock import AsyncMock, Mock

import pytest

from src.core.infra.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState
from src.models.database import Database
from src.services.bot.vfs_bot import VFSBot
from src.services.notification.notification import NotificationService


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
        "anti_detection": {"enabled": False},
    }

    # Create mocks
    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)

    # Create bot instance
    bot = VFSBot(config, db, notifier)

    # Verify circuit_breaker service exists
    assert bot.circuit_breaker is not None

    # Test concurrent error recording
    async def record_errors(count: int):
        """Record multiple errors concurrently."""
        for _ in range(count):
            await bot.circuit_breaker.record_failure()

    # Run concurrent error recordings
    await asyncio.gather(
        record_errors(5),
        record_errors(5),
        record_errors(5),
    )

    # Verify circuit breaker tracked the errors
    stats = bot.circuit_breaker.get_stats()
    assert stats["failure_count"] > 0


@pytest.mark.asyncio
async def test_circuit_breaker_async_signature():
    """Test that circuit breaker record_failure is async and returns None."""
    config = {
        "bot": {"check_interval": 30, "headless": True},
        "captcha": {"provider": "manual", "api_key": ""},
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "mission": "nld",
            "language": "tr",
        },
        "anti_detection": {"enabled": False},
    }

    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    bot = VFSBot(config, db, notifier)

    # Verify record_failure is a coroutine function
    assert asyncio.iscoroutinefunction(bot.circuit_breaker.record_failure)

    # Test that it can be awaited
    result = await bot.circuit_breaker.record_failure()
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
        "anti_detection": {"enabled": False},
    }

    db = Mock(spec=Database)
    notifier = Mock(spec=NotificationService)
    bot = VFSBot(config, db, notifier)

    # Record enough errors to trigger circuit breaker
    # Default MAX_CONSECUTIVE_ERRORS is typically 5
    for _ in range(10):
        await bot.circuit_breaker.record_failure()

    # Circuit breaker should be open
    is_available = await bot.circuit_breaker.can_execute()
    assert is_available is False


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


# Tests for CircuitBreaker with custom parameters (from services)


@pytest.mark.asyncio
async def test_circuit_breaker_service_initialization():
    """Test CircuitBreaker initializes in CLOSED state."""
    cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60.0, name="ServiceCB")

    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert await cb.can_execute() is True


@pytest.mark.asyncio
async def test_circuit_breaker_service_opens_on_consecutive_failures():
    """Test CircuitBreaker opens after consecutive failures."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60.0, name="ServiceCB")

    # Record failures
    await cb.record_failure()
    await cb.record_failure()
    assert await cb.can_execute() is True

    # Third failure should open circuit
    await cb.record_failure()
    assert await cb.can_execute() is False
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_service_resets_on_success():
    """Test CircuitBreaker resets consecutive errors on success."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60.0, name="ServiceCB")

    await cb.record_failure()
    await cb.record_failure()
    assert cb.failure_count == 2

    # Success should reset counter
    await cb.record_success()
    assert cb.failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_service_half_open_transition():
    """Test CircuitBreaker transitions to HALF_OPEN after timeout."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1.0, name="ServiceCB")

    # Open circuit
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Wait for reset timeout
    await asyncio.sleep(1.1)

    # Should transition to HALF_OPEN on next check
    is_available = await cb.can_execute()
    assert is_available is True
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_service_get_stats():
    """Test getting CircuitBreaker statistics."""
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60.0, name="ServiceCB")

    await cb.record_failure()
    await cb.record_failure()

    stats = cb.get_stats()

    assert isinstance(stats, dict)
    assert stats["state"] == CircuitState.CLOSED.value
    assert stats["failure_count"] == 2
    assert stats["failure_threshold"] == 3


@pytest.mark.asyncio
async def test_circuit_breaker_service_manual_reset():
    """Test manual reset of CircuitBreaker."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=60.0, name="ServiceCB")

    # Open circuit
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Manual reset
    await cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert await cb.can_execute() is True


@pytest.mark.asyncio
async def test_circuit_breaker_timeout_utc():
    """Test that circuit breaker timeout calculation uses UTC correctly."""
    import asyncio
    from datetime import datetime, timedelta, timezone

    cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1.0, name="TestUTCTimeout")

    # Open the circuit with a failure
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Verify failure time is timezone-aware
    assert cb._last_failure_time is not None
    assert cb._last_failure_time.tzinfo is not None

    # Should not be able to execute immediately
    assert await cb.can_execute() is False

    # Wait for timeout to pass
    await asyncio.sleep(1.1)

    # Should be able to attempt reset now
    assert await cb._should_attempt_reset() is True


@pytest.mark.asyncio
async def test_circuit_breaker_failure_time_utc():
    """Test that failure timestamps are stored in UTC."""
    from datetime import timezone

    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60.0, name="TestUTCFailure")

    # Record a failure
    await cb.record_failure()

    # Verify the last failure time is timezone-aware (UTC)
    assert cb._last_failure_time is not None
    assert cb._last_failure_time.tzinfo == timezone.utc


# ==============================================================================
# Batch Error Rate Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_batch_error_rate_threshold_constant_exists():
    """Test that BATCH_ERROR_RATE_THRESHOLD constant exists in CircuitBreaker config."""
    from src.constants import CircuitBreakerConfig

    # Verify constant exists
    assert hasattr(CircuitBreakerConfig, "BATCH_ERROR_RATE_THRESHOLD")

    # Verify it's a float
    assert isinstance(CircuitBreakerConfig.BATCH_ERROR_RATE_THRESHOLD, float)

    # Verify it's 0.5 (50%)
    assert CircuitBreakerConfig.BATCH_ERROR_RATE_THRESHOLD == 0.5


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Batch processing methods removed - test needs rewrite for current implementation"
)
async def test_batch_error_rate_zero_records_success():
    """Test that zero error rate records success."""
    from unittest.mock import MagicMock, patch

    # We'll mock the entire VFSBot init process
    with (
        patch("src.services.bot.vfs_bot.BotServiceFactory"),
        patch("src.services.bot.vfs_bot.BrowserManager"),
        patch("src.services.bot.vfs_bot.BookingWorkflow"),
    ):

        config = {
            "bot": {"check_interval": 30, "headless": True},
            "captcha": {"provider": "manual", "api_key": ""},
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tr",
                "mission": "nld",
                "language": "tr",
            },
            "anti_detection": {"enabled": False},
        }

        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)
        bot = VFSBot(config, db, notifier)

        # Mock circuit breaker methods
        bot.circuit_breaker.record_success = AsyncMock()
        bot.circuit_breaker.record_failure = AsyncMock()

        # Mock _record_circuit_breaker_trip
        bot._record_circuit_breaker_trip = AsyncMock()

        # Mock _send_alert_safe
        bot._send_alert_safe = AsyncMock()

        # Mock _process_user_with_semaphore to succeed
        async def mock_process_success(user):
            return {"success": True}

        bot._process_user_with_semaphore = mock_process_success

        # Create test users
        users = [{"id": i, "email": f"user{i}@test.com"} for i in range(10)]

        # Process batch (all should succeed)
        await bot._process_batch(users)

        # Verify record_success was called
        bot.circuit_breaker.record_success.assert_called_once()
        bot.circuit_breaker.record_failure.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Batch processing methods removed - test needs rewrite for current implementation"
)
async def test_batch_error_rate_below_threshold_records_success():
    """Test that error rate below 50% records success."""
    from unittest.mock import MagicMock, patch

    with (
        patch("src.services.bot.vfs_bot.BotServiceFactory"),
        patch("src.services.bot.vfs_bot.BrowserManager"),
        patch("src.services.bot.vfs_bot.BookingWorkflow"),
    ):

        config = {
            "bot": {"check_interval": 30, "headless": True},
            "captcha": {"provider": "manual", "api_key": ""},
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tr",
                "mission": "nld",
                "language": "tr",
            },
            "anti_detection": {"enabled": False},
        }

        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)
        bot = VFSBot(config, db, notifier)

        # Mock circuit breaker methods
        bot.circuit_breaker.record_success = AsyncMock()
        bot.circuit_breaker.record_failure = AsyncMock()

        # Mock _record_circuit_breaker_trip
        bot._record_circuit_breaker_trip = AsyncMock()

        # Mock _send_alert_safe
        bot._send_alert_safe = AsyncMock()

        # Track call count for mixed success/failure
        call_count = [0]

        async def mock_process_mixed(user):
            call_count[0] += 1
            # Fail 4 out of 10 (40% error rate, below 50% threshold)
            if call_count[0] <= 4:
                raise Exception("Test error")
            return {"success": True}

        bot._process_user_with_semaphore = mock_process_mixed

        # Create test users
        users = [{"id": i, "email": f"user{i}@test.com"} for i in range(10)]

        # Process batch (40% errors, below 50% threshold)
        await bot._process_batch(users)

        # Verify record_success was called (not record_failure)
        bot.circuit_breaker.record_success.assert_called_once()
        bot.circuit_breaker.record_failure.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Batch processing methods removed - test needs rewrite for current implementation"
)
async def test_batch_error_rate_above_threshold_records_failure():
    """Test that error rate at or above 50% records failure."""
    from unittest.mock import MagicMock, patch

    with (
        patch("src.services.bot.vfs_bot.BotServiceFactory"),
        patch("src.services.bot.vfs_bot.BrowserManager"),
        patch("src.services.bot.vfs_bot.BookingWorkflow"),
    ):

        config = {
            "bot": {"check_interval": 30, "headless": True},
            "captcha": {"provider": "manual", "api_key": ""},
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tr",
                "mission": "nld",
                "language": "tr",
            },
            "anti_detection": {"enabled": False},
        }

        db = MagicMock(spec=Database)
        notifier = MagicMock(spec=NotificationService)
        bot = VFSBot(config, db, notifier)

        # Mock circuit breaker methods
        bot.circuit_breaker.record_success = AsyncMock()
        bot.circuit_breaker.record_failure = AsyncMock()

        # Mock _record_circuit_breaker_trip
        bot._record_circuit_breaker_trip = AsyncMock()

        # Mock _send_alert_safe
        bot._send_alert_safe = AsyncMock()

        # Track call count for mixed success/failure
        call_count = [0]

        async def mock_process_high_errors(user):
            call_count[0] += 1
            # Fail 6 out of 10 (60% error rate, above 50% threshold)
            if call_count[0] <= 6:
                raise Exception("Test error")
            return {"success": True}

        bot._process_user_with_semaphore = mock_process_high_errors

        # Create test users
        users = [{"id": i, "email": f"user{i}@test.com"} for i in range(10)]

        # Process batch (60% errors, above 50% threshold)
        await bot._process_batch(users)

        # Verify record_failure was called (not record_success)
        bot.circuit_breaker.record_failure.assert_called_once()
        bot.circuit_breaker.record_success.assert_not_called()
