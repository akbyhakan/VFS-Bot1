"""Tests for dynamic token update functionality in VFS API client."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.services.vfs.auth import VFSAuth
from src.services.vfs.booking import VFSBooking
from src.services.vfs.models import VFSSession
from src.services.vfs.slots import VFSSlots
from src.utils.security.endpoint_rate_limiter import EndpointRateLimiter


class TestVFSAuthTokenUpdate:
    """Test VFSAuth.check_and_update_token_from_data method."""

    @pytest.fixture
    def mock_session_getter(self):
        """Mock HTTP session getter."""
        session = MagicMock()
        session.headers = {}
        return lambda: session

    @pytest.fixture
    def auth(self, mock_session_getter):
        """Create VFSAuth instance."""
        limiter = EndpointRateLimiter()
        auth = VFSAuth(
            mission_code="nld",
            endpoint_limiter=limiter,
            http_session_getter=mock_session_getter,
        )
        # Set up a session
        auth.session = VFSSession(
            access_token="old-token",
            refresh_token="old-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            user_id="user123",
            email="test@example.com",
        )
        return auth

    def test_no_session(self, auth):
        """Test that method returns False when no session exists."""
        auth.session = None
        data = {"accessToken": "new-token"}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)
        assert result is False

    def test_update_from_response_body_access_token(self, auth):
        """Test updating token from response body with accessToken key."""
        data = {"accessToken": "new-token", "refreshToken": "new-refresh", "expiresIn": 60}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is True
        assert auth.session.access_token == "new-token"
        assert auth.session.refresh_token == "new-refresh"
        assert "Authorization" in auth._session.headers
        assert auth._session.headers["Authorization"] == "Bearer new-token"

    def test_update_from_response_body_snake_case(self, auth):
        """Test updating token from response body with access_token key."""
        data = {"access_token": "new-snake-token", "refresh_token": "new-refresh-snake"}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is True
        assert auth.session.access_token == "new-snake-token"
        assert auth.session.refresh_token == "new-refresh-snake"

    def test_update_from_set_cookie_header(self, auth):
        """Test updating token from Set-Cookie header."""
        data = {}
        headers = {"Set-Cookie": "accesstoken=cookie-token; Path=/; HttpOnly"}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is True
        assert auth.session.access_token == "cookie-token"

    def test_no_update_when_token_same(self, auth):
        """Test that no update occurs when token is the same."""
        data = {"accessToken": "old-token"}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is False

    def test_no_update_when_no_token_in_response(self, auth):
        """Test that no update occurs when response has no token."""
        data = {"someOtherField": "value"}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is False

    def test_data_is_list(self, auth):
        """Test handling when data is a list instead of dict."""
        data = [{"id": "1", "name": "Test"}]
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is False

    def test_update_expiry_with_expires_in(self, auth):
        """Test that expiry time is updated when expiresIn is provided."""
        before = datetime.now(timezone.utc)
        data = {"accessToken": "new-token", "expiresIn": 120}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is True
        # Expiry should be updated (with buffer applied)
        assert auth.session.expires_at > before

    def test_update_without_expires_in_uses_default(self, auth):
        """Test that default expiry is used when expiresIn is not provided."""
        before = datetime.now(timezone.utc)
        data = {"accessToken": "new-token"}
        headers = {}

        result = auth.check_and_update_token_from_data(data, headers)

        assert result is True
        # Expiry should be updated with default (60 minutes with buffer)
        assert auth.session.expires_at > before


class TestVFSSlotsTokenUpdate:
    """Test VFSSlots token update callback integration."""

    @pytest.fixture
    def mock_session_getter(self):
        """Mock HTTP session getter."""
        session = MagicMock()
        session.headers = {}
        return lambda: session

    @pytest.fixture
    def mock_token_callback(self):
        """Mock token update callback."""
        return MagicMock(return_value=True)

    @pytest.fixture
    def slots(self, mock_session_getter, mock_token_callback):
        """Create VFSSlots instance with token callback."""
        limiter = EndpointRateLimiter()
        ensure_auth = AsyncMock()
        return VFSSlots(
            endpoint_limiter=limiter,
            http_session_getter=mock_session_getter,
            ensure_authenticated=ensure_auth,
            token_update_callback=mock_token_callback,
        )

    @pytest.mark.asyncio
    async def test_get_centres_calls_token_callback(self, slots, mock_token_callback):
        """Test that get_centres calls token update callback."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"id": "1", "name": "Test Centre"}])
        mock_response.headers = {"Set-Cookie": "accesstoken=new-token"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        slots._session.get = MagicMock(return_value=mock_response)

        centres = await slots.get_centres()

        assert len(centres) == 1
        # Token callback should have been called with data and headers
        mock_token_callback.assert_called_once()
        call_args = mock_token_callback.call_args
        assert call_args[0][0] == [{"id": "1", "name": "Test Centre"}]
        assert "Set-Cookie" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_visa_categories_calls_token_callback(self, slots, mock_token_callback):
        """Test that get_visa_categories calls token update callback."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value=[{"id": "1", "name": "Category", "accessToken": "new-token"}]
        )
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        slots._session.get = MagicMock(return_value=mock_response)

        categories = await slots.get_visa_categories("centre123")

        assert len(categories) == 1
        mock_token_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_callback_error_is_non_critical(self, slots):
        """Test that token callback errors don't break the flow."""
        # Create a callback that raises an exception
        failing_callback = MagicMock(side_effect=Exception("Callback error"))
        slots._token_update_callback = failing_callback

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"id": "1", "name": "Test Centre"}])
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        slots._session.get = MagicMock(return_value=mock_response)

        # Should not raise exception
        centres = await slots.get_centres()
        assert len(centres) == 1

    @pytest.mark.asyncio
    async def test_no_callback_works(self):
        """Test that slots work without token callback."""
        limiter = EndpointRateLimiter()
        session = MagicMock()
        session.headers = {}
        ensure_auth = AsyncMock()

        # Create slots without token callback
        slots = VFSSlots(
            endpoint_limiter=limiter,
            http_session_getter=lambda: session,
            ensure_authenticated=ensure_auth,
            token_update_callback=None,
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"id": "1", "name": "Test Centre"}])
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        slots._session.get = MagicMock(return_value=mock_response)

        # Should work without callback
        centres = await slots.get_centres()
        assert len(centres) == 1


