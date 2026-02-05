"""Adaptive scheduler - saate göre akıllı interval yönetimi."""
import logging
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class AdaptiveScheduler:
    """Saate ve güne göre check interval'ı otomatik ayarla."""

    # Türkiye saatine göre schedule
    SCHEDULE = {
        "peak": {
            "hours": [8, 9, 14, 15],
            "interval_min": 15,
            "interval_max": 30,
            "description": "Peak saatleri - Agresif mod",
        },
        "normal": {
            "hours": [10, 11, 12, 13, 16, 17, 18],
            "interval_min": 45,
            "interval_max": 60,
            "description": "Normal saatler",
        },
        "low": {
            "hours": [19, 20, 21, 22, 23, 0],
            "interval_min": 90,
            "interval_max": 120,
            "description": "Düşük aktivite",
        },
        "sleep": {
            "hours": [1, 2, 3, 4, 5, 6, 7],
            "interval_min": 600,
            "interval_max": 900,
            "description": "Uyku modu - 10-15 dakika",
        },
    }

    def __init__(self, timezone: str = "Europe/Istanbul", country_multiplier: float = 1.0):
        self.timezone = ZoneInfo(timezone)
        self.country_multiplier = country_multiplier

    def get_current_mode(self) -> str:
        """Mevcut saat için modu getir."""
        current_hour = datetime.now(self.timezone).hour

        for mode, config in self.SCHEDULE.items():
            hours: Any = config["hours"]
            if current_hour in hours:
                return mode

        return "normal"

    def get_optimal_interval(self) -> int:
        """Mevcut saat için optimal interval (saniye)."""
        import random

        mode = self.get_current_mode()
        config = self.SCHEDULE[mode]

        # Rastgele interval (min-max arası)
        interval_min: Any = config["interval_min"]
        interval_max: Any = config["interval_max"]
        base_interval = random.randint(interval_min, interval_max)

        # Ülke multiplier uygula
        adjusted_interval = int(base_interval / self.country_multiplier)

        # Minimum 10 saniye
        final_interval = max(10, adjusted_interval)

        logger.debug(f"Mode: {mode}, Base: {base_interval}s, Adjusted: {final_interval}s")
        return final_interval

    def get_mode_info(self) -> Dict[str, Any]:
        """Mevcut mod bilgisini getir."""
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
        """Uyku modunda mı?"""
        return self.get_current_mode() == "sleep"

    def should_pause(self) -> bool:
        """Bot duraklatılmalı mı? (Opsiyonel - gece tamamen durdurma)"""
        # Varsayılan: hayır, sadece yavaşlat
        return False
