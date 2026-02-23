"""VFS Authentication Module - Handles login and token refresh."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, Union

import aiohttp
from loguru import logger

from src.core.rate_limiting import EndpointRateLimiter

from ...core.exceptions import (
    VFSAuthenticationError,
    VFSRateLimitError,
    VFSSessionExpiredError,
)
from ...utils.token_utils import calculate_effective_expiry
from .encryption import VFSPasswordEncryption, get_vfs_api_base
from .models import VFSSession

if TYPE_CHECKING:
    from typing import Optional


def _get_token_refresh_buffer() -> int:
    """Get token refresh buffer from environment with safe parsing."""
    raw = os.getenv("TOKEN_REFRESH_BUFFER_MINUTES", "5")
    try:
        value = int(raw)
        if value < 0:
            logger.warning(
                f"TOKEN_REFRESH_BUFFER_MINUTES must be >= 0, got {value}. Using default 5."
            )
            return 5
        return value
    except (ValueError, TypeError):
        logger.warning(f"Invalid TOKEN_REFRESH_BUFFER_MINUTES: '{raw}'. Using default 5.")
        return 5


class VFSAuth:
    """Handles VFS authentication - login, token refresh, and session validation."""

    def __init__(
        self,
        mission_code: str,
        endpoint_limiter: EndpointRateLimiter,
        http_session_getter: Callable[[], aiohttp.ClientSession],
    ):
        """
        Initialize VFS authentication handler.

        Args:
            mission_code: Target country code (fra, nld, hrv, etc.)
            endpoint_limiter: Rate limiter for API endpoints
            http_session_getter: Callable that returns the HTTP session
        """
        self.mission_code = mission_code
        self.endpoint_limiter = endpoint_limiter
        self._http_session_getter = http_session_getter

        self.session: Optional[VFSSession] = None
        self._refresh_lock = asyncio.Lock()

    @property
    def _session(self) -> aiohttp.ClientSession:
        """Get HTTP session from parent client."""
        return self._http_session_getter()

    async def login(self, email: str, password: str, turnstile_token: str) -> VFSSession:
        """
        Login to VFS Global.

        Args:
            email: User email
            password: User password (plain text, will be encrypted)
            turnstile_token: Solved Cloudflare Turnstile token

        Returns:
            VFSSession with tokens

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        # Apply rate limiting for login endpoint
        await self.endpoint_limiter.acquire("login")

        encrypted_password = VFSPasswordEncryption.encrypt(password)

        # Import here to avoid circular dependency
        from ...constants.countries import SOURCE_COUNTRY_CODE

        payload = {
            "username": email,
            "password": encrypted_password,
            "missioncode": self.mission_code,
            "countrycode": SOURCE_COUNTRY_CODE,
            "captcha_version": "cloudflare-v1",
            "captcha_api_key": turnstile_token,
        }

        logger.info(f"Logging in to VFS for mission: {self.mission_code}")

        async with self._session.post(
            f"{get_vfs_api_base()}/user/login",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as response:
            # Handle 429 rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.endpoint_limiter.on_rate_limited("login", retry_after)
                logger.error(f"Rate limited by VFS on login (429), retry after {retry_after}s")
                raise VFSRateLimitError(
                    f"Rate limited on login endpoint. Retry after {retry_after}s",
                    wait_time=retry_after,
                )

            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Login failed: {response.status}")
                logger.debug(f"Error details: {error_text[:200]}...")
                raise VFSAuthenticationError(f"Login failed with status {response.status}")

            data = await response.json()

            # Calculate token expiration time
            # VFS tokens typically expire after 1 hour, but we add buffer for safety
            token_refresh_buffer = _get_token_refresh_buffer()
            expires_in = data.get("expiresIn", 60)
            effective_expiry = calculate_effective_expiry(expires_in, token_refresh_buffer)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=effective_expiry)

            self.session = VFSSession(
                access_token=data["accessToken"],
                refresh_token=data.get("refreshToken", ""),
                expires_at=expires_at,
                user_id=data.get("userId", ""),
                email=email,
            )

            # Update session headers with auth token
            self._session.headers.update({"Authorization": f"Bearer {self.session.access_token}"})

            logger.info(f"Login successful for {email[:3]}***")
            return self.session

    async def ensure_authenticated(self) -> None:
        """
        Ensure we have a valid session.

        Raises:
            VFSSessionExpiredError: If session is not valid or has expired
        """
        if not self.session:
            raise VFSSessionExpiredError("Not authenticated. Call login() first.")

        # Check if token has expired or is about to expire
        if datetime.now(timezone.utc) >= self.session.expires_at:
            logger.warning("Token has expired, attempting refresh")
            await self.refresh_token()

    async def refresh_token(self) -> None:
        """
        Refresh the authentication token with guard against concurrent refresh.

        Raises:
            VFSAuthenticationError: If token refresh fails
        """
        async with self._refresh_lock:
            if not self.session or not self.session.refresh_token:
                raise VFSAuthenticationError(
                    "Cannot refresh token: No refresh token available. Please login again."
                )

            try:
                async with self._session.post(
                    f"{get_vfs_api_base()}/user/refresh",
                    json={"refreshToken": self.session.refresh_token},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Token refresh failed: {response.status} - {error_text}")
                        raise VFSAuthenticationError(
                            f"Token refresh failed with status {response.status}"
                        )

                    data = await response.json()

                    # Update session with new tokens
                    token_refresh_buffer = _get_token_refresh_buffer()
                    expires_in = data.get("expiresIn", 60)
                    effective_expiry = calculate_effective_expiry(expires_in, token_refresh_buffer)

                    self.session.access_token = data["accessToken"]
                    self.session.refresh_token = data.get(
                        "refreshToken", self.session.refresh_token
                    )
                    self.session.expires_at = datetime.now(timezone.utc) + timedelta(
                        minutes=effective_expiry
                    )

                    # Update session headers with new auth token
                    self._session.headers.update(
                        {"Authorization": f"Bearer {self.session.access_token}"}
                    )

                    logger.info(
                        f"Token refreshed successfully, expires at {self.session.expires_at}"
                    )

            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                if isinstance(e, VFSAuthenticationError):
                    raise
                raise VFSSessionExpiredError(f"Token refresh failed: {e}")

    def check_and_update_token_from_data(
        self, data: Union[Dict[str, Any], list], response_headers: Any
    ) -> bool:
        """
        Check and update token from response data and headers.

        This method handles dynamic token updates that may occur in intermediate
        API responses (not just login/refresh). VFS API may return new tokens in:
        1. Set-Cookie header with 'accesstoken=' prefix
        2. Response body with 'accessToken' or 'access_token' key

        Args:
            data: Parsed response data (dict or list)
            response_headers: Response headers from aiohttp

        Returns:
            True if token was updated, False otherwise
        """
        if not self.session:
            # No active session to update
            return False

        token_updated = False
        new_access_token = None
        new_refresh_token = None
        new_expires_in = None

        # 1. Check Set-Cookie header for accesstoken
        try:
            set_cookie_list = response_headers.getall("Set-Cookie", [])
            for set_cookie in set_cookie_list:
                if set_cookie and "accesstoken=" in set_cookie.lower():
                    for cookie_part in set_cookie.split(";"):
                        cookie_part = cookie_part.strip()
                        if cookie_part.lower().startswith("accesstoken="):
                            cookie_value = cookie_part.split("=", 1)[1]
                            if cookie_value and cookie_value != self.session.access_token:
                                new_access_token = cookie_value
                                logger.info("Found new access token in Set-Cookie header")
                                break
                if new_access_token:
                    break
        except Exception as e:
            logger.debug(f"Error checking Set-Cookie header: {e}")

        # 2. Check response body for token fields (only if data is a dict)
        if isinstance(data, dict):
            # Check for accessToken or access_token in response
            body_access_token = data.get("accessToken") or data.get("access_token")
            if body_access_token and body_access_token != self.session.access_token:
                new_access_token = body_access_token
                logger.info("Found new access token in response body")

            # Also check for refresh token and expiry
            new_refresh_token = data.get("refreshToken") or data.get("refresh_token")
            new_expires_in = data.get("expiresIn") or data.get("expires_in")

        # 3. Update session if new token found
        if new_access_token:
            self.session.access_token = new_access_token
            token_updated = True

            # Update refresh token if present
            if new_refresh_token:
                self.session.refresh_token = new_refresh_token

            # Update expiry time if present
            if new_expires_in:
                token_refresh_buffer = _get_token_refresh_buffer()
                effective_expiry = calculate_effective_expiry(new_expires_in, token_refresh_buffer)
                self.session.expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=effective_expiry
                )
            else:
                # Default expiry if not provided (1 hour with buffer)
                token_refresh_buffer = _get_token_refresh_buffer()
                effective_expiry = calculate_effective_expiry(60, token_refresh_buffer)
                self.session.expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=effective_expiry
                )

            # Update session headers with new token
            self._session.headers.update({"Authorization": f"Bearer {new_access_token}"})

            logger.info(
                f"Token updated dynamically from API response, "
                f"expires at {self.session.expires_at}"
            )

        return token_updated
