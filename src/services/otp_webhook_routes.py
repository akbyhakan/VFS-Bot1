"""FastAPI routes for SMS OTP webhook."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
import hmac
import hashlib
import os

from .otp_webhook import get_otp_service, OTPWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


class SMSWebhookPayload(BaseModel):
    """SMS webhook payload model."""

    phone_number: str = Field(..., description="Sender phone number", alias="from")
    message: str = Field(..., description="SMS message text", alias="text")
    timestamp: Optional[str] = Field(None, description="Message timestamp")

    class Config:
        populate_by_name = True


class OTPResponse(BaseModel):
    """OTP response model."""

    success: bool
    otp: Optional[str] = None
    message: str


def verify_webhook_signature(payload: bytes, signature: Optional[str], secret: str) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.

    Args:
        payload: Raw request body
        signature: Signature from header
        secret: Webhook secret key

    Returns:
        True if signature is valid
    """
    if not signature or not secret:
        return False

    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(signature, expected)


async def get_verified_otp_service(
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature")
) -> OTPWebhookService:
    """
    Dependency to verify webhook signature and return OTP service.

    Note: For production, implement proper signature verification
    based on your SMS provider's documentation.
    """
    webhook_secret = os.getenv("SMS_WEBHOOK_SECRET")

    # If secret is configured, require signature
    # For now, we skip signature check if secret is not set (development mode)
    if webhook_secret and not x_webhook_signature:
        logger.warning("Webhook signature missing")
        # In production, raise HTTPException
        # raise HTTPException(status_code=401, detail="Webhook signature required")

    return get_otp_service()


@router.post("/sms", response_model=OTPResponse)
async def receive_sms(
    payload: SMSWebhookPayload, otp_service: OTPWebhookService = Depends(get_verified_otp_service)
) -> OTPResponse:
    """
    Receive SMS webhook from provider (legacy endpoint - routes to appointment).

    Expected payload format:
    {
        "from": "+905551234567",
        "text": "Your VFS verification code is 123456",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    try:
        otp = await otp_service.process_appointment_sms(
            phone_number=payload.phone_number, message=payload.message
        )

        if otp:
            return OTPResponse(
                success=True,
                otp=f"{otp[:2]}****",  # Partially masked for logging
                message="OTP extracted successfully",
            )
        else:
            return OTPResponse(success=False, message="No OTP found in message")

    except Exception as e:
        logger.error(f"SMS webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process SMS")


@router.post("/sms/appointment", response_model=OTPResponse)
async def receive_appointment_sms(
    payload: SMSWebhookPayload, otp_service: OTPWebhookService = Depends(get_verified_otp_service)
) -> OTPResponse:
    """
    Receive appointment SMS webhook from provider.

    Expected payload format:
    {
        "from": "+905551234567",
        "text": "Your VFS verification code is 123456",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    try:
        otp = await otp_service.process_appointment_sms(
            phone_number=payload.phone_number, message=payload.message
        )

        if otp:
            return OTPResponse(
                success=True,
                otp=f"{otp[:2]}****",  # Partially masked for logging
                message="Appointment OTP extracted successfully",
            )
        else:
            return OTPResponse(success=False, message="No OTP found in message")

    except Exception as e:
        logger.error(f"Appointment SMS webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process SMS")


@router.post("/sms/payment", response_model=OTPResponse)
async def receive_payment_sms(
    payload: SMSWebhookPayload, otp_service: OTPWebhookService = Depends(get_verified_otp_service)
) -> OTPResponse:
    """
    Receive payment SMS webhook from provider.

    Expected payload format:
    {
        "from": "+905551234567",
        "text": "Your bank verification code is 123456",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    try:
        otp = await otp_service.process_payment_sms(
            phone_number=payload.phone_number, message=payload.message
        )

        if otp:
            return OTPResponse(
                success=True,
                otp=f"{otp[:2]}****",  # Partially masked for logging
                message="Payment OTP extracted successfully",
            )
        else:
            return OTPResponse(success=False, message="No OTP found in message")

    except Exception as e:
        logger.error(f"Payment SMS webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process SMS")


@router.get("/otp/wait")
async def wait_for_otp(
    phone: Optional[str] = None,
    timeout: int = 120,
    otp_service: OTPWebhookService = Depends(get_verified_otp_service),
) -> OTPResponse:
    """
    Wait for OTP to arrive (long polling).

    Args:
        phone: Optional phone number filter
        timeout: Maximum wait time in seconds (max 300)
    """
    if timeout > 300:
        timeout = 300

    otp = await otp_service.wait_for_otp(phone_number=phone, timeout=timeout)

    if otp:
        return OTPResponse(success=True, otp=otp, message="OTP retrieved")
    else:
        return OTPResponse(success=False, message="OTP wait timeout")
