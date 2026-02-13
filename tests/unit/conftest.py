"""Pytest configuration for unit tests - minimal version."""

import os
import secrets
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

# Try to load test-specific environment file if it exists
test_env_file = Path(__file__).parent.parent / ".env.test"
if test_env_file.exists():
    load_dotenv(test_env_file)

# Test constants - generate dynamically if not in .env.test
TEST_API_SECRET_KEY = os.getenv(
    "TEST_API_SECRET_KEY", secrets.token_urlsafe(48)  # 48 bytes = ~64 chars when base64url-encoded
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

# NOW it's safe to import from src
import pytest
import pytest_asyncio


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
