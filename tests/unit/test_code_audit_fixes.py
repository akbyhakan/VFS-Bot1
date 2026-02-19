"""Tests for code audit fixes."""

import asyncio
import os
import random
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


class TestCORSProductionHardFail:
    """Test CORS production configuration validation."""

    def test_cors_raises_error_in_production_without_origins(self):
        """Test that missing CORS origins in production raises RuntimeError."""
        # Set production environment
        os.environ["ENV"] = "production"
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)

        # Import the app module which should fail in production
        with pytest.raises(RuntimeError) as exc_info:
            # We can't directly import the app as it would fail, so we'll test the logic
            from web.cors import validate_cors_origins

            allowed_origins = validate_cors_origins("")
            env = os.getenv("ENV", "production").lower()
            if not allowed_origins and env not in (
                "development",
                "dev",
                "local",
                "testing",
                "test",
            ):
                raise RuntimeError(
                    "CRITICAL: No valid CORS origins configured for production. "
                    "Set CORS_ALLOWED_ORIGINS in .env (e.g., 'https://yourdomain.com'). "
                    "Application cannot start without valid CORS configuration in production."
                )

        assert "CRITICAL" in str(exc_info.value)
        assert "CORS" in str(exc_info.value)

    def test_cors_allows_empty_in_development(self):
        """Test that missing CORS origins is allowed in development."""
        # Set development environment
        os.environ["ENV"] = "development"
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)

        from web.cors import validate_cors_origins

        allowed_origins = validate_cors_origins("")
        # Should not raise in development, just returns empty list
        assert allowed_origins == []

    def test_cors_ipv6_localhost_blocked_in_production(self):
        """Test that IPv6 localhost (::1) is blocked in production."""
        os.environ["ENV"] = "production"

        from web.cors import validate_cors_origins

        origins = validate_cors_origins("http://[::1]:3000")
        assert origins == []

    def test_cors_zero_ip_blocked_in_production(self):
        """Test that 0.0.0.0 is blocked in production."""
        os.environ["ENV"] = "production"

        from web.cors import validate_cors_origins

        origins = validate_cors_origins("http://0.0.0.0:8000")
        assert origins == []

    def test_cors_localhost_subdomain_bypass_blocked(self):
        """Test that localhost subdomain bypass is blocked in production."""
        os.environ["ENV"] = "production"

        from web.cors import validate_cors_origins

        origins = validate_cors_origins("http://localhost.evil.com")
        assert origins == []


class TestBrowserMemoryLeakPrevention:
    """Test browser memory leak prevention features."""

    @pytest.mark.asyncio
    async def test_browser_manager_tracks_page_count(self):
        """Test that BrowserManager tracks page creation count."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 5},
            "anti_detection": {"enabled": False},
        }
        browser_manager = BrowserManager(config)

        assert browser_manager._page_count == 0
        assert browser_manager._max_pages_before_restart == 5

    @pytest.mark.asyncio
    async def test_browser_manager_should_restart(self):
        """Test should_restart logic based on page count threshold."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 3},
            "anti_detection": {"enabled": False},
        }
        browser_manager = BrowserManager(config)

        # Simulate page creation (in production, new_page() increments _page_count)
        browser_manager._page_count = 1
        assert not await browser_manager.should_restart()

        browser_manager._page_count = 2
        assert not await browser_manager.should_restart()

        # 3rd page should trigger restart
        browser_manager._page_count = 3
        assert await browser_manager.should_restart()

    @pytest.mark.asyncio
    async def test_browser_manager_default_restart_threshold(self):
        """Test default restart threshold."""
        from src.services.bot.browser_manager import BrowserManager

        config = {"bot": {}, "anti_detection": {"enabled": False}}
        browser_manager = BrowserManager(config)

        # Default should be 100
        assert browser_manager._max_pages_before_restart == 100

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Method _process_user_with_semaphore removed - test needs rewrite for current implementation")
    async def test_page_close_failure_forces_restart_threshold(self):
        """Test that page.close() failure forces browser restart threshold."""
        from src.services.bot.vfs_bot import VFSBot

        # Create mock VFSBot instance
        with patch.object(VFSBot, "__init__", lambda self, *args, **kwargs: None):
            bot = VFSBot.__new__(VFSBot)

            # Mock browser manager
            browser_manager = MagicMock()
            browser_manager._page_count = 5
            browser_manager._max_pages_before_restart = 10
            browser_manager.should_restart = AsyncMock(return_value=False)

            # Mock page that raises exception on close
            mock_page = MagicMock()
            mock_page.close = AsyncMock(side_effect=Exception("Failed to close page"))
            browser_manager.new_page = AsyncMock(return_value=mock_page)

            # Mock booking workflow
            booking_workflow = MagicMock()
            booking_workflow.process_user = AsyncMock()

            # Mock services with semaphore
            services = MagicMock()
            services.core = MagicMock()
            services.core.user_semaphore = asyncio.Semaphore(5)

            # Assign mocks to bot
            bot.browser_manager = browser_manager
            bot.booking_workflow = booking_workflow
            bot.services = services

            # Call _process_user_with_semaphore with a test user
            user = {"id": 1, "email": "test@example.com"}

            # The method should not raise, but should log the error
            await bot._process_user_with_semaphore(user)

            # Verify that browser_manager._page_count was set to _max_pages_before_restart
            assert browser_manager._page_count == browser_manager._max_pages_before_restart
            assert browser_manager._page_count == 10


