"""Tests for database operations with password encryption."""

import pytest
from pathlib import Path
from cryptography.fernet import Fernet

from src.models.database import Database
from src.utils.encryption import PasswordEncryption


@pytest.fixture
def encryption_key(monkeypatch):
    """Set up encryption key for tests."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    return key


@pytest.fixture
async def test_db(encryption_key):
    """Create a test database."""
    db_path = "test_database.db"
    db = Database(db_path)
    await db.connect()
    yield db
    await db.close()
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_add_user_encrypts_password(test_db, encryption_key):
    """Test that add_user encrypts passwords."""
    email = "test@example.com"
    password = "MyPassword123"
    
    user_id = await test_db.add_user(
        email=email,
        password=password,
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay"
    )
    
    assert user_id > 0
    
    # Get user from database
    users = await test_db.get_active_users()
    assert len(users) == 1
    
    user = users[0]
    assert user["email"] == email
    
    # Password should be encrypted (not plaintext)
    assert user["password"] != password
    
    # But should be decryptable
    enc = PasswordEncryption(encryption_key)
    decrypted = enc.decrypt_password(user["password"])
    assert decrypted == password


@pytest.mark.asyncio
async def test_get_user_with_decrypted_password(test_db):
    """Test getting user with decrypted password."""
    email = "test@example.com"
    password = "MyPassword123"
    
    user_id = await test_db.add_user(
        email=email,
        password=password,
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay"
    )
    
    # Get user with decrypted password
    user = await test_db.get_user_with_decrypted_password(user_id)
    
    assert user is not None
    assert user["email"] == email
    assert user["password"] == password  # Should be decrypted


@pytest.mark.asyncio
async def test_get_active_users_with_decrypted_passwords(test_db):
    """Test getting all active users with decrypted passwords."""
    # Add multiple users
    users_data = [
        ("user1@example.com", "password1"),
        ("user2@example.com", "password2"),
        ("user3@example.com", "password3"),
    ]
    
    for email, password in users_data:
        await test_db.add_user(
            email=email,
            password=password,
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay"
        )
    
    # Get all users with decrypted passwords
    users = await test_db.get_active_users_with_decrypted_passwords()
    
    assert len(users) == 3
    
    # Check passwords are decrypted
    for i, user in enumerate(users):
        assert user["password"] == users_data[i][1]


@pytest.mark.asyncio
async def test_connection_pooling(test_db):
    """Test that connection pooling works."""
    # Connection pool should be initialized
    assert len(test_db._pool) == test_db.pool_size
    
    # Should be able to get connections
    async with test_db.get_connection() as conn:
        assert conn is not None


@pytest.mark.asyncio
async def test_concurrent_database_operations(test_db):
    """Test concurrent database operations with connection pool."""
    import asyncio
    
    async def add_user(i):
        await test_db.add_user(
            email=f"user{i}@example.com",
            password=f"password{i}",
            centre="Istanbul",
            category="Tourism",
            subcategory="Short Stay"
        )
    
    # Add 10 users concurrently
    tasks = [add_user(i) for i in range(10)]
    await asyncio.gather(*tasks)
    
    # Should have 10 users
    users = await test_db.get_active_users()
    assert len(users) == 10


@pytest.mark.asyncio
async def test_add_personal_details(test_db):
    """Test adding personal details for a user."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay"
    )
    
    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "AB123456",
        "email": "test@example.com",
    }
    
    details_id = await test_db.add_personal_details(user_id, details)
    assert details_id > 0
    
    # Get details back
    retrieved = await test_db.get_personal_details(user_id)
    assert retrieved is not None
    assert retrieved["first_name"] == "John"
    assert retrieved["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_add_appointment(test_db):
    """Test adding an appointment."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay"
    )
    
    appointment_id = await test_db.add_appointment(
        user_id=user_id,
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
        date="2024-12-25",
        time="10:00",
        reference="REF123456"
    )
    
    assert appointment_id > 0
    
    # Get appointments
    appointments = await test_db.get_appointments(user_id)
    assert len(appointments) == 1
    assert appointments[0]["reference_number"] == "REF123456"


@pytest.mark.asyncio
async def test_add_log(test_db):
    """Test adding log entries."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay"
    )
    
    await test_db.add_log("INFO", "Test log message", user_id)
    await test_db.add_log("ERROR", "Test error", user_id)
    
    logs = await test_db.get_logs(limit=10)
    assert len(logs) >= 2
