"""Webhook management routes for per-user OTP webhooks."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.models.database import Database
from web.dependencies import verify_jwt_token
from src.services.otp_webhook import get_otp_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])


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
async def receive_otp(token: str, body: dict):
    """
    Receive OTP via user-specific webhook.

    Args:
        token: Unique webhook token
        body: Request body containing OTP data

    Returns:
        Success message with user_id

    Raises:
        HTTPException: If token is invalid
    """
    db = Database()
    try:
        await db.connect()

        # Find user by webhook token
        user = await db.get_user_by_webhook_token(token)
        if not user:
            raise HTTPException(status_code=404, detail="Invalid webhook token")

        # Extract OTP from various possible fields
        otp_code = body.get("message") or body.get("otp") or body.get("body") or body.get("text")
        phone_number = body.get("phone") or body.get("from") or body.get("phone_number") or ""

        if not otp_code:
            raise HTTPException(status_code=400, detail="No OTP found in request body")

        # Get OTP service and process the SMS for this user
        otp_service = get_otp_service()
        
        # Store OTP with user_id as identifier
        await otp_service.process_appointment_sms(
            phone_number=f"user_{user['id']}_{phone_number}",
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
