"""Tests for E6: Backup file encryption."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet


class TestBackupEncryption:
    """Tests for E6: Backup file encryption in async backup service."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create a temporary backup directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def encryption_key(self):
        """Generate a test encryption key."""
        return Fernet.generate_key().decode()

    def test_backup_file_extension_is_encrypted(self, temp_backup_dir, encryption_key):
        """Verify backup files use .sql.enc extension."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        backup_path = backup_service._generate_backup_path()
        assert backup_path.suffix == ".enc"
        assert str(backup_path).endswith(".sql.enc")

    def test_generate_backup_path_uses_enc_extension(self, temp_backup_dir, encryption_key):
        """Test _generate_backup_path returns .sql.enc path."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        backup_path = backup_service._generate_backup_path()
        assert "vfs_bot_backup_" in str(backup_path)
        assert backup_path.name.endswith(".sql.enc")

    @pytest.mark.asyncio
    async def test_create_backup_produces_encrypted_file(self, temp_backup_dir, encryption_key):
        """Test that create_backup produces an encrypted file, not plain SQL."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Mock the pg_dump subprocess call
        with patch.object(backup_service, "_perform_backup") as mock_backup:
            # Simulate pg_dump creating a plain SQL file
            async def create_temp_sql(db_url, path):
                temp_path = Path(path)
                temp_path.write_text("-- Test SQL backup\nCREATE TABLE test (id INT);")

            mock_backup.side_effect = create_temp_sql

            backup_path = await backup_service.create_backup()

            # Verify encrypted file exists
            assert backup_path.endswith(".sql.enc")
            assert Path(backup_path).exists()

            # Verify temp SQL file was deleted
            temp_sql_path = Path(backup_path).with_suffix('.sql')
            assert not temp_sql_path.exists()

    @pytest.mark.asyncio
    async def test_encrypted_backup_not_readable_as_sql(self, temp_backup_dir, encryption_key):
        """Test that encrypted backup content is not valid SQL."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Mock the pg_dump subprocess call
        with patch.object(backup_service, "_perform_backup") as mock_backup:
            sql_content = "-- Test SQL backup\nCREATE TABLE test (id INT);"

            async def create_temp_sql(db_url, path):
                Path(path).write_text(sql_content)

            mock_backup.side_effect = create_temp_sql

            backup_path = await backup_service.create_backup()

            # Read encrypted content
            encrypted_content = Path(backup_path).read_text()

            # Encrypted content should not match original SQL
            assert encrypted_content != sql_content
            assert "CREATE TABLE" not in encrypted_content
            # Fernet output is base64, should contain gAAAAA prefix
            assert "gAAAAA" in encrypted_content

    @pytest.mark.asyncio
    async def test_restore_decrypts_before_restore(self, temp_backup_dir, encryption_key):
        """Test restore flow decrypts .sql.enc before feeding to psql."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Create a test encrypted backup
        test_sql = "-- Test SQL\nCREATE TABLE test (id INT);"
        encrypted_path = Path(temp_backup_dir) / "test_backup.sql.enc"

        # Encrypt test data
        cipher = Fernet(encryption_key.encode())
        encrypted_data = cipher.encrypt(test_sql.encode())
        encrypted_path.write_bytes(encrypted_data)

        # Mock the restore subprocess call
        with patch.object(backup_service, "_perform_restore") as mock_restore, \
             patch.object(backup_service, "create_backup") as mock_create:

            mock_restore.return_value = None
            mock_create.return_value = None

            result = await backup_service.restore_from_backup(str(encrypted_path))

            # Verify restore was called
            assert mock_restore.called
            restore_call_args = mock_restore.call_args[0]

            # The first argument should be the path to decrypted temp file
            decrypted_path = restore_call_args[0]
            # Temp file should have been cleaned up
            assert not Path(decrypted_path).exists()

    def test_encryption_key_from_env(self, temp_backup_dir, encryption_key):
        """Test _get_encryption_key reads from environment."""
        from src.utils.db_backup import DatabaseBackup

        # Test BACKUP_ENCRYPTION_KEY priority
        os.environ["BACKUP_ENCRYPTION_KEY"] = encryption_key
        os.environ["ENCRYPTION_KEY"] = "different_key"

        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        key = backup_service._get_encryption_key()
        assert key.decode() == encryption_key

        # Test fallback to ENCRYPTION_KEY
        os.environ.pop("BACKUP_ENCRYPTION_KEY", None)
        os.environ["ENCRYPTION_KEY"] = encryption_key

        key = backup_service._get_encryption_key()
        assert key.decode() == encryption_key

    def test_encryption_key_missing_raises_error(self, temp_backup_dir):
        """Test that missing encryption key raises clear error."""
        from src.utils.db_backup import DatabaseBackup

        # Remove both keys
        os.environ.pop("BACKUP_ENCRYPTION_KEY", None)
        os.environ.pop("ENCRYPTION_KEY", None)

        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        with pytest.raises(ValueError) as exc_info:
            backup_service._get_encryption_key()

        assert "BACKUP_ENCRYPTION_KEY or ENCRYPTION_KEY" in str(exc_info.value)

    def test_encrypt_decrypt_roundtrip(self, temp_backup_dir, encryption_key):
        """Test encrypt then decrypt produces original content."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        original_content = "-- Test SQL backup\nCREATE TABLE users (id INT, name VARCHAR(100));"
        plain_path = Path(temp_backup_dir) / "test.sql"
        encrypted_path = Path(temp_backup_dir) / "test.sql.enc"
        decrypted_path = Path(temp_backup_dir) / "test_decrypted.sql"

        # Write original
        plain_path.write_text(original_content)

        # Encrypt
        backup_service._encrypt_file(plain_path, encrypted_path)

        # Verify encrypted file is different
        encrypted_content = encrypted_path.read_text()
        assert encrypted_content != original_content

        # Decrypt
        backup_service._decrypt_file(encrypted_path, decrypted_path)

        # Verify roundtrip
        decrypted_content = decrypted_path.read_text()
        assert decrypted_content == original_content

    @pytest.mark.asyncio
    async def test_cleanup_handles_both_extensions(self, temp_backup_dir, encryption_key):
        """Test cleanup handles both .sql and .sql.enc files."""
        from datetime import datetime, timedelta, timezone
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
            retention_days=1,  # Only keep 1 day
        )

        # Create old encrypted backup
        old_enc = Path(temp_backup_dir) / "vfs_bot_backup_20200101_000000.sql.enc"
        old_enc.write_text("old encrypted")

        # Create old legacy backup
        old_sql = Path(temp_backup_dir) / "vfs_bot_backup_20200102_000000.sql"
        old_sql.write_text("old plain")

        # Touch files to make them old
        import time
        old_time = time.time() - (2 * 24 * 3600)  # 2 days ago
        os.utime(old_enc, (old_time, old_time))
        os.utime(old_sql, (old_time, old_time))

        # Create new backup
        new_enc = Path(temp_backup_dir) / "vfs_bot_backup_20260210_000000.sql.enc"
        new_enc.write_text("new encrypted")

        # Run cleanup
        deleted = await backup_service.cleanup_old_backups()

        # Verify old files deleted
        assert not old_enc.exists()
        assert not old_sql.exists()
        # New file kept
        assert new_enc.exists()
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_list_backups_includes_encrypted_flag(self, temp_backup_dir, encryption_key):
        """Test list_backups includes encrypted status."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Create encrypted backup
        enc_backup = Path(temp_backup_dir) / "vfs_bot_backup_20260210_120000.sql.enc"
        enc_backup.write_text("encrypted")

        # Create legacy backup
        sql_backup = Path(temp_backup_dir) / "vfs_bot_backup_20260210_110000.sql"
        sql_backup.write_text("plain")

        backups = await backup_service.list_backups()

        assert len(backups) == 2

        # Check encrypted flag
        enc_found = False
        plain_found = False

        for backup in backups:
            if backup["filename"].endswith(".sql.enc"):
                assert backup["encrypted"] is True
                enc_found = True
            elif backup["filename"].endswith(".sql"):
                assert backup["encrypted"] is False
                plain_found = True

        assert enc_found and plain_found

    @pytest.mark.asyncio
    async def test_get_stats_includes_encryption_status(self, temp_backup_dir, encryption_key):
        """Test get_stats includes encryption_enabled field."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        stats = backup_service.get_stats()

        assert "encryption_enabled" in stats
        assert stats["encryption_enabled"] is True


