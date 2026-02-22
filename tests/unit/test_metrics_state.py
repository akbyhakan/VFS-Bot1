"""Unit tests for ThreadSafeMetrics."""

import threading

import pytest

from web.state.metrics import ThreadSafeMetrics


class TestThreadSafeMetricsBasicOps:
    """Tests for basic increment/get/set operations."""

    def test_default_keys_present(self):
        """Test that default metric keys are present after init."""
        metrics = ThreadSafeMetrics()
        assert metrics.get("requests_total") == 0
        assert metrics.get("slots_found") == 0
        assert metrics.get("appointments_booked") == 0

    def test_increment_existing_key(self):
        """Test incrementing an existing metric key."""
        metrics = ThreadSafeMetrics()
        metrics.increment("requests_total")
        assert metrics.get("requests_total") == 1

    def test_increment_by_custom_value(self):
        """Test incrementing by a custom value."""
        metrics = ThreadSafeMetrics()
        metrics.increment("slots_found", 5)
        assert metrics.get("slots_found") == 5

    def test_increment_nonexistent_key(self):
        """Test that incrementing a non-existent key does nothing."""
        metrics = ThreadSafeMetrics()
        metrics.increment("nonexistent_key")
        assert metrics.get("nonexistent_key") is None

    def test_get_with_default(self):
        """Test get returns default for missing key."""
        metrics = ThreadSafeMetrics()
        result = metrics.get("missing_key", default=42)
        assert result == 42

    def test_set_existing_key(self):
        """Test setting an existing metric key."""
        metrics = ThreadSafeMetrics()
        metrics.set("requests_total", 100)
        assert metrics.get("requests_total") == 100

    def test_set_new_key(self):
        """Test setting a new metric key."""
        metrics = ThreadSafeMetrics()
        metrics.set("custom_metric", "value")
        assert metrics.get("custom_metric") == "value"


class TestThreadSafeMetricsErrors:
    """Tests for error tracking."""

    def test_add_error_new_type(self):
        """Test adding a new error type."""
        metrics = ThreadSafeMetrics()
        metrics.add_error("ConnectionError")
        errors = metrics.get("errors")
        assert errors["ConnectionError"] == 1

    def test_add_error_existing_type_increments(self):
        """Test that adding an existing error type increments count."""
        metrics = ThreadSafeMetrics()
        metrics.add_error("TimeoutError")
        metrics.add_error("TimeoutError")
        errors = metrics.get("errors")
        assert errors["TimeoutError"] == 2

    def test_add_multiple_error_types(self):
        """Test adding multiple different error types."""
        metrics = ThreadSafeMetrics()
        metrics.add_error("TypeError")
        metrics.add_error("ValueError")
        errors = metrics.get("errors")
        assert errors["TypeError"] == 1
        assert errors["ValueError"] == 1


class TestThreadSafeMetricsToDict:
    """Tests for to_dict and deep copy validation."""

    def test_to_dict_returns_all_keys(self):
        """Test that to_dict includes all default keys."""
        metrics = ThreadSafeMetrics()
        d = metrics.to_dict()
        assert "requests_total" in d
        assert "slots_found" in d
        assert "errors" in d
        assert "start_time" in d

    def test_to_dict_deep_copy(self):
        """Test that to_dict returns a deep copy (mutations don't affect internal state)."""
        metrics = ThreadSafeMetrics()
        metrics.add_error("SomeError")

        d = metrics.to_dict()
        d["errors"]["injected"] = 999
        d["requests_total"] = 9999

        # Internal state should not be affected
        assert metrics.get("requests_total") == 0
        errors = metrics.get("errors")
        assert "injected" not in errors

    def test_to_dict_reflects_mutations(self):
        """Test that to_dict reflects the current state."""
        metrics = ThreadSafeMetrics()
        metrics.increment("requests_total", 3)
        metrics.set("slots_found", 7)

        d = metrics.to_dict()
        assert d["requests_total"] == 3
        assert d["slots_found"] == 7


class TestThreadSafeMetricsDictAccess:
    """Tests for dictionary-style access."""

    def test_setitem(self):
        """Test dictionary-style item assignment."""
        metrics = ThreadSafeMetrics()
        metrics["requests_total"] = 42
        assert metrics.get("requests_total") == 42

    def test_getitem(self):
        """Test dictionary-style item access."""
        metrics = ThreadSafeMetrics()
        metrics.set("slots_found", 10)
        assert metrics["slots_found"] == 10

    def test_contains(self):
        """Test 'in' operator for key existence."""
        metrics = ThreadSafeMetrics()
        assert "requests_total" in metrics
        assert "nonexistent_key" not in metrics


class TestThreadSafeMetricsAsync:
    """Tests for async methods."""

    @pytest.mark.asyncio
    async def test_async_increment(self):
        """Test async_increment updates metric."""
        metrics = ThreadSafeMetrics()
        await metrics.async_increment("requests_total", 3)
        assert metrics.get("requests_total") == 3

    @pytest.mark.asyncio
    async def test_async_get(self):
        """Test async_get retrieves metric."""
        metrics = ThreadSafeMetrics()
        metrics.set("slots_found", 5)
        result = await metrics.async_get("slots_found")
        assert result == 5

    @pytest.mark.asyncio
    async def test_async_set(self):
        """Test async_set updates metric."""
        metrics = ThreadSafeMetrics()
        await metrics.async_set("requests_total", 99)
        assert metrics.get("requests_total") == 99

    @pytest.mark.asyncio
    async def test_async_to_dict(self):
        """Test async_to_dict returns deep copy."""
        metrics = ThreadSafeMetrics()
        metrics.increment("requests_total", 2)

        d = await metrics.async_to_dict()
        d["requests_total"] = 9999

        # Internal state should not change
        assert metrics.get("requests_total") == 2


class TestThreadSafeMetricsThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_increments(self):
        """Test that concurrent increments are thread-safe."""
        metrics = ThreadSafeMetrics()
        num_threads = 10
        increments_per_thread = 100

        def increment():
            for _ in range(increments_per_thread):
                metrics.increment("requests_total")

        threads = [threading.Thread(target=increment) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert metrics.get("requests_total") == num_threads * increments_per_thread
