"""VFS Authentication Module - Handles login and token refresh."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import aiohttp
from loguru import logger

from ...core.exceptions import (
    VFSAuthenticationError,
    VFSRateLimitError,
    VFSSessionExpiredError,
)
from ...utils.security.endpoint_rate_limiter import EndpointRateLimiter
from ...utils.token_utils import calculate_effective_expiry
from .encryption import VFSPasswordEncryption, get_vfs_api_base
from .models import VFSSession

if TYPE_CHECKING:
    from typing import Optional


class VFSAuth:
    """Handles VFS authentication - login, token refresh, and session validation."""

    def __init__(
        self,
        mission_code: str,
        endpoint_limiter: EndpointRateLimiter,
        http_session_getter,
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
        self._is_refreshing = False  # Guard flag for token refresh
        self._refresh_complete_event = asyncio.Event()  # Signal when refresh completes
        self._refresh_complete_event.set()  # Initially set (no refresh in progress)

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
        from ...core.countries import SOURCE_COUNTRY_CODE

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
            token_refresh_buffer = int(os.getenv("TOKEN_REFRESH_BUFFER_MINUTES", "5"))
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
            VFSAuthenticationError: If token refresh fails or already in progress
        """
        if self._is_refreshing:
            logger.warning("Token refresh already in progress, waiting for completion...")
            # Wait for ongoing refresh to complete (with timeout)
            try:
                await asyncio.wait_for(self._refresh_complete_event.wait(), timeout=10.0)
                # Check if session is now valid
                if self.session and datetime.now(timezone.utc) < self.session.expires_at:
                    logger.info("Token refresh completed by another caller")
                    return  # Another refresh completed successfully
                else:
                    raise VFSAuthenticationError("Token refresh completed but session invalid")
            except asyncio.TimeoutError:
                raise VFSAuthenticationError(
                    "Token refresh timeout - another refresh taking too long"
                )

        # Clear the event to signal refresh in progress
        self._refresh_complete_event.clear()
        self._is_refreshing = True

        try:
            if not self.session or not self.session.refresh_token:
                raise VFSAuthenticationError(
                    "Cannot refresh token: No refresh token available. Please login again."
                )

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
                token_refresh_buffer = int(os.getenv("TOKEN_REFRESH_BUFFER_MINUTES", "5"))
                expires_in = data.get("expiresIn", 60)
                effective_expiry = calculate_effective_expiry(expires_in, token_refresh_buffer)

                self.session.access_token = data["accessToken"]
                self.session.refresh_token = data.get("refreshToken", self.session.refresh_token)
                self.session.expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=effective_expiry
                )

                # Update session headers with new auth token
                self._session.headers.update(
                    {"Authorization": f"Bearer {self.session.access_token}"}
                )

                logger.info(f"Token refreshed successfully, expires at {self.session.expires_at}")

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            if isinstance(e, VFSAuthenticationError):
                raise
            raise VFSSessionExpiredError(f"Token refresh failed: {e}")
        finally:
            self._is_refreshing = False
            self._refresh_complete_event.set()  # Signal completion
