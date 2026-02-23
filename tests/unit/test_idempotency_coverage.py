"""Coverage tests for src/utils/idempotency.py."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import src.utils.idempotency as idempotency_module
from src.utils.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyBackend,
    RedisIdempotencyBackend,
    get_idempotency_store,
)


@pytest.fixture(autouse=True)
def reset_global_store(monkeypatch):
    monkeypatch.setattr(idempotency_module, "_idempotency_store", None)
    yield
    monkeypatch.setattr(idempotency_module, "_idempotency_store", None)


# ── InMemoryIdempotencyBackend ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_in_memory_get_hit():
    backend = InMemoryIdempotencyBackend()
    await backend.set("k1", {"data": "value"}, ttl_seconds=60)
    result = await backend.get("k1")
    assert result == {"data": "value"}


@pytest.mark.asyncio
async def test_in_memory_get_miss():
    backend = InMemoryIdempotencyBackend()
    result = await backend.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_in_memory_get_expired():
    backend = InMemoryIdempotencyBackend()
    await backend.set("expired", "val", ttl_seconds=1)
    # Manually set the record as expired
    from src.utils.idempotency import IdempotencyRecord

    backend._store["expired"] = IdempotencyRecord(
        key="expired",
        result="val",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=60),
    )
    result = await backend.get("expired")
    assert result is None
    assert "expired" not in backend._store


@pytest.mark.asyncio
async def test_in_memory_cleanup_expired():
    backend = InMemoryIdempotencyBackend()
    from src.utils.idempotency import IdempotencyRecord

    backend._store["old"] = IdempotencyRecord(
        key="old",
        result="x",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    backend._store["fresh"] = IdempotencyRecord(
        key="fresh",
        result="y",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    removed = await backend.cleanup_expired()
    assert removed == 1
    assert "old" not in backend._store
    assert "fresh" in backend._store


@pytest.mark.asyncio
async def test_in_memory_cleanup_no_expired():
    backend = InMemoryIdempotencyBackend()
    removed = await backend.cleanup_expired()
    assert removed == 0


def test_in_memory_is_not_distributed():
    backend = InMemoryIdempotencyBackend()
    assert backend.is_distributed is False


# ── RedisIdempotencyBackend ───────────────────────────────────────────────────


def test_redis_backend_init():
    mock_redis = MagicMock()
    backend = RedisIdempotencyBackend(mock_redis)
    assert backend._redis is mock_redis


@pytest.mark.asyncio
async def test_redis_backend_get_hit():
    import json

    mock_redis = MagicMock()
    mock_redis.get = MagicMock(return_value=json.dumps({"result": "value"}))
    backend = RedisIdempotencyBackend(mock_redis)

    result = await backend.get("mykey")
    assert result == {"result": "value"}


@pytest.mark.asyncio
async def test_redis_backend_get_miss():
    mock_redis = MagicMock()
    mock_redis.get = MagicMock(return_value=None)
    backend = RedisIdempotencyBackend(mock_redis)

    result = await backend.get("missing")
    assert result is None


@pytest.mark.asyncio
async def test_redis_backend_get_invalid_json():
    mock_redis = MagicMock()
    mock_redis.get = MagicMock(return_value="not-valid-json{{{")
    backend = RedisIdempotencyBackend(mock_redis)

    result = await backend.get("bad")
    assert result is None


@pytest.mark.asyncio
async def test_redis_backend_set():
    mock_redis = MagicMock()
    mock_redis.setex = MagicMock()
    backend = RedisIdempotencyBackend(mock_redis)

    await backend.set("k", {"val": 1}, ttl_seconds=300)
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args[0]
    assert call_args[0] == "idempotency:k"
    assert call_args[1] == 300


@pytest.mark.asyncio
async def test_redis_backend_cleanup_returns_zero():
    mock_redis = MagicMock()
    backend = RedisIdempotencyBackend(mock_redis)
    removed = await backend.cleanup_expired()
    assert removed == 0


def test_redis_backend_is_distributed():
    mock_redis = MagicMock()
    backend = RedisIdempotencyBackend(mock_redis)
    assert backend.is_distributed is True


# ── IdempotencyStore.__init__ ─────────────────────────────────────────────────


def test_idempotency_store_with_explicit_backend():
    backend = InMemoryIdempotencyBackend()
    store = IdempotencyStore(ttl_seconds=3600, backend=backend)
    assert store._backend is backend
    assert store._ttl == 3600


def test_idempotency_store_auto_detect_no_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = IdempotencyStore()
    assert isinstance(store._backend, InMemoryIdempotencyBackend)


def test_idempotency_store_auto_detect_redis_url_fails(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    with patch("src.core.infra.redis_manager.RedisManager.get_client", return_value=None):
        store = IdempotencyStore()
    assert isinstance(store._backend, InMemoryIdempotencyBackend)


def test_idempotency_store_auto_detect_redis_success(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_redis = MagicMock()
    with patch("src.core.infra.redis_manager.RedisManager.get_client", return_value=mock_redis):
        store = IdempotencyStore()
    assert isinstance(store._backend, RedisIdempotencyBackend)


# ── IdempotencyStore.check_and_set ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_and_set_cached():
    backend = InMemoryIdempotencyBackend()
    store = IdempotencyStore(backend=backend)

    # Pre-populate
    key = store._generate_key("op", {"a": 1})
    await backend.set(key, {"cached": True}, ttl_seconds=60)

    async def noop():
        return {"should": "not be called"}

    result, was_cached = await store.check_and_set("op", {"a": 1}, execute_fn=noop)
    assert was_cached is True
    assert result == {"cached": True}


@pytest.mark.asyncio
async def test_check_and_set_uncached():
    store = IdempotencyStore()

    async def execute():
        return {"fresh": "result"}

    result, was_cached = await store.check_and_set("new_op", {"x": 2}, execute_fn=execute)
    assert was_cached is False
    assert result == {"fresh": "result"}

    # Second call should be cached
    result2, was_cached2 = await store.check_and_set("new_op", {"x": 2}, execute_fn=execute)
    assert was_cached2 is True
    assert result2 == {"fresh": "result"}


# ── IdempotencyStore.cleanup_expired ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_idempotency_store_cleanup_expired():
    store = IdempotencyStore()
    removed = await store.cleanup_expired()
    assert removed == 0


# ── get_idempotency_store ─────────────────────────────────────────────────────


def test_get_idempotency_store_creates_new():
    store = get_idempotency_store()
    assert isinstance(store, IdempotencyStore)


def test_get_idempotency_store_returns_same_instance():
    s1 = get_idempotency_store()
    s2 = get_idempotency_store()
    assert s1 is s2
