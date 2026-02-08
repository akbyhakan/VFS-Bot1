"""Tests for security improvements: SQL injection protection, API key hashing,
thread safety, and JWT validation."""

import asyncio
import logging
import os
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.fernet import Fernet

from src.core.auth import _get_jwt_settings
from src.core.security import _get_api_key_salt, hash_api_key
from src.models.database import ALLOWED_PERSONAL_DETAILS_FIELDS, Database
from src.utils.encryption import reset_encryption
from web.dependencies import ThreadSafeBotState


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test and reset global encryption instance."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # Reset global encryption instance to ensure it uses the new key
    reset_encryption()
    yield key
    # Cleanup: reset encryption instance after test
    reset_encryption()


@pytest.fixture
async def test_db(unique_encryption_key):
    """Create a test database."""
    from src.constants import Database as DatabaseConfig
    
    test_db_url = DatabaseConfig.TEST_URL
    db = Database(database_url=test_db_url)
    
    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")
    
    yield db
    await db.close()


# ==============================================================================
# SQL Injection Protection Tests
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.security
async def test_update_personal_details_allows_whitelisted_fields(
    test_db, unique_encryption_key, caplog
):
    """Test that update_personal_details allows whitelisted fields."""
    # Create a user first
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password123",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Add personal details
    await test_db.add_personal_details(
        user_id=user_id,
        details={
            "first_name": "John",
            "last_name": "Doe",
            "passport_number": "AB123456",
            "email": "test@example.com",
            "mobile_number": "1234567890",
        },
    )

    # Update with allowed fields
    updated = await test_db.update_personal_details(
        user_id=user_id,
        first_name="Jane",
        passport_number="CD789012",
        email="jane@example.com",
    )

    assert updated is True

    # Verify update
    details = await test_db.get_personal_details(user_id)
    assert details["first_name"] == "Jane"
    assert details["passport_number"] == "CD789012"
    assert details["email"] == "jane@example.com"


@pytest.mark.asyncio
@pytest.mark.security
async def test_update_personal_details_blocks_disallowed_fields(
    test_db, unique_encryption_key, caplog
):
    """Test that update_personal_details blocks disallowed fields and logs warning."""
    # Set caplog to capture WARNING level logs
    caplog.set_level(logging.WARNING)

    # Create a user first
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password123",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Add personal details
    await test_db.add_personal_details(
        user_id=user_id,
        details={
            "first_name": "John",
            "last_name": "Doe",
            "passport_number": "AB123456",
            "email": "test@example.com",
            "mobile_number": "1234567890",
        },
    )

    # Try to update with a disallowed field (SQL injection attempt)
    updated = await test_db.update_personal_details(
        user_id=user_id,
        first_name="Jane",
        malicious_field="DROP TABLE users;",  # SQL injection attempt
    )

    # Should still return True (update succeeded for allowed fields)
    assert updated is True

    # Check that warning was logged
    assert any("disallowed field" in record.message.lower() for record in caplog.records)
    assert any("malicious_field" in record.message for record in caplog.records)

    # Verify only allowed field was updated
    details = await test_db.get_personal_details(user_id)
    assert details["first_name"] == "Jane"
    assert "malicious_field" not in details


@pytest.mark.asyncio
@pytest.mark.security
async def test_allowed_fields_whitelist_is_frozen():
    """Test that ALLOWED_PERSONAL_DETAILS_FIELDS is a frozenset (immutable)."""
    assert isinstance(ALLOWED_PERSONAL_DETAILS_FIELDS, frozenset)

    # Verify it contains expected fields
    expected_fields = {
        "first_name",
        "last_name",
        "passport_number",
        "passport_expiry",
        "gender",
        "mobile_code",
        "mobile_number",
        "email",
        "nationality",
        "date_of_birth",
        "address_line1",
        "address_line2",
        "state",
        "city",
        "postcode",
    }
    assert ALLOWED_PERSONAL_DETAILS_FIELDS == expected_fields


# ==============================================================================
# Audit Logging Tests
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.security
async def test_add_audit_log(test_db):
    """Test adding audit log entries."""
    log_id = await test_db.add_audit_log(
        action="login",
        username="admin",
        ip_address="127.0.0.1",
        user_agent="Mozilla/5.0",
        details='{"browser": "Chrome"}',
        success=True,
    )

    assert log_id > 0


