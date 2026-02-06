"""Tests for database backup service."""

import asyncio
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.utils.db_backup import DatabaseBackup, get_backup_service


@pytest.mark.asyncio
class TestDatabaseBackup:
    """Test cases for DatabaseBackup class."""

    def create_test_db(self, db_path: Path) -> None:
        """Create a test SQLite database with sample data."""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create table and insert data
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("INSERT INTO users (name) VALUES ('Alice')")
        cursor.execute("INSERT INTO users (name) VALUES ('Bob')")

        conn.commit()
        conn.close()

    async def test_initialization(self):
        """Test service initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            service = DatabaseBackup(
                db_path=str(db_path),
                backup_dir=str(backup_dir),
                retention_days=5,
                interval_hours=3,
            )

            assert service._db_path == db_path
            assert service._backup_dir == backup_dir
            assert service._retention_days == 5
            assert service._interval_hours == 3
            assert backup_dir.exists()  # Should be created

    async def test_create_backup(self):
        """Test creating a backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create test database
            self.create_test_db(db_path)

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            # Create backup
            backup_path = await service.create_backup()

            assert Path(backup_path).exists()
            assert Path(backup_path).stat().st_size > 0
            assert "vfs_bot_backup_" in backup_path
            assert backup_path.endswith(".db")

    async def test_backup_contains_data(self):
        """Test that backup contains the same data as source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create test database
            self.create_test_db(db_path)

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            # Create backup
            backup_path = await service.create_backup()

            # Verify backup has same data
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 2

    async def test_missing_source_database(self):
        """Test backup fails when source database doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nonexistent.db"
            backup_dir = Path(tmpdir) / "backups"

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            with pytest.raises(FileNotFoundError):
                await service.create_backup()

    async def test_cleanup_old_backups(self):
        """Test cleanup of old backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create test database
            self.create_test_db(db_path)

            service = DatabaseBackup(
                db_path=str(db_path), backup_dir=str(backup_dir), retention_days=0
            )

            # Create backup
            await service.create_backup()

            # Wait a moment
            await asyncio.sleep(0.1)

            # Cleanup (retention is 0 days, so it should delete)
            deleted = await service.cleanup_old_backups()

            assert deleted == 1

    async def test_list_backups(self):
        """Test listing backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create test database
            self.create_test_db(db_path)

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            # Create multiple backups with enough delay for different timestamps
            await service.create_backup()
            await asyncio.sleep(1.1)  # Ensure different timestamp in filename
            await service.create_backup()

            # List backups
            backups = await service.list_backups()

            assert len(backups) >= 1  # At least one backup should exist
            assert all("path" in b for b in backups)
            assert all("filename" in b for b in backups)
            assert all("size_bytes" in b for b in backups)
            assert all("created_at" in b for b in backups)
            assert all("age_days" in b for b in backups)

            # Should be sorted by creation time (newest first)
            if len(backups) >= 2:
                assert backups[0]["created_at"] >= backups[1]["created_at"]

    async def test_restore_from_backup(self):
        """Test restoring from a backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create original database
            self.create_test_db(db_path)

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            # Create backup
            backup_path = await service.create_backup()

            # Modify original database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name) VALUES ('Charlie')")
            conn.commit()
            conn.close()

            # Verify modification
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count_before = cursor.fetchone()[0]
            conn.close()
            assert count_before == 3

            # Restore from backup
            success = await service.restore_from_backup(backup_path)
            assert success is True

            # Verify restoration (should be back to 2 users)
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count_after = cursor.fetchone()[0]
            conn.close()

            assert count_after == 2

    async def test_restore_nonexistent_backup(self):
        """Test restore fails when backup doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            with pytest.raises(FileNotFoundError):
                await service.restore_from_backup("/nonexistent/backup.db")

    async def test_get_stats(self):
        """Test getting backup statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create test database
            self.create_test_db(db_path)

            service = DatabaseBackup(
                db_path=str(db_path),
                backup_dir=str(backup_dir),
                retention_days=7,
                interval_hours=6,
            )

            # Create a backup
            await service.create_backup()

            stats = service.get_stats()

            assert stats["db_path"] == str(db_path)
            assert stats["backup_dir"] == str(backup_dir)
            assert stats["retention_days"] == 7
            assert stats["interval_hours"] == 6
            assert stats["scheduled_running"] is False
            assert stats["backup_count"] == 1
            assert stats["total_backup_size_bytes"] > 0
            assert stats["latest_backup"] is not None

    async def test_scheduled_backups(self):
        """Test scheduled backup functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create test database
            self.create_test_db(db_path)

            # Use very short interval for testing
            service = DatabaseBackup(
                db_path=str(db_path), backup_dir=str(backup_dir), interval_hours=0.001
            )

            # Start scheduled backups
            await service.start_scheduled_backups()
            assert service._running is True

            # Wait for at least one backup to complete
            await asyncio.sleep(1)

            # Stop scheduled backups
            await service.stop_scheduled_backups()
            assert service._running is False

            # Check that at least one backup was created
            backups = await service.list_backups()
            assert len(backups) >= 1

    async def test_backup_preserves_safety_backup(self):
        """Test that restore creates a safety backup of current DB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backup_dir = Path(tmpdir) / "backups"

            # Create original database
            self.create_test_db(db_path)

            service = DatabaseBackup(db_path=str(db_path), backup_dir=str(backup_dir))

            # Create backup
            backup_path = await service.create_backup()

            # Modify original
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name) VALUES ('Charlie')")
            conn.commit()
            conn.close()

            # Restore
            await service.restore_from_backup(backup_path)

            # Check that safety backup was created
            safety_backup = db_path.with_suffix(".db.pre-restore")
            assert safety_backup.exists()

            # Verify safety backup has the modified data
            conn = sqlite3.connect(str(safety_backup))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 3


class TestDatabaseBackupGlobal:
    """Test cases for global database backup service."""

    def test_get_backup_service_singleton(self):
        """Test that get_backup_service returns singleton."""
        # Clear any existing instance
        from src.utils import db_backup

        db_backup._backup_service = None

        service1 = get_backup_service(db_path="db1.db", retention_days=5)
        service2 = get_backup_service(db_path="db2.db", retention_days=10)

        # Should return the same instance
        assert service1 is service2
        assert str(service1._db_path) == "db1.db"
        assert service1._retention_days == 5

    def test_get_backup_service_creates_instance(self):
        """Test that service is created if not exists."""
        from src.utils import db_backup

        db_backup._backup_service = None

        service = get_backup_service()

        assert service is not None
        assert isinstance(service, DatabaseBackup)
