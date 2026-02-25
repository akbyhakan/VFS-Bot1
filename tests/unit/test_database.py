"""Tests for database operations with password encryption."""

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from src.models.database import Database
from src.repositories import (
    AppointmentRepository,
    AppointmentRequestRepository,
    LogRepository,
    TokenBlacklistRepository,
    AccountPoolRepository,
)
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
    from src.constants import Database as DatabaseConfig

    # Use PostgreSQL test database URL
    test_db_url = DatabaseConfig.TEST_URL
    db = Database(database_url=test_db_url)

    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")

    # Setup: ensure clean state before test
    try:
        async with db.get_connection() as conn:
            await conn.execute("""
                TRUNCATE TABLE appointment_persons, appointment_requests, appointments,
                personal_details, token_blacklist, audit_log, logs, payment_card,
                user_webhooks, users RESTART IDENTITY CASCADE
            """)
    except Exception:
        pass

    yield db

    # Teardown: clean up after test
    try:
        async with db.get_connection() as conn:
            await conn.execute("""
                TRUNCATE TABLE appointment_persons, appointment_requests, appointments,
                personal_details, token_blacklist, audit_log, logs, payment_card,
                user_webhooks, users RESTART IDENTITY CASCADE
            """)
    except Exception:
        pass
    await db.close()


@pytest.mark.asyncio
async def test_add_user_encrypts_password(test_db, unique_encryption_key):
    """Test that add_user encrypts passwords."""
    email = "test@example.com"
    password = "MyPassword123"

    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": email,
            "password": password,
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    assert user_id > 0

    # Get user from database
    users = await user_repo.get_all_active()
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

    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": email,
            "password": password,
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Get user with decrypted password
    user = await user_repo.get_by_id_with_password(user_id)

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

    user_repo = AccountPoolRepository(test_db)
    for email, password in users_data:
        await user_repo.create(
            {
                "email": email,
                "password": password,
                "center_name": "Istanbul",
                "visa_category": "Tourism",
                "visa_subcategory": "Short Stay",
            }
        )

    # Get all users with decrypted passwords
    users = await user_repo.get_all_active_with_passwords()

    assert len(users) == 3

    # Check passwords are decrypted (order may vary)
    emails_and_passwords = {user["email"]: user["password"] for user in users}
    for email, password in users_data:
        assert emails_and_passwords[email] == password


@pytest.mark.asyncio
async def test_connection_pooling(test_db):
    """Test that connection pooling works."""
    # Connection pool should be initialized
    assert test_db.pool is not None

    # Should be able to get connections
    async with test_db.get_connection() as conn:
        assert conn is not None


@pytest.mark.asyncio
async def test_concurrent_database_operations(test_db):
    """Test concurrent database operations with connection pool."""
    import asyncio

    user_repo = AccountPoolRepository(test_db)

    async def add_user(i):
        await user_repo.create(
            {
                "email": f"user{i}@example.com",
                "password": f"password{i}",
                "center_name": "Istanbul",
                "visa_category": "Tourism",
                "visa_subcategory": "Short Stay",
            }
        )

    # Add 10 users concurrently
    tasks = [add_user(i) for i in range(10)]
    await asyncio.gather(*tasks)

    # Should have 10 users
    users = await user_repo.get_all_active()
    assert len(users) == 10


