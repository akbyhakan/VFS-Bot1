"""Coverage tests for src/core/security.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.core.security import APIKeyManager, generate_api_key, verify_api_key


@pytest.fixture(autouse=True)
def reset_manager():
    APIKeyManager.reset()
    yield
    APIKeyManager.reset()


@pytest.fixture(autouse=True)
def set_testing_env(monkeypatch):
    monkeypatch.setenv("ENV", "testing")
    monkeypatch.delenv("API_KEY_SALT", raising=False)
    monkeypatch.delenv("DASHBOARD_API_KEY", raising=False)


# ── get_salt / _load_salt ────────────────────────────────────────────────────


def test_get_salt_returns_bytes():
    manager = APIKeyManager()
    salt = manager.get_salt()
    assert isinstance(salt, bytes)
    assert len(salt) > 0


def test_get_salt_raises_runtime_error_when_salt_none(monkeypatch):
    """Cover the 'if self._salt is None: raise RuntimeError' branch (line 62)."""
    manager = APIKeyManager()
    # Force _load_salt to be a no-op so _salt stays None
    with patch.object(manager, "_load_salt", return_value=None):
        # Reset cached salt
        manager._salt = None
        with pytest.raises(RuntimeError, match="Failed to load API key salt"):
            manager.get_salt()


def test_load_salt_with_explicit_env_var(monkeypatch):
    monkeypatch.setenv("API_KEY_SALT", "a" * 32)
    manager = APIKeyManager()
    salt = manager.get_salt()
    assert salt == ("a" * 32).encode()


def test_load_salt_too_short_raises(monkeypatch):
    monkeypatch.setenv("ENV", "testing")
    monkeypatch.setenv("API_KEY_SALT", "tooshort")
    with pytest.raises(ValueError, match="at least 32 characters"):
        APIKeyManager().get_salt()


# ── add_key ──────────────────────────────────────────────────────────────────


def test_add_key_returns_hash_and_stores_metadata():
    manager = APIKeyManager()
    key = generate_api_key()
    meta = {"name": "test-key", "scopes": ["read"]}
    key_hash = manager.add_key(key, meta)
    assert isinstance(key_hash, str)
    assert len(key_hash) == 64  # sha256 hex
    # Verify metadata is stored
    result = manager.verify_key(key)
    assert result is not None
    assert result["name"] == "test-key"


def test_add_key_auto_adds_created_timestamp():
    manager = APIKeyManager()
    key = generate_api_key()
    meta = {"name": "no-created"}
    manager.add_key(key, meta)
    result = manager.verify_key(key)
    assert "created" in result


def test_add_key_preserves_existing_created():
    manager = APIKeyManager()
    key = generate_api_key()
    ts = "2024-01-01T00:00:00+00:00"
    meta = {"name": "keyed", "created": ts}
    manager.add_key(key, meta)
    result = manager.verify_key(key)
    assert result["created"] == ts


# ── verify_key ───────────────────────────────────────────────────────────────


def test_verify_key_returns_metadata_for_valid_key():
    manager = APIKeyManager()
    key = generate_api_key()
    manager.add_key(key, {"name": "valid"})
    assert manager.verify_key(key) is not None


def test_verify_key_returns_none_for_invalid_key():
    manager = APIKeyManager()
    assert manager.verify_key("not-a-real-key") is None


# ── rotate_key ───────────────────────────────────────────────────────────────


def test_rotate_key_replaces_old_key_with_new():
    manager = APIKeyManager()
    old_key = generate_api_key()
    new_key = generate_api_key()
    manager.add_key(old_key, {"name": "to-rotate"})

    new_hash = manager.rotate_key(old_key, new_key)

    assert new_hash is not None
    assert manager.verify_key(old_key) is None
    result = manager.verify_key(new_key)
    assert result is not None
    assert "rotated_at" in result
    assert "rotation_grace_until" in result


def test_rotate_key_returns_none_when_old_key_not_found():
    manager = APIKeyManager()
    result = manager.rotate_key("nonexistent-key", generate_api_key())
    assert result is None


# ── cleanup_expired_keys ─────────────────────────────────────────────────────


def test_cleanup_expired_keys_removes_past_grace_period():
    from datetime import datetime, timedelta, timezone

    manager = APIKeyManager()
    key = generate_api_key()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    manager.add_key(key, {"name": "expired-grace", "rotation_grace_until": past})

    removed = manager.cleanup_expired_keys()
    assert removed >= 1
    assert manager.verify_key(key) is None


def test_cleanup_expired_keys_removes_old_creation():
    from datetime import datetime, timedelta, timezone

    manager = APIKeyManager()
    key = generate_api_key()
    old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    # Bypass add_key timestamp injection by directly setting
    key_hash = manager.add_key(key, {"name": "old-key"})
    manager._keys[key_hash]["created"] = old_ts

    removed = manager.cleanup_expired_keys(max_age_days=90)
    assert removed >= 1


def test_cleanup_expired_keys_keeps_recent():
    manager = APIKeyManager()
    key = generate_api_key()
    manager.add_key(key, {"name": "fresh"})

    removed = manager.cleanup_expired_keys(max_age_days=90)
    assert removed == 0
    assert manager.verify_key(key) is not None


def test_cleanup_expired_keys_invalid_timestamps():
    """Cover the ValueError/TypeError paths for invalid timestamps."""
    manager = APIKeyManager()
    key = generate_api_key()
    key_hash = manager.add_key(key, {"name": "bad-ts"})
    manager._keys[key_hash]["rotation_grace_until"] = "not-a-date"
    manager._keys[key_hash]["created"] = "also-bad"

    # Should not raise
    removed = manager.cleanup_expired_keys()
    assert removed == 0


# ── load_keys ────────────────────────────────────────────────────────────────


def test_load_keys_adds_dashboard_api_key(monkeypatch):
    master = generate_api_key()
    monkeypatch.setenv("DASHBOARD_API_KEY", master)
    manager = APIKeyManager()
    manager.load_keys()
    result = manager.verify_key(master)
    assert result is not None
    assert result["name"] == "master"
    assert "admin" in result["scopes"]


def test_load_keys_no_env_var_does_nothing(monkeypatch):
    monkeypatch.delenv("DASHBOARD_API_KEY", raising=False)
    manager = APIKeyManager()
    manager.load_keys()
    # No keys were added from env
    assert len(manager._keys) == 0


# ── verify_api_key (async) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_api_key_raises_401_for_invalid():
    creds = MagicMock(spec=HTTPAuthorizationCredentials)
    creds.credentials = "invalid-key-xyz"

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(creds)

    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_returns_metadata_for_valid():
    manager = APIKeyManager()
    key = generate_api_key()
    manager.add_key(key, {"name": "async-test", "scopes": ["read"]})

    creds = MagicMock(spec=HTTPAuthorizationCredentials)
    creds.credentials = key

    result = await verify_api_key(creds)
    assert result["name"] == "async-test"
