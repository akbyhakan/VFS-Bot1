"""Tests for models module lazy imports."""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModelsLazyImports:
    """Test models module lazy import functionality."""

    def test_import_database(self):
        """Test lazy import of Database."""
        from src.models import Database

        assert Database is not None
        assert Database.__name__ == "Database"

    def test_import_user_create(self):
        """Test lazy import of UserCreate."""
        from src.models import UserCreate

        assert UserCreate is not None

    def test_import_user_response(self):
        """Test lazy import of UserResponse."""
        from src.models import UserResponse

        assert UserResponse is not None

    def test_import_appointment_create(self):
        """Test lazy import of AppointmentCreate."""
        from src.models import AppointmentCreate

        assert AppointmentCreate is not None

    def test_import_appointment_response(self):
        """Test lazy import of AppointmentResponse."""
        from src.models import AppointmentResponse

        assert AppointmentResponse is not None

    def test_import_bot_config(self):
        """Test lazy import of BotConfig."""
        from src.models import BotConfig

        assert BotConfig is not None

    def test_import_notification_config(self):
        """Test lazy import of NotificationConfig."""
        from src.models import NotificationConfig

        assert NotificationConfig is not None

    def test_import_invalid_attribute(self):
        """Test importing invalid attribute raises AttributeError."""
        import src.models

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = src.models.InvalidAttribute

    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from src.models import __all__

        expected = [
            "Database",
            "UserCreate",
            "UserResponse",
            "AppointmentCreate",
            "AppointmentResponse",
            "BotConfig",
            "NotificationConfig",
        ]
        assert set(__all__) == set(expected)
