"""Payment and payment card routes for VFS-Bot web application."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.models.database import Database
from web.dependencies import (
    PaymentCardRequest,
    PaymentCardResponse,
    PaymentInitiateRequest,
    get_db,
    verify_jwt_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["payment"])


@router.get("/payment-card", response_model=Optional[PaymentCardResponse])
async def get_payment_card(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Get saved payment card (masked) - requires authentication.

    Args:
        token_data: Verified token data
        db: Database instance

    Returns:
        Masked payment card data or None if no card exists
    """
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
    except Exception as e:
        logger.error(f"Failed to get payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payment card")


@router.post("/payment-card", status_code=201)
async def save_payment_card(
    card_data: PaymentCardRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Save payment card with CVV.

    Note: This is a personal bot where the user stores their own data
    on their own server. CVV is encrypted and stored for automatic payments.

    Args:
        card_data: Payment card data including CVV
        token_data: Verified token data
        db: Database instance

    Returns:
        Success message with card ID
    """
    try:
        card_id = await db.save_payment_card(
            {
                "card_holder_name": card_data.card_holder_name,
                "card_number": card_data.card_number,
                "expiry_month": card_data.expiry_month,
                "expiry_year": card_data.expiry_year,
                "cvv": card_data.cvv,
            }
        )

        logger.info(f"Payment card saved/updated by {token_data.get('sub', 'unknown')}")
        return {
            "success": True,
            "card_id": card_id,
            "message": "Payment card saved successfully",
        }
    except ValueError as e:
        logger.error(f"Invalid card data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to save payment card")


@router.delete("/payment-card")
async def delete_payment_card(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Delete saved payment card - requires authentication.

    Args:
        token_data: Verified token data
        db: Database instance

    Returns:
        Success message
    """
    try:
        deleted = await db.delete_payment_card()
        if not deleted:
            raise HTTPException(status_code=404, detail="No payment card found")

        logger.info(f"Payment card deleted by {token_data.get('sub', 'unknown')}")
        return {"success": True, "message": "Payment card deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete payment card")


@router.post("/payment/initiate")
async def initiate_payment(
    request: PaymentInitiateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    db: Database = Depends(get_db),
):
    """
    Initiate payment with CVV from database.

    Note: CVV is retrieved from encrypted database storage for automatic payments.

    Args:
        request: Payment initiation data with appointment_id
        token_data: JWT token data
        db: Database instance

    Returns:
        Payment result
    """
    try:
        # Get appointment
        appointment = await db.get_appointment_request(request.appointment_id)
        if not appointment:
            raise HTTPException(404, "Appointment not found")

        # Get saved card with decrypted CVV
        card = await db.get_payment_card()
        if not card:
            raise HTTPException(404, "No payment card saved")

        if not card.get("cvv"):
            raise HTTPException(400, "CVV not found in saved card")

        # Process payment with CVV from database
        # TODO: Implement actual payment processing
        logger.info(f"Payment initiated for appointment {request.appointment_id}")

        return {
            "success": True,
            "message": "Payment completed",
            "appointment_id": request.appointment_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        raise HTTPException(500, "Payment processing failed")
