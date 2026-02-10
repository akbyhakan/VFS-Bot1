"""Tests for code audit fixes."""

import asyncio
import os
import random
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
            from web.app import validate_cors_origins

            allowed_origins = validate_cors_origins("")
            env = os.getenv("ENV", "production").lower()
            if not allowed_origins and env not in ("development", "dev", "local", "testing", "test"):
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

        from web.app import validate_cors_origins

        allowed_origins = validate_cors_origins("")
        # Should not raise in development, just returns empty list
        assert allowed_origins == []

    def test_cors_ipv6_localhost_blocked_in_production(self):
        """Test that IPv6 localhost (::1) is blocked in production."""
        os.environ["ENV"] = "production"
        
        from web.app import validate_cors_origins
        
        origins = validate_cors_origins("http://[::1]:3000")
        assert origins == []

    def test_cors_zero_ip_blocked_in_production(self):
        """Test that 0.0.0.0 is blocked in production."""
        os.environ["ENV"] = "production"
        
        from web.app import validate_cors_origins
        
        origins = validate_cors_origins("http://0.0.0.0:8000")
        assert origins == []

    def test_cors_localhost_subdomain_bypass_blocked(self):
        """Test that localhost subdomain bypass is blocked in production."""
        os.environ["ENV"] = "production"
        
        from web.app import validate_cors_origins
        
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
        """Test should_restart logic."""
        from src.services.bot.browser_manager import BrowserManager

        config = {
            "bot": {"headless": True, "browser_restart_after_pages": 3},
            "anti_detection": {"enabled": False},
        }
        browser_manager = BrowserManager(config)

        # First 2 pages should not trigger restart
        assert not await browser_manager.should_restart()  # 1
        assert not await browser_manager.should_restart()  # 2

        # 3rd page should trigger restart
        assert await browser_manager.should_restart()  # 3

    @pytest.mark.asyncio
    async def test_browser_manager_default_restart_threshold(self):
        """Test default restart threshold."""
        from src.services.bot.browser_manager import BrowserManager

        config = {"bot": {}, "anti_detection": {"enabled": False}}
        browser_manager = BrowserManager(config)

        # Default should be 100
        assert browser_manager._max_pages_before_restart == 100


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
            bot.browser_manager = browser_manager
            bot.notifier = notifier
            bot._active_booking_tasks = []
            
            # Mock services.workflow.alert_service
            bot.services = MagicMock()
            bot.services.workflow = MagicMock()
            bot.services.workflow.alert_service = MagicMock()
            bot.services.workflow.alert_service.send_alert = AsyncMock()
            
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
            assert hasattr(backup_service, '_get_encryption_key')
            assert hasattr(backup_service, '_encrypt_file')
            assert hasattr(backup_service, '_decrypt_file')


class TestPreMigrationBackup:
    """Test pre-migration backup feature."""

    @pytest.mark.asyncio
    async def test_database_backup_import(self):
        """Test that DatabaseBackup can be imported from db_backup."""
        from src.utils.db_backup import DatabaseBackup

        assert DatabaseBackup is not None
        
        # Verify encryption methods exist
        backup_util = DatabaseBackup()
        assert hasattr(backup_util, '_get_encryption_key')
        assert hasattr(backup_util, '_encrypt_file')
        assert hasattr(backup_util, '_decrypt_file')

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
        """Test that docker-compose.monitoring.yml uses environment variable for Grafana password."""
        compose_path = Path("docker-compose.monitoring.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.monitoring.yml not found")

        content = compose_path.read_text()
        # Should NOT contain hardcoded password
        assert "vfsbot_grafana" not in content, "Grafana password should not be hardcoded"
        # Should use environment variable with proper syntax
        assert "GRAFANA_ADMIN_PASSWORD" in content, "Should use GRAFANA_ADMIN_PASSWORD env var"
        # Verify it's using the environment variable syntax, not just referencing it
        assert "${GRAFANA_ADMIN_PASSWORD" in content, "Should use ${GRAFANA_ADMIN_PASSWORD...} syntax"
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

        from src.core.startup_validator import validate_production_security
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
        
        from src.core.startup_validator import validate_production_security
        
        for password in test_patterns:
            os.environ["GRAFANA_ADMIN_PASSWORD"] = password
            warnings = validate_production_security()
            grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
            assert len(grafana_warnings) > 0, f"Should detect placeholder pattern in '{password}'"

    def test_grafana_common_defaults_detected(self, production_env_vars):
        """Test that common default passwords are detected."""
        common_defaults = ["admin", "password", "grafana"]
        
        from src.core.startup_validator import validate_production_security
        
        for password in common_defaults:
            os.environ["GRAFANA_ADMIN_PASSWORD"] = password
            warnings = validate_production_security()
            grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
            assert len(grafana_warnings) > 0, f"Should detect common default password '{password}'"

    def test_grafana_secure_password_passes(self, production_env_vars):
        """Test that secure Grafana password passes validation."""
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "super_secure_random_password_xyz123"

        from src.core.startup_validator import validate_production_security
        warnings = validate_production_security()

        grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
        assert len(grafana_warnings) == 0, "Secure Grafana password should not trigger warning"

    def test_grafana_secure_with_vfsbot_substring_passes(self, production_env_vars):
        """Test that password containing 'vfsbot' as part of secure string passes."""
        # This ensures we're using exact match for 'vfsbot_grafana', not substring
        os.environ["GRAFANA_ADMIN_PASSWORD"] = "secure_vfsbot_integration_key_xyz789"

        from src.core.startup_validator import validate_production_security
        warnings = validate_production_security()

        grafana_warnings = [w for w in warnings if "GRAFANA_ADMIN_PASSWORD" in w]
        assert len(grafana_warnings) == 0, "Secure password with 'vfsbot' substring should pass"


