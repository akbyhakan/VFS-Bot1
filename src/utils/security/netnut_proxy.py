"""NetNut proxy manager with CSV support."""

import csv
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.models.database import Database


def mask_proxy_password(proxy_endpoint: str) -> str:
    """
    Mask password in proxy endpoint for safe logging.

    Args:
        proxy_endpoint: Proxy endpoint in format server:port:username:password

    Returns:
        Masked endpoint with password replaced by ***
    """
    parts = proxy_endpoint.split(":")
    if len(parts) == 4:
        return f"{parts[0]}:{parts[1]}:{parts[2]}:***"
    return proxy_endpoint


class NetNutProxyManager:
    """Manage NetNut proxies with CSV loading and rotation."""

    def __init__(self):
        """Initialize NetNut proxy manager."""
        self.proxies: List[Dict[str, Any]] = []
        self.failed_proxies: List[str] = []
        self.current_proxy_index: int = 0
        self._allocation_index: int = 0

    def load_from_csv(self, file_path: Path) -> int:
        """
        Load proxies from CSV file.

        Expected CSV format:
        endpoint
        server:port:username:password

        Args:
            file_path: Path to CSV file

        Returns:
            Number of proxies loaded
        """
        if not file_path.exists():
            logger.warning(f"Proxy CSV file not found: {file_path}")
            return 0

        loaded_count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    endpoint = row.get("endpoint", "").strip()
                    if not endpoint or endpoint.startswith("#"):
                        continue

                    proxy = self._parse_netnut_endpoint(endpoint)
                    if proxy:
                        self.proxies.append(proxy)
                        loaded_count += 1

            logger.info(f"Loaded {loaded_count} proxies from {file_path}")
            return loaded_count

        except Exception as e:
            logger.error(f"Error loading proxies from CSV: {e}")
            return 0

    def load_from_csv_content(self, csv_content: str) -> int:
        """
        Load proxies from CSV content string.

        Args:
            csv_content: CSV content as string

        Returns:
            Number of proxies loaded
        """
        loaded_count = 0
        try:
            lines = csv_content.strip().split("\n")

            # Check if first line is header
            if lines and lines[0].strip().lower() == "endpoint":
                lines = lines[1:]  # Skip header

            for line in lines:
                endpoint = line.strip()
                if not endpoint or endpoint.startswith("#"):
                    continue

                proxy = self._parse_netnut_endpoint(endpoint)
                if proxy:
                    self.proxies.append(proxy)
                    loaded_count += 1

            logger.info(f"Loaded {loaded_count} proxies from CSV content")
            return loaded_count

        except Exception as e:
            logger.error(f"Error loading proxies from CSV content: {e}")
            return 0

    def _parse_netnut_endpoint(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Parse NetNut endpoint format.

        Format: server:port:username:password
        Example: gw.netnut.net:5959:ntnt_8zq7s8ef-res-tr-sid-657606515:Ab4ME55ouIYefAT

        Args:
            endpoint: NetNut endpoint string

        Returns:
            Dictionary with proxy configuration or None on error
        """
        try:
            parts = endpoint.split(":")

            if len(parts) != 4:
                logger.error(f"Invalid NetNut endpoint format: {endpoint}")
                return None

            server, port_str, username, password = parts

            try:
                port = int(port_str)
            except ValueError:
                logger.error(f"Invalid port number in endpoint: {port_str}")
                return None

            proxy_dict = {
                "server": f"http://{server}:{port}",
                "host": server,
                "port": port,
                "username": username,
                "password": password,
                "protocol": "http",
                "endpoint": endpoint,  # Store original endpoint for tracking
            }

            return proxy_dict

        except Exception as e:
            logger.error(f"Error parsing NetNut endpoint '{endpoint}': {e}")
            return None

    def get_random_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Select a random available proxy (not failed).

        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.proxies:
            return None

        # Get available proxies (not failed)
        available = [p for p in self.proxies if p["endpoint"] not in self.failed_proxies]

        if not available:
            logger.warning("No available proxies (all failed), resetting failed list")
            self.failed_proxies.clear()
            available = self.proxies

        proxy = random.choice(available)
        logger.debug(f"Selected random proxy: {proxy['server']}")
        return proxy

    def rotate_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Switch to next proxy in rotation.

        Returns:
            Next proxy dictionary or None
        """
        if not self.proxies:
            return None

        # Move to next proxy
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        proxy = self.proxies[self.current_proxy_index]

        # Skip if this one failed
        if proxy["endpoint"] in self.failed_proxies:
            # Try to get a non-failed one
            return self.get_random_proxy()

        logger.info(f"Rotated to proxy: {proxy['server']}")
        return proxy

    def mark_proxy_failed(self, proxy: Dict[str, Any]) -> None:
        """
        Mark proxy as failed.

        Args:
            proxy: Proxy dictionary that failed
        """
        if proxy and proxy["endpoint"] not in self.failed_proxies:
            self.failed_proxies.append(proxy["endpoint"])
            logger.info(
                f"Marked proxy as failed: {proxy['endpoint']} "
                f"({len(self.failed_proxies)} total failed)"
            )

    def get_playwright_proxy(
        self, proxy: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Return Playwright-compatible proxy format.

        Args:
            proxy: Proxy dictionary (if None, uses random proxy)

        Returns:
            Playwright proxy configuration or None
        """
        if proxy is None:
            proxy = self.get_random_proxy()

        if not proxy:
            return None

        # Playwright proxy format
        playwright_proxy: Dict[str, str] = {
            "server": proxy["server"],
            "username": proxy["username"],
            "password": proxy["password"],
        }

        return playwright_proxy

    def get_stats(self) -> Dict[str, int]:
        """
        Get proxy statistics.

        Returns:
            Dictionary with total, active, and failed proxy counts
        """
        total = len(self.proxies)
        failed = len(self.failed_proxies)
        active = total - failed

        return {
            "total": total,
            "active": active,
            "failed": failed,
        }

    def get_proxy_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all proxies with status.

        Returns:
            List of proxy dictionaries with status
        """
        proxy_list = []
        for proxy in self.proxies:
            proxy_info = {
                "endpoint": proxy["endpoint"],
                "host": proxy["host"],
                "port": proxy["port"],
                "username": proxy["username"],
                "status": "failed" if proxy["endpoint"] in self.failed_proxies else "active",
            }
            proxy_list.append(proxy_info)

        return proxy_list

    def clear_all(self) -> None:
        """Clear all proxies and failed proxy tracking."""
        self.proxies.clear()
        self.failed_proxies.clear()
        self.current_proxy_index = 0
        logger.info("Cleared all proxies")

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
            Next proxy dictionary in sequence or None if no proxies
        """
        if not self.proxies:
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
            
            # Check if this proxy has failed (NetNut uses 'endpoint' for tracking)
            if proxy["endpoint"] not in self.failed_proxies:
                logger.info(
                    f"Allocated proxy {mask_proxy_password(proxy['endpoint'])} "
                    f"(allocation index: {current_index})"
                )
                return proxy
            
            # Skip failed proxy and continue
            logger.debug(f"Skipping failed proxy {mask_proxy_password(proxy['endpoint'])}")
            attempts += 1
        
        # All proxies have failed, reset failed list and return first proxy
        logger.warning("All proxies marked as failed, resetting failed list")
        self.failed_proxies.clear()
        
        # Reset to first proxy
        self._allocation_index = 1 % total_proxies
        proxy = self.proxies[0]
        logger.info(
            f"Allocated proxy {mask_proxy_password(proxy['endpoint'])} "
            f"after reset (allocation index: 0)"
        )
        return proxy

    def reset_allocation_index(self) -> None:
        """Reset the allocation index to 0."""
        self._allocation_index = 0
        logger.info("Reset allocation index to 0")

    async def load_from_database(self, db: "Database") -> int:
        """
        Load proxies from database with decrypted passwords.

        Args:
            db: Database instance

        Returns:
            Number of proxies loaded
        """
        try:
            proxies = await db.get_active_proxies()
            loaded_count = 0

            for proxy in proxies:
                proxy_dict = {
                    "id": proxy["id"],
                    "server": f"http://{proxy['server']}:{proxy['port']}",
                    "host": proxy["server"],
                    "port": proxy["port"],
                    "username": proxy["username"],
                    "password": proxy["password"],  # Already decrypted by database layer
                    "protocol": "http",
                    "endpoint": f"{proxy['server']}:{proxy['port']}:{proxy['username']}",
                }
                self.proxies.append(proxy_dict)
                loaded_count += 1

            logger.info(f"Loaded {loaded_count} proxies from database")
            return loaded_count

        except Exception as e:
            logger.error(f"Error loading proxies from database: {e}")
            return 0
