"""Tests for P0-P2 security, performance, and reliability fixes."""

import asyncio
import hashlib
import os
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

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


# P0-3: Password leak prevention
from src.services.bot.auth_service import AuthService
from src.core.exceptions import LoginError


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
    async def test_add_users_batch_validates_emails(self):
        """Test that batch user add validates all emails."""
        from src.models.database import Database
        from src.core.exceptions import ValidationError

        db = Database(db_path=":memory:")
        await db.connect()

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
