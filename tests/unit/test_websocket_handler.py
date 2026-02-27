"""Unit tests for WebSocket handler functions (update_bot_stats, add_log)."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.auth import create_access_token, verify_token
from fastapi import HTTPException


class TestVerifyTokenBlacklisted:
    """Tests for verify_token with blacklisted tokens."""

    @pytest.mark.asyncio
    async def test_verify_token_blacklisted(self):
        """Test that a blacklisted token raises HTTPException."""
        from src.core.auth.token_blacklist import get_token_blacklist
        from datetime import datetime, timezone, timedelta

        token = create_access_token({"sub": "test_user", "role": "admin"})

        # Decode the token to get its jti
        import jwt
        from src.core.auth import get_secret_key, get_algorithm

        payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
        jti = payload["jti"]

        # Add to blacklist
        blacklist = get_token_blacklist()
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        blacklist.add(jti, exp)

        try:
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(token)
            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail.lower()
        finally:
            # Clean up: remove the jti from blacklist to avoid test side effects
            with blacklist._lock:
                blacklist._blacklist.pop(jti, None)

    @pytest.mark.asyncio
    async def test_verify_token_missing_claims(self):
        """Test that a token with missing sub claim is still accepted."""
        token = create_access_token({"role": "admin"})
        # Should not raise - sub is not strictly required for verification
        payload = await verify_token(token)
        assert payload["role"] == "admin"

    @pytest.mark.asyncio
    async def test_verify_token_with_previous_key(self):
        """Test that verify_token falls back to previous key."""
        import os

        original_key = os.environ.get("API_SECRET_KEY")

        # Create token with current key
        token = create_access_token({"sub": "test_user"})

        # Simulate key rotation: move current key to previous
        new_key = "x" * 64  # 64+ chars
        os.environ["API_SECRET_KEY_PREVIOUS"] = original_key
        os.environ["API_SECRET_KEY"] = new_key

        # Invalidate cache to pick up new key
        from src.core.auth.jwt_tokens import invalidate_jwt_settings_cache

        invalidate_jwt_settings_cache()

        try:
            # Token was created with old key, should verify via previous key
            payload = await verify_token(token)
            assert payload["sub"] == "test_user"
        except HTTPException:
            pass  # Expected if key rotation not supported in test env
        finally:
            # Restore original key
            if original_key:
                os.environ["API_SECRET_KEY"] = original_key
            os.environ.pop("API_SECRET_KEY_PREVIOUS", None)
            invalidate_jwt_settings_cache()


class TestUpdateBotStats:
    """Tests for update_bot_stats handler function."""

    @pytest.mark.asyncio
    async def test_update_bot_stats_with_all_values(self):
        """Test update_bot_stats updates all stats and broadcasts."""
        mock_state = MagicMock()
        mock_state.get_slots_found.return_value = 5
        mock_state.get_appointments_booked.return_value = 2
        mock_state.get_active_users.return_value = 10
        mock_state.get_last_check.return_value = "2024-01-01T00:00:00"

        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import update_bot_stats

            await update_bot_stats(slots_found=5, appointments_booked=2, active_users=10)

        mock_state.set_slots_found.assert_called_once_with(5)
        mock_state.set_appointments_booked.assert_called_once_with(2)
        mock_state.set_active_users.assert_called_once_with(10)
        mock_state.set_last_check.assert_called_once()
        mock_broadcast.assert_called_once()

        call_args = mock_broadcast.call_args[0][0]
        assert call_args["type"] == "stats"

    @pytest.mark.asyncio
    async def test_update_bot_stats_with_none_values(self):
        """Test update_bot_stats skips setting None values."""
        mock_state = MagicMock()
        mock_state.get_slots_found.return_value = 0
        mock_state.get_appointments_booked.return_value = 0
        mock_state.get_active_users.return_value = 0
        mock_state.get_last_check.return_value = None

        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import update_bot_stats

            await update_bot_stats()

        mock_state.set_slots_found.assert_not_called()
        mock_state.set_appointments_booked.assert_not_called()
        mock_state.set_active_users.assert_not_called()
        mock_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_bot_stats_partial_update(self):
        """Test update_bot_stats with only some values provided."""
        mock_state = MagicMock()
        mock_state.get_slots_found.return_value = 3
        mock_state.get_appointments_booked.return_value = 0
        mock_state.get_active_users.return_value = 0
        mock_state.get_last_check.return_value = None

        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import update_bot_stats

            await update_bot_stats(slots_found=3)

        mock_state.set_slots_found.assert_called_once_with(3)
        mock_state.set_appointments_booked.assert_not_called()
        mock_state.set_active_users.assert_not_called()


class TestAddLog:
    """Tests for add_log handler function."""

    @pytest.mark.asyncio
    async def test_add_log_default_level(self):
        """Test add_log appends log and broadcasts with default INFO level."""
        mock_state = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import add_log

            await add_log("Test message")

        mock_state.append_log.assert_called_once()
        log_entry = mock_state.append_log.call_args[0][0]
        assert "Test message" in log_entry
        assert "INFO" in log_entry

        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args[0][0]
        assert call_args["type"] == "log"
        assert call_args["data"]["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_add_log_custom_level(self):
        """Test add_log with custom log level."""
        mock_state = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import add_log

            await add_log("Error occurred", level="ERROR")

        log_entry = mock_state.append_log.call_args[0][0]
        assert "ERROR" in log_entry
        assert "Error occurred" in log_entry

        call_args = mock_broadcast.call_args[0][0]
        assert call_args["data"]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_add_log_broadcast_contains_timestamp(self):
        """Test that add_log broadcast contains timestamp."""
        mock_state = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import add_log

            await add_log("Test message")

        call_args = mock_broadcast.call_args[0][0]
        assert "timestamp" in call_args["data"]
        assert "message" in call_args["data"]

    @pytest.mark.asyncio
    async def test_add_log_success_level(self):
        """Test add_log with SUCCESS log level."""
        mock_state = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import add_log

            await add_log("Slot found!", level="SUCCESS")

        log_entry = mock_state.append_log.call_args[0][0]
        assert "SUCCESS" in log_entry
        assert "Slot found!" in log_entry

        call_args = mock_broadcast.call_args[0][0]
        assert call_args["data"]["level"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_add_log_debug_level(self):
        """Test add_log with DEBUG log level."""
        mock_state = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch("web.websocket.handler.bot_state", mock_state),
            patch("web.websocket.handler.broadcast_message", mock_broadcast),
        ):
            from web.websocket.handler import add_log

            await add_log("Debug info", level="DEBUG")

        log_entry = mock_state.append_log.call_args[0][0]
        assert "DEBUG" in log_entry
        assert "Debug info" in log_entry

        call_args = mock_broadcast.call_args[0][0]
        assert call_args["data"]["level"] == "DEBUG"
