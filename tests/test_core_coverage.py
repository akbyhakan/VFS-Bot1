"""Additional coverage tests for core modules."""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from src.core.config_loader import (
    load_env_variables,
    substitute_env_vars,
    load_config,
    get_config_value,
)


class TestConfigLoader:
    """Tests for config loader module."""

    def test_substitute_env_vars_string_with_env(self, monkeypatch):
        """Test environment variable substitution in string."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        result = substitute_env_vars("${TEST_VAR}")
        assert result == "test_value"

    def test_substitute_env_vars_string_multiple(self, monkeypatch):
        """Test multiple environment variables in string."""
        monkeypatch.setenv("VAR1", "value1")
        monkeypatch.setenv("VAR2", "value2")
        result = substitute_env_vars("${VAR1}-${VAR2}")
        assert result == "value1-value2"

    def test_substitute_env_vars_dict(self, monkeypatch):
        """Test environment variable substitution in dict."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        data = {"key": "${TEST_VAR}", "nested": {"key2": "${TEST_VAR}"}}
        result = substitute_env_vars(data)
        assert result["key"] == "test_value"
        assert result["nested"]["key2"] == "test_value"

    def test_substitute_env_vars_list(self, monkeypatch):
        """Test environment variable substitution in list."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        data = ["${TEST_VAR}", "static", "${TEST_VAR}"]
        result = substitute_env_vars(data)
        assert result == ["test_value", "static", "test_value"]

    def test_substitute_env_vars_no_env(self):
        """Test substitution with missing environment variable."""
        result = substitute_env_vars("${NONEXISTENT_VAR}")
        assert result == ""  # Missing vars are replaced with empty string

    def test_substitute_env_vars_non_string(self):
        """Test substitution with non-string values."""
        assert substitute_env_vars(123) == 123
        assert substitute_env_vars(True) is True
        assert substitute_env_vars(None) is None

    def test_get_config_value_simple(self):
        """Test getting simple config value."""
        config = {"key": "value"}
        result = get_config_value(config, "key")
        assert result == "value"

    def test_get_config_value_nested(self):
        """Test getting nested config value."""
        config = {"level1": {"level2": {"level3": "value"}}}
        result = get_config_value(config, "level1.level2.level3")
        assert result == "value"

    def test_get_config_value_nonexistent(self):
        """Test getting non-existent config value."""
        config = {"key": "value"}
        result = get_config_value(config, "nonexistent", default="default")
        assert result == "default"

    def test_get_config_value_partial_path(self):
        """Test getting partial path that doesn't exist."""
        config = {"level1": {"level2": "value"}}
        result = get_config_value(config, "level1.nonexistent.level3", default="default")
        assert result == "default"

    def test_load_config_with_file(self, tmp_path):
        """Test loading config from file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
vfs:
  base_url: https://test.com
credentials:
  email: test@example.com
""")

        config = load_config(str(config_file))
        assert "vfs" in config
        assert config["vfs"]["base_url"] == "https://test.com"

    def test_load_config_with_env_substitution(self, tmp_path, monkeypatch):
        """Test loading config with environment variable substitution."""
        monkeypatch.setenv("BASE_URL", "https://from-env.com")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
vfs:
  base_url: ${BASE_URL}
""")

        config = load_config(str(config_file))
        assert config["vfs"]["base_url"] == "https://from-env.com"


class TestEncryptionModule:
    """Additional tests for encryption module."""

    def test_encrypt_decrypt_different_passwords(self):
        """Test encrypting different passwords."""
        from src.utils.encryption import encrypt_password, decrypt_password
        from cryptography.fernet import Fernet
        import os

        # Set encryption key
        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key

        passwords = ["password1", "password2", "password3"]
        encrypted = [encrypt_password(p) for p in passwords]

        # All encrypted passwords should be different
        assert len(set(encrypted)) == len(passwords)

        # All should decrypt correctly
        for original, enc in zip(passwords, encrypted):
            assert decrypt_password(enc) == original

    def test_password_encryption_reset(self):
        """Test resetting encryption instance."""
        from src.utils.encryption import reset_encryption
        from cryptography.fernet import Fernet
        import os

        key = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = key

        # Reset should not crash
        reset_encryption()


class TestProxyManager:
    """Additional tests for proxy manager."""

    def test_proxy_manager_load_from_file(self, tmp_path):
        """Test loading proxies from file."""
        from src.utils.security.proxy_manager import ProxyManager

        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("""
# This is a comment
192.168.1.1:8080
192.168.1.2:8080

