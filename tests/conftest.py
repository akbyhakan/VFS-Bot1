"""Pytest configuration and common fixtures."""

import os
import sys
import warnings
from pathlib import Path

# Test constants
TEST_API_SECRET_KEY = "test-secret-key-for-testing-minimum-32-characters-long"

# CRITICAL: Set environment variables BEFORE any src imports
# These must be set before importing any modules that check for them at import time
os.environ.setdefault("API_SECRET_KEY", TEST_API_SECRET_KEY)

from cryptography.fernet import Fernet

if not os.getenv("ENCRYPTION_KEY"):
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# NOW it's safe to import from src
import pytest
import pytest_asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

from src.models.database import Database
from src.services.notification import NotificationService


def pytest_configure(config):
    """Configure pytest environment before tests run."""
    # Environment variables already set above, but ensure they're still set
    os.environ.setdefault("API_SECRET_KEY", TEST_API_SECRET_KEY)
    if not os.getenv("ENCRYPTION_KEY"):
        os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    # Set VFS_ENCRYPTION_KEY for VFS API tests
    if not os.getenv("VFS_ENCRYPTION_KEY"):
        import secrets
        os.environ["VFS_ENCRYPTION_KEY"] = secrets.token_urlsafe(32)

    # Suppress async mock warnings
    warnings.filterwarnings("ignore", message="coroutine.*was never awaited")
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=pytest.PytestUnraisableExceptionWarning)


@pytest.fixture(scope="session")
def session_encryption_key():
    """Session-scoped encryption key for tests."""
    return os.getenv("ENCRYPTION_KEY")


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Automatically set up test environment for all tests."""
    # Ensure ENCRYPTION_KEY is set
    if not os.getenv("ENCRYPTION_KEY"):
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)

    # Suppress async-related warnings during tests
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        warnings.filterwarnings("ignore", message=".*was never awaited.*")
        yield
    # Cleanup after test if needed


@pytest_asyncio.fixture
async def database(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    await db.connect()
    yield db
    await db.close()
    # Cleanup is automatic with tmp_path


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
        "captcha": {
            "api_key": "dd22eca10ee02b8bfcb0a991ea2099dd",
            "manual_timeout": 10,
        },
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


@pytest.fixture
def security_config():
    """Security-focused test configuration."""
    return {
        "api_secret_key_min_length": 32,
        "encryption_key_required": True,
        "plaintext_password_allowed": False,
    }
