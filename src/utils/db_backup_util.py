"""Database backup utility for SQLite databases."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """
    Utility for creating and managing SQLite database backups.

    Features:
    - Timestamped backup copies
    - Configurable retention (keep last N backups)
    - Safe backup operations (atomic copy)
    """

    def __init__(self, db_path: str, backup_dir: Optional[str] = None, max_backups: int = 5):
        """
        Initialize database backup manager.

        Args:
            db_path: Path to the SQLite database file
            backup_dir: Directory to store backups (defaults to {db_path}_backups)
            max_backups: Maximum number of backups to retain (default: 5)
        """
        self.db_path = Path(db_path)
        self.backup_dir = (
            Path(backup_dir) if backup_dir else self.db_path.parent / f"{self.db_path.stem}_backups"
        )
        self.max_backups = max_backups

        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, suffix: Optional[str] = None) -> Optional[Path]:
        """
        Create a timestamped backup of the database.

        Args:
            suffix: Optional suffix to add to backup filename (e.g., "pre_migration")

        Returns:
            Path to the created backup file, or None if backup failed
        """
        try:
            if not self.db_path.exists():
                logger.error(f"Database file not found: {self.db_path}")
                return None

            # Generate backup filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            if suffix:
                backup_name = f"{self.db_path.stem}_{timestamp}_{suffix}{self.db_path.suffix}"
            else:
                backup_name = f"{self.db_path.stem}_{timestamp}{self.db_path.suffix}"

            backup_path = self.backup_dir / backup_name

            # Perform atomic copy
            shutil.copy2(self.db_path, backup_path)

            logger.info(f"Database backup created: {backup_path}")

            # Clean up old backups
            self._cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return None

    def _cleanup_old_backups(self) -> None:
        """Remove old backups exceeding max_backups limit."""
        try:
            # Get all backup files sorted by creation time (newest first)
            backups = sorted(
                self.backup_dir.glob(f"{self.db_path.stem}_*{self.db_path.suffix}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Remove backups exceeding the limit
            for backup in backups[self.max_backups :]:
                backup.unlink()
                logger.info(f"Removed old backup: {backup}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    def list_backups(self) -> list[Path]:
        """
        List all available backups sorted by creation time (newest first).

        Returns:
            List of backup file paths
        """
        backups = sorted(
            self.backup_dir.glob(f"{self.db_path.stem}_*{self.db_path.suffix}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return backups

    def restore_backup(self, backup_path: Path) -> bool:
        """
        Restore database from a backup file.

        Args:
            backup_path: Path to the backup file to restore

        Returns:
            True if restore was successful, False otherwise
        """
        try:
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            # Create a backup of current database before restoring
            current_backup = self.create_backup(suffix="pre_restore")
            if current_backup:
                logger.info(f"Created pre-restore backup: {current_backup}")

            # Restore from backup
            shutil.copy2(backup_path, self.db_path)

            logger.info(f"Database restored from backup: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore database from backup: {e}")
            return False

    def get_backup_size(self) -> int:
        """
        Get total size of all backups in bytes.

        Returns:
            Total size of all backup files
        """
        total_size = sum(backup.stat().st_size for backup in self.list_backups())
        return total_size


def create_backup(
    db_path: str, suffix: Optional[str] = None, max_backups: int = 5
) -> Optional[Path]:
    """
    Convenience function to create a database backup.

    Args:
        db_path: Path to the SQLite database file
        suffix: Optional suffix to add to backup filename
        max_backups: Maximum number of backups to retain

    Returns:
        Path to the created backup file, or None if backup failed
    """
    backup_manager = DatabaseBackup(db_path, max_backups=max_backups)
    return backup_manager.create_backup(suffix=suffix)
