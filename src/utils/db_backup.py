"""PostgreSQL database backup and restore utilities.

This module provides automated backup functionality for PostgreSQL databases
using pg_dump and pg_restore for online (hot) backups.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from cryptography.fernet import Fernet, MultiFernet
from loguru import logger

from src.utils.masking import mask_database_url


class DatabaseBackup:
    """
    Handles automated PostgreSQL database backups with retention management.

    Uses pg_dump for online backups without blocking the database.
    Automatically cleans up old backups based on retention policy.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        backup_dir: str = "data/backups",
        retention_days: int = 7,
        interval_hours: int = 6,
        max_backups: Optional[int] = None,
    ):
        """
        Initialize database backup service.

        Args:
            database_url: PostgreSQL database URL
            backup_dir: Directory to store backup files
            retention_days: Number of days to keep backups (default: 7)
            interval_hours: Hours between scheduled backups (default: 6)
            max_backups: Maximum number of backups to retain (if set, overrides retention_days)
        """
        self._database_url: str = database_url or os.getenv(
            "DATABASE_URL") or "postgresql://localhost:5432/vfs_bot"
        self._backup_dir = Path(backup_dir)
        self._retention_days = retention_days
        self._interval_hours = interval_hours
        self._max_backups = max_backups
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Ensure backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        retention_info = f"{max_backups} backups" if max_backups else f"{retention_days}d"
        logger.info(
            f"Database backup initialized: {mask_database_url(self._database_url)} -> {backup_dir} "
            f"(retention: {retention_info}, interval: {interval_hours}h)"
        )

    def _get_encryption_key(self) -> bytes:
        """
        Get encryption key for backups.

        Reads from BACKUP_ENCRYPTION_KEY env var first, falls back to ENCRYPTION_KEY.
        Also checks for old keys to support key rotation.

        Returns:
            Fernet encryption key as bytes

        Raises:
            ValueError: If no encryption key is available
        """
        key = os.getenv("BACKUP_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")
        if not key:
            raise ValueError(
                "Backup encryption requires BACKUP_ENCRYPTION_KEY or "
                "ENCRYPTION_KEY environment variable. "
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
            with open(plain_path, "rb") as f:
                plain_data = f.read()

            # Encrypt
            encrypted_data = cipher.encrypt(plain_data)

            # Write encrypted file
            with open(encrypted_path, "wb") as f:
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
        Decrypt a file using Fernet encryption with key rotation support.

        Args:
            encrypted_path: Path to encrypted file
            plain_path: Path to decrypted output file

        Raises:
            Exception: If decryption fails
        """
        try:
            # Build key list for MultiFernet (new key first, then old key if available)
            key = self._get_encryption_key()
            fernet_keys = [Fernet(key)]

            # Check for old backup encryption key
            old_key = os.getenv("BACKUP_ENCRYPTION_KEY_OLD") or os.getenv("ENCRYPTION_KEY_OLD")
            if old_key:
                try:
                    old_key_bytes = old_key.encode() if isinstance(old_key, str) else old_key
                    fernet_keys.append(Fernet(old_key_bytes))
                    logger.debug("Old backup encryption key loaded for decryption")
                except Exception as e:
                    logger.warning(f"Failed to load old backup encryption key: {e}")

            cipher = MultiFernet(fernet_keys)

            # Read encrypted file
            with open(encrypted_path, "rb") as f:
                encrypted_data = f.read()

            # Decrypt (MultiFernet tries all keys automatically)
            plain_data = cipher.decrypt(encrypted_data)

            # Write plain file
            with open(plain_path, "wb") as f:
                f.write(plain_data)

        except Exception as e:
            logger.error(f"File decryption failed: {e}", exc_info=True)
            raise

    def _generate_backup_path(self, suffix: Optional[str] = None) -> Path:
        """
        Generate timestamped backup file path.

        Args:
            suffix: Optional suffix to add to filename (e.g., "pre_migration")

        Returns:
            Path object for new backup file
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if suffix:
            filename = f"vfs_bot_backup_{timestamp}_{suffix}.sql.enc"
        else:
            filename = f"vfs_bot_backup_{timestamp}.sql.enc"
        return self._backup_dir / filename

    async def create_backup(self, suffix: Optional[str] = None) -> str:
        """
        Create a backup of the database.

        Uses pg_dump for online backup without locking the database.
        Encrypts the backup file using Fernet encryption.

        Args:
            suffix: Optional suffix to add to backup filename (e.g., "pre_migration")

        Returns:
            Path to created backup file

        Raises:
            Exception: On backup failure
        """
        backup_path = self._generate_backup_path(suffix=suffix)
        temp_sql_path = backup_path.with_suffix(".sql")  # Temporary unencrypted file

        logger.info(f"Creating database backup: {backup_path}")

        try:
            # Run pg_dump to temporary SQL file
            await self._perform_backup(self._database_url, str(temp_sql_path))

            # Verify temp backup was created
            if not temp_sql_path.exists():
                raise Exception("Backup file was not created")

            # Encrypt the backup file
            self._encrypt_file(temp_sql_path, backup_path)

            # Securely delete the temporary plain SQL file
            temp_sql_path.unlink()

            backup_size = backup_path.stat().st_size
            logger.info(
                f"Backup created and encrypted successfully: {backup_path} ({backup_size:,} bytes)"
            )

            return str(backup_path)

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            # Clean up partial files if they exist
            if temp_sql_path.exists():
                temp_sql_path.unlink()
            if backup_path.exists():
                backup_path.unlink()
            raise

    async def _perform_backup(self, database_url: str, backup_path: str) -> None:
        """
        Perform PostgreSQL backup using pg_dump (async operation).

        Args:
            database_url: PostgreSQL database URL
            backup_path: Backup destination path
        """
        # Set up environment with password if present
        env = os.environ.copy()

        # Parse database URL to extract connection parameters
        parsed = urlparse(database_url)

        # Build pg_dump command with separate parameters for security
        cmd = ["pg_dump"]

        if parsed.hostname:
            cmd.extend(["-h", parsed.hostname])
        if parsed.port:
            cmd.extend(["-p", str(parsed.port)])
        if parsed.username:
            cmd.extend(["-U", parsed.username])
        if parsed.path and len(parsed.path) > 1:
            cmd.extend(["-d", parsed.path[1:]])  # Remove leading /

        cmd.extend(["-f", backup_path])

        # Set password in environment for security
        if parsed.password:
            env["PGPASSWORD"] = parsed.password

        # Run pg_dump
        process = await asyncio.create_subprocess_exec(
            *cmd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"pg_dump failed with return code {process.returncode}: {error_msg}")

        logger.debug("PostgreSQL backup completed")

    async def cleanup_old_backups(self) -> int:
        """
        Remove backups based on retention policy.

        If max_backups is set, keeps only the N most recent backups.
        Otherwise, removes backups older than retention_days.

        Handles both encrypted (.sql.enc) and legacy unencrypted (.sql) backups.

        Returns:
            Number of backups deleted
        """
        if not self._backup_dir.exists():
            return 0

        deleted_count = 0

        try:
            # Collect both encrypted and legacy backups
            all_backups: list[Path] = []
            for pattern in ["vfs_bot_backup_*.sql.enc", "vfs_bot_backup_*.sql"]:
                all_backups.extend(self._backup_dir.glob(pattern))

            if self._max_backups is not None:
                # Count-based cleanup: keep only N most recent backups
                logger.debug(f"Cleaning up backups exceeding limit of {self._max_backups}")

                # Sort by modification time (newest first)
                backups_sorted = sorted(all_backups, key=lambda p: p.stat().st_mtime, reverse=True)

                # Remove backups exceeding the limit
                for backup_file in backups_sorted[self._max_backups :]:
                    logger.info(f"Deleting old backup (count limit): {backup_file}")
                    backup_file.unlink()
                    deleted_count += 1
            else:
                # Time-based cleanup: remove backups older than retention_days
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
                logger.debug(f"Cleaning up backups older than {self._retention_days} days")

                for backup_file in all_backups:
                    # Get file modification time
                    mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)

                    if mtime < cutoff_time:
                        logger.info(
                            f"Deleting old backup: {backup_file} "
                            f"(age: {datetime.now(timezone.utc) - mtime})"
                        )
                        backup_file.unlink()
                        deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backup(s)")

            return deleted_count

        except Exception as e:
            logger.error(f"Error during backup cleanup: {e}", exc_info=True)
            return deleted_count

    async def start_scheduled_backups(self) -> None:
        """Start periodic backup loop."""
        if self._running:
            logger.warning("Scheduled backups already running")
            return

        self._running = True
        logger.info(f"Started scheduled backups (interval: {self._interval_hours}h)")

        # Start background task
        self._task = asyncio.create_task(self._backup_loop())

    async def stop_scheduled_backups(self) -> None:
        """Stop periodic backup loop."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Scheduled backups stopped")

    async def _backup_loop(self) -> None:
        """Main backup loop."""
        while self._running:
            try:
                # Perform backup
                backup_path = await self.create_backup()
                logger.info(f"Scheduled backup completed: {backup_path}")

                # Clean up old backups
                deleted = await self.cleanup_old_backups()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old backup(s)")

                # Wait for next backup
                await asyncio.sleep(self._interval_hours * 3600)

            except asyncio.CancelledError:
                logger.debug("Backup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in backup loop: {e}", exc_info=True)
                # Wait a bit before retrying
                await asyncio.sleep(300)  # 5 minutes

    async def restore_from_backup(self, backup_path: str) -> bool:
        """
        Restore database from backup file.

        Supports both encrypted (.sql.enc) and legacy unencrypted (.sql) backups.

        Args:
            backup_path: Path to backup file

        Returns:
            True if restore was successful

        Raises:
            FileNotFoundError: If backup file doesn't exist
        """
        backup_file = Path(backup_path)

        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        logger.warning(f"Restoring database from backup: {backup_path}")

        temp_sql_file = None
        temp_sql_path = None
        try:
            # Create a backup of current database before restoring
            logger.info("Creating safety backup of current DB before restore")
            await self.create_backup()

            # Check if this is an encrypted backup
            is_encrypted = backup_file.suffix == ".enc"

            if is_encrypted:
                # Decrypt to temporary file (use NamedTemporaryFile for security)
                temp_sql_file = tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".sql", dir=self._backup_dir, delete=False
                )
                temp_sql_path = Path(temp_sql_file.name)
                temp_sql_file.close()  # Close so decrypt can write to it

                self._decrypt_file(backup_file, temp_sql_path)
                restore_path = str(temp_sql_path)
            else:
                # Use unencrypted backup directly
                restore_path = str(backup_file)

            # Restore from backup using psql
            await self._perform_restore(restore_path, self._database_url)

            logger.info("Database restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database restore failed: {e}", exc_info=True)
            return False
        finally:
            # Clean up temporary decrypted file
            if temp_sql_path and temp_sql_path.exists():
                temp_sql_path.unlink()
                logger.debug(f"Cleaned up temporary restore file: {temp_sql_path}")

    async def _perform_restore(self, backup_path: str, database_url: str) -> None:
        """
        Perform database restore using psql (async operation).

        Args:
            backup_path: Source backup file
            database_url: Target database URL
        """
        # Set up environment with password if present
        env = os.environ.copy()

        # Parse database URL to extract connection parameters
        parsed = urlparse(database_url)

        # Build psql command with separate parameters for security
        cmd = ["psql"]

        if parsed.hostname:
            cmd.extend(["-h", parsed.hostname])
        if parsed.port:
            cmd.extend(["-p", str(parsed.port)])
        if parsed.username:
            cmd.extend(["-U", parsed.username])
        if parsed.path and len(parsed.path) > 1:
            cmd.extend(["-d", parsed.path[1:]])  # Remove leading /

        cmd.extend(["-f", backup_path])

        # Set password in environment for security
        if parsed.password:
            env["PGPASSWORD"] = parsed.password

        # Run psql to restore
        process = await asyncio.create_subprocess_exec(
            *cmd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(
                f"psql restore failed with return code {process.returncode}: {error_msg}"
            )

        logger.debug("Restored backup to database")

    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available backups with metadata.

        Supports both encrypted (.sql.enc) and legacy unencrypted (.sql) backups.

        Returns:
            List of backup info dictionaries
        """
        backups: list[dict[str, Any]] = []

        if not self._backup_dir.exists():
            return backups

        try:
            # Collect both encrypted and legacy backups
            all_backups: list[Path] = []
            for pattern in ["vfs_bot_backup_*.sql.enc", "vfs_bot_backup_*.sql"]:
                all_backups.extend(self._backup_dir.glob(pattern))

            # Sort by modification time (newest first)
            for backup_file in sorted(all_backups, key=lambda p: p.stat().st_mtime, reverse=True):
                stat = backup_file.stat()
                is_encrypted = backup_file.suffix == ".enc"

                backups.append(
                    {
                        "path": str(backup_file),
                        "filename": backup_file.name,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "age_days": (
                            datetime.now(timezone.utc)
                            - datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                        ).days,
                        "encrypted": is_encrypted,
                    }
                )

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}", exc_info=True)
            return backups

    def get_backup_size(self) -> int:
        """
        Get total size of all backups in bytes.

        Returns:
            Total size of all backup files
        """
        total_size = 0

        if self._backup_dir.exists():
            # Collect both encrypted and legacy backups
            for pattern in ["vfs_bot_backup_*.sql.enc", "vfs_bot_backup_*.sql"]:
                for backup_file in self._backup_dir.glob(pattern):
                    total_size += backup_file.stat().st_size

        return total_size

    def get_stats(self) -> Dict[str, Any]:
        """
        Get backup service statistics.

        Returns:
            Dictionary with statistics
        """
        backups = []
        total_size = 0

        if self._backup_dir.exists():
            # Collect both encrypted and legacy backups
            for pattern in ["vfs_bot_backup_*.sql.enc", "vfs_bot_backup_*.sql"]:
                for backup_file in self._backup_dir.glob(pattern):
                    size = backup_file.stat().st_size
                    backups.append(backup_file.name)
                    total_size += size

        return {
            "database_url": mask_database_url(self._database_url),
            "backup_dir": str(self._backup_dir),
            "retention_days": self._retention_days,
            "interval_hours": self._interval_hours,
            "scheduled_running": self._running,
            "backup_count": len(backups),
            "total_backup_size_bytes": total_size,
            "latest_backup": backups[0] if backups else None,
            "encryption_enabled": True,
        }


# Global singleton instance
_backup_service: Optional[DatabaseBackup] = None


def get_backup_service(
    database_url: Optional[str] = None,
    backup_dir: str = "data/backups",
    retention_days: int = 7,
    interval_hours: int = 6,
) -> DatabaseBackup:
    """
    Get or create the global database backup service.

    Args:
        database_url: Database URL (only used on first call)
        backup_dir: Backup directory (only used on first call)
        retention_days: Retention period (only used on first call)
        interval_hours: Backup interval (only used on first call)

    Returns:
        DatabaseBackup instance
    """
    global _backup_service

    if _backup_service is None:
        _backup_service = DatabaseBackup(
            database_url=database_url,
            backup_dir=backup_dir,
            retention_days=retention_days,
            interval_hours=interval_hours,
        )

    return _backup_service
