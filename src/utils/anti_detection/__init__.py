"""Anti-detection utilities."""

import importlib as _importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cloudflare_handler import CloudflareHandler as CloudflareHandler
    from .fingerprint_bypass import FingerprintBypass as FingerprintBypass
    from .human_simulator import HumanSimulator as HumanSimulator
    from .stealth_config import StealthConfig as StealthConfig
    from .tls_handler import TLSHandler as TLSHandler

_LAZY_MODULE_MAP = {
    "CloudflareHandler": ("src.utils.anti_detection.cloudflare_handler", "CloudflareHandler"),
    "FingerprintBypass": ("src.utils.anti_detection.fingerprint_bypass", "FingerprintBypass"),
    "HumanSimulator": ("src.utils.anti_detection.human_simulator", "HumanSimulator"),
    "StealthConfig": ("src.utils.anti_detection.stealth_config", "StealthConfig"),
    "TLSHandler": ("src.utils.anti_detection.tls_handler", "TLSHandler"),
}

__all__ = list(_LAZY_MODULE_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazy import with explicit mapping - importlib based."""
    if name in _LAZY_MODULE_MAP:
        module_path, attr_name = _LAZY_MODULE_MAP[name]
        module = _importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
