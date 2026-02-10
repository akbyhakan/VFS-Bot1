"""Database backup utility for PostgreSQL databases."""

import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from loguru import logger


class DatabaseBackup:
    """
    Utility for creating and managing PostgreSQL database backups.

    Features:
    - Timestamped backup copies using pg_dump
    - Configurable retention (keep last N backups)
    - Safe backup operations (pg_dump)
    """

    def __init__(self, database_url: str = None, backup_dir: Optional[str] = None, max_backups: int = 5):
        """
        Initialize database backup manager.

        Args:
            database_url: PostgreSQL database URL
            backup_dir: Directory to store backups (defaults to data/backups)
            max_backups: Maximum number of backups to retain (default: 5)
        """
        self.database_url = database_url or os.getenv("DATABASE_URL", "postgresql://localhost:5432/vfs_bot")
        self.backup_dir = Path(backup_dir) if backup_dir else Path("data/backups")
        self.max_backups = max_backups

        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_encryption_key(self) -> bytes:
        """
        Get encryption key for backups.
        
        Reads from BACKUP_ENCRYPTION_KEY env var first, falls back to ENCRYPTION_KEY.
        
        Returns:
            Fernet encryption key as bytes
            
        Raises:
            ValueError: If no encryption key is available
        """
        key = os.getenv("BACKUP_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "Backup encryption requires BACKUP_ENCRYPTION_KEY or ENCRYPTION_KEY environment variable. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        return key.encode() if isinstance(key, str) else key
    
    def _encrypt_file(self, plain_path: Path, encrypted_path: Path) -> None:
        """
        Encrypt a file using Fernet encryption.
        
        Args:
            plain_path: Path to plain text file
            encrypted_path: Path to encrypted output file
            
        Raises:
            Exception: If encryption fails
        """
        try:
            key = self._get_encryption_key()
            cipher = Fernet(key)
            
            # Read plain file
            with open(plain_path, 'rb') as f:
                plain_data = f.read()
            
            # Encrypt
            encrypted_data = cipher.encrypt(plain_data)
            
            # Write encrypted file
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions (Unix only)
            try:
                os.chmod(encrypted_path, 0o600)
            except (OSError, AttributeError):
                pass  # Skip on Windows or if chmod fails
                
        except Exception as e:
            logger.error(f"File encryption failed: {e}", exc_info=True)
            raise
    
    def _decrypt_file(self, encrypted_path: Path, plain_path: Path) -> None:
        """
        Decrypt a file using Fernet encryption.
        
        Args:
            encrypted_path: Path to encrypted file
            plain_path: Path to decrypted output file
            
        Raises:
            Exception: If decryption fails
        """
        try:
            key = self._get_encryption_key()
            cipher = Fernet(key)
            
            # Read encrypted file
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt
            plain_data = cipher.decrypt(encrypted_data)
            
            # Write plain file
            with open(plain_path, 'wb') as f:
                f.write(plain_data)
                
        except Exception as e:
            logger.error(f"File decryption failed: {e}", exc_info=True)
            raise

    def create_backup(self, suffix: Optional[str] = None) -> Optional[Path]:
        """
        Create a timestamped backup of the database using pg_dump.
        
        Encrypts the backup file using Fernet encryption.

        Args:
            suffix: Optional suffix to add to backup filename (e.g., "pre_migration")

        Returns:
            Path to the created backup file, or None if backup failed
        """
        try:
            # Generate backup filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            if suffix:
                backup_name = f"vfs_bot_{timestamp}_{suffix}.sql.enc"
                temp_sql_name = f"vfs_bot_{timestamp}_{suffix}.sql"
            else:
                backup_name = f"vfs_bot_{timestamp}.sql.enc"
                temp_sql_name = f"vfs_bot_{timestamp}.sql"

            backup_path = self.backup_dir / backup_name
            temp_sql_path = self.backup_dir / temp_sql_name

            # Set up environment with password if present
            env = os.environ.copy()
            parsed = urlparse(self.database_url)
            
            # Build pg_dump command with separate parameters for security
            cmd = ['pg_dump']
            
            if parsed.hostname:
                cmd.extend(['-h', parsed.hostname])
            if parsed.port:
                cmd.extend(['-p', str(parsed.port)])
            if parsed.username:
                cmd.extend(['-U', parsed.username])
            if parsed.path and len(parsed.path) > 1:
                cmd.extend(['-d', parsed.path[1:]])  # Remove leading /
            
            cmd.extend(['-f', str(temp_sql_path)])
            
            # Set password in environment for security
            if parsed.password:
                env['PGPASSWORD'] = parsed.password

            # Perform backup using pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr}")
                return None

            # Encrypt the backup file
            self._encrypt_file(temp_sql_path, backup_path)
            
            # Securely delete the temporary plain SQL file
            temp_sql_path.unlink()

            logger.info(f"Database backup created and encrypted: {backup_path}")

            # Clean up old backups
            self._cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            # Clean up partial files
            if temp_sql_path.exists():
                temp_sql_path.unlink()
            if backup_path.exists():
                backup_path.unlink()
            return None

    def _cleanup_old_backups(self) -> None:
        """
        Remove old backups exceeding max_backups limit.
        
        Handles both encrypted (.sql.enc) and legacy unencrypted (.sql) backups.
        """
        try:
            # Get all backup files (both encrypted and legacy) sorted by creation time (newest first)
            backups = []
            for pattern in ["vfs_bot_*.sql.enc", "vfs_bot_*.sql"]:
                backups.extend(self.backup_dir.glob(pattern))
            
            backups = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)

            # Remove backups exceeding the limit
            for backup in backups[self.max_backups :]:
                backup.unlink()
                logger.info(f"Removed old backup: {backup}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    def list_backups(self) -> list[Path]:
        """
        List all available backups sorted by creation time (newest first).
        
        Includes both encrypted (.sql.enc) and legacy unencrypted (.sql) backups.

        Returns:
            List of backup file paths
        """
        # Collect both encrypted and legacy backups
        backups = []
        for pattern in ["vfs_bot_*.sql.enc", "vfs_bot_*.sql"]:
            backups.extend(self.backup_dir.glob(pattern))
        
        # Sort by creation time (newest first)
        backups = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)
        return backups

    def restore_backup(self, backup_path: Path) -> bool:
        """
        Restore database from a backup file using psql.
        
        Supports both encrypted (.sql.enc) and legacy unencrypted (.sql) backups.

        Args:
            backup_path: Path to the backup file to restore

        Returns:
            True if restore was successful, False otherwise
        """
        temp_sql_file = None
        temp_sql_path = None
        try:
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            # Create a backup of current database before restoring
            current_backup = self.create_backup(suffix="pre_restore")
            if current_backup:
                logger.info(f"Created pre-restore backup: {current_backup}")

            # Check if this is an encrypted backup
            is_encrypted = backup_path.suffix == '.enc'
            
            if is_encrypted:
                # Decrypt to temporary file (use NamedTemporaryFile for security)
                temp_sql_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix='.sql', dir=self.backup_dir, delete=False
                )
                temp_sql_path = Path(temp_sql_file.name)
                temp_sql_file.close()  # Close so decrypt can write to it
                
                self._decrypt_file(backup_path, temp_sql_path)
                restore_path = temp_sql_path
            else:
                # Use unencrypted backup directly
                restore_path = backup_path

            # Set up environment with password if present
            env = os.environ.copy()
            parsed = urlparse(self.database_url)
            
            # Build psql command with separate parameters for security
            cmd = ['psql']
            
            if parsed.hostname:
                cmd.extend(['-h', parsed.hostname])
            if parsed.port:
                cmd.extend(['-p', str(parsed.port)])
            if parsed.username:
                cmd.extend(['-U', parsed.username])
            if parsed.path and len(parsed.path) > 1:
                cmd.extend(['-d', parsed.path[1:]])  # Remove leading /
            
            cmd.extend(['-f', str(restore_path)])
            
            # Set password in environment for security
            if parsed.password:
                env['PGPASSWORD'] = parsed.password

            # Restore from backup using psql
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"psql restore failed: {result.stderr}")
                return False

            logger.info(f"Database restored from backup: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore database from backup: {e}")
            return False
        finally:
            # Clean up temporary decrypted file
            if temp_sql_path and temp_sql_path.exists():
                temp_sql_path.unlink()
                logger.debug(f"Cleaned up temporary restore file: {temp_sql_path}")

    def get_backup_size(self) -> int:
        """
        Get total size of all backups in bytes.

        Returns:
            Total size of all backup files
        """
        total_size = sum(backup.stat().st_size for backup in self.list_backups())
        return total_size


def create_backup(
    database_url: str = None, suffix: Optional[str] = None, max_backups: int = 5
) -> Optional[Path]:
    """
    Convenience function to create a database backup.

    Args:
        database_url: PostgreSQL database URL
        suffix: Optional suffix to add to backup filename
        max_backups: Maximum number of backups to retain

    Returns:
        Path to the created backup file, or None if backup failed
    """
    backup_manager = DatabaseBackup(database_url, max_backups=max_backups)
    return backup_manager.create_backup(suffix=suffix)
