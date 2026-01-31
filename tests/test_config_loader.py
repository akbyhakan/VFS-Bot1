"""Tests for core/config_loader module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from src.core.config_loader import (
    load_env_variables,
    substitute_env_vars,
    load_config,
)


class TestLoadEnvVariables:
    """Tests for load_env_variables function."""

    @patch("src.core.config_loader.load_dotenv")
    @patch("pathlib.Path.exists")
    def test_load_env_variables_file_exists(self, mock_exists, mock_load_dotenv):
        """Test loading environment variables when .env file exists."""
        mock_exists.return_value = True
        load_env_variables()
        mock_load_dotenv.assert_called_once()

    @patch("src.core.config_loader.load_dotenv")
    @patch("pathlib.Path.exists")
    def test_load_env_variables_file_not_exists(self, mock_exists, mock_load_dotenv):
        """Test loading environment variables when .env file doesn't exist."""
        mock_exists.return_value = False
        load_env_variables()
        mock_load_dotenv.assert_not_called()


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
        with patch.dict(os.environ, {}, clear=True):
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


class TestLoadConfig:
    """Tests for load_config function."""

    @patch("builtins.open", new_callable=mock_open, read_data="key: value\n")
    @patch("src.core.config_loader.substitute_env_vars")
    def test_load_config_basic(self, mock_substitute, mock_file):
        """Test loading basic config file."""
        mock_substitute.side_effect = lambda x: x
        result = load_config("test_config.yaml")
        assert isinstance(result, dict)
        mock_file.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data="key: ${VAR}\n")
    @patch.dict(os.environ, {"VAR": "value"})
    def test_load_config_with_env_vars(self, mock_file):
        """Test loading config with environment variable substitution."""
        result = load_config("test_config.yaml")
        assert result["key"] == "value"

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

    @patch("builtins.open", new_callable=mock_open, read_data="nested:\n  key: value\n")
    def test_load_config_nested_structure(self, mock_file):
        """Test loading config with nested structure."""
        result = load_config("nested.yaml")
        assert "nested" in result
        assert result["nested"]["key"] == "value"
