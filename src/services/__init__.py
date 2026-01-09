"""Business logic services module."""

__all__ = [
    "VFSBot",
    "CaptchaSolver",
    "CaptchaProvider",
    "CentreFetcher",
    "NotificationService",
]


def __getattr__(name):
    """Lazy import of services to avoid missing dependencies."""
    if name == "VFSBot":
        from .bot_service import VFSBot

        return VFSBot
    elif name == "CaptchaSolver":
        from .captcha_solver import CaptchaSolver

        return CaptchaSolver
    elif name == "CaptchaProvider":
        from .captcha_solver import CaptchaProvider

        return CaptchaProvider
    elif name == "CentreFetcher":
        from .centre_fetcher import CentreFetcher

        return CentreFetcher
    elif name == "NotificationService":
        from .notification import NotificationService

        return NotificationService

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