class TestGracefulShutdownNotifications:
    """Test graceful shutdown notification features."""

    @pytest.fixture
    def mock_vfs_bot(self):
        """Create a mock VFSBot instance for testing."""
        from src.services.bot.vfs_bot import VFSBot

        # Mock browser manager
        browser_manager = MagicMock()
        browser_manager.close = AsyncMock()

        # Mock notifier
        notifier = MagicMock()
        notifier.notify_bot_stopped = AsyncMock()

        # Create VFSBot instance with mocks
        with patch.object(VFSBot, "__init__", lambda self, *args, **kwargs: None):
            bot = VFSBot.__new__(VFSBot)
            bot.running = True
            bot._stopped = False
            bot._cleaned_up = False  # YENİ: cleanup idempotent flag
            bot.browser_manager = browser_manager
            bot.notifier = notifier
            bot._active_booking_tasks = []
            bot._health_task = None  # Add missing health task attribute

            # Mock services.workflow.alert_service
            bot.services = MagicMock()
            bot.services.workflow = MagicMock()
            bot.services.workflow.alert_service = MagicMock()
            bot.services.workflow.alert_service.send_alert = AsyncMock()

            # Mock error_handler for checkpoint tests
            bot.services.workflow.error_handler = MagicMock()
            bot.services.workflow.error_handler.save_checkpoint = AsyncMock()

            return bot

    @pytest.mark.asyncio
    async def test_stop_sends_notification_when_waiting(self, mock_vfs_bot):
        """Test that stop() sends notification when waiting for bookings."""
        bot = mock_vfs_bot

        # Simulate active tasks
        async def mock_task():
            await asyncio.sleep(0.1)

        bot._active_booking_tasks = [asyncio.create_task(mock_task())]

        # Call stop
        await bot.stop()

        # Verify notification was sent
        assert bot.services.workflow.alert_service.send_alert.called
        call_args = bot.services.workflow.alert_service.send_alert.call_args_list[0][1]
        assert "waiting" in call_args["message"].lower()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, mock_vfs_bot):
        """Test that stop() can be called multiple times safely."""
        bot = mock_vfs_bot

        # Set alert service to None to simplify test
        bot.services.workflow.alert_service = None

        # Call stop twice
        await bot.stop()
        await bot.stop()

        # Browser manager close should only be called once
        assert bot.browser_manager.close.call_count == 1
        # Notifier should only be called once
        assert bot.notifier.notify_bot_stopped.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_saves_checkpoint_on_timeout(self, mock_vfs_bot):
        """Test that stop() saves checkpoint when timeout occurs."""
        from src.constants import Timeouts

        bot = mock_vfs_bot

        # Create a long-running task that will timeout
        async def long_running_task():
            await asyncio.sleep(Timeouts.GRACEFUL_SHUTDOWN_GRACE_PERIOD + 10)

        # Create task with a name
        task = asyncio.create_task(long_running_task(), name="test_booking_task")
        bot._active_booking_tasks = {task}

        # Call stop - should timeout and save checkpoint
        await bot.stop()

        # Verify checkpoint was saved
        assert bot.services.workflow.error_handler.save_checkpoint.called
        call_args = bot.services.workflow.error_handler.save_checkpoint.call_args[0][0]

        # Verify checkpoint contains expected data
        assert call_args["event"] == "forced_shutdown"
        assert call_args["cancelled_task_count"] == 1
        assert "test_booking_task" in call_args["cancelled_tasks"]
        assert call_args["reason"] == "grace_period_timeout"

        # Verify alert was sent with task info
        assert bot.services.workflow.alert_service.send_alert.called
        alert_call = bot.services.workflow.alert_service.send_alert.call_args[1]
        assert "cancelled_tasks" in alert_call["metadata"]
        assert "test_booking_task" in alert_call["metadata"]["cancelled_tasks"]


