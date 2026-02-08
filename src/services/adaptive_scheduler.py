"""Adaptive scheduler - intelligent interval management based on time of day."""
import logging
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class AdaptiveScheduler:
    """Automatically adjust check intervals based on time of day and weekday."""

    # Schedule based on Turkey timezone
    SCHEDULE = {
        "peak": {
            "hours": [8, 9, 14, 15],
            "interval_min": 15,
            "interval_max": 30,
            "description": "Peak hours - Aggressive mode",
        },
        "normal": {
            "hours": [10, 11, 12, 13, 16, 17, 18],
            "interval_min": 45,
            "interval_max": 60,
            "description": "Normal hours",
        },
        "low": {
            "hours": [19, 20, 21, 22, 23, 0],
            "interval_min": 90,
            "interval_max": 120,
            "description": "Low activity",
        },
        "sleep": {
            "hours": [1, 2, 3, 4, 5, 6, 7],
            "interval_min": 600,
            "interval_max": 900,
            "description": "Sleep mode - 10-15 minutes",
        },
    }

    def __init__(self, timezone: str = "Europe/Istanbul", country_multiplier: float = 1.0):
        self.timezone = ZoneInfo(timezone)
        self.country_multiplier = country_multiplier

    def get_current_mode(self) -> str:
        """Get the scheduling mode for the current hour."""
        current_hour = datetime.now(self.timezone).hour

        for mode, config in self.SCHEDULE.items():
            hours: Any = config["hours"]
            if current_hour in hours:
                return mode

        return "normal"

    def get_optimal_interval(self) -> int:
        """Get optimal check interval in seconds for the current hour."""
        import random

        mode = self.get_current_mode()
        config = self.SCHEDULE[mode]

        # Random interval between min and max
        interval_min: Any = config["interval_min"]
        interval_max: Any = config["interval_max"]
        base_interval = random.randint(interval_min, interval_max)

        # Apply country multiplier
        adjusted_interval = int(base_interval / self.country_multiplier)

        # Minimum 10 seconds
        final_interval = max(10, adjusted_interval)

        logger.debug(f"Mode: {mode}, Base: {base_interval}s, Adjusted: {final_interval}s")
        return final_interval

    def get_mode_info(self) -> Dict[str, Any]:
        """Get current mode information."""
        mode = self.get_current_mode()
        config = self.SCHEDULE[mode]
        return {
            "mode": mode,
            "description": config["description"],
            "interval_range": f"{config['interval_min']}-{config['interval_max']}s",
            "current_hour": datetime.now(self.timezone).hour,
            "country_multiplier": self.country_multiplier,
        }

    def is_sleep_mode(self) -> bool:
        """Check if currently in sleep mode."""
        return self.get_current_mode() == "sleep"

    def should_pause(self) -> bool:
        """Check if bot should pause completely (optional - full night stop)."""
        # Default: no, just slow down
        return False
