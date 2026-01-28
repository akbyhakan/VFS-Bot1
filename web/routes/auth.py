"""Authentication routes for VFS-Bot web application."""

import os
import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.security import generate_api_key
from src.core.auth import create_access_token
from web.dependencies import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/generate-key")
async def create_api_key_endpoint(secret: str) -> Dict[str, str]:
    """
    Generate API key with admin secret - one-time use endpoint.

    Args:
        secret: Admin secret from environment

    Returns:
        New API key

    Raises:
        HTTPException: If admin secret is invalid
    """
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret or secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    new_key = generate_api_key()
    return {"api_key": new_key, "note": "Save this key securely! It will not be shown again."}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: LoginRequest) -> TokenResponse:
    """
    Login endpoint - returns JWT token.

    Args:
        request: FastAPI request object (required for rate limiter)
        credentials: Username and password

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid or environment not configured
    """
    from src.core.auth import verify_password

    # Get credentials from environment - fail if not set
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_password:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: ADMIN_USERNAME and ADMIN_PASSWORD must be set",
        )

    # Check username
    if credentials.username != admin_username:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check password - ONLY accept bcrypt hashed passwords
    # Security requirement: Plaintext passwords are not allowed in ANY environment
    if not admin_password.startswith(("$2b$", "$2a$", "$2y$")):
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: ADMIN_PASSWORD must be bcrypt hashed. "
            'Use: python -c "from passlib.context import CryptContext; '
            "print(CryptContext(schemes=['bcrypt']).hash('your-password'))\"",
        )
    
    password_valid = verify_password(credentials.password, admin_password)

    if not password_valid:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": credentials.username, "name": credentials.username}
    )

    return TokenResponse(access_token=access_token)
