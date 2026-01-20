"""Integration tests for database operations."""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from src.models.database import Database


@pytest_asyncio.fixture
async def integration_db(tmp_path: Path) -> AsyncGenerator[Database, None]:
    """
    Create integration test database.

    Args:
        tmp_path: Pytest temporary directory fixture

    Yields:
        Database instance for testing
    """
    db_path = tmp_path / "integration_test.db"
    db = Database(str(db_path))
    await db.connect()
    yield db
    await db.close()


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, integration_db: Database):
        """Test creating multiple users concurrently."""

        async def create_user(i: int) -> int:
            """Create a single user."""
            return await integration_db.add_user(
                email=f"user{i}@test.com",
                password=f"password{i}",
                centre="Istanbul",
                category="Schengen",
                subcategory="Tourism"
            )

        # Create 10 users concurrently
        tasks = [create_user(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all succeeded
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 10, "All user creations should succeed"

        # Verify unique IDs
        assert len(set(successful)) == 10, "All user IDs should be unique"

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, integration_db: Database):
        """Test behavior when connection pool is exhausted."""

        async def long_running_query(delay: float) -> bool:
            """Hold a connection for specified delay."""
            async with integration_db.get_connection(timeout=5.0) as conn:
                await asyncio.sleep(delay)
                return True

        # Start tasks that will hold connections
        # Pool size is 10 by default, so 5 concurrent tasks should be fine
        tasks = [long_running_query(0.5) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert all(results), "All queries should complete successfully"

    @pytest.mark.asyncio
    async def test_connection_pool_timeout(self, integration_db: Database):
        """Test connection pool timeout when all connections are busy."""

        async def hold_connection(duration: float) -> None:
            """Hold a connection for specified duration."""
            async with integration_db.get_connection(timeout=5.0) as conn:
                await asyncio.sleep(duration)

        # Fill the connection pool (default size is 10)
        hold_tasks = [hold_connection(2.0) for _ in range(10)]

        # Start the holding tasks
        asyncio.create_task(asyncio.gather(*hold_tasks))
        await asyncio.sleep(0.1)  # Give time for connections to be acquired

        # Try to get another connection with short timeout - should fail
        with pytest.raises(RuntimeError, match="Database connection pool exhausted"):
            async with integration_db.get_connection(timeout=0.5):
                pass

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, integration_db: Database):
        """Test transaction isolation between connections."""

        # Create a user
        user_id = await integration_db.add_user(
            email="test@example.com",
            password="testpass",
            centre="Istanbul",
            category="Schengen",
            subcategory="Tourism"
        )

        async def read_user() -> dict:
            """Read user in separate connection."""
            async with integration_db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                    row = await cursor.fetchone()
                    return dict(row) if row else {}

        async def update_user() -> None:
            """Update user in separate connection."""
            async with integration_db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "UPDATE users SET centre = ? WHERE id = ?",
                        ("Ankara", user_id)
                    )
                    await conn.commit()

        # Initial read
        user = await read_user()
        assert user["centre"] == "Istanbul"

        # Update in separate connection
        await update_user()

        # Read again - should see the update
        user = await read_user()
        assert user["centre"] == "Ankara"

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self, integration_db: Database):
        """Test concurrent read and write operations."""

        # Create initial users
        user_ids = []
        for i in range(5):
            user_id = await integration_db.add_user(
                email=f"concurrent{i}@test.com",
                password=f"pass{i}",
                centre="Istanbul",
                category="Schengen",
                subcategory="Tourism"
            )
            user_ids.append(user_id)

        async def read_users() -> list:
            """Read all users."""
            return await integration_db.get_active_users()

        async def add_personal_details(user_id: int) -> None:
            """Add personal details for a user."""
            await integration_db.add_personal_details(
                user_id=user_id,
                details={
                    "first_name": f"User{user_id}",
                    "last_name": "Test",
                    "passport_number": f"PASS{user_id:04d}",
                    "email": f"concurrent{user_id}@test.com"
                }
            )

        # Mix reads and writes concurrently
        tasks = []
        tasks.extend([read_users() for _ in range(3)])
        tasks.extend([add_personal_details(uid) for uid in user_ids])
        tasks.extend([read_users() for _ in range(3)])

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"No exceptions should occur, but got: {exceptions}"

    @pytest.mark.asyncio
    async def test_health_check(self, integration_db: Database):
        """Test database health check functionality."""
        is_healthy = await integration_db.health_check()
        assert is_healthy is True, "Database should be healthy"

    @pytest.mark.asyncio
    async def test_batch_personal_details_retrieval(self, integration_db: Database):
        """Test batch retrieval of personal details."""

        # Create users with personal details
        user_ids = []
        for i in range(5):
            user_id = await integration_db.add_user(
                email=f"batch{i}@test.com",
                password=f"pass{i}",
                centre="Istanbul",
                category="Schengen",
                subcategory="Tourism"
            )
            user_ids.append(user_id)

            await integration_db.add_personal_details(
                user_id=user_id,
                details={
                    "first_name": f"User{i}",
                    "last_name": "Batch",
                    "passport_number": f"BATCH{i:04d}",
                    "email": f"batch{i}@test.com"
                }
            )

        # Retrieve all at once (batch operation)
        details_map = await integration_db.get_personal_details_batch(user_ids)

        # Verify all details retrieved
        assert len(details_map) == 5, "Should retrieve all personal details"
        for user_id in user_ids:
            assert user_id in details_map, f"User {user_id} should be in results"
            assert details_map[user_id]["first_name"].startswith("User")
