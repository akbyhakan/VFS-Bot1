"""Tests for user model."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.models.user import (
    UserRole,
    UserSettings,
    User,
    UserCreate,
    UserResponse,
)


def test_user_role_enum():
    """Test UserRole enum values."""
    assert UserRole.ADMIN == "admin"
    assert UserRole.USER == "user"
    assert UserRole.TESTER == "tester"


def test_user_settings_defaults():
    """Test UserSettings default values."""
    settings = UserSettings()
    assert settings.use_direct_api is False
    assert settings.preferred_language == "tr"
    assert settings.notification_enabled is True


def test_user_settings_custom():
    """Test UserSettings with custom values."""
    settings = UserSettings(
        use_direct_api=True,
        preferred_language="en",
        notification_enabled=False
    )
    assert settings.use_direct_api is True
    assert settings.preferred_language == "en"
    assert settings.notification_enabled is False


def test_user_model_defaults():
    """Test User model with default values."""
    user = User(
        id="1",
        email="test@example.com",
        password_hash="hashed_password"
    )
    assert user.role == UserRole.USER
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_user_is_tester_property():
    """Test is_tester property."""
    normal_user = User(
        id="1",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER
    )
    assert normal_user.is_tester is False
    
    tester_user = User(
        id="2",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )
    assert tester_user.is_tester is True


def test_user_uses_direct_api_property():
    """Test uses_direct_api property."""
    # Normal user without direct API setting
    user1 = User(
        id="1",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER
    )
    assert user1.uses_direct_api is False
    
    # Normal user with direct API setting enabled
    user2 = User(
        id="2",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER,
        settings=UserSettings(use_direct_api=True)
    )
    assert user2.uses_direct_api is True
    
    # Tester always uses direct API
    user3 = User(
        id="3",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )
    assert user3.uses_direct_api is True
    
    # Tester uses direct API even if setting is False
    user4 = User(
        id="4",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER,
        settings=UserSettings(use_direct_api=False)
    )
    assert user4.uses_direct_api is True


def test_user_create_model():
    """Test UserCreate model."""
    user_create = UserCreate(
        email="new@example.com",
        password="securepassword123",
        role=UserRole.USER
    )
    assert user_create.email == "new@example.com"
    assert user_create.password == "securepassword123"
    assert user_create.role == UserRole.USER


def test_user_create_default_role():
    """Test UserCreate with default role."""
    user_create = UserCreate(
        email="new@example.com",
        password="securepassword123"
    )
    assert user_create.role == UserRole.USER


def test_user_create_invalid_email():
    """Test UserCreate with invalid email."""
    with pytest.raises(ValidationError):
        UserCreate(
            email="invalid-email",
            password="securepassword123"
        )


def test_user_response_model():
    """Test UserResponse model."""
    user = User(
        id="1",
        email="test@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )
    
    response = UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_tester=user.is_tester,
        uses_direct_api=user.uses_direct_api,
        created_at=user.created_at
    )
    
    assert response.id == "1"
    assert response.email == "test@example.com"
    assert response.role == UserRole.TESTER
    assert response.is_tester is True
    assert response.uses_direct_api is True


def test_all_user_roles():
    """Test all user role types."""
    admin = User(
        id="1",
        email="admin@example.com",
        password_hash="hash",
        role=UserRole.ADMIN
    )
    assert admin.role == UserRole.ADMIN
    assert admin.is_tester is False
    
    user = User(
        id="2",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER
    )
    assert user.role == UserRole.USER
    assert user.is_tester is False
    
    tester = User(
        id="3",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )
    assert tester.role == UserRole.TESTER
    assert tester.is_tester is True
