"""Test REQUIRE_MIGRATIONS environment variable functionality."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.database import Database


@pytest.mark.asyncio
async def test_require_migrations_default_true():
    """Test that REQUIRE_MIGRATIONS defaults to True."""
    db = Database(database_url="postgresql://test:test@localhost:5432/test")
    assert db._require_migrations is True


@pytest.mark.asyncio
async def test_require_migrations_explicit_false():
    """Test that REQUIRE_MIGRATIONS=false disables requirement."""
    with patch.dict(os.environ, {"REQUIRE_MIGRATIONS": "false"}):
        db = Database(database_url="postgresql://test:test@localhost:5432/test")
        assert db._require_migrations is False


@pytest.mark.asyncio
async def test_require_migrations_explicit_true():
    """Test that REQUIRE_MIGRATIONS=true enables requirement."""
    with patch.dict(os.environ, {"REQUIRE_MIGRATIONS": "true"}):
        db = Database(database_url="postgresql://test:test@localhost:5432/test")
        assert db._require_migrations is True


@pytest.mark.asyncio
async def test_missing_alembic_raises_error_when_required():
    """Test that missing alembic_version raises RuntimeError when REQUIRE_MIGRATIONS=true."""
    with patch.dict(os.environ, {"REQUIRE_MIGRATIONS": "true"}):
        db = Database(database_url="postgresql://test:test@localhost:5432/test")

        # Mock the pool and connection
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=False)  # alembic_version not found

        mock_acquire_cm = MagicMock()
        mock_acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_cm.__aexit__ = AsyncMock(
            return_value=None
        )  # Return None to not suppress exceptions

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acquire_cm
        mock_pool.close = AsyncMock()

        # Mock asyncpg.create_pool in the correct module
        with patch(
            "src.models.db_connection.asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)
        ):
            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="Alembic version table not found"):
                await db.connect()


@pytest.mark.asyncio
async def test_missing_alembic_warning_when_not_required():
    """Test that missing alembic_version only warns when REQUIRE_MIGRATIONS=false."""
    with patch.dict(os.environ, {"REQUIRE_MIGRATIONS": "false"}):
        db = Database(database_url="postgresql://test:test@localhost:5432/test")

        # Mock the pool and connection
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=False)  # alembic_version not found

        mock_acquire_cm = MagicMock()
        mock_acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_cm.__aexit__ = AsyncMock(
            return_value=None
        )  # Return None to not suppress exceptions

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acquire_cm

        # Mock asyncpg.create_pool in the correct module
        with patch(
            "src.models.db_connection.asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)
        ):
            # Should NOT raise, only warn
            await db.connect()

            # Verify connection was attempted
            assert db.pool is not None


@pytest.mark.asyncio
async def test_reconnect_skips_migration_check():
    """Test that reconnect() skips Alembic migration check after first connect()."""
    with patch.dict(os.environ, {"REQUIRE_MIGRATIONS": "true"}):
        db = Database(database_url="postgresql://test:test@localhost:5432/test")

        # Mock the pool and connection
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=True)  # alembic_version found

        mock_acquire_cm = MagicMock()
        mock_acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_cm.__aexit__ = AsyncMock(
            return_value=None
        )  # Return None to not suppress exceptions

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acquire_cm
        mock_pool.close = AsyncMock()

        # Mock asyncpg.create_pool in the correct module
        with patch(
            "src.models.db_connection.asyncpg.create_pool",
            new=AsyncMock(return_value=mock_pool),
        ):
            # First connect - should check migrations
            await db.connect()

            # Verify migration check was called
            # Should call fetchval at least twice: EXISTS check + version_num query
            assert mock_conn.fetchval.call_count >= 2
            # Verify the first call was the EXISTS check
            first_call_query = mock_conn.fetchval.call_args_list[0][0][0]
            assert "EXISTS" in first_call_query and "alembic_version" in first_call_query

            mock_conn.fetchval.reset_mock()

            # Reconnect - should NOT check migrations again
            await db.reconnect()

            # Verify migration check was NOT called during reconnect
            # fetchval should not be called at all
            assert mock_conn.fetchval.call_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