class TestVFSBookingTokenUpdate:
    """Test VFSBooking token update callback integration."""

    @pytest.fixture
    def mock_session_getter(self):
        """Mock HTTP session getter."""
        session = MagicMock()
        session.headers = {}
        return lambda: session

    @pytest.fixture
    def mock_token_callback(self):
        """Mock token update callback."""
        return MagicMock(return_value=True)

    @pytest.fixture
    def booking(self, mock_session_getter, mock_token_callback):
        """Create VFSBooking instance with token callback."""
        limiter = EndpointRateLimiter()
        ensure_auth = AsyncMock()
        return VFSBooking(
            endpoint_limiter=limiter,
            http_session_getter=mock_session_getter,
            ensure_authenticated=ensure_auth,
            token_update_callback=mock_token_callback,
        )

    @pytest.mark.asyncio
    async def test_book_appointment_calls_token_callback(self, booking, mock_token_callback):
        """Test that book_appointment calls token update callback."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "success": True,
                "bookingId": "booking123",
                "accessToken": "new-token-from-booking",
            }
        )
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        booking._session.post = MagicMock(return_value=mock_response)

        result = await booking.book_appointment(
            slot_date="2024-01-15", slot_time="10:00", applicant_data={"name": "Test"}
        )

        assert result["success"] is True
        # Token callback should have been called
        mock_token_callback.assert_called_once()
        call_args = mock_token_callback.call_args
        assert "accessToken" in call_args[0][0]


class TestExplicitReadAndPass:
    """Test explicit read and pass pattern for JSON responses."""

    @pytest.fixture
    def mock_session_getter(self):
        """Mock HTTP session getter."""
        session = MagicMock()
        session.headers = {}
        return lambda: session

    @pytest.fixture
    def slots(self, mock_session_getter):
        """Create VFSSlots instance."""
        limiter = EndpointRateLimiter()
        ensure_auth = AsyncMock()
        return VFSSlots(
            endpoint_limiter=limiter,
            http_session_getter=mock_session_getter,
            ensure_authenticated=ensure_auth,
            token_update_callback=None,
        )

    @pytest.mark.asyncio
    async def test_handles_non_json_response(self, slots):
        """Test that non-JSON response is handled gracefully."""
        from src.core.exceptions import VFSApiError

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=aiohttp.ContentTypeError(None, None))
        mock_response.text = AsyncMock(return_value="<html>Maintenance page</html>")
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        slots._session.get = MagicMock(return_value=mock_response)

        # Should raise VFSApiError
        with pytest.raises(VFSApiError, match="Non-JSON response from VFS API"):
            await slots.get_centres()

    @pytest.mark.asyncio
    async def test_handles_value_error_on_json_parse(self, slots):
        """Test that ValueError during JSON parsing is handled."""
        from src.core.exceptions import VFSApiError

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_response.text = AsyncMock(return_value="Invalid response")
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        slots._session.get = MagicMock(return_value=mock_response)

        # Should raise VFSApiError
        with pytest.raises(VFSApiError, match="Non-JSON response from VFS API"):
            await slots.get_centres()
