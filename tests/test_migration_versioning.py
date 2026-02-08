"""Tests for database migration versioning system.

This test suite validates the migration versioning system in the Database class:
- Fresh database setup: Verifies that all migrations are properly applied to new databases
- Backward compatibility: Ensures existing databases with columns are properly detected
- Idempotency: Confirms migrations can run multiple times without errors or duplicates
- Column verification: Validates that all migrated columns exist in their target tables
"""

import pytest
from cryptography.fernet import Fernet

from src.constants import Database as DatabaseConfig
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
async def test_migration_versioning_fresh_db(unique_encryption_key):
    """Test that migration versioning works on a fresh database."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    # Check that schema_migrations table exists
    async with db.conn.acquire() as conn:
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='schema_migrations')"
        )
        assert result is True, "schema_migrations table should exist"

        # Check that all migrations are recorded
        migrations = await conn.fetch(
            "SELECT version, description FROM schema_migrations ORDER BY version"
        )
        
        # Should have 5 migrations
        assert len(migrations) == 5, f"Expected 5 migrations, got {len(migrations)}"
        
        # Verify migration versions
        expected_versions = [1, 2, 3, 4, 5]
        actual_versions = [m["version"] for m in migrations]
        assert actual_versions == expected_versions, f"Expected versions {expected_versions}, got {actual_versions}"

    await db.close()


@pytest.mark.asyncio
async def test_migration_versioning_backward_compatibility(unique_encryption_key):
    """Test backward compatibility - migrations detected as already applied."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    # Simulate an old database by removing schema_migrations table
    # and checking that columns still get marked as applied
    async with db.conn.acquire() as conn:
        # Drop schema_migrations table
        await conn.execute("DROP TABLE IF EXISTS schema_migrations")

    await db.close()

    # Reconnect - this should detect existing columns and mark migrations as applied
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    async with db.conn.acquire() as conn:
        # Check that all migrations are now marked as applied
        migrations = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        
        assert len(migrations) == 5, f"Expected 5 migrations to be marked as applied, got {len(migrations)}"

    await db.close()


@pytest.mark.asyncio
async def test_migration_idempotency(unique_encryption_key):
    """Test that migrations are idempotent (running twice doesn't fail)."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    # Count migrations
    async with db.conn.acquire() as conn:
        count1 = await conn.fetchval("SELECT COUNT(*) FROM schema_migrations")

    await db.close()

    # Reconnect and migrations should run again (but skip already applied)
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    async with db.conn.acquire() as conn:
        count2 = await conn.fetchval("SELECT COUNT(*) FROM schema_migrations")

    # Count should be the same (no new migrations applied)
    assert count1 == count2, f"Migration count changed from {count1} to {count2}"

    await db.close()


@pytest.mark.asyncio
async def test_migrated_columns_exist(unique_encryption_key):
    """Test that all migrated columns actually exist in the tables."""
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    async with db.conn.acquire() as conn:
        # Check appointment_requests columns
        columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='appointment_requests'"
        )
        column_names = [col["column_name"] for col in columns]
        
        assert "visa_category" in column_names
        assert "visa_subcategory" in column_names

        # Check appointment_persons columns
        person_columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='appointment_persons'"
        )
        person_column_names = [col["column_name"] for col in person_columns]
        
        assert "gender" in person_column_names
        assert "is_child_with_parent" in person_column_names

        # Check payment_card columns
        payment_columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='payment_card'"
        )
        payment_column_names = [col["column_name"] for col in payment_columns]
        
        assert "cvv_encrypted" in payment_column_names

    await db.close()
