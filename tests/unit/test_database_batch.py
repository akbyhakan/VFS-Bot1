"""Tests for database batch query functionality."""

import pytest

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.repositories import AccountPoolRepository


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    yield db

    try:
        async with db.get_connection() as conn:
            await conn.execute("""
                TRUNCATE TABLE appointment_persons, appointment_requests, appointments,
                personal_details, token_blacklist, audit_log, logs, payment_card,
                user_webhooks, users RESTART IDENTITY CASCADE
            """)
    except Exception:
        pass
    await db.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_personal_details_batch_empty(temp_db):
    """Test batch query with empty list."""
    user_repo = AccountPoolRepository(temp_db)
    result = await user_repo.get_personal_details_batch([])
    assert result == {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_personal_details_batch_single(temp_db):
    """Test batch query with single user."""
    # Create a user
    user_repo = AccountPoolRepository(temp_db)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "testpass123",
            "center_name": "Istanbul",
            "visa_category": "Tourist",
            "visa_subcategory": "Single Entry",
        }
    )

    # Add personal details
    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "A12345678",
        "email": "test@example.com",
    }
    user_repo_write = AccountPoolRepository(temp_db)
    await user_repo_write.add_personal_details(user_id, details)

    # Batch query
    result = await user_repo_write.get_personal_details_batch([user_id])

    assert len(result) == 1
    assert user_id in result
    assert result[user_id]["first_name"] == "John"
    assert result[user_id]["last_name"] == "Doe"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_personal_details_batch_multiple(temp_db):
    """Test batch query with multiple users."""
    # Create multiple users
    user_repo = AccountPoolRepository(temp_db)
    user1_id = await user_repo.create(
        {
            "email": "user1@example.com",
            "password": "pass1",
            "center_name": "Istanbul",
            "visa_category": "Tourist",
            "visa_subcategory": "Single Entry",
        }
    )

    user2_id = await user_repo.create(
        {
            "email": "user2@example.com",
            "password": "pass2",
            "center_name": "Ankara",
            "visa_category": "Business",
            "visa_subcategory": "Multiple Entry",
        }
    )

    user3_id = await user_repo.create(
        {
            "email": "user3@example.com",
            "password": "pass3",
            "center_name": "Izmir",
            "visa_category": "Student",
            "visa_subcategory": "Single Entry",
        }
    )

    # Add personal details
    user_repo_write = AccountPoolRepository(temp_db)
    await user_repo_write.add_personal_details(
        user1_id,
        {
            "first_name": "Alice",
            "last_name": "Smith",
            "passport_number": "P111",
            "email": "user1@example.com",
        },
    )

    await user_repo_write.add_personal_details(
        user2_id,
        {
            "first_name": "Bob",
            "last_name": "Jones",
            "passport_number": "P222",
            "email": "user2@example.com",
        },
    )

    await user_repo_write.add_personal_details(
        user3_id,
        {
            "first_name": "Charlie",
            "last_name": "Brown",
            "passport_number": "P333",
            "email": "user3@example.com",
        },
    )

    # Batch query all three
    result = await user_repo_write.get_personal_details_batch([user1_id, user2_id, user3_id])

    assert len(result) == 3
    assert result[user1_id]["first_name"] == "Alice"
    assert result[user2_id]["first_name"] == "Bob"
    assert result[user3_id]["first_name"] == "Charlie"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_personal_details_batch_missing_users(temp_db):
    """Test batch query with some non-existent users."""
    # Create one user
    user_repo = AccountPoolRepository(temp_db)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "testpass",
            "center_name": "Istanbul",
            "visa_category": "Tourist",
            "visa_subcategory": "Single Entry",
        }
    )

    await user_repo.add_personal_details(
        user_id,
        {
            "first_name": "John",
            "last_name": "Doe",
            "passport_number": "P123",
            "email": "test@example.com",
        },
    )

    # Query with mix of existing and non-existing IDs
    result = await user_repo.get_personal_details_batch([user_id, 9999, 8888])

    # Should only return the existing user
    assert len(result) == 1
    assert user_id in result
    assert 9999 not in result
    assert 8888 not in result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_personal_details_batch_invalid_ids():
    """Test batch query with invalid user IDs."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    try:
        user_repo = AccountPoolRepository(db)
        # Test with invalid IDs (negative, zero)
        with pytest.raises(ValueError, match="Invalid user_id"):
            await user_repo.get_personal_details_batch([0])

        with pytest.raises(ValueError, match="Invalid user_id"):
            await user_repo.get_personal_details_batch([-1])

        with pytest.raises(ValueError, match="Invalid user_id"):
            await user_repo.get_personal_details_batch([1, -5, 3])
    finally:
        await db.close()
