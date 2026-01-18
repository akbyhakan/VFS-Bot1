"""Connection pool stress tests."""

import pytest
import asyncio
from src.models.database import Database


@pytest.mark.asyncio
async def test_connection_pool_stress():
    """Test 100 concurrent queries with pool of 10."""
    db = Database(":memory:", pool_size=10)
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
async def test_connection_pool_timeout():
    """Test connection pool timeout when pool is exhausted."""
    db = Database(":memory:", pool_size=2)
    await db.connect()
    
    try:
        # Acquire all connections
        conn1 = await db.get_connection()
        conn2 = await db.get_connection()
        
        # Try to acquire one more with short timeout - should timeout
        with pytest.raises(asyncio.TimeoutError):
            async with db.get_connection(timeout=0.1) as conn:
                pass
        
        # Release connections back
        await db._available_connections.put(conn1)
        await db._available_connections.put(conn2)
        
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_concurrent_writes():
    """Test concurrent write operations don't cause corruption."""
    db = Database(":memory:", pool_size=5)
    await db.connect()
    
    async def add_user(i: int):
        await db.add_user(
            email=f"user{i}@example.com",
            password="testpass123",
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay"
        )
    
    try:
        # Create 20 users concurrently
        tasks = [add_user(i) for i in range(20)]
        await asyncio.gather(*tasks)
        
        # Verify all users were created
        users = await db.get_all_users()
        assert len(users) == 20
        
        # Verify email uniqueness
        emails = [u["email"] for u in users]
        assert len(set(emails)) == 20
        
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_connection_cleanup_on_error():
    """Test connections are returned to pool even on error."""
    db = Database(":memory:", pool_size=5)
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
