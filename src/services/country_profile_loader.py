"""Ülke profil yükleyici."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class CountryProfileLoader:
    """Ülke profillerini yükle ve yönet."""

    def __init__(self, config_path: str = "config/country_profiles.yaml"):
        self.config_path = Path(config_path)
        self._profiles: Dict[str, Any] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """YAML dosyasından profilleri yükle."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self._profiles = data.get("country_profiles", {})

    def get_profile(self, country_code: str) -> Optional[Dict[str, Any]]:
        """Ülke profilini getir."""
        return self._profiles.get(country_code.lower())

    def get_retry_multiplier(self, country_code: str) -> float:
        """Ülke için retry multiplier getir."""
        profile = self.get_profile(country_code)
        if profile:
            multiplier: float = profile.get("retry_multiplier", 1.0)
            return multiplier
        return 1.0

    def get_timezone(self, country_code: str) -> str:
        """Ülke timezone'ını getir."""
        profile = self.get_profile(country_code)
        if profile:
            timezone: str = profile.get("timezone", "Europe/Istanbul")
            return timezone
        return "Europe/Istanbul"

    def get_all_countries(self) -> Dict[str, Any]:
        """Tüm ülke profillerini getir."""
        return self._profiles
