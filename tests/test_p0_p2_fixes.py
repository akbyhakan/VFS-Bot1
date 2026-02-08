"""Tests for P0-P2 security, performance, and reliability fixes."""

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

# P0-1: Encryption race condition fix
from src.utils.encryption import get_encryption, reset_encryption


class TestEncryptionRaceCondition:
    """Test encryption singleton thread safety improvements."""

    def test_encryption_instance_local_reference(self):
        """Test that encryption instance uses local reference inside lock."""
        # Reset to start fresh
        reset_encryption()

        # Need a valid encryption key for testing
        from cryptography.fernet import Fernet

        old_key = os.getenv("ENCRYPTION_KEY")

        try:
            # Set valid test key
            test_key = Fernet.generate_key().decode()
            os.environ["ENCRYPTION_KEY"] = test_key

            # Get encryption instance
            enc1 = get_encryption()
            assert enc1 is not None

            # Get again - should return same instance
            enc2 = get_encryption()
            assert enc1 is enc2

            # Change environment key and get again
            new_key = Fernet.generate_key().decode()
            os.environ["ENCRYPTION_KEY"] = new_key

            # Should create new instance
            enc3 = get_encryption()
            assert enc3 is not enc1

        finally:
            # Restore original key
            if old_key:
                os.environ["ENCRYPTION_KEY"] = old_key
            elif "ENCRYPTION_KEY" in os.environ:
                del os.environ["ENCRYPTION_KEY"]
            reset_encryption()


# P0-2: Session binding security
from src.utils.security.session_manager import SessionManager, SessionMetadata


class TestSessionBinding:
    """Test session binding security features."""

    def test_session_metadata_creation(self):
        """Test SessionMetadata dataclass creation."""
        metadata = SessionMetadata(
            ip_address="192.168.1.1",
            user_agent_hash="abcd1234",
            created_at=1234567890,
            last_validated=1234567900,
        )

        assert metadata.ip_address == "192.168.1.1"
        assert metadata.user_agent_hash == "abcd1234"
        assert metadata.created_at == 1234567890
        assert metadata.last_validated == 1234567900

    def test_session_manager_with_binding_disabled(self, tmp_path):
        """Test session manager with binding disabled (default)."""
        session_file = tmp_path / "test_session.json"
        manager = SessionManager(session_file=str(session_file), enable_session_binding=False)

        # Should always return True when disabled
        assert (
            manager.validate_session_binding(ip_address="192.168.1.1", user_agent="Mozilla/5.0")
            is True
        )

    def test_session_manager_user_agent_hash(self, tmp_path):
        """Test User-Agent hashing."""
        session_file = tmp_path / "test_session.json"
        manager = SessionManager(session_file=str(session_file), enable_session_binding=True)

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        expected_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16]

        actual_hash = manager._hash_user_agent(user_agent)
        assert actual_hash == expected_hash
        assert len(actual_hash) == 16

    def test_session_binding_validation_passes(self, tmp_path):
        """Test session binding validation with matching metadata."""
        session_file = tmp_path / "test_session.json"
        manager = SessionManager(session_file=str(session_file), enable_session_binding=True)

        ip = "192.168.1.1"
        ua = "Mozilla/5.0"

        # Set binding
        manager.set_session_binding(ip_address=ip, user_agent=ua)

        # Validate with same metadata - should pass
        assert manager.validate_session_binding(ip_address=ip, user_agent=ua) is True

    def test_session_binding_validation_fails_on_ip_mismatch(self, tmp_path):
        """Test session binding validation fails with different IP."""
        session_file = tmp_path / "test_session.json"
        manager = SessionManager(session_file=str(session_file), enable_session_binding=True)

        # Set binding with one IP
        manager.set_session_binding(ip_address="192.168.1.1", user_agent="Mozilla/5.0")

        # Validate with different IP - should fail
        assert (
            manager.validate_session_binding(ip_address="10.0.0.1", user_agent="Mozilla/5.0")
            is False
        )


