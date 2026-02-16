"""Payment and payment card routes for VFS-Bot web application."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.repositories import AppointmentRequestRepository, PaymentRepository
from web.dependencies import (
    get_appointment_request_repository,
    get_payment_repository,
    verify_jwt_token,
)
from web.models.payment import (
    PaymentCardRequest,
    PaymentCardResponse,
    PaymentInitiateRequest,
)

router = APIRouter(prefix="/payment", tags=["payment"])


@router.get("/payment-card", response_model=Optional[PaymentCardResponse])
async def get_payment_card(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    payment_repo: PaymentRepository = Depends(get_payment_repository),
):
    """
    Get saved payment card (masked) - requires authentication.

    Args:
        token_data: Verified token data
        payment_repo: PaymentRepository instance

    Returns:
        Masked payment card data or None if no card exists
    """
    try:
        card = await payment_repo.get_masked()
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
    payment_repo: PaymentRepository = Depends(get_payment_repository),
):
    """
    Save payment card.

    Note: CVV is NOT stored per PCI-DSS Requirement 3.2.
    Card holder must enter CVV at payment time.

    Validation is automatically handled by Pydantic PaymentCardRequest model:
    - Card number: 13-19 digits, Luhn algorithm validated
    - Cardholder name: 2-100 characters, letters and spaces only
    - Expiry month: 01-12 format
    - Expiry year: YY or YYYY format

    Args:
        card_data: Payment card data (no CVV)
        token_data: Verified token data
        payment_repo: PaymentRepository instance

    Returns:
        Success message with card ID
    """
    try:
        # Build card data dictionary
        card_dict = {
            "card_holder_name": card_data.card_holder_name,
            "card_number": card_data.card_number,
            "expiry_month": card_data.expiry_month,
            "expiry_year": card_data.expiry_year,
        }

        # Repository handles upsert logic (create or update)
        card_id = await payment_repo.create(card_dict)

        logger.info(f"Payment card saved/updated by {token_data.get('sub', 'unknown')}")
        return {
            "success": True,
            "card_id": card_id,
            "message": "Payment card saved successfully",
        }
    except ValueError as e:
        logger.warning("Payment card validation failed for user %s", token_data.get('sub', 'unknown'))
        raise HTTPException(status_code=400, detail="Invalid card data format")
    except Exception as e:
        logger.error(f"Failed to save payment card: {e}")
        raise HTTPException(status_code=500, detail="Failed to save payment card")


@router.delete("/payment-card")
async def delete_payment_card(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    payment_repo: PaymentRepository = Depends(get_payment_repository),
):
    """
    Delete saved payment card - requires authentication.

    Args:
        token_data: Verified token data
        payment_repo: PaymentRepository instance

    Returns:
        Success message
    """
    try:
        deleted = await payment_repo.delete()
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
    payment_repo: PaymentRepository = Depends(get_payment_repository),
    appt_req_repo: AppointmentRequestRepository = Depends(get_appointment_request_repository),
):
    """
    Initiate payment for an appointment.

    NOTE: Payment processing is not yet implemented.
    This endpoint returns 501 until a payment gateway is integrated.
    """
    # Validate appointment exists
    try:
        appointment = await appt_req_repo.get_by_id(request.appointment_id)
        if not appointment:
            raise HTTPException(404, "Appointment not found")

        # Validate card exists
        card = await payment_repo.get()
        if not card:
            raise HTTPException(404, "No payment card saved")

        # Payment processing not yet implemented
        logger.warning(
            f"Payment initiation attempted for appointment {request.appointment_id} "
            "but payment processing is not yet implemented"
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Payment processing is not yet implemented. "
            "This endpoint will be available once a payment gateway is integrated.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        raise HTTPException(500, "Payment processing failed")
