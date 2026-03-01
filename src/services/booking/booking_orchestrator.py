"""Booking orchestrator - coordinates all booking steps."""

import asyncio
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from ...constants import BookingOTPSelectors
from ...core.sensitive import SensitiveDict
from ..otp_manager.otp_webhook import get_otp_service
from ...utils.helpers import random_delay
from .booking_validator import BookingValidator
from .form_filler import FormFiller
from .payment_handler import PaymentHandler
from .selector_utils import get_selector
from .slot_selector import SlotSelector


class BookingOrchestrator:
    """
    VFS Randevu Alma Servisi - PART 2

    Orchestrates the booking flow by coordinating form filling,
    slot selection, payment, and validation.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        captcha_solver: Any = None,
        human_sim: Any = None,
        payment_service: Any = None,
    ):
        """
        Initialize booking orchestrator.

        Args:
            config: Bot configuration dictionary
            captcha_solver: Optional captcha solver instance
            human_sim: Optional human simulator for realistic interactions
            payment_service: Optional PaymentService instance for
                secure payment processing

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
        await random_delay(3, 7)

        await self.wait_for_overlay(page)

        logger.info("Review and Pay completed")

    def _get_otp_service(self):
        """Get OTP service singleton instance."""
        return get_otp_service()

    async def _handle_booking_otp_if_present(self, page: Page) -> bool:
        """
        Handle booking OTP verification if present (country-specific).

        This method checks if the booking OTP screen is visible and handles
        the full OTP flow: generate → input → verify → continue.

        Args:
            page: Playwright page

        Returns:
            True if OTP handled successfully or not present, False on failure
        """
        try:
            # Check if OTP generate button is visible
            otp_generate_button = page.locator(BookingOTPSelectors.GENERATE_BUTTON).first

            is_visible = await otp_generate_button.is_visible()
            if not is_visible:
                logger.debug(
                    "Booking OTP screen not present - skipping (country doesn't require it)"
                )
                return True

            logger.info("Booking OTP screen detected - starting OTP flow")

            # Step 1: Click generate OTP button
            logger.info("Clicking 'Generate OTP' button...")
            await otp_generate_button.click()
            await asyncio.sleep(2)

            # Step 2: Wait for OTP input field to appear
            logger.info("Waiting for OTP input field...")
            otp_input = page.locator(BookingOTPSelectors.INPUT_FIELD)
            await otp_input.wait_for(state="visible", timeout=10000)
            logger.info("OTP input field visible")

            # Step 3: Get OTP from service (email/SMS)
            logger.info("Waiting for OTP from email/SMS (timeout: 120s)...")
            otp_service = self._get_otp_service()
            otp_code = await otp_service.wait_for_appointment_otp(timeout=120)

            if not otp_code:
                logger.error("Failed to receive booking OTP within timeout")
                return False

            # Log masked OTP (show first 2 characters if available)
            masked_otp = f"{otp_code[:2]}****" if len(otp_code) >= 2 else "****"
            logger.info(f"Received booking OTP: {masked_otp}")

            # Step 4: Fill OTP into input field
            logger.info("Filling OTP into input field...")
            await otp_input.fill(otp_code)
            await asyncio.sleep(1)

            # Step 5: Click verify button
            logger.info("Clicking 'Verify' button...")
            verify_button = page.locator(BookingOTPSelectors.VERIFY_BUTTON).first
            await verify_button.click()
            await asyncio.sleep(2)

            # Step 6: Wait for success message
            logger.info("Waiting for OTP verification success message...")
            success_message = page.locator(BookingOTPSelectors.SUCCESS_MESSAGE)
            await success_message.wait_for(state="visible", timeout=10000)
            logger.info("OTP verification successful")

            # Step 7: Click continue button
            logger.info("Clicking 'Continue' button...")
            continue_button = page.locator(BookingOTPSelectors.CONTINUE_BUTTON).first
            await continue_button.click()
            await asyncio.sleep(1)

            # Step 8: Wait for overlay to disappear
            await self.wait_for_overlay(page)

            logger.info("Booking OTP flow completed successfully")
            return True

        except Exception as e:
            logger.error(f"Booking OTP handling failed: {e}", exc_info=True)
            return False

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

            # Early validation: Ensure PaymentService is available before starting expensive flow
            if self.payment_service is None:
                logger.error(
                    "PaymentService is required for payment processing. "
                    "Failing early to avoid wasting resources on booking steps."
                )
                raise ValueError(
                    "PaymentService is required - legacy payment mode "
                    "removed"
                )

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

            # Step 2.5: Handle booking OTP if present (country-specific)
            if not await self._handle_booking_otp_if_present(page):
                logger.error("Booking OTP handling failed")
                return False

            # Step 3: Select appointment slot
            if not await self.slot_selector.select_appointment_slot(page, reservation):
                logger.error("Failed to select appointment slot")
                return False

            # Step 4: Skip services page
            await self.skip_services_page(page)

            # Step 5: Review and pay
            await self.handle_review_and_pay(page)

            # Step 6: Process payment with PaymentService
            # Use PaymentService for secure payment processing
            user_id = reservation.get("user_id", 0)
            card_details_wrapped = reservation.get("payment_card")

            try:
                # Unwrap SensitiveDict at point of use only
                card_details: Optional[Dict[str, Any]] = None
                if isinstance(card_details_wrapped, SensitiveDict):
                    card_details = card_details_wrapped.to_dict()
                else:
                    # Fallback for non-SensitiveDict (backward compatibility)
                    card_details = card_details_wrapped

                payment_success = await self.payment_service.process_payment(
                    page=page, user_id=user_id, card_details=card_details
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
