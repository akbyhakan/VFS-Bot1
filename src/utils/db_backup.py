"""SQLite database backup and restore utilities.

This module provides automated backup functionality for SQLite databases
using the native backup API for online (hot) backups.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """
    Handles automated SQLite database backups with retention management.

    Uses SQLite's backup API for online backups without blocking the database.
    Automatically cleans up old backups based on retention policy.
    """

    def __init__(
        self,
        db_path: str = "data/vfs_bot.db",
        backup_dir: str = "data/backups",
        retention_days: int = 7,
        interval_hours: int = 6,
    ):
        """
        Initialize database backup service.

        Args:
            db_path: Path to SQLite database file
            backup_dir: Directory to store backup files
            retention_days: Number of days to keep backups (default: 7)
            interval_hours: Hours between scheduled backups (default: 6)
        """
        self._db_path = Path(db_path)
        self._backup_dir = Path(backup_dir)
        self._retention_days = retention_days
        self._interval_hours = interval_hours
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Ensure backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Database backup initialized: {db_path} -> {backup_dir} "
            f"(retention: {retention_days}d, interval: {interval_hours}h)"
        )

    def _generate_backup_path(self) -> Path:
        """
        Generate timestamped backup file path.

        Returns:
            Path object for new backup file
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"vfs_bot_backup_{timestamp}.db"
        return self._backup_dir / filename

    async def create_backup(self) -> str:
        """
        Create a backup of the database.

        Uses SQLite's backup API for online backup without locking the database.

        Returns:
            Path to created backup file

        Raises:
            FileNotFoundError: If source database doesn't exist
            Exception: On backup failure
        """
        if not self._db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self._db_path}")

        backup_path = self._generate_backup_path()

        logger.info(f"Creating database backup: {backup_path}")

        try:
            # Run backup in thread pool to avoid blocking asyncio
            await asyncio.to_thread(self._perform_backup, str(self._db_path), str(backup_path))

            # Verify backup was created
            if not backup_path.exists():
                raise Exception("Backup file was not created")

            backup_size = backup_path.stat().st_size
            logger.info(f"Backup created successfully: {backup_path} ({backup_size:,} bytes)")

            return str(backup_path)

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            # Clean up partial backup if it exists
            if backup_path.exists():
                backup_path.unlink()
            raise

    @staticmethod
    def _perform_backup(source_path: str, backup_path: str) -> None:
        """
        Perform SQLite backup using backup API (blocking operation).

        Args:
            source_path: Source database path
            backup_path: Backup destination path
        """
        # Connect to source and destination databases
        source_conn = sqlite3.connect(source_path)
        backup_conn = sqlite3.connect(backup_path)

        try:
            # Perform online backup
            with source_conn:
                source_conn.backup(backup_conn)

            logger.debug("SQLite backup completed")

        finally:
            source_conn.close()
            backup_conn.close()

    async def cleanup_old_backups(self) -> int:
        """
        Remove backups older than retention period.

        Returns:
            Number of backups deleted
        """
        if not self._backup_dir.exists():
            return 0

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        deleted_count = 0

        logger.debug(f"Cleaning up backups older than {self._retention_days} days")

        try:
            for backup_file in self._backup_dir.glob("vfs_bot_backup_*.db"):
                # Get file modification time
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)

                if mtime < cutoff_time:
                    logger.info(f"Deleting old backup: {backup_file} (age: {datetime.now(timezone.utc) - mtime})")
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

        try:
            # Create a backup of current database before restoring
            if self._db_path.exists():
                current_backup = self._db_path.with_suffix(".db.pre-restore")
                logger.info(f"Creating safety backup of current DB: {current_backup}")
                await asyncio.to_thread(self._db_path.rename, current_backup)

            # Copy backup to main database location
            await asyncio.to_thread(self._perform_restore, str(backup_file), str(self._db_path))

            logger.info("Database restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database restore failed: {e}", exc_info=True)
            return False

    @staticmethod
    def _perform_restore(backup_path: str, target_path: str) -> None:
        """
        Perform database restore (blocking operation).

        Args:
            backup_path: Source backup file
            target_path: Target database path
        """
        import shutil

        shutil.copy2(backup_path, target_path)
        logger.debug(f"Copied backup to {target_path}")

    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available backups with metadata.

        Returns:
            List of backup info dictionaries
        """
        backups = []

        if not self._backup_dir.exists():
            return backups

        try:
            for backup_file in sorted(
                self._backup_dir.glob("vfs_bot_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                stat = backup_file.stat()
                backups.append(
                    {
                        "path": str(backup_file),
                        "filename": backup_file.name,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "age_days": (
                            datetime.now(timezone.utc)
                            - datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                        ).days,
                    }
                )

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}", exc_info=True)
            return backups

    def get_stats(self) -> Dict[str, Any]:
        """
        Get backup service statistics.

        Returns:
            Dictionary with statistics
        """
        backups = []
        total_size = 0

        if self._backup_dir.exists():
            for backup_file in self._backup_dir.glob("vfs_bot_backup_*.db"):
                size = backup_file.stat().st_size
                backups.append(backup_file.name)
                total_size += size

        return {
            "db_path": str(self._db_path),
            "backup_dir": str(self._backup_dir),
            "retention_days": self._retention_days,
            "interval_hours": self._interval_hours,
            "scheduled_running": self._running,
            "backup_count": len(backups),
            "total_backup_size_bytes": total_size,
            "latest_backup": backups[0] if backups else None,
        }


# Global singleton instance
_backup_service: Optional[DatabaseBackup] = None


def get_backup_service(
    db_path: str = "data/vfs_bot.db",
    backup_dir: str = "data/backups",
    retention_days: int = 7,
    interval_hours: int = 6,
) -> DatabaseBackup:
    """
    Get or create the global database backup service.

    Args:
        db_path: Database path (only used on first call)
        backup_dir: Backup directory (only used on first call)
        retention_days: Retention period (only used on first call)
        interval_hours: Backup interval (only used on first call)

    Returns:
        DatabaseBackup instance
    """
    global _backup_service

    if _backup_service is None:
        _backup_service = DatabaseBackup(
            db_path=db_path,
            backup_dir=backup_dir,
            retention_days=retention_days,
            interval_hours=interval_hours,
        )

    return _backup_service
