"""Shared fixtures for integration tests requiring real PostgreSQL and Redis."""

import logging
import os
from typing import Any, AsyncGenerator, Dict

import pytest
import pytest_asyncio

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.repositories.appointment_repository import AppointmentRepository
from src.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


def pytest_collection_modifyitems(config, items):
    """
    Automatically skip integration tests if database is unavailable.

    This prevents test failures in environments without PostgreSQL.
    """
    # Check if we should skip integration tests
    test_db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")

    # If no database URL is set, skip all integration tests
    if not test_db_url:
        skip_integration = pytest.mark.skip(
            reason="TEST_DATABASE_URL or DATABASE_URL not set - skipping integration tests"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
        return

    # Try to connect to verify database is available
    try:
        import asyncio

        import asyncpg

        async def check_db():
            try:
                conn = await asyncio.wait_for(asyncpg.connect(test_db_url), timeout=5.0)
                await conn.close()
                return True
            except Exception as e:
                logger.warning(f"Database connection failed: {e}")
                return False

        db_available = asyncio.run(check_db())

        if not db_available:
            skip_integration = pytest.mark.skip(
                reason="PostgreSQL database is not available - skipping integration tests"
            )
            for item in items:
                if "integration" in item.keywords:
                    item.add_marker(skip_integration)
    except Exception as e:
        logger.error(f"Error checking database availability: {e}")
        skip_integration = pytest.mark.skip(reason=f"Cannot verify database availability: {e}")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[Database, None]:
    """
    Provide a real database connection for integration tests.

    Automatically cleans up test data after each test by truncating tables.

    Yields:
        Database instance connected to test database
    """
    # Use TEST_DATABASE_URL or fallback to DATABASE_URL with test suffix
    database_url = os.getenv("TEST_DATABASE_URL") or DatabaseConfig.TEST_URL

    db = Database(database_url=database_url)
    await db.connect()

    try:
        yield db
    finally:
        # Cleanup: truncate test tables (preserve schema)
        try:
            async with db.pool.acquire() as conn:
                # Disable foreign key constraints temporarily
                await conn.execute("SET CONSTRAINTS ALL DEFERRED;")

                # Truncate tables in reverse dependency order
                await conn.execute("TRUNCATE TABLE appointments RESTART IDENTITY CASCADE;")
                await conn.execute("TRUNCATE TABLE personal_details RESTART IDENTITY CASCADE;")
                await conn.execute("TRUNCATE TABLE users RESTART IDENTITY CASCADE;")
                await conn.execute("TRUNCATE TABLE appointment_history RESTART IDENTITY CASCADE;")
                await conn.execute("TRUNCATE TABLE audit_logs RESTART IDENTITY CASCADE;")

                logger.info("Test database tables truncated successfully")
        except Exception as e:
            logger.warning(f"Failed to truncate test tables: {e}")

        await db.close()


@pytest_asyncio.fixture
async def user_repo(test_db: Database) -> UserRepository:
    """
    Provide a UserRepository connected to the test database.

    Args:
        test_db: Test database fixture

    Returns:
        UserRepository instance
    """
    return UserRepository(test_db)


@pytest_asyncio.fixture
async def appointment_repo(test_db: Database) -> AppointmentRepository:
    """
    Provide an AppointmentRepository connected to the test database.

    Args:
        test_db: Test database fixture

    Returns:
        AppointmentRepository instance
    """
    return AppointmentRepository(test_db)


@pytest_asyncio.fixture
async def test_user(user_repo: UserRepository) -> Dict[str, Any]:
    """
    Create a test user in the database for reuse across tests.

    Args:
        user_repo: UserRepository fixture

    Returns:
        Dictionary containing test user data including ID
    """
    user_data = {
        "email": "integration_test@example.com",
        "password": "SecureTestPass123!",
        "center_name": "Istanbul",
        "visa_category": "Schengen",
        "visa_subcategory": "Tourism",
    }

    user_id = await user_repo.create(user_data)

    return {"id": user_id, **user_data}


@pytest.fixture
def redis_available() -> bool:
    """
    Check if Redis is available for testing.

    Returns:
        True if Redis is available, False otherwise
    """
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return False

    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=2)
        client.ping()
        client.close()
        return True
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return False
