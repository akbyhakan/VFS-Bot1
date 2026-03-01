"""Session orchestrator for managing VFS booking sessions with account pool."""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from src.constants import AccountPoolConfig
from src.models.database import Database
from src.repositories.account_pool_repository import AccountPoolRepository
from src.repositories.appointment_request_repository import AppointmentRequestRepository

from .account_pool import AccountPool, PooledAccount

if TYPE_CHECKING:
    from src.services.bot.booking_workflow import BookingWorkflow
    from src.services.bot.browser_manager import BrowserManager


class SessionOrchestrator:
    """
    Orchestrates booking sessions across missions using pooled accounts.

    Each session:
    1. Gets active pending missions (grouped by country_code)
    2. For each mission, acquires account from pool
    3. Opens browser, logs in, checks slots
    4. Releases account back to pool with result
    5. Skips completed missions
    """

    def __init__(
        self,
        db: Database,
        account_pool: AccountPool,
        booking_workflow: "BookingWorkflow",
        browser_manager: "BrowserManager",
        max_concurrent_missions: int = AccountPoolConfig.MAX_CONCURRENT_MISSIONS,
    ):
        """
        Initialize session orchestrator.

        Args:
            db: Database instance
            account_pool: Account pool instance
            booking_workflow: Booking workflow instance
            browser_manager: Browser manager instance
            max_concurrent_missions: Maximum concurrent missions per session
        """
        self.db = db
        self.account_pool = account_pool
        self.booking_workflow = booking_workflow
        self.browser_manager = browser_manager
        self.max_concurrent_missions = max_concurrent_missions

        self.appointment_request_repo = AppointmentRequestRepository(db)
        self.account_pool_repo = AccountPoolRepository(db)

        self.session_number = 0
        self._semaphore = asyncio.Semaphore(max_concurrent_missions)

        logger.info(
            f"SessionOrchestrator initialized (max_concurrent_missions={max_concurrent_missions})"
        )

    async def get_active_missions(self) -> Dict[str, List[Any]]:
        """
        Get active pending appointment requests grouped by mission (country_code).

        Returns:
            Dictionary mapping country_code to list of appointment requests
            Example: {"fr": [request1, request2], "be": [request3]}
        """
        # Get all pending appointment requests
        all_pending = await self.appointment_request_repo.get_all(status="pending")

        # Group by country_code (mission)
        missions: Dict[str, List[Any]] = {}
        for request in all_pending:
            country_code = request.country_code.lower()
            if country_code not in missions:
                missions[country_code] = []
            missions[country_code].append(request)

        logger.info(
            f"Found {len(all_pending)} pending requests across {len(missions)} missions: "
            f"{list(missions.keys())}"
        )
        return missions

    async def run_session(self) -> Dict[str, Any]:
        """
        Run one complete session cycle.

        Process:
        1. Get active missions
        2. For each mission, acquire account and process
        3. Handle results and release accounts
        4. Return session summary

        Returns:
            Session summary with statistics
        """
        self.session_number += 1
        session_start = datetime.now(timezone.utc)

        logger.info(f"========== SESSION {self.session_number} START ==========")

        # Get active missions
        missions = await self.get_active_missions()

        if not missions:
            logger.info("No active missions - session complete")
            return {
                "session_number": self.session_number,
                "missions_processed": 0,
                "results": {},
                "duration_seconds": 0,
            }

        # Process missions in parallel (up to max_concurrent_missions)
        tasks = []
        for mission_code, requests in missions.items():
            task = asyncio.create_task(
                self._process_mission_with_semaphore(mission_code, requests),
                name=f"session_{self.session_number}_mission_{mission_code}",
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Compile session summary
        session_end = datetime.now(timezone.utc)
        duration = (session_end - session_start).total_seconds()

        mission_results: dict[str, Any] = {}
        for mission_code, result in zip(missions.keys(), results):
            if isinstance(result, BaseException):
                mission_results[mission_code] = {
                    "status": "error",
                    "error": str(result),
                }
            else:
                mission_results[mission_code] = result

        summary = {
            "session_number": self.session_number,
            "missions_processed": len(missions),
            "results": mission_results,
            "duration_seconds": duration,
        }

        logger.info(
            f"========== SESSION {self.session_number} END "
            f"(duration: {duration:.1f}s, missions: {len(missions)}) =========="
        )

        # Note: Each mission now creates and closes its own isolated BrowserManager instance,
        # so there's no need to restart the shared browser_manager after the session.
        # The shared browser_manager is retained for backwards compatibility and potential
        # future use cases, but is no longer used by mission processing.

        return summary

    async def _process_mission_with_semaphore(
        self,
        mission_code: str,
        requests: List[Any],
    ) -> Dict[str, Any]:
        """
        Process a mission with semaphore for concurrency control.

        Args:
            mission_code: Mission/country code
            requests: List of appointment requests for this mission

        Returns:
            Mission processing result
        """
        async with self._semaphore:
            return await self._process_mission(mission_code, requests)

    async def _acquire_account(
        self,
        mission_code: str,
        requests: List[Any],
    ) -> Optional[PooledAccount]:
        """
        Acquire an account from the pool for the given mission.

        Logs a warning and returns None if no account is available.

        Args:
            mission_code: Mission/country code for logging
            requests: List of appointment requests (used for count logging)

        Returns:
            Acquired PooledAccount, or None if none available
        """
        account = await self.account_pool.acquire_account()
        if not account:
            logger.warning(f"No available account for mission {mission_code}")
            return None

        logger.info(
            f"Mission {mission_code.upper()}: Using account {account.id} ({account.email})"
        )
        return account

    def _create_mission_browser(self) -> "BrowserManager":
        """
        Create an isolated BrowserManager instance for a single mission.

        Uses ``type(self.browser_manager)`` to instantiate a new browser
        with the same config/header/proxy as the injected instance, avoiding
        any runtime import and the circular dependency it would cause
        (vfs_bot.py → session_orchestrator.py → browser_manager.py).

        Each mission gets its own Chromium process with a separate:
        - Cookie jar (no session conflicts)
        - Proxy (from proxy pool via allocate_next())
        - Fingerprint (from fingerprint rotator)

        Returns:
            New BrowserManager instance configured like self.browser_manager
        """
        return type(self.browser_manager)(
            config=self.browser_manager.config,
            header_manager=self.browser_manager.header_manager,
            proxy_manager=self.browser_manager.proxy_manager,
        )

    async def _cleanup_mission_resources(
        self,
        page: Optional[Page],
        browser: Any,
        mission_code: str,
    ) -> None:
        """
        Safely close the mission page and browser, logging any errors.

        Args:
            page: Playwright Page to close, or None if never opened
            browser: BrowserManager instance to close, or None if never started
            mission_code: Mission/country code for log messages
        """
        if page:
            try:
                await page.close()
                logger.debug(f"Closed page for mission {mission_code.upper()}")
            except Exception as close_error:
                logger.error(
                    f"Failed to close page for mission {mission_code}: {close_error}"
                )

        if browser:
            try:
                await browser.close()
                logger.info(f"Closed browser instance for mission {mission_code.upper()}")
            except Exception as browser_close_error:
                logger.error(
                    f"Failed to close browser for mission {mission_code}: {browser_close_error}"
                )

    async def _release_account_with_logging(
        self,
        account: PooledAccount,
        mission_code: str,
        started_at: Any,
        requests: List[Any],
        result: str,
        error_message: Optional[str],
    ) -> None:
        """
        Log account usage and release the account back to the pool.

        Args:
            account: PooledAccount to release
            mission_code: Mission/country code for log metadata
            started_at: Datetime when the mission started
            requests: List of appointment requests processed
            result: Outcome string (e.g. "success", "error")
            error_message: Error message if the mission failed, else None
        """
        completed_at = datetime.now(timezone.utc)

        # Log usage — include all request IDs in metadata for full audit trail
        try:
            request_ids = [req.id for req in requests] if requests else []
            primary_request_id = request_ids[0] if request_ids else None

            await self.account_pool_repo.log_usage(
                account_id=account.id,
                mission_code=mission_code,
                session_number=self.session_number,
                result=result,
                started_at=started_at,
                request_id=primary_request_id,
                error_message=(
                    f"Requests: {request_ids}; Error: {error_message}"
                    if error_message
                    else f"Requests: {request_ids}"
                ),
                completed_at=completed_at,
            )
        except Exception as log_error:
            logger.error(f"Failed to log account usage: {log_error}")

        # Release account back to pool
        try:
            await self.account_pool.release_account(
                account_id=account.id,
                result=result,
                error_message=error_message,
            )
        except Exception as release_error:
            logger.error(f"Failed to release account: {release_error}")

    async def _process_mission(
        self,
        mission_code: str,
        requests: List[Any],
    ) -> Dict[str, Any]:
        """
        Process a single mission (country).

        1. Acquire account from pool
        2. Create isolated browser instance for this mission
        3. Open browser page
        4. Process appointment requests with booking workflow
        5. Release account with result
        6. Clean up browser resources

        Args:
            mission_code: Mission/country code
            requests: List of appointment requests for this mission

        Returns:
            Mission processing result
        """
        logger.info(
            f"Processing mission {mission_code.upper()} "
            f"({len(requests)} request(s)) - session {self.session_number}"
        )

        started_at = datetime.now(timezone.utc)
        account: Optional[PooledAccount] = None
        mission_browser = None
        page: Optional[Page] = None
        result = "error"
        error_message = None

        try:
            account = await self._acquire_account(mission_code, requests)
            if not account:
                return {
                    "status": "no_account",
                    "mission_code": mission_code,
                    "requests_count": len(requests),
                }

            logger.info(f"Starting isolated browser instance for mission {mission_code.upper()}")
            mission_browser = self._create_mission_browser()
            await mission_browser.start()

            page = await mission_browser.new_page()

            result = await self.booking_workflow.process_mission(
                page=page,
                account=account,
                appointment_requests=requests,
            )

            logger.info(f"Mission {mission_code.upper()} completed with result: {result}")

            return {
                "status": "completed",
                "mission_code": mission_code,
                "result": result,
                "account_id": account.id,
                "requests_count": len(requests),
            }

        except Exception as e:
            logger.error(
                f"Error processing mission {mission_code}: {e}",
                exc_info=True,
            )
            error_message = str(e)
            result = "error"

            return {
                "status": "error",
                "mission_code": mission_code,
                "error": error_message,
                "account_id": account.id if account else None,
                "requests_count": len(requests),
            }

        finally:
            await self._cleanup_mission_resources(page, mission_browser, mission_code)
            if account:
                await self._release_account_with_logging(
                    account, mission_code, started_at, requests, result, error_message
                )
