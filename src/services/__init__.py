"""Business logic services module."""

import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot_service import VFSBot as VFSBot
    from .captcha_solver import CaptchaSolver as CaptchaSolver
    from .centre_fetcher import CentreFetcher as CentreFetcher
    from .notification import NotificationService as NotificationService

_LAZY_MODULE_MAP = {
    "VFSBot": ("src.services.bot_service", "VFSBot"),
    "CaptchaSolver": ("src.services.captcha_solver", "CaptchaSolver"),
    "CentreFetcher": ("src.services.centre_fetcher", "CentreFetcher"),
    "NotificationService": ("src.services.notification", "NotificationService"),
}

__all__ = list(_LAZY_MODULE_MAP.keys())


def __getattr__(name: str):
    """Lazy import with explicit mapping - importlib based."""
    if name in _LAZY_MODULE_MAP:
        module_path, attr_name = _LAZY_MODULE_MAP[name]
        module = _importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
