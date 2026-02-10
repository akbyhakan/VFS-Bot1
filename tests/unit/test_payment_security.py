"""Tests for payment card security."""

import os

import pytest
from cryptography.fernet import Fernet

from src.constants import Database as DbConstants
from src.models.database import Database
from src.repositories import PaymentRepository
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
async def test_db(unique_encryption_key):
    """Create a test database."""
    database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
    db = Database(database_url=database_url)
    await db.connect()
    yield db
    await db.close()


@pytest.mark.asyncio
@pytest.mark.security
async def test_card_stored_without_cvv(test_db):
    """
    CVV should NOT be stored per PCI-DSS Requirement 3.2.

    Card holder must enter CVV at payment time.
    """
    # Save card WITHOUT CVV
    payment_repo = PaymentRepository(test_db)
    card_id = await payment_repo.create({
        "card_holder_name": "Test User",
        "card_number": "4111111111111111",
        "expiry_month": "12",
        "expiry_year": "2025",
    })

    assert card_id > 0

    # Retrieve card
    card = await test_db.get_payment_card()

    assert card is not None
    # Assert CVV is NOT present (PCI-DSS compliance)
    assert "cvv" not in card
    assert "cvv_encrypted" not in card

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
    payment_repo = PaymentRepository(test_db)
    await payment_repo.create({
        "card_holder_name": "Test User",
        "card_number": "4111111111111111",
        "expiry_month": "12",
        "expiry_year": "2025",
    })

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
async def test_card_number_encryption(test_db):
    """
    Test that card numbers are properly encrypted in the database.
    """
    card_number = "4111111111111111"

    # Save card
    payment_repo = PaymentRepository(test_db)
    await payment_repo.create({
        "card_holder_name": "Test User",
        "card_number": card_number,
        "expiry_month": "12",
        "expiry_year": "2025",
    })

    # Query the database directly to check encryption
    async with test_db.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT card_number_encrypted FROM payment_card LIMIT 1"
        )

        # The encrypted value should NOT be the plaintext
        assert row["card_number_encrypted"] != card_number
        # The encrypted value should be a non-empty string
        assert len(row["card_number_encrypted"]) > 0


@pytest.mark.asyncio
@pytest.mark.security
async def test_card_update(test_db):
    """
    Test that updating a card works correctly.
    """
    # Create initial card
    payment_repo = PaymentRepository(test_db)
    card_id = await payment_repo.create({
        "card_holder_name": "Test User",
        "card_number": "4111111111111111",
        "expiry_month": "12",
        "expiry_year": "2025",
    })

    # Update card
    updated_id = await payment_repo.create({
        "card_holder_name": "Updated User",
        "card_number": "4111111111111111",
        "expiry_month": "01",
        "expiry_year": "2026",
    })

    # Should update the same card
    assert updated_id == card_id

    # Verify update
    card = await test_db.get_payment_card()
    assert card["card_holder_name"] == "Updated User"
    assert card["expiry_month"] == "01"
    assert card["expiry_year"] == "2026"
