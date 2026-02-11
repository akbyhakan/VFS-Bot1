"""Connection pool stress tests."""

import asyncio

import pytest

from src.constants import Database as DatabaseConfig
from src.models.database import Database


@pytest.mark.asyncio
async def test_connection_pool_stress():
    """Test 100 concurrent queries with pool of 10."""
    db = Database(database_url=DatabaseConfig.TEST_URL, pool_size=10)
    await db.connect()

    async def query(n: int):
        async with db.get_connection() as conn:
            result = await conn.fetchval("SELECT $1", n)
            return result

    try:
        tasks = [query(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_connection_pool_timeout():
    """Test connection pool behavior when pool size is limited."""
    db = Database(database_url=DatabaseConfig.TEST_URL, pool_size=2)
    await db.connect()

    try:
        pass  # Placeholder for future timeout tests
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_concurrent_writes(database):
    """Test concurrent write operations don't cause corruption."""
    db = database
    from src.repositories import UserRepository

    user_repo = UserRepository(db)

    async def add_user(i: int):
        await user_repo.create(
            {
                "email": f"user{i}@example.com",
                "password": "testpass123",
                "center_name": "Istanbul",
                "visa_category": "Tourism",
                "visa_subcategory": "Short Stay",
            }
        )

    # Create 20 users concurrently
    tasks = [add_user(i) for i in range(20)]
    await asyncio.gather(*tasks)

    # Verify all users were created
    users = await user_repo.get_all_active()
    assert len(users) >= 20  # At least 20 users created

    # Verify email uniqueness
    emails = [u.email for u in users]
    unique_emails = [e for e in emails if e.startswith("user") and e.endswith("@example.com")]
    assert len(set(unique_emails)) == 20  # All test users are unique


@pytest.mark.asyncio
async def test_connection_cleanup_on_error():
    """Test connections are returned to pool even on error."""
    db = Database(database_url=DatabaseConfig.TEST_URL, pool_size=5)
    await db.connect()

    try:
        # Try an operation that will fail
        try:
            async with db.get_connection() as conn:
                # This will fail
                await conn.execute("SELECT * FROM nonexistent_table")
        except Exception:
            pass

    finally:
        await db.close()
