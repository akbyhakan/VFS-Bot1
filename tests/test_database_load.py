"""Connection pool stress tests."""

import asyncio

import pytest

from src.models.database import Database


@pytest.mark.asyncio
async def test_connection_pool_stress(tmp_path):
    """Test 100 concurrent queries with pool of 10."""
    db_path = tmp_path / "test_pool.db"
    db = Database(str(db_path), pool_size=10)
    await db.connect()

    async def query(n: int):
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT ?", (n,))
                return await cur.fetchone()

    try:
        tasks = [query(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        assert db._available_connections.qsize() == 10  # All returned

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_connection_pool_timeout(tmp_path):
    """Test connection pool behavior when pool size is limited."""
    db_path = tmp_path / "test_timeout.db"
    db = Database(str(db_path), pool_size=2)
    await db.connect()

    try:
        # Verify pool size is correct
        assert db._available_connections.qsize() == 2

        # Acquire connections
        async with db.get_connection():
            # Pool should have 1 available
            assert db._available_connections.qsize() == 1

            async with db.get_connection():
                # Pool should be empty
                assert db._available_connections.qsize() == 0

        # After exiting context managers, pool should be full again
        assert db._available_connections.qsize() == 2

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_concurrent_writes(database):
    """Test concurrent write operations don't cause corruption."""
    db = database

    async def add_user(i: int):
        await db.add_user(
            email=f"user{i}@example.com",
            password="testpass123",
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay",
        )

    # Create 20 users concurrently
    tasks = [add_user(i) for i in range(20)]
    await asyncio.gather(*tasks)

    # Verify all users were created
    users = await db.get_active_users()  # Use get_active_users instead
    assert len(users) >= 20  # At least 20 users created

    # Verify email uniqueness
    emails = [u["email"] for u in users]
    unique_emails = [e for e in emails if e.startswith("user") and e.endswith("@example.com")]
    assert len(set(unique_emails)) == 20  # All test users are unique


@pytest.mark.asyncio
async def test_connection_cleanup_on_error(tmp_path):
    """Test connections are returned to pool even on error."""
    db_path = tmp_path / "test_cleanup.db"
    db = Database(str(db_path), pool_size=5)
    await db.connect()

    try:
        initial_count = db._available_connections.qsize()

        # Try an operation that will fail
        try:
            async with db.get_connection() as conn:
                async with conn.cursor() as cur:
                    # This will fail
                    await cur.execute("SELECT * FROM nonexistent_table")
        except Exception:
            pass

        # Connection should be returned to pool
        final_count = db._available_connections.qsize()
        assert final_count == initial_count

    finally:
        await db.close()
