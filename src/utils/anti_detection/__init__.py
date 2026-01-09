"""Anti-detection utilities."""

__all__ = [
    "CloudflareHandler",
    "FingerprintBypass",
    "HumanSimulator",
    "StealthConfig",
    "TLSHandler",
]


def __getattr__(name):
    """Lazy import of anti-detection utilities to avoid missing dependencies."""
    if name == "CloudflareHandler":
        from .cloudflare_handler import CloudflareHandler

        return CloudflareHandler
    elif name == "FingerprintBypass":
        from .fingerprint_bypass import FingerprintBypass

        return FingerprintBypass
    elif name == "HumanSimulator":
        from .human_simulator import HumanSimulator

        return HumanSimulator
    elif name == "StealthConfig":
        from .stealth_config import StealthConfig

        return StealthConfig
    elif name == "TLSHandler":
        from .tls_handler import TLSHandler

        return TLSHandler

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
