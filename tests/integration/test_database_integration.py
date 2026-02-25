"""Integration tests for database operations."""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.repositories import AccountPoolRepository

# Try to import testcontainers
try:
    from testcontainers.postgres import PostgresContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False


@pytest_asyncio.fixture
async def postgres_url() -> AsyncGenerator[str, None]:
    """
    Create a PostgreSQL container for integration tests.

    Yields:
        PostgreSQL connection URL
    """
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not available")

    # Use testcontainers to create a real PostgreSQL instance
    with PostgresContainer("postgres:15") as postgres:
        yield postgres.get_connection_url()


@pytest_asyncio.fixture
async def db(postgres_url: str) -> AsyncGenerator[Database, None]:
    """
    Create database instance using testcontainers PostgreSQL.

    Args:
        postgres_url: PostgreSQL connection URL from container

    Yields:
        Database instance for testing
    """
    database = Database(database_url=postgres_url)
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def integration_db() -> AsyncGenerator[Database, None]:
    """
    Create integration test database.

    Yields:
        Database instance for testing
    """
    db = Database(database_url=DatabaseConfig.TEST_URL)
    await db.connect()
    yield db
    await db.close()


@pytest.mark.integration
class TestDatabaseIntegrationWithTestcontainers:
    """Integration tests using testcontainers for real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_database_connect_and_health_check(self, db: Database):
        """Test database connection and health check."""
        # Verify connection is established
        assert db.pool is not None, "Database pool should be established"

        # Verify health check passes
        is_healthy = await db.health_check()
        assert is_healthy is True, "Database should be healthy"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_connection_pool_under_pressure(self, db: Database):
        """Test connection pool under concurrent load."""

        async def health_check_task() -> bool:
            """Execute a health check."""
            try:
                return await db.health_check()
            except Exception:
                return False

        # Create 20 concurrent health check tasks
        tasks = [health_check_task() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # At least 90% should succeed
        success_count = sum(1 for r in results if r is True)
        success_rate = success_count / len(results)

        assert success_rate >= 0.90, (
            f"Expected >= 90% success rate, got {success_rate:.1%} "
            f"({success_count}/{len(results)} successful)"
        )


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, integration_db: Database):
        """Test creating multiple users concurrently."""

        async def create_user(i: int) -> int:
            """Create a single user."""
            user_repo = AccountPoolRepository(integration_db)
            return await user_repo.create(
                {
                    "email": f"user{i}@test.com",
                    "password": f"password{i}",
                    "center_name": "Istanbul",
                    "visa_category": "Schengen",
                    "visa_subcategory": "Tourism",
                }
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
            async with integration_db.get_connection(timeout=5.0):
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
            async with integration_db.get_connection(timeout=5.0):
                await asyncio.sleep(duration)

        # Fill the connection pool (default size is 10)
        hold_tasks = [hold_connection(2.0) for _ in range(10)]

        # Start the holding tasks - gather returns a future, not a coroutine
        gather_future = asyncio.gather(*hold_tasks)
        await asyncio.sleep(0.1)  # Give time for connections to be acquired

        # Try to get another connection with short timeout - should fail
        from src.core.exceptions import DatabasePoolTimeoutError

        with pytest.raises(DatabasePoolTimeoutError, match="Database connection pool exhausted"):
            async with integration_db.get_connection(timeout=0.5):
                pass

        # Clean up: wait for holding tasks to complete or cancel them
        try:
            await asyncio.wait_for(gather_future, timeout=3.0)
        except asyncio.TimeoutError:
            gather_future.cancel()
            try:
                await gather_future
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_transaction_isolation(self, integration_db: Database):
        """Test transaction isolation between connections."""

        # Create a user
        user_repo = AccountPoolRepository(integration_db)
        user_id = await user_repo.create(
            {
                "email": "test@example.com",
                "password": "testpass",
                "center_name": "Istanbul",
                "visa_category": "Schengen",
                "visa_subcategory": "Tourism",
            }
        )

        async def read_user() -> dict:
            """Read user in separate connection."""
            async with integration_db.get_connection() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
                return dict(row) if row else {}

        async def update_user() -> None:
            """Update user in separate connection."""
            async with integration_db.get_connection() as conn:
                await conn.execute("UPDATE users SET centre = $1 WHERE id = $2", "Ankara", user_id)

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
        user_repo = AccountPoolRepository(integration_db)
        user_ids = []
        for i in range(5):
            user_id = await user_repo.create(
                {
                    "email": f"concurrent{i}@test.com",
                    "password": f"pass{i}",
                    "center_name": "Istanbul",
                    "visa_category": "Schengen",
                    "visa_subcategory": "Tourism",
                }
            )
            user_ids.append(user_id)

        user_repo = AccountPoolRepository(integration_db)

        async def read_users() -> list:
            """Read all users."""
            return await user_repo.get_all_active()

        async def add_personal_details(user_id: int) -> None:
            """Add personal details for a user."""
            await AccountPoolRepository(integration_db).add_personal_details(
                user_id=user_id,
                details={
                    "first_name": f"User{user_id}",
                    "last_name": "Test",
                    "passport_number": f"PASS{user_id:04d}",
                    "email": f"concurrent{user_id}@test.com",
                },
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

        # Verify failure counter is reset
        assert integration_db._consecutive_failures == 0

        # Verify state is CONNECTED
        assert integration_db.state == "connected"

    @pytest.mark.asyncio
    async def test_batch_personal_details_retrieval(self, integration_db: Database):
        """Test batch retrieval of personal details."""

        # Create users with personal details
        user_repo = AccountPoolRepository(integration_db)
        user_ids = []
        for i in range(5):
            user_id = await user_repo.create(
                {
                    "email": f"batch{i}@test.com",
                    "password": f"pass{i}",
                    "center_name": "Istanbul",
                    "visa_category": "Schengen",
                    "visa_subcategory": "Tourism",
                }
            )
            user_ids.append(user_id)

            await AccountPoolRepository(integration_db).add_personal_details(
                user_id=user_id,
                details={
                    "first_name": f"User{i}",
                    "last_name": "Batch",
                    "passport_number": f"BATCH{i:04d}",
                    "email": f"batch{i}@test.com",
                },
            )

        # Retrieve all at once (batch operation)
        details_map = await AccountPoolRepository(integration_db).get_personal_details_batch(user_ids)

        # Verify all details retrieved
        assert len(details_map) == 5, "Should retrieve all personal details"
        for user_id in user_ids:
            assert user_id in details_map, f"User {user_id} should be in results"
            assert details_map[user_id]["first_name"].startswith("User")


@pytest.mark.integration
class TestDatabaseContextManager:
    """Tests for database async context manager."""

    @pytest.mark.asyncio
    async def test_database_context_manager(self):
        """Test database async context manager."""
        from src.models.database import Database

        async with Database(database_url=DatabaseConfig.TEST_URL) as db:
            assert db.pool is not None

            # Should be able to use the database
            user_repo = AccountPoolRepository(db)
            user_id = await user_repo.create(
                {
                    "email": "context@test.com",
                    "password": "password",
                    "center_name": "Istanbul",
                    "visa_category": "Schengen",
                    "visa_subcategory": "Tourism",
                }
            )
            assert user_id > 0

        # After context exit, connection should be closed
        # (We can't easily test this without accessing internals)

    @pytest.mark.asyncio
    async def test_database_context_manager_exception_handling(self):
        """Test that database context manager closes on exception."""
        from src.models.database import Database

        with pytest.raises(RuntimeError):
            async with Database(database_url=DatabaseConfig.TEST_URL) as db:
                assert db.pool is not None
                # Force an exception
                raise RuntimeError("Test exception")

        # Context manager should have closed the connection despite exception


@pytest.mark.integration
class TestCentreFetcherCache:
    """Tests for CentreFetcher cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_background_cleanup(self):
        """Test background cache cleanup removes expired entries."""
        import asyncio

        from src.services.data_sync.centre_fetcher import CentreFetcher

        fetcher = CentreFetcher(
            base_url="https://example.com",
            country="tur",
            mission="deu",
            language="tr",
            cache_ttl=1,  # 1 second TTL for testing
        )

        # Manually add a cache entry
        fetcher._set_cache("test_key", "test_value", ttl=1)

        # Verify entry exists
        assert fetcher._get_from_cache("test_key") == "test_value"

        # Wait for expiry
        await asyncio.sleep(1.5)

        # Clean up expired entries
        removed = await fetcher.cleanup_expired()

        # Should have removed the expired entry
        assert removed == 1
        assert fetcher._get_from_cache("test_key") is None

    @pytest.mark.asyncio
    async def test_periodic_cleanup_task(self):
        """Test that periodic cleanup task can be started."""
        import asyncio

        from src.services.data_sync.centre_fetcher import CentreFetcher

        fetcher = CentreFetcher(
            base_url="https://example.com", country="tur", mission="deu", language="tr", cache_ttl=1
        )

        # Start periodic cleanup (short interval for testing)
        cleanup_task = await fetcher.start_periodic_cleanup(interval_seconds=0.5)

        # Verify task is running
        assert not cleanup_task.done()

        # Cancel the task
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass  # Expected
