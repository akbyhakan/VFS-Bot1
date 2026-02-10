"""Tests for db_factory module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.database import Database
from src.models.db_factory import DatabaseFactory


class TestDatabaseFactory:
    """Tests for DatabaseFactory singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        DatabaseFactory.reset_instance()

    def teardown_method(self):
        """Clean up after each test."""
        DatabaseFactory.reset_instance()

    def test_get_instance_creates_singleton(self):
        """Test that get_instance creates a singleton instance."""
        db1 = DatabaseFactory.get_instance()
        db2 = DatabaseFactory.get_instance()
        assert db1 is db2
        assert isinstance(db1, Database)

    def test_get_instance_with_custom_path(self):
        """Test get_instance with custom database URL."""
        db = DatabaseFactory.get_instance(database_url="postgresql://localhost/custom_db")
        assert db.database_url == "postgresql://localhost/custom_db"

    def test_get_instance_with_default_path(self):
        """Test get_instance uses default database URL."""
        import os
        db = DatabaseFactory.get_instance()
        # Should use default from environment or fallback
        expected = os.getenv("DATABASE_URL", "postgresql://localhost:5432/vfs_bot")
        assert db.database_url == expected

    def test_get_instance_with_pool_size(self):
        """Test get_instance with custom pool size."""
        db = DatabaseFactory.get_instance(pool_size=10)
        assert isinstance(db, Database)

    def test_get_instance_ignores_later_params(self):
        """Test that params are ignored after first instance creation."""
        db1 = DatabaseFactory.get_instance(database_url="postgresql://localhost/first_db")
        db2 = DatabaseFactory.get_instance(database_url="postgresql://localhost/second_db")
        assert db1 is db2
        assert db1.database_url == "postgresql://localhost/first_db"

    def test_reset_instance(self):
        """Test reset_instance clears singleton."""
        db1 = DatabaseFactory.get_instance()
        DatabaseFactory.reset_instance()
        db2 = DatabaseFactory.get_instance()
        assert db1 is not db2

    def test_reset_instance_when_none(self):
        """Test reset_instance when no instance exists."""
        DatabaseFactory.reset_instance()
        assert DatabaseFactory._instance is None

    @pytest.mark.asyncio
    async def test_ensure_connected_creates_connection(self):
        """Test ensure_connected creates and connects database."""
        with patch.object(Database, "connect", new_callable=AsyncMock) as _:
            db = await DatabaseFactory.ensure_connected()
            assert isinstance(db, Database)

    @pytest.mark.asyncio
    async def test_ensure_connected_when_already_connected(self):
        """Test ensure_connected when database is already connected."""
        db = DatabaseFactory.get_instance()
        # Simulate already connected
        db.pool = MagicMock()

        with patch.object(Database, "connect", new_callable=AsyncMock) as mock_connect:
            result = await DatabaseFactory.ensure_connected()
            assert result is db
            # Connect should not be called if already connected
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_instance(self):
        """Test close_instance closes and resets singleton."""
        with patch.object(Database, "close", new_callable=AsyncMock) as mock_close:
            _ = DatabaseFactory.get_instance()
            await DatabaseFactory.close_instance()
            mock_close.assert_called_once()
            assert DatabaseFactory._instance is None

    @pytest.mark.asyncio
    async def test_close_instance_when_none(self):
        """Test close_instance when no instance exists."""
        # Should not raise an error
        await DatabaseFactory.close_instance()
        assert DatabaseFactory._instance is None

    def test_thread_safety(self):
        """Test that singleton is thread-safe."""
        import threading

        instances = []

        def create_instance():
            db = DatabaseFactory.get_instance()
            instances.append(db)

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(instances) == 10
        assert all(instance is instances[0] for instance in instances)

    def test_get_instance_none_path_uses_default(self):
        """Test that None database_url uses default value."""
        import os
        db = DatabaseFactory.get_instance(database_url=None)
        expected = os.getenv("DATABASE_URL", "postgresql://localhost:5432/vfs_bot")
        assert db.database_url == expected

    @pytest.mark.asyncio
    async def test_ensure_connected_calls_connect(self):
        """Test ensure_connected calls connect when conn is None."""
        with patch.object(Database, "connect", new_callable=AsyncMock) as mock_connect:
            db = DatabaseFactory.get_instance()
            db.pool = None
            await DatabaseFactory.ensure_connected()
            mock_connect.assert_called_once()