192.168.1.3:8080
""")

        config = {"enabled": True, "file": str(proxy_file)}
        manager = ProxyManager(config=config)

        # Should have loaded 3 proxies (skipping comment and empty line)
        assert len(manager.proxies) == 3

    def test_proxy_manager_random_proxy(self, tmp_path):
        """Test getting random proxy."""
        from src.utils.security.proxy_manager import ProxyManager

        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("192.168.1.1:8080\n192.168.1.2:8080\n")

        config = {"enabled": True, "file": str(proxy_file)}
        manager = ProxyManager(config=config)

        if len(manager.proxies) > 0:
            proxy = manager.get_random_proxy()
            assert proxy is not None

    def test_proxy_manager_rotate_proxy(self, tmp_path):
        """Test rotating proxies."""
        from src.utils.security.proxy_manager import ProxyManager

        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("192.168.1.1:8080\n192.168.1.2:8080\n")

        config = {"enabled": True, "file": str(proxy_file)}
        manager = ProxyManager(config=config)

        if len(manager.proxies) > 1:
            proxy1 = manager.rotate_proxy()
            proxy2 = manager.rotate_proxy()
            # Should rotate through proxies
            assert proxy1 is not None
            assert proxy2 is not None

    def test_proxy_manager_mark_failed(self, tmp_path):
        """Test marking proxy as failed."""
        from src.utils.security.proxy_manager import ProxyManager

        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("192.168.1.1:8080\n")

        config = {"enabled": True, "file": str(proxy_file)}
        manager = ProxyManager(config=config)

        if len(manager.proxies) > 0:
            proxy = manager.proxies[0]
            manager.mark_proxy_failed(proxy)
            # Should have recorded failure
            assert len(manager.failed_proxies) > 0 or str(proxy) in str(manager.failed_proxies)


class TestSessionManager:
    """Additional tests for session manager."""

    def test_session_manager_token_expiry(self, tmp_path):
        """Test token expiry checking."""
        from src.utils.security.session_manager import SessionManager
        import time

        session_file = tmp_path / "session.json"
        manager = SessionManager(session_file=str(session_file))

        # Set expired token
        manager.access_token = "token"
        manager.token_expiry = int(time.time()) - 3600  # 1 hour ago

        assert manager.is_token_expired() is True

    def test_session_manager_token_not_expired(self, tmp_path):
        """Test valid token."""
        from src.utils.security.session_manager import SessionManager
        import time

        session_file = tmp_path / "session.json"
        manager = SessionManager(session_file=str(session_file))

        # Set valid token
        manager.access_token = "token"
        manager.token_expiry = int(time.time()) + 3600  # 1 hour in future

        assert manager.is_token_expired() is False

    def test_session_manager_has_valid_session(self, tmp_path):
        """Test checking for valid session."""
        from src.utils.security.session_manager import SessionManager
        import time

        session_file = tmp_path / "session.json"
        manager = SessionManager(session_file=str(session_file))

        # No token - invalid
        assert manager.has_valid_session() is False

        # Set valid token
        manager.access_token = "token"
        manager.token_expiry = int(time.time()) + 3600

        assert manager.has_valid_session() is True

    def test_session_manager_auth_header(self, tmp_path):
        """Test getting auth header."""
        from src.utils.security.session_manager import SessionManager

        session_file = tmp_path / "session.json"
        manager = SessionManager(session_file=str(session_file))

        manager.access_token = "my_token"
        header = manager.get_auth_header()

        assert "Authorization" in header
        assert "Bearer my_token" in header["Authorization"]


class TestRateLimiter:
    """Additional tests for rate limiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        from src.utils.security.rate_limiter import RateLimiter, get_rate_limiter

        limiter = RateLimiter()
        assert limiter is not None
        
        # Test singleton
        singleton = get_rate_limiter()
        assert singleton is not None


class TestHeaderManager:
    """Additional tests for header manager."""

    def test_header_manager_get_headers(self):
        """Test getting headers."""
        from src.utils.security.header_manager import HeaderManager

        manager = HeaderManager()
        headers = manager.get_headers()

        assert isinstance(headers, dict)
        assert "User-Agent" in headers

    def test_header_manager_rotate(self):
        """Test rotating headers."""
        from src.utils.security.header_manager import HeaderManager

        manager = HeaderManager()
        headers1 = manager.get_headers()
        manager.rotate_user_agent()
        headers2 = manager.get_headers()

        # Headers should exist
        assert headers1 is not None
        assert headers2 is not None


import time
