"""Enhanced User-Agent rotation with real browser versions."""

import logging
import random
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HeaderManager:
    """Dynamic header management with UA rotation."""

    # Updated user agents (Jan 2024)
    USER_AGENTS: List[Dict[str, str]] = [
        {
            "ua": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "platform": "Windows",
        },
        {
            "ua": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="121", "Google Chrome";v="121"',
            "platform": "Windows",
        },
        {
            "ua": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "platform": "macOS",
        },
        {
            "ua": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "platform": "Linux",
        },
        {
            "ua": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
            ),
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "platform": "Windows",
        },
    ]

    def __init__(self, base_url: str = "https://visa.vfsglobal.com", rotation_interval: int = 10):
        """
        Initialize header manager.

        Args:
            base_url: Base URL for referer
            rotation_interval: Rotate UA every N requests
        """
        self.base_url = base_url
        self.rotation_interval = rotation_interval
        self.request_count = 0
        self.current_ua = random.choice(self.USER_AGENTS)
        logger.info(f"HeaderManager initialized with {self.current_ua['platform']} UA")

    def rotate_user_agent(self) -> None:
        """Rotate to new user agent."""
        old_ua = self.current_ua
        # Ensure we get a different UA
        available = [ua for ua in self.USER_AGENTS if ua != old_ua]
        self.current_ua = random.choice(available)
        logger.info(f"Rotated UA: {self.current_ua['platform']}")

    def get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """
        Get headers with automatic rotation.

        Args:
            referer: Custom referer URL

        Returns:
            Headers dictionary
        """
        # Auto-rotate based on interval
        self.request_count += 1
        if self.request_count % self.rotation_interval == 0:
            self.rotate_user_agent()

        return {
            "User-Agent": self.current_ua["ua"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
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
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.current_ua["platform"]}"',
            "Referer": referer or self.base_url,
        }

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
        # Auto-rotate based on interval
        self.request_count += 1
        if self.request_count % self.rotation_interval == 0:
            self.rotate_user_agent()

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
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": f'"{self.current_ua["platform"]}"',
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        if referer:
            headers["Referer"] = referer

        return headers

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
