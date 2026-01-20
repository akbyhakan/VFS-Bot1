"""Password encryption utilities using Fernet symmetric encryption."""

import os
import logging
import threading
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _normalize_key(key: Optional[str | bytes]) -> str:
    """
    Normalize encryption key to string format.

    Args:
        key: Encryption key as string or bytes

    Returns:
        Key as string
    """
    if isinstance(key, bytes):
        return key.decode()
    elif isinstance(key, str):
        return key
    else:
        raise ValueError("Encryption key must be string or bytes")


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
            # Normalize and store key for comparison
            self._key = _normalize_key(key)
            # Create cipher with normalized key
            cipher_key = key.encode() if isinstance(key, str) else key
            self.cipher = Fernet(cipher_key)
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
_encryption_lock = threading.Lock()


def reset_encryption() -> None:
    """
    Reset the global encryption instance.
    Thread-safe implementation.
    """
    global _encryption_instance
    with _encryption_lock:
        _encryption_instance = None
        logger.info("Encryption instance reset")


def get_encryption() -> PasswordEncryption:
    """
    Get global encryption instance (singleton) - thread-safe.

    Uses double-checked locking pattern for efficiency.
    Recreates instance if encryption key changes.

    Returns:
        PasswordEncryption instance
    """
    global _encryption_instance

    current_key = os.getenv("ENCRYPTION_KEY")

    # First check without lock (fast path)
    if _encryption_instance is not None and current_key is not None:
        # Check if key matches - if so, return existing instance
        if _normalize_key(current_key) == _encryption_instance._key:
            return _encryption_instance

    # Acquire lock for initialization or key change
    with _encryption_lock:
        # Double-check after acquiring lock (complete double-checked locking pattern)
        if _encryption_instance is None:
            # Create new instance
            _encryption_instance = PasswordEncryption()
        elif current_key is not None and _normalize_key(current_key) != _encryption_instance._key:
            # Key changed - create new instance with proper cleanup
            logger.warning("Encryption key changed, reinitializing...")
            # Old instance will be garbage collected
            _encryption_instance = PasswordEncryption()
        elif _encryption_instance is not None and current_key is not None:
            # Instance exists and key matches - return it
            if _normalize_key(current_key) == _encryption_instance._key:
                return _encryption_instance

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
