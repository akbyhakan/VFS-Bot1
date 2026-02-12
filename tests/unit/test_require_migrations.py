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
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()
        
        # Set the pool
        db.pool = mock_pool
        
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
        mock_acquire_cm.__aexit__ = AsyncMock()
        
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_acquire_cm
        
        # Mock asyncpg.create_pool to return our mock pool
        with patch('asyncpg.create_pool', new=AsyncMock(return_value=mock_pool)):
            # Should NOT raise, only warn
            await db.connect()
            
            # Verify connection was attempted
            assert db.pool is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
