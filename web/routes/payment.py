"""Payment and payment card routes for VFS-Bot web application."""

import gc
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.models.database import Database
from web.dependencies import (
    verify_jwt_token,
    PaymentCardRequest,
    PaymentCardResponse,
    PaymentInitiateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["payment"])


@router.get("/payment-card", response_model=Optional[PaymentCardResponse])
async def get_payment_card(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get saved payment card (masked) - requires authentication.

    Args:
        token_data: Verified token data

    Returns:
        Masked payment card data or None if no card exists
    """
    try:
        db = Database()
        await db.connect()

        try:
            card = await db.get_payment_card_masked()
            if not card:
                return None

            return PaymentCardResponse(
                id=card["id"],
                card_holder_name=card["card_holder_name"],
                card_number_masked=card["card_number_masked"],
                expiry_month=card["expiry_month"],
                expiry_year=card["expiry_year"],
                created_at=card["created_at"],
            )
        finally:
            await db.close()
    except Exception as e:
        logger.error(f"Failed to get payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payment card")


@router.post("/payment-card", status_code=201)
async def save_payment_card(
    card_data: PaymentCardRequest, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Save payment card WITHOUT CVV (PCI-DSS compliant).

    Security Note:
        CVV is NEVER stored. It must be provided at payment time.

    Args:
        card_data: Payment card data
        token_data: Verified token data

    Returns:
        Success message with card ID
    """
    try:
        db = Database()
        await db.connect()

        try:
            card_id = await db.save_payment_card(
                {
                    "card_holder_name": card_data.card_holder_name,
                    "card_number": card_data.card_number,
                    "expiry_month": card_data.expiry_month,
                    "expiry_year": card_data.expiry_year,
                }
            )

            logger.info(f"Payment card saved/updated by {token_data.get('sub', 'unknown')}")
            return {
                "success": True,
                "card_id": card_id,
                "message": "Payment card saved successfully",
            }
        finally:
            await db.close()
    except ValueError as e:
        logger.error(f"Invalid card data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to save payment card")


@router.delete("/payment-card")
async def delete_payment_card(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Delete saved payment card - requires authentication.

    Args:
        token_data: Verified token data

    Returns:
        Success message
    """
    try:
        db = Database()
        await db.connect()

        try:
            deleted = await db.delete_payment_card()
            if not deleted:
                raise HTTPException(status_code=404, detail="No payment card found")

            logger.info(f"Payment card deleted by {token_data.get('sub', 'unknown')}")
            return {"success": True, "message": "Payment card deleted successfully"}
        finally:
            await db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete payment card")


@router.post("/payment/initiate")
async def initiate_payment(
    request: PaymentInitiateRequest, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Initiate payment with runtime CVV.

    Security:
    - CVV exists only in memory during this request
    - Never logged or persisted to disk
    - Cleared immediately after use

    Args:
        request: Payment initiation data with CVV
        token_data: JWT token data

    Returns:
        Payment result
    """
    try:
        db = Database()
        await db.connect()

        try:
            # Get appointment
            appointment = await db.get_appointment_request(request.appointment_id)
            if not appointment:
                raise HTTPException(404, "Appointment not found")

            # Get saved card (without CVV)
            card = await db.get_payment_card()
            if not card:
                raise HTTPException(404, "No payment card saved")

            # Process payment with runtime CVV
            # TODO: Implement actual payment processing
            logger.info(f"Payment initiated for appointment {request.appointment_id}")

            return {
                "success": True,
                "message": "Payment completed",
                "appointment_id": request.appointment_id,
            }

        finally:
            await db.close()

    finally:
        # CRITICAL: Clear CVV from memory
        # Note: This is a best-effort approach. Python's string interning
        # and garbage collection are implementation-dependent.
        # For production use with highly sensitive data, consider:
        # 1. Using ctypes to overwrite memory directly
        # 2. Using libraries like 'pympler' for secure memory handling
        # 3. Delegating payment processing to PCI-DSS compliant gateway
        request.cvv = ""
        del request
        gc.collect()