@pytest.mark.asyncio
async def test_add_personal_details(test_db):
    """Test adding personal details for a user."""
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "password",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "AB123456",
        "email": "test@example.com",
    }

    details_id = await AccountPoolRepository(test_db).add_personal_details(user_id, details)
    assert details_id > 0

    # Get details back
    retrieved = await AccountPoolRepository(test_db).get_personal_details(user_id)
    assert retrieved is not None
    assert retrieved["first_name"] == "John"
    assert retrieved["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_add_appointment(test_db):
    """Test adding an appointment."""
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "password",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    appointment_repo = AppointmentRepository(test_db)
    appointment_id = await appointment_repo.create(
        {
            "user_id": user_id,
            "centre": "Istanbul",
            "category": "Tourism",
            "subcategory": "Short Stay",
            "appointment_date": "2024-12-25",
            "appointment_time": "10:00",
            "reference_number": "REF123456",
        }
    )

    assert appointment_id > 0

    # Get appointments
    appointments = [a.to_dict() for a in await AppointmentRepository(test_db).get_by_user(user_id)]
    assert len(appointments) == 1
    assert appointments[0]["reference_number"] == "REF123456"


@pytest.mark.asyncio
async def test_add_log(test_db):
    """Test adding log entries."""
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "password",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    await LogRepository(test_db).create(
        {"level": "INFO", "message": "Test log message", "user_id": user_id}
    )
    await LogRepository(test_db).create(
        {"level": "ERROR", "message": "Test error", "user_id": user_id}
    )

    logs = await LogRepository(test_db).get_all(limit=10)
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

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul", "Ankara"],
            "preferred_dates": ["15/02/2026", "16/02/2026"],
            "person_count": 2,
            "persons": persons,
        }
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

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Get the request
    entity = await AppointmentRequestRepository(test_db).get_by_id(request_id)
    request = entity.to_dict() if entity else None

    assert request is not None
    assert request["id"] == request_id
    assert request["country_code"] == "nld"
    assert request["centres"] == ["Istanbul"]
    assert request["preferred_dates"] == ["15/02/2026"]
    assert request["person_count"] == 1
    assert request["status"] == "pending"
    assert len(request["persons"]) == 1
    assert request["persons"][0]["first_name"] == "John"
    assert request["booked_date"] is None


@pytest.mark.asyncio
async def test_update_appointment_request_booked_date(test_db):
    """Test updating appointment request status to booked with booked_date."""
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

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Update status to booked with booked_date
    updated = await AppointmentRequestRepository(test_db).update_status(
        request_id, "booked", booked_date="15/02/2026"
    )

    assert updated is True

    # Verify booked_date is stored
    entity = await AppointmentRequestRepository(test_db).get_by_id(request_id)
    request = entity.to_dict() if entity else None
    assert request is not None
    assert request["status"] == "booked"
    assert request["booked_date"] == "15/02/2026"


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
    id1 = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    id2 = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "aut",
            "visa_category": "Business",
            "visa_subcategory": "Conference",
            "centres": ["Ankara"],
            "preferred_dates": ["20/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Get all requests
    requests = [r.to_dict() for r in await AppointmentRequestRepository(test_db).get_all()]

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

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Update status
    completed_at = datetime.now(timezone.utc)
    updated = await AppointmentRequestRepository(test_db).update_status(
        request_id, "completed", completed_at=completed_at
    )

    assert updated is True

    # Verify update
    entity = await AppointmentRequestRepository(test_db).get_by_id(request_id)
    request = entity.to_dict() if entity else None
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

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Delete the request
    deleted = await AppointmentRequestRepository(test_db).delete(request_id)
    assert deleted is True

    # Verify it's deleted
    entity = await AppointmentRequestRepository(test_db).get_by_id(request_id)
    request = entity.to_dict() if entity else None
    assert request is None


@pytest.mark.asyncio
async def test_get_pending_appointment_request_for_user(test_db):
    """Test getting pending appointment request for a user by email."""
    # Create a user
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "testuser@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Create an appointment request with the user's email
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
            "email": "testuser@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Get the request by user
    entity = await AppointmentRequestRepository(test_db).get_pending_for_user(user_id)
    request = entity.to_dict() if entity else None

    assert request is not None
    assert request["id"] == request_id
    assert request["status"] == "pending"
    assert len(request["persons"]) == 1
    assert request["persons"][0]["email"] == "testuser@example.com"


@pytest.mark.asyncio
async def test_get_pending_appointment_request_for_user_multi_person(test_db):
    """Test getting pending appointment request with multiple persons."""
    # Create a user
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "mainuser@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Create an appointment request with multiple persons
    persons = [
        {
            "first_name": "Main",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "mainuser@example.com",
            "is_child_with_parent": False,
        },
        {
            "first_name": "Second",
            "last_name": "Person",
            "gender": "female",
            "nationality": "Turkey",
            "birth_date": "20/05/1992",
            "passport_number": "U87654321",
            "passport_issue_date": "01/01/2021",
            "passport_expiry_date": "01/01/2031",
            "phone_code": "90",
            "phone_number": "5559876543",
            "email": "second@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul", "Ankara"],
            "preferred_dates": ["15/02/2026", "16/02/2026"],
            "person_count": 2,
            "persons": persons,
        }
    )

    # Get the request by user
    entity = await AppointmentRequestRepository(test_db).get_pending_for_user(user_id)
    request = entity.to_dict() if entity else None

    assert request is not None
    assert request["id"] == request_id
    assert request["person_count"] == 2
    assert len(request["persons"]) == 2
    assert request["persons"][0]["email"] == "mainuser@example.com"
    assert request["persons"][1]["email"] == "second@example.com"


