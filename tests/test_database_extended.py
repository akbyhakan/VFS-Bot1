"""Extended tests for database operations."""

import pytest
from cryptography.fernet import Fernet

from src.models.database import Database
from src.utils.encryption import reset_encryption


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    reset_encryption()
    yield key
    reset_encryption()


@pytest.fixture
async def test_db(tmp_path, unique_encryption_key):
    """Create a test database."""
    db_path = tmp_path / "test_extended.db"
    db = Database(str(db_path))
    await db.connect()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_get_appointments_empty(test_db):
    """Test getting appointments when none exist."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    appointments = await test_db.get_appointments(user_id)
    assert len(appointments) == 0


@pytest.mark.asyncio
async def test_multiple_appointments(test_db):
    """Test adding multiple appointments for a user."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Add multiple appointments
    for i in range(3):
        await test_db.add_appointment(
            user_id=user_id,
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay",
            date=f"2024-12-{25+i:02d}",
            time="10:00",
            reference=f"REF{i}",
        )

    appointments = await test_db.get_appointments(user_id)
    assert len(appointments) == 3


@pytest.mark.asyncio
async def test_get_all_appointments(test_db):
    """Test getting all appointments."""
    # Add two users with appointments
    for i in range(2):
        user_id = await test_db.add_user(
            email=f"user{i}@example.com",
            password="password",
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay",
        )
        await test_db.add_appointment(
            user_id=user_id,
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay",
            date="2024-12-25",
            time="10:00",
            reference=f"REF{i}",
        )

    # Get all appointments (no user_id filter)
    all_appointments = await test_db.get_appointments()
    assert len(all_appointments) >= 2


@pytest.mark.asyncio
async def test_get_logs_limit(test_db):
    """Test getting logs with limit."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Add 10 logs
    for i in range(10):
        await test_db.add_log("INFO", f"Message {i}", user_id)

    # Get only 5
    logs = await test_db.get_logs(limit=5)
    assert len(logs) == 5


@pytest.mark.asyncio
async def test_connection_pool_context_manager(test_db):
    """Test using connection pool context manager."""
    async with test_db.get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT 1")
        result = await cursor.fetchone()
        assert result[0] == 1


@pytest.mark.asyncio
async def test_multiple_concurrent_connections(test_db):
    """Test multiple concurrent connections from pool."""
    import asyncio

    async def use_connection(i):
        async with test_db.get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT ?", (i,))
            result = await cursor.fetchone()
            return result[0]

    # Use more connections than pool size to test queuing
    tasks = [use_connection(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    assert results == list(range(10))


@pytest.mark.asyncio
async def test_user_duplicate_email(test_db):
    """Test that duplicate email is handled."""
    await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
    )

    # Try to add duplicate
    with pytest.raises(Exception):  # Should raise unique constraint error
        await test_db.add_user(
            email="test@example.com",
            password="password2",
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay",
        )
