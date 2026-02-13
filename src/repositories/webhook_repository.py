"""Webhook repository implementation."""

import secrets
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.models.database import Database

from loguru import logger

from src.repositories.base import BaseRepository


class Webhook:
    """Webhook entity model."""

    def __init__(
        self,
        id: int,
        user_id: int,
        webhook_token: str,
        is_active: bool,
        created_at: str,
        updated_at: str,
    ):
        """Initialize webhook entity."""
        self.id = id
        self.user_id = user_id
        self.webhook_token = webhook_token
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert webhook to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "webhook_token": self.webhook_token,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WebhookRepository(BaseRepository[Webhook]):
    """Repository for webhook CRUD operations."""

    def __init__(self, database: "Database"):
        """
        Initialize webhook repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    def _row_to_webhook(self, row: Any) -> Webhook:
        """
        Convert database row to Webhook entity.

        Args:
            row: Database row

        Returns:
            Webhook entity
        """
        return Webhook(
            id=row["id"],
            user_id=row["user_id"],
            webhook_token=row["webhook_token"],
            is_active=bool(row.get("is_active", True)),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
        )

    async def get_by_id(self, id: int) -> Optional[Webhook]:
        """
        Get webhook by ID.

        Args:
            id: Webhook ID

        Returns:
            Webhook entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_webhooks WHERE id = $1",
                id,
            )

            if row is None:
                return None

            return self._row_to_webhook(row)

    async def get_by_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get webhook information for a user.

        Args:
            user_id: User ID

        Returns:
            Webhook data or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM user_webhooks WHERE user_id = $1
                """,
                user_id,
            )
            return dict(row) if row else None

    async def get_all(self, limit: int = 100) -> List[Webhook]:
        """
        Get all webhooks.

        Args:
            limit: Maximum number of webhooks to return

        Returns:
            List of webhook entities
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM user_webhooks ORDER BY created_at DESC LIMIT $1",
                limit,
            )

            return [self._row_to_webhook(row) for row in rows]

    async def create(self, user_id: int) -> str:
        """
        Create a unique webhook token for a user.

        Args:
            user_id: User ID

        Returns:
            Generated webhook token

        Raises:
            ValueError: If user already has a webhook
        """
        # Check if user already has a webhook
        existing = await self.get_by_user(user_id)
        if existing:
            raise ValueError("User already has a webhook")

        # Generate unique token
        token = secrets.token_urlsafe(32)

        async with self.db.get_connection() as conn:
            webhook_id = await conn.fetchval(
                """
                INSERT INTO user_webhooks (user_id, webhook_token, is_active)
                VALUES ($1, $2, true)
                RETURNING id
                """,
                user_id,
                token,
            )

        logger.info(f"Webhook created for user {user_id}: {token[:8]}...")
        return token

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update webhook.

        Args:
            id: Webhook ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        # Build dynamic update query
        updates: List[str] = []
        params: List[Any] = []
        param_num = 1

        if "is_active" in data:
            updates.append(f"is_active = ${param_num}")
            params.append(data["is_active"])
            param_num += 1

        if "webhook_token" in data:
            updates.append(f"webhook_token = ${param_num}")
            params.append(data["webhook_token"])
            param_num += 1

        if not updates:
            return False  # Nothing to update

        updates.append("updated_at = NOW()")
        params.append(id)

        query = f"UPDATE user_webhooks SET {', '.join(updates)} WHERE id = ${param_num}"

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *params)
            updated = result != "UPDATE 0"

            if updated:
                logger.info(f"Webhook {id} updated")

            return updated

    async def delete(self, id: int) -> bool:
        """
        Delete webhook by ID.

        Args:
            id: Webhook ID

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM user_webhooks WHERE id = $1",
                id,
            )
            deleted = result != "DELETE 0"

            if deleted:
                logger.info(f"Webhook {id} deleted")

            return deleted

    async def delete_by_user(self, user_id: int) -> bool:
        """
        Delete a user's webhook.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM user_webhooks WHERE user_id = $1
                """,
                user_id,
            )
            deleted = result != "DELETE 0"

        if deleted:
            logger.info(f"Webhook deleted for user {user_id}")
        return deleted

    async def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by webhook token.

        Args:
            token: Webhook token

        Returns:
            User data or None if token not found or inactive
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.*
                FROM users u
                JOIN user_webhooks w ON u.id = w.user_id
                WHERE w.webhook_token = $1 AND w.is_active = true
                """,
                token,
            )
            return dict(row) if row else None
