"""Authentication routes for VFS-Bot web application."""

import hmac
import logging
import os
from typing import Dict

from fastapi import APIRouter, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.auth import create_access_token
from src.core.security import generate_api_key
from web.dependencies import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

# Process-level flag for one-time use enforcement
_admin_secret_consumed = False


@router.post("/generate-key")
@limiter.limit("3/hour")
async def create_api_key_endpoint(
    request: Request, x_admin_secret: str = Header(..., alias="X-Admin-Secret")
) -> Dict[str, str]:
    """
    Generate API key with admin secret - one-time use endpoint.

    Args:
        request: FastAPI request object (required for rate limiter)
        x_admin_secret: Admin secret from X-Admin-Secret header

    Returns:
        New API key

    Raises:
        HTTPException: If admin secret is invalid
    """
    global _admin_secret_consumed
    
    # Check if admin secret has already been used
    if _admin_secret_consumed:
        client_ip = get_remote_address(request)
        logger.warning(f"Attempt to reuse consumed admin secret from {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="Admin secret already used. Set a new ADMIN_SECRET in .env and restart the application to generate another key."
        )
    
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(status_code=500, detail="Server configuration error")

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_admin_secret, admin_secret):
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    new_key = generate_api_key()
    
    # Mark admin secret as consumed
    _admin_secret_consumed = True
    logger.info("Admin secret consumed - one-time use enforced")
    
    return {
        "api_key": new_key,
        "note": "Save this key securely! It will not be shown again. The admin secret is now invalidated and cannot be used again."
    }


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
