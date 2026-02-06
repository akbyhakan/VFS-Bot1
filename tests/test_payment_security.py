"""Tests for payment card security with CVV encryption."""

import pytest
from cryptography.fernet import Fernet

from src.models.database import Database
from src.utils.encryption import reset_encryption


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test and reset global encryption instance."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # Reset global encryption instance to ensure it uses the new key
    reset_encryption()
    yield key
    # Cleanup: reset encryption instance after test
    reset_encryption()


@pytest.fixture
async def test_db(tmp_path, unique_encryption_key):
    """Create a test database."""
    db_path = tmp_path / "test_payment_security.db"
    db = Database(str(db_path))
    await db.connect()
    yield db
    await db.close()


@pytest.mark.asyncio
@pytest.mark.security
async def test_cvv_stored_encrypted_in_database(test_db):
    """
    CVV should be encrypted when stored in the database.

    Note: This is a personal bot where the user stores their own data
    on their own server. CVV is encrypted for automatic payments.
    """
    # Save card WITH CVV
    card_id = await test_db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "123",
        }
    )

    assert card_id > 0

    # Retrieve card
    card = await test_db.get_payment_card()

    assert card is not None
    # Assert CVV is decrypted and available
    assert card["cvv"] == "123"
    assert "cvv_encrypted" not in card  # Encrypted field should be removed

    # Verify card has expected fields
    assert card["card_holder_name"] == "Test User"
    assert card["expiry_month"] == "12"
    assert card["expiry_year"] == "2025"
    # Card number should be decrypted
    assert card["card_number"] == "4111111111111111"


@pytest.mark.asyncio
@pytest.mark.security
async def test_masked_card_no_cvv(test_db):
    """
    Test that masked card endpoint doesn't expose CVV.
    """
    # Save card
    await test_db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "456",
        }
    )

    # Get masked card
    card = await test_db.get_payment_card_masked()

    assert card is not None
    # Assert CVV is not present in masked view
    assert "cvv" not in card
    assert "cvv_encrypted" not in card

    # Verify masking works
    assert card["card_number_masked"] == "**** **** **** 1111"


@pytest.mark.asyncio
@pytest.mark.security
async def test_connection_pool_leak_protection(test_db):
    """
    Connection pool should not leak on exceptions.

    This test ensures that database connections are properly returned
    to the pool even when exceptions occur during operations.
    """
    # Get initial pool size
    initial_available = test_db._available_connections.qsize()

    # Try to perform an operation that will fail
    try:
        async with test_db.get_connection():
            # Simulate an error
            raise Exception("Simulated error")
    except Exception:
        pass

    # Wait a moment for cleanup
    import asyncio

    await asyncio.sleep(0.1)

    # Connection should be returned to pool
    final_available = test_db._available_connections.qsize()
    assert (
        final_available == initial_available
    ), f"Connection pool leaked! Initial: {initial_available}, Final: {final_available}"


@pytest.mark.asyncio
@pytest.mark.security
async def test_card_number_and_cvv_encryption(test_db):
    """
    Test that card numbers and CVV are properly encrypted in the database.
    """
    card_number = "4111111111111111"
    cvv = "789"

    # Save card
    await test_db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": card_number,
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": cvv,
        }
    )

    # Query the database directly to check encryption
    async with test_db.get_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT card_number_encrypted, cvv_encrypted FROM payment_card LIMIT 1"
            )
            row = await cursor.fetchone()

            # The encrypted values should NOT be the plaintext
            assert row["card_number_encrypted"] != card_number
            assert row["cvv_encrypted"] != cvv
            # The encrypted values should be non-empty strings
            assert len(row["card_number_encrypted"]) > 0
            assert len(row["cvv_encrypted"]) > 0


@pytest.mark.asyncio
@pytest.mark.security
async def test_card_update_with_cvv(test_db):
    """
    Test that updating a card with CVV works correctly.
    """
    # Create initial card
    card_id = await test_db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "123",
        }
    )

    # Update card (with new CVV)
    updated_id = await test_db.save_payment_card(
        {
            "card_holder_name": "Updated User",
            "card_number": "4111111111111111",
            "expiry_month": "01",
            "expiry_year": "2026",
            "cvv": "456",
        }
    )

    # Should update the same card
    assert updated_id == card_id

    # Verify update
    card = await test_db.get_payment_card()
    assert card["card_holder_name"] == "Updated User"
    assert card["expiry_month"] == "01"
    assert card["expiry_year"] == "2026"
    assert card["cvv"] == "456"  # CVV should be updated