class TestBackupUtilEncryption:
    """Tests for merged db_backup.py encryption (was db_backup_util.py)."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create a temporary backup directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def encryption_key(self):
        """Generate a test encryption key."""
        return Fernet.generate_key().decode()

    @pytest.mark.asyncio
    async def test_async_backup_creates_encrypted_file(self, temp_backup_dir, encryption_key):
        """Test async create_backup produces encrypted output."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Mock pg_dump using async subprocess
        with patch.object(backup_service, "_perform_backup") as mock_backup:
            # Simulate successful pg_dump
            async def create_temp_sql(db_url, path):
                temp_path = Path(path)
                temp_path.write_text("-- Test SQL backup")

            mock_backup.side_effect = create_temp_sql

            backup_path = await backup_service.create_backup()

            assert backup_path is not None
            assert backup_path.endswith(".sql.enc")
            assert Path(backup_path).exists()

            # Verify temp SQL was deleted
            temp_sql = Path(backup_path).with_suffix('.sql')
            assert not temp_sql.exists()

    @pytest.mark.asyncio
    async def test_async_restore_decrypts(self, temp_backup_dir, encryption_key):
        """Test async restore_from_backup handles encrypted files."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Create encrypted backup
        test_sql = "-- Test SQL\nCREATE TABLE test (id INT);"
        encrypted_path = Path(temp_backup_dir) / "test_backup.sql.enc"

        cipher = Fernet(encryption_key.encode())
        encrypted_data = cipher.encrypt(test_sql.encode())
        encrypted_path.write_bytes(encrypted_data)

        # Mock subprocess and create_backup
        with patch.object(backup_service, "_perform_restore") as mock_restore, \
             patch.object(backup_service, "create_backup") as mock_create:

            mock_restore.return_value = None
            mock_create.return_value = str(Path(temp_backup_dir) / "pre_restore.sql.enc")

            result = await backup_service.restore_from_backup(str(encrypted_path))

            assert result is True
            assert mock_restore.called

    @pytest.mark.asyncio
    async def test_async_cleanup_handles_both_extensions(self, temp_backup_dir, encryption_key):
        """Test async cleanup handles .sql and .sql.enc with max_backups."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
            max_backups=2,
        )

        # Create multiple backups
        backups = [
            Path(temp_backup_dir) / "vfs_bot_backup_20260210_120000.sql.enc",
            Path(temp_backup_dir) / "vfs_bot_backup_20260210_110000.sql",
            Path(temp_backup_dir) / "vfs_bot_backup_20260210_100000.sql.enc",
            Path(temp_backup_dir) / "vfs_bot_backup_20260210_090000.sql",
        ]

        import time
        for i, backup in enumerate(backups):
            backup.write_text(f"backup {i}")
            # Set mtime to ensure order (newest first)
            mtime = time.time() - (i * 100)
            os.utime(backup, (mtime, mtime))

        # Run cleanup
        deleted = await backup_service.cleanup_old_backups()

        # Should keep 2 newest, delete 2 oldest
        assert backups[0].exists()  # newest encrypted
        assert backups[1].exists()  # 2nd newest
        assert not backups[2].exists()  # 3rd - deleted
        assert not backups[3].exists()  # oldest - deleted
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_async_list_backups_both_extensions(self, temp_backup_dir, encryption_key):
        """Test list_backups returns both encrypted and legacy files."""
        from src.utils.db_backup import DatabaseBackup

        os.environ["ENCRYPTION_KEY"] = encryption_key
        backup_service = DatabaseBackup(
            database_url="postgresql://test:test@localhost:5432/test",
            backup_dir=temp_backup_dir,
        )

        # Create both types
        enc_backup = Path(temp_backup_dir) / "vfs_bot_backup_20260210_120000.sql.enc"
        enc_backup.write_text("encrypted")

        sql_backup = Path(temp_backup_dir) / "vfs_bot_backup_20260210_110000.sql"
        sql_backup.write_text("plain")

        backups = await backup_service.list_backups()

        assert len(backups) == 2
        backup_names = [b["filename"] for b in backups]
        assert "vfs_bot_backup_20260210_120000.sql.enc" in backup_names
        assert "vfs_bot_backup_20260210_110000.sql" in backup_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