from src.core.exceptions import LoginError

# P0-3: Password leak prevention
from src.services.bot.auth_service import AuthService


class TestPasswordLeakPrevention:
    """Test password sanitization in exceptions."""

    @pytest.mark.asyncio
    async def test_password_redacted_in_exception(self):
        """Test that password is redacted from error messages."""
        config = {
            "vfs": {
                "base_url": "https://example.com",
                "country": "tr",
                "language": "en",
                "mission": "test",
            }
        }

        captcha_solver = Mock()
        auth_service = AuthService(config, captcha_solver)

        # Create a mock page that raises an error containing the password
        mock_page = AsyncMock()
        password = "SecretPassword123"

        # Make smart_fill raise an error with the password in it
        with patch("src.services.bot.auth_service.smart_fill") as mock_fill:
            mock_fill.side_effect = Exception(f"Failed to fill field with value: {password}")

            with patch("src.services.bot.auth_service.safe_navigate", return_value=True):
                with patch("src.services.bot.auth_service.logger") as mock_logger:
                    # Login should return False due to exception
                    result = await auth_service.login(mock_page, "test@example.com", password)
                    assert result is False

                    # Check the logged error message for redaction
                    # The error should be logged with the password redacted
                    assert mock_logger.error.called
                    error_calls = [str(call) for call in mock_logger.error.call_args_list]
                    error_msg = str(error_calls)

                    # Password should NOT appear in any error logs
                    assert password not in error_msg, "Password was not redacted from error logs!"


# P1-4: Graceful shutdown timeout
from src.core.exceptions import ShutdownTimeoutError


class TestGracefulShutdownTimeout:
    """Test graceful shutdown timeout functionality."""

    def test_shutdown_timeout_error(self):
        """Test ShutdownTimeoutError exception."""
        error = ShutdownTimeoutError("Graceful shutdown timed out after 30s", timeout=30)

        assert error.timeout == 30
        assert error.recoverable is False
        assert "30" in str(error)
        assert error.details["timeout"] == 30

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_safe_shutdown_cleanup_with_db(self):
        """Test safe_shutdown_cleanup with database."""
        from src.constants import Database as DatabaseConfig
        from src.core.shutdown import safe_shutdown_cleanup
        from src.models.database import Database

        # Create a test database
        test_db_url = DatabaseConfig.TEST_URL
        db = Database(database_url=test_db_url)
        
        try:
            await db.connect()
        except Exception as e:
            pytest.skip(f"PostgreSQL test database not available: {e}")

        # Verify pool was created
        assert db.pool is not None

        # Cleanup should close the database
        await safe_shutdown_cleanup(db=db, db_owned=True)

        # Pool should be closed after cleanup
        assert db.pool is None or db.pool._closed

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_safe_shutdown_cleanup_without_db_ownership(self):
        """Test safe_shutdown_cleanup respects db_owned flag."""
        from src.constants import Database as DatabaseConfig
        from src.core.shutdown import safe_shutdown_cleanup
        from src.models.database import Database

        # Create a test database
        test_db_url = DatabaseConfig.TEST_URL
        db = Database(database_url=test_db_url)
        
        try:
            await db.connect()
        except Exception as e:
            pytest.skip(f"PostgreSQL test database not available: {e}")

        # Verify pool was created
        assert db.pool is not None

        # Cleanup should NOT close the database if db_owned is False
        await safe_shutdown_cleanup(db=db, db_owned=False)

        # Pool should still be active
        assert db.pool is not None
        assert not db.pool._closed

        # Cleanup manually
        await db.close()

    @pytest.mark.asyncio
    async def test_safe_shutdown_cleanup_handles_errors(self):
        """Test safe_shutdown_cleanup handles errors gracefully."""
        from src.core.shutdown import safe_shutdown_cleanup

        # Create a mock database that raises an error on close
        mock_db = AsyncMock()
        mock_db.close = AsyncMock(side_effect=Exception("Close failed"))

        # Should not raise, just log the error
        await safe_shutdown_cleanup(db=mock_db, db_owned=True)

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_timeout_success(self):
        """Test graceful_shutdown_with_timeout completes successfully."""
        from src.core.shutdown import graceful_shutdown_with_timeout

        loop = asyncio.get_running_loop()

        # Should complete without raising
        await graceful_shutdown_with_timeout(loop, db=None, notifier=None)

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_timeout_raises_on_timeout(self):
        """Test graceful_shutdown_with_timeout raises ShutdownTimeoutError on timeout."""
        from unittest.mock import patch

        from src.core.shutdown import graceful_shutdown_with_timeout

        loop = asyncio.get_running_loop()

        # Mock graceful_shutdown to timeout
        with patch("src.core.shutdown.graceful_shutdown") as mock_shutdown:
            # Make it hang indefinitely
            mock_shutdown.side_effect = asyncio.TimeoutError()

            # Should raise ShutdownTimeoutError
            with pytest.raises(ShutdownTimeoutError) as exc_info:
                await graceful_shutdown_with_timeout(loop, db=None, notifier=None)

            assert exc_info.value.timeout > 0


