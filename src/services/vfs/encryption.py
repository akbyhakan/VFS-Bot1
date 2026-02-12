"""VFS API Encryption - Password encryption and environment utilities."""

import base64
import hashlib
import os
import secrets

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from loguru import logger

from ...core.exceptions import ConfigurationError


def _get_required_env(name: str) -> str:
    """Get required environment variable with lazy validation.

    Args:
        name: Environment variable name

    Returns:
        Environment variable value

    Raises:
        ConfigurationError: If environment variable is not set
    """
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(
            f"{name} environment variable must be set. " "Check your .env file configuration."
        )
    return value


def get_vfs_api_base() -> str:
    """Get VFS API base URL (lazy loaded)."""
    return _get_required_env("VFS_API_BASE")


def get_vfs_assets_base() -> str:
    """Get VFS Assets base URL (lazy loaded)."""
    return _get_required_env("VFS_ASSETS_BASE")


def get_contentful_base() -> str:
    """Get Contentful base URL (lazy loaded)."""
    return _get_required_env("CONTENTFUL_BASE")


class VFSPasswordEncryption:
    """VFS Global password encryption (AES-256-CBC)."""

    @classmethod
    def _get_encryption_key(cls) -> bytes:
        """
        Get encryption key from environment variable.

        Returns:
            Encryption key as bytes

        Raises:
            ConfigurationError: If VFS_ENCRYPTION_KEY is not set or invalid
        """
        from ...utils.secure_memory import SecureKeyContext

        key_str = os.getenv("VFS_ENCRYPTION_KEY")
        if not key_str:
            raise ConfigurationError(
                "VFS_ENCRYPTION_KEY environment variable must be set. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        with SecureKeyContext(key_str) as key_buf:
            if len(key_buf) < 32:
                raise ConfigurationError(
                    f"VFS_ENCRYPTION_KEY must be at least 32 bytes (current: {len(key_buf)}). "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            if len(key_buf) > 32:
                logger.warning(
                    f"VFS_ENCRYPTION_KEY is {len(key_buf)} bytes, "
                    f"deriving 32-byte key using SHA-256 for consistency"
                )
                derived = hashlib.sha256(bytes(key_buf)).digest()
                return derived

            return bytes(key_buf[:32])
        # key_buf is securely zeroed here by SecureKeyContext.__exit__

    @classmethod
    def encrypt(cls, password: str) -> str:
        """
        Encrypt password for VFS API.

        Args:
            password: Plain text password

        Returns:
            Base64 encoded encrypted password
        """
        encryption_key = cls._get_encryption_key()
        iv = secrets.token_bytes(16)
        cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
        padded_data = pad(password.encode("utf-8"), AES.block_size)
        encrypted = cipher.encrypt(padded_data)

        # VFS expects IV + encrypted data, base64 encoded
        return base64.b64encode(iv + encrypted).decode("utf-8")
