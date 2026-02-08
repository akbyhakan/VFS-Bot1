"""Shared dependencies, models, and utilities for VFS-Bot web application.

This module provides dependency injection functions and backward compatibility
re-exports for the modular web package structure.

Note: Since v2.1, models have been moved to web.models/, state management to
web.state/, and WebSocket management to web.websocket/. This file maintains
backward compatibility by re-exporting all these components.
"""

import logging
from typing import Any, AsyncIterator, Dict

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.auth import verify_token
from src.models.database import Database
from src.models.db_factory import DatabaseFactory

# Backward compatibility re-exports - Models
from web.models import *  # noqa: F401,F403
from web.models.appointments import (  # noqa: F401
    AppointmentPersonRequest,
    AppointmentPersonResponse,
    AppointmentRequestCreate,
    AppointmentRequestResponse,
)
from web.models.auth import LoginRequest, TokenResponse  # noqa: F401
from web.models.bot import BotCommand, StatusUpdate  # noqa: F401
from web.models.common import CountryResponse, WebhookUrlsResponse  # noqa: F401
from web.models.payment import (  # noqa: F401
    PaymentCardRequest,
    PaymentCardResponse,
    PaymentInitiateRequest,
)
from web.models.proxy import (  # noqa: F401
    ProxyCreateRequest,
    ProxyResponse,
    ProxyUpdateRequest,
)
from web.models.users import UserCreateRequest, UserModel, UserUpdateRequest  # noqa: F401

# Backward compatibility re-exports - State Management
from web.state.bot_state import ThreadSafeBotState  # noqa: F401
from web.state.metrics import ThreadSafeMetrics  # noqa: F401

# Backward compatibility re-exports - WebSocket
from web.websocket.manager import ConnectionManager  # noqa: F401

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer()


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
    Authorization header is kept for backward compatibility with API clients.

    Args:
        request: FastAPI request object

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or missing
    """
    from fastapi import HTTPException
    
    token = None
    
    # First, try to get token from HttpOnly cookie (primary method)
    token = request.cookies.get("access_token")
    
    # Fallback to Authorization header (backward compatibility)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    # If no token found in either location, reject request
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return verify_token(token)


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
