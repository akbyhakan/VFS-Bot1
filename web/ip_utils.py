"""IP address validation and proxy utilities for FastAPI web application."""

import ipaddress
import os
import time
from typing import Optional

from fastapi import Request


def _is_valid_ip(ip_str: str) -> bool:
    """Validate IP address format."""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


# TTL-based cache for trusted proxies (replaces lru_cache for runtime updates)
_trusted_proxies_cache: Optional[frozenset[str]] = None
_trusted_proxies_cache_time: float = 0
_TRUSTED_PROXIES_TTL: int = 300  # 5 minutes TTL (matches JWT settings cache)


def _get_trusted_proxies() -> frozenset[str]:
    """
    Get trusted proxies with lazy initialization and TTL-based cache.

    This replaces lru_cache to support runtime configuration updates.
    Settings are cached for 5 minutes, then refreshed from environment.

    Returns:
        Frozenset of trusted proxy IP addresses
    """
    global _trusted_proxies_cache, _trusted_proxies_cache_time

    now = time.monotonic()

    # Return cached proxies if still valid
    if _trusted_proxies_cache is not None and (now - _trusted_proxies_cache_time) < _TRUSTED_PROXIES_TTL:
        return _trusted_proxies_cache

    # Load fresh proxies from environment
    trusted_proxies_str = os.getenv("TRUSTED_PROXIES", "")
    _trusted_proxies_cache = frozenset(p.strip() for p in trusted_proxies_str.split(",") if p.strip())
    _trusted_proxies_cache_time = now

    return _trusted_proxies_cache


def invalidate_trusted_proxies_cache() -> None:
    """
    Invalidate trusted proxies cache.

    This forces a reload of proxies from environment on next access.
    Useful for testing or when proxy configuration is updated at runtime.
    """
    global _trusted_proxies_cache, _trusted_proxies_cache_time
    _trusted_proxies_cache = None
    _trusted_proxies_cache_time = 0


def get_real_client_ip(request: Request) -> str:
    """
    Get real client IP with trusted proxy validation and IP format verification.

    Security: Only trust X-Forwarded-For from known proxies and validate
    IPs to prevent rate limit bypass attacks.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address
    """
    trusted_proxies = _get_trusted_proxies()

    client_host = request.client.host if request.client else "unknown"

    # Only trust forwarded headers from known proxies
    if trusted_proxies and client_host in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Parse all IPs in X-Forwarded-For chain
            ips = [ip.strip() for ip in forwarded.split(",")]
            # Return the first IP that is NOT a trusted proxy (rightmost untrusted IP)
            for ip in reversed(ips):
                if ip not in trusted_proxies and _is_valid_ip(ip):
                    return ip

        # Fallback to X-Real-IP if present and not a trusted proxy
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            real_ip = real_ip.strip()
            if real_ip not in trusted_proxies and _is_valid_ip(real_ip):
                return real_ip

    # Return client_host if it's a valid IP, otherwise return "unknown"
    return client_host if _is_valid_ip(client_host) else "unknown"
