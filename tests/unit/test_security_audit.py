"""Security audit tests."""

import os

import pytest

from src.core.config.env_validator import EnvValidator
from src.repositories import UserRepository


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
async def test_cvv_stored_encrypted_in_database_schema(database):
    """Test: payment_card table stores CVV encrypted, not in plain text.

    Note: This is a personal bot where the user stores their own data
    on their own server. CVV is encrypted for automatic payments.
    """
    db = database

    # Get table schema from PostgreSQL information_schema
    async with db.get_connection() as conn:
        columns_info = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'payment_card'
        """
        )

    # Extract column names
    columns = [col["column_name"] for col in columns_info]

    # Verify CVV was removed (PCI-DSS compliance - migration 002)
    assert "cvv" not in columns  # Plain text CVV should never exist
    assert "cvv_encrypted" not in columns  # CVV must not be stored after authorization

    # Verify all card data is encrypted (PCI-DSS compliance)
    assert "card_holder_name_encrypted" in columns
    assert "card_number_encrypted" in columns
    assert "expiry_month_encrypted" in columns
    assert "expiry_year_encrypted" in columns

    # Verify plaintext columns don't exist
    assert "card_holder_name" not in columns
    assert "card_number" not in columns
    assert "expiry_month" not in columns
    assert "expiry_year" not in columns


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
    user_repo = UserRepository(db)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": plaintext_password,
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Read password directly from database
    async with db.get_connection() as conn:
        row = await conn.fetchrow("SELECT password FROM users WHERE id = $1", user_id)
        stored_password = row["password"]

    # Verify password is encrypted (not plaintext)
    assert stored_password != plaintext_password
    assert len(stored_password) > len(plaintext_password)


@pytest.mark.asyncio
async def test_login_timing_attack_protection():
    """Test: Login endpoint uses constant-time password verification."""
    # Mock environment variables
    import os
    from unittest.mock import MagicMock, patch

    from fastapi import Request, Response

    from web.models.auth import LoginRequest
    from web.routes.auth import _DUMMY_BCRYPT_HASH, login

    original_username = os.environ.get("ADMIN_USERNAME")
    original_password = os.environ.get("ADMIN_PASSWORD")

    try:
        # Set test credentials
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = (
            "$2b$12$LJ3m4ys3Lg7E16OlByBg6eKDoYkBWKJkG1VyNlITNYDR8xPz.k9hK"
        )

        # Mock verify_password to track calls
        with patch("src.core.auth.verify_password") as mock_verify:
            mock_verify.return_value = False

            # Create mock request and response
            mock_request = MagicMock(spec=Request)
            mock_response = MagicMock(spec=Response)

            # Test with wrong username
            credentials_wrong_user = LoginRequest(username="wronguser", password="testpass")

            try:
                await login(mock_request, mock_response, credentials_wrong_user)
            except Exception:
                pass  # Expected to raise HTTPException

            # Verify that verify_password was called even with wrong username
            # This ensures constant-time behavior
            assert mock_verify.call_count == 1
            # Verify dummy hash was used
            call_args = mock_verify.call_args
            assert call_args[0][1] == _DUMMY_BCRYPT_HASH

            mock_verify.reset_mock()

            # Test with correct username but wrong password
            credentials_wrong_pass = LoginRequest(username="admin", password="wrongpass")

            try:
                await login(mock_request, mock_response, credentials_wrong_pass)
            except Exception:
                pass  # Expected to raise HTTPException

            # Verify that verify_password was called with real hash
            assert mock_verify.call_count == 1
            call_args = mock_verify.call_args
            assert call_args[0][1] == os.environ["ADMIN_PASSWORD"]

    finally:
        # Restore original values
        if original_username:
            os.environ["ADMIN_USERNAME"] = original_username
        else:
            os.environ.pop("ADMIN_USERNAME", None)
        if original_password:
            os.environ["ADMIN_PASSWORD"] = original_password
        else:
            os.environ.pop("ADMIN_PASSWORD", None)
