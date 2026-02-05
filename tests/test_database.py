"""Tests for database operations with password encryption."""

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from src.models.database import Database
from src.utils.encryption import PasswordEncryption, reset_encryption


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test and reset global encryption instance."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # Reset global encryption instance to ensure it uses the new key
    reset_encryption()
    yield key
    # Cleanup: reset encryption instance after test
    reset_encryption()


@pytest.fixture
async def test_db(tmp_path, unique_encryption_key):
    """Create a test database."""
    db_path = tmp_path / "test_database.db"
    db = Database(str(db_path))
    await db.connect()
    yield db
    await db.close()
    # Cleanup is automatic with tmp_path


@pytest.mark.asyncio
async def test_add_user_encrypts_password(test_db, unique_encryption_key):
    """Test that add_user encrypts passwords."""
    email = "test@example.com"
    password = "MyPassword123"

    user_id = await test_db.add_user(
        email=email,
        password=password,
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
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
    enc = PasswordEncryption(unique_encryption_key)
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
        subcategory="Short Stay",
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
            subcategory="Short Stay",
        )

    # Get all users with decrypted passwords
    users = await test_db.get_active_users_with_decrypted_passwords()

    assert len(users) == 3

    # Check passwords are decrypted (order may vary)
    emails_and_passwords = {user["email"]: user["password"] for user in users}
    for email, password in users_data:
        assert emails_and_passwords[email] == password


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
            subcategory="Short Stay",
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
        subcategory="Short Stay",
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
        subcategory="Short Stay",
    )

    appointment_id = await test_db.add_appointment(
        user_id=user_id,
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay",
        date="2024-12-25",
        time="10:00",
        reference="REF123456",
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
        subcategory="Short Stay",
    )

    await test_db.add_log("INFO", "Test log message", user_id)
    await test_db.add_log("ERROR", "Test error", user_id)

    logs = await test_db.get_logs(limit=10)
    assert len(logs) >= 2


@pytest.mark.asyncio
async def test_create_appointment_request(test_db):
    """Test creating an appointment request."""
    persons = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "john@example.com",
            "is_child_with_parent": False,
        },
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "gender": "female",
            "nationality": "Turkey",
            "birth_date": "20/05/1992",
            "passport_number": "U87654321",
            "passport_issue_date": "01/01/2021",
            "passport_expiry_date": "01/01/2031",
            "phone_code": "90",
            "phone_number": "5559876543",
            "email": "jane@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await test_db.create_appointment_request(
        country_code="nld",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul", "Ankara"],
        preferred_dates=["15/02/2026", "16/02/2026"],
        person_count=2,
        persons=persons,
    )

    assert request_id > 0