@pytest.mark.asyncio
@pytest.mark.security
async def test_get_audit_logs(test_db):
    """Test retrieving audit log entries."""
    # Add multiple log entries
    await test_db.add_audit_log(action="login", username="admin", success=True)
    await test_db.add_audit_log(action="logout", username="admin", success=True)
    await test_db.add_audit_log(action="user_created", username="admin", success=True)

    # Get all logs
    logs = await test_db.get_audit_logs(limit=10)
    assert len(logs) == 3

    # Get filtered by action
    login_logs = await test_db.get_audit_logs(action="login")
    assert len(login_logs) == 1
    assert login_logs[0]["action"] == "login"


@pytest.mark.asyncio
@pytest.mark.security
async def test_get_audit_logs_with_user_filter(test_db):
    """Test filtering audit logs by user_id."""
    # Create users
    user1_id = await test_db.add_user(
        email="user1@example.com",
        password="pass123",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )
    user2_id = await test_db.add_user(
        email="user2@example.com",
        password="pass456",
        centre="Ankara",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Add audit logs for different users
    await test_db.add_audit_log(action="payment_initiated", user_id=user1_id)
    await test_db.add_audit_log(action="payment_initiated", user_id=user2_id)
    await test_db.add_audit_log(action="login", user_id=user1_id)

    # Filter by user
    user1_logs = await test_db.get_audit_logs(user_id=user1_id)
    assert len(user1_logs) == 2
    assert all(log["user_id"] == user1_id for log in user1_logs)


# ==============================================================================
# API Key Hashing with Salt Tests
# ==============================================================================


@pytest.mark.security
def test_api_key_hash_with_salt(monkeypatch):
    """Test that API keys are hashed with salt using HMAC-SHA256."""
    # Set a custom salt (must be at least 32 characters)
    monkeypatch.setenv("API_KEY_SALT", "test-salt-12345-with-sufficient-length-for-security")

    # Clear cached salt
    import src.core.security as security_module

    security_module._API_KEY_SALT = None

    api_key = "my-secret-api-key-123"
    hash1 = hash_api_key(api_key)
    hash2 = hash_api_key(api_key)

    # Same key should produce same hash
    assert hash1 == hash2

    # Hash should be 64 characters (SHA256 hex)
    assert len(hash1) == 64

    # Different key should produce different hash
    different_key = "different-api-key-456"
    hash3 = hash_api_key(different_key)
    assert hash1 != hash3


@pytest.mark.security
def test_api_key_hash_different_with_different_salt(monkeypatch):
    """Test that different salts produce different hashes."""
    import src.core.security as security_module

    api_key = "my-api-key"

    # First hash with salt1 (at least 32 characters)
    monkeypatch.setenv("API_KEY_SALT", "salt1-with-enough-characters-to-be-secure-and-valid")
    security_module._API_KEY_SALT = None
    hash1 = hash_api_key(api_key)

    # Second hash with salt2 (at least 32 characters)
    monkeypatch.setenv("API_KEY_SALT", "salt2-with-enough-characters-to-be-secure-and-valid")
    security_module._API_KEY_SALT = None
    hash2 = hash_api_key(api_key)

    # Hashes should be different
    assert hash1 != hash2


@pytest.mark.security
def test_api_key_hash_uses_default_salt_when_env_not_set(monkeypatch):
    """Test that a default salt is used when API_KEY_SALT env var is not set."""
    import src.core.security as security_module

    # Ensure env var is not set and set ENV to development to allow default salt
    monkeypatch.delenv("API_KEY_SALT", raising=False)
    monkeypatch.setenv("ENV", "development")
    security_module._API_KEY_SALT = None

    api_key = "test-key"
    hash_value = hash_api_key(api_key)

    # Should still produce a valid hash
    assert len(hash_value) == 64
    assert hash_value.isalnum()


# ==============================================================================
# Thread-Safe Bot State Tests
# ==============================================================================


@pytest.mark.security
def test_thread_safe_bot_state_initialization():
    """Test that ThreadSafeBotState initializes correctly."""
    state = ThreadSafeBotState()

    assert state["running"] is False
    assert state["status"] == "stopped"
    assert state["slots_found"] == 0
    assert isinstance(state["logs"], deque)


@pytest.mark.security
def test_thread_safe_bot_state_get_set():
    """Test get/set methods work correctly."""
    state = ThreadSafeBotState()

    # Test set
    state.set("running", True)
    assert state.get("running") is True

    # Test default value
    assert state.get("nonexistent", "default") == "default"


@pytest.mark.security
def test_thread_safe_bot_state_getitem_setitem():
    """Test dictionary-style access."""
    state = ThreadSafeBotState()

    # Test setitem
    state["slots_found"] = 42
    assert state["slots_found"] == 42

    # Test getitem
    value = state["status"]
    assert value == "stopped"


@pytest.mark.security
def test_thread_safe_bot_state_concurrent_access():
    """Test that ThreadSafeBotState is thread-safe under concurrent access."""
    state = ThreadSafeBotState()
    state["counter"] = 0

    def increment_counter(iterations=1000):
        """Increment counter multiple times."""
        for _ in range(iterations):
            current = state["counter"]
            state["counter"] = current + 1

    # Run multiple threads concurrently
    threads = []
    num_threads = 10
    iterations_per_thread = 100

    for _ in range(num_threads):
        thread = threading.Thread(target=increment_counter, args=(iterations_per_thread,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify final count
    expected_count = num_threads * iterations_per_thread
    assert state["counter"] == expected_count


@pytest.mark.security
def test_thread_safe_bot_state_logs_deque():
    """Test that logs deque in ThreadSafeBotState maintains max length."""
    state = ThreadSafeBotState()
    logs = state["logs"]

    # Add more than maxlen items
    for i in range(600):
        logs.append(f"Log entry {i}")

    # Should only keep last 500
    assert len(logs) == 500
    assert logs[0] == "Log entry 100"  # First 100 were dropped
    assert logs[-1] == "Log entry 599"


# ==============================================================================
# JWT Secret Key Length Tests
# ==============================================================================


@pytest.mark.security
def test_jwt_secret_key_minimum_length_64(monkeypatch):
    """Test that JWT secret key must be at least 64 characters."""
    # Clear cache
    _get_jwt_settings.cache_clear()

    # Test with short key (should fail)
    short_key = "x" * 32  # Only 32 characters
    monkeypatch.setenv("API_SECRET_KEY", short_key)

    with pytest.raises(ValueError) as exc_info:
        _get_jwt_settings()

    assert "at least 64 characters" in str(exc_info.value)


@pytest.mark.security
def test_jwt_secret_key_accepts_64_chars(monkeypatch):
    """Test that JWT secret key accepts exactly 64 characters."""
    # Clear cache
    _get_jwt_settings.cache_clear()

    # Test with exactly 64 characters
    valid_key = "x" * 64
    monkeypatch.setenv("API_SECRET_KEY", valid_key)

    settings = _get_jwt_settings()
    assert settings.secret_key == valid_key


@pytest.mark.security
def test_jwt_secret_key_accepts_longer_than_64(monkeypatch):
    """Test that JWT secret key accepts more than 64 characters."""
    # Clear cache
    _get_jwt_settings.cache_clear()

    # Test with more than 64 characters
    valid_key = "x" * 100
    monkeypatch.setenv("API_SECRET_KEY", valid_key)

    settings = _get_jwt_settings()
    assert settings.secret_key == valid_key


@pytest.mark.security
def test_jwt_secret_key_not_set(monkeypatch):
    """Test that missing JWT secret key raises error."""
    # Clear cache
    _get_jwt_settings.cache_clear()

    # Remove env var
    monkeypatch.delenv("API_SECRET_KEY", raising=False)

    with pytest.raises(ValueError) as exc_info:
        _get_jwt_settings()

    assert "must be set" in str(exc_info.value)


# ==============================================================================
# Constants Consistency Tests
# ==============================================================================


@pytest.mark.security
def test_database_pool_size_default():
    """Test that Database.POOL_SIZE has the correct default value."""
    from src.constants import Database

    # Default should be 10
    assert Database.POOL_SIZE == 10
