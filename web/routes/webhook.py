"""Webhook management routes for per-user OTP webhooks."""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from src.models.database import Database
from web.dependencies import verify_jwt_token
from src.services.otp_webhook import get_otp_service
from src.utils.webhook_utils import verify_webhook_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])

# OTP field priority order for webhook payloads
OTP_FIELD_PRIORITY = ["message", "otp", "body", "text"]
PHONE_FIELD_PRIORITY = ["phone", "from", "phone_number"]


@router.post("/users/{user_id}/create")
async def create_webhook(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Create a unique webhook for a user.

    Args:
        user_id: User ID
        token_data: Verified token data

    Returns:
        Webhook token and URL

    Raises:
        HTTPException: If user already has a webhook or creation fails
    """
    db = Database()
    try:
        await db.connect()

        # Verify user exists
        async with db.get_connection() as conn:
            cursor = await conn.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            user = await cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

        # Check if webhook already exists
        existing = await db.get_user_webhook(user_id)
        if existing:
            raise HTTPException(status_code=400, detail="User already has a webhook")

        # Create webhook
        token = await db.create_user_webhook(user_id)
        webhook_url = f"/api/webhook/otp/{token}"

        logger.info(f"Webhook created for user {user_id} by {token_data.get('sub', 'unknown')}")

        return {
            "token": token,
            "webhook_url": webhook_url,
            "message": "Webhook created successfully"
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create webhook")
    finally:
        await db.close()


@router.get("/users/{user_id}")
async def get_webhook(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Get webhook information for a user.

    Args:
        user_id: User ID
        token_data: Verified token data

    Returns:
        Webhook data or null if not found
    """
    db = Database()
    try:
        await db.connect()

        webhook = await db.get_user_webhook(user_id)
        
        if not webhook:
            return {"webhook": None}

        return {
            "webhook": {
                "token": webhook["webhook_token"],
                "webhook_url": f"/api/webhook/otp/{webhook['webhook_token']}",
                "created_at": webhook["created_at"]
            }
        }

    except Exception as e:
        logger.error(f"Error getting webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get webhook")
    finally:
        await db.close()


@router.delete("/users/{user_id}")
async def delete_webhook(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Delete a user's webhook.

    Args:
        user_id: User ID
        token_data: Verified token data

    Returns:
        Success message

    Raises:
        HTTPException: If webhook not found
    """
    db = Database()
    try:
        await db.connect()

        success = await db.delete_user_webhook(user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Webhook not found")

        logger.info(f"Webhook deleted for user {user_id} by {token_data.get('sub', 'unknown')}")

        return {"message": "Webhook deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete webhook")
    finally:
        await db.close()


@router.post("/otp/{token}")
async def receive_otp(token: str, request: Request, body: dict):
    """
    Receive OTP via user-specific webhook.

    Args:
        token: Unique webhook token
        request: FastAPI request object
        body: Request body containing OTP data

    Returns:
        Success message with user_id

    Raises:
        HTTPException: If token is invalid or signature verification fails
    """
    # Get webhook secret from environment
    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    
    # Verify webhook signature if secret is configured
    if webhook_secret:
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            logger.warning(f"Webhook request without signature for token {token[:8]}...")
            raise HTTPException(
                status_code=401,
                detail="Missing webhook signature"
            )
        
        # Get raw body for signature verification
        raw_body = await request.body()
        if not verify_webhook_signature(raw_body, signature, webhook_secret):
            logger.error(f"Invalid webhook signature for token {token[:8]}...")
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
        logger.debug(f"Webhook signature verified for token {token[:8]}...")
    
    db = Database()
    try:
        await db.connect()

        # Find user by webhook token
        user = await db.get_user_by_webhook_token(token)
        if not user:
            raise HTTPException(status_code=404, detail="Invalid webhook token")

        # Extract OTP from various possible fields (in priority order)
        otp_code = next((body.get(field) for field in OTP_FIELD_PRIORITY if body.get(field)), None)
        phone_number = next((body.get(field) for field in PHONE_FIELD_PRIORITY if body.get(field)), "")

        if not otp_code:
            raise HTTPException(status_code=400, detail="No OTP found in request body")

        # Get OTP service and process the SMS for this user
        otp_service = get_otp_service()
        
        # Store OTP with user_id as identifier for lookup
        # Format: user_{user_id}_{phone_number} to ensure uniqueness per user
        phone_identifier = f"user_{user['id']}_{phone_number}"
        await otp_service.process_appointment_sms(
            phone_number=phone_identifier,
            message=str(otp_code)
        )

        logger.info(f"OTP received for user {user['id']} via webhook: {str(otp_code)[:2]}****")

        return {
            "status": "received",
            "user_id": user["id"],
            "message": "OTP processed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing OTP webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process OTP")
    finally:
        await db.close()
