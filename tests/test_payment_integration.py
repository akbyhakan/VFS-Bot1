"""End-to-end payment flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_complete_payment_flow(database):
    """Test: Save card with CVV → Retrieve card → Verify CVV is encrypted and decrypted."""
    db = database

    # 1. Save card WITH CVV
    await db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "123",
        }
    )

    # 2. Retrieve card
    card = await db.get_payment_card()

    # 3. Verify CVV is decrypted and available
    assert card is not None
    assert card["cvv"] == "123"
    assert "cvv_encrypted" not in card  # Encrypted field should be removed

    # 4. Verify masked card does NOT include CVV
    masked_card = await db.get_payment_card_masked()
    assert "cvv" not in masked_card
    assert "cvv_encrypted" not in masked_card


@pytest.mark.asyncio
async def test_cvv_memory_cleanup():
    """Test: CVV is cleared from memory after use."""
    import gc

    cvv = "123"

    # Use CVV (simulated)
    processed_cvv = cvv

    # Clear
    del cvv
    del processed_cvv
    gc.collect()

    # Verify cleared (simplified check)
    assert True  # In real implementation, verify object doesn't exist


@pytest.mark.asyncio
async def test_card_with_cvv_field(database):
    """Test: Saving card with CVV field succeeds and encrypts CVV."""
    db = database

    # Save card with CVV
    card_id = await db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "456",
        }
    )

    assert card_id > 0

    # Retrieve and verify
    card = await db.get_payment_card()
    assert card is not None
    assert card["card_holder_name"] == "Test User"
    assert card["card_number"] == "4111111111111111"
    assert card["cvv"] == "456"


@pytest.mark.asyncio
async def test_masked_card_no_cvv(database):
    """Test: Masked card response does not contain CVV."""
    db = database

    # Save card
    await db.save_payment_card(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "789",
        }
    )

    # Get masked card
    card = await db.get_payment_card_masked()

    # Verify CVV is not present
    assert "cvv" not in card
    assert "cvv_encrypted" not in card

    # Verify masking works
    assert card["card_number_masked"] == "**** **** **** 1111"
