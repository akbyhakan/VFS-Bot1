"""VFS Booking Module - Handles appointment booking."""

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

import aiohttp
from loguru import logger

from ...core.exceptions import VFSApiError, VFSRateLimitError
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
        token_update_callback: Optional[Callable[[Any, Any], bool]] = None,
    ):
        """
        Initialize VFS booking handler.

        Args:
            endpoint_limiter: Rate limiter for API endpoints
            http_session_getter: Callable that returns the HTTP session
            ensure_authenticated: Callable that ensures authentication is valid
            token_update_callback: Optional callback to update token from response data
        """
        self.endpoint_limiter = endpoint_limiter
        self._http_session_getter = http_session_getter
        self._ensure_authenticated = ensure_authenticated
        self._token_update_callback = token_update_callback

    @property
    def _session(self) -> aiohttp.ClientSession:
        """Get HTTP session from parent client."""
        return self._http_session_getter()

    def _check_token_update(self, data: Any, response_headers: Any) -> None:
        """
        Check and update token from response data (non-critical operation).

        Args:
            data: Parsed response data
            response_headers: Response headers
        """
        if self._token_update_callback:
            try:
                self._token_update_callback(data, response_headers)
            except Exception as e:
                # Token update is non-critical, log and continue
                logger.debug(f"Token update callback failed (non-critical): {e}")

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
            VFSApiError: If response is not valid JSON
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

            # Explicit Read & Pass: body'yi güvenli şekilde bir kere oku
            try:
                data = await response.json()
            except (aiohttp.ContentTypeError, ValueError) as e:
                # Sunucu JSON yerine HTML/text dönerse (bakım sayfası, hata sayfası vb.)
                error_text = await response.text()
                logger.error(
                    f"Unexpected non-JSON response (status={response.status}): "
                    f"{error_text[:200]}..."
                )
                raise VFSApiError(f"Non-JSON response from VFS API: {response.status}")

            # Dinamik token takibi: aynı data objesini kontrolcüye gönder
            self._check_token_update(data, response.headers)

            if response.status == 200:
                logger.info(f"Appointment booked: {slot_date} {slot_time}")
            else:
                logger.error(f"Booking failed: {data}")

            result: BookingResponse = data
            return result
