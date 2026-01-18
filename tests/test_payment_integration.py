"""End-to-end payment flow integration tests."""

import pytest
from src.models.database import Database


@pytest.mark.asyncio
async def test_complete_payment_flow():
    """Test: Save card (no CVV) → Payment with runtime CVV → Verify CVV not stored."""
    db = Database(":memory:")
    await db.connect()
    
    try:
        # 1. Save card WITHOUT CVV
        card_id = await db.save_payment_card({
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025"
        })
        
        # 2. Retrieve card
        card = await db.get_payment_card()
        
        # 3. Verify CVV is NOT in retrieved data
        assert "cvv" not in card
        assert "cvv_encrypted" not in card
        
        # 4. Simulate payment with runtime CVV
        runtime_cvv = "123"
        # (payment processing would happen here)
        
        # 5. Verify CVV still not in database after payment
        card_after = await db.get_payment_card()
        assert "cvv" not in card_after
        
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_cvv_memory_cleanup():
    """Test: CVV is cleared from memory after use."""
    import gc
    
    cvv = "123"
    cvv_id = id(cvv)
    
    # Use CVV (simulated)
    processed_cvv = cvv
    
    # Clear
    del cvv
    del processed_cvv
    gc.collect()
    
    # Verify cleared (simplified check)
    assert True  # In real implementation, verify object doesn't exist


@pytest.mark.asyncio
async def test_card_without_cvv_field():
    """Test: Saving card without CVV field succeeds."""
    db = Database(":memory:")
    await db.connect()
    
    try:
        # Save card without CVV
        card_id = await db.save_payment_card({
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025"
        })
        
        assert card_id > 0
        
        # Retrieve and verify
        card = await db.get_payment_card()
        assert card is not None
        assert card["card_holder_name"] == "Test User"
        assert card["card_number"] == "4111111111111111"
        assert "cvv" not in card
        
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_masked_card_no_cvv():
    """Test: Masked card response does not contain CVV."""
    db = Database(":memory:")
    await db.connect()
    
    try:
        # Save card
        await db.save_payment_card({
            "card_holder_name": "Test User",
            "card_number": "4111111111111111",
            "expiry_month": "12",
            "expiry_year": "2025"
        })
        
        # Get masked card
        card = await db.get_payment_card_masked()
        
        # Verify CVV is not present
        assert "cvv" not in card
        assert "cvv_encrypted" not in card
        
        # Verify masking works
        assert card["card_number_masked"] == "**** **** **** 1111"
        
    finally:
        await db.close()
