"""Tests for database parameter validation."""

import pytest
from cryptography.fernet import Fernet

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.repositories import UserRepository


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """
    Set up unique encryption key for each test and reset global encryption instance.

    This fixture ensures test isolation by:
    1. Generating a fresh Fernet encryption key for each test
    2. Setting it in the ENCRYPTION_KEY environment variable
    3. Resetting the global encryption instance before and after the test

    Yields:
        str: The generated encryption key
    """
    from src.utils.encryption import reset_encryption

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    reset_encryption()
    yield key
    reset_encryption()


@pytest.fixture
async def test_db(unique_encryption_key):
    """Create a test database."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")

    # Clean slate before each test
    try:
        async with db.get_connection() as conn:
            await conn.execute("""
                TRUNCATE TABLE appointment_persons, appointment_requests, appointments,
                personal_details, token_blacklist, audit_log, logs, payment_card,
                user_webhooks, users RESTART IDENTITY CASCADE
            """)
    except Exception:
        pass

    # Add a test user
    user_repo = UserRepository(db)
    await user_repo.create(
        {
            "email": "test@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

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
async def test_get_user_with_invalid_user_id_negative(test_db):
    """Test that negative user_id raises ValueError."""
    user_repo = UserRepository(test_db)
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await user_repo.get_by_id_with_password(-1)


@pytest.mark.asyncio
async def test_get_user_with_invalid_user_id_zero(test_db):
    """Test that zero user_id raises ValueError."""
    user_repo = UserRepository(test_db)
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await user_repo.get_by_id_with_password(0)


@pytest.mark.asyncio
async def test_get_user_with_invalid_user_id_string(test_db):
    """Test that string user_id raises ValueError."""
    user_repo = UserRepository(test_db)
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await user_repo.get_by_id_with_password("not_an_int")  # type: ignore


@pytest.mark.asyncio
async def test_get_personal_details_with_invalid_user_id(test_db):
    """Test that invalid user_id raises ValueError in get_personal_details."""
    user_repo = UserRepository(test_db)
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await user_repo.get_personal_details(-1)


@pytest.mark.asyncio
async def test_add_personal_details_with_invalid_user_id(test_db):
    """Test that invalid user_id raises ValueError in add_personal_details."""
    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "ABC123",
        "email": "john@example.com",
    }

    user_repo = UserRepository(test_db)
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await user_repo.add_personal_details(0, details)


@pytest.mark.asyncio
async def test_delete_user_with_invalid_user_id(test_db):
    """Test that invalid user_id raises ValueError in hard_delete."""
    user_repo = UserRepository(test_db)
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await user_repo.hard_delete(-5)


@pytest.mark.asyncio
async def test_valid_user_id_passes_validation(test_db):
    """Test that valid user_id passes validation."""
    # This should not raise an error
    user_repo = UserRepository(test_db)
    user = await user_repo.get_by_id_with_password(1)
    assert user is not None
    assert user["id"] == 1
