"""Selector management module for VFS-Bot.

This module consolidates all selector-related functionality including:
- Selector management and country-aware selection
- Adaptive learning and AI-powered repair
- Health monitoring and self-healing capabilities
"""

from src.selector.ai_repair import AISelectorRepair
from src.selector.learning import SelectorLearner
from src.selector.manager import CountryAwareSelectorManager, get_selector_manager
from src.selector.self_healing import SelectorSelfHealing
from src.selector.watcher import SelectorHealthCheck

# Alias for backward compatibility
SelectorManager = CountryAwareSelectorManager

__all__ = [
    "CountryAwareSelectorManager",
    "SelectorManager",
    "get_selector_manager",
    "SelectorLearner",
    "SelectorHealthCheck",
    "AISelectorRepair",
    "SelectorSelfHealing",
]


# Import ResilienceManager at the end to avoid circular import
def __getattr__(name):
    """Lazy import for ResilienceManager to avoid circular imports."""
    if name == "ResilienceManager":
        from src.resilience import ResilienceManager

        return ResilienceManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
