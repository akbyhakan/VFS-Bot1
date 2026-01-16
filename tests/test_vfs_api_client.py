"""Tests for VFS API Client."""

import base64
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from src.services.vfs_api_client import (
    VFSPasswordEncryption,
    VFSApiClient,
    VFSSession,
    SlotAvailability,
    VFS_API_BASE,
)
from src.core.exceptions import VFSSessionExpiredError, VFSAuthenticationError


class TestVFSPasswordEncryption:
    """Test VFS password encryption."""

    def test_encryption_key_length(self):
        """Test encryption key is 32 bytes for AES-256."""
        assert len(VFSPasswordEncryption.ENCRYPTION_KEY) == 32

    def test_encrypt_password(self):
        """Test password encryption."""
        password = "testpassword123"
        encrypted = VFSPasswordEncryption.encrypt(password)

        # Should return base64 string
        assert isinstance(encrypted, str)

        # Should be base64 decodable
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 0

        # IV (16 bytes) + encrypted data
        assert len(decoded) >= 16

    def test_encrypt_decrypt_roundtrip(self):
        """Test that we can decrypt what we encrypt."""
        password = "testpassword123"
        encrypted = VFSPasswordEncryption.encrypt(password)

        # Decode from base64
        decoded = base64.b64decode(encrypted)

        # Extract IV and ciphertext
        iv = decoded[:16]
        ciphertext = decoded[16:]

        # Decrypt
        cipher = AES.new(VFSPasswordEncryption.ENCRYPTION_KEY, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)

        # Should match original
        assert decrypted.decode("utf-8") == password

    def test_encrypt_different_passwords_produce_different_outputs(self):
        """Test that different passwords produce different encrypted outputs."""
        password1 = "password1"
        password2 = "password2"

        encrypted1 = VFSPasswordEncryption.encrypt(password1)
        encrypted2 = VFSPasswordEncryption.encrypt(password2)

        assert encrypted1 != encrypted2

    def test_encrypt_same_password_produces_different_outputs(self):
        """Test that same password produces different outputs (due to random IV)."""
        password = "testpassword"

        encrypted1 = VFSPasswordEncryption.encrypt(password)
        encrypted2 = VFSPasswordEncryption.encrypt(password)

        # Should be different due to random IV
        assert encrypted1 != encrypted2

    def test_encrypt_empty_password(self):
        """Test encrypting empty password."""
        encrypted = VFSPasswordEncryption.encrypt("")
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    def test_encrypt_unicode_password(self):
        """Test encrypting unicode password."""
        password = "şifre123üğıö"  # Turkish characters
        encrypted = VFSPasswordEncryption.encrypt(password)

        # Verify decryption
        decoded = base64.b64decode(encrypted)
        iv = decoded[:16]
        ciphertext = decoded[16:]
        cipher = AES.new(VFSPasswordEncryption.ENCRYPTION_KEY, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)

        assert decrypted.decode("utf-8") == password


