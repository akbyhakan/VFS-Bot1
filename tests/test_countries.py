"""Tests for countries configuration."""

import pytest
from src.core.countries import (
    validate_mission_code,
    get_route,
    get_country_info,
    get_all_mission_codes,
    SOURCE_COUNTRY_CODE,
    SOURCE_LANGUAGE,
    SUPPORTED_COUNTRIES,
)


def test_source_country():
    """Test source country constants."""
    assert SOURCE_COUNTRY_CODE == "tur"
    assert SOURCE_LANGUAGE == "tr"


def test_supported_countries_count():
    """Test that all 21 Schengen countries are supported."""
    assert len(SUPPORTED_COUNTRIES) == 21


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