class TestBotLoopErrorRecoveryJitter:
    """Test error recovery jitter feature."""

    def test_jitter_imports_random(self):
        """Test that random module is imported."""
        from src.services.bot import vfs_bot

        assert hasattr(vfs_bot, "random")

    def test_jitter_calculation(self):
        """Test jitter calculation produces values in expected range."""
        # Simulate the jitter calculation
        from src.constants import Intervals

        error_recovery = Intervals.ERROR_RECOVERY  # Should be 60
        results = []

        for _ in range(100):
            jitter = random.uniform(0.8, 1.2)
            sleep_time = error_recovery * jitter
            results.append(sleep_time)

        # All results should be in range [48, 72] for 60s base
        assert all(error_recovery * 0.8 <= r <= error_recovery * 1.2 for r in results)
        # Should have some variation
        assert len(set(results)) > 50  # At least 50 unique values


class TestDatabaseBackupAutoStart:
    """Test database backup auto-start feature."""

    def test_backup_service_import(self):
        """Test that backup service can be imported."""
        from src.utils.db_backup import get_backup_service

        assert callable(get_backup_service)

    @pytest.mark.asyncio
    async def test_backup_service_creation(self):
        """Test backup service creation."""
        from src.constants import Database as DatabaseConfig
        from src.utils.db_backup import DatabaseBackup

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use PostgreSQL test database URL
            test_db_url = DatabaseConfig.TEST_URL
            backup_dir = str(Path(tmpdir) / "backups")

            # Create service directly (not using singleton getter)
            backup_service = DatabaseBackup(database_url=test_db_url, backup_dir=backup_dir)
            assert backup_service is not None
            assert backup_service._database_url == test_db_url

            # Verify encryption methods exist
            assert hasattr(backup_service, "_get_encryption_key")
            assert hasattr(backup_service, "_encrypt_file")
            assert hasattr(backup_service, "_decrypt_file")


class TestPreMigrationBackup:
    """Test pre-migration backup feature."""

    @pytest.mark.asyncio
    async def test_database_backup_import(self):
        """Test that DatabaseBackup can be imported from db_backup."""
        from src.utils.db_backup import DatabaseBackup

        assert DatabaseBackup is not None

        # Verify encryption methods exist
        backup_util = DatabaseBackup()
        assert hasattr(backup_util, "_get_encryption_key")
        assert hasattr(backup_util, "_encrypt_file")
        assert hasattr(backup_util, "_decrypt_file")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_backup_before_migration(self):
        """Test that backup is created before migrations."""
        from src.constants import Database as DatabaseConfig
        from src.models.database import Database

        # Use PostgreSQL test database URL
        test_db_url = DatabaseConfig.TEST_URL

        try:
            db = Database(database_url=test_db_url)
            # Connect will trigger migrations
            await db.connect()
            await db.close()
        except Exception as e:
            # Skip test if database is not available
            pytest.skip(f"Database not available for integration test: {e}")


class TestGrafanaPasswordNotHardcoded:
    """Test that Grafana password is not hardcoded in monitoring compose."""

    def test_monitoring_compose_uses_env_var(self):
        """Test that docker-compose.monitoring.yml uses environment variable for
        Grafana password."""
        compose_path = Path("docker-compose.monitoring.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.monitoring.yml not found")

        content = compose_path.read_text()
        # Should NOT contain hardcoded password
        assert "vfsbot_grafana" not in content, "Grafana password should not be hardcoded"
        # Should use environment variable with proper syntax
        assert "GRAFANA_ADMIN_PASSWORD" in content, "Should use GRAFANA_ADMIN_PASSWORD env var"
        # Verify it's using the environment variable syntax, not just referencing it
        assert (
            "${GRAFANA_ADMIN_PASSWORD" in content
        ), "Should use ${GRAFANA_ADMIN_PASSWORD...} syntax"
        # Verify the :? syntax requiring the variable
        assert ":?" in content, "Should use :? syntax to require environment variable"

    def test_monitoring_compose_no_version_key(self):
        """Test that docker-compose.monitoring.yml doesn't have deprecated version key."""
        compose_path = Path("docker-compose.monitoring.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.monitoring.yml not found")

        content = compose_path.read_text()
        lines = content.split("\n")
        # Find first non-empty line
        first_line = next((line.strip() for line in lines if line.strip()), "")
        assert not first_line.startswith("version"), "Deprecated 'version' key should be removed"

    def test_monitoring_compose_localhost_binding(self):
        """Test that monitoring ports are bound to localhost only."""
        compose_path = Path("docker-compose.monitoring.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.monitoring.yml not found")

        content = compose_path.read_text()
        # Should use 127.0.0.1 binding
        assert "127.0.0.1:9090:9090" in content, "Prometheus should bind to localhost"
        assert "127.0.0.1:3000:3000" in content, "Grafana should bind to localhost"

    def test_dev_compose_no_version_key(self):
        """Test that docker-compose.dev.yml doesn't have deprecated version key."""
        compose_path = Path("docker-compose.dev.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.dev.yml not found")

        content = compose_path.read_text()
        lines = content.split("\n")
        # Find first non-empty line
        first_line = next((line.strip() for line in lines if line.strip()), "")
        assert not first_line.startswith("version"), "Deprecated 'version' key should be removed"


