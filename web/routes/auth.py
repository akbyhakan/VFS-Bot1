"""Authentication routes for VFS-Bot web application."""

import hmac
import logging
import os
from typing import Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.auth import create_access_token
from src.core.security import generate_api_key
from src.models.database import Database
from web.dependencies import LoginRequest, TokenResponse, get_db, verify_jwt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


async def _is_admin_secret_consumed(db: Database) -> bool:
    """
    Check if admin secret has been consumed (multi-worker safe).
    
    Args:
        db: Database instance
        
    Returns:
        True if admin secret has been consumed, False otherwise
    """
    async with db.get_connection() as conn:
        result = await conn.fetchval(
            "SELECT consumed FROM admin_secret_usage ORDER BY id DESC LIMIT 1"
        )
        return bool(result) if result is not None else False


async def _mark_admin_secret_consumed(db: Database) -> None:
    """
    Mark admin secret as consumed (multi-worker safe).
    
    Args:
        db: Database instance
    """
    async with db.get_connection() as conn:
        await conn.execute(
            """INSERT INTO admin_secret_usage (id, consumed, consumed_at)
               VALUES (1, true, NOW())
               ON CONFLICT (id) DO UPDATE SET consumed = true, consumed_at = NOW()"""
        )


@router.post("/generate-key")
@limiter.limit("3/hour")
async def create_api_key_endpoint(
    request: Request,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
    db: Database = Depends(get_db),
) -> Dict[str, str]:
    """
    Generate API key with admin secret - one-time use endpoint.

    Args:
        request: FastAPI request object (required for rate limiter)
        x_admin_secret: Admin secret from X-Admin-Secret header
        db: Database instance

    Returns:
        New API key

    Raises:
        HTTPException: If admin secret is invalid
    """
    # Check if admin secret has already been used (multi-worker safe)
    if await _is_admin_secret_consumed(db):
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
    
    # Mark admin secret as consumed (multi-worker safe)
    await _mark_admin_secret_consumed(db)
    logger.info("Admin secret consumed - one-time use enforced")
    
    return {
        "api_key": new_key,
        "note": "Save this key securely! It will not be shown again. The admin secret is now invalidated and cannot be used again."
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, response: Response, credentials: LoginRequest) -> TokenResponse:
    """
    Login endpoint - returns JWT token and sets HttpOnly cookie.

    Args:
        request: FastAPI request object (required for rate limiter)
        response: FastAPI response object (for setting cookies)
        credentials: Username and password

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid or environment not configured
    """
    from src.core.auth import verify_password
    from src.core.settings import get_settings

    # Get credentials from environment - fail if not set
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_password:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: ADMIN_USERNAME and ADMIN_PASSWORD must be set",
        )

    # Check username with constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(credentials.username, admin_username):
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

    # Set HttpOnly cookie for security (primary auth method)
    settings = get_settings()
    is_production = settings.is_production()
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access (XSS protection)
        secure=is_production,  # HTTPS only in production
        samesite="strict",  # CSRF protection
        max_age=86400,  # 24 hours (matches JWT expiry)
        path="/",
    )

    # Also return token in response body for backward compatibility
    # (API clients and existing code that uses Authorization header)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    _: Dict[str, Any] = Depends(verify_jwt_token)
) -> Dict[str, str]:
    """
    Logout endpoint - clears the HttpOnly cookie.
    
    Requires authentication to prevent unauthorized cookie manipulation.

    Args:
        response: FastAPI response object (for clearing cookies)
        _: JWT token payload (dependency for authentication)

    Returns:
        Success message
    """
    # Clear the access_token cookie
    response.delete_cookie(key="access_token", path="/")
    
    return {"message": "Logged out successfully"}