@pytest.mark.asyncio
async def test_get_pending_appointment_request_for_user_no_request(test_db):
    """Test getting pending appointment request when none exists."""
    # Create a user
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "noappointment@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # No appointment request created
    entity = await AppointmentRequestRepository(test_db).get_pending_for_user(user_id)
    request = entity.to_dict() if entity else None

    assert request is None


@pytest.mark.asyncio
async def test_get_pending_appointment_request_for_user_completed_status(test_db):
    """Test that completed requests are not returned."""
    # Create a user
    user_repo = AccountPoolRepository(test_db)
    user_id = await user_repo.create(
        {
            "email": "completed@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Create an appointment request
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
            "email": "completed@example.com",
            "is_child_with_parent": False,
        },
    ]

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Mark as completed
    await AppointmentRequestRepository(test_db).update_status(request_id, "completed")

    # Should not return completed request
    entity = await AppointmentRequestRepository(test_db).get_pending_for_user(user_id)
    request = entity.to_dict() if entity else None

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

    request_id = await AppointmentRequestRepository(test_db).create(
        {
            "country_code": "nld",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
            "centres": ["Istanbul"],
            "preferred_dates": ["15/02/2026"],
            "person_count": 1,
            "persons": persons,
        }
    )

    # Mark as completed with old timestamp (35 days ago)
    old_date = datetime.now(timezone.utc) - timedelta(days=35)
    await AppointmentRequestRepository(test_db).update_status(
        request_id, "completed", completed_at=old_date
    )

    # Run cleanup (30 days threshold)
    deleted_count = await AppointmentRequestRepository(test_db).cleanup_completed(days=30)

    # Should have deleted 1 request
    assert deleted_count == 1

    # Verify it's deleted
    entity = await AppointmentRequestRepository(test_db).get_by_id(request_id)
    request = entity.to_dict() if entity else None
    assert request is None


@pytest.mark.asyncio
class TestTokenBlacklist:
    """Tests for token blacklist operations."""

    async def test_add_blacklisted_token(self, test_db):
        """Test adding a token to the blacklist."""
        from datetime import datetime, timedelta, timezone

        jti = "test-jti-12345"
        exp = datetime.now(timezone.utc) + timedelta(hours=1)

        await TokenBlacklistRepository(test_db).add(jti, exp)

        # Verify it's blacklisted
        is_blacklisted = await TokenBlacklistRepository(test_db).is_blacklisted(jti)
        assert is_blacklisted is True

    async def test_is_token_blacklisted_returns_false_for_non_blacklisted(self, test_db):
        """Test that non-blacklisted tokens return False."""
        is_blacklisted = await TokenBlacklistRepository(test_db).is_blacklisted("non-existent-jti")
        assert is_blacklisted is False

    async def test_expired_token_not_blacklisted(self, test_db):
        """Test that expired tokens are not considered blacklisted."""
        from datetime import datetime, timedelta, timezone

        jti = "expired-jti"
        exp = datetime.now(timezone.utc) - timedelta(hours=1)  # Already expired

        await TokenBlacklistRepository(test_db).add(jti, exp)

        # Should not be blacklisted because it's expired
        is_blacklisted = await TokenBlacklistRepository(test_db).is_blacklisted(jti)
        assert is_blacklisted is False

    async def test_get_active_blacklisted_tokens(self, test_db):
        """Test getting all active blacklisted tokens."""
        from datetime import datetime, timedelta, timezone

        # Add active tokens
        active_tokens = []
        for i in range(3):
            jti = f"active-jti-{i}"
            exp = datetime.now(timezone.utc) + timedelta(hours=i + 1)
            await TokenBlacklistRepository(test_db).add(jti, exp)
            active_tokens.append(jti)

        # Add expired token
        expired_jti = "expired-jti"
        expired_exp = datetime.now(timezone.utc) - timedelta(hours=1)
        await TokenBlacklistRepository(test_db).add(expired_jti, expired_exp)

        # Get active tokens
        tokens = await TokenBlacklistRepository(test_db).get_active()

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
            await TokenBlacklistRepository(test_db).add(jti, exp)

        # Add active token
        active_jti = "active-jti"
        active_exp = datetime.now(timezone.utc) + timedelta(hours=1)
        await TokenBlacklistRepository(test_db).add(active_jti, active_exp)

        # Run cleanup
        deleted_count = await TokenBlacklistRepository(test_db).cleanup_expired()

        # Should have deleted 3 expired tokens
        assert deleted_count == 3

        # Active token should still be there
        is_blacklisted = await TokenBlacklistRepository(test_db).is_blacklisted(active_jti)
        assert is_blacklisted is True