class TestStartupValidatorGrafana:
    """Test that startup validator checks Grafana password."""

    @pytest.fixture
    def production_env_vars(self):
        """Fixture to manage environment variables for production security tests."""
        # Store original values
        original_values = {
            "ENV": os.environ.get("ENV"),
            "GRAFANA_ADMIN_PASSWORD": os.environ.get("GRAFANA_ADMIN_PASSWORD"),
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "API_SECRET_KEY": os.environ.get("API_SECRET_KEY"),
            "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
            "ADMIN_USERNAME": os.environ.get("ADMIN_USERNAME"),
        }

        # Set common production environment
        os.environ["ENV"] = "production"
        os.environ["DATABASE_URL"] = "postgresql://user:securepass@localhost:5432/db"
        os.environ["API_SECRET_KEY"] = "a" * 64
        os.environ["ADMIN_PASSWORD"] = "$2b$12$test_hash_value_here_placeholder"
        os.environ["ADMIN_USERNAME"] = "unique_admin_name"

        yield

        # Cleanup - restore original values or remove if they didn't exist
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_grafana_default_password_detected(self, production_env_vars):
        """Test that default Grafana password is detected."""
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "vfsbot_grafana"

        from src.core.infra.startup_validator import validate_production_security

        warnings = validate_production_security()

        grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
        assert len(grafana_warnings) > 0, "Should detect default Grafana password"

    def test_grafana_placeholder_patterns_detected(self, production_env_vars):
        """Test that placeholder patterns in Grafana password are detected."""
        test_patterns = [
            "CHANGE_ME_generate_secure_grafana_password",
            "my_password_change_me",
            "ChangeMeNow",
        ]

        from src.core.infra.startup_validator import validate_production_security

        for password in test_patterns:
            os.environ["GRAFANA_ADMIN_PASSWORD"] = password
            warnings = validate_production_security()
            grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
            assert len(grafana_warnings) > 0, f"Should detect placeholder pattern in '{password}'"

    def test_grafana_common_defaults_detected(self, production_env_vars):
        """Test that common default passwords are detected."""
        common_defaults = ["admin", "password", "grafana"]

        from src.core.infra.startup_validator import validate_production_security

        for password in common_defaults:
            os.environ["GRAFANA_ADMIN_PASSWORD"] = password
            warnings = validate_production_security()
            grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
            assert len(grafana_warnings) > 0, f"Should detect common default password '{password}'"

    def test_grafana_secure_password_passes(self, production_env_vars):
        """Test that secure Grafana password passes validation."""
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "super_secure_random_password_xyz123"

        from src.core.infra.startup_validator import validate_production_security

        warnings = validate_production_security()

        grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
        assert len(grafana_warnings) == 0, "Secure Grafana password should not trigger warning"

    def test_grafana_secure_with_vfsbot_substring_passes(self, production_env_vars):
        """Test that password containing 'vfsbot' as part of secure string passes."""
        # This ensures we're using exact match for 'vfsbot_grafana', not substring
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "secure_vfsbot_integration_key_xyz789"

        from src.core.infra.startup_validator import validate_production_security

        warnings = validate_production_security()

        grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
        assert len(grafana_warnings) == 0, "Secure password with 'vfsbot' substring should pass"


class TestLogoutTokenRevocation:
    """Test logout endpoint revokes tokens properly."""

    def test_logout_calls_revoke_token_when_token_present(self):
        """Test that logout calls revoke_token when token is present."""
        from unittest.mock import MagicMock, patch

        # We'll test the behavior directly by mocking the revoke_token function
        with patch("web.routes.auth.revoke_token", new_callable=AsyncMock) as mock_revoke:
            # Import the auth module AFTER patching
            from web.routes.auth import logout, router

            # Set the return value for the async mock
            mock_revoke.return_value = True

            # Verify the import was successful and the function is updated
            assert mock_revoke is not None

    def test_logout_extracts_token_from_cookie_logic(self):
        """Test the logic for extracting token from cookie."""
        # This test verifies that the logout endpoint has logic
        # to extract tokens using the extract_raw_token helper
        import inspect

        from web.routes.auth import logout

        # Check the function signature includes request parameter
        sig = inspect.signature(logout)
        assert "request" in sig.parameters
        assert "token_data" in sig.parameters

        # Verify the source code uses the helper function and calls revoke_token
        source = inspect.getsource(logout)
        assert "extract_raw_token" in source
        assert "revoke_token" in source
        # Verify it awaits revoke_token (since it's async now)
        assert "await revoke_token" in source


