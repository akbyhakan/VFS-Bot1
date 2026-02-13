"""FastAPI routes for SMS OTP webhook."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from src.core.environment import Environment
from src.utils.webhook_utils import verify_webhook_signature

from .otp_webhook import OTPWebhookService, get_otp_service

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


async def verify_webhook_signature_local(request: Request) -> None:
    """
    Local webhook signature verification dependency.
    
    This is a duplicate of verify_webhook_request from web.dependencies
    to avoid circular import issues.
    
    - Production: SMS_WEBHOOK_SECRET required, signature required, reject on failure
    - Development: If secret configured, signature required and verified (reject on failure)
    - Development without secret: Warning log, bypass
    
    Raises:
        HTTPException: If signature verification fails or secret is not configured in production
    """
    webhook_secret = os.getenv("SMS_WEBHOOK_SECRET")
    
    # Production mode: secret is REQUIRED
    if Environment.is_production() and not webhook_secret:
        logger.error("SMS_WEBHOOK_SECRET not configured in production")
        raise HTTPException(
            status_code=500,
            detail="SMS_WEBHOOK_SECRET must be configured in production"
        )
    
    # If secret is configured, verify signature
    if webhook_secret:
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            logger.warning("Missing X-Webhook-Signature header")
            raise HTTPException(
                status_code=401,
                detail="Missing webhook signature"
            )
        
        # Get raw body for signature verification
        body = await request.body()
        if not verify_webhook_signature(body, signature, webhook_secret):
            logger.error("Invalid webhook signature")
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
        
        logger.debug(f"Webhook signature verified (ENV: {Environment.current()})")
    
    elif Environment.is_development():
        # Development mode without secret: log warning but allow
        logger.warning(
            "DEVELOPMENT MODE: No SMS_WEBHOOK_SECRET configured - "
            "signature validation disabled. DO NOT use in production!"
        )


async def get_verified_otp_service() -> OTPWebhookService:
    """
    Dependency to return OTP service.
    
    Note: Webhook signature verification is now handled separately.
    This function now only returns the OTP service.
    """
    return get_otp_service()


@router.post("/sms", response_model=OTPResponse)
async def receive_sms(
    payload: SMSWebhookPayload,
    otp_service: OTPWebhookService = Depends(get_verified_otp_service),
    _: None = Depends(verify_webhook_signature_local),
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
    payload: SMSWebhookPayload,
    otp_service: OTPWebhookService = Depends(get_verified_otp_service),
    _: None = Depends(verify_webhook_signature_local),
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
    payload: SMSWebhookPayload,
    otp_service: OTPWebhookService = Depends(get_verified_otp_service),
    _: None = Depends(verify_webhook_signature_local),
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
