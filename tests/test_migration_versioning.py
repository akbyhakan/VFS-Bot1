"""Tests for database migration versioning system."""

import pytest
from cryptography.fernet import Fernet

from src.models.database import Database
from src.utils.encryption import reset_encryption


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test and reset global encryption instance."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    reset_encryption()
    yield key
    reset_encryption()


@pytest.mark.asyncio
async def test_migration_versioning_fresh_db(tmp_path, unique_encryption_key):
    """Test that migration versioning works on a fresh database."""
    db_path = tmp_path / "test_fresh_migrations.db"
    db = Database(str(db_path))
    await db.connect()

    # Check that schema_migrations table exists
    async with db.conn.cursor() as cursor:
        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
        result = await cursor.fetchone()
        assert result is not None, "schema_migrations table should exist"

        # Check that all migrations are recorded
        await cursor.execute("SELECT version, description FROM schema_migrations ORDER BY version")
        migrations = await cursor.fetchall()
        
        # Should have 5 migrations
        assert len(migrations) == 5, f"Expected 5 migrations, got {len(migrations)}"
        
        # Verify migration versions
        expected_versions = [1, 2, 3, 4, 5]
        actual_versions = [m[0] for m in migrations]
        assert actual_versions == expected_versions, f"Expected versions {expected_versions}, got {actual_versions}"

    await db.close()


@pytest.mark.asyncio
async def test_migration_versioning_backward_compatibility(tmp_path, unique_encryption_key):
    """Test backward compatibility - migrations detected as already applied."""
    db_path = tmp_path / "test_backward_compat.db"
    db = Database(str(db_path))
    await db.connect()

    # Simulate an old database by removing schema_migrations table
    # and checking that columns still get marked as applied
    async with db.conn.cursor() as cursor:
        # Drop schema_migrations table
        await cursor.execute("DROP TABLE IF EXISTS schema_migrations")
        await db.conn.commit()

    await db.close()

    # Reconnect - this should detect existing columns and mark migrations as applied
    db = Database(str(db_path))
    await db.connect()

    async with db.conn.cursor() as cursor:
        # Check that all migrations are now marked as applied
        await cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        migrations = await cursor.fetchall()
        
        assert len(migrations) == 5, f"Expected 5 migrations to be marked as applied, got {len(migrations)}"

    await db.close()


@pytest.mark.asyncio
async def test_migration_idempotency(tmp_path, unique_encryption_key):
    """Test that migrations are idempotent (running twice doesn't fail)."""
    db_path = tmp_path / "test_idempotency.db"
    db = Database(str(db_path))
    await db.connect()

    # Count migrations
    async with db.conn.cursor() as cursor:
        await cursor.execute("SELECT COUNT(*) FROM schema_migrations")
        count1 = (await cursor.fetchone())[0]

    await db.close()

    # Reconnect and migrations should run again (but skip already applied)
    db = Database(str(db_path))
    await db.connect()

    async with db.conn.cursor() as cursor:
        await cursor.execute("SELECT COUNT(*) FROM schema_migrations")
        count2 = (await cursor.fetchone())[0]

    # Count should be the same (no new migrations applied)
    assert count1 == count2, f"Migration count changed from {count1} to {count2}"

    await db.close()


@pytest.mark.asyncio
async def test_migrated_columns_exist(tmp_path, unique_encryption_key):
    """Test that all migrated columns actually exist in the tables."""
    db_path = tmp_path / "test_columns.db"
    db = Database(str(db_path))
    await db.connect()

    async with db.conn.cursor() as cursor:
        # Check appointment_requests columns
        await cursor.execute("PRAGMA table_info(appointment_requests)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        assert "visa_category" in column_names
        assert "visa_subcategory" in column_names

        # Check appointment_persons columns
        await cursor.execute("PRAGMA table_info(appointment_persons)")
        person_columns = await cursor.fetchall()
        person_column_names = [col[1] for col in person_columns]
        
        assert "gender" in person_column_names
        assert "is_child_with_parent" in person_column_names

        # Check payment_card columns
        await cursor.execute("PRAGMA table_info(payment_card)")
        payment_columns = await cursor.fetchall()
        payment_column_names = [col[1] for col in payment_columns]
        
        assert "cvv_encrypted" in payment_column_names

    await db.close()
