"""VFS Global Direct API Client for Turkey."""

import asyncio
import base64
import hashlib
import logging
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TypedDict

import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from ..core.countries import SOURCE_COUNTRY_CODE, get_country_info, get_route, validate_mission_code
from ..core.exceptions import (
    ConfigurationError,
    VFSAuthenticationError,
    VFSRateLimitError,
    VFSSessionExpiredError,
)
from ..utils.security.endpoint_rate_limiter import EndpointRateLimiter
from ..utils.token_utils import calculate_effective_expiry

logger = logging.getLogger(__name__)


# VFS Global API Base URLs - Lazy loaded to prevent module-level crashes


def _get_required_env(name: str) -> str:
    """Get required environment variable with lazy validation.
    
    Args:
        name: Environment variable name
        
    Returns:
        Environment variable value
        
    Raises:
        ConfigurationError: If environment variable is not set
    """
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(
            f"{name} environment variable must be set. "
            "Check your .env file configuration."
        )
    return value


def get_vfs_api_base() -> str:
    """Get VFS API base URL (lazy loaded)."""
    return _get_required_env("VFS_API_BASE")


def get_vfs_assets_base() -> str:
    """Get VFS Assets base URL (lazy loaded)."""
    return _get_required_env("VFS_ASSETS_BASE")


def get_contentful_base() -> str:
    """Get Contentful base URL (lazy loaded)."""
    return _get_required_env("CONTENTFUL_BASE")


class CentreInfo(TypedDict):
    """Type definition for VFS Centre information."""

    id: str
    name: str
    code: str
    address: str


class VisaCategoryInfo(TypedDict):
    """Type definition for Visa Category information."""

    id: str
    name: str
    code: str


class VisaSubcategoryInfo(TypedDict):
    """Type definition for Visa Subcategory information."""

    id: str
    name: str
    code: str
    visaCategoryId: str


class BookingResponse(TypedDict):
    """Type definition for Appointment Booking response."""

    bookingId: str
    status: str
    message: str


