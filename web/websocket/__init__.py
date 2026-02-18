"""WebSocket management for VFS-Bot web application."""

from .manager import ConnectionManager

__all__ = ["ConnectionManager", "websocket_endpoint", "update_bot_stats", "add_log"]


def __getattr__(name: str):
    """Lazy import handler functions to avoid circular imports with web.dependencies."""
    if name in ("websocket_endpoint", "update_bot_stats", "add_log"):
        from .handler import add_log, update_bot_stats, websocket_endpoint

        _exports = {
            "websocket_endpoint": websocket_endpoint,
            "update_bot_stats": update_bot_stats,
            "add_log": add_log,
        }
        # Cache in module globals for subsequent access
        globals().update(_exports)
        return _exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
