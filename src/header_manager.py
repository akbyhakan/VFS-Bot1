"""Dynamic header rotation with consistent User-Agent and Sec-CH-UA headers."""

import logging
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class HeaderManager:
    """Manage HTTP headers with dynamic rotation."""

    # User-Agent strings for different browsers
    USER_AGENTS = [
        {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_mobile": "?0",
        },
        {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_mobile": "?0",
        },
        {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_mobile": "?0",
        },
    ]

    def __init__(self):
        """Initialize header manager with random User-Agent."""
        self.current_ua_index = random.randint(0, len(self.USER_AGENTS) - 1)
        self.current_ua = self.USER_AGENTS[self.current_ua_index]
        logger.info(f"HeaderManager initialized with UA index {self.current_ua_index}")

    def get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """
        Get complete header set with referer.

        Args:
            referer: Optional referer URL

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "User-Agent": self.current_ua["ua"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-CH-UA": self.current_ua["sec_ch_ua"],
            "Sec-CH-UA-Mobile": self.current_ua["sec_ch_ua_mobile"],
            "Sec-CH-UA-Platform": self.current_ua["sec_ch_ua_platform"],
            "Cache-Control": "max-age=0",
        }

        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"

        return headers

    def get_api_headers(
        self, token: Optional[str] = None, referer: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get API-specific headers with Bearer token.

        Args:
            token: Optional Bearer token
            referer: Optional referer URL

        Returns:
            Dictionary of HTTP headers for API requests
        """
        headers = {
            "User-Agent": self.current_ua["ua"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/json",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-CH-UA": self.current_ua["sec_ch_ua"],
            "Sec-CH-UA-Mobile": self.current_ua["sec_ch_ua_mobile"],
            "Sec-CH-UA-Platform": self.current_ua["sec_ch_ua_platform"],
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        if referer:
            headers["Referer"] = referer

        return headers

    def rotate_user_agent(self) -> None:
        """Switch to new User-Agent."""
        # Select a different UA
        new_index = self.current_ua_index
        while new_index == self.current_ua_index and len(self.USER_AGENTS) > 1:
            new_index = random.randint(0, len(self.USER_AGENTS) - 1)

        self.current_ua_index = new_index
        self.current_ua = self.USER_AGENTS[self.current_ua_index]
        logger.info(f"User-Agent rotated to index {self.current_ua_index}")

    def get_user_agent(self) -> str:
        """
        Get current User-Agent string.

        Returns:
            Current User-Agent string
        """
        return self.current_ua["ua"]

    def get_sec_ch_ua(self) -> str:
        """
        Get current Sec-CH-UA header.

        Returns:
            Current Sec-CH-UA header value
        """
        return self.current_ua["sec_ch_ua"]
