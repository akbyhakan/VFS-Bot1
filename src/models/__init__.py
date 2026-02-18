"""Database models module."""

import importlib as _importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .database import Database as Database
    from .schemas import AppointmentCreate as AppointmentCreate
    from .schemas import AppointmentResponse as AppointmentResponse
    from .schemas import UserCreate as UserCreate
    from .schemas import UserResponse as UserResponse

# Explicit lazy-loading map: name -> (module_path, attribute_name)
_LAZY_MODULE_MAP = {
    "Database": ("src.models.database", "Database"),
    "UserCreate": ("src.models.schemas", "UserCreate"),
    "UserResponse": ("src.models.schemas", "UserResponse"),
    "AppointmentCreate": ("src.models.schemas", "AppointmentCreate"),
    "AppointmentResponse": ("src.models.schemas", "AppointmentResponse"),
}

# Auto-derive __all__ from _LAZY_MODULE_MAP to prevent manual sync issues
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
