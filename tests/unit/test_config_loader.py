"""Tests for core/config_loader module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.core.config.config_loader import (
    load_config,
    load_env_variables,
    substitute_env_vars,
)

# Minimal valid config for testing
MINIMAL_VALID_CONFIG_YAML = """
vfs:
  base_url: https://test.vfsglobal.com
  country: tst
  mission: tst
  centres: [Test Centre]
bot:
  check_interval: 30
  headless: true
captcha:
  provider: 2captcha
  api_key: test_key
notifications:
  telegram:
    enabled: false
"""


class TestLoadEnvVariables:
    """Tests for load_env_variables function."""

    @patch("src.core.config.config_loader.load_dotenv")
    @patch("pathlib.Path.exists")
    def test_load_env_variables_file_exists(self, mock_exists, mock_load_dotenv):
        """Test loading environment variables when .env file exists."""
        mock_exists.return_value = True
        load_env_variables()
        mock_load_dotenv.assert_called_once()

    @patch("src.core.config.config_loader.load_dotenv")
    @patch("pathlib.Path.exists")
    def test_load_env_variables_file_not_exists(self, mock_exists, mock_load_dotenv):
        """Test loading environment variables when .env file doesn't exist."""
        mock_exists.return_value = False
        load_env_variables()
        mock_load_dotenv.assert_not_called()

    def test_load_env_variables_path_resolves_to_project_root(self):
        """Test that .env path resolves to project root, not src/ directory."""
        import src.core.config.config_loader as config_loader_module

        # Get the actual location of config_loader.py
        config_loader_file = Path(config_loader_module.__file__)

        # Verify that 4 parents points to project root
        env_path_4_parents = config_loader_file.parent.parent.parent.parent / ".env"

        # Verify that 3 parents would incorrectly point to src/
        env_path_3_parents = config_loader_file.parent.parent.parent / ".env"

        # The correct path (4 parents) should have 'VFS-Bot1' or similar as parent directory name
        # The incorrect path (3 parents) should have 'src' as parent directory name
        assert env_path_3_parents.parent.name == "src", "3 parents should point to src/.env"
        assert (
            env_path_4_parents.parent.name != "src"
        ), "4 parents should NOT point to src directory"

        # Verify the path ends with .env
        assert env_path_4_parents.name == ".env"


