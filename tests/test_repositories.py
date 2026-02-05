"""Tests for repository pattern implementation."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.exceptions import RecordNotFoundError, ValidationError
from src.models.database import Database
from src.repositories.user_repository import User, UserRepository


@pytest.fixture
async def mock_db():
    """Create a mock database instance."""
    db = Mock(spec=Database)

    # Mock get_connection as an async context manager
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    db.get_connection = MagicMock(return_value=mock_conn)

    # Mock database methods
    db.add_user = AsyncMock(return_value=1)
    db.add_personal_details = AsyncMock(return_value=None)
    db.update_user = AsyncMock(return_value=True)

    return db


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": 1,
        "email": "test@example.com",
        "phone": "+905551234567",
        "first_name": "John",
        "last_name": "Doe",
        "center_name": "Istanbul",
        "visa_category": "Tourist",
        "visa_subcategory": "Short Stay",
        "is_active": True,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }


@pytest.mark.asyncio
async def test_user_repository_get_by_id(mock_db, sample_user_data):
    """Test getting user by ID."""
    repo = UserRepository(mock_db)

    # Mock database response
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=sample_user_data)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Get user
    user = await repo.get_by_id(1)

    assert user is not None
    assert isinstance(user, User)
    assert user.id == 1
    assert user.email == "test@example.com"
    assert user.first_name == "John"


@pytest.mark.asyncio
async def test_user_repository_get_by_id_not_found(mock_db):
    """Test getting non-existent user."""
    repo = UserRepository(mock_db)

    # Mock database response - no user found
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Get user
    user = await repo.get_by_id(999)

    assert user is None


@pytest.mark.asyncio
async def test_user_repository_get_by_email(mock_db, sample_user_data):
    """Test getting user by email."""
    repo = UserRepository(mock_db)

    # Mock database response
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=sample_user_data)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Get user
    user = await repo.get_by_email("test@example.com")

    assert user is not None
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_user_repository_get_all(mock_db, sample_user_data):
    """Test getting all users."""
    repo = UserRepository(mock_db)

    # Mock database response
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[sample_user_data, sample_user_data])
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Get all users
    users = await repo.get_all(limit=10)

    assert len(users) == 2
    assert all(isinstance(u, User) for u in users)


@pytest.mark.asyncio
async def test_user_repository_create_valid(mock_db):
    """Test creating a user with valid data."""
    repo = UserRepository(mock_db)

    data = {
        "email": "new@example.com",
        "password": "password123",
        "phone": "+905551234567",
        "first_name": "Jane",
        "last_name": "Smith",
        "center_name": "Ankara",
        "visa_category": "Work",
        "visa_subcategory": "Long Stay",
    }

    # Create user
    user_id = await repo.create(data)

    assert user_id == 1
    mock_db.add_user.assert_called_once()


@pytest.mark.asyncio
async def test_user_repository_create_missing_email(mock_db):
    """Test creating user without email."""
    repo = UserRepository(mock_db)

    data = {
        "center_name": "Istanbul",
    }

    # Should raise validation error
    with pytest.raises(ValidationError) as exc_info:
        await repo.create(data)

    assert "email" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_user_repository_create_invalid_email(mock_db):
    """Test creating user with invalid email."""
    repo = UserRepository(mock_db)

    data = {
        "email": "invalid-email",  # No @ symbol
        "center_name": "Istanbul",
    }

    # Should raise validation error
    with pytest.raises(ValidationError) as exc_info:
        await repo.create(data)

    assert "email" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_user_repository_update_valid(mock_db, sample_user_data):
    """Test updating user with valid data."""
    repo = UserRepository(mock_db)

    # Mock get_by_id to return existing user
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=sample_user_data)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    update_data = {
        "first_name": "UpdatedName",
        "is_active": False,
    }

    # Update user
    success = await repo.update(1, update_data)

    assert success is True
    mock_db.update_user.assert_called_once_with(
        user_id=1,
        email=None,
        password=None,
        centre=None,
        category=None,
        subcategory=None,
        active=False,
    )


@pytest.mark.asyncio
async def test_user_repository_update_not_found(mock_db):
    """Test updating non-existent user."""
    repo = UserRepository(mock_db)

    # Mock get_by_id to return None
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    update_data = {"first_name": "UpdatedName"}

    # Should raise RecordNotFoundError
    with pytest.raises(RecordNotFoundError):
        await repo.update(999, update_data)


@pytest.mark.asyncio
async def test_user_repository_update_invalid_email(mock_db, sample_user_data):
    """Test updating user with invalid email."""
    repo = UserRepository(mock_db)

    # Mock get_by_id to return existing user
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=sample_user_data)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    update_data = {"email": "invalid-email"}

    # Should raise validation error
    with pytest.raises(ValidationError):
        await repo.update(1, update_data)


@pytest.mark.asyncio
async def test_user_repository_delete(mock_db, sample_user_data):
    """Test soft deleting a user."""
    repo = UserRepository(mock_db)

    # Mock get_by_id to return existing user
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=sample_user_data)
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Delete user (soft delete)
    success = await repo.delete(1)

    assert success is True
    # Should call update_user with is_active=False
    mock_db.update_user.assert_called_once()


@pytest.mark.asyncio
async def test_user_repository_hard_delete(mock_db):
    """Test hard deleting a user."""
    repo = UserRepository(mock_db)

    # Mock database response
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 1
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()

    # Hard delete user
    success = await repo.hard_delete(1)

    assert success is True
    mock_conn.commit.assert_called_once()


@pytest.mark.asyncio
async def test_user_repository_get_active_count(mock_db):
    """Test getting active user count."""
    repo = UserRepository(mock_db)

    # Mock database response
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=(5,))
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Get active count
    count = await repo.get_active_count()

    assert count == 5


@pytest.mark.asyncio
async def test_user_to_dict(sample_user_data):
    """Test User entity to_dict method."""
    user = User(**sample_user_data)

    user_dict = user.to_dict()

    assert user_dict["id"] == 1
    assert user_dict["email"] == "test@example.com"
    assert user_dict["first_name"] == "John"
    assert user_dict["is_active"] is True


@pytest.mark.asyncio
async def test_user_repository_get_all_active_only(mock_db, sample_user_data):
    """Test getting only active users."""
    repo = UserRepository(mock_db)

    # Mock database response
    mock_conn = await mock_db.get_connection().__aenter__()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[sample_user_data])
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    # Get active users only
    users = await repo.get_all(limit=10, active_only=True)

    assert len(users) == 1
    # Verify query includes WHERE is_active = 1
    call_args = mock_conn.execute.call_args
    assert "is_active = 1" in call_args[0][0]
