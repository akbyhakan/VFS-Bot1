"""Tests for utils/idempotency module."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.utils.idempotency import IdempotencyRecord, IdempotencyStore


class TestIdempotencyRecord:
    """Tests for IdempotencyRecord dataclass."""

    def test_record_creation(self):
        """Test creating an IdempotencyRecord."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=1)
        record = IdempotencyRecord(
            key="test_key", result="test_result", created_at=now, expires_at=expires
        )
        assert record.key == "test_key"
        assert record.result == "test_result"
        assert record.created_at == now
        assert record.expires_at == expires


class TestIdempotencyStore:
    """Tests for IdempotencyStore."""

    def test_initialization(self):
        """Test IdempotencyStore initialization."""
        store = IdempotencyStore(ttl_seconds=3600)
        assert store._ttl == 3600
        assert isinstance(store._store, dict)
        assert len(store._store) == 0

    def test_initialization_default_ttl(self):
        """Test IdempotencyStore with default TTL."""
        store = IdempotencyStore()
        assert store._ttl == 86400  # 24 hours

    def test_generate_key(self):
        """Test key generation from operation and params."""
        store = IdempotencyStore()
        key1 = store._generate_key("test_op", {"param1": "value1"})
        key2 = store._generate_key("test_op", {"param1": "value1"})
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 64  # SHA256 hex digest

    def test_generate_key_different_params(self):
        """Test that different params generate different keys."""
        store = IdempotencyStore()
        key1 = store._generate_key("test_op", {"param1": "value1"})
        key2 = store._generate_key("test_op", {"param1": "value2"})
        assert key1 != key2

    def test_generate_key_param_order(self):
        """Test that param order doesn't affect key."""
        store = IdempotencyStore()
        key1 = store._generate_key("test_op", {"a": 1, "b": 2})
        key2 = store._generate_key("test_op", {"b": 2, "a": 1})
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns None."""
        store = IdempotencyStore()
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test setting and getting a value."""
        store = IdempotencyStore()
        key = "test_key"
        value = {"result": "success"}
        await store.set(key, value)
        result = await store.get(key)
        assert result == value

    @pytest.mark.asyncio
    async def test_get_expired_key(self):
        """Test getting expired key returns None."""
        store = IdempotencyStore(ttl_seconds=-1)  # Immediate expiry
        key = "test_key"
        await store.set(key, "value")
        # Wait a bit to ensure it expires
        await asyncio.sleep(0.01)
        result = await store.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test that cleanup removes expired keys."""
        store = IdempotencyStore(ttl_seconds=0)
        key = "test_key"
        await store.set(key, "value")
        await asyncio.sleep(0.1)
        # Access it which should trigger cleanup
        await store.get(key)
        # Key should be removed from store
        assert key not in store._store

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to store."""
        store = IdempotencyStore()
        key = "concurrent_key"

        async def writer():
            await store.set(key, "value")

        async def reader():
            return await store.get(key)

        # Run multiple concurrent operations
        await asyncio.gather(writer(), writer(), reader(), reader())

    @pytest.mark.asyncio
    async def test_multiple_keys(self):
        """Test storing multiple keys."""
        store = IdempotencyStore()
        await store.set("key1", "value1")
        await store.set("key2", "value2")
        await store.set("key3", "value3")

        assert await store.get("key1") == "value1"
        assert await store.get("key2") == "value2"
        assert await store.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_overwrite_key(self):
        """Test overwriting an existing key."""
        store = IdempotencyStore()
        key = "test_key"
        await store.set(key, "value1")
        await store.set(key, "value2")
        assert await store.get(key) == "value2"

    def test_generate_key_with_complex_params(self):
        """Test key generation with complex parameters."""
        store = IdempotencyStore()
        params = {"list": [1, 2, 3], "dict": {"nested": "value"}, "int": 42}
        key = store._generate_key("complex_op", params)
        assert isinstance(key, str)
        assert len(key) == 64