class TestSubstituteEnvVars:
    """Tests for substitute_env_vars function."""

    def test_substitute_simple_string(self):
        """Test substituting a simple environment variable in string."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = substitute_env_vars("${TEST_VAR}")
            assert result == "test_value"

    def test_substitute_string_with_text(self):
        """Test substituting env var in string with surrounding text."""
        with patch.dict(os.environ, {"HOST": "localhost"}):
            result = substitute_env_vars("http://${HOST}:8080")
            assert result == "http://localhost:8080"

    def test_substitute_multiple_vars(self):
        """Test substituting multiple environment variables."""
        with patch.dict(os.environ, {"USER": "admin", "PASS": "secret"}):
            result = substitute_env_vars("${USER}:${PASS}")
            assert result == "admin:secret"

    def test_substitute_missing_var(self):
        """Test substituting missing environment variable."""
        # Set development environment to ensure dev mode behavior
        with patch.dict(os.environ, {"ENV": "development"}, clear=True):
            result = substitute_env_vars("${MISSING_VAR}")
            assert result == ""

    def test_substitute_dict(self):
        """Test substituting environment variables in dictionary."""
        with patch.dict(os.environ, {"VAR1": "value1", "VAR2": "value2"}):
            config = {"key1": "${VAR1}", "key2": "${VAR2}"}
            result = substitute_env_vars(config)
            assert result == {"key1": "value1", "key2": "value2"}

    def test_substitute_nested_dict(self):
        """Test substituting env vars in nested dictionary."""
        with patch.dict(os.environ, {"DB_HOST": "localhost"}):
            config = {"database": {"host": "${DB_HOST}"}}
            result = substitute_env_vars(config)
            assert result == {"database": {"host": "localhost"}}

    def test_substitute_list(self):
        """Test substituting environment variables in list."""
        with patch.dict(os.environ, {"ITEM": "test"}):
            config = ["${ITEM}", "static"]
            result = substitute_env_vars(config)
            assert result == ["test", "static"]

    def test_substitute_non_string(self):
        """Test substitute_env_vars with non-string values."""
        assert substitute_env_vars(42) == 42
        assert substitute_env_vars(True) is True
        assert substitute_env_vars(None) is None

    def test_substitute_no_pattern(self):
        """Test string without env var pattern."""
        result = substitute_env_vars("no variables here")
        assert result == "no variables here"

    def test_substitute_critical_env_var_missing_production(self):
        """Test that missing critical env var raises ValueError in production."""
        with patch.dict(os.environ, {"ENV": "production"}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                substitute_env_vars("${ENCRYPTION_KEY}")
            assert "CRITICAL" in str(exc_info.value)
            assert "ENCRYPTION_KEY" in str(exc_info.value)

    def test_substitute_critical_env_var_missing_development(self):
        """Test that missing critical env var logs warning but returns empty string in dev."""
        import logging

        with patch.dict(os.environ, {"ENV": "development"}, clear=True):
            with patch("src.core.config.config_loader.logger") as mock_logger:
                result = substitute_env_vars("${VFS_ENCRYPTION_KEY}")
                assert result == ""
                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[0][0]
                assert "VFS_ENCRYPTION_KEY" in call_args
                assert "not set" in call_args

    def test_substitute_critical_env_var_set(self):
        """Test that critical env var is substituted when set."""
        with patch.dict(os.environ, {"ENCRYPTION_KEY": "test-key-123"}):
            result = substitute_env_vars("${ENCRYPTION_KEY}")
            assert result == "test-key-123"


class TestLoadConfig:
    """Tests for load_config function."""

    @patch("builtins.open", new_callable=mock_open, read_data=MINIMAL_VALID_CONFIG_YAML)
    @patch("src.core.config.config_loader.substitute_env_vars")
    def test_load_config_basic(self, mock_substitute, mock_file):
        """Test loading basic config file."""
        mock_substitute.side_effect = lambda x: x
        result = load_config("test_config.yaml")
        assert isinstance(result, dict)
        assert "vfs" in result
        assert "bot" in result
        mock_file.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data=MINIMAL_VALID_CONFIG_YAML.replace("test_key", "${VAR}"))
    @patch.dict(os.environ, {"VAR": "value"})
    def test_load_config_with_env_vars(self, mock_file):
        """Test loading config with environment variable substitution."""
        result = load_config("test_config.yaml")
        assert result["captcha"]["api_key"] == "value"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_load_config_file_not_found(self, mock_file):
        """Test load_config with non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_config("missing.yaml")

    @patch("builtins.open", new_callable=mock_open, read_data="invalid yaml: : :")
    def test_load_config_invalid_yaml(self, mock_file):
        """Test load_config with invalid YAML."""
        with pytest.raises(Exception):
            load_config("invalid.yaml")

    @patch("builtins.open", new_callable=mock_open, read_data=MINIMAL_VALID_CONFIG_YAML)
    def test_load_config_nested_structure(self, mock_file):
        """Test loading config with nested structure."""
        result = load_config("nested.yaml")
        assert "vfs" in result
        assert result["vfs"]["country"] == "tst"

    @patch("pathlib.Path.exists")
    def test_load_config_no_fallback_in_production(self, mock_exists):
        """Test that config loading raises error in production when file is missing."""
        # Config file doesn't exist, example also doesn't exist
        mock_exists.return_value = False

        with patch.dict(os.environ, {"ENV": "production"}):
            with pytest.raises(FileNotFoundError) as exc_info:
                load_config("missing.yaml")
            assert "CRITICAL" in str(exc_info.value)
            assert "production" in str(exc_info.value)

    @patch("src.core.config.config_validator.ConfigValidator.validate", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="example: config\n")
    def test_load_config_fallback_in_development(self, mock_file, mock_validate):
        """Test that config loading falls back to example in development."""
        with patch.dict(os.environ, {"ENV": "development"}):
            with patch("pathlib.Path.exists") as mock_exists:
                # Multiple calls to exists() during load_config:
                # First: .env path check in load_env_variables()
                # Second: main config file check
                # Third: example config file check (should return True)
                mock_exists.side_effect = [False, False, True]

                # Should not raise an error in development mode
                result = load_config("config/config.yaml")

                # Result should contain the example config data
                assert result == {"example": "config"}