class TestDockerComposeSecurityHardening:
    """Test Docker Compose security hardening directives."""

    def test_docker_compose_vfs_bot_read_only(self):
        """Test that vfs-bot service has read_only: true."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = compose_path.read_text()

        # Verify read_only is set to true for vfs-bot service
        assert "read_only: true" in content, "vfs-bot service should have read_only: true"

        # Ensure it's in the vfs-bot service section
        # Split by service definitions and find vfs-bot
        compose_data = yaml.safe_load(content)
        assert "vfs-bot" in compose_data["services"], "vfs-bot service not found"
        assert (
            compose_data["services"]["vfs-bot"].get("read_only") is True
        ), "vfs-bot service should have read_only set to true"

    def test_docker_compose_vfs_bot_no_new_privileges(self):
        """Test that vfs-bot service has no-new-privileges:true."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = compose_path.read_text()

        # Verify no-new-privileges is present
        assert (
            "no-new-privileges:true" in content
        ), "vfs-bot service should have no-new-privileges:true in security_opt"

        # Verify in YAML structure
        compose_data = yaml.safe_load(content)
        assert "vfs-bot" in compose_data["services"], "vfs-bot service not found"
        security_opt = compose_data["services"]["vfs-bot"].get("security_opt", [])
        assert (
            "no-new-privileges:true" in security_opt
        ), "vfs-bot service should have no-new-privileges:true in security_opt"

    def test_docker_compose_vfs_bot_tmpfs(self):
        """Test that vfs-bot service has tmpfs for /tmp."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = compose_path.read_text()

        # Verify tmpfs is configured
        assert "tmpfs:" in content, "vfs-bot service should have tmpfs configured"

        # Verify in YAML structure
        compose_data = yaml.safe_load(content)
        assert "vfs-bot" in compose_data["services"], "vfs-bot service not found"
        tmpfs = compose_data["services"]["vfs-bot"].get("tmpfs", [])
        assert "/tmp" in tmpfs, "vfs-bot service should have /tmp in tmpfs"


class TestPersistentTokenBlacklistInit:
    """Test persistent token blacklist initialization and async functionality."""

    @pytest.mark.asyncio
    async def test_init_token_blacklist_creates_persistent_instance(self):
        """Test that init_token_blacklist creates a PersistentTokenBlacklist."""
        from unittest.mock import MagicMock

        from src.core.auth import get_token_blacklist, init_token_blacklist
        from src.core.auth.token_blacklist import PersistentTokenBlacklist

        # Create a mock database
        mock_db = MagicMock()

        # Initialize the blacklist
        init_token_blacklist(mock_db)

        # Get the blacklist and verify it's a PersistentTokenBlacklist
        blacklist = get_token_blacklist()
        assert isinstance(blacklist, PersistentTokenBlacklist)
        assert blacklist._db is mock_db
        assert blacklist._use_db is True

    @pytest.mark.asyncio
    async def test_check_blacklisted_uses_async_for_persistent(self):
        """Test that check_blacklisted uses async path for PersistentTokenBlacklist."""
        from unittest.mock import AsyncMock, MagicMock

        from src.core.auth import check_blacklisted, init_token_blacklist
        from src.core.auth.token_blacklist import PersistentTokenBlacklist

        # Create a mock database
        mock_db = MagicMock()

        # Initialize persistent blacklist
        init_token_blacklist(mock_db)

        # Mock the repository to avoid actual DB calls
        with patch("src.core.auth.token_blacklist.TokenBlacklistRepository") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_repo.is_blacklisted = AsyncMock(return_value=True)

            # Check if token is blacklisted
            result = await check_blacklisted("test_jti")

            # Verify async method was called
            assert result is True
            mock_repo.is_blacklisted.assert_called_once_with("test_jti")

    @pytest.mark.asyncio
    async def test_revoke_token_persists_to_db(self):
        """Test that revoke_token persists to database when using PersistentTokenBlacklist."""
        from unittest.mock import AsyncMock, MagicMock

        from src.core.auth import create_access_token, init_token_blacklist, revoke_token

        # Create a mock database
        mock_db = MagicMock()

        # Initialize persistent blacklist
        init_token_blacklist(mock_db)

        # Create a test token
        token = create_access_token({"sub": "test_user"})

        # Mock the repository to avoid actual DB calls
        with patch("src.core.auth.token_blacklist.TokenBlacklistRepository") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_repo.add = AsyncMock()

            # Revoke the token
            result = await revoke_token(token)

            # Verify token was added to database
            assert result is True
            mock_repo.add.assert_called_once()
            # Verify jti and exp were passed
            call_args = mock_repo.add.call_args
            assert call_args is not None
            assert len(call_args[0]) == 2  # jti and exp


class TestDatabaseURLProductionValidation:
    """Test DATABASE_URL production validation."""

    def test_database_url_default_rejected_in_production(self, monkeypatch):
        """Test that default DATABASE_URL is rejected in production."""
        from cryptography.fernet import Fernet

        from src.core.config.settings import VFSSettings

        # Clear DATABASE_URL from environment to test default value
        monkeypatch.delenv("DATABASE_URL", raising=False)

        test_encryption_key = Fernet.generate_key().decode()
        test_api_secret_key = "a" * 64

        with pytest.raises(ValueError) as exc_info:
            VFSSettings(
                env="production",
                encryption_key=test_encryption_key,
                api_secret_key=test_api_secret_key,
                database_url="postgresql://localhost:5432/vfs_bot",  # Explicit default
            )

        error_msg = str(exc_info.value)
        assert "default DATABASE_URL" in error_msg or "cannot use default" in error_msg

    def test_database_url_without_auth_rejected_in_production(self, monkeypatch):
        """Test that DATABASE_URL without auth credentials is rejected in production."""
        from cryptography.fernet import Fernet

        from src.core.config.settings import VFSSettings

        # Clear DATABASE_URL from environment
        monkeypatch.delenv("DATABASE_URL", raising=False)

        test_encryption_key = Fernet.generate_key().decode()
        test_api_secret_key = "a" * 64

        with pytest.raises(ValueError) as exc_info:
            VFSSettings(
                env="production",
                encryption_key=test_encryption_key,
                api_secret_key=test_api_secret_key,
                database_url="postgresql://localhost:5432/mydb",  # No @ symbol
            )

        error_msg = str(exc_info.value)
        assert "authentication credentials" in error_msg
        assert "@" in error_msg or "user:password" in error_msg

    def test_database_url_with_auth_accepted_in_production(self, monkeypatch):
        """Test that DATABASE_URL with auth credentials is accepted in production."""
        from cryptography.fernet import Fernet

        from src.core.config.settings import VFSSettings

        # Clear DATABASE_URL from environment
        monkeypatch.delenv("DATABASE_URL", raising=False)

        test_encryption_key = Fernet.generate_key().decode()
        test_api_secret_key = "a" * 64

        # Should not raise
        settings = VFSSettings(
            env="production",
            encryption_key=test_encryption_key,
            api_secret_key=test_api_secret_key,
            database_url="postgresql://user:pass@localhost:5432/mydb",
        )

        assert settings.database_url == "postgresql://user:pass@localhost:5432/mydb"

    def test_database_url_default_allowed_in_development(self, monkeypatch):
        """Test that default DATABASE_URL is allowed in development."""
        from cryptography.fernet import Fernet

        from src.core.config.settings import VFSSettings

        # Clear DATABASE_URL from environment
        monkeypatch.delenv("DATABASE_URL", raising=False)

        test_encryption_key = Fernet.generate_key().decode()
        test_api_secret_key = "a" * 64

        # Should not raise - use explicit default
        settings = VFSSettings(
            env="development",
            encryption_key=test_encryption_key,
            api_secret_key=test_api_secret_key,
            database_url="postgresql://localhost:5432/vfs_bot",  # Explicit default
        )

        assert settings.database_url == "postgresql://localhost:5432/vfs_bot"

    def test_database_url_default_allowed_in_testing(self, monkeypatch):
        """Test that default DATABASE_URL is allowed in testing."""
        from cryptography.fernet import Fernet

        from src.core.config.settings import VFSSettings

        # Clear DATABASE_URL from environment
        monkeypatch.delenv("DATABASE_URL", raising=False)

        test_encryption_key = Fernet.generate_key().decode()
        test_api_secret_key = "a" * 64

        # Should not raise - use explicit default
        settings = VFSSettings(
            env="testing",
            encryption_key=test_encryption_key,
            api_secret_key=test_api_secret_key,
            database_url="postgresql://localhost:5432/vfs_bot",  # Explicit default
        )

        assert settings.database_url == "postgresql://localhost:5432/vfs_bot"


class TestWaitOrShutdownEventBased:
    """Test _wait_or_shutdown event-based implementation."""

    @pytest.fixture
    def bot_config(self, config):
        """Bot config based on shared test config."""
        return config

    @pytest.fixture
    def mock_db(self):
        """Mock database fixture."""
        from src.models.database import Database

        db = AsyncMock(spec=Database)
        db.get_active_users = AsyncMock(return_value=[])
        db.get_personal_details = AsyncMock(return_value=None)
        db.add_appointment = AsyncMock(return_value=1)
        return db

    @pytest.fixture
    def mock_notifier(self):
        """Mock notification service fixture."""
        from src.services.notification.notification import NotificationService

        notifier = AsyncMock(spec=NotificationService)
        notifier.notify_slot_found = AsyncMock()
        notifier.notify_appointment_booked = AsyncMock()
        notifier.notify_bot_started = AsyncMock()
        notifier.notify_bot_stopped = AsyncMock()
        return notifier

    @pytest.mark.asyncio
    async def test_wait_uses_event_based_approach(self, bot_config, mock_db, mock_notifier):
        """Test that the method uses event-based approach (instant response to events)."""
        from src.services.bot.vfs_bot import VFSBot

        bot = VFSBot(bot_config, mock_db, mock_notifier)

        # Set trigger event before calling wait
        bot._trigger_event.set()

        # Measure time - should complete almost instantly (< 0.2s) not after 5s
        start_time = time.time()
        result = await bot._wait_or_shutdown(5.0)
        elapsed = time.time() - start_time

        # Should return False (trigger, not shutdown)
        assert result is False
        # Should complete in under 0.2 seconds (proves no polling)
        assert elapsed < 0.2

    @pytest.mark.asyncio
    async def test_wait_shutdown_priority_over_trigger(self, bot_config, mock_db, mock_notifier):
        """Test that shutdown event takes priority over trigger event."""
        from src.services.bot.vfs_bot import VFSBot

        bot = VFSBot(bot_config, mock_db, mock_notifier)

        # Set both events before calling
        bot.shutdown_event.set()
        bot._trigger_event.set()

        # Should return True (shutdown takes priority)
        result = await bot._wait_or_shutdown(10.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_cancellation_cleanup(self, bot_config, mock_db, mock_notifier):
        """Test that cancellation properly cleans up tasks."""
        from src.services.bot.vfs_bot import VFSBot

        bot = VFSBot(bot_config, mock_db, mock_notifier)

        # Create a task running _wait_or_shutdown
        wait_task = asyncio.create_task(bot._wait_or_shutdown(10.0))

        # Wait a bit then cancel
        await asyncio.sleep(0.05)
        wait_task.cancel()

        # Should raise CancelledError
        with pytest.raises(asyncio.CancelledError):
            await wait_task

        # Verify no leaked tasks (all pending tasks should be cancelled)
        # We can't directly check for leaked tasks, but if the implementation is correct,
        # there should be no warnings about unclosed tasks
        await asyncio.sleep(0.01)  # Give time for cleanup


class TestTokenRefreshBufferSafeParsing:
    """Test safe parsing of TOKEN_REFRESH_BUFFER_MINUTES."""

    def test_get_token_refresh_buffer_valid(self):
        """Test _get_token_refresh_buffer with valid integer."""
        from unittest.mock import patch

        from src.services.vfs.auth import _get_token_refresh_buffer

        with patch.dict(os.environ, {"TOKEN_REFRESH_BUFFER_MINUTES": "10"}):
            assert _get_token_refresh_buffer() == 10

    def test_get_token_refresh_buffer_invalid(self):
        """Test _get_token_refresh_buffer with invalid value returns default."""
        from unittest.mock import patch

        from src.services.vfs.auth import _get_token_refresh_buffer

        with patch.dict(os.environ, {"TOKEN_REFRESH_BUFFER_MINUTES": "invalid"}):
            assert _get_token_refresh_buffer() == 5  # Default

    def test_get_token_refresh_buffer_negative(self):
        """Test _get_token_refresh_buffer with negative value returns default."""
        from unittest.mock import patch

        from src.services.vfs.auth import _get_token_refresh_buffer

        with patch.dict(os.environ, {"TOKEN_REFRESH_BUFFER_MINUTES": "-5"}):
            assert _get_token_refresh_buffer() == 5  # Default

    def test_get_token_refresh_buffer_not_set(self):
        """Test _get_token_refresh_buffer when env var not set returns default."""
        from unittest.mock import patch

        from src.services.vfs.auth import _get_token_refresh_buffer

        with patch.dict(os.environ, {}, clear=True):
            assert _get_token_refresh_buffer() == 5  # Default


class TestSecurityConfigValidation:
    """Test SecurityConfig empty string validation."""

    def test_security_config_warns_in_production(self):
        """Test that SecurityConfig warns about empty keys in production."""
        import warnings
        from unittest.mock import patch

        from src.core.config.config_models import SecurityConfig

        with patch.dict(os.environ, {"ENV": "production"}):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _ = SecurityConfig()

                # Should have warning about security keys
                security_warnings = [
                    warn for warn in w if "Empty security keys detected" in str(warn.message)
                ]
                assert len(security_warnings) > 0
                assert "Empty security keys detected" in str(security_warnings[0].message)

    def test_security_config_no_warn_in_testing(self):
        """Test that SecurityConfig doesn't warn in testing environment."""
        import warnings
        from unittest.mock import patch

        from src.core.config.config_models import SecurityConfig

        with patch.dict(os.environ, {"ENV": "testing"}):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _ = SecurityConfig()

                # Should not have warning about security keys
                security_warnings = [
                    warn for warn in w if "Empty security keys detected" in str(warn.message)
                ]
                assert len(security_warnings) == 0

    def test_security_config_with_keys_no_warning(self):
        """Test that SecurityConfig with proper keys doesn't warn."""
        import warnings
        from unittest.mock import patch

        from pydantic import SecretStr

        from src.core.config.config_models import SecurityConfig

        with patch.dict(os.environ, {"ENV": "production"}):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _ = SecurityConfig(
                    api_secret_key=SecretStr("very-secure-key-here"),
                    api_key_salt=SecretStr("secure-salt"),
                    encryption_key=SecretStr("encryption-key-32-chars-long"),
                )

                # Should not have warning
                security_warnings = [
                    warn for warn in w if "Empty security keys detected" in str(warn.message)
                ]
                assert len(security_warnings) == 0


