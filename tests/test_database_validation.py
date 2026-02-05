"""Tests for database parameter validation."""

import pytest
from cryptography.fernet import Fernet

from src.models.database import Database


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
async def test_db(tmp_path, unique_encryption_key):
    """Create a test database."""
    db_path = tmp_path / "test_validation.db"
    db = Database(str(db_path))
    await db.connect()

    # Add a test user
    await db.add_user(
        email="test@example.com",
        password="password123",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    yield db
    await db.close()


@pytest.mark.asyncio
async def test_get_user_with_invalid_user_id_negative(test_db):
    """Test that negative user_id raises ValueError."""
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await test_db.get_user_with_decrypted_password(-1)


@pytest.mark.asyncio
async def test_get_user_with_invalid_user_id_zero(test_db):
    """Test that zero user_id raises ValueError."""
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await test_db.get_user_with_decrypted_password(0)


@pytest.mark.asyncio
async def test_get_user_with_invalid_user_id_string(test_db):
    """Test that string user_id raises ValueError."""
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await test_db.get_user_with_decrypted_password("not_an_int")  # type: ignore


@pytest.mark.asyncio
async def test_get_personal_details_with_invalid_user_id(test_db):
    """Test that invalid user_id raises ValueError in get_personal_details."""
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await test_db.get_personal_details(-1)


@pytest.mark.asyncio
async def test_add_personal_details_with_invalid_user_id(test_db):
    """Test that invalid user_id raises ValueError in add_personal_details."""
    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "ABC123",
        "email": "john@example.com",
    }

    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await test_db.add_personal_details(0, details)


@pytest.mark.asyncio
async def test_delete_user_with_invalid_user_id(test_db):
    """Test that invalid user_id raises ValueError in delete_user."""
    with pytest.raises(ValueError, match="Invalid user_id.*Must be a positive integer"):
        await test_db.delete_user(-5)


@pytest.mark.asyncio
async def test_valid_user_id_passes_validation(test_db):
    """Test that valid user_id passes validation."""
    # This should not raise an error
    user = await test_db.get_user_with_decrypted_password(1)
    assert user is not None
    assert user["id"] == 1
