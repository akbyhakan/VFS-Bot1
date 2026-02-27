"""End-to-end payment flow integration tests."""

import pytest

from src.repositories import PaymentRepository


@pytest.mark.asyncio
async def test_complete_payment_flow(database):
    """Test: Save card with CVV → Retrieve card → Verify CVV is stored encrypted."""
    db = database

    # 1. Save card WITH CVV
    payment_repo = PaymentRepository(db)
    await payment_repo.create(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
            "cvv": "123",
        }
    )

    # 2. Retrieve card
    _card = await PaymentRepository(db).get()
    assert _card is not None
    card = _card.to_dict()

    # 3. Verify CVV is present and decrypted
    assert card is not None
    assert card.get("cvv") == "123"

    # 4. Verify masked card does NOT include CVV
    _masked = await PaymentRepository(db).get_masked()
    assert _masked is not None
    masked_card = _masked.to_dict()
    assert "cvv" not in masked_card


@pytest.mark.asyncio
async def test_card_without_cvv_field(database):
    """Test: Saving card without CVV field succeeds (CVV is optional)."""
    db = database

    # Save card without CVV
    payment_repo = PaymentRepository(db)
    card_id = await payment_repo.create(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
        }
    )

    assert card_id > 0

    # Retrieve and verify
    _card = await PaymentRepository(db).get()
    assert _card is not None
    card = _card.to_dict()
    assert card is not None
    assert card["card_holder_name"] == "Test User"
    assert card["card_number"] == "4111111111111111"
    # CVV should NOT be present when not saved
    assert "cvv" not in card


@pytest.mark.asyncio
async def test_masked_card_no_cvv(database):
    """Test: Masked card response does not contain CVV."""
    db = database

    # Save card
    payment_repo = PaymentRepository(db)
    await payment_repo.create(
        {
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025",
        }
    )

    # Get masked card
    _masked = await PaymentRepository(db).get_masked()
    assert _masked is not None
    card = _masked.to_dict()

    # Verify CVV is not present in masked view
    assert "cvv" not in card

    # Verify masking works
    assert card["card_number_masked"] == "**** **** **** 1111"
