"""Webhook OTP receiver route for per-user webhooks (webhook signature-protected)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from src.repositories import WebhookRepository
from src.services.otp_manager.otp_webhook import get_otp_service
from web.dependencies import (
    get_webhook_repository,
    verify_webhook_request,
)

router = APIRouter(prefix="/api/webhook", tags=["webhook-otp"])

# OTP field priority order for webhook payloads
OTP_FIELD_PRIORITY = ["message", "otp", "body", "text"]
PHONE_FIELD_PRIORITY = ["phone", "from", "phone_number"]


@router.post("/otp/{token}")
async def receive_otp(
    token: str,
    request: Request,
    body: dict,
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
    _: None = Depends(verify_webhook_request),
):
    """
    Receive OTP via user-specific webhook.

    Args:
        token: Unique webhook token
        request: FastAPI request object
        body: Request body containing OTP data
        webhook_repo: WebhookRepository instance

    Returns:
        Success message with user_id

    Raises:
        HTTPException: If token is invalid or signature verification fails
    """
    try:
        # Find user by webhook token
        user = await webhook_repo.get_user_by_token(token)
        if not user:
            raise HTTPException(status_code=404, detail="Invalid webhook token")

        # Extract OTP from various possible fields (in priority order)
        otp_code = next((body.get(field) for field in OTP_FIELD_PRIORITY if body.get(field)), None)
        phone_number = next(
            (body.get(field) for field in PHONE_FIELD_PRIORITY if body.get(field)), ""
        )

        if not otp_code:
            raise HTTPException(status_code=400, detail="No OTP found in request body")

        # Get OTP service and process the SMS for this user
        otp_service = get_otp_service()

        # Store OTP with user_id as identifier for lookup
        # Format: user_{user_id}_{phone_number} to ensure uniqueness per user
        phone_identifier = f"user_{user['id']}_{phone_number}"
        await otp_service.process_appointment_sms(
            phone_number=phone_identifier, message=str(otp_code)
        )

        logger.info(f"OTP received for user {user['id']} via webhook: {str(otp_code)[:2]}****")

        return {
            "status": "received",
            "user_id": user["id"],
            "message": "OTP processed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing OTP webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process OTP")
