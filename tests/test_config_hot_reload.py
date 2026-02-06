"""Tests for configuration hot-reload service."""

import asyncio
import tempfile
from pathlib import Path

import pytest
import yaml

from src.core.config_hot_reload import ConfigHotReload, get_hot_reload_service


@pytest.mark.asyncio
class TestConfigHotReload:
    """Test cases for ConfigHotReload class."""

    async def test_initialization(self):
        """Test service initialization."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"test": "value"}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=5)

            assert service._config_path == Path(config_path)
            assert service._check_interval == 5
            assert len(service._callbacks) == 0
            assert service._running is False
        finally:
            Path(config_path).unlink()

    async def test_start_stop(self):
        """Test starting and stopping the service."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"test": "value"}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=1)

            # Start
            await service.start()
            assert service._running is True
            assert service._task is not None

            # Stop
            await service.stop()
            assert service._running is False
            assert service._task is None
        finally:
            Path(config_path).unlink()

    async def test_callback_registration(self):
        """Test registering reload callbacks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"test": "value"}, f)

        try:
            service = ConfigHotReload(config_path=config_path)

            def callback1(config):
                pass

            def callback2(config):
                pass

            service.on_reload(callback1)
            service.on_reload(callback2)

            assert len(service._callbacks) == 2
        finally:
            Path(config_path).unlink()

    async def test_config_change_detection(self):
        """Test that config changes are detected."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"version": 1}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=1)

            # Track callback invocations
            callback_invoked = asyncio.Event()
            received_config = {}

            def callback(config):
                received_config.update(config)
                callback_invoked.set()

            service.on_reload(callback)
            await service.start()

            # Wait a bit for initial state
            await asyncio.sleep(0.5)

            # Modify config file
            with open(config_path, "w") as f:
                yaml.dump({"version": 2, "new_key": "new_value"}, f)

            # Wait for callback
            try:
                await asyncio.wait_for(callback_invoked.wait(), timeout=5)
                assert received_config.get("version") == 2
                assert received_config.get("new_key") == "new_value"
            except asyncio.TimeoutError:
                pytest.fail("Callback not invoked after config change")
            finally:
                await service.stop()
        finally:
            Path(config_path).unlink()

    async def test_async_callback(self):
        """Test that async callbacks are supported."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"version": 1}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=1)

            callback_invoked = asyncio.Event()

            async def async_callback(config):
                await asyncio.sleep(0.1)  # Simulate async work
                callback_invoked.set()

            service.on_reload(async_callback)
            await service.start()

            await asyncio.sleep(0.5)

            # Modify config
            with open(config_path, "w") as f:
                yaml.dump({"version": 2}, f)

            # Wait for async callback
            try:
                await asyncio.wait_for(callback_invoked.wait(), timeout=5)
            except asyncio.TimeoutError:
                pytest.fail("Async callback not invoked")
            finally:
                await service.stop()
        finally:
            Path(config_path).unlink()

    async def test_non_reloadable_keys_preserved(self):
        """Test that non-reloadable keys are preserved."""
        service = ConfigHotReload()

        old_config = {
            "encryption_key": "old_secret_key",
            "api_secret_key": "old_api_secret",
            "some_setting": "old_value",
        }

        new_config = {
            "encryption_key": "new_secret_key",  # Should NOT be reloaded
            "api_secret_key": "new_api_secret",  # Should NOT be reloaded
            "some_setting": "new_value",  # Should be reloaded
        }

        merged = service._safe_reload(new_config, old_config)

        # Non-reloadable keys should keep old values
        assert merged["encryption_key"] == "old_secret_key"
        assert merged["api_secret_key"] == "old_api_secret"
        # Regular keys should be updated
        assert merged["some_setting"] == "new_value"

    async def test_invalid_yaml_handling(self):
        """Test handling of invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"version": 1}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=1)

            callback_count = [0]

            def callback(config):
                callback_count[0] += 1

            service.on_reload(callback)
            await service.start()

            await asyncio.sleep(0.5)

            # Write invalid YAML
            with open(config_path, "w") as f:
                f.write("invalid: yaml: content: {")

            # Wait and check that callback was NOT invoked
            await asyncio.sleep(2)
            assert callback_count[0] == 0

            await service.stop()
        finally:
            Path(config_path).unlink()

    async def test_missing_config_file(self):
        """Test handling when config file doesn't exist."""
        service = ConfigHotReload(config_path="/nonexistent/config.yaml")

        with pytest.raises(FileNotFoundError):
            await service.start()

    async def test_get_stats(self):
        """Test getting service statistics."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"test": "value"}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=15)

            def callback(config):
                pass

            service.on_reload(callback)
            service.on_reload(callback)

            stats = service.get_stats()

            assert stats["config_path"] == config_path
            assert stats["check_interval"] == 15
            assert stats["running"] is False
            assert stats["callbacks_registered"] == 2
            assert stats["non_reloadable_keys_count"] > 0
        finally:
            Path(config_path).unlink()

    async def test_custom_non_reloadable_keys(self):
        """Test custom non-reloadable keys."""
        custom_keys = frozenset({"custom_key1", "custom_key2"})
        service = ConfigHotReload(non_reloadable_keys=custom_keys)

        assert service._non_reloadable_keys == custom_keys

        old_config = {
            "custom_key1": "old_value1",
            "custom_key2": "old_value2",
            "normal_key": "old_normal",
        }

        new_config = {
            "custom_key1": "new_value1",
            "custom_key2": "new_value2",
            "normal_key": "new_normal",
        }

        merged = service._safe_reload(new_config, old_config)

        assert merged["custom_key1"] == "old_value1"
        assert merged["custom_key2"] == "old_value2"
        assert merged["normal_key"] == "new_normal"

    async def test_callback_error_handling(self):
        """Test that errors in callbacks don't crash the service."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_path = f.name
            yaml.dump({"version": 1}, f)

        try:
            service = ConfigHotReload(config_path=config_path, check_interval=1)

            # Add a callback that raises an error
            def bad_callback(config):
                raise ValueError("Callback error")

            good_callback_invoked = asyncio.Event()

            def good_callback(config):
                good_callback_invoked.set()

            service.on_reload(bad_callback)
            service.on_reload(good_callback)

            await service.start()
            await asyncio.sleep(0.5)

            # Modify config
            with open(config_path, "w") as f:
                yaml.dump({"version": 2}, f)

            # Good callback should still be invoked despite bad callback error
            try:
                await asyncio.wait_for(good_callback_invoked.wait(), timeout=5)
            except asyncio.TimeoutError:
                pytest.fail("Good callback not invoked after bad callback error")
            finally:
                await service.stop()
        finally:
            Path(config_path).unlink()


@pytest.mark.asyncio
class TestConfigHotReloadGlobal:
    """Test cases for global config hot-reload service."""

    def test_get_hot_reload_service_singleton(self):
        """Test that get_hot_reload_service returns singleton."""
        # Clear any existing instance
        from src.core import config_hot_reload

        config_hot_reload._hot_reload_service = None

        service1 = get_hot_reload_service(config_path="config1.yaml", check_interval=10)
        service2 = get_hot_reload_service(config_path="config2.yaml", check_interval=20)

        # Should return the same instance
        assert service1 is service2
        assert str(service1._config_path) == "config1.yaml"
        assert service1._check_interval == 10

    def test_get_hot_reload_service_creates_instance(self):
        """Test that service is created if not exists."""
        from src.core import config_hot_reload

        config_hot_reload._hot_reload_service = None

        service = get_hot_reload_service()

        assert service is not None
        assert isinstance(service, ConfigHotReload)
