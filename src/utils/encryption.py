"""Password encryption utilities using Fernet symmetric encryption."""

import os
import logging
import threading
import asyncio
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Support for key rotation
ENCRYPTION_KEY_OLD = os.getenv("ENCRYPTION_KEY_OLD")  # For key rotation


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
            # Generate key hash for identification
            self._key_hash = hashlib.sha256(self._key.encode()).hexdigest()[:16]
            # Create cipher with normalized key
            cipher_key = key.encode() if isinstance(key, str) else key
            self.cipher = Fernet(cipher_key)

            # Only log key hash in non-production environments
            env = os.getenv("ENV", "production").lower()
            if env != "production":
                logger.debug(f"Password encryption initialized (key hash: {self._key_hash})")
            else:
                logger.info("Password encryption initialized successfully")
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY: {e}") from e

    @property
    def key_hash(self) -> str:
        """Return truncated hash of current key for identification."""
        return self._key_hash

    def can_decrypt(self, encrypted_data: str) -> bool:
        """
        Check if current key can decrypt the given data.

        Args:
            encrypted_data: Encrypted data to test

        Returns:
            True if data can be decrypted with current key
        """
        try:
            self.cipher.decrypt(encrypted_data.encode())
            return True
        except InvalidToken:
            return False
        except Exception:
            return False

    @staticmethod
    def migrate_data(old_key: str, new_key: str, encrypted_data: str) -> str:
        """
        Re-encrypt data with a new key.

        Args:
            old_key: Old encryption key (base64 encoded)
            new_key: New encryption key (base64 encoded)
            encrypted_data: Data encrypted with old key

        Returns:
            Data encrypted with new key

        Raises:
            ValueError: If decryption with old key or encryption with new key fails
        """
        try:
            # Create ciphers with both keys
            old_cipher = Fernet(old_key.encode() if isinstance(old_key, str) else old_key)
            new_cipher = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)

            # Decrypt with old key
            decrypted = old_cipher.decrypt(encrypted_data.encode())

            # Encrypt with new key
            return new_cipher.encrypt(decrypted).decode()
        except Exception as e:
            logger.error(f"Failed to migrate encryption data: {e}")
            raise ValueError(f"Encryption migration failed: {e}") from e

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
        Decrypt an encrypted password with key rotation support.

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
        except InvalidToken:
            # Try old key if available (key rotation support)
            if ENCRYPTION_KEY_OLD:
                logger.info("Trying old encryption key for backward compatibility")
                try:
                    old_cipher = Fernet(
                        ENCRYPTION_KEY_OLD.encode()
                        if isinstance(ENCRYPTION_KEY_OLD, str)
                        else ENCRYPTION_KEY_OLD
                    )
                    decrypted = old_cipher.decrypt(encrypted_password.encode())
                    return decrypted.decode()
                except InvalidToken:
                    logger.error("Failed to decrypt with both current and old encryption keys")
                    raise ValueError("Invalid encryption key or corrupted password")
            else:
                logger.error("Failed to decrypt password: invalid token or key")
                raise ValueError("Invalid encryption key or corrupted password")
        except Exception as e:
            logger.error(f"Failed to decrypt password: {e}")
            raise


# Global instance
_encryption_instance: Optional[PasswordEncryption] = None
_encryption_lock = threading.Lock()
_encryption_lock_async = asyncio.Lock()


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

    Always uses lock to prevent race conditions during key changes.
    Recreates instance if encryption key changes.

    Returns:
        PasswordEncryption instance
    """
    global _encryption_instance

    # Always acquire lock to prevent race conditions
    with _encryption_lock:
        current_key = os.getenv("ENCRYPTION_KEY")
        if _encryption_instance is None or (
            current_key and _normalize_key(current_key) != _encryption_instance._key
        ):
            _encryption_instance = PasswordEncryption()
        return _encryption_instance


async def get_encryption_async() -> PasswordEncryption:
    """
    Get global encryption instance (singleton) - async-safe.

    Always uses async lock to prevent race conditions during key changes.
    Recreates instance if encryption key changes.

    Returns:
        PasswordEncryption instance
    """
    global _encryption_instance

    # Always acquire async lock to prevent race conditions
    async with _encryption_lock_async:
        current_key = os.getenv("ENCRYPTION_KEY")
        if _encryption_instance is None or (
            current_key and _normalize_key(current_key) != _encryption_instance._key
        ):
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
