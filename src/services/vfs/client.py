"""VFS API Client - Main client implementation."""

import secrets
import time
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger

from ...core.countries import get_country_info, get_route, validate_mission_code
from ...utils.security.endpoint_rate_limiter import EndpointRateLimiter
from .auth import VFSAuth
from .booking import VFSBooking
from .models import (
    BookingResponse,
    CentreInfo,
    SlotAvailability,
    VFSSession,
    VisaCategoryInfo,
    VisaSubcategoryInfo,
)
from .slots import VFSSlots


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

        self._http_session: Optional[aiohttp.ClientSession] = None
        self._client_source: Optional[str] = None

        # Per-endpoint rate limiter (Issue 3.4)
        self.endpoint_limiter = EndpointRateLimiter()

        # Initialize modular components
        self._auth = VFSAuth(
            mission_code=mission_code,
            endpoint_limiter=self.endpoint_limiter,
            http_session_getter=lambda: self._session,
        )
        self._slots = VFSSlots(
            endpoint_limiter=self.endpoint_limiter,
            http_session_getter=lambda: self._session,
            ensure_authenticated=lambda: self._auth.ensure_authenticated(),
        )
        self._booking = VFSBooking(
            endpoint_limiter=self.endpoint_limiter,
            http_session_getter=lambda: self._session,
            ensure_authenticated=lambda: self._auth.ensure_authenticated(),
        )

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
                    "Chrome/135.0.0.0 Safari/537.36"
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

    @property
    def session(self) -> Optional[VFSSession]:
        """Get current session (for backward compatibility)."""
        return self._auth.session

    @session.setter
    def session(self, value: Optional[VFSSession]) -> None:
        """Set session (for backward compatibility)."""
        self._auth.session = value

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
        return await self._auth.login(email, password, turnstile_token)

    async def get_centres(self) -> List[CentreInfo]:
        """
        Get available VFS centres.

        Returns:
            List of centre information

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
        """
        return await self._slots.get_centres()

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
        return await self._slots.get_visa_categories(centre_id)

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
        return await self._slots.get_visa_subcategories(centre_id, category_id)

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
        return await self._slots.check_slot_availability(centre_id, category_id, subcategory_id)

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
        return await self._booking.book_appointment(slot_date, slot_time, applicant_data)

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
