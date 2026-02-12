"""VFS Booking Module - Handles appointment booking."""

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

import aiohttp
from loguru import logger

from ...core.exceptions import VFSRateLimitError
from ...utils.security.endpoint_rate_limiter import EndpointRateLimiter
from .encryption import get_vfs_api_base
from .models import BookingResponse

if TYPE_CHECKING:
    pass


class VFSBooking:
    """Handles VFS appointment booking."""

    def __init__(
        self,
        endpoint_limiter: EndpointRateLimiter,
        http_session_getter: Callable[[], aiohttp.ClientSession],
        ensure_authenticated: Callable[[], Awaitable[None]],
    ):
        """
        Initialize VFS booking handler.

        Args:
            endpoint_limiter: Rate limiter for API endpoints
            http_session_getter: Callable that returns the HTTP session
            ensure_authenticated: Callable that ensures authentication is valid
        """
        self.endpoint_limiter = endpoint_limiter
        self._http_session_getter = http_session_getter
        self._ensure_authenticated = ensure_authenticated

    @property
    def _session(self) -> aiohttp.ClientSession:
        """Get HTTP session from parent client."""
        return self._http_session_getter()

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
