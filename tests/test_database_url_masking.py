"""Tests for database URL masking."""

import pytest

from src.models.database import _mask_database_url


class TestDatabaseURLMasking:
    """Tests for _mask_database_url function."""

    def test_mask_postgresql_url_with_credentials(self):
        """Test masking PostgreSQL URL with username and password."""
        url = "postgresql://user:password@localhost:5432/mydb"
        masked = _mask_database_url(url)
        
        assert "user" not in masked
        assert "password" not in masked
        assert "***:***@localhost:5432" in masked
        assert "postgresql://" in masked
        assert "/mydb" in masked

    def test_mask_postgresql_url_with_special_chars(self):
        """Test masking URL with special characters in password."""
        url = "postgresql://user:p@ss!w0rd@localhost:5432/mydb"
        masked = _mask_database_url(url)
        
        assert "user" not in masked
        assert "p@ss!w0rd" not in masked
        assert "***:***@localhost:5432" in masked

    def test_mask_sqlite_url(self):
        """Test masking SQLite URL (no @ symbol)."""
        url = "sqlite:///path/to/database.db"
        masked = _mask_database_url(url)
        
        assert "sqlite://***" == masked
        assert "/path/to/database.db" not in masked

    def test_mask_url_without_credentials(self):
        """Test URL without credentials shows hostname."""
        url = "postgresql://localhost:5432/mydb"
        masked = _mask_database_url(url)
        
        assert "localhost:5432" in masked
        assert "/mydb" in masked
        assert "postgresql://" in masked

    def test_mask_url_with_empty_password(self):
        """Test URL with username but empty password."""
        url = "postgresql://user:@localhost:5432/mydb"
        masked = _mask_database_url(url)
        
        assert "user" not in masked
        assert "***:***@localhost:5432" in masked

    def test_mask_url_with_only_username(self):
        """Test URL with only username (no password)."""
        url = "postgresql://user@localhost:5432/mydb"
        masked = _mask_database_url(url)
        
        assert "user" not in masked
        assert "***:***@localhost:5432" in masked

    def test_mask_invalid_url(self):
        """Test handling of completely invalid URL."""
        url = "not-a-valid-url"
        masked = _mask_database_url(url)
        
        # Should return safe placeholder for invalid URLs
        assert masked == "<unparseable-url>"

    def test_mask_url_with_query_parameters(self):
        """Test URL with query parameters containing credentials."""
        url = "postgresql://user:pass@localhost:5432/mydb?password=secret"
        masked = _mask_database_url(url)
        
        # Main credentials in netloc should be masked
        assert "user" not in masked.split('?')[0]  # Check URL part before query params
        assert "pass" not in masked.split('?')[0]  # Check URL part before query params
        assert "***:***@localhost:5432" in masked
        # Query parameters are preserved (not ideal but acceptable for this fix)
        assert "?password=secret" in masked

    def test_mask_url_without_port(self):
        """Test URL without explicit port."""
        url = "postgresql://user:pass@localhost/mydb"
        masked = _mask_database_url(url)
        
        assert "user" not in masked
        assert "pass" not in masked
        assert "***:***@localhost" in masked
        assert "/mydb" in masked

    def test_mask_url_with_ip_address(self):
        """Test URL with IP address instead of hostname."""
        url = "postgresql://user:pass@192.168.1.100:5432/mydb"
        masked = _mask_database_url(url)
        
        assert "user" not in masked
        assert "pass" not in masked
        assert "***:***@192.168.1.100:5432" in masked

    def test_mask_empty_string(self):
        """Test masking empty string."""
        url = ""
        masked = _mask_database_url(url)
        
        assert masked == "<unparseable-url>"

    def test_mask_mysql_url(self):
        """Test masking MySQL URL."""
        url = "mysql://root:secret@localhost:3306/testdb"
        masked = _mask_database_url(url)
        
        assert "root" not in masked
        assert "secret" not in masked
        assert "***:***@localhost:3306" in masked
        assert "mysql://" in masked
