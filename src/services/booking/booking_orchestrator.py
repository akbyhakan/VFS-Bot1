"""Booking orchestrator - coordinates all booking steps."""

import asyncio
import logging
import random
from typing import Any, Dict

from playwright.async_api import Page

from .selector_utils import get_selector
from .form_filler import FormFiller
from .slot_selector import SlotSelector
from .payment_handler import PaymentHandler
from .booking_validator import BookingValidator
from ...core.sensitive import SensitiveDict

logger = logging.getLogger(__name__)


class BookingOrchestrator:
    """
    VFS Randevu Alma Servisi - PART 2

    Orchestrates the booking flow by coordinating form filling,
    slot selection, payment, and validation.
    """

    def __init__(self, config: Dict[str, Any], captcha_solver: Any = None, human_sim: Any = None, payment_service: Any = None):
        """
        Initialize booking orchestrator.

        Args:
            config: Bot configuration dictionary
            captcha_solver: Optional captcha solver instance
            human_sim: Optional human simulator for realistic interactions
            payment_service: Optional PaymentService instance for PCI-DSS compliant payment processing

        Example:
            >>> config = {'vfs': {'form_wait_seconds': 21}}
            >>> orchestrator = BookingOrchestrator(config=config)
        """
        self.config = config
        self.captcha_solver = captcha_solver
        self.human_sim = human_sim
        self.payment_service = payment_service

        # Initialize components
        self.form_filler = FormFiller(config, human_sim)
        self.slot_selector = SlotSelector(captcha_solver)
        self.payment_handler = PaymentHandler(config, payment_service)
        self.validator = BookingValidator()

        logger.info("BookingOrchestrator initialized")

    async def wait_for_overlay(self, page: Page, timeout: int = 30000) -> None:
        """
        Wait for loading overlay to disappear.
        Tries multiple overlay selectors.

        Args:
            page: Playwright page
            timeout: Maximum wait time in ms
        """
        await self.form_filler.wait_for_overlay(page, timeout)

    async def skip_services_page(self, page: Page) -> None:
        """
        Skip services page without selecting anything.

        Args:
            page: Playwright page
        """
        logger.info("Services page - skipping...")

        await self.wait_for_overlay(page)
        await page.click(get_selector("continue_button"))
        await self.wait_for_overlay(page)

        logger.info("Services page skipped")

    async def handle_review_and_pay(self, page: Page) -> None:
        """
        Handle review and pay page - check boxes and click Online Pay.

        Args:
            page: Playwright page
        """
        logger.info("Review and Pay page...")

        await self.wait_for_overlay(page)

        # Check both checkboxes
        checkboxes = await page.locator(get_selector("terms_checkbox")).all()

        for i, checkbox in enumerate(checkboxes):
            if not await checkbox.is_checked():
                await checkbox.click()
                logger.info(f"Checkbox {i + 1} checked")

        # Click Online Pay
        await page.click(get_selector("online_pay_button"))
        logger.info("Clicked 'Online Öde'")

        await self.wait_for_overlay(page)

        # Payment disclaimer page - click Continue
        await page.click(get_selector("continue_button"))

        # Random wait 3-7 seconds
        wait_time = random.uniform(3, 7)
        logger.info(f"Waiting {wait_time:.1f} seconds...")
        await asyncio.sleep(wait_time)

        await self.wait_for_overlay(page)

        logger.info("Review and Pay completed")

    async def run_booking_flow(self, page: Page, reservation: Dict[str, Any]) -> bool:
        """
        Run complete booking flow.

        Args:
            page: Playwright page (already on appointment page after slot check)
            reservation: Full reservation data

        Returns:
            True if booking successful
        """
        try:
            logger.info("=" * 50)
            logger.info("STARTING APPOINTMENT BOOKING FLOW")
            logger.info("=" * 50)

            # Step 1: Double match check (capacity + date)
            match_result = await self.validator.check_double_match(page, reservation)
            if not match_result["match"]:
                logger.warning(f"Double match failed: {match_result['message']}")
                return False

            # Click Continue to proceed
            await page.click(get_selector("continue_button"))
            await self.wait_for_overlay(page)

            # Step 2: Fill all applicant forms
            await self.form_filler.fill_all_applicants(page, reservation)

            # Step 3: Select appointment slot
            if not await self.slot_selector.select_appointment_slot(page, reservation):
                logger.error("Failed to select appointment slot")
                return False

            # Step 4: Skip services page
            await self.skip_services_page(page)

            # Step 5: Review and pay
            await self.handle_review_and_pay(page)

            # Step 6: Process payment with PaymentService (PCI-DSS compliant)
            if self.payment_service is None:
                logger.error(
                    "PaymentService is required for payment processing. "
                    "Legacy inline payment mode has been removed for security (PCI-DSS compliance)."
                )
                raise ValueError("PaymentService is required - legacy payment mode removed for PCI-DSS compliance")

            # Use PaymentService for secure payment processing
            user_id = reservation.get("user_id", 0)
            card_details_wrapped = reservation.get("payment_card")
            
            try:
                # Unwrap SensitiveDict at point of use only
                if isinstance(card_details_wrapped, SensitiveDict):
                    card_details = card_details_wrapped.to_dict()
                else:
                    # Fallback for non-SensitiveDict (backward compatibility)
                    card_details = card_details_wrapped
                
                # PaymentService will enforce PCI-DSS security controls
                # It will reject automated payments in production
                payment_success = await self.payment_service.process_payment(
                    page=page,
                    user_id=user_id,
                    card_details=card_details
                )
            finally:
                # Securely wipe card details from memory after use
                if isinstance(card_details_wrapped, SensitiveDict):
                    card_details_wrapped.wipe()
                card_details = None
            
            if not payment_success:
                logger.error("Payment processing failed")
                return False

            logger.info("=" * 50)
            logger.info("✅ BOOKING FLOW COMPLETED SUCCESSFULLY")
            logger.info("=" * 50)

            return True

        except Exception as e:
            logger.error(f"Booking flow error: {e}", exc_info=True)
            return False
