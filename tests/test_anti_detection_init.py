"""Tests for anti_detection module lazy imports."""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAntiDetectionLazyImports:
    """Test anti_detection module lazy import functionality."""

    def test_import_cloudflare_handler(self):
        """Test lazy import of CloudflareHandler."""
        from src.utils.anti_detection import CloudflareHandler

        assert CloudflareHandler is not None
        assert CloudflareHandler.__name__ == "CloudflareHandler"

    def test_import_fingerprint_bypass(self):
        """Test lazy import of FingerprintBypass."""
        from src.utils.anti_detection import FingerprintBypass

        assert FingerprintBypass is not None
        assert FingerprintBypass.__name__ == "FingerprintBypass"

    def test_import_human_simulator(self):
        """Test lazy import of HumanSimulator."""
        from src.utils.anti_detection import HumanSimulator

        assert HumanSimulator is not None
        assert HumanSimulator.__name__ == "HumanSimulator"

    def test_import_stealth_config(self):
        """Test lazy import of StealthConfig."""
        from src.utils.anti_detection import StealthConfig

        assert StealthConfig is not None
        assert StealthConfig.__name__ == "StealthConfig"

    def test_import_tls_handler(self):
        """Test lazy import of TLSHandler."""
        from src.utils.anti_detection import TLSHandler

        assert TLSHandler is not None
        assert TLSHandler.__name__ == "TLSHandler"

    def test_import_invalid_attribute(self):
        """Test importing invalid attribute raises AttributeError."""
        import src.utils.anti_detection

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = src.utils.anti_detection.InvalidAttribute

    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from src.utils.anti_detection import __all__

        expected = [
            "CloudflareHandler",
            "FingerprintBypass",
            "HumanSimulator",
            "StealthConfig",
            "TLSHandler",
        ]
        assert set(__all__) == set(expected)

    def test_tls_handler_instantiation(self):
        """Test TLSHandler can be instantiated after import."""
        from src.utils.anti_detection import TLSHandler

        handler = TLSHandler()
        assert handler is not None

    def test_stealth_config_instantiation(self):
        """Test StealthConfig can be instantiated after import."""
        from src.utils.anti_detection import StealthConfig

        config = StealthConfig()
        assert config is not None

    def test_fingerprint_bypass_instantiation(self):
        """Test FingerprintBypass can be instantiated after import."""
        from src.utils.anti_detection import FingerprintBypass

        bypass = FingerprintBypass()
        assert bypass is not None
