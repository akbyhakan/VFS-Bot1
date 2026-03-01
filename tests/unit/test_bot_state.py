"""Unit tests for ThreadSafeBotState."""

import threading
from collections import deque

import pytest

from web.state.bot_state import ThreadSafeBotState


class TestThreadSafeBotStateGettersSetters:
    """Tests for getters and setters."""

    def test_default_values(self):
        """Test default values after initialization."""
        state = ThreadSafeBotState()
        assert state.get_running() is False
        assert state.get_status() == "stopped"
        assert state.get_last_check() is None
        assert state.get_slots_found() == 0
        assert state.get_appointments_booked() == 0
        assert state.get_active_users() == 0

    def test_set_running(self):
        """Test set_running / get_running."""
        state = ThreadSafeBotState()
        state.set_running(True)
        assert state.get_running() is True
        state.set_running(False)
        assert state.get_running() is False

    def test_set_status(self):
        """Test set_status / get_status."""
        state = ThreadSafeBotState()
        state.set_status("running")
        assert state.get_status() == "running"

    def test_set_last_check(self):
        """Test set_last_check / get_last_check."""
        state = ThreadSafeBotState()
        state.set_last_check("2024-01-01T00:00:00")
        assert state.get_last_check() == "2024-01-01T00:00:00"
        state.set_last_check(None)
        assert state.get_last_check() is None

    def test_set_slots_found(self):
        """Test set_slots_found / get_slots_found."""
        state = ThreadSafeBotState()
        state.set_slots_found(42)
        assert state.get_slots_found() == 42

    def test_set_appointments_booked(self):
        """Test set_appointments_booked / get_appointments_booked."""
        state = ThreadSafeBotState()
        state.set_appointments_booked(7)
        assert state.get_appointments_booked() == 7

    def test_set_active_users(self):
        """Test set_active_users / get_active_users."""
        state = ThreadSafeBotState()
        state.set_active_users(15)
        assert state.get_active_users() == 15

    def test_read_only_default_false(self):
        """Test read_only defaults to False."""
        state = ThreadSafeBotState()
        assert state.get_read_only() is False

    def test_set_read_only(self):
        """Test set_read_only / get_read_only."""
        state = ThreadSafeBotState()
        state.set_read_only(True)
        assert state.get_read_only() is True
        state.set_read_only(False)
        assert state.get_read_only() is False


class TestThreadSafeBotStateAtomicOps:
    """Tests for atomic increment operations."""

    def test_increment_slots_found_default(self):
        """Test increment_slots_found with default count."""
        state = ThreadSafeBotState()
        state.increment_slots_found()
        assert state.get_slots_found() == 1

    def test_increment_slots_found_custom(self):
        """Test increment_slots_found with custom count."""
        state = ThreadSafeBotState()
        state.increment_slots_found(5)
        assert state.get_slots_found() == 5

    def test_increment_appointments_booked_default(self):
        """Test increment_appointments_booked with default count."""
        state = ThreadSafeBotState()
        state.increment_appointments_booked()
        assert state.get_appointments_booked() == 1

    def test_increment_appointments_booked_custom(self):
        """Test increment_appointments_booked with custom count."""
        state = ThreadSafeBotState()
        state.increment_appointments_booked(3)
        assert state.get_appointments_booked() == 3


class TestThreadSafeBotStateLogs:
    """Tests for log operations."""

    def test_append_log(self):
        """Test append_log adds to logs."""
        state = ThreadSafeBotState()
        state.append_log("First log")
        logs = state.get_logs_list()
        assert logs[0]["message"] == "First log"
        assert logs[0]["level"] == "INFO"
        assert "timestamp" in logs[0]

    def test_get_logs_list_returns_copy(self):
        """Test get_logs_list returns a list copy."""
        state = ThreadSafeBotState()
        state.append_log("msg1")
        logs = state.get_logs_list()
        assert isinstance(logs, list)
        logs.append({"message": "injected", "level": "INFO", "timestamp": "2024-01-01 00:00:00"})
        # Should not affect internal state
        assert not any(l["message"] == "injected" for l in state.get_logs_list())

    def test_get_logs_returns_deque(self):
        """Test get_logs returns the deque reference."""
        state = ThreadSafeBotState()
        state.append_log("msg")
        logs_deque = state.get_logs()
        assert isinstance(logs_deque, deque)

    def test_logs_maxlen_enforced(self):
        """Test that deque maxlen=500 is enforced."""
        state = ThreadSafeBotState()
        for i in range(600):
            state.append_log(f"Log message {i}")
        logs = state.get_logs_list()
        assert len(logs) == 500
        # Most recent entries should be kept
        assert any(l["message"] == "Log message 599" for l in logs)
        # Oldest entries should be dropped
        assert not any(l["message"] == "Log message 0" for l in logs)


class TestThreadSafeBotStateToDict:
    """Tests for dictionary conversion."""

    def test_to_dict_contains_all_keys(self):
        """Test to_dict returns all expected keys."""
        state = ThreadSafeBotState()
        d = state.to_dict()
        assert "running" in d
        assert "status" in d
        assert "last_check" in d
        assert "slots_found" in d
        assert "appointments_booked" in d
        assert "active_users" in d
        assert "logs" in d

    def test_to_dict_reflects_state(self):
        """Test to_dict reflects current state."""
        state = ThreadSafeBotState()
        state.set_running(True)
        state.set_status("running")
        state.set_slots_found(10)
        state.append_log("test log")

        d = state.to_dict()
        assert d["running"] is True
        assert d["status"] == "running"
        assert d["slots_found"] == 10
        assert any(entry["message"] == "test log" for entry in d["logs"])

    @pytest.mark.asyncio
    async def test_async_to_dict(self):
        """Test async_to_dict returns same data as to_dict."""
        state = ThreadSafeBotState()
        state.set_running(True)
        state.set_slots_found(5)

        sync_dict = state.to_dict()
        async_dict = await state.async_to_dict()

        assert sync_dict["running"] == async_dict["running"]
        assert sync_dict["slots_found"] == async_dict["slots_found"]


class TestThreadSafeBotStateThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_increments(self):
        """Test that concurrent increments are thread-safe."""
        state = ThreadSafeBotState()
        num_threads = 10
        increments_per_thread = 100

        def increment():
            for _ in range(increments_per_thread):
                state.increment_slots_found()

        threads = [threading.Thread(target=increment) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert state.get_slots_found() == num_threads * increments_per_thread
