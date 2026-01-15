"""Tests for VFS Global Turkey countries configuration."""

import pytest
from src.core.countries import (
    CountryInfo,
    SOURCE_COUNTRY_CODE,
    SOURCE_LANGUAGE,
    SUPPORTED_COUNTRIES,
    validate_mission_code,
    get_route,
    get_country_info,
    get_all_mission_codes,
    get_centres_for_mission,
)


def test_source_country():
    """Test source country constants."""
    assert SOURCE_COUNTRY_CODE == "tur"
    assert SOURCE_LANGUAGE == "tr"


def test_supported_countries_count():
    """Test that all 21 Schengen countries are supported."""
    assert len(SUPPORTED_COUNTRIES) == 21


def test_all_countries_have_required_fields():
    """Test that all countries have complete information."""
    for code, info in SUPPORTED_COUNTRIES.items():
        assert isinstance(code, str)
        assert len(code) == 3
        assert isinstance(info, CountryInfo)
        assert info.code == code
        assert len(info.name_en) > 0
        assert len(info.name_tr) > 0
        assert len(info.centres) > 0
        assert info.route.startswith("turkey/")


def test_all_countries_have_istanbul():
    """Test that Istanbul is a centre for all countries."""
    for info in SUPPORTED_COUNTRIES.values():
        assert "Istanbul" in info.centres


def test_france_has_six_centres():
    """Test that France has the most centres."""
    france = SUPPORTED_COUNTRIES["fra"]
    assert len(france.centres) == 6
    assert "Gaziantep" in france.centres
    assert "Antalya" in france.centres
    assert "Bursa" in france.centres


def test_bulgaria_has_edirne():
    """Test that Bulgaria has Edirne centre."""
    bulgaria = SUPPORTED_COUNTRIES["bgr"]
    assert "Edirne" in bulgaria.centres


def test_validate_mission_code_valid():
    """Test validation with valid mission codes."""
    # Should not raise for valid codes
    validate_mission_code("nld")
    validate_mission_code("fra")
    validate_mission_code("hrv")


def test_validate_mission_code_invalid():
    """Test validation with invalid mission code."""
    with pytest.raises(ValueError, match="Unsupported mission code"):
        validate_mission_code("xxx")
    
    with pytest.raises(ValueError, match="Unsupported mission code"):
        validate_mission_code("usa")


def test_get_route():
    """Test getting route for mission codes."""
    assert get_route("nld") == "turkey/netherlands"
    assert get_route("fra") == "turkey/france"
    assert get_route("hrv") == "turkey/croatia"


def test_get_route_invalid():
    """Test getting route with invalid mission code."""
    with pytest.raises(ValueError):
        get_route("invalid")


def test_get_country_info():
    """Test getting country information."""
    info = get_country_info("nld")
    assert info.code == "nld"
    assert info.name_en == "Netherlands"
    assert info.name_tr == "Hollanda"
    assert info.route == "turkey/netherlands"


def test_get_country_info_all_countries():
    """Test country info for all supported countries."""
    for code in SUPPORTED_COUNTRIES.keys():
        info = get_country_info(code)
        assert info.code == code
        assert info.name_en
        assert info.name_tr
        assert info.route.startswith("turkey/")


def test_get_all_mission_codes():
    """Test getting all mission codes."""
    codes = get_all_mission_codes()
    assert len(codes) == 21
    assert "nld" in codes
    assert "fra" in codes
    assert "hrv" in codes


def test_all_routes_unique():
    """Test that all routes are unique."""
    routes = [info.route for info in SUPPORTED_COUNTRIES.values()]
    assert len(routes) == len(set(routes))


def test_all_names_exist():
    """Test that all countries have English and Turkish names."""
    for info in SUPPORTED_COUNTRIES.values():
        assert info.name_en
        assert info.name_tr
        assert len(info.name_en) > 0
        assert len(info.name_tr) > 0


def test_get_centres_for_mission():
    """Test getting centres for valid missions."""
    centres = get_centres_for_mission("nld")
    assert isinstance(centres, list)
    assert "Istanbul" in centres
    assert "Ankara" in centres
    assert "Izmir" in centres


def test_get_centres_for_mission_invalid():
    """Test getting centres raises error for invalid missions."""
    with pytest.raises(ValueError, match="Unsupported mission code"):
        get_centres_for_mission("deu")


def test_get_centres_france():
    """Test getting centres for France (has most centres)."""
    centres = get_centres_for_mission("fra")
    assert len(centres) == 6
    assert "Istanbul" in centres
    assert "Gaziantep" in centres


def test_get_centres_bulgaria():
    """Test getting centres for Bulgaria (has Edirne)."""
    centres = get_centres_for_mission("bgr")
    assert "Edirne" in centres
