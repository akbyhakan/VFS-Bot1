"""Ülke profil yükleyici."""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class CountryProfileLoader:
    """Ülke profillerini yükle ve yönet."""
    
    def __init__(self, config_path: str = "config/country_profiles.yaml"):
        self.config_path = Path(config_path)
        self._profiles: Dict[str, Any] = {}
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """YAML dosyasından profilleri yükle."""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._profiles = data.get('country_profiles', {})
    
    def get_profile(self, country_code: str) -> Optional[Dict[str, Any]]:
        """Ülke profilini getir."""
        return self._profiles.get(country_code.lower())
    
    def get_retry_multiplier(self, country_code: str) -> float:
        """Ülke için retry multiplier getir."""
        profile = self.get_profile(country_code)
        return profile.get('retry_multiplier', 1.0) if profile else 1.0
    
    def get_timezone(self, country_code: str) -> str:
        """Ülke timezone'ını getir."""
        profile = self.get_profile(country_code)
        return profile.get('timezone', 'Europe/Istanbul') if profile else 'Europe/Istanbul'
    
    def get_all_countries(self) -> Dict[str, Any]:
        """Tüm ülke profillerini getir."""
        return self._profiles
