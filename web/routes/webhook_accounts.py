"""Webhook CRUD routes for per-user OTP webhooks (JWT-protected)."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src.repositories import WebhookRepository
from src.repositories.account_pool_repository import AccountPoolRepository
from web.dependencies import (
    get_vfs_account_repository,
    get_webhook_repository,
    verify_jwt_token,
)

router = APIRouter(prefix="/webhook", tags=["webhook-accounts"])


@router.post("/users/{user_id}/create")
async def create_webhook(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """
    Create a unique webhook for a VFS account.

    Args:
        user_id: VFS Account ID (kept as user_id for URL backward compatibility)
        token_data: Verified token data
        webhook_repo: WebhookRepository instance
        account_repo: AccountPoolRepository instance

    Returns:
        Webhook token and URL

    Raises:
        HTTPException: If account already has a webhook or creation fails
    """
    try:
        # Verify account exists using AccountPoolRepository
        account = await account_repo.get_account_by_id(user_id, decrypt=False)
        if not account:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if webhook already exists
        existing = await webhook_repo.get_by_user(user_id)
        if existing:
            raise HTTPException(status_code=400, detail="User already has a webhook")

        # Create webhook
        token = await webhook_repo.create(user_id)
        webhook_url = f"/api/webhook/otp/{token}"

        logger.info(f"Webhook created for user {user_id} by {token_data.get('sub', 'unknown')}")

        return {
            "token": token,
            "webhook_url": webhook_url,
            "message": "Webhook created successfully",
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create webhook")


@router.get("/users/{user_id}")
async def get_webhook(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
):
    """
    Get webhook information for a user.

    Args:
        user_id: User ID
        token_data: Verified token data
        webhook_repo: WebhookRepository instance

    Returns:
        Webhook data or null if not found
    """
    try:
        webhook = await webhook_repo.get_by_user(user_id)

        if not webhook:
            return {"webhook": None}

        return {
            "webhook": {
                "token": webhook["webhook_token"],
                "webhook_url": f"/api/webhook/otp/{webhook['webhook_token']}",
                "created_at": webhook["created_at"],
            }
        }

    except Exception as e:
        logger.error(f"Error getting webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get webhook")


@router.delete("/users/{user_id}")
async def delete_webhook(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    webhook_repo: WebhookRepository = Depends(get_webhook_repository),
):
    """
    Delete a user's webhook.

    Args:
        user_id: User ID
        token_data: Verified token data
        webhook_repo: WebhookRepository instance

    Returns:
        Success message

    Raises:
        HTTPException: If webhook not found
    """
    try:
        success = await webhook_repo.delete_by_user(user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Webhook not found")

        logger.info(f"Webhook deleted for user {user_id} by {token_data.get('sub', 'unknown')}")

        return {"message": "Webhook deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete webhook")
