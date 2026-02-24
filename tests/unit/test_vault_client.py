"""Unit tests for VaultClient."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.core.config.vault_client import VaultClient


class TestVaultClientInit:
    """Tests for VaultClient initialisation."""

    def test_default_values(self):
        """Test that defaults are read from environment variables."""
        with patch.dict(os.environ, {"VAULT_ADDR": "http://vault:8200", "VAULT_TOKEN": "s.token123"}):
            client = VaultClient()
        assert client.url == "http://vault:8200"
        assert client.token == "s.token123"
        assert client.mount_point == "secret"

    def test_fallback_url_when_env_not_set(self):
        """Test that url falls back to localhost when VAULT_ADDR is not set."""
        env = {k: v for k, v in os.environ.items() if k != "VAULT_ADDR"}
        with patch.dict(os.environ, env, clear=True):
            client = VaultClient()
        assert client.url == "http://127.0.0.1:8200"

    def test_custom_values(self):
        """Test that explicit arguments override environment variables."""
        client = VaultClient(
            url="https://vault.example.com",
            token="custom-token",
            mount_point="kv",
        )
        assert client.url == "https://vault.example.com"
        assert client.token == "custom-token"
        assert client.mount_point == "kv"

    def test_client_lazy_init(self):
        """Test that the hvac client is not created on __init__."""
        client = VaultClient()
        assert client._client is None


class TestVaultClientIsAvailable:
    """Tests for VaultClient.is_available()."""

    def test_returns_false_when_hvac_not_installed(self):
        """is_available() returns False when hvac cannot be imported."""
        client = VaultClient()
        with patch.object(client, "_ensure_hvac", side_effect=ImportError("no hvac")):
            assert client.is_available() is False

    def test_returns_false_when_vault_unreachable(self):
        """is_available() returns False when Vault server is unreachable."""
        client = VaultClient()
        mock_hvac = MagicMock()
        mock_hvac_client = MagicMock()
        mock_hvac_client.is_authenticated.side_effect = Exception("connection refused")
        mock_hvac.Client.return_value = mock_hvac_client
        with patch.object(client, "_ensure_hvac", return_value=mock_hvac):
            assert client.is_available() is False

    def test_returns_false_when_not_authenticated(self):
        """is_available() returns False when token is invalid."""
        client = VaultClient()
        mock_hvac = MagicMock()
        mock_hvac_client = MagicMock()
        mock_hvac_client.is_authenticated.return_value = False
        mock_hvac.Client.return_value = mock_hvac_client
        with patch.object(client, "_ensure_hvac", return_value=mock_hvac):
            assert client.is_available() is False

    def test_returns_true_when_authenticated(self):
        """is_available() returns True when Vault is reachable and authenticated."""
        client = VaultClient()
        mock_hvac = MagicMock()
        mock_hvac_client = MagicMock()
        mock_hvac_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_hvac_client
        with patch.object(client, "_ensure_hvac", return_value=mock_hvac):
            assert client.is_available() is True


class TestVaultClientGetSecret:
    """Tests for VaultClient.get_secret()."""

    def test_raises_import_error_when_hvac_missing(self):
        """get_secret() raises ImportError when hvac is not installed."""
        client = VaultClient()
        with patch.object(client, "_ensure_hvac", side_effect=ImportError("no hvac")):
            with pytest.raises(ImportError, match="hvac"):
                client.get_secret("some/path", "key")

    def test_returns_secret_value(self):
        """get_secret() returns the correct value from Vault."""
        client = VaultClient()
        mock_hvac_client = MagicMock()
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"my_key": "super-secret"}}
        }
        client._client = mock_hvac_client

        result = client.get_secret("app/config", "my_key")

        assert result == "super-secret"
        mock_hvac_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="app/config",
            mount_point="secret",
        )

    def test_raises_key_error_for_missing_key(self):
        """get_secret() raises KeyError when key is absent from secret data."""
        client = VaultClient()
        mock_hvac_client = MagicMock()
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"other_key": "value"}}
        }
        client._client = mock_hvac_client

        with pytest.raises(KeyError):
            client.get_secret("app/config", "missing_key")


class TestVaultClientGetDatabaseCredentials:
    """Tests for VaultClient.get_database_credentials()."""

    def test_returns_credentials_dict(self):
        """get_database_credentials() returns correctly structured dict."""
        client = VaultClient()
        mock_hvac_client = MagicMock()
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "host": "db.example.com",
                    "port": "5432",
                    "username": "vfs_user",
                    "password": "db-secret",
                    "database": "vfs_bot",
                }
            }
        }
        client._client = mock_hvac_client

        creds = client.get_database_credentials()

        assert creds["host"] == "db.example.com"
        assert creds["port"] == 5432
        assert creds["username"] == "vfs_user"
        assert creds["password"] == "db-secret"
        assert creds["database"] == "vfs_bot"

    def test_uses_defaults_for_optional_fields(self):
        """get_database_credentials() fills in defaults for optional fields."""
        client = VaultClient()
        mock_hvac_client = MagicMock()
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "username": "vfs_user",
                    "password": "db-secret",
                }
            }
        }
        client._client = mock_hvac_client

        creds = client.get_database_credentials()

        assert creds["host"] == "localhost"
        assert creds["port"] == 5432
        assert creds["database"] == "vfs_bot"
