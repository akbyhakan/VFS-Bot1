"""FastAPI routes for SMS OTP webhook."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from .otp_webhook import OTPWebhookService, get_otp_service

router = APIRouter(prefix="/api/webhook", tags=["webhook-sms"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


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


# WARNING: This function is a deliberate duplicate of web.dependencies.verify_webhook_request
# due to circular import constraints.
async def verify_webhook_signature_local(request: Request) -> None:
    """
    Local webhook verification dependency (no-op for localhost usage).
    """
    pass


async def get_verified_otp_service() -> OTPWebhookService:
    """
    Dependency to return OTP service.

    Note: Webhook signature verification is now handled separately.
    This function now only returns the OTP service.
    """
    return get_otp_service()


@router.post("/sms/appointment", response_model=OTPResponse)
@limiter.limit("60/minute")
async def receive_appointment_sms(
    request: Request,
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
@limiter.limit("60/minute")
async def receive_payment_sms(
    request: Request,
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
@limiter.limit("10/minute")
async def wait_for_otp(
    request: Request,
    phone: Optional[str] = None,
    timeout: int = 120,
    otp_service: OTPWebhookService = Depends(get_verified_otp_service),
    _: None = Depends(verify_webhook_signature_local),
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
        return OTPResponse(success=True, otp=f"{otp[:2]}****", message="OTP retrieved")
    else:
        return OTPResponse(success=False, message="OTP wait timeout")