@pytest.mark.asyncio
class TestDatabasePoolExhaustion:
    """Tests for database connection pool exhaustion."""

    @pytest.mark.integration
    async def test_connection_pool_exhaustion(self, unique_encryption_key):
        """Test behavior when connection pool is exhausted."""
        import asyncio

        from src.constants import Database as DatabaseConfig
        from src.core.exceptions import DatabasePoolTimeoutError

        # Use PostgreSQL test database with small pool
        test_db_url = DatabaseConfig.TEST_URL
        db = Database(database_url=test_db_url, pool_size=2)

        try:
            await db.connect()
        except Exception as e:
            pytest.skip(f"PostgreSQL test database not available: {e}")

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

        # Verify failure counter is reset
        assert test_db._consecutive_failures == 0

    async def test_health_check_resets_degraded_state(self, test_db):
        """Test that health_check resets degraded state on successful check."""
        # Simulate degraded state by setting consecutive failures
        test_db._consecutive_failures = 5
        initial_state = test_db.state
        assert initial_state == "degraded"  # Should be in degraded state

        # Run health check - should reset the failure counter
        result = await test_db.health_check()
        assert result is True

        # Verify state is restored to CONNECTED
        assert test_db._consecutive_failures == 0
        assert test_db.state == "connected"

        # Verify last successful query timestamp was updated
        from datetime import datetime, timezone

        assert test_db._last_successful_query is not None
        # Should be recent (within last few seconds)
        time_diff = (datetime.now(timezone.utc) - test_db._last_successful_query).total_seconds()
        assert time_diff < 5


@pytest.mark.asyncio
async def test_close_sets_pool_to_none(tmp_path, unique_encryption_key):
    """Test that close() sets pool to None and state to disconnected."""
    from src.constants import Database as DatabaseConfig

    test_db_url = DatabaseConfig.TEST_URL
    db = Database(database_url=test_db_url)

    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")

    # Verify connected state
    assert db.state == "connected"
    assert db.pool is not None

    # Close the database
    await db.close()

    # Verify pool is None and state is disconnected
    assert db.pool is None
    assert db.state == "disconnected"


@pytest.mark.asyncio
async def test_pool_stats_method():
    """Test get_pool_stats method returns correct structure."""
    from src.constants import Database as DatabaseConfig
    from src.models.db_connection import DatabaseConnectionManager

    test_db_url = DatabaseConfig.TEST_URL
    db = DatabaseConnectionManager(database_url=test_db_url)

    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")

    try:
        # Get pool stats
        stats = db.get_pool_stats()

        # Verify structure
        assert "pool_size" in stats
        assert "pool_free" in stats
        assert "pool_used" in stats
        assert "utilization" in stats

        # Verify types
        assert isinstance(stats["pool_size"], int)
        assert isinstance(stats["pool_free"], int)
        assert isinstance(stats["pool_used"], int)
        assert isinstance(stats["utilization"], (int, float))

        # Verify ranges
        assert stats["pool_size"] > 0
        assert stats["pool_free"] >= 0
        assert stats["pool_used"] >= 0
        assert 0.0 <= stats["utilization"] <= 1.0

        # Verify consistency
        assert stats["pool_used"] + stats["pool_free"] <= stats["pool_size"]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_pool_stats_without_connection():
    """Test get_pool_stats when pool is not connected."""
    from src.models.db_connection import DatabaseConnectionManager

    db = DatabaseConnectionManager(
        database_url="postgresql://test:test@localhost/test", pool_size=10
    )

    # Get stats before connecting
    stats = db.get_pool_stats()

    # Should return the configured pool size but zero usage
    assert stats["pool_size"] == 10  # Should match configured size
    assert stats["pool_free"] == 0
    assert stats["pool_used"] == 0
    assert stats["utilization"] == 0.0