class TestVFSApiClient:
    """Test VFS API Client."""

    @pytest.fixture
    def mock_captcha_solver(self):
        """Mock captcha solver."""
        solver = AsyncMock()
        solver.solve_turnstile = AsyncMock(return_value="mock-turnstile-token")
        return solver

    @pytest.fixture
    def client(self, mock_captcha_solver):
        """Create VFS API client."""
        return VFSApiClient(mission_code="nld", captcha_solver=mock_captcha_solver, timeout=30)

    def test_init_valid_mission(self, mock_captcha_solver):
        """Test initialization with valid mission code."""
        client = VFSApiClient(mission_code="nld", captcha_solver=mock_captcha_solver)

        assert client.mission_code == "nld"
        assert client.route == "tur/tr/nld"
        assert client.country_info.name_en == "Netherlands"
        assert client.timeout == 30

    def test_init_invalid_mission(self, mock_captcha_solver):
        """Test initialization with invalid mission code."""
        with pytest.raises(ValueError, match="Unsupported mission code"):
            VFSApiClient(mission_code="deu", captcha_solver=mock_captcha_solver)

    def test_generate_client_source(self, client):
        """Test client source generation."""
        source = client._generate_client_source()

        assert isinstance(source, str)
        assert "-vfs-turkey" in source
        assert len(source.split("-")) == 4  # timestamp-random-vfs-turkey

    @pytest.mark.asyncio
    async def test_init_http_session(self, client):
        """Test HTTP session initialization."""
        await client._init_http_session()

        assert client._http_session is not None
        assert client._client_source is not None

        # Check headers
        headers = client._http_session.headers
        assert headers["route"] == "tur/tr/nld"
        assert headers["clientsource"] is not None
        assert "visa.vfsglobal.com" in headers["Origin"]

        await client.close()

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing HTTP session."""
        await client._init_http_session()
        assert client._http_session is not None

        await client.close()
        assert client._http_session is None

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_captcha_solver):
        """Test using client as context manager."""
        async with VFSApiClient("nld", mock_captcha_solver) as client:
            assert client._http_session is not None

        # Should be closed after context
        assert client._http_session is None

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """Test successful login."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "accessToken": "mock-access-token",
                "refreshToken": "mock-refresh-token",
                "userId": "user123",
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_init_http_session", new_callable=AsyncMock):
            client._http_session = AsyncMock()
            client._http_session.post = MagicMock(return_value=mock_response)
            client._http_session.headers = {}

            session = await client.login(
                email="test@example.com", password="password123", turnstile_token="turnstile-token"
            )

            assert isinstance(session, VFSSession)
            assert session.access_token == "mock-access-token"
            assert session.refresh_token == "mock-refresh-token"
            assert session.user_id == "user123"
            assert session.email == "test@example.com"

            # Check that auth header was updated
            assert "Authorization" in client._http_session.headers

    @pytest.mark.asyncio
    async def test_login_failure(self, client):
        """Test failed login."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Invalid credentials")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_init_http_session", new_callable=AsyncMock):
            client._http_session = AsyncMock()
            client._http_session.post = MagicMock(return_value=mock_response)

            with pytest.raises(Exception, match="Login failed: 401"):
                await client.login(
                    email="test@example.com",
                    password="wrongpassword",
                    turnstile_token="turnstile-token",
                )

    @pytest.mark.asyncio
    async def test_get_centres(self, client):
        """Test getting centres."""
        client.session = VFSSession(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now(),
            user_id="user123",
            email="test@example.com",
        )

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(
            return_value=[
                {"id": "1", "name": "Istanbul"},
                {"id": "2", "name": "Ankara"},
            ]
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client._http_session = AsyncMock()
        client._http_session.get = MagicMock(return_value=mock_response)

        centres = await client.get_centres()

        assert len(centres) == 2
        assert centres[0]["name"] == "Istanbul"

    @pytest.mark.asyncio
    async def test_get_visa_categories(self, client):
        """Test getting visa categories."""
        client.session = VFSSession(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now(),
            user_id="user123",
            email="test@example.com",
        )

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(
            return_value=[
                {"id": "1", "name": "Schengen Visa"},
            ]
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client._http_session = AsyncMock()
        client._http_session.get = MagicMock(return_value=mock_response)

        categories = await client.get_visa_categories("centre123")

        assert len(categories) == 1
        assert categories[0]["name"] == "Schengen Visa"

    @pytest.mark.asyncio
    async def test_check_slot_availability_available(self, client):
        """Test checking slot availability when slots are available."""
        client.session = VFSSession(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now(),
            user_id="user123",
            email="test@example.com",
        )

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

        client._http_session = AsyncMock()
        client._http_session.get = MagicMock(return_value=mock_response)

        availability = await client.check_slot_availability(
            centre_id="centre123", category_id="cat123", subcategory_id="subcat123"
        )

        assert isinstance(availability, SlotAvailability)
        assert availability.available is True
        assert len(availability.dates) == 2
        assert "2024-01-15" in availability.dates

    @pytest.mark.asyncio
    async def test_check_slot_availability_not_available(self, client):
        """Test checking slot availability when no slots are available."""
        client.session = VFSSession(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now(),
            user_id="user123",
            email="test@example.com",
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"availableDates": [], "message": "No slots available"}
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client._http_session = AsyncMock()
        client._http_session.get = MagicMock(return_value=mock_response)

        availability = await client.check_slot_availability(
            centre_id="centre123", category_id="cat123", subcategory_id="subcat123"
        )

        assert availability.available is False
        assert len(availability.dates) == 0

    @pytest.mark.asyncio
    async def test_check_slot_availability_error(self, client):
        """Test checking slot availability when API returns error."""
        client.session = VFSSession(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now(),
            user_id="user123",
            email="test@example.com",
        )

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        client._http_session = AsyncMock()
        client._http_session.get = MagicMock(return_value=mock_response)

        availability = await client.check_slot_availability(
            centre_id="centre123", category_id="cat123", subcategory_id="subcat123"
        )

        assert availability.available is False
        assert "API error: 500" in availability.message

    @pytest.mark.asyncio
    async def test_ensure_authenticated_not_logged_in(self, client):
        """Test ensure authenticated raises error when not logged in."""
        with pytest.raises(VFSSessionExpiredError, match="Not authenticated"):
            await client._ensure_authenticated()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_logged_in(self, client):
        """Test ensure authenticated passes when logged in."""
        from datetime import timedelta

        client.session = VFSSession(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now() + timedelta(hours=1),  # Token not expired yet
            user_id="user123",
            email="test@example.com",
        )

        # Should not raise
        await client._ensure_authenticated()

    @pytest.mark.asyncio
    async def test_solve_turnstile(self, client, mock_captcha_solver):
        """Test solving Turnstile captcha."""
        token = await client.solve_turnstile(
            page_url="https://visa.vfsglobal.com/tur/tr/nld", site_key="mock-site-key"
        )

        assert token == "mock-turnstile-token"
        mock_captcha_solver.solve_turnstile.assert_called_once()


class TestVFSSession:
    """Test VFSSession dataclass."""

    def test_vfs_session_creation(self):
        """Test creating VFS session."""
        session = VFSSession(
            access_token="access123",
            refresh_token="refresh123",
            expires_at=datetime(2024, 1, 1, 12, 0, 0),
            user_id="user123",
            email="test@example.com",
        )

        assert session.access_token == "access123"
        assert session.refresh_token == "refresh123"
        assert session.user_id == "user123"
        assert session.email == "test@example.com"


class TestSlotAvailability:
    """Test SlotAvailability dataclass."""

    def test_slot_availability_creation(self):
        """Test creating slot availability."""
        availability = SlotAvailability(
            available=True,
            dates=["2024-01-15", "2024-01-16"],
            centre_id="centre123",
            category_id="cat123",
            message="Slots found",
        )

        assert availability.available is True
        assert len(availability.dates) == 2
        assert availability.message == "Slots found"

    def test_slot_availability_no_message(self):
        """Test slot availability without message."""
        availability = SlotAvailability(
            available=False, dates=[], centre_id="centre123", category_id="cat123"
        )

        assert availability.message is None