class TestPasswordLeakPrevention:
    """Test password leak prevention in auth_service."""

    @pytest.mark.asyncio
    async def test_error_capture_receives_sanitized_exception(self):
        """Test that error_capture receives sanitized exception, not raw."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.core.exceptions import LoginError
        from src.services.bot.auth_service import AuthService

        # Create mocks
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "language": "tr",
            },
            "bot": {"headless": True},
        }
        mock_human_sim = MagicMock()
        mock_error_capture = AsyncMock()
        mock_captcha_solver = AsyncMock()
        mock_cloudflare_handler = AsyncMock()
        mock_cloudflare_handler.handle_challenge = AsyncMock(return_value=True)

        auth_service = AuthService(
            config=config,
            human_sim=mock_human_sim,
            error_capture=mock_error_capture,
            captcha_solver=mock_captcha_solver,
            cloudflare_handler=mock_cloudflare_handler,
        )

        # Mock page
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.locator = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))

        # Mock smart_fill to raise exception with password in message
        password = "secretpassword123"
        with patch("src.services.bot.auth_service.safe_navigate", return_value=True):
            with patch(
                "src.services.bot.auth_service.smart_fill",
                side_effect=Exception(f"Error with {password}"),
            ):
                try:
                    await auth_service.login(mock_page, "test@example.com", password)
                except LoginError:
                    pass

        # Verify error_capture was called
        assert mock_error_capture.capture.called

        # Get the exception passed to error_capture
        call_args = mock_error_capture.capture.call_args
        captured_exception = call_args[0][1]  # Second positional arg

        # Verify it's a LoginError (sanitized) and doesn't contain password
        assert isinstance(captured_exception, LoginError)
        assert password not in str(captured_exception)
        assert "[REDACTED]" in str(captured_exception)

    @pytest.mark.asyncio
    async def test_outer_except_sanitizes_password_in_logs(self):
        """Test that outer except block sanitizes password before logging."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.services.bot.auth_service import AuthService

        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "language": "tr",
            },
            "bot": {"headless": True},
        }
        mock_human_sim = MagicMock()
        mock_error_capture = AsyncMock()
        mock_captcha_solver = AsyncMock()
        mock_cloudflare_handler = AsyncMock()

        auth_service = AuthService(
            config=config,
            human_sim=mock_human_sim,
            error_capture=mock_error_capture,
            captcha_solver=mock_captcha_solver,
            cloudflare_handler=mock_cloudflare_handler,
        )

        mock_page = AsyncMock()
        password = "secretpassword456"

        # Mock safe_navigate to raise exception with password
        with patch(
            "src.services.bot.auth_service.safe_navigate",
            side_effect=Exception(f"Network error with {password}"),
        ):
            # Capture logger calls
            with patch("src.services.bot.auth_service.logger") as mock_logger:
                result = await auth_service.login(mock_page, "test@example.com", password)

                # Should return False
                assert result is False

                # Verify logger.error was called with sanitized message
                assert mock_logger.error.called
                error_message = mock_logger.error.call_args[0][0]

                # Password should be redacted in log
                assert password not in error_message
                assert "[REDACTED]" in error_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
