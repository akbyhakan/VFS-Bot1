"""Payment processing service for VFS appointment booking."""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PaymentMethod(Enum):
    """Payment method types."""

    MANUAL = "manual"  # Wait for user to pay manually
    AUTOMATED_CARD = "automated_card"  # Automated card payment (requires encrypted card details)


class PaymentService:
    """Handle payment processing for VFS appointments."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize payment service.

        Args:
            config: Payment configuration
        """
        self.config = config
        self.method = PaymentMethod(config.get("method", "manual"))
        self.timeout = config.get("timeout", 300)  # 5 minutes default

        # Security warning for automated payments
        if self.method == PaymentMethod.AUTOMATED_CARD:
            logger.warning(
                "⚠️  AUTOMATED CARD PAYMENT ENABLED - ENSURE PCI-DSS COMPLIANCE!"
            )
            logger.warning(
                "Card details must be encrypted with strong encryption (AES-256 minimum)"
            )
            logger.warning("Store encrypted card details in secure vault only")

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
            card_details: Encrypted card details for automated payment

        Returns:
            True if payment successful

        Raises:
            ValueError: If automated payment selected but no card details provided
        """
        logger.info(f"Processing payment for user {user_id} using method: {self.method.value}")

        if self.method == PaymentMethod.MANUAL:
            return await self._process_manual_payment(page, user_id, amount)
        elif self.method == PaymentMethod.AUTOMATED_CARD:
            if not card_details:
                raise ValueError(
                    "Automated card payment requires encrypted card details"
                )
            return await self._process_automated_payment(page, user_id, card_details)
        else:
            logger.error(f"Unknown payment method: {self.method}")
            return False

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
            await asyncio.wait_for(
                self._wait_for_payment_confirmation(page), timeout=self.timeout
            )

            logger.info(f"✅ Payment confirmed for user {user_id}")
            payment_record["status"] = "success"
            payment_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            return True

        except asyncio.TimeoutError:
            logger.error(
                f"❌ Payment timeout after {self.timeout}s for user {user_id}"
            )
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
        tasks = [page.wait_for_selector(sel, timeout=self.timeout * 1000) for sel in selectors]

        try:
            # Race - first one to complete wins
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def _process_automated_payment(
        self, page: Page, user_id: int, encrypted_card_details: Dict[str, str]
    ) -> bool:
        """
        Process automated card payment.

        ⚠️  WARNING: This is a framework implementation only!
        
        BEFORE USING IN PRODUCTION:
        1. Ensure PCI-DSS Level 1 compliance
        2. Use secure card vault (e.g., Stripe, Braintree)
        3. Never log card details
        4. Encrypt all card data with AES-256 minimum
        5. Use TLS 1.2+ for all communications
        6. Implement fraud detection
        7. Get security audit certification

        Args:
            page: Playwright page object
            user_id: User ID
            encrypted_card_details: Encrypted card details

        Returns:
            True if payment successful
        """
        logger.warning("⚠️  AUTOMATED PAYMENT ATTEMPTED - ENSURE PCI-DSS COMPLIANCE!")

        try:
            # ⚠️  AUTOMATED PAYMENT NOT IMPLEMENTED
            # This is a framework/placeholder for future PCI-DSS compliant implementation
            
            logger.error(
                "❌ AUTOMATED PAYMENT NOT IMPLEMENTED - Use manual payment mode instead!"
            )
            logger.error(
                "Automated payment requires: "
                "1. PCI-DSS Level 1 compliance "
                "2. Secure card vault integration "
                "3. Proper encryption/decryption "
                "4. Security audit certification"
            )
            
            # Return false to prevent accidental usage
            return False
            
            # TODO: Future implementation should:
            # 1. Use secure payment gateway (Stripe, Braintree, etc.)
            # 2. Never store card details locally
            # 3. Use tokenization for card data
            # 4. Implement 3D Secure authentication
            # 5. Get PCI-DSS certification
            # 6. Security audit before deployment

        except Exception as e:
            logger.error(f"❌ Automated payment failed for user {user_id}: {e}")
            return False

    def validate_card_details(
        self, encrypted_card_details: Dict[str, str]
    ) -> bool:
        """
        Validate encrypted card details structure.

        Args:
            encrypted_card_details: Encrypted card details

        Returns:
            True if valid structure
        """
        required_keys = ["encrypted_number", "encrypted_expiry", "encrypted_cvv"]
        return all(key in encrypted_card_details for key in required_keys)