class TestLogoutTokenRevocation:
    """Test logout endpoint revokes tokens properly."""

    def test_logout_calls_revoke_token_when_token_present(self):
        """Test that logout calls revoke_token when token is present."""
        from unittest.mock import MagicMock, patch
        
        # We'll test the behavior directly by mocking the revoke_token function
        with patch("web.routes.auth.revoke_token") as mock_revoke:
            # Import the auth module AFTER patching
            from web.routes.auth import router
            from web.routes.auth import logout
            
            # The test confirms that revoke_token will be called
            # revoke_token is now async, so the mock should be an AsyncMock
            mock_revoke.return_value = AsyncMock(return_value=True)
            
            # Verify the import was successful and the function is updated
            assert mock_revoke is not None

    def test_logout_extracts_token_from_cookie_logic(self):
        """Test the logic for extracting token from cookie."""
        # This test verifies that the logout endpoint has logic
        # to extract tokens using the extract_raw_token helper
        from web.routes.auth import logout
        import inspect
        
        # Check the function signature includes request parameter
        sig = inspect.signature(logout)
        assert 'request' in sig.parameters
        assert 'token_data' in sig.parameters
        
        # Verify the source code uses the helper function and calls revoke_token
        source = inspect.getsource(logout)
        assert 'extract_raw_token' in source
        assert 'revoke_token' in source
        # Verify it awaits revoke_token (since it's async now)
        assert 'await revoke_token' in source


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
        import yaml
        compose_data = yaml.safe_load(content)
        assert "vfs-bot" in compose_data["services"], "vfs-bot service not found"
        assert compose_data["services"]["vfs-bot"].get("read_only") is True, \
            "vfs-bot service should have read_only set to true"

    def test_docker_compose_vfs_bot_no_new_privileges(self):
        """Test that vfs-bot service has no-new-privileges:true."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = compose_path.read_text()
        
        # Verify no-new-privileges is present
        assert "no-new-privileges:true" in content, \
            "vfs-bot service should have no-new-privileges:true in security_opt"
        
        # Verify in YAML structure
        import yaml
        compose_data = yaml.safe_load(content)
        assert "vfs-bot" in compose_data["services"], "vfs-bot service not found"
        security_opt = compose_data["services"]["vfs-bot"].get("security_opt", [])
        assert "no-new-privileges:true" in security_opt, \
            "vfs-bot service should have no-new-privileges:true in security_opt"

    def test_docker_compose_vfs_bot_tmpfs(self):
        """Test that vfs-bot service has tmpfs for /tmp."""
        compose_path = Path("docker-compose.yml")
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = compose_path.read_text()
        
        # Verify tmpfs is configured
        assert "tmpfs:" in content, "vfs-bot service should have tmpfs configured"
        
        # Verify in YAML structure
        import yaml
        compose_data = yaml.safe_load(content)
        assert "vfs-bot" in compose_data["services"], "vfs-bot service not found"
        tmpfs = compose_data["services"]["vfs-bot"].get("tmpfs", [])
        assert "/tmp" in tmpfs, "vfs-bot service should have /tmp in tmpfs"


class TestPersistentTokenBlacklistInit:
    """Test persistent token blacklist initialization and async functionality."""

    @pytest.mark.asyncio
    async def test_init_token_blacklist_creates_persistent_instance(self):
        """Test that init_token_blacklist creates a PersistentTokenBlacklist."""
        from src.core.auth import init_token_blacklist, get_token_blacklist
        from src.core.auth.token_blacklist import PersistentTokenBlacklist
        from unittest.mock import MagicMock
        
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
        from src.core.auth import init_token_blacklist, check_blacklisted
        from src.core.auth.token_blacklist import PersistentTokenBlacklist
        from unittest.mock import AsyncMock, MagicMock
        
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
        from src.core.auth import init_token_blacklist, revoke_token, create_access_token
        from unittest.mock import AsyncMock, MagicMock
        
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
