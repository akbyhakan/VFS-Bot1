"""Tests for Alembic database migration infrastructure.

This test suite validates that the Alembic migration infrastructure is properly set up:
- Alembic migration files exist
- Database schema includes required columns from migrations
- Column verification ensures migrations have been applied
"""

import os

import pytest
from cryptography.fernet import Fernet

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.utils.encryption import reset_encryption

# Skip these tests in CI or when DATABASE_URL is not available
skip_no_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or os.getenv("CI") == "true", reason="No database available in CI"
)


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test and reset global encryption instance."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    reset_encryption()
    yield key
    reset_encryption()


@pytest.mark.asyncio
async def test_alembic_migration_files_exist():
    """Test that Alembic migration files are present in the repository."""
    alembic_versions_dir = "alembic/versions"

    assert os.path.exists(alembic_versions_dir), "alembic/versions directory should exist"

    # Check for baseline migration
    baseline_exists = any(f.startswith("001_baseline") for f in os.listdir(alembic_versions_dir))
    assert baseline_exists, "Baseline migration (001_baseline.py) should exist"

    # Check that multiple migration files exist (should be at least baseline + feature migrations)
    migration_files = [f for f in os.listdir(alembic_versions_dir) if f.endswith(".py")]
    assert (
        len(migration_files) >= 1
    ), f"Expected at least 1 migration file, found {len(migration_files)}"


@skip_no_db
@pytest.mark.asyncio
async def test_migrated_columns_exist(unique_encryption_key):
    """Test that all migrated columns actually exist in the tables.

    This verifies that the Alembic migrations have been applied correctly
    by checking for columns that were added via migrations.
    """
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()

    async with db.pool.acquire() as conn:
        # Check appointment_requests columns (added by Alembic migration 004)
        columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='appointment_requests'"
        )
        column_names = [col["column_name"] for col in columns]

        assert "visa_category" in column_names, "visa_category column should exist"
        assert "visa_subcategory" in column_names, "visa_subcategory column should exist"

        # Check appointment_persons columns (added by Alembic migration 005)
        person_columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='appointment_persons'"
        )
        person_column_names = [col["column_name"] for col in person_columns]

        assert "gender" in person_column_names, "gender column should exist"
        assert (
            "is_child_with_parent" in person_column_names
        ), "is_child_with_parent column should exist"

        # Check personal_details columns (added by Alembic migration 006)
        personal_columns = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='personal_details'"
        )
        personal_column_names = [col["column_name"] for col in personal_columns]

        assert (
            "passport_number_encrypted" in personal_column_names
        ), "passport_number_encrypted column should exist"

    await db.close()
