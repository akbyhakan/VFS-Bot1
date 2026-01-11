"""Tests for authentication module."""

import pytest
import os
from datetime import timedelta
from jose import jwt

from src.core.auth import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
    SECRET_KEY,
    ALGORITHM,
)
from fastapi import HTTPException


def test_create_access_token():
    """Test JWT token creation."""
    data = {"sub": "testuser", "name": "Test User"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    # Decode and verify
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testuser"
    assert payload["name"] == "Test User"
    assert "exp" in payload


def test_create_access_token_with_expiry():
    """Test JWT token creation with custom expiry."""
    data = {"sub": "testuser"}
    expires_delta = timedelta(hours=1)
    token = create_access_token(data, expires_delta)

    assert token is not None
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    """Test that passwords longer than 72 bytes are truncated."""
    # Create a password longer than 72 bytes (using ASCII chars = 1 byte each)
    long_password = "a" * 100
    hashed = hash_password(long_password)

    # Should hash successfully
    assert hashed is not None
    assert isinstance(hashed, str)

    # Verify with the same long password
    assert verify_password(long_password, hashed) is True

    # Verify that only the first 72 bytes matter (ASCII: 72 chars = 72 bytes)
    truncated_password = long_password[:72]
    assert verify_password(truncated_password, hashed) is True


def test_verify_password_long_password():
    """Test that verify_password handles passwords longer than 72 bytes."""
    # Hash a long password (using ASCII chars = 1 byte each)
    long_password = "b" * 100
    hashed = hash_password(long_password)

    # Verify with the full password
    assert verify_password(long_password, hashed) is True

    # Verify with password truncated to 72 bytes (ASCII: 72 chars = 72 bytes)
    truncated = long_password[:72]
    assert verify_password(truncated, hashed) is True

    # Verify that bytes beyond 72 don't matter
    different_tail = long_password[:72] + "xyz"
    assert verify_password(different_tail, hashed) is True


def test_hash_password_multibyte_characters():
    """Test password hashing with multi-byte UTF-8 characters."""
    # Use emoji and other multi-byte characters
    # Each emoji is typically 4 bytes in UTF-8
    multibyte_password = "password" + "🔒" * 20  # Should exceed 72 bytes

    hashed = hash_password(multibyte_password)

    # Should hash successfully
    assert hashed is not None
    assert isinstance(hashed, str)

    # Should verify correctly with the same password
    assert verify_password(multibyte_password, hashed) is True

    # Test that truncation is consistent between hash and verify
    # Hash a password that's exactly at the boundary
    boundary_password = "a" * 70 + "🔒"  # 70 ASCII + 4-byte emoji = 74 bytes
    hashed2 = hash_password(boundary_password)
    assert verify_password(boundary_password, hashed2) is True
