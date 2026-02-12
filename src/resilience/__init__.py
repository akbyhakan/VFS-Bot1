"""Central resilience package for anti-fragile bot operations.

This module provides unified resilience capabilities:
- ResilienceManager: Central orchestrator for all resilience features
- ForensicLogger: Country-aware black box logging with screenshots and DOM dumps
- SmartWait: 3-stage selector resolution (semantic → CSS → AI repair)
- AIRepairV2: Structured output AI repair with Pydantic models
- HotReloadableSelectorManager: File-polling based selector hot-reload
- RepairResult: Pydantic model for AI repair responses
"""

from src.resilience.ai_repair_v2 import AIRepairV2, RepairResult
from src.resilience.forensic_logger import ForensicLogger
from src.resilience.hot_reload import HotReloadableSelectorManager
from src.resilience.manager import ResilienceManager
from src.resilience.smart_wait import SmartWait

__all__ = [
    "ResilienceManager",
    "ForensicLogger",
    "SmartWait",
    "AIRepairV2",
    "RepairResult",
    "HotReloadableSelectorManager",
]
