"""Tests for proxy management functionality."""

import os

import pytest

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.repositories.proxy_repository import ProxyRepository
from src.utils.encryption import decrypt_password, encrypt_password
from src.utils.security.netnut_proxy import NetNutProxyManager, mask_proxy_password

# Skip these tests when DATABASE_URL is not available
skip_no_db = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="No database available")


@skip_no_db
@pytest.mark.asyncio
class TestProxyDatabase:
    """Test proxy database operations."""

    async def test_add_proxy(self):
        """Test adding a proxy to database."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxy
            proxy_id = await proxy_repo.create(
                {
                    "server": "gw.example.com",
                    "port": 8080,
                    "username": "test_user",
                    "password": "test_password",
                }
            )

            assert proxy_id > 0

            # Verify proxy was added
            proxy = await proxy_repo.get_by_id(proxy_id)
            assert proxy is not None
            assert proxy.server == "gw.example.com"
            assert proxy.port == 8080
            assert proxy.username == "test_user"
            assert proxy.password == "test_password"  # Should be decrypted
            assert proxy.is_active is True
            assert proxy.failure_count == 0

        finally:
            await db.close()

    async def test_proxy_password_encryption(self):
        """Test that proxy passwords are encrypted in database."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxy
            proxy_id = await proxy_repo.create(
                {
                    "server": "gw.example.com",
                    "port": 8080,
                    "username": "test_user",
                    "password": "secret_password_123",
                }
            )

            # Read directly from database to verify encryption
            async with db.get_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT password_encrypted FROM proxy_endpoints WHERE id = $1",
                    proxy_id,
                )
                encrypted_password = row["password_encrypted"]

            # Encrypted password should not match plain text
            assert encrypted_password != "secret_password_123"

            # But should decrypt correctly
            decrypted = decrypt_password(encrypted_password)
            assert decrypted == "secret_password_123"

        finally:
            await db.close()

    async def test_get_active_proxies(self):
        """Test retrieving active proxies."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add multiple proxies
            proxy1_id = await proxy_repo.create(
                {
                    "server": "proxy1.example.com",
                    "port": 8080,
                    "username": "user1",
                    "password": "pass1",
                }
            )
            proxy2_id = await proxy_repo.create(
                {
                    "server": "proxy2.example.com",
                    "port": 8081,
                    "username": "user2",
                    "password": "pass2",
                }
            )

            # Make one inactive
            await proxy_repo.update(proxy2_id, {"is_active": False})

            # Get active proxies
            active = await proxy_repo.get_active()

            # Only one should be active
            assert len(active) == 1
            assert active[0]["id"] == proxy1_id
            assert active[0]["server"] == "proxy1.example.com"
            assert active[0]["password"] == "pass1"  # Should be decrypted

        finally:
            await db.close()

    async def test_update_proxy(self):
        """Test updating a proxy."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxy
            proxy_id = await proxy_repo.create(
                {
                    "server": "gw.example.com",
                    "port": 8080,
                    "username": "test_user",
                    "password": "test_password",
                }
            )

            # Update proxy
            updated = await proxy_repo.update(
                proxy_id,
                {"server": "new.example.com", "port": 9090, "password": "new_password"},
            )

            assert updated is True

            # Verify updates
            proxy = await proxy_repo.get_by_id(proxy_id)
            assert proxy.server == "new.example.com"
            assert proxy.port == 9090
            assert proxy.username == "test_user"  # Should remain unchanged
            assert proxy.password == "new_password"

        finally:
            await db.close()

    async def test_delete_proxy(self):
        """Test deleting a proxy."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxy
            proxy_id = await proxy_repo.create(
                {
                    "server": "gw.example.com",
                    "port": 8080,
                    "username": "test_user",
                    "password": "test_password",
                }
            )

            # Delete proxy
            deleted = await proxy_repo.delete(proxy_id)
            assert deleted is True

            # Verify deletion
            proxy = await proxy_repo.get_by_id(proxy_id)
            assert proxy is None

            # Deleting again should return False
            deleted_again = await proxy_repo.delete(proxy_id)
            assert deleted_again is False

        finally:
            await db.close()

    async def test_mark_proxy_failed(self):
        """Test marking a proxy as failed."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxy
            proxy_id = await proxy_repo.create(
                {
                    "server": "gw.example.com",
                    "port": 8080,
                    "username": "test_user",
                    "password": "test_password",
                }
            )

            # Initially failure_count should be 0
            proxy = await proxy_repo.get_by_id(proxy_id)
            assert proxy.failure_count == 0

            # Mark as failed
            await proxy_repo.mark_failed(proxy_id)

            # Verify failure count incremented
            proxy = await proxy_repo.get_by_id(proxy_id)
            assert proxy.failure_count == 1

            # Mark failed again
            await proxy_repo.mark_failed(proxy_id)
            proxy = await proxy_repo.get_by_id(proxy_id)
            assert proxy.failure_count == 2

        finally:
            await db.close()

    async def test_reset_proxy_failures(self):
        """Test resetting proxy failure counts."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxies
            proxy1_id = await proxy_repo.create(
                {
                    "server": "proxy1.example.com",
                    "port": 8080,
                    "username": "user1",
                    "password": "pass1",
                }
            )
            proxy2_id = await proxy_repo.create(
                {
                    "server": "proxy2.example.com",
                    "port": 8081,
                    "username": "user2",
                    "password": "pass2",
                }
            )

            # Mark both as failed
            await proxy_repo.mark_failed(proxy1_id)
            await proxy_repo.mark_failed(proxy1_id)
            await proxy_repo.mark_failed(proxy2_id)

            # Verify failure counts
            proxy1 = await proxy_repo.get_by_id(proxy1_id)
            proxy2 = await proxy_repo.get_by_id(proxy2_id)
            assert proxy1.failure_count == 2
            assert proxy2.failure_count == 1

            # Reset all failures
            count = await proxy_repo.reset_all_failures()
            assert count == 2  # Both proxies should be reset

            # Verify all failure counts are 0
            proxy1 = await proxy_repo.get_by_id(proxy1_id)
            proxy2 = await proxy_repo.get_by_id(proxy2_id)
            assert proxy1.failure_count == 0
            assert proxy2.failure_count == 0

        finally:
            await db.close()

    async def test_get_proxy_stats(self):
        """Test getting proxy statistics."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Initially no proxies
            stats = await proxy_repo.get_stats()
            assert stats["total_proxies"] == 0
            assert stats["active_proxies"] == 0
            assert stats["inactive_proxies"] == 0
            assert stats["failed_proxies"] == 0

            # Add proxies
            await proxy_repo.create(
                {
                    "server": "proxy1.example.com",
                    "port": 8080,
                    "username": "user1",
                    "password": "pass1",
                }
            )
            proxy2_id = await proxy_repo.create(
                {
                    "server": "proxy2.example.com",
                    "port": 8081,
                    "username": "user2",
                    "password": "pass2",
                }
            )
            await proxy_repo.create(
                {
                    "server": "proxy3.example.com",
                    "port": 8082,
                    "username": "user3",
                    "password": "pass3",
                }
            )

            # Make one inactive
            await proxy_repo.update(proxy2_id, {"is_active": False})

            # Get stats
            stats = await proxy_repo.get_stats()
            assert stats["total_proxies"] == 3
            assert stats["active_proxies"] == 2
            assert stats["inactive_proxies"] == 1
            assert stats["failed_proxies"] == 0

            # Mark a proxy as failed
            await proxy_repo.mark_failed(proxy2_id)

            # Verify failed_proxies count increases
            stats = await proxy_repo.get_stats()
            assert stats["failed_proxies"] == 1

        finally:
            await db.close()

    async def test_unique_constraint(self):
        """Test that duplicate proxies are rejected."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxy
            await proxy_repo.create(
                {
                    "server": "gw.example.com",
                    "port": 8080,
                    "username": "test_user",
                    "password": "test_password",
                }
            )

            # Try to add duplicate - should raise ValueError
            with pytest.raises(ValueError, match="already exists"):
                await proxy_repo.create(
                    {
                        "server": "gw.example.com",
                        "port": 8080,
                        "username": "test_user",
                        "password": "different_password",
                    }
                )

        finally:
            await db.close()


class TestNetNutProxyManager:
    """Test NetNut proxy manager."""

    @skip_no_db
    @pytest.mark.asyncio
    async def test_load_from_database(self):
        """Test loading proxies from database."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            async with db.get_connection() as conn:
                await conn.execute("TRUNCATE proxy_endpoints CASCADE")

            proxy_repo = ProxyRepository(db)

            # Add proxies
            await proxy_repo.create(
                {"server": "gw.example.com", "port": 8080, "username": "user1", "password": "pass1"}
            )
            await proxy_repo.create(
                {
                    "server": "gw2.example.com",
                    "port": 8081,
                    "username": "user2",
                    "password": "pass2",
                }
            )

            # Load into proxy manager
            manager = NetNutProxyManager()
            count = await manager.load_from_database(db)

            assert count == 2
            assert len(manager.proxies) == 2

            # Verify proxy format
            proxy = manager.proxies[0]
            assert "id" in proxy
            assert "server" in proxy
            assert "host" in proxy
            assert "port" in proxy
            assert "username" in proxy
            assert "password" in proxy
            assert "protocol" in proxy
            assert "endpoint" in proxy

        finally:
            await db.close()

    def test_mask_proxy_password(self):
        """Test password masking utility."""
        # Test valid endpoint
        endpoint = "gw.netnut.net:5959:ntnt_user:secret_password"
        masked = mask_proxy_password(endpoint)
        assert masked == "gw.netnut.net:5959:ntnt_user:***"

        # Test invalid format (should return as-is)
        invalid = "invalid_format"
        masked = mask_proxy_password(invalid)
        assert masked == invalid

        # Test partial format
        partial = "server:port:username"
        masked = mask_proxy_password(partial)
        assert masked == partial


class TestProxyEncryption:
    """Test proxy password encryption."""

    def test_encrypt_decrypt_password(self):
        """Test password encryption and decryption."""
        # Ensure ENCRYPTION_KEY is set
        if not os.getenv("ENCRYPTION_KEY"):
            from cryptography.fernet import Fernet

            os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        original_password = "test_secret_password_123"

        # Encrypt
        encrypted = encrypt_password(original_password)

        # Encrypted should be different from original
        assert encrypted != original_password

        # Decrypt
        decrypted = decrypt_password(encrypted)

        # Decrypted should match original
        assert decrypted == original_password

    def test_encryption_consistency(self):
        """Test that same password encrypts differently each time (IV)."""
        # Ensure ENCRYPTION_KEY is set
        if not os.getenv("ENCRYPTION_KEY"):
            from cryptography.fernet import Fernet

            os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        password = "test_password"

        # Encrypt twice
        encrypted1 = encrypt_password(password)
        encrypted2 = encrypt_password(password)

        # Should be different due to IV
        assert encrypted1 != encrypted2

        # But both should decrypt to same value
        assert decrypt_password(encrypted1) == password
        assert decrypt_password(encrypted2) == password
