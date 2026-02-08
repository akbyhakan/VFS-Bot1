"""Pytest configuration and common fixtures."""

import os
import secrets
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

# Try to load test-specific environment file if it exists
test_env_file = Path(__file__).parent / ".env.test"
if test_env_file.exists():
    load_dotenv(test_env_file)

# Test constants - generate dynamically if not in .env.test
TEST_API_SECRET_KEY = os.getenv(
    "TEST_API_SECRET_KEY", secrets.token_urlsafe(48)  # Generate 64+ character key
)

# CRITICAL: Set environment variables BEFORE any src imports
# These must be set before importing any modules that check for them at import time
os.environ.setdefault("API_SECRET_KEY", TEST_API_SECRET_KEY)
os.environ.setdefault("ENV", "testing")

from cryptography.fernet import Fernet

if not os.getenv("ENCRYPTION_KEY"):
    # Generate a new encryption key for tests
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

# NOW it's safe to import from src
import pytest
import pytest_asyncio

from src.models.database import Database
from src.services.notification import NotificationService


def pytest_configure(config):
    """Configure pytest environment before tests run."""
    # Environment variables already set above, but ensure they're still set
    os.environ.setdefault("API_SECRET_KEY", TEST_API_SECRET_KEY)
    os.environ.setdefault("ENV", "testing")

    if not os.getenv("ENCRYPTION_KEY"):
        os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    # Set VFS_ENCRYPTION_KEY for VFS API tests
    if not os.getenv("VFS_ENCRYPTION_KEY"):
        os.environ["VFS_ENCRYPTION_KEY"] = secrets.token_urlsafe(32)

    # Set API_KEY_SALT for security tests
    if not os.getenv("API_KEY_SALT"):
        os.environ["API_KEY_SALT"] = secrets.token_urlsafe(32)

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
async def database():
    """
    Create a test database.
    
    Note: This fixture requires a PostgreSQL test database to be available.
    Set TEST_DATABASE_URL environment variable or it will use the default.
    """
    import os
    from src.constants import Database as DbConstants
    
    # Use test database URL from environment or default
    database_url = os.getenv("TEST_DATABASE_URL", DbConstants.TEST_URL)
    
    db = Database(database_url=database_url)
    await db.connect()
    yield db
    await db.close()


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
            "api_key": "test_dummy_key_not_real",
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
        "api_secret_key_min_length": 64,  # Updated from 32 to 64
        "encryption_key_required": True,
        "plaintext_password_allowed": False,
    }
