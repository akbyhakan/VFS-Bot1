"""Payment processing service for VFS appointment booking."""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page


class PaymentMethod(Enum):
    """Payment method types."""

    MANUAL = "manual"  # Wait for user to pay manually


class PaymentService:
    """Handle payment processing for VFS appointments."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize payment service.

        Args:
            config: Payment configuration
        """
        self.config = config
        method_str = config.get("method", "manual")
        self.method = PaymentMethod(method_str)
        self.timeout = config.get("timeout", 300)  # 5 minutes default

    async def process_payment(
        self,
        page: Page,
        user_id: int,
        amount: Optional[float] = None,
        card_details: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Process payment for appointment booking.

        Args:
            page: Playwright page object (on payment page)
            user_id: User ID for logging
            amount: Payment amount (if known)
            card_details: Card details (not used - manual payment only)

        Returns:
            True if payment successful
        """
        # SECURITY: Ensure card_details are never logged
        # Create safe version for logging (without sensitive data)
        safe_log_data = {
            "user_id": user_id,
            "method": self.method.value,
            "amount": amount if amount else "not_specified",
        }
        logger.info(f"Processing payment: {safe_log_data}")

        return await self._process_manual_payment(page, user_id, amount)

    async def _process_manual_payment(
        self, page: Page, user_id: int, amount: Optional[float]
    ) -> bool:
        """
        Process manual payment (wait for user to complete).

        Args:
            page: Playwright page object
            user_id: User ID
            amount: Payment amount

        Returns:
            True if payment confirmed
        """
        logger.info(
            f"🔔 MANUAL PAYMENT REQUIRED for user {user_id}"
            + (f" - Amount: {amount}" if amount else "")
        )
        logger.info(f"⏳ Waiting up to {self.timeout}s for payment completion...")

        # Log payment details
        payment_record = {
            "user_id": user_id,
            "method": "manual",
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "waiting",
        }
        logger.info(f"Payment record: {payment_record}")

        # Wait for user to complete payment
        # Look for common payment success indicators
        try:
            # Wait for confirmation page or success message
            # This is VFS-specific - adjust selectors as needed
            await asyncio.wait_for(self._wait_for_payment_confirmation(page), timeout=self.timeout)

            logger.info(f"✅ Payment confirmed for user {user_id}")
            payment_record["status"] = "success"
            payment_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            return True

        except asyncio.TimeoutError:
            logger.error(f"❌ Payment timeout after {self.timeout}s for user {user_id}")
            payment_record["status"] = "timeout"
            return False
        except Exception as e:
            logger.error(f"❌ Payment error for user {user_id}: {e}")
            payment_record["status"] = "error"
            payment_record["error"] = str(e)
            return False

    async def _wait_for_payment_confirmation(self, page: Page) -> None:
        """
        Wait for payment confirmation indicators.

        Args:
            page: Playwright page object
        """
        # Multiple possible success indicators
        selectors = [
            ".payment-success",
            ".payment-confirmed",
            ".booking-confirmed",
            "text=Payment Successful",
            "text=Payment Confirmed",
            "text=Booking Confirmed",
        ]

        # Wait for any of these selectors
        tasks = [
            asyncio.create_task(page.wait_for_selector(sel, timeout=self.timeout * 1000))
            for sel in selectors
        ]

        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            # Drain exceptions from done tasks to prevent
            # "Task exception was never retrieved" warnings
            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None:
                    logger.warning(
                        f"Payment selector task completed with exception: {exc}",
                        exc_info=exc,
                    )
        finally:
            # Cancel remaining tasks and await them
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
