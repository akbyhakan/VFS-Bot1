"""Tests for database backup service."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.db_backup import DatabaseBackup, get_backup_service


@pytest.mark.asyncio
class TestDatabaseBackup:
    """Test cases for DatabaseBackup class."""

    async def test_initialization(self):
        """Test service initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir),
                retention_days=5,
                interval_hours=3,
            )

            assert service._database_url == "postgresql://user:pass@localhost:5432/testdb"
            assert service._backup_dir == backup_dir
            assert service._retention_days == 5
            assert service._interval_hours == 3
            assert backup_dir.exists()  # Should be created

    @patch("asyncio.create_subprocess_exec")
    async def test_create_backup(self, mock_subprocess):
        """Test creating a backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            # Create a side effect that creates the file when pg_dump is called
            def create_backup_file(*args, **kwargs):
                # The command is unpacked, so args is like ('pg_dump', '-h', 'localhost', ...)
                if "-f" in args:
                    f_index = args.index("-f")
                    if f_index + 1 < len(args):
                        backup_path = args[f_index + 1]
                        Path(backup_path).touch()
                
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_process.returncode = 0
                return mock_process

            mock_subprocess.side_effect = create_backup_file

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir)
            )

            # Create backup
            backup_path = await service.create_backup()

            # Verify subprocess was called with correct command
            assert mock_subprocess.called
            call_args = mock_subprocess.call_args
            # args are after unpacking
            cmd_args = call_args[0]
            
            # Should contain pg_dump and appropriate flags
            assert "pg_dump" in cmd_args
            assert "-h" in cmd_args and "localhost" in cmd_args
            assert "-p" in cmd_args and "5432" in cmd_args
            assert "-U" in cmd_args and "user" in cmd_args
            assert "-d" in cmd_args and "testdb" in cmd_args
            assert "-f" in cmd_args
            
            assert Path(backup_path).exists()
            assert "vfs_bot_backup_" in backup_path
            assert backup_path.endswith(".sql")

    @patch("asyncio.create_subprocess_exec")
    async def test_backup_command_structure(self, mock_subprocess):
        """Test that backup generates the correct pg_dump command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            # Mock successful pg_dump process
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            service = DatabaseBackup(
                database_url="postgresql://testuser:testpass@testhost:5433/testdb",
                backup_dir=str(backup_dir)
            )

            # Create backup
            try:
                await service.create_backup()
            except Exception:
                pass  # File won't exist, but we only care about the command

            # Verify the command structure
            assert mock_subprocess.called
            call_args = mock_subprocess.call_args
            cmd_args = call_args[0]
            
            assert cmd_args[0] == "pg_dump"
            # Verify connection parameters
            assert "-h" in cmd_args
            assert "testhost" in cmd_args
            assert "-p" in cmd_args
            assert "5433" in cmd_args
            assert "-U" in cmd_args
            assert "testuser" in cmd_args
            assert "-d" in cmd_args
            assert "testdb" in cmd_args
            
            # Verify password is in environment, not command line (security)
            kwargs = call_args[1]
            assert "env" in kwargs
            assert kwargs["env"]["PGPASSWORD"] == "testpass"

    @patch("asyncio.create_subprocess_exec")
    async def test_backup_failure(self, mock_subprocess):
        """Test backup handles pg_dump failures gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            # Mock failed pg_dump process
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(
                return_value=(b"", b"pg_dump: error: connection failed")
            )
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir)
            )

            # Should raise exception on failure
            with pytest.raises(Exception) as exc_info:
                await service.create_backup()
            
            assert "pg_dump failed" in str(exc_info.value)

    async def test_cleanup_old_backups(self):
        """Test cleanup of old backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir),
                retention_days=0
            )

            # Create a fake old backup file
            old_backup = backup_dir / "vfs_bot_backup_20200101_120000.sql"
            old_backup.write_text("fake backup content")

            # Wait a moment
            await asyncio.sleep(0.1)

            # Cleanup (retention is 0 days, so it should delete)
            deleted = await service.cleanup_old_backups()

            assert deleted == 1
            assert not old_backup.exists()

    async def test_list_backups(self):
        """Test listing backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir)
            )

            # Create multiple fake backup files
            backup1 = backup_dir / "vfs_bot_backup_20240101_120000.sql"
            backup1.write_text("backup 1")
            
            await asyncio.sleep(0.1)
            
            backup2 = backup_dir / "vfs_bot_backup_20240102_120000.sql"
            backup2.write_text("backup 2")

            # List backups
            backups = await service.list_backups()

            assert len(backups) == 2
            assert all("path" in b for b in backups)
            assert all("filename" in b for b in backups)
            assert all("size_bytes" in b for b in backups)
            assert all("created_at" in b for b in backups)
            assert all("age_days" in b for b in backups)

            # Should be sorted by creation time (newest first)
            assert backups[0]["filename"] > backups[1]["filename"]

    @patch("asyncio.create_subprocess_exec")
    async def test_restore_from_backup(self, mock_subprocess):
        """Test restoring from a backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            # Create a fake backup file
            backup_path = backup_dir / "vfs_bot_backup_20240101_120000.sql"
            backup_path.write_text("fake backup content")

            # Create a side effect that creates the file when pg_dump is called (for safety backup)
            def create_backup_file(*args, **kwargs):
                # args is unpacked command elements
                if "-f" in args:
                    f_index = args.index("-f")
                    if f_index + 1 < len(args):
                        file_path = args[f_index + 1]
                        Path(file_path).touch()
                
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_process.returncode = 0
                return mock_process

            mock_subprocess.side_effect = create_backup_file

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir)
            )

            # Restore from backup
            success = await service.restore_from_backup(str(backup_path))
            assert success is True

            # Should be called at least twice (safety backup + restore)
            assert mock_subprocess.call_count >= 2

    async def test_restore_nonexistent_backup(self):
        """Test restore fails when backup doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir)
            )

            with pytest.raises(FileNotFoundError):
                await service.restore_from_backup("/nonexistent/backup.sql")

    @patch("asyncio.create_subprocess_exec")
    async def test_restore_command_structure(self, mock_subprocess):
        """Test that restore generates the correct psql command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            # Create a fake backup file
            backup_path = backup_dir / "vfs_bot_backup_20240101_120000.sql"
            backup_path.write_text("fake backup content")

            # Create a side effect that creates files and tracks calls
            def create_backup_file(*args, **kwargs):
                # args is unpacked command elements
                if "-f" in args:
                    f_index = args.index("-f")
                    if f_index + 1 < len(args):
                        file_path = args[f_index + 1]
                        Path(file_path).touch()
                
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_process.returncode = 0
                return mock_process

            mock_subprocess.side_effect = create_backup_file

            service = DatabaseBackup(
                database_url="postgresql://testuser:testpass@testhost:5433/testdb",
                backup_dir=str(backup_dir)
            )

            # Restore from backup
            await service.restore_from_backup(str(backup_path))

            # Get the last call (restore call, not the safety backup call)
            last_call_args = mock_subprocess.call_args_list[-1]
            # args are unpacked elements
            cmd_args = last_call_args[0]
            
            # Should use psql for restore
            assert cmd_args[0] == "psql"
            assert "-h" in cmd_args
            assert "testhost" in cmd_args
            assert "-p" in cmd_args
            assert "5433" in cmd_args
            assert "-U" in cmd_args
            assert "testuser" in cmd_args
            assert "-d" in cmd_args
            assert "testdb" in cmd_args
            assert "-f" in cmd_args

    async def test_get_stats(self):
        """Test getting backup statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()

            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir),
                retention_days=7,
                interval_hours=6,
            )

            # Create a fake backup
            backup_file = backup_dir / "vfs_bot_backup_20240101_120000.sql"
            backup_file.write_text("fake backup content")

            stats = service.get_stats()

            assert stats["database_url"] == "postgresql://user:pass@localhost:5432/testdb"
            assert stats["backup_dir"] == str(backup_dir)
            assert stats["retention_days"] == 7
            assert stats["interval_hours"] == 6
            assert stats["scheduled_running"] is False
            assert stats["backup_count"] == 1
            assert stats["total_backup_size_bytes"] > 0
            assert stats["latest_backup"] is not None

    @patch("asyncio.create_subprocess_exec")
    async def test_scheduled_backups(self, mock_subprocess):
        """Test scheduled backup functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"

            # Create a side effect that creates the file when pg_dump is called
            def create_backup_file(*args, **kwargs):
                # args is unpacked command elements
                if "-f" in args:
                    f_index = args.index("-f")
                    if f_index + 1 < len(args):
                        file_path = args[f_index + 1]
                        Path(file_path).touch()
                
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_process.returncode = 0
                return mock_process

            mock_subprocess.side_effect = create_backup_file

            # Use very short interval for testing (in hours)
            service = DatabaseBackup(
                database_url="postgresql://user:pass@localhost:5432/testdb",
                backup_dir=str(backup_dir),
                interval_hours=0.001  # ~3.6 seconds
            )

            # Start scheduled backups
            await service.start_scheduled_backups()
            assert service._running is True

            # Wait for at least one backup to be attempted
            await asyncio.sleep(1)

            # Stop scheduled backups
            await service.stop_scheduled_backups()
            assert service._running is False

            # Verify pg_dump was called (at least once for the scheduled backup)
            assert mock_subprocess.called


class TestDatabaseBackupGlobal:
    """Test cases for global database backup service."""

    def test_get_backup_service_singleton(self):
        """Test that get_backup_service returns singleton."""
        # Clear any existing instance
        from src.utils import db_backup

        db_backup._backup_service = None

        service1 = get_backup_service(
            database_url="postgresql://user:pass@localhost:5432/db1",
            retention_days=5
        )
        service2 = get_backup_service(
            database_url="postgresql://user:pass@localhost:5432/db2",
            retention_days=10
        )

        # Should return the same instance
        assert service1 is service2
        assert service1._database_url == "postgresql://user:pass@localhost:5432/db1"
        assert service1._retention_days == 5

    def test_get_backup_service_creates_instance(self):
        """Test that service is created if not exists."""
        from src.utils import db_backup

        db_backup._backup_service = None

        service = get_backup_service()

        assert service is not None
        assert isinstance(service, DatabaseBackup)
