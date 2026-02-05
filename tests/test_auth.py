"""Tests for authentication module."""

import os
from datetime import timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

from src.core.auth import (
    create_access_token,
    get_algorithm,
    get_secret_key,
    hash_password,
    verify_password,
    verify_token,
)


def test_create_access_token():
    """Test JWT token creation."""
    data = {"sub": "testuser", "name": "Test User"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    # Decode and verify
    payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
    assert payload["sub"] == "testuser"
    assert payload["name"] == "Test User"
    assert "exp" in payload


def test_create_access_token_with_expiry():
    """Test JWT token creation with custom expiry."""
    data = {"sub": "testuser"}
    expires_delta = timedelta(hours=1)
    token = create_access_token(data, expires_delta)

    assert token is not None
    payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
    assert payload["sub"] == "testuser"


def test_verify_token_valid():
    """Test token verification with valid token."""
    data = {"sub": "testuser", "name": "Test User"}
    token = create_access_token(data)

    payload = verify_token(token)
    assert payload["sub"] == "testuser"
    assert payload["name"] == "Test User"


def test_verify_token_invalid():
    """Test token verification with invalid token."""
    with pytest.raises(HTTPException) as exc_info:
        verify_token("invalid.token.here")

    assert exc_info.value.status_code == 401


def test_verify_token_expired():
    """Test token verification with expired token."""
    data = {"sub": "testuser"}
    # Create token that expired immediately
    expires_delta = timedelta(seconds=-1)
    token = create_access_token(data, expires_delta)

    with pytest.raises(HTTPException) as exc_info:
        verify_token(token)

    assert exc_info.value.status_code == 401


def test_hash_password():
    """Test password hashing."""
    password = "testpassword123"
    hashed = hash_password(password)

    assert hashed is not None
    assert hashed != password
    assert len(hashed) > 0


def test_verify_password_correct():
    """Test password verification with correct password."""
    password = "testpassword123"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test password verification with incorrect password."""
    password = "testpassword123"
    hashed = hash_password(password)

    assert verify_password("wrongpassword", hashed) is False


def test_hash_password_different_each_time():
    """Test that same password produces different hashes (salt)."""
    password = "testpassword123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_hash_password_long_password():
    """Test password hashing with password longer than 72 bytes."""
    from src.core.exceptions import ValidationError

    # Create a password that's longer than 72 bytes (ASCII)
    long_password = "a" * 100
    assert len(long_password.encode("utf-8")) > 72

    # Should raise ValidationError instead of silently truncating
    with pytest.raises(ValidationError) as exc_info:
        hash_password(long_password)

    assert "exceeds maximum length" in str(exc_info.value).lower()


def test_verify_password_long_password():
    """Test password verification with long passwords."""
    from src.core.exceptions import ValidationError

    # Create two passwords that are identical in first 72 bytes
    password1 = "a" * 80
    password2 = "a" * 72 + "b" * 8

    # Both should raise ValidationError
    with pytest.raises(ValidationError):
        hash_password(password1)

    with pytest.raises(ValidationError):
        hash_password(password2)


def test_hash_password_multibyte_characters():
    """Test password hashing with multi-byte UTF-8 characters."""
    from src.core.exceptions import ValidationError

    # Use Chinese characters which are 3 bytes each in UTF-8
    # "测试密码" = 4 chars * 3 bytes = 12 bytes per repetition
    # 7 repetitions = 28 chars, 84 bytes (> 72 bytes)
    multibyte_password = "测试密码" * 7  # 28 chars, 84 bytes
    assert len(multibyte_password.encode("utf-8")) > 72

    # Should raise ValidationError for exceeding byte limit
    with pytest.raises(ValidationError):
        hash_password(multibyte_password)


def test_jwt_key_rotation(monkeypatch):
    """Test JWT key rotation support with API_SECRET_KEY_PREVIOUS."""
    import secrets

    # Create two different keys
    old_key = secrets.token_urlsafe(48)
    new_key = secrets.token_urlsafe(48)

    # Set old key and create token
    monkeypatch.setenv("API_SECRET_KEY", old_key)

    # Clear the LRU cache for _get_jwt_settings
    from src.core.auth import _get_jwt_settings

    _get_jwt_settings.cache_clear()

    data = {"sub": "testuser", "name": "Test User"}
    old_token = create_access_token(data)

    # Change to new key and set old key as previous
    monkeypatch.setenv("API_SECRET_KEY", new_key)
    monkeypatch.setenv("API_SECRET_KEY_PREVIOUS", old_key)
    _get_jwt_settings.cache_clear()

    # Old token should still verify using the previous key
    payload = verify_token(old_token)
    assert payload["sub"] == "testuser"
    assert payload["name"] == "Test User"

    # New token should verify with new key
    new_token = create_access_token(data)
    payload = verify_token(new_token)
    assert payload["sub"] == "testuser"


def test_jwt_key_rotation_without_previous_key(monkeypatch):
    """Test that tokens fail when key changes without API_SECRET_KEY_PREVIOUS."""
    import secrets

    # Create two different keys
    old_key = secrets.token_urlsafe(48)
    new_key = secrets.token_urlsafe(48)

    # Set old key and create token
    monkeypatch.setenv("API_SECRET_KEY", old_key)

    # Clear the LRU cache for _get_jwt_settings
    from src.core.auth import _get_jwt_settings

    _get_jwt_settings.cache_clear()

    data = {"sub": "testuser"}
    old_token = create_access_token(data)

    # Change to new key WITHOUT setting previous
    monkeypatch.setenv("API_SECRET_KEY", new_key)
    if "API_SECRET_KEY_PREVIOUS" in os.environ:
        monkeypatch.delenv("API_SECRET_KEY_PREVIOUS")
    _get_jwt_settings.cache_clear()

    # Old token should fail to verify
    with pytest.raises(HTTPException) as exc_info:
        verify_token(old_token)

    assert exc_info.value.status_code == 401
