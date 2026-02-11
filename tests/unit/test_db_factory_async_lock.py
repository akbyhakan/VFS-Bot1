"""Tests for DatabaseFactory async lock."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models.db_factory import DatabaseFactory


class TestDatabaseFactoryAsyncLock:
    def setup_method(self):
        DatabaseFactory.reset_instance()

    def teardown_method(self):
        DatabaseFactory.reset_instance()

    @pytest.mark.asyncio
    async def test_ensure_connected_uses_async_lock(self):
        mock_db = MagicMock()
        mock_db.pool = None
        mock_db.connect = AsyncMock()
        
        with patch.object(DatabaseFactory, 'get_instance', return_value=mock_db):
            db = await DatabaseFactory.ensure_connected()
            assert db is mock_db
            mock_db.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_instance_uses_async_lock(self):
        mock_db = MagicMock()
        mock_db.close = AsyncMock()
        DatabaseFactory._instance = mock_db
        
        await DatabaseFactory.close_instance()
        mock_db.close.assert_called_once()
        assert DatabaseFactory._instance is None

    @pytest.mark.asyncio
    async def test_concurrent_ensure_connected(self):
        """Test that concurrent ensure_connected calls are properly serialized."""
        mock_db = MagicMock()
        mock_db.pool = None
        mock_db.connect = AsyncMock()
        
        with patch.object(DatabaseFactory, 'get_instance', return_value=mock_db):
            # Call ensure_connected multiple times concurrently
            tasks = [DatabaseFactory.ensure_connected() for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            # All should return the same instance
            assert all(r is mock_db for r in results)
            # Connect should only be called once
            mock_db.connect.assert_called_once()

    def test_reset_instance_resets_lock(self):
        """Test that reset_instance also resets the async lock."""
        # Create a lock
        DatabaseFactory._get_async_lock()
        assert DatabaseFactory._async_lock is not None
        
        # Reset
        DatabaseFactory.reset_instance()
        
        # Lock should be None
        assert DatabaseFactory._async_lock is None
