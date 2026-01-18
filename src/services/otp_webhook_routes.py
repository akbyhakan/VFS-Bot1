"""FastAPI routes for SMS OTP webhook."""

import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from pydantic import BaseModel, Field

from .otp_webhook import get_otp_service, OTPWebhookService
from ..utils.webhook_utils import verify_webhook_signature

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


async def get_verified_otp_service(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
) -> OTPWebhookService:
    """
    Dependency to verify webhook signature and return OTP service.

    Production mode STRICTLY requires signature verification.
    Development mode also requires signature if SMS_WEBHOOK_SECRET is set.
    """
    webhook_secret = os.getenv("SMS_WEBHOOK_SECRET")
    env = os.getenv("ENV", "production").lower()

    # In production, webhook secret MUST be configured
    if env == "production" and not webhook_secret:
        logger.error("🚨 SMS_WEBHOOK_SECRET not set in production environment")
        raise HTTPException(
            status_code=500,
            detail="SMS_WEBHOOK_SECRET must be configured in production"
        )

    # Signature verification is REQUIRED in production
    if env == "production":
        if not x_webhook_signature:
            logger.warning(f"⚠️ Webhook signature missing in production (IP: {request.client.host if request.client else 'unknown'})")
            raise HTTPException(
                status_code=401,
                detail="X-Webhook-Signature header required in production"
            )

        # Verify signature
        body = await request.body()
        if not verify_webhook_signature(body, x_webhook_signature, webhook_secret):
            logger.error(f"❌ Invalid webhook signature from IP: {request.client.host if request.client else 'unknown'}")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        logger.debug("✅ Webhook signature verified")
    
    # Development mode - still enforce signature if webhook_secret is set
    elif webhook_secret:
        if not x_webhook_signature:
            logger.warning("⚠️ DEV MODE: Webhook signature missing (but secret is configured)")
        else:
            body = await request.body()
            if not verify_webhook_signature(body, x_webhook_signature, webhook_secret):
                logger.warning("⚠️ DEV MODE: Invalid webhook signature (continuing anyway)")
            else:
                logger.debug("✅ DEV MODE: Webhook signature verified")
    else:
        logger.warning("⚠️ DEV MODE: No webhook secret configured - signature validation disabled")

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
