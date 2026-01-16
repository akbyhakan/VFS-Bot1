"""VFS Global Direct API Client for Turkey."""

import base64
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from ..core.countries import (
    SOURCE_COUNTRY_CODE,
    get_route,
    validate_mission_code,
    get_country_info,
)
from ..core.exceptions import (
    VFSAuthenticationError,
    VFSSessionExpiredError,
    ConfigurationError,
)
from ..constants import Defaults

logger = logging.getLogger(__name__)


# VFS Global API Base URLs
VFS_API_BASE = "https://lift-api.vfsglobal.com"
VFS_ASSETS_BASE = "https://liftassets.vfsglobal.com"
CONTENTFUL_BASE = "https://d2ab400qlgxn2g.cloudfront.net/dev/spaces"


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
        key = os.getenv("VFS_ENCRYPTION_KEY")
        if not key:
            raise ConfigurationError(
                "VFS_ENCRYPTION_KEY environment variable must be set. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        key_bytes = key.encode("utf-8")

        # Enforce minimum 32 bytes for security
        if len(key_bytes) < 32:
            raise ConfigurationError(
                f"VFS_ENCRYPTION_KEY must be at least 32 bytes (current: {len(key_bytes)}). "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Use first 32 bytes for AES-256
        return key_bytes[:32]

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
        """Initialize HTTP session with proper headers."""
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

            self._http_session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

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
        """
        await self._init_http_session()

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
            f"{VFS_API_BASE}/user/login",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Login failed: {response.status} - {error_text}")
                raise VFSAuthenticationError(f"Login failed with status {response.status}")

            data = await response.json()

            # Calculate token expiration time
            # VFS tokens typically expire after 1 hour, but we add buffer for safety
            token_refresh_buffer = int(
                os.getenv(
                    "TOKEN_REFRESH_BUFFER_MINUTES", str(Defaults.TOKEN_REFRESH_BUFFER_MINUTES)
                )
            )
            expires_at = datetime.now() + timedelta(
                minutes=data.get("expiresIn", 60) - token_refresh_buffer
            )

            self.session = VFSSession(
                access_token=data["accessToken"],
                refresh_token=data.get("refreshToken", ""),
                expires_at=expires_at,
                user_id=data.get("userId", ""),
                email=email,
            )

            # Update session headers with auth token
            self._session.headers.update({"Authorization": f"Bearer {self.session.access_token}"})

            logger.info(f"Login successful for {email[:3]}***, token expires at {expires_at}")
            return self.session

    async def get_centres(self) -> List[Dict[str, Any]]:
        """
        Get available VFS centres.

        Returns:
            List of centre information
        """
        await self._ensure_authenticated()

        async with self._session.get(f"{VFS_API_BASE}/master/center") as response:
            data = await response.json()
            logger.info(f"Retrieved {len(data)} centres")
            return data  # type: ignore[no-any-return]

    async def get_visa_categories(self, centre_id: str) -> List[Dict[str, Any]]:
        """
        Get visa categories for a centre.

        Args:
            centre_id: VFS centre ID

        Returns:
            List of visa categories
        """
        await self._ensure_authenticated()

        async with self._session.get(
            f"{VFS_API_BASE}/master/visacategory", params={"centerId": centre_id}
        ) as response:
            data = await response.json()
            return data  # type: ignore[no-any-return]

    async def get_visa_subcategories(
        self, centre_id: str, category_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get visa subcategories.

        Args:
            centre_id: VFS centre ID
            category_id: Visa category ID

        Returns:
            List of visa subcategories
        """
        await self._ensure_authenticated()

        async with self._session.get(
            f"{VFS_API_BASE}/master/subvisacategory",
            params={"centerId": centre_id, "visaCategoryId": category_id},
        ) as response:
            data = await response.json()
            return data  # type: ignore[no-any-return]

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
        """
        await self._ensure_authenticated()

        params = {
            "centerId": centre_id,
            "visaCategoryId": category_id,
            "subVisaCategoryId": subcategory_id,
        }

        async with self._session.get(
            f"{VFS_API_BASE}/appointment/slots", params=params
        ) as response:
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
    ) -> Dict[str, Any]:
        """
        Book an appointment.

        Args:
            slot_date: Appointment date (YYYY-MM-DD)
            slot_time: Appointment time (HH:MM)
            applicant_data: Applicant information

        Returns:
            Booking confirmation
        """
        await self._ensure_authenticated()

        payload = {"appointmentDate": slot_date, "appointmentTime": slot_time, **applicant_data}

        async with self._session.post(
            f"{VFS_API_BASE}/appointment/applicants", json=payload
        ) as response:
            data = await response.json()

            if response.status == 200:
                logger.info(f"Appointment booked: {slot_date} {slot_time}")
            else:
                logger.error(f"Booking failed: {data}")

            return data  # type: ignore[no-any-return]

    async def _ensure_authenticated(self) -> None:
        """
        Ensure we have a valid session.

        Raises:
            VFSSessionExpiredError: If session is not valid or has expired
        """
        if not self.session:
            raise VFSSessionExpiredError("Not authenticated. Call login() first.")

        # Check if token has expired or is about to expire
        if datetime.now() >= self.session.expires_at:
            logger.warning("Token has expired, attempting refresh")
            await self._refresh_token()

    async def _refresh_token(self) -> None:
        """
        Refresh the authentication token.

        Raises:
            VFSAuthenticationError: If token refresh fails
        """
        if not self.session or not self.session.refresh_token:
            raise VFSAuthenticationError(
                "Cannot refresh token: No refresh token available. Please login again."
            )

        try:
            async with self._session.post(
                f"{VFS_API_BASE}/user/refresh", json={"refreshToken": self.session.refresh_token}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token refresh failed: {response.status} - {error_text}")
                    raise VFSAuthenticationError(
                        f"Token refresh failed with status {response.status}"
                    )

                data = await response.json()

                # Update session with new tokens
                token_refresh_buffer = int(
                    os.getenv(
                        "TOKEN_REFRESH_BUFFER_MINUTES", str(Defaults.TOKEN_REFRESH_BUFFER_MINUTES)
                    )
                )
                self.session.access_token = data["accessToken"]
                self.session.refresh_token = data.get("refreshToken", self.session.refresh_token)
                self.session.expires_at = datetime.now() + timedelta(
                    minutes=data.get("expiresIn", 60) - token_refresh_buffer
                )

                # Update session headers with new auth token
                self._session.headers.update(
                    {"Authorization": f"Bearer {self.session.access_token}"}
                )

                logger.info(f"Token refreshed successfully, expires at {self.session.expires_at}")
        except Exception as e:
            if isinstance(e, VFSAuthenticationError):
                raise
            logger.error(f"Token refresh failed: {e}")
            raise VFSSessionExpiredError(f"Token refresh failed: {e}")

    async def solve_turnstile(self, page_url: str, site_key: str) -> str:
        """
        Solve Cloudflare Turnstile captcha.

        Args:
            page_url: Page URL where Turnstile is displayed
            site_key: Turnstile site key

        Returns:
            Turnstile token
        """
        # type: ignore[no-any-return]
        return await self.captcha_solver.solve_turnstile(
            page_url=page_url, site_key=site_key
        )
