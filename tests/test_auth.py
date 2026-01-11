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