@pytest.mark.asyncio
async def test_get_appointment_request(test_db):
    """Test getting an appointment request with persons."""
    persons = [
        {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "john@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await test_db.create_appointment_request(
        country_code="nld",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Get the request
    request = await test_db.get_appointment_request(request_id)

    assert request is not None
    assert request["id"] == request_id
    assert request["country_code"] == "nld"
    assert request["centres"] == ["Istanbul"]
    assert request["preferred_dates"] == ["15/02/2026"]
    assert request["person_count"] == 1
    assert request["status"] == "pending"
    assert len(request["persons"]) == 1
    assert request["persons"][0]["first_name"] == "John"


@pytest.mark.asyncio
async def test_get_all_appointment_requests(test_db):
    """Test getting all appointment requests."""
    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "test@example.com",
            "is_child_with_parent": False,
        },
    ]

    # Create multiple requests
    id1 = await test_db.create_appointment_request(
        country_code="nld",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    id2 = await test_db.create_appointment_request(
        country_code="aut",
        visa_category="Business",
        visa_subcategory="Conference",
        centres=["Ankara"],
        preferred_dates=["20/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Get all requests
    requests = await test_db.get_all_appointment_requests()

    assert len(requests) >= 2
    assert any(r["id"] == id1 for r in requests)
    assert any(r["id"] == id2 for r in requests)


@pytest.mark.asyncio
async def test_update_appointment_request_status(test_db):
    """Test updating appointment request status."""
    from datetime import datetime, timezone

    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "test@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await test_db.create_appointment_request(
        country_code="nld",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Update status
    completed_at = datetime.now(timezone.utc)
    updated = await test_db.update_appointment_request_status(
        request_id=request_id, status="completed", completed_at=completed_at
    )

    assert updated is True

    # Verify update
    request = await test_db.get_appointment_request(request_id)
    assert request["status"] == "completed"
    assert request["completed_at"] is not None


@pytest.mark.asyncio
async def test_delete_appointment_request(test_db):
    """Test deleting an appointment request."""
    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "test@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await test_db.create_appointment_request(
        country_code="nld",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Delete the request
    deleted = await test_db.delete_appointment_request(request_id)
    assert deleted is True

    # Verify it's deleted
    request = await test_db.get_appointment_request(request_id)
    assert request is None


@pytest.mark.asyncio
async def test_cleanup_completed_requests(test_db):
    """Test cleanup of old completed requests."""
    from datetime import datetime, timedelta, timezone

    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "test@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await test_db.create_appointment_request(
        country_code="nld",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Mark as completed with old timestamp (35 days ago)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)
    await test_db.update_appointment_request_status(
        request_id=request_id, status="completed", completed_at=old_date
    )

    # Run cleanup (30 days threshold)
    deleted_count = await test_db.cleanup_completed_requests(days=30)

    # Should have deleted 1 request
    assert deleted_count == 1

    # Verify it's deleted
    request = await test_db.get_appointment_request(request_id)
    assert request is None


@pytest.mark.asyncio
class TestTokenBlacklist:
    """Tests for token blacklist operations."""

    async def test_add_blacklisted_token(self, test_db):
        """Test adding a token to the blacklist."""
        from datetime import datetime, timedelta, timezone

        jti = "test-jti-12345"
        exp = datetime.now(timezone.utc) + timedelta(hours=1)

        await test_db.add_blacklisted_token(jti, exp)

        # Verify it's blacklisted
        is_blacklisted = await test_db.is_token_blacklisted(jti)
        assert is_blacklisted is True

    async def test_is_token_blacklisted_returns_false_for_non_blacklisted(self, test_db):
        """Test that non-blacklisted tokens return False."""
        is_blacklisted = await test_db.is_token_blacklisted("non-existent-jti")
        assert is_blacklisted is False

    async def test_expired_token_not_blacklisted(self, test_db):
        """Test that expired tokens are not considered blacklisted."""
        from datetime import datetime, timedelta, timezone

        jti = "expired-jti"
        exp = datetime.now(timezone.utc) - timedelta(hours=1)  # Already expired

        await test_db.add_blacklisted_token(jti, exp)

        # Should not be blacklisted because it's expired
        is_blacklisted = await test_db.is_token_blacklisted(jti)
        assert is_blacklisted is False

    async def test_get_active_blacklisted_tokens(self, test_db):
        """Test getting all active blacklisted tokens."""
        from datetime import datetime, timedelta, timezone

        # Add active tokens
        active_tokens = []
        for i in range(3):
            jti = f"active-jti-{i}"
            exp = datetime.now(timezone.utc) + timedelta(hours=i + 1)
            await test_db.add_blacklisted_token(jti, exp)
            active_tokens.append(jti)

        # Add expired token
        expired_jti = "expired-jti"
        expired_exp = datetime.now(timezone.utc) - timedelta(hours=1)
        await test_db.add_blacklisted_token(expired_jti, expired_exp)

        # Get active tokens
        tokens = await test_db.get_active_blacklisted_tokens()

        # Should only get active tokens
        assert len(tokens) == 3
        token_jtis = [t[0] for t in tokens]
        for jti in active_tokens:
            assert jti in token_jtis
        assert expired_jti not in token_jtis

    async def test_cleanup_expired_tokens(self, test_db):
        """Test cleanup of expired tokens."""
        from datetime import datetime, timedelta, timezone

        # Add expired tokens
        for i in range(3):
            jti = f"expired-jti-{i}"
            exp = datetime.now(timezone.utc) - timedelta(hours=i + 1)
            await test_db.add_blacklisted_token(jti, exp)

        # Add active token
        active_jti = "active-jti"
        active_exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await test_db.add_blacklisted_token(active_jti, active_exp)

        # Run cleanup
        deleted_count = await test_db.cleanup_expired_tokens()

        # Should have deleted 3 expired tokens
        assert deleted_count == 3

        # Active token should still be there
        is_blacklisted = await test_db.is_token_blacklisted(active_jti)
        assert is_blacklisted is True


@pytest.mark.asyncio
class TestDatabasePoolExhaustion:
    """Tests for database connection pool exhaustion."""

    async def test_connection_pool_exhaustion(self, tmp_path, unique_encryption_key):
        """Test behavior when connection pool is exhausted."""
        import asyncio

        from src.core.exceptions import DatabasePoolTimeoutError

        db_path = tmp_path / "test_pool.db"
        db = Database(str(db_path), pool_size=2)
        await db.connect()

        try:
            # Hold all connections
            async def hold_connection():
                async with db.get_connection(timeout=1.0):
                    await asyncio.sleep(2.0)

            # Start tasks to hold all connections
            tasks = [asyncio.create_task(hold_connection()) for _ in range(2)]
            await asyncio.sleep(0.1)  # Let tasks acquire connections

            # Try to get another connection - should timeout
            with pytest.raises(DatabasePoolTimeoutError):
                async with db.get_connection(timeout=0.5):
                    pass

            # Cancel holding tasks
            for task in tasks:
                task.cancel()

            # Wait for cancellation
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await db.close()

    async def test_health_check_passes(self, test_db):
        """Test that health check passes on healthy database."""
        result = await test_db.health_check()
        assert result is True
