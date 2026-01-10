"""Tests for VFS bot functionality."""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.bot_service import VFSBot
from src.models.database import Database
from src.services.notification import NotificationService


@pytest_asyncio.fixture
async def database():
    """Create a test database."""
    db = Database("test.db")
    await db.connect()
    yield db
    await db.close()
    # Cleanup
    Path("test.db").unlink(missing_ok=True)


@pytest.fixture
def config():
    """Test configuration."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
            "centres": ["Istanbul"],
            "category": "Schengen Visa",
            "subcategory": "Tourism",
        },
        "credentials": {"email": "test@example.com", "password": "testpass"},
        "notifications": {"telegram": {"enabled": False}, "email": {"enabled": False}},
        "captcha": {"provider": "manual", "api_key": "", "manual_timeout": 10},
        "bot": {
            "check_interval": 5,
            "headless": True,
            "screenshot_on_error": False,
            "max_retries": 1,
        },
        "appointments": {"preferred_dates": [], "preferred_times": [], "random_selection": True},
    }


@pytest.mark.asyncio
async def test_database_connection(database):
    """Test database connection and table creation."""
    assert database.conn is not None


@pytest.mark.asyncio
async def test_add_user(database):
    """Test adding a user to database."""
    user_id = await database.add_user(
        email="test@example.com",
        password="testpass",
        centre="Istanbul",
        category="Schengen Visa",
        subcategory="Tourism",
    )
    assert user_id > 0


@pytest.mark.asyncio
async def test_get_active_users(database):
    """Test retrieving active users."""
    await database.add_user(
        email="test@example.com",
        password="testpass",
        centre="Istanbul",
        category="Schengen Visa",
        subcategory="Tourism",
    )

    users = await database.get_active_users()
    assert len(users) == 1
    assert users[0]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_add_personal_details(database):
    """Test adding personal details."""
    user_id = await database.add_user(
        email="test@example.com",
        password="testpass",
        centre="Istanbul",
        category="Schengen Visa",
        subcategory="Tourism",
    )

    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "AB123456",
        "email": "test@example.com",
    }

    details_id = await database.add_personal_details(user_id, details)
    assert details_id > 0

    retrieved = await database.get_personal_details(user_id)
    assert retrieved["first_name"] == "John"


@pytest.mark.asyncio
async def test_add_appointment(database):
    """Test adding an appointment."""
    user_id = await database.add_user(
        email="test@example.com",
        password="testpass",
        centre="Istanbul",
        category="Schengen Visa",
        subcategory="Tourism",
    )

    appointment_id = await database.add_appointment(
        user_id=user_id,
        centre="Istanbul",
        category="Schengen Visa",
        subcategory="Tourism",
        date="2024-01-15",
        time="10:00",
        reference="REF123",
    )

    assert appointment_id > 0

    appointments = await database.get_appointments(user_id)
    assert len(appointments) == 1
    assert appointments[0]["reference_number"] == "REF123"


def test_bot_initialization(config):
    """Test bot initialization."""
    db = Database("test.db")
    notifier = NotificationService(config["notifications"])
    bot = VFSBot(config, db, notifier)

    assert bot.config == config
    assert bot.running is False
