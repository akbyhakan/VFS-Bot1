"""Tests for security utilities."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.security import generate_api_key, hash_api_key, load_api_keys, API_KEYS


def test_generate_api_key():
    """Test API key generation."""
    key1 = generate_api_key()
    key2 = generate_api_key()

    assert isinstance(key1, str)
    assert isinstance(key2, str)
    assert len(key1) > 0
    assert len(key2) > 0
    assert key1 != key2  # Should be unique


def test_hash_api_key():
    """Test API key hashing."""
    key = "test_api_key_12345"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)

    assert isinstance(hash1, str)
    assert len(hash1) == 64  # SHA256 hex length
    assert hash1 == hash2  # Same input should give same hash


def test_hash_api_key_different_inputs():
    """Test that different keys produce different hashes."""
    key1 = "test_key_1"
    key2 = "test_key_2"

    hash1 = hash_api_key(key1)
    hash2 = hash_api_key(key2)

    assert hash1 != hash2


def test_load_api_keys_without_env():
    """Test loading API keys when environment variable is not set."""
    # Clear any existing keys
    API_KEYS.clear()

    load_api_keys()

    # Should not add keys if no env var
    assert len(API_KEYS) == 0 or "master" not in [v.get("name") for v in API_KEYS.values()]


def test_load_api_keys_with_env(monkeypatch):
    """Test loading API keys with environment variable."""
    # Clear any existing keys
    API_KEYS.clear()

    test_key = "test_master_key_12345"
    monkeypatch.setenv("DASHBOARD_API_KEY", test_key)

    load_api_keys()

    # Should have added the master key
    key_hash = hash_api_key(test_key)
    assert key_hash in API_KEYS
    assert API_KEYS[key_hash]["name"] == "master"
    assert "admin" in API_KEYS[key_hash]["scopes"]


def test_api_keys_structure(monkeypatch):
    """Test API keys structure."""
    API_KEYS.clear()

    test_key = "test_key_67890"
    monkeypatch.setenv("DASHBOARD_API_KEY", test_key)

    load_api_keys()

    key_hash = hash_api_key(test_key)
    assert key_hash in API_KEYS
    assert "name" in API_KEYS[key_hash]
    assert "created" in API_KEYS[key_hash]
    assert "scopes" in API_KEYS[key_hash]
    assert isinstance(API_KEYS[key_hash]["scopes"], list)
