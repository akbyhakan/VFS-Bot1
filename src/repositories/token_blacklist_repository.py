"""Token blacklist repository implementation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from src.models.database import Database
from src.repositories.base import BaseRepository
from src.utils.db_helpers import _parse_command_tag


class TokenBlacklistEntry:
    """Token blacklist entry entity model."""

    def __init__(self, jti: str, exp: datetime):
        """Initialize token blacklist entry entity."""
        self.jti = jti
        self.exp = exp

    def to_dict(self) -> Dict[str, Any]:
        """Convert token blacklist entry to dictionary."""
        return {
            "jti": self.jti,
            "exp": self.exp.isoformat() if isinstance(self.exp, datetime) else self.exp,
        }


class TokenBlacklistRepository(BaseRepository[TokenBlacklistEntry]):
    """Repository for token blacklist operations."""

    def __init__(self, database: Database):
        """
        Initialize token blacklist repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    async def get_by_id(self, id: int) -> Optional[TokenBlacklistEntry]:
        """
        Get token by ID (not applicable for blacklist - use jti instead).

        Args:
            id: Not used

        Returns:
            None
        """
        logger.warning("get_by_id not supported for TokenBlacklist - use is_blacklisted instead")
        return None

    async def get_all(self, limit: int = 100) -> List[TokenBlacklistEntry]:
        """
        Get all active (non-expired) blacklisted tokens.

        Args:
            limit: Not used (returns all active tokens)

        Returns:
            List of TokenBlacklistEntry entities
        """
        async with self.db.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            rows = await conn.fetch(
                """
                SELECT jti, exp FROM token_blacklist
                WHERE exp > $1
                """,
                now,
            )
            return [
                TokenBlacklistEntry(
                    jti=row[0],
                    exp=datetime.fromisoformat(row[1]) if isinstance(row[1], str) else row[1],
                )
                for row in rows
            ]

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Add a token to the blacklist (not returning an ID).

        Args:
            data: Token data (jti, exp)

        Returns:
            1 if successful, 0 otherwise
        """
        jti = data.get("jti")
        exp = data.get("exp")

        if not jti or not exp:
            raise ValueError("Both jti and exp are required")

        # Ensure exp is a datetime object
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)

        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO token_blacklist (jti, exp)
                VALUES ($1, $2)
                ON CONFLICT (jti) DO UPDATE SET exp = EXCLUDED.exp
                """,
                jti,
                exp.isoformat(),
            )
            logger.debug(f"Token blacklisted: {jti}")
            return 1

    async def add(self, jti: str, exp: datetime) -> None:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID to blacklist
            exp: Token expiration time
        """
        await self.create({"jti": jti, "exp": exp})

    async def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted and not expired
        """
        async with self.db.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            result = await conn.fetchval(
                """
                SELECT 1 FROM token_blacklist
                WHERE jti = $1 AND exp > $2
                """,
                jti,
                now,
            )
            return result is not None

    async def get_active(self) -> List[tuple[str, datetime]]:
        """
        Get all active (non-expired) blacklisted tokens.

        Returns:
            List of (jti, exp) tuples
        """
        entries = await self.get_all()
        return [(entry.jti, entry.exp) for entry in entries]

    async def cleanup_expired(self) -> int:
        """
        Remove expired tokens from blacklist.

        Returns:
            Number of tokens removed
        """
        async with self.db.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            result = await conn.execute(
                """
                DELETE FROM token_blacklist
                WHERE exp <= $1
                """,
                now,
            )
            count = _parse_command_tag(result)
            if count > 0:
                logger.info(f"Cleaned up {count} expired tokens from blacklist")
            return count

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update token blacklist entry (not typically supported).

        Args:
            id: Not used
            data: Update data

        Returns:
            False
        """
        logger.warning("Token blacklist entries cannot be updated")
        return False

    async def delete(self, id: int) -> bool:
        """
        Delete token by ID (use jti instead).

        Args:
            id: Not used

        Returns:
            False
        """
        logger.warning("Use delete_by_jti instead")
        return False

    async def delete_by_jti(self, jti: str) -> bool:
        """
        Remove a specific token from the blacklist.

        Args:
            jti: JWT ID to remove

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM token_blacklist WHERE jti = $1",
                jti,
            )
            deleted = _parse_command_tag(result) > 0

            if deleted:
                logger.info(f"Token removed from blacklist: {jti}")

            return deleted