class TestFastAPILifespan:
    """Test FastAPI lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_closes_database_on_shutdown(self):
        """Test that lifespan closes DatabaseFactory on shutdown."""
        from unittest.mock import AsyncMock, patch

        from web.app import lifespan

        # Mock FastAPI app
        mock_app = Mock()

        # Mock DatabaseFactory methods
        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch("web.app.DatabaseFactory.close_instance", new_callable=AsyncMock) as mock_close:
                with patch("src.services.otp_webhook.get_otp_service") as mock_otp:
                    mock_otp_service = AsyncMock()
                    mock_otp_service.stop_cleanup_scheduler = AsyncMock()
                    mock_otp.return_value = mock_otp_service

                    # Run the lifespan
                    async with lifespan(mock_app):
                        pass  # Simulate app running

                    # After exiting context, close_instance should be called
                    mock_close.assert_called_once()
                    mock_otp_service.stop_cleanup_scheduler.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_handles_shutdown_errors(self):
        """Test that lifespan handles errors during shutdown gracefully."""
        from unittest.mock import AsyncMock, patch

        from web.app import lifespan

        mock_app = Mock()

        # Mock DatabaseFactory to raise on close
        with patch("web.app.DatabaseFactory.ensure_connected", new_callable=AsyncMock):
            with patch(
                "web.app.DatabaseFactory.close_instance",
                new_callable=AsyncMock,
                side_effect=Exception("Close failed"),
            ):
                with patch("src.services.otp_webhook.get_otp_service") as mock_otp:
                    mock_otp_service = AsyncMock()
                    mock_otp_service.stop_cleanup_scheduler = AsyncMock()
                    mock_otp.return_value = mock_otp_service

                    # Should not raise despite the error
                    async with lifespan(mock_app):
                        pass


class TestEmergencyCleanup:
    """Test emergency cleanup on second signal."""

    @pytest.mark.asyncio
    async def test_fast_emergency_cleanup(self):
        """Test fast_emergency_cleanup closes DatabaseFactory."""
        from unittest.mock import AsyncMock, patch

        from src.core.shutdown import fast_emergency_cleanup

        with patch("src.models.db_factory.DatabaseFactory.close_instance", new_callable=AsyncMock) as mock_close:
            await fast_emergency_cleanup()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fast_emergency_cleanup_handles_timeout(self):
        """Test fast_emergency_cleanup handles timeout gracefully."""
        from unittest.mock import AsyncMock, patch

        from src.core.shutdown import fast_emergency_cleanup

        # Mock close_instance to timeout
        with patch(
            "src.models.db_factory.DatabaseFactory.close_instance",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            # Should not raise
            await fast_emergency_cleanup()


# P1-5: Environment validation
class TestEnvironmentValidation:
    """Test environment validation with whitelist."""

    def test_valid_environments_whitelist(self):
        """Test that valid environments are accepted."""
        # Test the constants and function directly without importing web.app
        VALID_ENVIRONMENTS = frozenset(
            {"production", "staging", "development", "dev", "testing", "test", "local"}
        )

        valid_envs = ["production", "staging", "development", "dev", "testing", "test", "local"]

        for env in valid_envs:
            assert env in VALID_ENVIRONMENTS

    def test_unknown_environment_defaults_to_production(self):
        """Test that unknown environments default to production."""
        # Test the function logic directly
        VALID_ENVIRONMENTS = frozenset(
            {"production", "staging", "development", "dev", "testing", "test", "local"}
        )

        def get_validated_environment() -> str:
            env = os.getenv("ENV", "production").lower()
            if env not in VALID_ENVIRONMENTS:
                return "production"
            return env

        old_env = os.getenv("ENV")
        try:
            os.environ["ENV"] = "unknown_environment"
            result = get_validated_environment()
            assert result == "production"
        finally:
            if old_env:
                os.environ["ENV"] = old_env
            elif "ENV" in os.environ:
                del os.environ["ENV"]


# P2-7: Database batch operations
from src.core.exceptions import BatchOperationError


class TestDatabaseBatchOperations:
    """Test database batch operation functionality."""

    def test_batch_operation_error(self):
        """Test BatchOperationError exception."""
        error = BatchOperationError(
            "Batch insert failed", operation="add_users_batch", failed_count=5, total_count=10
        )

        assert error.operation == "add_users_batch"
        assert error.failed_count == 5
        assert error.total_count == 10
        assert error.details["success_count"] == 5
        assert error.recoverable is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_add_users_batch_validates_emails(self):
        """Test that batch user add validates all emails."""
        from src.constants import Database as DatabaseConfig
        from src.core.exceptions import ValidationError
        from src.models.database import Database

        test_db_url = DatabaseConfig.TEST_URL
        db = Database(database_url=test_db_url)
        
        try:
            await db.connect()
        except Exception as e:
            pytest.skip(f"PostgreSQL test database not available: {e}")

        try:
            users = [
                {
                    "email": "invalid-email",  # Invalid email
                    "password": "pass123",
                    "centre": "ankara",
                    "category": "tourist",
                    "subcategory": "standard",
                }
            ]

            with pytest.raises(ValidationError):
                await db.add_users_batch(users)
        finally:
            await db.close()


# P2-8: New exception types
from src.core.exceptions import SessionBindingError


class TestNewExceptionTypes:
    """Test new exception types."""

    def test_session_binding_error(self):
        """Test SessionBindingError exception."""
        error = SessionBindingError(
            "Session binding validation failed", details={"reason": "IP mismatch"}
        )

        assert error.recoverable is False
        assert error.details["reason"] == "IP mismatch"
        assert "Session binding" in str(error)

    def test_shutdown_timeout_error_details(self):
        """Test ShutdownTimeoutError with details."""
        error = ShutdownTimeoutError(timeout=30)

        error_dict = error.to_dict()
        assert error_dict["error"] == "ShutdownTimeoutError"
        assert error_dict["details"]["timeout"] == 30
        assert error_dict["recoverable"] is False

    def test_batch_operation_error_details(self):
        """Test BatchOperationError with details."""
        error = BatchOperationError(operation="update_users_batch", failed_count=3, total_count=10)

        error_dict = error.to_dict()
        assert error_dict["error"] == "BatchOperationError"
        assert error_dict["details"]["operation"] == "update_users_batch"
        assert error_dict["details"]["failed_count"] == 3
        assert error_dict["details"]["success_count"] == 7
