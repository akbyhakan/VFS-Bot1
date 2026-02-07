"""PostgreSQL database backup and restore utilities.

This module provides automated backup functionality for PostgreSQL databases
using pg_dump and pg_restore for online (hot) backups.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """
    Handles automated PostgreSQL database backups with retention management.

    Uses pg_dump for online backups without blocking the database.
    Automatically cleans up old backups based on retention policy.
    """

    def __init__(
        self,
        database_url: str = None,
        backup_dir: str = "data/backups",
        retention_days: int = 7,
        interval_hours: int = 6,
    ):
        """
        Initialize database backup service.

        Args:
            database_url: PostgreSQL database URL
            backup_dir: Directory to store backup files
            retention_days: Number of days to keep backups (default: 7)
            interval_hours: Hours between scheduled backups (default: 6)
        """
        self._database_url = database_url or os.getenv("DATABASE_URL", "postgresql://localhost:5432/vfs_bot")
        self._backup_dir = Path(backup_dir)
        self._retention_days = retention_days
        self._interval_hours = interval_hours
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Ensure backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Database backup initialized: {self._database_url} -> {backup_dir} "
            f"(retention: {retention_days}d, interval: {interval_hours}h)"
        )

    def _generate_backup_path(self) -> Path:
        """
        Generate timestamped backup file path.

        Returns:
            Path object for new backup file
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"vfs_bot_backup_{timestamp}.sql"
        return self._backup_dir / filename

    async def create_backup(self) -> str:
        """
        Create a backup of the database.

        Uses pg_dump for online backup without locking the database.

        Returns:
            Path to created backup file

        Raises:
            Exception: On backup failure
        """
        backup_path = self._generate_backup_path()

        logger.info(f"Creating database backup: {backup_path}")

        try:
            # Run pg_dump asynchronously
            await self._perform_backup(self._database_url, str(backup_path))

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
        cmd = ['pg_dump']
        
        if parsed.hostname:
            cmd.extend(['-h', parsed.hostname])
        if parsed.port:
            cmd.extend(['-p', str(parsed.port)])
        if parsed.username:
            cmd.extend(['-U', parsed.username])
        if parsed.path and len(parsed.path) > 1:
            cmd.extend(['-d', parsed.path[1:]])  # Remove leading /
        
        cmd.extend(['-f', backup_path])
        
        # Set password in environment for security
        if parsed.password:
            env['PGPASSWORD'] = parsed.password
        
        # Run pg_dump
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"pg_dump failed with return code {process.returncode}: {error_msg}")
        
        logger.debug("PostgreSQL backup completed")

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
            for backup_file in self._backup_dir.glob("vfs_bot_backup_*.sql"):
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
            logger.info("Creating safety backup of current DB before restore")
            await self.create_backup()

            # Restore from backup using psql
            await self._perform_restore(str(backup_file), self._database_url)

            logger.info("Database restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database restore failed: {e}", exc_info=True)
            return False

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
        cmd = ['psql']
        
        if parsed.hostname:
            cmd.extend(['-h', parsed.hostname])
        if parsed.port:
            cmd.extend(['-p', str(parsed.port)])
        if parsed.username:
            cmd.extend(['-U', parsed.username])
        if parsed.path and len(parsed.path) > 1:
            cmd.extend(['-d', parsed.path[1:]])  # Remove leading /
        
        cmd.extend(['-f', backup_path])
        
        # Set password in environment for security
        if parsed.password:
            env['PGPASSWORD'] = parsed.password
        
        # Run psql to restore
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"psql restore failed with return code {process.returncode}: {error_msg}")
        
        logger.debug(f"Restored backup to database")

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
                self._backup_dir.glob("vfs_bot_backup_*.sql"), key=lambda p: p.stat().st_mtime, reverse=True
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
            for backup_file in self._backup_dir.glob("vfs_bot_backup_*.sql"):
                size = backup_file.stat().st_size
                backups.append(backup_file.name)
                total_size += size

        return {
            "database_url": self._database_url,
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
    database_url: str = None,
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
