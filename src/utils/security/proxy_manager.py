"""Rotate proxies with failure tracking."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class ProxyManager:
    """Manage proxy rotation with failure tracking."""

    def __init__(self, config: Optional[Dict[Any, Any]] = None):
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
        self._allocation_index: int = 0

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

    def _parse_proxy(self, proxy_string: str) -> Optional[Dict[str, Any]]:
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



    def mark_proxy_failed(self, proxy: Dict[str, Any]) -> None:
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

    def rotate_proxy(self) -> Optional[Dict[str, Any]]:
        """Switch to next available proxy (sequential, skip failed)."""
        if not self.enabled or not self.proxies:
            return None

        total = len(self.proxies)
        attempts = 0

        while attempts < total:
            self.current_proxy_index = (self.current_proxy_index + 1) % total
            proxy = self.proxies[self.current_proxy_index]

            if proxy["server"] not in self.failed_proxies:
                logger.info(f"Rotated to proxy: {proxy['server']}")
                return proxy

            attempts += 1

        # All failed → reset and return next
        logger.warning("All proxies failed, resetting failed list")
        self.failed_proxies.clear()
        self.current_proxy_index = (self.current_proxy_index + 1) % total
        proxy = self.proxies[self.current_proxy_index]
        logger.info(f"Rotated to proxy after reset: {proxy['server']}")
        return proxy

    def get_playwright_proxy(
        self, proxy: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Return Playwright-compatible proxy format.

        Args:
            proxy: Proxy dictionary (if None, uses rotate_proxy)

        Returns:
            Playwright proxy configuration or None
        """
        if not self.enabled:
            return None

        if proxy is None:
            proxy = self.rotate_proxy()

        if not proxy:
            return None

        # Only include fields that Playwright accepts
        playwright_proxy: Dict[str, str] = {"server": proxy["server"]}

        if "username" in proxy and "password" in proxy:
            playwright_proxy["username"] = proxy["username"]
            playwright_proxy["password"] = proxy["password"]

        return playwright_proxy

    def get_current_proxy(self) -> Optional[Dict[str, Any]]:
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

    def allocate_next(self) -> Optional[Dict[str, Any]]:
        """
        Allocate the next proxy sequentially (deterministic allocation).
        
        This method provides deterministic proxy allocation for multi-mission scenarios,
        ensuring each browser gets a unique proxy in sequential order. The allocation
        index advances with each call and wraps around when reaching the end.
        
        Returns:
            Next proxy dictionary in sequence or None if disabled/no proxies
        """
        if not self.enabled or not self.proxies:
            return None

        total_proxies = len(self.proxies)
        attempts = 0
        
        # Try to find a non-failed proxy, wrapping around if needed
        while attempts < total_proxies:
            # Get proxy at current allocation index
            current_index = self._allocation_index
            proxy = self.proxies[current_index]
            
            # Advance allocation index for next call (with wrap-around)
            self._allocation_index = (self._allocation_index + 1) % total_proxies
            
            # Check if this proxy has failed
            if proxy["server"] not in self.failed_proxies:
                logger.info(
                    f"Allocated proxy {proxy['server']} (allocation index: {current_index})"
                )
                return proxy
            
            # Skip failed proxy and continue
            logger.debug(f"Skipping failed proxy {proxy['server']}")
            attempts += 1
        
        # All proxies have failed, reset failed list and return first proxy
        logger.warning("All proxies marked as failed, resetting failed list")
        self.failed_proxies.clear()
        
        # Reset to first proxy
        self._allocation_index = 1 % total_proxies
        proxy = self.proxies[0]
        logger.info(f"Allocated proxy {proxy['server']} after reset (allocation index: 0)")
        return proxy

    def reset_allocation_index(self) -> None:
        """Reset the allocation index to 0."""
        self._allocation_index = 0
        logger.info("Reset allocation index to 0")
