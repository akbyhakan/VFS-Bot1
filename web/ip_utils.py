"""IP address validation and proxy utilities for FastAPI web application."""

import ipaddress
import os
from functools import lru_cache

from fastapi import Request


def _is_valid_ip(ip_str: str) -> bool:
    """Validate IP address format."""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


@lru_cache(maxsize=1)
def _get_trusted_proxies() -> frozenset[str]:
    """Parse trusted proxies once and cache."""
    trusted_proxies_str = os.getenv("TRUSTED_PROXIES", "")
    return frozenset(p.strip() for p in trusted_proxies_str.split(",") if p.strip())


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
