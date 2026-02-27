"""Account pool repository for managing VFS account pool."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from src.repositories.base import BaseRepository
from src.utils.encryption import decrypt_password, encrypt_password

if TYPE_CHECKING:
    from src.models.database import Database


class AccountPoolRepository(BaseRepository):
    """Repository for VFS account pool operations."""

    async def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Get account by ID."""
        return await self.get_account_by_id(id)

    async def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all accounts."""
        return await self.get_available_accounts()

    async def create(self, data: Dict[str, Any]) -> int:
        """Create a new account."""
        return await self.create_account(
            email=data["email"],
            password=data["password"],
            phone=data.get("phone", ""),
        )

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """Update an account."""
        if "is_active" in data or "email" in data or "password" in data or "phone" in data:
            return await self.update_account(id, data)
        status = data.get("status", "available")
        return await self.update_account_status(id, status)

    async def delete(self, id: int) -> bool:
        """Permanently delete an account from the database."""
        return await self.hard_delete_account(id)

    async def get_available_accounts(self) -> List[Dict[str, Any]]:
        """
        Get all available accounts (not in cooldown or quarantine).

        Returns accounts where:
        - status = 'available'
        - cooldown_until is NULL or in the past
        - quarantine_until is NULL or in the past
        - is_active = TRUE

        Sorted by last_used_at ASC (LRU - least recently used first).

        Returns:
            List of account dictionaries with decrypted passwords
        """
        async with self.db.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT id, email, password, phone, status,
                       last_used_at, cooldown_until, quarantine_until,
                       consecutive_failures, total_uses, is_active,
                       created_at, updated_at
                FROM vfs_account_pool
                WHERE is_active = TRUE
                  AND status = 'available'
                  AND (cooldown_until IS NULL OR cooldown_until <= NOW())
                  AND (quarantine_until IS NULL OR quarantine_until <= NOW())
                ORDER BY last_used_at ASC NULLS FIRST
                """)

            accounts = []
            for row in rows:
                account = dict(row)
                # Decrypt password
                try:
                    account["password"] = decrypt_password(account["password"])
                except Exception as e:
                    logger.error(f"Failed to decrypt password for account {account['id']}: {e}")
                    continue
                accounts.append(account)

            return accounts

    async def get_account_by_id(
        self, account_id: int, decrypt: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get account by ID.

        Args:
            account_id: Account ID
            decrypt: Whether to decrypt the password (default: True)

        Returns:
            Account dictionary or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, email, password, phone, status,
                       last_used_at, cooldown_until, quarantine_until,
                       consecutive_failures, total_uses, is_active,
                       created_at, updated_at
                FROM vfs_account_pool
                WHERE id = $1
                """,
                account_id,
            )

            if row is None:
                return None

            account = dict(row)
            if decrypt:
                try:
                    account["password"] = decrypt_password(account["password"])
                except Exception as e:
                    logger.error(f"Failed to decrypt password for account {account_id}: {e}")
                    return None

            return account

    async def update_account_status(
        self,
        account_id: int,
        status: str,
        cooldown_until: Optional[datetime] = None,
        quarantine_until: Optional[datetime] = None,
        consecutive_failures: Optional[int] = None,
    ) -> bool:
        """
        Update account status and related fields.

        Args:
            account_id: Account ID
            status: New status ('available', 'in_use', 'cooldown', 'quarantine')
            cooldown_until: Optional cooldown expiration timestamp
            quarantine_until: Optional quarantine expiration timestamp
            consecutive_failures: Optional consecutive failure count

        Returns:
            True if update successful, False otherwise
        """
        async with self.db.get_connection() as conn:
            # Build dynamic update query
            updates = ["status = $2"]
            params: List[Any] = [account_id, status]
            param_idx = 3

            if cooldown_until is not None:
                updates.append(f"cooldown_until = ${param_idx}")
                params.append(cooldown_until)
                param_idx += 1

            if quarantine_until is not None:
                updates.append(f"quarantine_until = ${param_idx}")
                params.append(quarantine_until)
                param_idx += 1

            if consecutive_failures is not None:
                updates.append(f"consecutive_failures = ${param_idx}")
                params.append(consecutive_failures)
                param_idx += 1

            query = f"""
                UPDATE vfs_account_pool
                SET {', '.join(updates)}
                WHERE id = $1
            """

            result = await conn.execute(query, *params)
            return bool(result == "UPDATE 1")

    async def acquire_next_available_account(self) -> Optional[Dict[str, Any]]:
        """
        Atomically acquire the next available account using SELECT FOR UPDATE SKIP LOCKED.

        This is safe for multiple concurrent workers/instances sharing the same database.
        Combines the SELECT and UPDATE in a single transaction to prevent TOCTOU races.

        Returns:
            Account dictionary with decrypted password if available, None otherwise
        """
        async with self.db.get_connection() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""
                    UPDATE vfs_account_pool
                    SET status = 'in_use',
                        last_used_at = NOW()
                    WHERE id = (
                        SELECT id FROM vfs_account_pool
                        WHERE is_active = TRUE
                          AND status = 'available'
                          AND (cooldown_until IS NULL OR cooldown_until <= NOW())
                          AND (quarantine_until IS NULL OR quarantine_until <= NOW())
                        ORDER BY last_used_at ASC NULLS FIRST
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id, email, password, phone, status,
                              last_used_at, cooldown_until, quarantine_until,
                              consecutive_failures, total_uses, is_active,
                              created_at, updated_at
                """)

                if row is None:
                    return None

                account = dict(row)
                # Decrypt password
                try:
                    account["password"] = decrypt_password(account["password"])
                except Exception as e:
                    logger.error(f"Failed to decrypt password for account {account['id']}: {e}")
                    # Revert status since we can't use this account
                    await conn.execute(
                        "UPDATE vfs_account_pool SET status = 'available' WHERE id = $1",
                        account["id"],
                    )
                    return None

                return account

    async def mark_account_in_use(self, account_id: int) -> bool:
        """
        Mark account as in use.

        Args:
            account_id: Account ID

        Returns:
            True if successful, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE vfs_account_pool
                SET status = 'in_use',
                    last_used_at = NOW()
                WHERE id = $1
                """,
                account_id,
            )
            return bool(result == "UPDATE 1")

    async def release_account(
        self,
        account_id: int,
        result_status: str,
        cooldown_until: Optional[datetime] = None,
        quarantine_until: Optional[datetime] = None,
    ) -> bool:
        """
        Release account back to pool with appropriate status.

        Args:
            account_id: Account ID
            result_status: Result of the usage
                ('success', 'no_slot', 'login_fail', 'error', 'banned')
            cooldown_until: Optional cooldown expiration timestamp
            quarantine_until: Optional quarantine expiration timestamp

        Returns:
            True if successful, False otherwise
        """
        async with self.db.get_connection() as conn:
            # Determine new status and failure handling
            if result_status in ("success", "no_slot"):
                # Success or no slot - cooldown, reset failures
                new_status = "cooldown"
                consecutive_failures = 0
                total_uses_increment = 1
            elif result_status in ("login_fail", "error"):
                # Increment failures, check for quarantine
                row = await conn.fetchrow(
                    "SELECT consecutive_failures FROM vfs_account_pool WHERE id = $1",
                    account_id,
                )
                if row:
                    current_failures = row["consecutive_failures"]
                    consecutive_failures = current_failures + 1
                    total_uses_increment = 1
                    # Quarantine handled by caller via quarantine_until parameter
                    new_status = "quarantine" if quarantine_until else "available"
                else:
                    logger.error(f"Account {account_id} not found for release")
                    return False
            elif result_status == "banned":
                # Banned - quarantine
                new_status = "quarantine"
                consecutive_failures = None  # Don't reset on ban
                total_uses_increment = 1
            else:
                logger.error(f"Invalid result_status: {result_status}")
                return False

            # Update account
            update_parts = [
                "status = $2",
                "total_uses = total_uses + $3",
            ]
            params: List[Any] = [account_id, new_status, total_uses_increment]
            param_idx = 4

            if consecutive_failures is not None:
                update_parts.append(f"consecutive_failures = ${param_idx}")
                params.append(consecutive_failures)
                param_idx += 1

            if cooldown_until is not None:
                update_parts.append(f"cooldown_until = ${param_idx}")
                params.append(cooldown_until)
                param_idx += 1

            if quarantine_until is not None:
                update_parts.append(f"quarantine_until = ${param_idx}")
                params.append(quarantine_until)
                param_idx += 1

            query = f"""
                UPDATE vfs_account_pool
                SET {', '.join(update_parts)}
                WHERE id = $1
            """

            result = await conn.execute(query, *params)
            return bool(result == "UPDATE 1")

    async def log_usage(
        self,
        account_id: int,
        mission_code: str,
        session_number: int,
        result: str,
        started_at: datetime,
        request_id: Optional[int] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> int:
        """
        Log account usage to account_usage_log table.

        Args:
            account_id: Account ID
            mission_code: Mission/country code
            session_number: Session number
            result: Result status ('success', 'no_slot', 'login_fail', 'error', 'banned')
            started_at: Usage start timestamp
            request_id: Optional appointment request ID
            error_message: Optional error message
            completed_at: Optional completion timestamp

        Returns:
            Log entry ID
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO account_usage_log
                (account_id, mission_code, session_number, request_id, result,
                 error_message, started_at, completed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                account_id,
                mission_code,
                session_number,
                request_id,
                result,
                error_message,
                started_at,
                completed_at or datetime.now(timezone.utc),
            )
            return row["id"] if row else 0

    async def get_next_available_cooldown_time(self) -> Optional[datetime]:
        """
        Get the earliest cooldown expiration time for accounts in cooldown.

        Returns:
            Earliest cooldown_until timestamp, or None if no accounts in cooldown
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT MIN(cooldown_until) as earliest_cooldown
                FROM vfs_account_pool
                WHERE is_active = TRUE
                  AND status = 'cooldown'
                  AND cooldown_until > NOW()
                """)
            return row["earliest_cooldown"] if row and row["earliest_cooldown"] else None

    async def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get account pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE is_active = TRUE) as total_active,
                    COUNT(*) FILTER (
                        WHERE is_active = TRUE AND status = 'available'
                        AND (cooldown_until IS NULL OR cooldown_until <= NOW())
                        AND (quarantine_until IS NULL OR quarantine_until <= NOW())
                    ) as available,
                    COUNT(*) FILTER (WHERE is_active = TRUE AND status = 'in_use') as in_use,
                    COUNT(*) FILTER (WHERE is_active = TRUE AND status = 'cooldown') as in_cooldown,
                    COUNT(*) FILTER (
                        WHERE is_active = TRUE AND status = 'quarantine'
                    ) as quarantined,
                    AVG(total_uses) FILTER (WHERE is_active = TRUE) as avg_uses,
                    MAX(total_uses) FILTER (WHERE is_active = TRUE) as max_uses
                FROM vfs_account_pool
                """)

            return {
                "total_active": row["total_active"] or 0,
                "available": row["available"] or 0,
                "in_use": row["in_use"] or 0,
                "in_cooldown": row["in_cooldown"] or 0,
                "quarantined": row["quarantined"] or 0,
                "avg_uses": float(row["avg_uses"]) if row["avg_uses"] else 0.0,
                "max_uses": row["max_uses"] or 0,
            }

    async def create_account(
        self,
        email: str,
        password: str,
        phone: str,
    ) -> int:
        """
        Create a new account in the pool.

        Args:
            email: Account email
            password: Plain text password (will be encrypted)
            phone: Phone number

        Returns:
            Created account ID
        """
        encrypted_password = encrypt_password(password)

        async with self.db.get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO vfs_account_pool (email, password, phone)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                email,
                encrypted_password,
                phone,
            )
            return row["id"] if row else 0

    async def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts (active and inactive) for dashboard listing."""
        async with self.db.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT id, email, phone, status, is_active,
                       last_used_at, created_at, updated_at
                FROM vfs_account_pool
                ORDER BY created_at DESC
                """)
            return [dict(row) for row in rows]

    async def update_account(self, account_id: int, data: Dict[str, Any]) -> bool:
        """
        Update account fields (email, password, phone, is_active).

        Args:
            account_id: Account ID
            data: Fields to update

        Returns:
            True if update successful, False otherwise
        """
        updates: List[str] = []
        params: List[Any] = [account_id]
        param_idx = 2

        if "email" in data and data["email"] is not None:
            updates.append(f"email = ${param_idx}")
            params.append(data["email"])
            param_idx += 1

        if "password" in data and data["password"] is not None:
            updates.append(f"password = ${param_idx}")
            params.append(encrypt_password(data["password"]))
            param_idx += 1

        if "phone" in data and data["phone"] is not None:
            updates.append(f"phone = ${param_idx}")
            params.append(data["phone"])
            param_idx += 1

        if "is_active" in data and data["is_active"] is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(data["is_active"])
            param_idx += 1

        if not updates:
            return False

        updates.append("updated_at = NOW()")

        query = f"""
            UPDATE vfs_account_pool
            SET {', '.join(updates)}
            WHERE id = $1
        """

        async with self.db.get_connection() as conn:
            result = await conn.execute(query, *params)
            return bool(result == "UPDATE 1")

    async def hard_delete_account(self, account_id: int) -> bool:
        """
        Permanently delete an account from the database.

        Related records in account_usage_log are automatically removed
        via the ON DELETE CASCADE constraint defined in the migration.

        Args:
            account_id: Account ID

        Returns:
            True if successful, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM vfs_account_pool
                WHERE id = $1
                """,
                account_id,
            )
            return bool(result == "DELETE 1")

    async def deactivate_account(self, account_id: int) -> bool:
        """
        Soft-delete an account by setting is_active = FALSE.

        Args:
            account_id: Account ID

        Returns:
            True if successful, False otherwise
        """
        async with self.db.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE vfs_account_pool
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = $1
                """,
                account_id,
            )
            return bool(result == "UPDATE 1")
