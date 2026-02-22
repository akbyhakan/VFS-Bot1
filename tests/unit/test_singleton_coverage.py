"""Tests for utils/singleton module - thread-safe singleton registry."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from src.utils.singleton import (
    get_instance,
    get_or_create_async,
    get_or_create_sync,
    list_instances,
    reset,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset singleton registry before and after every test."""
    reset()
    yield
    reset()


class TestGetOrCreateSync:
    """Tests for get_or_create_sync."""

    def test_creates_new_instance(self):
        """Factory is called when key does not exist."""
        factory = MagicMock(return_value="instance_value")

        result = get_or_create_sync("my_key", factory)

        assert result == "instance_value"
        factory.assert_called_once()

    def test_returns_existing_instance(self):
        """Factory is called only once for the same key."""
        factory = MagicMock(return_value=object())

        first = get_or_create_sync("same_key", factory)
        second = get_or_create_sync("same_key", factory)

        assert first is second
        factory.assert_called_once()

    def test_different_keys_create_different_instances(self):
        """Different keys produce different instances."""
        factory_a = MagicMock(return_value="a")
        factory_b = MagicMock(return_value="b")

        a = get_or_create_sync("key_a", factory_a)
        b = get_or_create_sync("key_b", factory_b)

        assert a == "a"
        assert b == "b"
        assert a is not b

    def test_factory_called_with_args(self):
        """Positional args are forwarded to factory."""

        def factory(x, y):
            return x + y

        result = get_or_create_sync("sum_key", factory, 3, 4)

        assert result == 7

    def test_factory_called_with_kwargs(self):
        """Keyword args are forwarded to factory."""

        def factory(*, name, value):
            return {"name": name, "value": value}

        result = get_or_create_sync("dict_key", factory, name="test", value=42)

        assert result == {"name": "test", "value": 42}

    def test_thread_safety_same_instance(self):
        """Multiple threads get the same instance."""
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return object()

        results = []
        errors = []

        def worker():
            try:
                inst = get_or_create_sync("thread_key", factory)
                results.append(inst)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10
        assert all(r is results[0] for r in results)
        assert call_count == 1


class TestGetOrCreateAsync:
    """Tests for get_or_create_async."""

    @pytest.mark.asyncio
    async def test_creates_instance_with_async_factory(self):
        """Async factory is awaited and result stored."""

        async def async_factory():
            return "async_result"

        result = await get_or_create_async("async_key", async_factory)

        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_creates_instance_with_sync_factory(self):
        """Sync factory is called directly (not awaited)."""

        def sync_factory():
            return "sync_result"

        result = await get_or_create_async("sync_async_key", sync_factory)

        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_returns_existing_instance(self):
        """Second call returns same object without calling factory again."""
        call_count = 0

        async def async_factory():
            nonlocal call_count
            call_count += 1
            return object()

        first = await get_or_create_async("async_existing", async_factory)
        second = await get_or_create_async("async_existing", async_factory)

        assert first is second
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_factory_with_args(self):
        """Args are forwarded to async factory."""

        async def factory(x, y):
            return x * y

        result = await get_or_create_async("async_args_key", factory, 3, 7)

        assert result == 21

    @pytest.mark.asyncio
    async def test_async_factory_with_kwargs(self):
        """Kwargs are forwarded to async factory."""

        async def factory(*, msg):
            return msg.upper()

        result = await get_or_create_async("async_kwargs_key", factory, msg="hello")

        assert result == "HELLO"


class TestReset:
    """Tests for reset function."""

    def test_reset_specific_key_removes_it(self):
        """reset(key) removes only that key."""
        get_or_create_sync("key1", lambda: "v1")
        get_or_create_sync("key2", lambda: "v2")

        reset("key1")

        assert get_instance("key1") is None
        assert get_instance("key2") == "v2"

    def test_reset_all_clears_everything(self):
        """reset() with no args clears all instances."""
        get_or_create_sync("k1", lambda: "v1")
        get_or_create_sync("k2", lambda: "v2")

        reset()

        assert get_instance("k1") is None
        assert get_instance("k2") is None
        assert list_instances() == {}

    def test_reset_non_existent_key_is_no_op(self):
        """reset on a key that doesn't exist does not raise."""
        reset("nonexistent_key")  # should not raise

    def test_reset_allows_factory_to_be_called_again(self):
        """After reset, factory is called again on next get_or_create_sync."""
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return object()

        get_or_create_sync("reset_test", factory)
        reset("reset_test")
        get_or_create_sync("reset_test", factory)

        assert call_count == 2


class TestGetInstance:
    """Tests for get_instance function."""

    def test_returns_none_for_nonexistent_key(self):
        """get_instance returns None when key hasn't been created."""
        result = get_instance("does_not_exist")
        assert result is None

    def test_returns_instance_for_existing_key(self):
        """get_instance returns the created instance."""
        expected = {"key": "value"}
        get_or_create_sync("existing_key", lambda: expected)

        result = get_instance("existing_key")

        assert result is expected

    def test_does_not_create_new_instance(self):
        """get_instance never triggers factory."""
        factory = MagicMock(return_value="created")

        result = get_instance("never_created_key")

        assert result is None
        factory.assert_not_called()


class TestListInstances:
    """Tests for list_instances function."""

    def test_empty_when_no_singletons(self):
        """list_instances returns empty dict when nothing created."""
        result = list_instances()
        assert result == {}

    def test_returns_all_created_instances(self):
        """list_instances includes all created singletons."""
        get_or_create_sync("list_k1", lambda: "v1")
        get_or_create_sync("list_k2", lambda: "v2")

        result = list_instances()

        assert "list_k1" in result
        assert "list_k2" in result
        assert result["list_k1"] == "v1"
        assert result["list_k2"] == "v2"

    def test_returns_copy_not_reference(self):
        """Mutating the returned dict does not affect the registry."""
        get_or_create_sync("copy_key", lambda: "original")

        instances = list_instances()
        instances["copy_key"] = "mutated"

        assert get_instance("copy_key") == "original"
