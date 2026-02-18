"""Tests for VFS modular components (auth, slots, booking)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import (
    VFSAuthenticationError,
    VFSRateLimitError,
    VFSSessionExpiredError,
)
from src.core.rate_limiting import EndpointRateLimiter
from src.services.vfs import VFSAuth, VFSBooking, VFSSlots
from src.services.vfs.models import VFSSession


class TestVFSAuth:
    """Test VFS Authentication module."""

    @pytest.fixture
    def endpoint_limiter(self):
        """Create endpoint rate limiter."""
        return EndpointRateLimiter()

    @pytest.fixture
    def mock_http_session(self):
        """Create mock HTTP session."""
        session = AsyncMock()
        session.headers = {}
        return session

    @pytest.fixture
    def auth(self, endpoint_limiter, mock_http_session):
        """Create VFS Auth instance."""
        return VFSAuth(
            mission_code="nld",
            endpoint_limiter=endpoint_limiter,
            http_session_getter=lambda: mock_http_session,
        )

    @pytest.mark.asyncio
    async def test_login_success(self, auth, mock_http_session):
        """Test successful login."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "accessToken": "mock-access-token",
                "refreshToken": "mock-refresh-token",
                "userId": "user123",
                "expiresIn": 60,
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        session = await auth.login(
            email="test@example.com", password="password123", turnstile_token="turnstile-token"
        )

        assert session is not None
        assert session.access_token == "mock-access-token"
        assert session.refresh_token == "mock-refresh-token"
        assert session.user_id == "user123"
        assert session.email == "test@example.com"
        assert session.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_login_failure(self, auth, mock_http_session):
        """Test failed login."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Invalid credentials")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        with pytest.raises(VFSAuthenticationError, match="Login failed with status 401"):
            await auth.login(
                email="test@example.com",
                password="wrongpassword",
                turnstile_token="turnstile-token",
            )

    @pytest.mark.asyncio
    async def test_login_rate_limit(self, auth, mock_http_session):
        """Test rate limited login."""
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        with pytest.raises(VFSRateLimitError, match="Rate limited on login endpoint"):
            await auth.login(
                email="test@example.com", password="password123", turnstile_token="turnstile-token"
            )

    @pytest.mark.asyncio
    async def test_ensure_authenticated_no_session(self, auth):
        """Test ensure_authenticated with no session."""
        with pytest.raises(VFSSessionExpiredError, match="Not authenticated"):
            await auth.ensure_authenticated()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_expired_session(self, auth, mock_http_session):
        """Test ensure_authenticated with expired session."""
        # Set up an expired session
        auth.session = VFSSession(
            access_token="old-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            user_id="user123",
            email="test@example.com",
        )

        # Mock refresh token response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "accessToken": "new-access-token",
                "refreshToken": "new-refresh-token",
                "expiresIn": 60,
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        await auth.ensure_authenticated()

        assert auth.session.access_token == "new-access-token"

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth, mock_http_session):
        """Test successful token refresh."""
        auth.session = VFSSession(
            access_token="old-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            user_id="user123",
            email="test@example.com",
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "accessToken": "new-access-token",
                "refreshToken": "new-refresh-token",
                "expiresIn": 60,
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        await auth.refresh_token()

        assert auth.session.access_token == "new-access-token"
        assert auth.session.refresh_token == "new-refresh-token"


class TestVFSSlots:
    """Test VFS Slots module."""

    @pytest.fixture
    def endpoint_limiter(self):
        """Create endpoint rate limiter."""
        return EndpointRateLimiter()

    @pytest.fixture
    def mock_http_session(self):
        """Create mock HTTP session."""
        session = AsyncMock()
        session.headers = {}
        return session

    @pytest.fixture
    def mock_ensure_auth(self):
        """Create mock ensure_authenticated callable."""
        return AsyncMock()

    @pytest.fixture
    def slots(self, endpoint_limiter, mock_http_session, mock_ensure_auth):
        """Create VFS Slots instance."""
        return VFSSlots(
            endpoint_limiter=endpoint_limiter,
            http_session_getter=lambda: mock_http_session,
            ensure_authenticated=mock_ensure_auth,
        )

    @pytest.mark.asyncio
    async def test_get_centres_success(self, slots, mock_http_session):
        """Test successful get centres."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value=[
                {"id": "centre1", "name": "Centre 1"},
                {"id": "centre2", "name": "Centre 2"},
            ]
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.get = MagicMock(return_value=mock_response)

        centres = await slots.get_centres()

        assert len(centres) == 2
        assert centres[0]["id"] == "centre1"

    @pytest.mark.asyncio
    async def test_check_slot_availability_success(self, slots, mock_http_session):
        """Test successful slot availability check."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "availableDates": ["2024-01-15", "2024-01-16"],
                "message": "Slots available",
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.get = MagicMock(return_value=mock_response)

        result = await slots.check_slot_availability("centre1", "cat1", "subcat1")

        assert result.available is True
        assert len(result.dates) == 2
        assert result.centre_id == "centre1"

    @pytest.mark.asyncio
    async def test_check_slot_availability_none(self, slots, mock_http_session):
        """Test slot availability check with no slots."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"availableDates": [], "message": "No slots"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.get = MagicMock(return_value=mock_response)

        result = await slots.check_slot_availability("centre1", "cat1", "subcat1")

        assert result.available is False
        assert len(result.dates) == 0


class TestVFSBooking:
    """Test VFS Booking module."""

    @pytest.fixture
    def endpoint_limiter(self):
        """Create endpoint rate limiter."""
        return EndpointRateLimiter()

    @pytest.fixture
    def mock_http_session(self):
        """Create mock HTTP session."""
        session = AsyncMock()
        session.headers = {}
        return session

    @pytest.fixture
    def mock_ensure_auth(self):
        """Create mock ensure_authenticated callable."""
        return AsyncMock()

    @pytest.fixture
    def booking(self, endpoint_limiter, mock_http_session, mock_ensure_auth):
        """Create VFS Booking instance."""
        return VFSBooking(
            endpoint_limiter=endpoint_limiter,
            http_session_getter=lambda: mock_http_session,
            ensure_authenticated=mock_ensure_auth,
        )

    @pytest.mark.asyncio
    async def test_book_appointment_success(self, booking, mock_http_session):
        """Test successful appointment booking."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "appointmentId": "appt123",
                "status": "confirmed",
                "message": "Booking successful",
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        applicant_data = {"name": "Test User", "email": "test@example.com"}
        result = await booking.book_appointment("2024-01-15", "10:00", applicant_data)

        assert result["appointmentId"] == "appt123"
        assert result["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_book_appointment_rate_limit(self, booking, mock_http_session):
        """Test rate limited booking."""
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_http_session.post = MagicMock(return_value=mock_response)

        applicant_data = {"name": "Test User", "email": "test@example.com"}

        with pytest.raises(VFSRateLimitError, match="Rate limited on booking endpoint"):
            await booking.book_appointment("2024-01-15", "10:00", applicant_data)
