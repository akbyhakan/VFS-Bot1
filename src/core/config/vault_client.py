"""HashiCorp Vault client for self-hosted secret management.

This module provides a VaultClient class that integrates with a HashiCorp Vault
instance running on-premises or in a private network.  It uses the ``hvac``
library which is an optional dependency.  Install it with::

    pip install vfs-bot[vault]

If ``hvac`` is not installed, :py:meth:`VaultClient.is_available` returns
``False`` and all other methods raise :py:exc:`ImportError`.
"""

import os
from typing import Any

from loguru import logger


class VaultClient:
    """Client for reading secrets from a HashiCorp Vault KV v2 mount.

    Args:
        url: Vault server address.  Defaults to the ``VAULT_ADDR`` environment
            variable, falling back to ``http://127.0.0.1:8200``.
        token: Vault authentication token.  Defaults to ``VAULT_TOKEN`` env var.
        mount_point: KV v2 mount point (default: ``"secret"``).
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        mount_point: str = "secret",
    ) -> None:
        self.url = url or os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        self.token = token or os.environ.get("VAULT_TOKEN", "")
        self.mount_point = mount_point
        self._client: Any = None  # lazy-initialised hvac.Client

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_hvac(self) -> Any:
        """Import hvac and raise a helpful error when not installed.

        Returns:
            The ``hvac`` module.

        Raises:
            ImportError: When ``hvac`` is not installed.
        """
        try:
            import hvac  # noqa: PLC0415

            return hvac
        except ImportError as exc:
            raise ImportError(
                "The 'hvac' package is required for Vault integration.  "
                "Install it with: pip install vfs-bot[vault]"
            ) from exc

    def _get_client(self) -> Any:
        """Return (and lazily initialise) the hvac.Client instance.

        Returns:
            An authenticated ``hvac.Client``.
        """
        if self._client is None:
            hvac = self._ensure_hvac()
            logger.debug("Connecting to Vault at {}", self.url)
            self._client = hvac.Client(url=self.url, token=self.token)
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_secret(self, path: str, key: str) -> str:
        """Read a single key from a KV v2 secret.

        Args:
            path: Secret path relative to the mount point (e.g. ``"vfs-bot/app"``).
            key: Key name within the secret data.

        Returns:
            The secret value as a string.

        Raises:
            ImportError: When ``hvac`` is not installed.
            KeyError: When ``key`` is not present in the secret data.
        """
        client = self._get_client()
        try:
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            data: dict = response["data"]["data"]
            return data[key]
        except Exception as exc:
            logger.error("Failed to read secret {}/{}: {}", path, key, exc)
            raise

    def get_database_credentials(self) -> dict:
        """Return database connection credentials from Vault.

        Reads from the ``vfs-bot/database`` path and returns a dict with keys:
        ``host``, ``port``, ``username``, ``password``, ``database``.

        Returns:
            Dictionary of database connection parameters.

        Raises:
            ImportError: When ``hvac`` is not installed.
        """
        client = self._get_client()
        try:
            response = client.secrets.kv.v2.read_secret_version(
                path="vfs-bot/database",
                mount_point=self.mount_point,
            )
            data: dict = response["data"]["data"]
            return {
                "host": data.get("host", "localhost"),
                "port": int(data.get("port", 5432)),
                "username": data["username"],
                "password": data["password"],
                "database": data.get("database", "vfs_bot"),
            }
        except Exception as exc:
            logger.error("Failed to read database credentials from Vault: {}", exc)
            raise

    def get_all_secrets(self, path: str) -> dict:
        """Return all key-value pairs stored at a given path.

        Args:
            path: Secret path relative to the mount point.

        Returns:
            Dictionary of all secrets at that path.

        Raises:
            ImportError: When ``hvac`` is not installed.
        """
        client = self._get_client()
        try:
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            return dict(response["data"]["data"])
        except Exception as exc:
            logger.error("Failed to read secrets at {}: {}", path, exc)
            raise

    def is_available(self) -> bool:
        """Check whether Vault is reachable and the token is authenticated.

        Returns:
            ``True`` when Vault is reachable and authenticated, ``False`` otherwise
            (including when ``hvac`` is not installed).
        """
        try:
            hvac = self._ensure_hvac()
        except ImportError:
            logger.debug("hvac not installed; Vault is unavailable")
            return False

        try:
            client = hvac.Client(url=self.url, token=self.token)
            result: bool = client.is_authenticated()
            if result:
                logger.debug("Vault is available and authenticated at {}", self.url)
            else:
                logger.warning("Vault at {} is reachable but token is not authenticated", self.url)
            return result
        except Exception as exc:
            logger.debug("Vault is not available at {}: {}", self.url, exc)
            return False
