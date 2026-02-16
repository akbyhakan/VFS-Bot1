"""VFS Slots Module - Handles centres, categories, and slot availability checking."""

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional

import aiohttp
from loguru import logger

from ...core.exceptions import VFSApiError, VFSRateLimitError
from ...utils.security.endpoint_rate_limiter import EndpointRateLimiter
from .encryption import get_vfs_api_base
from .models import CentreInfo, SlotAvailability, VisaCategoryInfo, VisaSubcategoryInfo

if TYPE_CHECKING:
    pass


class VFSSlots:
    """Handles VFS slot checking - centres, categories, and slot availability."""

    def __init__(
        self,
        endpoint_limiter: EndpointRateLimiter,
        http_session_getter: Callable[[], aiohttp.ClientSession],
        ensure_authenticated: Callable[[], Awaitable[None]],
        token_update_callback: Optional[Callable[[Any, Any], bool]] = None,
    ):
        """
        Initialize VFS slots handler.

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

    async def get_centres(self) -> List[CentreInfo]:
        """
        Get available VFS centres.

        Returns:
            List of centre information

        Raises:
            VFSRateLimitError: If rate limited by VFS (429 response)
            VFSApiError: If response is not valid JSON
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
            VFSApiError: If response is not valid JSON
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
            VFSApiError: If response is not valid JSON
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
            VFSApiError: If response is not valid JSON
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
                logger.error(f"Rate limited by VFS on slot check (429), retry after {retry_after}s")
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

            available_dates = data.get("availableDates", [])

            return SlotAvailability(
                available=len(available_dates) > 0,
                dates=available_dates,
                centre_id=centre_id,
                category_id=category_id,
                message=data.get("message"),
            )
