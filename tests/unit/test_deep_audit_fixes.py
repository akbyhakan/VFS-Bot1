"""Tests for deep logical and runtime audit fixes.

Covers:
- selector_utils: Silent failure logging
- booking_validator: Safe dict access for reservation data
- runners: Safe dict access for start_result
- bot_controller: Safe dict access for stop_result in restart_bot
- audit_logger: Non-blocking async file write
- secure_memory: Logging on ctypes fallback
- encryption: Logging on unexpected errors in can_decrypt/needs_migration
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── selector_utils: Silent failure now logs ──────────────────────────────────


class TestSelectorUtilsLogging:
    """Test that selector resolution failures are logged instead of silently swallowed."""

    def test_resolve_selector_logs_on_exception(self):
        """Exception in manager.get_all() should be logged at debug level."""
        mock_manager = MagicMock()
        mock_manager.get_all.side_effect = RuntimeError("selector store unavailable")

        with (
            patch(
                "src.services.booking.selector_utils.get_selector_manager",
                return_value=mock_manager,
            ),
            patch("src.services.booking.selector_utils.logger") as mock_logger,
        ):
            from src.services.booking.selector_utils import resolve_selector

            result = resolve_selector("first_name")

            # Should fallback to original key
            assert result == ["first_name"]
            # Should have logged the error at debug level
            mock_logger.debug.assert_called_once()
            assert "selector store unavailable" in mock_logger.debug.call_args[0][0]


# ── booking_validator: Safe dict access ──────────────────────────────────────


class TestBookingValidatorSafeDictAccess:
    """Test that missing reservation keys return error dict instead of KeyError."""

    @pytest.mark.asyncio
    async def test_check_double_match_missing_person_count(self):
        """Missing person_count should return error result, not raise KeyError."""
        from src.services.booking.booking_validator import BookingValidator

        validator = BookingValidator()
        mock_page = AsyncMock()

        reservation = {"preferred_dates": ["01/01/2025"]}  # Missing person_count
        result = await validator.check_double_match(mock_page, reservation)

        assert result["match"] is False
        assert "person_count" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_check_double_match_missing_preferred_dates(self):
        """Missing preferred_dates should return error result, not raise KeyError."""
        from src.services.booking.booking_validator import BookingValidator

        validator = BookingValidator()
        mock_page = AsyncMock()

        reservation = {"person_count": 2}  # Missing preferred_dates
        result = await validator.check_double_match(mock_page, reservation)

        assert result["match"] is False
        assert "preferred_dates" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_check_double_match_empty_reservation(self):
        """Empty reservation dict should return error result, not raise KeyError."""
        from src.services.booking.booking_validator import BookingValidator

        validator = BookingValidator()
        mock_page = AsyncMock()

        result = await validator.check_double_match(mock_page, {})

        assert result["match"] is False


# ── bot_controller: Safe dict access in restart_bot ──────────────────────────


class TestBotControllerSafeDictAccess:
    """Test restart_bot handles missing dict keys gracefully."""

    @pytest.mark.asyncio
    async def test_restart_bot_handles_unexpected_stop_result(self):
        """restart_bot should not crash if stop_result has unexpected structure."""
        from src.core.bot_controller import BotController

        await BotController.reset_instance()
        controller = await BotController.get_instance()
        controller._configured = True

        # Mock stop_bot to return dict without expected keys
        controller.stop_bot = AsyncMock(return_value={})
        controller.start_bot = AsyncMock(
            return_value={"status": "success", "message": "Bot started"}
        )

        # Should not raise KeyError
        result = await controller.restart_bot()
        assert result["status"] == "success"
        await BotController.reset_instance()

    @pytest.mark.asyncio
    async def test_restart_bot_handles_stop_error_without_message(self):
        """restart_bot should handle stop error result missing 'message' key."""
        from src.core.bot_controller import BotController

        await BotController.reset_instance()
        controller = await BotController.get_instance()
        controller._configured = True

        # Mock stop_bot to return error without message key
        controller.stop_bot = AsyncMock(return_value={"status": "error"})
        controller.start_bot = AsyncMock(
            return_value={"status": "success", "message": "Bot started"}
        )

        # Should not raise KeyError - missing 'message' defaults to ""
        result = await controller.restart_bot()
        # stop_result has status "error" and message defaults to "" which doesn't
        # contain "not running", so it returns the stop_result
        assert result["status"] == "error"
        await BotController.reset_instance()


# ── audit_logger: Non-blocking async file write ─────────────────────────────


class TestAuditLoggerNonBlockingWrite:
    """Test that audit logger file writes are non-blocking."""

    @pytest.mark.asyncio
    async def test_write_to_file_uses_asyncio_to_thread(self):
        """_write_to_file should delegate to asyncio.to_thread."""
        from src.utils.audit_logger import AuditEntry, AuditLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            audit_logger = AuditLogger(log_file=str(log_path))

            entry = AuditEntry(
                action="test_action",
                user_id=1,
                username="testuser",
                ip_address="127.0.0.1",
                user_agent="test",
                details={},
                timestamp="2025-01-01T00:00:00",
            )

            with patch("src.utils.audit_logger.asyncio.to_thread", new_callable=AsyncMock) as mock:
                mock.return_value = None
                await audit_logger._write_to_file(entry)
                mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_file_actually_writes(self):
        """_write_to_file should successfully write entry to disk."""
        from src.utils.audit_logger import AuditEntry, AuditLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            audit_logger = AuditLogger(log_file=str(log_path))

            entry = AuditEntry(
                action="test_action",
                user_id=1,
                username="testuser",
                ip_address="127.0.0.1",
                user_agent="test",
                details={"key": "value"},
                timestamp="2025-01-01T00:00:00",
            )

            await audit_logger._write_to_file(entry)

            assert log_path.exists()
            content = log_path.read_text()
            parsed = json.loads(content.strip())
            assert parsed["action"] == "test_action"
            assert parsed["username"] == "testuser"


# ── secure_memory: Logging on ctypes fallback ───────────────────────────────


class TestSecureMemoryLogging:
    """Test that ctypes fallback in secure_zero_memory logs the error."""

    def test_ctypes_failure_logs_debug(self):
        """When ctypes.memset fails, should log debug and use fallback."""
        from src.utils.secure_memory import secure_zero_memory

        data = bytearray(b"secret")

        with (
            patch("src.utils.secure_memory.ctypes") as mock_ctypes,
            patch("src.utils.secure_memory.logger") as mock_logger,
        ):
            mock_ctypes.memset.side_effect = OSError("memset failed")
            mock_ctypes.addressof.side_effect = OSError("memset failed")
            mock_c_char = MagicMock()
            mock_c_char.from_buffer.side_effect = OSError("memset failed")
            mock_ctypes.c_char.__mul__ = MagicMock(return_value=mock_c_char)

            secure_zero_memory(data)

            # Should have logged the fallback
            mock_logger.debug.assert_called_once()
            assert "fallback" in mock_logger.debug.call_args[0][0].lower()


# ── encryption: Logging on unexpected errors ─────────────────────────────────


class TestEncryptionLogging:
    """Test that encryption silent failures now log debug messages."""

    def test_can_decrypt_logs_unexpected_error(self, monkeypatch):
        """can_decrypt should log unexpected (non-InvalidToken) exceptions."""
        monkeypatch.setenv("ENCRYPTION_KEY", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=")

        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        monkeypatch.setenv("ENCRYPTION_KEY", key.decode())

        from src.utils.encryption import PasswordEncryption

        enc = PasswordEncryption(key.decode())

        with (
            patch.object(enc.cipher, "decrypt", side_effect=TypeError("unexpected")),
            patch("src.utils.encryption.logger") as mock_logger,
        ):
            result = enc.can_decrypt("some_data")
            assert result is False
            mock_logger.debug.assert_called()
            assert "can_decrypt" in mock_logger.debug.call_args[0][0]

    def test_needs_migration_logs_unexpected_error(self, monkeypatch):
        """needs_migration should log unexpected exceptions."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        monkeypatch.setenv("ENCRYPTION_KEY", key.decode())

        from src.utils.encryption import PasswordEncryption

        enc = PasswordEncryption(key.decode())

        # Mock the first Fernet to raise unexpected error
        with (
            patch("src.utils.encryption.Fernet") as mock_fernet_cls,
            patch("src.utils.encryption.logger") as mock_logger,
        ):
            mock_fernet_cls.side_effect = TypeError("unexpected error")
            result = enc.needs_migration("some_data")
            assert result is False
            mock_logger.debug.assert_called()
            assert "needs_migration" in mock_logger.debug.call_args[0][0]
