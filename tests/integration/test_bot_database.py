"""Integration tests for VFS bot database functionality."""

import asyncio

import pytest
import pytest_asyncio

from src.models.database import Database
from src.repositories import AppointmentRepository, AccountPoolRepository
from src.services.bot.vfs_bot import VFSBot
from src.services.notification.notification import NotificationService

# Add parent directory to path for imports


@pytest_asyncio.fixture
async def database():
    """Create a test database."""
    from src.constants import Database as DatabaseConfig

    test_db_url = DatabaseConfig.TEST_URL
    db = Database(database_url=test_db_url)

    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")

    yield db
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_connection(database):
    """Test database connection and table creation."""
    assert database.pool is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_user(database):
    """Test adding a user to database."""
    user_repo = AccountPoolRepository(database)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "testpass",
            "center_name": "Istanbul",
            "visa_category": "Schengen Visa",
            "visa_subcategory": "Tourism",
        }
    )
    assert user_id > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_active_users(database):
    """Test retrieving active users."""
    user_repo = AccountPoolRepository(database)
    await user_repo.create(
        {
            "email": "test@example.com",
            "password": "testpass",
            "center_name": "Istanbul",
            "visa_category": "Schengen Visa",
            "visa_subcategory": "Tourism",
        }
    )

    users = await user_repo.get_all_active()
    assert len(users) == 1
    assert users[0]["email"] == "test@example.com"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_personal_details(database):
    """Test adding personal details."""
    user_repo = AccountPoolRepository(database)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "testpass",
            "center_name": "Istanbul",
            "visa_category": "Schengen Visa",
            "visa_subcategory": "Tourism",
        }
    )

    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "AB123456",
        "email": "test@example.com",
    }

    details_id = await user_repo.add_personal_details(user_id, details)
    assert details_id > 0

    retrieved = await user_repo.get_personal_details(user_id)
    assert retrieved["first_name"] == "John"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_appointment(database):
    """Test adding an appointment."""
    user_repo = AccountPoolRepository(database)
    user_id = await user_repo.create(
        {
            "email": "test@example.com",
            "password": "testpass",
            "center_name": "Istanbul",
            "visa_category": "Schengen Visa",
            "visa_subcategory": "Tourism",
        }
    )

    appt_repo = AppointmentRepository(database)
    appointment_id = await appt_repo.create(
        {
            "user_id": user_id,
            "centre": "Istanbul",
            "category": "Schengen Visa",
            "subcategory": "Tourism",
            "appointment_date": "2024-01-15",
            "appointment_time": "10:00",
            "reference_number": "REF123",
        }
    )

    assert appointment_id > 0

    appointments = await appt_repo.get_by_user(user_id)
    assert len(appointments) == 1
    assert appointments[0].reference_number == "REF123"


@pytest.mark.integration
def test_bot_initialization(config):
    """Test bot initialization."""
    from src.constants import Database as DatabaseConfig

    db = Database(database_url=DatabaseConfig.TEST_URL)
    notifier = NotificationService(config["notifications"])
    bot = VFSBot(config, db, notifier)

    assert bot.config == config
    assert bot.running is False
