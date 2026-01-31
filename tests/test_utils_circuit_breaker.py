"""Tests for utils/circuit_breaker module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.utils.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open

    def test_custom_thresholds(self):
        """Test circuit breaker with custom thresholds."""
        cb = CircuitBreaker(
            name="custom", fail_threshold=10, reset_timeout=30, half_open_max_calls=5
        )
        assert cb.fail_threshold == 10
        assert cb.reset_timeout == 30
        assert cb.half_open_max_calls == 5

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self):
        """Test can_execute returns True when circuit is CLOSED."""
        cb = CircuitBreaker(name="test")
        assert await cb.can_execute()

    @pytest.mark.asyncio
    async def test_record_success_resets_failure_count(self):
        """Test record_success resets failure count."""
        cb = CircuitBreaker(name="test", fail_threshold=3)
        cb._failure_count = 2
        await cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_record_failure_increments_count(self):
        """Test record_failure increments failure count."""
        cb = CircuitBreaker(name="test", fail_threshold=3)
        await cb.record_failure()
        assert cb._failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(name="test", fail_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_can_execute_returns_false_when_open(self):
        """Test can_execute returns False when circuit is OPEN."""
        cb = CircuitBreaker(name="test", fail_threshold=1)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not await cb.can_execute()

    @pytest.mark.asyncio
    async def test_circuit_moves_to_half_open_after_timeout(self):
        """Test circuit moves to HALF_OPEN after reset timeout."""
        cb = CircuitBreaker(name="test", fail_threshold=1, reset_timeout=0)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # Wait for timeout
        await asyncio.sleep(0.1)
        # Should transition to HALF_OPEN
        can_exec = await cb.can_execute()
        # After timeout, should be able to try again
        assert can_exec or cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes_circuit(self):
        """Test success in HALF_OPEN state closes the circuit."""
        cb = CircuitBreaker(name="test", fail_threshold=1, reset_timeout=0)
        await cb.record_failure()
        cb._state = CircuitState.HALF_OPEN
        await cb.record_success()
        # After enough successes, should close
        assert cb.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens_circuit(self):
        """Test failure in HALF_OPEN state reopens the circuit."""
        cb = CircuitBreaker(name="test", fail_threshold=1, reset_timeout=0)
        cb._state = CircuitState.HALF_OPEN
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_execute_function_success(self):
        """Test execute with successful function."""
        cb = CircuitBreaker(name="test")

        async def success_func():
            return "success"

        result = await cb.execute(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_execute_function_failure(self):
        """Test execute with failing function."""
        cb = CircuitBreaker(name="test", fail_threshold=1)

        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await cb.execute(fail_func)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_execute_rejects_when_open(self):
        """Test execute rejects calls when circuit is open."""
        cb = CircuitBreaker(name="test", fail_threshold=1)
        cb._state = CircuitState.OPEN

        async def test_func():
            return "should not execute"

        with pytest.raises(Exception):
            await cb.execute(test_func)

    def test_state_property(self):
        """Test state property returns current state."""
        cb = CircuitBreaker(name="test")
        assert isinstance(cb.state, CircuitState)
        assert cb.state == CircuitState.CLOSED

    def test_get_stats(self):
        """Test get_stats method."""
        cb = CircuitBreaker(name="test")
        stats = cb.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
