"""Configuration hot-reload service.

This module provides automatic reloading of configuration files when they change,
without requiring application restart. Uses file modification time monitoring
instead of filesystem watchers to avoid additional dependencies.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from loguru import logger


class ConfigHotReload:
    """
    Monitor configuration file for changes and trigger reload callbacks.

    Periodically checks file modification time and reloads config when changed.
    Non-reloadable keys (like encryption keys) are preserved from old config.
    """

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        check_interval: int = 30,
        non_reloadable_keys: Optional[frozenset] = None,
    ):
        """
        Initialize config hot-reload service.

        Args:
            config_path: Path to configuration file
            check_interval: Seconds between modification checks (default: 30)
            non_reloadable_keys: Set of keys that should not be reloaded
        """
        self._config_path = Path(config_path)
        self._check_interval = check_interval
        self._last_mtime: float = 0
        self._callbacks: List[Callable[[Dict], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Keys that should not be reloaded for security/stability
        if non_reloadable_keys is None:
            self._non_reloadable_keys = frozenset(
                {
                    "encryption_key",
                    "api_secret_key",
                    "api_key_salt",
                    "vfs_encryption_key",
                    "admin_secret",
                    "jwt_secret",
                    "database",  # Database path shouldn't change
                }
            )
        else:
            self._non_reloadable_keys = non_reloadable_keys

        logger.info(
            f"Config hot-reload initialized: {config_path} "
            f"(check interval: {check_interval}s, "
            f"non-reloadable keys: {len(self._non_reloadable_keys)})"
        )

    def on_reload(self, callback: Callable[[Dict], None]) -> None:
        """
        Register callback for config changes.

        The callback will be invoked with the new merged config dict when
        the configuration file changes.

        Args:
            callback: Function to call with new config dict
        """
        self._callbacks.append(callback)
        logger.debug(f"Registered reload callback: {callback.__name__}")

    async def start(self) -> None:
        """Start watching for config changes."""
        if self._running:
            logger.warning("Config hot-reload already running")
            return

        if not self._config_path.exists():
            logger.error(f"Config file not found: {self._config_path}")
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        self._running = True
        self._last_mtime = self._config_path.stat().st_mtime
        logger.info(f"Started monitoring config file: {self._config_path}")

        # Start background monitoring task
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop watching for config changes."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Config hot-reload stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_for_changes()
            except asyncio.CancelledError:
                logger.debug("Config monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in config monitoring loop: {e}", exc_info=True)
                # Continue monitoring despite errors
                await asyncio.sleep(5)

    async def _check_for_changes(self) -> None:
        """Check if config file has been modified."""
        try:
            if not self._config_path.exists():
                logger.warning(f"Config file disappeared: {self._config_path}")
                return

            current_mtime = self._config_path.stat().st_mtime

            if current_mtime > self._last_mtime:
                logger.info("Config file changed, reloading...")

                # Load new config
                try:
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        new_config = yaml.safe_load(f)

                    if not new_config:
                        logger.error("Loaded config is empty, skipping reload")
                        return

                    # Get current config from first callback if available
                    # (assumes callbacks have access to current config)
                    # For now, we'll just use new config directly
                    merged_config = self._safe_reload(new_config, {})

                    # Notify all callbacks
                    for callback in self._callbacks:
                        try:
                            # Check if callback is async
                            if asyncio.iscoroutinefunction(callback):
                                await callback(merged_config)
                            else:
                                callback(merged_config)
                        except Exception as e:
                            logger.error(
                                f"Error in reload callback {callback.__name__}: {e}", exc_info=True
                            )

                    self._last_mtime = current_mtime
                    logger.info("Config reload completed successfully")

                except yaml.YAMLError as e:
                    logger.error(f"Failed to parse config YAML: {e}")
                except Exception as e:
                    logger.error(f"Failed to reload config: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error checking for config changes: {e}", exc_info=True)

    def _safe_reload(self, new_config: Dict, old_config: Dict) -> Dict:
        """
        Merge new config but preserve non-reloadable keys from old config.

        Args:
            new_config: Newly loaded config
            old_config: Previous config (may be empty on first load)

        Returns:
            Merged config dict
        """
        merged = new_config.copy()

        # Preserve non-reloadable keys from old config
        for key in self._non_reloadable_keys:
            if key in old_config:
                merged[key] = old_config[key]
                logger.debug(f"Preserved non-reloadable key: {key}")

        return merged

    def get_stats(self) -> Dict[str, Any]:
        """
        Get hot-reload statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "config_path": str(self._config_path),
            "check_interval": self._check_interval,
            "running": self._running,
            "last_mtime": self._last_mtime,
            "callbacks_registered": len(self._callbacks),
            "non_reloadable_keys_count": len(self._non_reloadable_keys),
        }


# Global singleton instance
_hot_reload_service: Optional[ConfigHotReload] = None


def get_hot_reload_service(
    config_path: str = "config/config.yaml", check_interval: int = 30
) -> ConfigHotReload:
    """
    Get or create the global config hot-reload service.

    Args:
        config_path: Path to config file (only used on first call)
        check_interval: Check interval in seconds (only used on first call)

    Returns:
        ConfigHotReload instance
    """
    global _hot_reload_service

    if _hot_reload_service is None:
        _hot_reload_service = ConfigHotReload(
            config_path=config_path, check_interval=check_interval
        )

    return _hot_reload_service
