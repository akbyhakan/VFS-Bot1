"""Tests for services module lazy imports."""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestServicesLazyImports:
    """Test services module lazy import functionality."""

    def test_import_vfs_bot(self):
        """Test lazy import of VFSBot."""
        from src.services import VFSBot

        assert VFSBot is not None
        assert VFSBot.__name__ == "VFSBot"

    def test_import_captcha_solver(self):
        """Test lazy import of CaptchaSolver."""
        from src.services import CaptchaSolver

        assert CaptchaSolver is not None
        assert CaptchaSolver.__name__ == "CaptchaSolver"

    def test_import_captcha_provider(self):
        """Test lazy import of CaptchaProvider."""
        from src.services import CaptchaProvider

        assert CaptchaProvider is not None
        assert CaptchaProvider.__name__ == "CaptchaProvider"

    def test_import_centre_fetcher(self):
        """Test lazy import of CentreFetcher."""
        from src.services import CentreFetcher

        assert CentreFetcher is not None
        assert CentreFetcher.__name__ == "CentreFetcher"

    def test_import_notification_service(self):
        """Test lazy import of NotificationService."""
        from src.services import NotificationService

        assert NotificationService is not None
        assert NotificationService.__name__ == "NotificationService"

    def test_import_invalid_attribute(self):
        """Test importing invalid attribute raises AttributeError."""
        import src.services

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = src.services.InvalidAttribute

    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from src.services import __all__

        expected = [
            "VFSBot",
            "CaptchaSolver",
            "CaptchaProvider",
            "CentreFetcher",
            "NotificationService",
        ]
        assert set(__all__) == set(expected)
