"""Tests for country_profile_loader module."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from src.services.data_sync.country_profile_loader import CountryProfileLoader


class TestCountryProfileLoader:
    """Tests for CountryProfileLoader class."""

    @pytest.fixture
    def sample_yaml_content(self):
        """Sample YAML content for testing."""
        return """version: "1.0"
country_profiles:
  nld:
    name: "Hollanda"
    name_en: "Netherlands"
    default_mode: "dynamic"
    timezone: "Europe/Amsterdam"
    language: "nl"
    retry_multiplier: 1.5
  deu:
    name: "Almanya"
    name_en: "Germany"
    default_mode: "dynamic"
    timezone: "Europe/Berlin"
    language: "de"
    retry_multiplier: 1.0
"""

    def test_load_profiles_success(self, sample_yaml_content, tmp_path):
        """Test successful loading of country profiles."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))

        assert "nld" in loader._profiles
        assert "deu" in loader._profiles
        assert loader._profiles["nld"]["name"] == "Hollanda"

    def test_load_profiles_file_not_exists(self, tmp_path):
        """Test loading when config file doesn't exist."""
        config_file = tmp_path / "nonexistent.yaml"

        loader = CountryProfileLoader(str(config_file))

        assert loader._profiles == {}

    def test_get_profile_exists(self, sample_yaml_content, tmp_path):
        """Test getting an existing profile."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        profile = loader.get_profile("nld")

        assert profile is not None
        assert profile["name"] == "Hollanda"
        assert profile["timezone"] == "Europe/Amsterdam"

    def test_get_profile_case_insensitive(self, sample_yaml_content, tmp_path):
        """Test that country code lookup is case insensitive."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        profile = loader.get_profile("NLD")

        assert profile is not None
        assert profile["name"] == "Hollanda"

    def test_get_profile_not_exists(self, sample_yaml_content, tmp_path):
        """Test getting a non-existent profile."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        profile = loader.get_profile("zzz")

        assert profile is None

    def test_get_retry_multiplier_exists(self, sample_yaml_content, tmp_path):
        """Test getting retry multiplier for existing country."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        multiplier = loader.get_retry_multiplier("nld")

        assert multiplier == 1.5

    def test_get_retry_multiplier_default(self, sample_yaml_content, tmp_path):
        """Test getting retry multiplier for non-existent country."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        multiplier = loader.get_retry_multiplier("zzz")

        assert multiplier == 1.0

    def test_get_timezone_exists(self, sample_yaml_content, tmp_path):
        """Test getting timezone for existing country."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        timezone = loader.get_timezone("deu")

        assert timezone == "Europe/Berlin"

    def test_get_timezone_default(self, sample_yaml_content, tmp_path):
        """Test getting timezone for non-existent country."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        timezone = loader.get_timezone("zzz")

        assert timezone == "Europe/Istanbul"

    def test_get_all_countries(self, sample_yaml_content, tmp_path):
        """Test getting all country profiles."""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(sample_yaml_content)

        loader = CountryProfileLoader(str(config_file))
        all_countries = loader.get_all_countries()

        assert len(all_countries) == 2
        assert "nld" in all_countries
        assert "deu" in all_countries

    def test_warning_logged_for_unsupported_country(self, tmp_path):
        """Test that a warning is logged for country codes not in SUPPORTED_COUNTRIES."""
        yaml_content = """version: "1.0"
country_profiles:
  nld:
    name: "Hollanda"
    name_en: "Netherlands"
    default_mode: "dynamic"
    timezone: "Europe/Amsterdam"
    language: "nl"
    retry_multiplier: 1.5
  deu:
    name: "Almanya"
    name_en: "Germany"
    default_mode: "dynamic"
    timezone: "Europe/Berlin"
    language: "de"
    retry_multiplier: 1.0
"""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(yaml_content)

        with patch(
            "src.services.data_sync.country_profile_loader.logger"
        ) as mock_logger:
            CountryProfileLoader(str(config_file))
            # deu is not in SUPPORTED_COUNTRIES, so a warning should be logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "deu" in str(call)
            ]
            assert len(warning_calls) == 1

    def test_no_warning_for_supported_country(self, tmp_path):
        """Test that no warning is logged for supported country codes."""
        yaml_content = """version: "1.0"
country_profiles:
  nld:
    name: "Hollanda"
    name_en: "Netherlands"
    default_mode: "dynamic"
    timezone: "Europe/Amsterdam"
    language: "nl"
    retry_multiplier: 1.5
"""
        config_file = tmp_path / "country_profiles.yaml"
        config_file.write_text(yaml_content)

        with patch(
            "src.services.data_sync.country_profile_loader.logger"
        ) as mock_logger:
            CountryProfileLoader(str(config_file))
            mock_logger.warning.assert_not_called()

