"""
TLS fingerprinting bypass using curl-cffi to mimic Chrome browser handshake.

Requirements:
    - curl-cffi: Required for Cloudflare bypass. Install with: pip install curl-cffi
"""

from typing import Any, Optional

from curl_cffi.requests import AsyncSession
from loguru import logger


class TLSHandler:
    """Handle TLS fingerprinting bypass using curl-cffi."""

    def __init__(self, impersonate: str = "chrome120"):
        """
        Initialize TLS handler.

        Args:
            impersonate: Browser to impersonate (e.g., chrome120, chrome119)
        """
        self.impersonate = impersonate
        self.session: Optional[AsyncSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()

    async def create_session(self) -> None:
        """Create async session with TLS impersonation."""
        try:
            self.session = AsyncSession(impersonate=self.impersonate)  # type: ignore[arg-type]
            logger.info(f"TLS session created with {self.impersonate} impersonation")
        except Exception as e:
            logger.error(f"Failed to create TLS session: {e}")
            self.session = None

    async def close_session(self) -> None:
        """Close the TLS session."""
        if self.session:
            try:
                await self.session.close()
                logger.info("TLS session closed")
            except Exception as e:
                logger.error(f"Error closing TLS session: {e}")
            finally:
                self.session = None

    async def request(self, method: str, url: str, **kwargs: Any) -> Optional[Any]:
        """
        Make HTTP request with TLS bypass.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            **kwargs: Additional request parameters

        Returns:
            Response object or None on failure
        """
        if not self.session:
            logger.warning("TLS session not initialized")
            return None

        try:
            response = await self.session.request(method, url, **kwargs)  # type: ignore[arg-type]
            logger.debug(f"TLS request successful: {method} {url}")
            return response
        except Exception as e:
            logger.error(f"TLS request failed: {e}")
            return None

    async def get(self, url: str, **kwargs: Any) -> Optional[Any]:
        """
        Make GET request with TLS bypass.

        Args:
            url: Target URL
            **kwargs: Additional request parameters

        Returns:
            Response object or None on failure
        """
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Optional[Any]:
        """
        Make POST request with TLS bypass.

        Args:
            url: Target URL
            **kwargs: Additional request parameters

        Returns:
            Response object or None on failure
        """
        return await self.request("POST", url, **kwargs)
