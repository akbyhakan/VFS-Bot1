"""Password encryption utilities using Fernet symmetric encryption."""

import os
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class PasswordEncryption:
    """Handles password encryption and decryption using Fernet."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption with key.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, reads from env.

        Raises:
            ValueError: If encryption key is not provided or invalid
        """
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY must be set in environment variables. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )

        try:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
            logger.info("Password encryption initialized successfully")
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY: {e}") from e

    def encrypt_password(self, password: str) -> str:
        """
        Encrypt a password.

        Args:
            password: Plain text password

        Returns:
            Encrypted password (base64 encoded)
        """
        try:
            encrypted = self.cipher.encrypt(password.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt password: {e}")
            raise

    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Decrypt an encrypted password.

        Args:
            encrypted_password: Encrypted password (base64 encoded)

        Returns:
            Decrypted plain text password

        Raises:
            ValueError: If decryption fails
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_password.encode())
            return decrypted.decode()
        except InvalidToken as e:
            logger.error("Failed to decrypt password: invalid token or key")
            raise ValueError("Invalid encryption key or corrupted password") from e
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            raise


# Global instance
_encryption_instance: Optional[PasswordEncryption] = None


def get_encryption() -> PasswordEncryption:
    """
    Get global encryption instance (singleton).

    Returns:
        PasswordEncryption instance
    """
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = PasswordEncryption()
    return _encryption_instance


def encrypt_password(password: str) -> str:
    """
    Encrypt a password using global instance.

    Args:
        password: Plain text password

    Returns:
        Encrypted password
    """
    return get_encryption().encrypt_password(password)


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt a password using global instance.

    Args:
        encrypted_password: Encrypted password

    Returns:
        Decrypted password
    """
    return get_encryption().decrypt_password(encrypted_password)
