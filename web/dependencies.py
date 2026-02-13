"""Shared dependencies, models, and utilities for VFS-Bot web application.

This module provides dependency injection functions and re-exports for the modular
web package structure.

Note: Since v2.1, models have been moved to web.models/, state management to
web.state/, and WebSocket management to web.websocket/. This file maintains
re-exports of all these components.
"""

import os
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from src.core.auth import verify_token
from src.core.environment import Environment
from src.core.security import APIKeyManager
from src.models.database import Database
from src.models.db_factory import DatabaseFactory
from src.utils.webhook_utils import verify_webhook_signature
from src.repositories import (
    AppointmentHistoryRepository,
    AppointmentRepository,
    AppointmentRequestRepository,
    AuditLogRepository,
    LogRepository,
    PaymentRepository,
    ProxyRepository,
    TokenBlacklistRepository,
    UserRepository,
    WebhookRepository,
)
from web.state.bot_state import ThreadSafeBotState
from web.state.metrics import ThreadSafeMetrics
from web.websocket.manager import ConnectionManager

security_scheme = HTTPBearer()


def extract_raw_token(request: Request) -> Optional[str]:
    """
    Extract raw JWT token from HttpOnly cookie or Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: Raw JWT token string, or None if not found
    """
    # First, try to get token from HttpOnly cookie (primary method)
    token = request.cookies.get("access_token")

    # Fallback to Authorization header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    return token


# Global state instances
bot_state = ThreadSafeBotState()
manager = ConnectionManager()
metrics = ThreadSafeMetrics()


# Dependency functions
async def verify_jwt_token(
    request: Request,
) -> Dict[str, Any]:
    """
    Verify JWT token from HttpOnly cookie or Authorization header.

    Cookie-based authentication is preferred for security (XSS protection).

    Args:
        request: FastAPI request object

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or missing
    """
    token = extract_raw_token(request)

    # If no token found in either location, reject request
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await verify_token(token)


async def verify_hybrid_auth(request: Request) -> Dict[str, Any]:
    """
    Hybrid authentication: accepts either JWT token or API key.
    
    Resolution order:
    1. Try JWT token (from HttpOnly cookie or Authorization header)
    2. If JWT fails, try API key (from Authorization header)
    3. If both fail, raise 401
    
    Returns:
        Dict with auth metadata. Includes 'auth_method' key ('jwt' or 'api_key').
    
    Raises:
        HTTPException: If both JWT and API key authentication fail
    """
    # First, try JWT authentication
    token = extract_raw_token(request)
    
    if token:
        try:
            # Try to verify as JWT token
            jwt_payload = await verify_token(token)
            # Add auth method indicator
            jwt_payload["auth_method"] = "jwt"
            return jwt_payload
        except Exception as jwt_error:
            # JWT verification failed, try API key
            logger.debug(f"JWT verification failed, attempting API key: {jwt_error}")
            
            # Try to verify as API key (only from Authorization header, not cookie)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header.split(" ")[1]
                manager = APIKeyManager()
                key_metadata = manager.verify_key(api_key)
                
                if key_metadata:
                    # Add auth method indicator
                    key_metadata["auth_method"] = "api_key"
                    return key_metadata
    
    # Both authentication methods failed
    raise HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_webhook_request(request: Request) -> None:
    """
    Shared webhook signature verification dependency.
    
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
        
        logger.debug("Webhook signature verified")
    
    elif Environment.is_development():
        # Development mode without secret: log warning but allow
        logger.warning(
            "DEVELOPMENT MODE: No SMS_WEBHOOK_SECRET configured - "
            "signature validation disabled. DO NOT use in production!"
        )


async def get_db() -> AsyncIterator[Database]:
    """
    FastAPI dependency — singleton DB via DatabaseFactory.

    Yields:
        Connected database instance

    Note:
        This is a singleton pattern. Do NOT close the database connection
        in route handlers. DatabaseFactory.close_instance() handles shutdown.
    """
    db = await DatabaseFactory.ensure_connected()
    yield db
    # Do NOT close — DatabaseFactory.close_instance() handles shutdown


async def broadcast_message(message: Dict[str, Any]) -> None:
    """
    Broadcast message to all connected WebSocket clients.

    Args:
        message: Message dictionary to broadcast
    """
    await manager.broadcast(message)


# Repository dependency functions
async def get_user_repository(db: Database = Depends(get_db)) -> UserRepository:
    """Get UserRepository instance."""
    return UserRepository(db)


async def get_appointment_repository(db: Database = Depends(get_db)) -> AppointmentRepository:
    """Get AppointmentRepository instance."""
    return AppointmentRepository(db)


async def get_log_repository(db: Database = Depends(get_db)) -> LogRepository:
    """Get LogRepository instance."""
    return LogRepository(db)


async def get_payment_repository(db: Database = Depends(get_db)) -> PaymentRepository:
    """Get PaymentRepository instance."""
    return PaymentRepository(db)


async def get_appointment_request_repository(
    db: Database = Depends(get_db),
) -> AppointmentRequestRepository:
    """Get AppointmentRequestRepository instance."""
    return AppointmentRequestRepository(db)


async def get_appointment_history_repository(
    db: Database = Depends(get_db),
) -> AppointmentHistoryRepository:
    """Get AppointmentHistoryRepository instance."""
    return AppointmentHistoryRepository(db)


async def get_audit_log_repository(db: Database = Depends(get_db)) -> AuditLogRepository:
    """Get AuditLogRepository instance."""
    return AuditLogRepository(db)


async def get_token_blacklist_repository(
    db: Database = Depends(get_db),
) -> TokenBlacklistRepository:
    """Get TokenBlacklistRepository instance."""
    return TokenBlacklistRepository(db)


async def get_webhook_repository(db: Database = Depends(get_db)) -> WebhookRepository:
    """Get WebhookRepository instance."""
    return WebhookRepository(db)


async def get_proxy_repository(db: Database = Depends(get_db)) -> ProxyRepository:
    """Get ProxyRepository instance."""
    return ProxyRepository(db)
