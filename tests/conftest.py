"""Pytest configuration and common fixtures."""

import os
import pytest
import pytest_asyncio
from pathlib import Path
import sys
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock
from cryptography.fernet import Fernet

# Set test environment variables before imports
os.environ["API_SECRET_KEY"] = "test-secret-key-for-testing-min-32-characters"


@pytest.fixture(autouse=True)
def setup_encryption_key(monkeypatch):
    """Automatically set ENCRYPTION_KEY for all tests if not already set."""
    if not os.getenv("ENCRYPTION_KEY"):
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
def config() -> Dict[str, Any]:
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
        "anti_detection": {"enabled": False},
    }


@pytest.fixture
def mock_page():
    """Mock Playwright page object."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.locator = MagicMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.select_option = AsyncMock()
    page.url = "https://visa.vfsglobal.com/tur/deu/en/login"
    page.screenshot = AsyncMock()
    page.close = AsyncMock()
    return page


@pytest.fixture
def mock_db():
    """Mock Database object."""
    db = AsyncMock()
    db.get_active_users = AsyncMock(return_value=[])
    db.get_personal_details = AsyncMock(return_value=None)
    db.add_appointment = AsyncMock(return_value=1)
    return db


@pytest.fixture
def mock_notifier():
    """Mock NotificationService object."""
    notifier = AsyncMock()
    notifier.notify_bot_started = AsyncMock()
    notifier.notify_bot_stopped = AsyncMock()
    notifier.notify_slot_found = AsyncMock()
    notifier.notify_booking_success = AsyncMock()
    notifier.notify_error = AsyncMock()
    return notifier
