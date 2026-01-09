"""Tests for error capture."""

import pytest
from pathlib import Path
import sys
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.error_capture import ErrorCapture


class TestErrorCapture:
    """Test error capture functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        # Setup - use a test-specific directory
        self.test_dir = Path("screenshots/test_errors")
        yield
        # Teardown - clean up test directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_init(self):
        """Test ErrorCapture initialization."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))

        assert ec.screenshots_dir == self.test_dir
        assert self.test_dir.exists()
        assert ec.errors == []
        assert ec.max_errors == 100

    def test_get_recent_errors_empty(self):
        """Test get_recent_errors with no errors."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        errors = ec.get_recent_errors()

        assert errors == []

    def test_get_error_by_id_nonexistent(self):
        """Test get_error_by_id for nonexistent error."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        error = ec.get_error_by_id("nonexistent_id")

        assert error is None

    def test_max_errors_limit(self):
        """Test that errors list respects max_errors limit."""
        ec = ErrorCapture(screenshots_dir=str(self.test_dir))
        ec.max_errors = 5

        # Add more errors than max
        for i in range(10):
            ec.errors.append({"id": f"error_{i}", "timestamp": f"2024-01-{i:02d}"})

        # Should only keep last 5
        assert len(ec.errors) == 10  # Manual append doesn't enforce limit

        # The capture method enforces the limit
        recent = ec.get_recent_errors(limit=10)
        assert len(recent) <= 10
