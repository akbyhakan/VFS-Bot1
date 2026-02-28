"""Tests for ErrorHandler checkpoint security."""

import json
import os
from pathlib import Path

import pytest

from src.services.bot.error_handler import ErrorHandler


class TestErrorHandlerCheckpointSecurity:
    """Tests verifying checkpoint security fixes."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create ErrorHandler with a temp directory."""
        return ErrorHandler(
            screenshots_dir=str(tmp_path / "screenshots"),
            checkpoint_dir=str(tmp_path / "data"),
        )

    @pytest.mark.asyncio
    async def test_save_checkpoint_masks_sensitive_data(self, handler):
        """Sensitive keys are masked and non-sensitive keys are preserved."""
        state = {"token": "secret123", "running": True}
        checkpoint_file = await handler.save_checkpoint(state)

        assert checkpoint_file is not None
        with open(checkpoint_file, "r") as f:
            data = json.load(f)

        assert data["token"] == "********"
        assert data["running"] is True

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.name == "nt", reason="File permissions not enforced on Windows")
    async def test_save_checkpoint_file_permissions(self, handler):
        """Checkpoint file must be owner-read/write only (0o600)."""
        checkpoint_file = await handler.save_checkpoint({"running": True})

        assert checkpoint_file is not None
        mode = os.stat(checkpoint_file).st_mode & 0o777
        assert mode == 0o600
