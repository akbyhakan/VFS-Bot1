"""
VFS Global Country Configuration for Turkey to Schengen Countries.

Supports all 21 Schengen countries with proper mission codes and routes.
"""

from dataclasses import dataclass
from typing import Dict


# Turkey as source country
SOURCE_COUNTRY_CODE = "tur"
SOURCE_LANGUAGE = "tr"


@dataclass
class CountryInfo:
    """Country information."""
    code: str
    name_en: str
    name_tr: str
    route: str


# All 21 Schengen countries supported by VFS Global Turkey
SUPPORTED_COUNTRIES: Dict[str, CountryInfo] = {
    "fra": CountryInfo("fra", "France", "Fransa", "turkey/france"),
    "nld": CountryInfo("nld", "Netherlands", "Hollanda", "turkey/netherlands"),
    "aut": CountryInfo("aut", "Austria", "Avusturya", "turkey/austria"),
    "bel": CountryInfo("bel", "Belgium", "Belçika", "turkey/belgium"),
    "cze": CountryInfo("cze", "Czech Republic", "Çekya", "turkey/czech-republic"),
    "pol": CountryInfo("pol", "Poland", "Polonya", "turkey/poland"),
    "swe": CountryInfo("swe", "Sweden", "İsveç", "turkey/sweden"),
    "che": CountryInfo("che", "Switzerland", "İsviçre", "turkey/switzerland"),
    "fin": CountryInfo("fin", "Finland", "Finlandiya", "turkey/finland"),
    "est": CountryInfo("est", "Estonia", "Estonya", "turkey/estonia"),
    "lva": CountryInfo("lva", "Latvia", "Letonya", "turkey/latvia"),
    "ltu": CountryInfo("ltu", "Lithuania", "Litvanya", "turkey/lithuania"),
    "lux": CountryInfo("lux", "Luxembourg", "Lüksemburg", "turkey/luxembourg"),
    "mlt": CountryInfo("mlt", "Malta", "Malta", "turkey/malta"),
    "nor": CountryInfo("nor", "Norway", "Norveç", "turkey/norway"),
    "dnk": CountryInfo("dnk", "Denmark", "Danimarka", "turkey/denmark"),
    "isl": CountryInfo("isl", "Iceland", "İzlanda", "turkey/iceland"),
    "svn": CountryInfo("svn", "Slovenia", "Slovenya", "turkey/slovenia"),
    "hrv": CountryInfo("hrv", "Croatia", "Hırvatistan", "turkey/croatia"),
    "bgr": CountryInfo("bgr", "Bulgaria", "Bulgaristan", "turkey/bulgaria"),
    "svk": CountryInfo("svk", "Slovakia", "Slovakya", "turkey/slovakia"),
}


def validate_mission_code(mission_code: str) -> None:
    """
    Validate that mission code is supported.
    
    Args:
        mission_code: 3-letter country code (e.g., 'nld', 'fra')
        
    Raises:
        ValueError: If mission code is not supported
    """
    if mission_code not in SUPPORTED_COUNTRIES:
        supported = ", ".join(sorted(SUPPORTED_COUNTRIES.keys()))
        raise ValueError(
            f"Unsupported mission code: {mission_code}. "
            f"Supported countries: {supported}"
        )


def get_route(mission_code: str) -> str:
    """
    Get VFS route for a mission code.
    
    Args:
        mission_code: 3-letter country code
        
    Returns:
        Route string (e.g., 'turkey/netherlands')
        
    Raises:
        ValueError: If mission code is not supported
    """
    validate_mission_code(mission_code)
    return SUPPORTED_COUNTRIES[mission_code].route


def get_country_info(mission_code: str) -> CountryInfo:
    """
    Get country information for a mission code.
    
    Args:
        mission_code: 3-letter country code
        
    Returns:
        CountryInfo object
        
    Raises:
        ValueError: If mission code is not supported
    """
    validate_mission_code(mission_code)
    return SUPPORTED_COUNTRIES[mission_code]


def get_all_mission_codes() -> list[str]:
    """
    Get list of all supported mission codes.
    
    Returns:
        List of 3-letter country codes
    """
    return list(SUPPORTED_COUNTRIES.keys())
