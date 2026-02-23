"""Unit tests for src/core/infra/redis_manager.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.infra.redis_manager import RedisManager


@pytest.fixture(autouse=True)
def reset_redis_manager():
    """Reset RedisManager singleton state before and after each test."""
    RedisManager.reset()
    yield
    RedisManager.reset()


# ── Singleton behavior ────────────────────────────────────────────────────────


def test_get_client_returns_none_when_no_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert RedisManager.get_client() is None


def test_get_client_singleton_same_instance(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client):
        c1 = RedisManager.get_client()
        c2 = RedisManager.get_client()
    assert c1 is c2
    assert c1 is mock_client


def test_get_client_returns_client_when_redis_available(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    with patch("redis.from_url", return_value=mock_client):
        mock_client.ping = MagicMock(return_value=True)
        client = RedisManager.get_client()
    assert client is mock_client


def test_get_client_returns_none_when_ping_fails(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(side_effect=Exception("ping failed"))
    with patch("redis.from_url", return_value=mock_client):
        client = RedisManager.get_client()
    assert client is None


def test_get_client_returns_none_when_from_url_raises(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    with patch("redis.from_url", side_effect=Exception("connection refused")):
        client = RedisManager.get_client()
    assert client is None


def test_get_client_uses_max_connections(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client) as mock_from_url:
        RedisManager.get_client()
        call_kwargs = mock_from_url.call_args[1]
        assert call_kwargs.get("max_connections") == 20


def test_get_client_cached_after_first_call(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client) as mock_from_url:
        RedisManager.get_client()
        RedisManager.get_client()
        # from_url should only be called once (singleton)
        assert mock_from_url.call_count == 1


# ── is_available ──────────────────────────────────────────────────────────────


def test_is_available_false_when_no_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert RedisManager.is_available() is False


def test_is_available_true_when_redis_connected(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client):
        assert RedisManager.is_available() is True


# ── health_check ──────────────────────────────────────────────────────────────


def test_health_check_false_when_no_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert RedisManager.health_check() is False


def test_health_check_true_when_ping_succeeds(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client):
        assert RedisManager.health_check() is True


def test_health_check_resets_and_returns_false_on_ping_failure(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    # First ping succeeds (during get_client init), then fails on health_check
    mock_client.ping = MagicMock(side_effect=[True, Exception("timeout")])
    with patch("redis.from_url", return_value=mock_client):
        RedisManager.get_client()  # Initialize
        result = RedisManager.health_check()
    assert result is False
    # After reset, _initialized should be False
    assert RedisManager._initialized is False


def test_health_check_reconnects_when_client_is_none_and_redis_url_set(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    # Simulate: first get_client() fails (returns None), then reconnect succeeds
    call_count = {"n": 0}

    def patched_create(cls):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None  # initial connection fails
        return mock_client  # reconnect succeeds

    with patch.object(RedisManager, "_create_client", classmethod(patched_create)):
        RedisManager.get_client()  # returns None, _initialized=True
        result = RedisManager.health_check()  # should try reconnect

    assert result is True


def test_health_check_returns_false_when_reconnect_also_fails(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    def patched_create(cls):
        return None  # always fail

    with patch.object(RedisManager, "_create_client", classmethod(patched_create)):
        RedisManager.get_client()  # returns None
        result = RedisManager.health_check()

    assert result is False


# ── reset ─────────────────────────────────────────────────────────────────────


def test_reset_clears_instance(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client):
        RedisManager.get_client()

    assert RedisManager._initialized is True
    RedisManager.reset()
    assert RedisManager._initialized is False
    assert RedisManager._instance is None


def test_reset_closes_existing_client(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    with patch("redis.from_url", return_value=mock_client):
        RedisManager.get_client()

    RedisManager.reset()
    mock_client.close.assert_called_once()


def test_reset_handles_close_error_gracefully(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    mock_client = MagicMock()
    mock_client.ping = MagicMock(return_value=True)
    mock_client.close = MagicMock(side_effect=Exception("close error"))
    with patch("redis.from_url", return_value=mock_client):
        RedisManager.get_client()

    # Should not raise
    RedisManager.reset()
    assert RedisManager._initialized is False
