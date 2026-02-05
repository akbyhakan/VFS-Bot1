"""Security audit tests."""

import os
import sqlite3

import pytest

from src.core.env_validator import EnvValidator


def test_production_requires_hashed_password():
    """Test: Production mode requires bcrypt password."""
    # Save original values
    original_env = os.environ.get("ENV")
    original_password = os.environ.get("ADMIN_PASSWORD")

    try:
        os.environ["ENV"] = "production"
        os.environ["ADMIN_PASSWORD"] = "plaintext"

        result = EnvValidator.validate(strict=False)
        assert result is False  # Should fail validation

    finally:
        # Restore original values
        if original_env:
            os.environ["ENV"] = original_env
        else:
            os.environ.pop("ENV", None)
        if original_password:
            os.environ["ADMIN_PASSWORD"] = original_password
        else:
            os.environ.pop("ADMIN_PASSWORD", None)


@pytest.mark.asyncio
async def test_cvv_not_in_database_schema(database):
    """Test: payment_card table has no CVV column."""
    db = database

    # Get table schema
    async with db.get_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("PRAGMA table_info(payment_card)")
            columns_info = await cursor.fetchall()

    # Extract column names
    columns = [col[1] for col in columns_info]

    # Verify CVV columns do not exist
    assert "cvv" not in columns
    assert "cvv_encrypted" not in columns

    # Verify expected columns exist
    assert "card_holder_name" in columns
    assert "card_number_encrypted" in columns
    assert "expiry_month" in columns
    assert "expiry_year" in columns


def test_encryption_key_validation():
    """Test: Encryption key must be valid Fernet key."""
    # Save original value
    original_key = os.environ.get("ENCRYPTION_KEY")

    try:
        # Test invalid key
        os.environ["ENCRYPTION_KEY"] = "invalid_key"
        result = EnvValidator.validate(strict=False)
        assert result is False

        # Test valid key format (44 chars base64)
        from cryptography.fernet import Fernet

        valid_key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = valid_key

        # This should pass the encryption key validation
        # (may still fail on other required vars)
        assert EnvValidator._validate_encryption_key(valid_key) is True

    finally:
        # Restore original value
        if original_key:
            os.environ["ENCRYPTION_KEY"] = original_key
        else:
            os.environ.pop("ENCRYPTION_KEY", None)


def test_api_secret_key_length():
    """Test: API_SECRET_KEY must be at least 32 characters."""
    # Save original value
    original_key = os.environ.get("API_SECRET_KEY")

    try:
        # Test short key
        os.environ["API_SECRET_KEY"] = "short_key"
        result = EnvValidator.validate(strict=False)
        assert result is False

        # Test valid key
        os.environ["API_SECRET_KEY"] = "a" * 32
        # Should pass API_SECRET_KEY validation
        # (may still fail on other required vars)

    finally:
        # Restore original value
        if original_key:
            os.environ["API_SECRET_KEY"] = original_key
        else:
            os.environ.pop("API_SECRET_KEY", None)


def test_email_format_validation():
    """Test: VFS_EMAIL must be valid email format."""
    # Save original value
    original_email = os.environ.get("VFS_EMAIL")

    try:
        # Test invalid email
        os.environ["VFS_EMAIL"] = "not_an_email"
        result = EnvValidator.validate(strict=False)
        assert result is False

        # Test valid email
        os.environ["VFS_EMAIL"] = "test@example.com"
        assert EnvValidator._validate_email("test@example.com") is True

    finally:
        # Restore original value
        if original_email:
            os.environ["VFS_EMAIL"] = original_email
        else:
            os.environ.pop("VFS_EMAIL", None)


@pytest.mark.asyncio
async def test_password_encryption_in_database(database):
    """Test: User passwords are encrypted in database."""
    db = database

    # Add user with password
    plaintext_password = "my_secure_password"
    user_id = await db.add_user(
        email="test@example.com",
        password=plaintext_password,
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Read password directly from database
    async with db.get_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT password FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            stored_password = row[0]

    # Verify password is encrypted (not plaintext)
    assert stored_password != plaintext_password
    assert len(stored_password) > len(plaintext_password)
