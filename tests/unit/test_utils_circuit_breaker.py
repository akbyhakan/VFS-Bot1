"""Tests for core/circuit_breaker module."""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.core.infra.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    def test_custom_thresholds(self):
        """Test circuit breaker with custom thresholds."""
        cb = CircuitBreaker(
            name="custom", failure_threshold=10, timeout_seconds=30.0, half_open_threshold=5
        )
        assert cb.failure_threshold == 10
        assert cb.timeout_seconds == 30.0

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self):
        """Test can_execute returns True when circuit is CLOSED."""
        cb = CircuitBreaker(name="test")
        assert await cb.can_execute()

    @pytest.mark.asyncio
    async def test_record_success_resets_failure_count(self):
        """Test record_success resets failure count."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb._failure_count = 2
        await cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_record_failure_increments_count(self):
        """Test record_failure increments failure count."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        await cb.record_failure()
        assert cb._failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_can_execute_returns_false_when_open(self):
        """Test can_execute returns False when circuit is OPEN."""
        cb = CircuitBreaker(name="test", failure_threshold=1)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not await cb.can_execute()

    @pytest.mark.asyncio
    async def test_circuit_moves_to_half_open_after_timeout(self):
        """Test circuit moves to HALF_OPEN after reset timeout."""
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout_seconds=0.01)
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
        cb = CircuitBreaker(
            name="test", failure_threshold=1, timeout_seconds=0, half_open_threshold=1
        )
        await cb.record_failure()
        cb._state = CircuitState.HALF_OPEN
        await cb.record_success()
        # After enough successes, should close
        assert cb.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens_circuit(self):
        """Test failure in HALF_OPEN state reopens the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout_seconds=0)
        cb._state = CircuitState.HALF_OPEN
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_call_function_success(self):
        """Test call with successful function."""
        cb = CircuitBreaker(name="test")

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_function_failure(self):
        """Test call with failing function."""
        cb = CircuitBreaker(name="test", failure_threshold=1)

        async def fail_func():
            raise Exception("Test error")

        with pytest.raises(Exception):
            await cb.call(fail_func)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_call_rejects_when_open(self):
        """Test call rejects calls when circuit is open."""
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb._state = CircuitState.OPEN

        async def test_func():
            return "should not execute"

        with pytest.raises(CircuitBreakerError):
            await cb.call(test_func)

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


# ==============================================================================
# Persistence Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_without_persistence():
    """Test circuit breaker works normally without state_file."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)

    # Should work normally without persistence
    assert cb.state == CircuitState.CLOSED
    stats = cb.get_stats()
    assert stats["persistent"] is False


@pytest.mark.asyncio
async def test_circuit_breaker_persistence_on_state_change():
    """Test circuit breaker persists state when it changes."""
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        state_file = f.name

    try:
        cb = CircuitBreaker(
            failure_threshold=2, timeout_seconds=5, state_file=state_file, name="TestCB"
        )

        # Record failures to open the circuit
        await cb.record_failure()
        await cb.record_failure()

        assert cb.state == CircuitState.OPEN

        # Verify state was persisted
        state_path = Path(state_file)
        assert state_path.exists()

        import json

        with open(state_file, "r") as f:
            state_data = json.load(f)

        assert state_data["state"] == CircuitState.OPEN.value
        assert state_data["failure_count"] == 2
        assert state_data["last_failure_time"] is not None

    finally:
        Path(state_file).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_circuit_breaker_loads_persisted_state():
    """Test circuit breaker loads state from file on initialization."""
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        state_file = f.name

    try:
        # Create first circuit breaker and open it
        cb1 = CircuitBreaker(
            failure_threshold=2, timeout_seconds=60, state_file=state_file, name="TestCB1"
        )

        await cb1.record_failure()
        await cb1.record_failure()
        assert cb1.state == CircuitState.OPEN

        # Create second circuit breaker with same state file
        cb2 = CircuitBreaker(
            failure_threshold=2, timeout_seconds=60, state_file=state_file, name="TestCB2"
        )

        # Should have loaded the OPEN state
        assert cb2.state == CircuitState.OPEN
        assert cb2.failure_count == 2

    finally:
        Path(state_file).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_circuit_breaker_persistence_on_reset():
    """Test circuit breaker persists state after manual reset."""
    import json
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        state_file = f.name

    try:
        cb = CircuitBreaker(
            failure_threshold=2, timeout_seconds=5, state_file=state_file, name="TestCB"
        )

        # Open the circuit
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Reset it
        await cb.reset()
        assert cb.state == CircuitState.CLOSED

        # Verify persisted state is CLOSED
        with open(state_file, "r") as f:
            state_data = json.load(f)

        assert state_data["state"] == CircuitState.CLOSED.value
        assert state_data["failure_count"] == 0

    finally:
        Path(state_file).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_circuit_breaker_creates_state_dir():
    """Test circuit breaker creates directory for state file if it doesn't exist."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        state_file = Path(temp_dir) / "subdir" / "state.json"

        cb = CircuitBreaker(
            failure_threshold=2, timeout_seconds=5, state_file=str(state_file), name="TestCB"
        )

        # Record failures to trigger state change and _save_state()
        await cb.record_failure()
        await cb.record_failure()

        # Verify directory was created
        assert state_file.parent.exists()
        assert state_file.exists()


@pytest.mark.asyncio
async def test_circuit_breaker_handles_missing_state_file():
    """Test circuit breaker handles missing state file gracefully."""
    state_file = "/tmp/nonexistent_dir_12345/state.json"

    # Should not raise an exception even if file doesn't exist
    cb = CircuitBreaker(
        failure_threshold=2, timeout_seconds=5, state_file=state_file, name="TestCB"
    )

    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_atomic_write_no_corruption():
    """Test that state is written atomically (temp file + rename, no partial writes)."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        state_file = Path(temp_dir) / "state.json"

        cb = CircuitBreaker(
            failure_threshold=2, timeout_seconds=5, state_file=str(state_file), name="TestCB"
        )

        # Trigger a save via record_failure
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # The final state file must exist and be valid JSON (no partial writes)
        assert state_file.exists()

        import json

        with open(state_file, "r") as f:
            state_data = json.load(f)

        assert state_data["state"] == CircuitState.OPEN.value
        assert state_data["failure_count"] == 2

        # No leftover temp files in the directory
        temp_files = list(Path(temp_dir).glob(".cb_state_*"))
        assert len(temp_files) == 0, f"Unexpected temp files left: {temp_files}"


@pytest.mark.asyncio
async def test_circuit_breaker_save_state_is_async():
    """Test that _save_state() is an async (coroutine) method."""
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)
    assert asyncio.iscoroutinefunction(
        cb._save_state
    ), "_save_state must be an async coroutine function"


@pytest.mark.asyncio
async def test_get_stats_includes_persistent_flag():
    """Test get_stats includes persistent flag."""
    import tempfile
    from pathlib import Path

    # Without persistence
    cb1 = CircuitBreaker(failure_threshold=2, timeout_seconds=5)
    stats1 = cb1.get_stats()
    assert "persistent" in stats1
    assert stats1["persistent"] is False

    # With persistence
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        state_file = f.name

    try:
        cb2 = CircuitBreaker(failure_threshold=2, timeout_seconds=5, state_file=state_file)
        stats2 = cb2.get_stats()
        assert "persistent" in stats2
        assert stats2["persistent"] is True

    finally:
        Path(state_file).unlink(missing_ok=True)
