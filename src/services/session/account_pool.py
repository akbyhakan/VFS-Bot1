"""Account pool management with LRU + cooldown strategy."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger

from src.constants import AccountPoolConfig
from src.models.database import Database
from src.repositories.account_pool_repository import AccountPoolRepository


@dataclass
class PooledAccount:
    """Represents a VFS account from the pool."""

    id: int
    email: str
    password: str
    phone: str
    status: str
    last_used_at: Optional[datetime]
    cooldown_until: Optional[datetime]
    quarantine_until: Optional[datetime]
    consecutive_failures: int
    total_uses: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> "PooledAccount":
        """Create PooledAccount from dictionary."""
        required_fields = ("id", "email", "password", "phone", "status", "created_at", "updated_at")
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(
                f"PooledAccount.from_dict: missing required fields: {missing}. "
                f"Available keys: {list(data.keys())}"
            )
        return cls(
            id=data["id"],
            email=data["email"],
            password=data["password"],
            phone=data["phone"],
            status=data["status"],
            last_used_at=data.get("last_used_at"),
            cooldown_until=data.get("cooldown_until"),
            quarantine_until=data.get("quarantine_until"),
            consecutive_failures=data.get("consecutive_failures", 0),
            total_uses=data.get("total_uses", 0),
            is_active=data.get("is_active", True),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )



class AccountPool:
    """
    Manages VFS account pool with LRU + cooldown hybrid allocation strategy.
    
    Thread-safe account acquisition and release with:
    - Cooldown period after each use
    - Quarantine on repeated failures
    - LRU (Least Recently Used) selection among available accounts
    """

    def __init__(
        self,
        db: Database,
        cooldown_seconds: int = AccountPoolConfig.COOLDOWN_SECONDS,
        quarantine_seconds: int = AccountPoolConfig.QUARANTINE_SECONDS,
        max_failures: int = AccountPoolConfig.MAX_FAILURES,
        shutdown_event: Optional[asyncio.Event] = None,
    ):
        """
        Initialize account pool.

        Args:
            db: Database instance
            cooldown_seconds: Cooldown duration after each use (default: 600s / 10 min)
            quarantine_seconds: Quarantine duration on max failures (default: 1800s / 30 min)
            max_failures: Maximum consecutive failures before quarantine (default: 3)
            shutdown_event: Optional shutdown event for graceful termination
        """
        self.db = db
        self.repo = AccountPoolRepository(db)
        self.cooldown_seconds = cooldown_seconds
        self.quarantine_seconds = quarantine_seconds
        self.max_failures = max_failures
        self._shutdown_event = shutdown_event
        self._lock = asyncio.Lock()  # Thread safety for acquire/release operations

        logger.info(
            f"AccountPool initialized (cooldown={cooldown_seconds}s, "
            f"quarantine={quarantine_seconds}s, max_failures={max_failures})"
        )

    async def _sleep_with_shutdown_check(self, sleep_time: float) -> bool:
        """
        Sleep for the specified time while checking for shutdown event.

        Args:
            sleep_time: Time to sleep in seconds

        Returns:
            True if shutdown was signaled during sleep, False if sleep completed normally
        """
        if self._shutdown_event is not None:
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=sleep_time)
                # If we get here, shutdown was signaled
                return True
            except asyncio.TimeoutError:
                # Sleep completed normally
                return False
        else:
            await asyncio.sleep(sleep_time)
            return False

    async def load_accounts(self) -> int:
        """
        Load and validate accounts from database.
        
        This is mainly for initialization and monitoring purposes.
        The actual account selection happens in acquire_account().

        Returns:
            Number of available accounts
        """
        accounts = await self.repo.get_available_accounts()
        logger.info(f"Loaded {len(accounts)} available accounts from pool")
        return len(accounts)

    async def acquire_account(self) -> Optional[PooledAccount]:
        """
        Acquire an account from the pool using LRU + cooldown strategy.
        
        Algorithm:
        1. Filter accounts where status = 'available' AND cooldown_until < NOW()
        2. Exclude quarantined accounts (quarantine_until > NOW())
        3. Sort remaining by last_used_at ASC (LRU first)
        4. Select and mark first account as 'in_use'
        5. Return None if no accounts available
        
        Thread-safe using asyncio.Lock.

        Returns:
            PooledAccount if available, None otherwise
        """
        async with self._lock:
            # Get available accounts (already filtered and LRU-sorted by repository)
            available = await self.repo.get_available_accounts()

            if not available:
                logger.warning("No available accounts in pool")
                return None

            # Select first account (LRU)
            account_dict = available[0]
            account_id = account_dict["id"]

            # Mark as in use
            success = await self.repo.mark_account_in_use(account_id)
            if not success:
                logger.error(f"Failed to mark account {account_id} as in_use")
                return None

            account = PooledAccount.from_dict(account_dict)
            logger.info(
                f"Acquired account {account_id} (email: {account.email}, "
                f"total_uses: {account.total_uses}, last_used: {account.last_used_at})"
            )
            return account

    async def release_account(
        self,
        account_id: int,
        result: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Release account back to pool with appropriate state transition.
        
        State transitions based on result:
        - 'success' or 'no_slot': → cooldown (reset failures)
        - 'login_fail' or 'error': → increment failures; quarantine if >= max_failures
        - 'banned': → quarantine (extended period)

        Args:
            account_id: Account ID to release
            result: Result status ('success', 'no_slot', 'login_fail', 'error', 'banned')
            error_message: Optional error message for logging

        Returns:
            True if release successful, False otherwise
        """
        async with self._lock:
            now = datetime.now(timezone.utc)

            if result in ("success", "no_slot"):
                # Success or no slot - cooldown
                cooldown_until = now + timedelta(seconds=self.cooldown_seconds)
                success = await self.repo.release_account(
                    account_id,
                    result_status=result,
                    cooldown_until=cooldown_until,
                )
                logger.info(
                    f"Released account {account_id} to cooldown "
                    f"(result: {result}, cooldown_until: {cooldown_until})"
                )
                return success

            elif result in ("login_fail", "error"):
                # Login failure or error - check for quarantine
                account = await self.repo.get_account_by_id(account_id, decrypt=False)
                if not account:
                    logger.error(f"Account {account_id} not found for release")
                    return False

                new_failures = account["consecutive_failures"] + 1

                if new_failures >= self.max_failures:
                    # Quarantine
                    quarantine_until = now + timedelta(seconds=self.quarantine_seconds)
                    success = await self.repo.release_account(
                        account_id,
                        result_status=result,
                        quarantine_until=quarantine_until,
                    )
                    logger.warning(
                        f"Account {account_id} QUARANTINED (failures: {new_failures}, "
                        f"quarantine_until: {quarantine_until}, error: {error_message})"
                    )
                else:
                    # Not yet at max failures - back to available
                    success = await self.repo.release_account(
                        account_id,
                        result_status=result,
                    )
                    logger.info(
                        f"Released account {account_id} with failure "
                        f"(result: {result}, failures: {new_failures}, error: {error_message})"
                    )
                return success

            elif result == "banned":
                # Banned - extended quarantine
                quarantine_until = now + timedelta(seconds=self.quarantine_seconds * 2)
                success = await self.repo.release_account(
                    account_id,
                    result_status=result,
                    quarantine_until=quarantine_until,
                )
                logger.error(
                    f"Account {account_id} BANNED - quarantined until {quarantine_until}"
                )
                return success

            else:
                logger.error(f"Invalid result status: {result}")
                return False

    async def get_wait_time(self) -> float:
        """
        Calculate time until next account becomes available.
        
        Returns the time in seconds until the earliest cooldown expires.
        If no accounts are in cooldown, returns 0.

        Returns:
            Wait time in seconds (0 if accounts available now)
        """
        earliest_cooldown = await self.repo.get_next_available_cooldown_time()

        if earliest_cooldown is None:
            return 0.0

        now = datetime.now(timezone.utc)
        wait_time = (earliest_cooldown - now).total_seconds()

        return max(0.0, wait_time)

    async def get_pool_status(self) -> dict:
        """
        Get current pool status for monitoring.

        Returns:
            Dictionary with pool statistics and status
        """
        stats = await self.repo.get_pool_stats()
        wait_time = await self.get_wait_time()

        return {
            **stats,
            "wait_time_seconds": wait_time,
            "config": {
                "cooldown_seconds": self.cooldown_seconds,
                "quarantine_seconds": self.quarantine_seconds,
                "max_failures": self.max_failures,
            },
        }

    async def wait_for_available_account(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for an account to become available.
        
        Polls for available accounts, waiting for cooldowns to expire if needed.

        Args:
            timeout: Maximum time to wait in seconds (None = wait indefinitely)

        Returns:
            True if account became available, False if timeout or shutdown requested
        """
        start_time = datetime.now(timezone.utc)

        while True:
            # Check for shutdown event
            if self._shutdown_event is not None and self._shutdown_event.is_set():
                logger.info("Shutdown event detected, stopping wait for account")
                return False

            # Check if account available now
            available = await self.repo.get_available_accounts()
            if available:
                return True

            # Check timeout
            if timeout:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed >= timeout:
                    logger.warning(f"Timed out waiting for available account ({timeout}s)")
                    return False

            # Calculate wait time
            wait_time = await self.get_wait_time()
            if wait_time <= 0:
                # No cooldowns but still no available accounts
                # This could happen if all accounts are quarantined
                logger.warning("No available accounts and no cooldowns - all accounts may be quarantined")
                
                # Sleep with shutdown event check
                if await self._sleep_with_shutdown_check(10.0):
                    logger.info("Shutdown event detected during sleep")
                    return False
                continue

            # Wait until next cooldown expires (capped at 60s for responsiveness)
            sleep_time = min(wait_time, 60.0)
            logger.info(f"Waiting {sleep_time:.1f}s for account cooldown to expire...")
            
            # Sleep with shutdown event check
            if await self._sleep_with_shutdown_check(sleep_time):
                logger.info("Shutdown event detected during cooldown wait")
                return False
