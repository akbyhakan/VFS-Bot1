"""Tests for DatabaseFactory async lock."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

        with patch.object(DatabaseFactory, "get_instance", return_value=mock_db):
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
        
        async def connect_side_effect():
            # Simulate successful connection by setting pool to non-None value
            mock_db.pool = "connection_pool"
        
        mock_db.connect = AsyncMock(side_effect=connect_side_effect)

        with patch.object(DatabaseFactory, "get_instance", return_value=mock_db):
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

    def test_class_lock_exists(self):
        """Test that _class_lock exists and is a threading.Lock."""
        assert hasattr(DatabaseFactory, "_class_lock")
        # threading.Lock() returns a lock type, check instance against the type
        assert isinstance(DatabaseFactory._class_lock, type(threading.Lock()))

    def test_class_lock_persists_after_reset(self):
        """Test that _class_lock is NOT reset during reset_instance()."""
        original_lock = DatabaseFactory._class_lock

        # Reset instance
        DatabaseFactory.reset_instance()

        # _class_lock should be the same instance (not reset)
        assert DatabaseFactory._class_lock is original_lock

    def test_thread_safe_async_lock_creation(self):
        """Test that multiple threads calling _get_async_lock() get the same lock instance."""
        DatabaseFactory.reset_instance()
        locks_from_threads = []
        barrier = threading.Barrier(5)  # Synchronize 5 threads

        def get_lock_from_thread():
            # Wait for all threads to be ready
            barrier.wait()
            # All threads call _get_async_lock() simultaneously
            lock = DatabaseFactory._get_async_lock()
            locks_from_threads.append(lock)

        # Create and start 5 threads
        threads = [threading.Thread(target=get_lock_from_thread) for _ in range(5)]
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All threads should have gotten the same lock instance
        assert len(locks_from_threads) == 5
        assert all(lock is locks_from_threads[0] for lock in locks_from_threads)
