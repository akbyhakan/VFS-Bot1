"""VFS Global Turkey - Supported Schengen Countries Configuration."""

from typing import Dict, List
from dataclasses import dataclass


# Turkey as source country
SOURCE_COUNTRY_CODE = "tur"
SOURCE_LANGUAGE = "tr"


@dataclass
class CountryInfo:
    """Country information with centres and route."""
    code: str
    name_en: str
    name_tr: str
    route: str
    centres: List[str]


# All 21 Schengen countries supported by VFS Global Turkey
SUPPORTED_COUNTRIES: Dict[str, CountryInfo] = {
    "fra": CountryInfo(
        code="fra",
        name_en="France",
        name_tr="Fransa",
        route="turkey/france",
        centres=["Istanbul", "Ankara", "Izmir", "Gaziantep", "Antalya", "Bursa"]
    ),
    "nld": CountryInfo(
        code="nld",
        name_en="Netherlands",
        name_tr="Hollanda",
        route="turkey/netherlands",
        centres=["Istanbul", "Ankara", "Izmir"]
    ),
    "aut": CountryInfo(
        code="aut",
        name_en="Austria",
        name_tr="Avusturya",
        route="turkey/austria",
        centres=["Istanbul", "Ankara"]
    ),
    "bel": CountryInfo(
        code="bel",
        name_en="Belgium",
        name_tr="Belçika",
        route="turkey/belgium",
        centres=["Istanbul", "Ankara"]
    ),
    "cze": CountryInfo(
        code="cze",
        name_en="Czech Republic",
        name_tr="Çekya",
        route="turkey/czech-republic",
        centres=["Istanbul", "Ankara"]
    ),
    "pol": CountryInfo(
        code="pol",
        name_en="Poland",
        name_tr="Polonya",
        route="turkey/poland",
        centres=["Istanbul", "Ankara", "Izmir"]
    ),
    "swe": CountryInfo(
        code="swe",
        name_en="Sweden",
        name_tr="İsveç",
        route="turkey/sweden",
        centres=["Istanbul", "Ankara"]
    ),
    "che": CountryInfo(
        code="che",
        name_en="Switzerland",
        name_tr="İsviçre",
        route="turkey/switzerland",
        centres=["Istanbul", "Ankara", "Izmir"]
    ),
    "fin": CountryInfo(
        code="fin",
        name_en="Finland",
        name_tr="Finlandiya",
        route="turkey/finland",
        centres=["Istanbul", "Ankara"]
    ),
    "est": CountryInfo(
        code="est",
        name_en="Estonia",
        name_tr="Estonya",
        route="turkey/estonia",
        centres=["Istanbul", "Ankara"]
    ),
    "lva": CountryInfo(
        code="lva",
        name_en="Latvia",
        name_tr="Letonya",
        route="turkey/latvia",
        centres=["Istanbul", "Ankara"]
    ),
    "ltu": CountryInfo(
        code="ltu",
        name_en="Lithuania",
        name_tr="Litvanya",
        route="turkey/lithuania",
        centres=["Istanbul", "Ankara"]
    ),
    "lux": CountryInfo(
        code="lux",
        name_en="Luxembourg",
        name_tr="Lüksemburg",
        route="turkey/luxembourg",
        centres=["Istanbul", "Ankara"]
    ),
    "mlt": CountryInfo(
        code="mlt",
        name_en="Malta",
        name_tr="Malta",
        route="turkey/malta",
        centres=["Istanbul", "Ankara"]
    ),
    "nor": CountryInfo(
        code="nor",
        name_en="Norway",
        name_tr="Norveç",
        route="turkey/norway",
        centres=["Istanbul", "Ankara"]
    ),
    "dnk": CountryInfo(
        code="dnk",
        name_en="Denmark",
        name_tr="Danimarka",
        route="turkey/denmark",
        centres=["Istanbul", "Ankara"]
    ),
    "isl": CountryInfo(
        code="isl",
        name_en="Iceland",
        name_tr="İzlanda",
        route="turkey/iceland",
        centres=["Istanbul", "Ankara"]
    ),
    "svn": CountryInfo(
        code="svn",
        name_en="Slovenia",
        name_tr="Slovenya",
        route="turkey/slovenia",
        centres=["Istanbul", "Ankara"]
    ),
    "hrv": CountryInfo(
        code="hrv",
        name_en="Croatia",
        name_tr="Hırvatistan",
        route="turkey/croatia",
        centres=["Istanbul", "Ankara"]
    ),
    "bgr": CountryInfo(
        code="bgr",
        name_en="Bulgaria",
        name_tr="Bulgaristan",
        route="turkey/bulgaria",
        centres=["Istanbul", "Ankara", "Edirne"]
    ),
    "svk": CountryInfo(
        code="svk",
        name_en="Slovakia",
        name_tr="Slovakya",
        route="turkey/slovakia",
        centres=["Istanbul", "Ankara"]
    ),
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


def get_all_mission_codes() -> List[str]:
    """
    Get list of all supported mission codes.
    
    Returns:
        List of 3-letter country codes
    """
    return list(SUPPORTED_COUNTRIES.keys())


def get_centres_for_mission(mission_code: str) -> List[str]:
    """
    Get available VFS centres for a mission.
    
    Args:
        mission_code: Target country code
        
    Returns:
        List of centre names
        
    Raises:
        ValueError: If mission code is not supported
    """
    validate_mission_code(mission_code)
    return SUPPORTED_COUNTRIES[mission_code].centres
