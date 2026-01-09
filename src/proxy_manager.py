"""Rotate proxies with failure tracking."""

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manage proxy rotation with failure tracking."""

    def __init__(self, config: dict = None):
        """
        Initialize proxy manager.

        Args:
            config: Configuration dictionary with proxy settings
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.proxy_file = Path(self.config.get("file", "config/proxies.txt"))
        self.rotate_on_error = self.config.get("rotate_on_error", True)

        self.proxies: List[Dict[str, str]] = []
        self.failed_proxies: List[str] = []
        self.current_proxy_index: int = 0

        if self.enabled:
            self.load_proxies()

    def load_proxies(self) -> int:
        """
        Load proxies from file.

        Returns:
            Number of proxies loaded
        """
        if not self.proxy_file.exists():
            logger.warning(f"Proxy file not found: {self.proxy_file}")
            return 0

        try:
            with open(self.proxy_file, "r") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                proxy = self._parse_proxy(line)
                if proxy:
                    self.proxies.append(proxy)

            logger.info(f"Loaded {len(self.proxies)} proxies from {self.proxy_file}")
            return len(self.proxies)

        except Exception as e:
            logger.error(f"Error loading proxies: {e}")
            return 0

    def _parse_proxy(self, proxy_string: str) -> Optional[Dict[str, str]]:
        """
        Parse proxy string to dictionary.

        Formats supported:
        - host:port
        - user:pass@host:port
        - http://host:port
        - http://user:pass@host:port
        - socks5://host:port

        Args:
            proxy_string: Proxy string to parse

        Returns:
            Dictionary with proxy configuration or None on error
        """
        try:
            proxy_string = proxy_string.strip()

            # Check if protocol is specified
            if "://" in proxy_string:
                # Extract protocol
                protocol, rest = proxy_string.split("://", 1)
            else:
                protocol = "http"
                rest = proxy_string

            # Check for authentication
            if "@" in rest:
                auth, server = rest.split("@", 1)
                username, password = auth.split(":", 1)
            else:
                username = None
                password = None
                server = rest

            # Parse host and port
            if ":" in server:
                host, port_str = server.rsplit(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    logger.error(f"Invalid port number: {port_str}")
                    return None
            else:
                host = server
                port = 8080 if protocol == "http" else 1080

            proxy_dict = {
                "server": f"{protocol}://{host}:{port}",
                "host": host,
                "port": port,
                "protocol": protocol,
            }

            if username and password:
                proxy_dict["username"] = username
                proxy_dict["password"] = password

            return proxy_dict

        except Exception as e:
            logger.error(f"Error parsing proxy '{proxy_string}': {e}")
            return None

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """
        Select random proxy from available proxies.

        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.enabled or not self.proxies:
            return None

        # Get available proxies (not failed)
        available = [p for p in self.proxies if p["server"] not in self.failed_proxies]

        if not available:
            logger.warning("No available proxies (all failed), resetting failed list")
            self.failed_proxies.clear()
            available = self.proxies

        proxy = random.choice(available)
        logger.debug(f"Selected random proxy: {proxy['server']}")
        return proxy

    def mark_proxy_failed(self, proxy: Dict[str, str]) -> None:
        """
        Track failed proxy.

        Args:
            proxy: Proxy dictionary that failed
        """
        if proxy and proxy["server"] not in self.failed_proxies:
            self.failed_proxies.append(proxy["server"])
            logger.info(
                f"Marked proxy as failed: {proxy['server']} ({len(self.failed_proxies)} total)"
            )

    def rotate_proxy(self) -> Optional[Dict[str, str]]:
        """
        Switch to next proxy.

        Returns:
            Next proxy dictionary or None
        """
        if not self.enabled or not self.proxies:
            return None

        # Move to next proxy
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        proxy = self.proxies[self.current_proxy_index]

        # Skip if this one failed
        if proxy["server"] in self.failed_proxies:
            # Try to get a non-failed one
            return self.get_random_proxy()

        logger.info(f"Rotated to proxy: {proxy['server']}")
        return proxy

    def get_playwright_proxy(
        self, proxy: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Return Playwright-compatible proxy format.

        Args:
            proxy: Proxy dictionary (if None, uses random proxy)

        Returns:
            Playwright proxy configuration or None
        """
        if not self.enabled:
            return None

        if proxy is None:
            proxy = self.get_random_proxy()

        if not proxy:
            return None

        playwright_proxy = {"server": proxy["server"]}

        if "username" in proxy and "password" in proxy:
            playwright_proxy["username"] = proxy["username"]
            playwright_proxy["password"] = proxy["password"]

        return playwright_proxy

    def get_current_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get currently selected proxy.

        Returns:
            Current proxy dictionary or None
        """
        if not self.enabled or not self.proxies:
            return None

        return self.proxies[self.current_proxy_index]

    def clear_failed_proxies(self) -> None:
        """Clear the failed proxies list."""
        self.failed_proxies.clear()
        logger.info("Cleared failed proxies list")
