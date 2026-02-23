"""Proxy repository implementation."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.models.database import Database

from loguru import logger

from src.repositories.base import BaseRepository
from src.utils.db_helpers import _parse_command_tag
from src.utils.encryption import decrypt_password, encrypt_password


class Proxy:
    """Proxy entity model."""

    def __init__(
        self,
        id: int,
        server: str,
        port: int,
        username: str,
        password: str,
        is_active: bool,
        last_used: Optional[str],
        failure_count: int,
        created_at: str,
        updated_at: str,
    ):
        """Initialize proxy entity."""
        self.id = id
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.is_active = is_active
        self.last_used = last_used
        self.failure_count = failure_count
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert proxy to dictionary."""
        return {
            "id": self.id,
            "server": self.server,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "is_active": self.is_active,
            "last_used": self.last_used,
            "failure_count": self.failure_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProxyRepository(BaseRepository[Proxy]):
    """Repository for proxy CRUD operations."""

    def _row_to_proxy(self, row: Any, decrypt: bool = True) -> Optional[Proxy]:
        """
        Convert database row to Proxy entity.

        Args:
            row: Database row
            decrypt: Whether to decrypt the password

        Returns:
            Proxy entity or None if decryption fails
        """
        password = ""
        if decrypt:
            try:
                password = decrypt_password(row["password_encrypted"])
            except Exception as e:
                logger.error(f"Failed to decrypt password for proxy {row['id']}: {e}")
                return None
        else:
            password = row.get("password_encrypted", "")

        return Proxy(
            id=row["id"],
            server=row["server"],
            port=row["port"],
            username=row["username"],
            password=password,
            is_active=bool(row.get("is_active", True)),
            last_used=str(row["last_used"]) if row.get("last_used") else None,
            failure_count=int(row.get("failure_count", 0)),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
        )

    async def get_by_id(self, id: int) -> Optional[Proxy]:
        """
        Get a single proxy by ID with decrypted password.

        Args:
            id: Proxy ID

        Returns:
            Proxy entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                WHERE id = $1
                """,
                id,
            )

            if not row:
                return None

            return self._row_to_proxy(row)

    async def get_all(self, limit: int = 100) -> List[Proxy]:
        """
        Get all proxies with decrypted passwords.

        Args:
            limit: Maximum number of proxies to return

        Returns:
            List of proxy entities
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )

            proxies = []
            for row in rows:
                proxy = self._row_to_proxy(row)
                if proxy:
                    proxies.append(proxy)

            return proxies

    async def get_active(self) -> List[Dict[str, Any]]:
        """
        Get all active proxies with decrypted passwords.

        Returns:
            List of proxy dictionaries with decrypted passwords
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT id, server, port, username, password_encrypted, is_active,
                       last_used, failure_count, created_at, updated_at
                FROM proxy_endpoints
                WHERE is_active = true
                ORDER BY failure_count ASC, last_used ASC NULLS FIRST
                """)

            proxies = []
            for row in rows:
                proxy_dict = dict(row)
                # Decrypt password
                try:
                    proxy_dict["password"] = decrypt_password(proxy_dict["password_encrypted"])
                    del proxy_dict["password_encrypted"]  # Remove encrypted version from response
                    proxies.append(proxy_dict)
                except Exception as e:
                    logger.error(f"Failed to decrypt password for proxy {proxy_dict['id']}: {e}")
                    # Skip proxies with decryption errors
                    continue

            return proxies

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Add a new proxy endpoint with encrypted password.

        Args:
            data: Proxy data (server, port, username, password)

        Returns:
            Proxy ID

        Raises:
            ValueError: If proxy already exists or required fields missing
        """
        server = data.get("server")
        port = data.get("port")
        username = data.get("username")
        password = data.get("password")

        if not all([server, port, username, password]):
            raise ValueError("server, port, username, and password are required")

        # Encrypt password before storing
        encrypted_password = encrypt_password(str(password))

        async with self.db.get_connection() as conn:
            try:
                proxy_id = await conn.fetchval(
                    """
                    INSERT INTO proxy_endpoints
                    (server, port, username, password_encrypted, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    RETURNING id
                    """,
                    server,
                    port,
                    username,
                    encrypted_password,
                )

                logger.info(f"Proxy added: {server}:{port} (ID: {proxy_id})")
                return proxy_id or 0

            except Exception as e:
                if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                    raise ValueError(
                        f"Proxy with server={server}, port={port}, "
                        f"username={username} already exists"
                    )
                raise

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update a proxy endpoint.

        Args:
            id: Proxy ID
            data: Update data (server, port, username, password, is_active)

        Returns:
            True if updated, False if not found

        Raises:
            ValueError: If update violates uniqueness constraint
        """
        # Build dynamic update query
        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if "server" in data and data["server"] is not None:
            updates.append(f"server = ${param_num}")
            params.append(data["server"])
            param_num += 1

        if "port" in data and data["port"] is not None:
            updates.append(f"port = ${param_num}")
            params.append(data["port"])
            param_num += 1

        if "username" in data and data["username"] is not None:
            updates.append(f"username = ${param_num}")
            params.append(data["username"])
            param_num += 1

        if "password" in data and data["password"] is not None:
            updates.append(f"password_encrypted = ${param_num}")
            params.append(encrypt_password(data["password"]))
            param_num += 1

        if "is_active" in data and data["is_active"] is not None:
            updates.append(f"is_active = ${param_num}")
            params.append(data["is_active"])
            param_num += 1

        if not updates:
            return False  # Nothing to update

        # Always update the updated_at timestamp
        updates.append("updated_at = NOW()")
        params.append(id)

        query = f"UPDATE proxy_endpoints SET {', '.join(updates)} WHERE id = ${param_num}"

        async with self.db.get_connection() as conn:
            try:
                result = await conn.execute(query, *params)
                updated: bool = result != "UPDATE 0"

                if updated:
                    logger.info(f"Proxy {id} updated")
                return updated

            except Exception as e:
                if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                    raise ValueError("Update violates uniqueness constraint")
                raise

    async def delete(self, id: int) -> bool:
        """
        Delete a proxy endpoint.

        Args:
            id: Proxy ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM proxy_endpoints WHERE id = $1",
                id,
            )
            deleted: bool = result != "DELETE 0"

        if deleted:
            logger.info(f"Proxy {id} deleted")
        return deleted

    async def mark_failed(self, proxy_id: int) -> bool:
        """
        Increment failure count for a proxy and update last_used.

        Args:
            proxy_id: Proxy ID

        Returns:
            True if updated, False if not found
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE proxy_endpoints
                SET failure_count = failure_count + 1,
                    last_used = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                proxy_id,
            )
            updated: bool = result != "UPDATE 0"

            if updated:
                logger.debug(f"Proxy {proxy_id} marked as failed")

            return updated

    async def reset_failures(self, proxy_id: int) -> bool:
        """
        Reset failure count for a proxy.

        Args:
            proxy_id: Proxy ID

        Returns:
            True if updated, False if not found
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE proxy_endpoints
                SET failure_count = 0,
                    updated_at = NOW()
                WHERE id = $1
                """,
                proxy_id,
            )
            updated: bool = result != "UPDATE 0"

            if updated:
                logger.info(f"Proxy {proxy_id} failures reset")

            return updated

    async def reset_all_failures(self) -> int:
        """
        Reset failure count for all proxies.

        Returns:
            Number of proxies updated
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute("""
                UPDATE proxy_endpoints
                SET failure_count = 0,
                    updated_at = NOW()
                WHERE failure_count > 0
                """)
            # Use helper to parse result count
            count = _parse_command_tag(result)

            if count > 0:
                logger.info(f"Reset failures for {count} proxies")

            return count

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get proxy statistics.

        Returns:
            Dictionary with proxy statistics
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_proxies,
                    COUNT(*) FILTER (WHERE is_active = true) as active_proxies,
                    COUNT(*) FILTER (WHERE is_active = false) as inactive_proxies,
                    AVG(failure_count) as avg_failure_count,
                    MAX(failure_count) as max_failure_count
                FROM proxy_endpoints
                """)

            if row:
                return {
                    "total_proxies": int(row["total_proxies"]),
                    "active_proxies": int(row["active_proxies"]),
                    "inactive_proxies": int(row["inactive_proxies"]),
                    "avg_failure_count": (
                        float(row["avg_failure_count"]) if row["avg_failure_count"] else 0.0
                    ),
                    "max_failure_count": (
                        int(row["max_failure_count"]) if row["max_failure_count"] else 0
                    ),
                }

            return {
                "total_proxies": 0,
                "active_proxies": 0,
                "inactive_proxies": 0,
                "avg_failure_count": 0.0,
                "max_failure_count": 0,
            }

    async def clear_all(self) -> int:
        """
        Clear all proxies from the database.

        Returns:
            Number of proxies deleted
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute("DELETE FROM proxy_endpoints")
            count = _parse_command_tag(result)

            if count > 0:
                logger.warning(f"Cleared all {count} proxies")

            return count