@dataclass
class VFSSession:
    """VFS authenticated session."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    user_id: str
    email: str


@dataclass
class SlotAvailability:
    """Appointment slot availability."""

    available: bool
    dates: List[str]
    centre_id: str
    category_id: str
    message: Optional[str] = None


class VFSPasswordEncryption:
    """VFS Global password encryption (AES-256-CBC)."""

    @classmethod
    def _get_encryption_key(cls) -> bytes:
        """
        Get encryption key from environment variable.

        Returns:
            Encryption key as bytes

        Raises:
            ConfigurationError: If VFS_ENCRYPTION_KEY is not set or invalid
        """
        from ..utils.secure_memory import SecureKeyContext

        key_str = os.getenv("VFS_ENCRYPTION_KEY")
        if not key_str:
            raise ConfigurationError(
                "VFS_ENCRYPTION_KEY environment variable must be set. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        with SecureKeyContext(key_str) as key_buf:
            if len(key_buf) < 32:
                raise ConfigurationError(
                    f"VFS_ENCRYPTION_KEY must be at least 32 bytes (current: {len(key_buf)}). "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            if len(key_buf) > 32:
                logger.warning(
                    f"VFS_ENCRYPTION_KEY is {len(key_buf)} bytes, "
                    f"deriving 32-byte key using SHA-256 for consistency"
                )
                derived = hashlib.sha256(bytes(key_buf)).digest()
                return derived

            return bytes(key_buf[:32])
        # key_buf is securely zeroed here by SecureKeyContext.__exit__

    @classmethod
    def encrypt(cls, password: str) -> str:
        """
        Encrypt password for VFS API.

        Args:
            password: Plain text password

        Returns:
            Base64 encoded encrypted password
        """
        encryption_key = cls._get_encryption_key()
        iv = secrets.token_bytes(16)
        cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
        padded_data = pad(password.encode("utf-8"), AES.block_size)
        encrypted = cipher.encrypt(padded_data)

        # VFS expects IV + encrypted data, base64 encoded
        return base64.b64encode(iv + encrypted).decode("utf-8")


class VFSApiClient:
    """
    Direct API client for VFS Global Turkey.

    Supports all 21 Schengen countries that can be applied from Turkey.
    """

    def __init__(self, mission_code: str, captcha_solver: Any, timeout: int = 30):
        """
        Initialize VFS API client.

        Args:
            mission_code: Target country code (fra, nld, hrv, etc.)
            captcha_solver: CaptchaSolver instance for Turnstile
            timeout: Request timeout in seconds
        """
        validate_mission_code(mission_code)

        self.mission_code = mission_code
        self.route = get_route(mission_code)
        self.country_info = get_country_info(mission_code)
        self.captcha_solver = captcha_solver
        self.timeout = timeout

        self.session: Optional[VFSSession] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._client_source: Optional[str] = None
        self._is_refreshing = False  # Guard flag for token refresh
        self._refresh_complete_event = asyncio.Event()  # Signal when refresh completes
        self._refresh_complete_event.set()  # Initially set (no refresh in progress)

        # Per-endpoint rate limiter (Issue 3.4)
        self.endpoint_limiter = EndpointRateLimiter()

        logger.info(
            f"VFSApiClient initialized for {self.country_info.name_en} "
            f"({self.mission_code}) - Route: {self.route}"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_http_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _init_http_session(self) -> None:
        """Initialize HTTP session with connection pooling."""
        if self._http_session is None:
            self._client_source = self._generate_client_source()

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Origin": "https://visa.vfsglobal.com",
                "Referer": f"https://visa.vfsglobal.com/{self.route}/",
                "route": self.route,
                "clientsource": self._client_source,
            }

            # Connection pooling configuration
            connector = aiohttp.TCPConnector(
                limit=50,  # Reduced from 100 for better memory management
                limit_per_host=20,  # Per-host limit
                ttl_dns_cache=120,  # DNS cache TTL (2 minutes)
                keepalive_timeout=30,  # Keepalive timeout
                enable_cleanup_closed=True,  # Enable closed connection cleanup
            )

            timeout = aiohttp.ClientTimeout(
                total=self.timeout,
                connect=10,  # Connection timeout
                sock_read=20,  # Socket read timeout
            )

            self._http_session = aiohttp.ClientSession(
                connector=connector,
                headers=headers,
                timeout=timeout,
            )
            logger.info("HTTP session initialized with connection pooling")

    def _generate_client_source(self) -> str:
        """Generate clientsource header value."""
        timestamp = int(time.time() * 1000)
        random_part = secrets.token_hex(16)
        return f"{timestamp}-{random_part}-vfs-turkey"

    async def close(self) -> None:
        """Close HTTP session."""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None

    @property
    def _session(self) -> aiohttp.ClientSession:
        """Get HTTP session, raising error if not initialized."""
        if self._http_session is None:
            raise RuntimeError("HTTP session not initialized. Call _init_http_session() first.")
        return self._http_session

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
        await self._init_http_session()

        # Apply rate limiting for login endpoint
        await self.endpoint_limiter.acquire("login")

        encrypted_password = VFSPasswordEncryption.encrypt(password)

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

    async def get_centres(self) -> List[CentreInfo]:
        """
        Get available VFS centres.

        Returns:
            List of centre information

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        await self._ensure_authenticated()

        # Apply rate limiting for centres endpoint
        await self.endpoint_limiter.acquire("centres")

        async with self._session.get(f"{get_vfs_api_base()}/master/center") as response:
            # Handle 429 rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.endpoint_limiter.on_rate_limited("centres", retry_after)
                logger.error(f"Rate limited by VFS on centres (429), retry after {retry_after}s")
                raise VFSRateLimitError(
                    f"Rate limited on centres endpoint. Retry after {retry_after}s",
                    wait_time=retry_after,
                )

            data = await response.json()
            logger.info(f"Retrieved {len(data)} centres")
            result: List[CentreInfo] = data
            return result

    async def get_visa_categories(self, centre_id: str) -> List[VisaCategoryInfo]:
        """
        Get visa categories for a centre.

        Args:
            centre_id: VFS centre ID

        Returns:
            List of visa categories

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        await self._ensure_authenticated()

        # Apply rate limiting for centres endpoint
        await self.endpoint_limiter.acquire("centres")

        async with self._session.get(
            f"{get_vfs_api_base()}/master/visacategory", params={"centerId": centre_id}
        ) as response:
            # Handle 429 rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.endpoint_limiter.on_rate_limited("centres", retry_after)
                logger.error(
                    f"Rate limited by VFS on visa categories (429), retry after {retry_after}s"
                )
                raise VFSRateLimitError(
                    f"Rate limited on visa categories endpoint. Retry after {retry_after}s",
                    wait_time=retry_after,
                )

            data = await response.json()
            result: List[VisaCategoryInfo] = data
            return result

    async def get_visa_subcategories(
        self, centre_id: str, category_id: str
    ) -> List[VisaSubcategoryInfo]:
        """
        Get visa subcategories.

        Args:
            centre_id: VFS centre ID
            category_id: Visa category ID

        Returns:
            List of visa subcategories

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        await self._ensure_authenticated()

        # Apply rate limiting for centres endpoint
        await self.endpoint_limiter.acquire("centres")

        async with self._session.get(
            f"{get_vfs_api_base()}/master/subvisacategory",
            params={"centerId": centre_id, "visaCategoryId": category_id},
        ) as response:
            # Handle 429 rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.endpoint_limiter.on_rate_limited("centres", retry_after)
                logger.error(
                    f"Rate limited by VFS on visa subcategories (429), "
                    f"retry after {retry_after}s"
                )
                raise VFSRateLimitError(
                    f"Rate limited on visa subcategories endpoint. Retry after {retry_after}s",
                    wait_time=retry_after,
                )

            data = await response.json()
            result: List[VisaSubcategoryInfo] = data
            return result

    async def check_slot_availability(
        self, centre_id: str, category_id: str, subcategory_id: str
    ) -> SlotAvailability:
        """
        Check appointment slot availability.

        Args:
            centre_id: VFS centre ID
            category_id: Visa category ID
            subcategory_id: Visa subcategory ID

        Returns:
            SlotAvailability with dates if available

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        await self._ensure_authenticated()

        # Apply rate limiting for slot check endpoint
        await self.endpoint_limiter.acquire("slot_check")

        params = {
            "centerId": centre_id,
            "visaCategoryId": category_id,
            "subVisaCategoryId": subcategory_id,
        }

        async with self._session.get(
            f"{get_vfs_api_base()}/appointment/slots", params=params
        ) as response:
            # Handle 429 rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.endpoint_limiter.on_rate_limited("slot_check", retry_after)
                logger.error(
                    f"Rate limited by VFS on slot check (429), retry after {retry_after}s"
                )
                raise VFSRateLimitError(
                    f"Rate limited on slot check endpoint. Retry after {retry_after}s",
                    wait_time=retry_after,
                )

            if response.status != 200:
                return SlotAvailability(
                    available=False,
                    dates=[],
                    centre_id=centre_id,
                    category_id=category_id,
                    message=f"API error: {response.status}",
                )

            data = await response.json()

            available_dates = data.get("availableDates", [])

            return SlotAvailability(
                available=len(available_dates) > 0,
                dates=available_dates,
                centre_id=centre_id,
                category_id=category_id,
                message=data.get("message"),
            )

    async def book_appointment(
        self, slot_date: str, slot_time: str, applicant_data: Dict[str, Any]
    ) -> BookingResponse:
        """
        Book an appointment.

        Args:
            slot_date: Appointment date (YYYY-MM-DD)
            slot_time: Appointment time (HH:MM)
            applicant_data: Applicant information

        Returns:
            Booking confirmation

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        await self._ensure_authenticated()

        # Apply rate limiting for booking endpoint
        await self.endpoint_limiter.acquire("booking")

        payload = {"appointmentDate": slot_date, "appointmentTime": slot_time, **applicant_data}

        async with self._session.post(
            f"{get_vfs_api_base()}/appointment/applicants", json=payload
        ) as response:
            # Handle 429 rate limiting
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.endpoint_limiter.on_rate_limited("booking", retry_after)
                logger.error(f"Rate limited by VFS on booking (429), retry after {retry_after}s")
                raise VFSRateLimitError(
                    f"Rate limited on booking endpoint. Retry after {retry_after}s",
                    wait_time=retry_after,
                )

            data = await response.json()

            if response.status == 200:
                logger.info(f"Appointment booked: {slot_date} {slot_time}")
            else:
                logger.error(f"Booking failed: {data}")

            result: BookingResponse = data
            return result

    async def _ensure_authenticated(self) -> None:
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
            await self._refresh_token()

    async def _refresh_token(self) -> None:
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
                f"{get_vfs_api_base()}/user/refresh", json={"refreshToken": self.session.refresh_token}
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

    async def solve_turnstile(self, page_url: str, site_key: str) -> str:
        """
        Solve Cloudflare Turnstile captcha.

        Args:
            page_url: Page URL where Turnstile is displayed
            site_key: Turnstile site key

        Returns:
            Turnstile token
        """
        result = await self.captcha_solver.solve_turnstile(page_url=page_url, site_key=site_key)
        return str(result)
