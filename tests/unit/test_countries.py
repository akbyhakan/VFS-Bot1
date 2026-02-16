"""Tests for VFS Global Turkey countries configuration."""

import pytest

from src.constants.countries import (
    SOURCE_COUNTRY_CODE,
    SOURCE_LANGUAGE,
    SUPPORTED_COUNTRIES,
    CountryInfo,
    MissionCode,
    get_all_supported_codes,
    get_country_info,
    get_route,
    validate_mission_code,
)


class TestMissionCode:
    """Test MissionCode enum."""

    def test_all_mission_codes_are_strings(self):
        """Test that all mission codes are valid strings."""
        for code in MissionCode:
            assert isinstance(code.value, str)
            assert len(code.value) == 3  # All country codes are 3 letters
            assert code.value.islower()  # All lowercase

    def test_mission_code_count(self):
        """Test that we have exactly 21 Schengen countries."""
        assert len(MissionCode) == 21

    def test_specific_mission_codes(self):
        """Test that specific mission codes exist."""
        assert MissionCode.FRANCE == "fra"
        assert MissionCode.NETHERLANDS == "nld"
        assert MissionCode.CROATIA == "hrv"
        assert MissionCode.BULGARIA == "bgr"
        assert MissionCode.SWITZERLAND == "che"


class TestCountryInfo:
    """Test CountryInfo NamedTuple."""

    def test_country_info_structure(self):
        """Test CountryInfo has correct fields."""
        info = CountryInfo(code="fra", name_en="France", name_tr="Fransa")
        assert info.code == "fra"
        assert info.name_en == "France"
        assert info.name_tr == "Fransa"


class TestSourceCountry:
    """Test source country constants."""

    def test_source_country_is_turkey(self):
        """Test that source country is always Turkey."""
        assert SOURCE_COUNTRY_CODE == "tur"
        assert SOURCE_LANGUAGE == "tr"


class TestSupportedCountries:
    """Test SUPPORTED_COUNTRIES dictionary."""

    def test_all_countries_have_required_fields(self):
        """Test that all countries have complete information."""
        for code, info in SUPPORTED_COUNTRIES.items():
            assert isinstance(code, str)
            assert len(code) == 3
            assert isinstance(info, CountryInfo)
            assert info.code == code
            assert len(info.name_en) > 0
            assert len(info.name_tr) > 0
            # centres field removed - should be fetched dynamically

    def test_country_count(self):
        """Test that we have exactly 21 supported countries."""
        assert len(SUPPORTED_COUNTRIES) == 21

    def test_specific_countries_exist(self):
        """Test that specific countries are in the dictionary."""
        assert "fra" in SUPPORTED_COUNTRIES
        assert "nld" in SUPPORTED_COUNTRIES
        assert "hrv" in SUPPORTED_COUNTRIES
        assert "bgr" in SUPPORTED_COUNTRIES

    # Tests for static centres removed - centres should be fetched dynamically via CentreFetcher


class TestGetRoute:
    """Test get_route function."""

    def test_get_route_valid_mission(self):
        """Test route generation for valid missions."""
        assert get_route("nld") == "tur/tr/nld"
        assert get_route("fra") == "tur/tr/fra"
        assert get_route("hrv") == "tur/tr/hrv"

    def test_get_route_invalid_mission(self):
        """Test route generation raises error for invalid missions."""
        with pytest.raises(ValueError, match="Unsupported mission code"):
            get_route("deu")  # Germany - not supported

        with pytest.raises(ValueError, match="Unsupported mission code"):
            get_route("usa")  # USA - not in Schengen

        with pytest.raises(ValueError, match="Unsupported mission code"):
            get_route("xxx")  # Invalid code

    def test_get_route_all_supported_countries(self):
        """Test route generation for all supported countries."""
        for code in SUPPORTED_COUNTRIES.keys():
            route = get_route(code)
            assert route.startswith("tur/tr/")
            assert route.endswith(f"/{code}")


class TestValidateMissionCode:
    """Test validate_mission_code function."""

    def test_validate_valid_missions(self):
        """Test validation passes for valid missions."""
        for code in SUPPORTED_COUNTRIES.keys():
            # Should not raise
            validate_mission_code(code)

    def test_validate_invalid_missions(self):
        """Test validation fails for invalid missions."""
        invalid_codes = ["deu", "esp", "ita", "prt", "usa", "gbr", "xxx"]
        for code in invalid_codes:
            with pytest.raises(ValueError, match="Unsupported mission code"):
                validate_mission_code(code)

    def test_validation_error_message_contains_supported_list(self):
        """Test that error message lists supported countries."""
        try:
            validate_mission_code("xxx")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            assert "Supported Schengen countries:" in error_msg
            # Check a few countries are mentioned
            assert "fra" in error_msg
            assert "nld" in error_msg


class TestGetCountryInfo:
    """Test get_country_info function."""

    def test_get_info_valid_mission(self):
        """Test getting info for valid missions."""
        info = get_country_info("nld")
        assert info.code == "nld"
        assert info.name_en == "Netherlands"
        assert info.name_tr == "Hollanda"
        # centres field removed - should be fetched dynamically

    def test_get_info_invalid_mission(self):
        """Test getting info raises error for invalid missions."""
        with pytest.raises(ValueError, match="Unsupported mission code"):
            get_country_info("deu")

    def test_get_info_all_countries(self):
        """Test getting info for all supported countries."""
        for code in SUPPORTED_COUNTRIES.keys():
            info = get_country_info(code)
            assert info.code == code
            assert len(info.name_en) > 0
            assert len(info.name_tr) > 0
            # centres field removed - should be fetched dynamically


class TestGetAllSupportedCodes:
    """Test get_all_supported_codes function."""

    def test_returns_list_of_codes(self):
        """Test that function returns list of codes."""
        codes = get_all_supported_codes()
        assert isinstance(codes, list)
        assert len(codes) == 21

    def test_all_codes_are_strings(self):
        """Test that all codes are strings."""
        codes = get_all_supported_codes()
        for code in codes:
            assert isinstance(code, str)
            assert len(code) == 3

    def test_contains_expected_codes(self):
        """Test that list contains expected codes."""
        codes = get_all_supported_codes()
        assert "fra" in codes
        assert "nld" in codes
        assert "hrv" in codes
        assert "bgr" in codes


class TestIntegration:
    """Integration tests for countries module."""

    def test_complete_workflow(self):
        """Test a complete workflow using the module."""
        # Get all supported codes
        codes = get_all_supported_codes()
        assert len(codes) > 0

        # Pick a code
        code = "nld"
        assert code in codes

        # Validate it
        validate_mission_code(code)  # Should not raise

        # Get route
        route = get_route(code)
        assert route == "tur/tr/nld"

        # Get country info
        info = get_country_info(code)
        assert info.code == code

        # Note: centres removed - should be fetched dynamically via CentreFetcher

    def test_all_mission_codes_in_supported_countries(self):
        """Test that all MissionCode enum values are in SUPPORTED_COUNTRIES."""
        for mission in MissionCode:
            assert mission.value in SUPPORTED_COUNTRIES

    def test_all_supported_countries_are_in_mission_code(self):
        """Test that all SUPPORTED_COUNTRIES are in MissionCode enum."""
        mission_values = [m.value for m in MissionCode]
        for code in SUPPORTED_COUNTRIES.keys():
            assert code in mission_values
