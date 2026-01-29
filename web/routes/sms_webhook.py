"""Dynamic SMS webhook routes for VFS accounts.

This module provides webhook endpoints for receiving SMS OTP messages
via SMS Forwarder app. Each VFS account has a unique webhook URL.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.services.webhook_token_manager import WebhookTokenManager, SMSPayloadParser

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/webhook/sms", tags=["SMS Webhook"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Global webhook token manager (will be initialized by OTPManager)
_webhook_manager: WebhookTokenManager = None


def set_webhook_manager(manager: WebhookTokenManager):
    """
    Set the global webhook token manager.
    
    Args:
        manager: WebhookTokenManager instance
    """
    global _webhook_manager
    _webhook_manager = manager
    logger.info("Webhook manager set for SMS webhook routes")


def get_webhook_manager() -> WebhookTokenManager:
    """
    Get the webhook token manager instance.
    
    Returns:
        WebhookTokenManager instance
        
    Raises:
        RuntimeError: If manager not initialized
    """
    if _webhook_manager is None:
        raise RuntimeError("Webhook manager not initialized. Call set_webhook_manager first.")
    return _webhook_manager


@router.post("/{token}")
@limiter.limit("60/minute")
async def receive_sms(token: str, request: Request):
    """
    Receive SMS from SMS Forwarder app.
    
    Supported payload formats:
    1. SMS Forwarder (Android):
       {"message": "OTP: 123456", "from": "+905551234567", "timestamp": "..."}
    
    2. Alternative format:
       {"text": "OTP: 123456", "phone": "+905551234567"}
    
    3. Simple format:
       {"body": "OTP: 123456"}
    
    Args:
        token: Unique webhook token
        request: FastAPI request object
        
    Returns:
        Success response with extracted OTP
        
    Raises:
        HTTPException: On validation or processing errors
    """
    try:
        # Get webhook manager
        manager = get_webhook_manager()
        
        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse request body: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Validate token and process SMS
        try:
            otp = manager.process_sms(token, body)
        except ValueError as e:
            logger.warning(f"Token validation failed: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        
        # Get webhook token details
        webhook_token = manager.validate_token(token)
        
        if not otp:
            logger.warning(
                f"No OTP extracted from SMS for account {webhook_token.account_id}"
            )
            # Still return success as SMS was received
            return {
                "status": "received",
                "account_id": webhook_token.account_id,
                "otp_extracted": False,
                "message": "SMS received but no OTP found"
            }
        
        # If there's a linked session, notify it via OTP manager
        if webhook_token.session_id:
            try:
                # Import here to avoid circular dependency
                from src.services.otp_webhook import get_otp_service
                otp_service = get_otp_service()
                
                # Process OTP for the session
                # Use account_id as identifier to route to correct session
                await otp_service.process_appointment_sms(
                    phone_number=f"webhook_{webhook_token.account_id}",
                    message=otp
                )
                
                logger.info(
                    f"OTP delivered to session {webhook_token.session_id} "
                    f"for account {webhook_token.account_id}"
                )
            except Exception as e:
                logger.error(f"Failed to notify session: {e}", exc_info=True)
                # Continue anyway as we successfully extracted OTP
        
        return {
            "status": "success",
            "account_id": webhook_token.account_id,
            "otp_extracted": True,
            "session_id": webhook_token.session_id,
            "message": "OTP received and processed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing SMS webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{token}/status")
@limiter.limit("60/minute")
async def webhook_status(token: str, request: Request):
    """
    Check webhook token status.
    
    Args:
        token: Webhook token
        request: FastAPI request object
        
    Returns:
        Token status information
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        manager = get_webhook_manager()
        
        webhook_token = manager.validate_token(token)
        
        if not webhook_token:
            raise HTTPException(status_code=404, detail="Invalid or inactive token")
        
        return {
            "status": "active",
            "account_id": webhook_token.account_id,
            "phone_number": webhook_token.phone_number,
            "webhook_url": webhook_token.webhook_url,
            "created_at": webhook_token.created_at.isoformat(),
            "last_used_at": (
                webhook_token.last_used_at.isoformat()
                if webhook_token.last_used_at
                else None
            ),
            "session_linked": webhook_token.session_id is not None,
            "session_id": webhook_token.session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking webhook status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{token}/test")
@limiter.limit("10/minute")
async def test_webhook(token: str, request: Request):
    """
    Test webhook connection without processing OTP.
    
    Useful for verifying webhook setup in SMS Forwarder app.
    
    Args:
        token: Webhook token
        request: FastAPI request object
        
    Returns:
        Test success response
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        manager = get_webhook_manager()
        
        webhook_token = manager.validate_token(token)
        
        if not webhook_token:
            raise HTTPException(status_code=404, detail="Invalid or inactive token")
        
        # Parse body to validate format
        try:
            body = await request.json()
            # Try to parse as SMS payload
            sms_payload = SMSPayloadParser.parse(body)
            
            return {
                "status": "test_success",
                "message": "Webhook is correctly configured",
                "account_id": webhook_token.account_id,
                "parsed_message": sms_payload.message[:100],  # Truncate for safety
                "parsed_phone": sms_payload.phone_number,
                "note": "This is a test - OTP was NOT processed"
            }
            
        except ValueError as e:
            # Payload parsing failed
            raise HTTPException(
                status_code=400,
                detail=f"Invalid SMS payload format: {str(e)}"
            )
        except Exception:
            # No body provided or invalid JSON - that's OK for test
            return {
                "status": "test_success",
                "message": "Webhook is reachable",
                "account_id": webhook_token.account_id,
                "note": "Send a proper SMS payload to verify format"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
