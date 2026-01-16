"""VFS Global Turkey - Supported Schengen Countries Configuration."""

from typing import Dict, List, NamedTuple
from enum import Enum


class MissionCode(str, Enum):
    """Supported mission (target country) codes for VFS Turkey."""

    FRANCE = "fra"
    NETHERLANDS = "nld"
    AUSTRIA = "aut"
    BELGIUM = "bel"
    CZECHIA = "cze"
    POLAND = "pol"
    SWEDEN = "swe"
    SWITZERLAND = "che"
    FINLAND = "fin"
    ESTONIA = "est"
    LATVIA = "lva"
    LITHUANIA = "ltu"
    LUXEMBOURG = "lux"
    MALTA = "mlt"
    NORWAY = "nor"
    DENMARK = "dnk"
    ICELAND = "isl"
    SLOVENIA = "svn"
    CROATIA = "hrv"
    BULGARIA = "bgr"
    SLOVAKIA = "svk"


class CountryInfo(NamedTuple):
    """Country information."""
    code: str
    name_en: str
    name_tr: str


# Source country is always Turkey
SOURCE_COUNTRY_CODE = "tur"
SOURCE_LANGUAGE = "tr"


# Supported target countries with their VFS centres in Turkey
SUPPORTED_COUNTRIES: Dict[str, CountryInfo] = {
    "fra": CountryInfo(
        code="fra",
        name_en="France",
        name_tr="Fransa"
    ),
    "nld": CountryInfo(
        code="nld",
        name_en="Netherlands",
        name_tr="Hollanda"
    ),
    "aut": CountryInfo(
        code="aut",
        name_en="Austria",
        name_tr="Avusturya"
    ),
    "bel": CountryInfo(
        code="bel",
        name_en="Belgium",
        name_tr="Belçika"
    ),
    "cze": CountryInfo(
        code="cze",
        name_en="Czechia",
        name_tr="Çekya"
    ),
    "pol": CountryInfo(
        code="pol",
        name_en="Poland",
        name_tr="Polonya"
    ),
    "swe": CountryInfo(
        code="swe",
        name_en="Sweden",
        name_tr="İsveç"
    ),
    "che": CountryInfo(
        code="che",
        name_en="Switzerland",
        name_tr="İsviçre"
    ),
    "fin": CountryInfo(
        code="fin",
        name_en="Finland",
        name_tr="Finlandiya"
    ),
    "est": CountryInfo(
        code="est",
        name_en="Estonia",
        name_tr="Estonya"
    ),
    "lva": CountryInfo(
        code="lva",
        name_en="Latvia",
        name_tr="Letonya"
    ),
    "ltu": CountryInfo(
        code="ltu",
        name_en="Lithuania",
        name_tr="Litvanya"
    ),
    "lux": CountryInfo(
        code="lux",
        name_en="Luxembourg",
        name_tr="Lüksemburg"
    ),
    "mlt": CountryInfo(
        code="mlt",
        name_en="Malta",
        name_tr="Malta"
    ),
    "nor": CountryInfo(
        code="nor",
        name_en="Norway",
        name_tr="Norveç"
    ),
    "dnk": CountryInfo(
        code="dnk",
        name_en="Denmark",
        name_tr="Danimarka"
    ),
    "isl": CountryInfo(
        code="isl",
        name_en="Iceland",
        name_tr="İzlanda"
    ),
    "svn": CountryInfo(
        code="svn",
        name_en="Slovenia",
        name_tr="Slovenya"
    ),
    "hrv": CountryInfo(
        code="hrv",
        name_en="Croatia",
        name_tr="Hırvatistan"
    ),
    "bgr": CountryInfo(
        code="bgr",
        name_en="Bulgaria",
        name_tr="Bulgaristan"
    ),
    "svk": CountryInfo(
        code="svk",
        name_en="Slovakia",
        name_tr="Slovakya"
    ),
}


def get_route(mission_code: str) -> str:
    """
    Get VFS route string for a mission.

    Args:
        mission_code: Target country code (e.g., 'nld', 'fra')

    Returns:
        Route string (e.g., 'tur/tr/nld')

    Raises:
        ValueError: If mission code is not supported
    """
    validate_mission_code(mission_code)
    return f"{SOURCE_COUNTRY_CODE}/{SOURCE_LANGUAGE}/{mission_code}"


def validate_mission_code(mission_code: str) -> None:
    """
    Validate that a mission code is supported.

    Args:
        mission_code: Target country code

    Raises:
        ValueError: If mission code is not in supported list
    """
    if mission_code not in SUPPORTED_COUNTRIES:
        supported = ", ".join(sorted(SUPPORTED_COUNTRIES.keys()))
        raise ValueError(
            f"Unsupported mission code: '{mission_code}'. "
            f"Supported Schengen countries: {supported}"
        )


def get_country_info(mission_code: str) -> CountryInfo:
    """
    Get country information.

    Args:
        mission_code: Target country code

    Returns:
        CountryInfo with code, names, and centres
    """
    validate_mission_code(mission_code)
    return SUPPORTED_COUNTRIES[mission_code]


def get_all_supported_codes() -> List[str]:
    """Get list of all supported mission codes."""
    return list(SUPPORTED_COUNTRIES.keys())


def get_centres_for_mission(mission_code: str) -> List[str]:
    """
    Get available VFS centres for a mission.

    DEPRECATED: Centres should be fetched dynamically from VFS website
    using CentreFetcher instead of this static list.

    Args:
        mission_code: Target country code

    Returns:
        Empty list (deprecated)

    Raises:
        DeprecationWarning: This function is deprecated
    """
    import warnings
    warnings.warn(
        "get_centres_for_mission() is deprecated. Use CentreFetcher to fetch centres dynamically.",
        DeprecationWarning,
        stacklevel=2
    )
    return []
