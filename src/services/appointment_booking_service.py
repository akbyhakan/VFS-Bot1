"""PART 2: VFS Otomatik Randevu Alma Servisi."""

import asyncio
import logging
import random
import re
from typing import Dict, Any

from playwright.async_api import Page

from .otp_webhook import get_otp_service

logger = logging.getLogger(__name__)


# VFS Form Selector'ları
VFS_SELECTORS = {
    # Detaylar Formu - Başvuru Sahibi
    "first_name": "#mat-input-3",
    "last_name": "#mat-input-4",
    "gender_dropdown": "#mat-select-value-3",
    "gender_female": '//mat-option[contains(., "Female")]',
    "gender_male": '//mat-option[contains(., "Male")]',
    "birth_date": "#dateOfBirth",
    "nationality_dropdown": "#mat-select-value-4",
    "nationality_turkey": (
        '(//mat-option[contains(., "Turkey")])[1] | ' '(//mat-option[contains(., "Türkiye")])[1]'
    ),
    "passport_number": "#mat-input-5",
    "passport_expiry": "#passportExpirtyDate",
    "phone_code": "#mat-input-6",
    "phone_number": "#mat-input-7",
    "email": "#mat-input-8",
    "child_checkbox": "#mat-mdc-checkbox-0-input",
    # Butonlar
    "save_button": '//button[contains(., "Kaydet")]',
    "add_another_button": '//button[contains(., "Başka Başvuru ekle")]',
    "continue_button": '//button[contains(., "Devam et")]',
    "back_button": '//button[contains(., "Geri Dön")]',
    "online_pay_button": "#trigger",
    # Takvim
    "available_date_cell": ".fc-daygrid-day.available",
    "time_slot_button": '//button[contains(., "Seç")]',
    "load_more_times": '//button[contains(., "Daha Fazla Yükle")]',
    "next_month_button": '//button[contains(@aria-label, "next")]',
    # Checkboxlar (Gözden Geçir ve Öde)
    "terms_checkbox": 'input[type="checkbox"]',
    # Ödeme Sayfası (Banka)
    "card_number": 'input[name="pan"]',
    "expiry_month": 'select[name="Ecom_Payment_Card_ExpDate_Month"]',
    "expiry_year": 'select[name="Ecom_Payment_Card_ExpDate_Year"]',
    "cvv": 'input[name="cv2"]',
    "payment_submit": "#btnSbmt",
    # 3D Secure OTP
    "otp_input": "#sifre3dinput",
    "otp_submit": "#DevamEt",
    # Overlay/Spinner
    "overlay": ".ngx-overlay",
    # Captcha Modal
    "captcha_modal": '//*[contains(text(), "Captcha")]',
    "captcha_submit": '//button[contains(., "Submit")]',
}


class AppointmentBookingService:
    """
    VFS Randevu Alma Servisi - PART 2

    Form doldurma, tarih/saat seçimi, ödeme ve 3D Secure işlemleri.
    """

    def __init__(self, config: Dict[str, Any], captcha_solver: Any = None, human_sim: Any = None):
        """
        Initialize booking service.

        Args:
            config: Bot configuration
            captcha_solver: Captcha solver instance
            human_sim: Human simulator instance
        """
        self.config = config
        self.captcha_solver = captcha_solver
        self.human_sim = human_sim
        self.otp_service = get_otp_service()

        logger.info("AppointmentBookingService initialized")

    async def wait_for_overlay(self, page: Page, timeout: int = 30000) -> None:
        """
        Wait for loading overlay to disappear.

        Args:
            page: Playwright page
            timeout: Maximum wait time in ms
        """
        try:
            overlay = page.locator(VFS_SELECTORS["overlay"])
            await overlay.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass  # Overlay might not exist

    async def human_type(self, page: Page, selector: str, text: str) -> None:
        """
        Type text with human-like delays.

        Args:
            page: Playwright page
            selector: Input selector
            text: Text to type
        """
        await page.click(selector)
        await page.fill(selector, "")  # Clear first

        for char in text:
            await page.type(selector, char, delay=random.randint(50, 150))
            if random.random() < 0.1:  # 10% chance of small pause
                await asyncio.sleep(random.uniform(0.1, 0.3))

    def normalize_date(self, date_str: str) -> str:
        """
        Normalize date format (DD-MM-YYYY -> DD/MM/YYYY).

        Args:
            date_str: Date string

        Returns:
            Normalized date string
        """
        return date_str.replace("-", "/")

    async def check_double_match(self, page: Page, reservation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Çift eşleştirme kontrolü: Kapasite + Tarih

        Args:
            page: Playwright page
            reservation: Reservation data with person_count and preferred_dates

        Returns:
            Dict with match status and details
        """
        required_capacity = reservation["person_count"]
        preferred_dates = [self.normalize_date(d) for d in reservation["preferred_dates"]]

        page_content = await page.content()

        # Pattern: "X Başvuru sahipleri .... : DD-MM-YYYY"
        pattern = r"(\d+)\s*Başvuru sahipleri.*?:\s*(\d{2}-\d{2}-\d{4})"
        match = re.search(pattern, page_content)

        if not match:
            return {
                "match": False,
                "capacity_match": False,
                "date_match": False,
                "found_capacity": 0,
                "found_date": None,
                "message": "Randevu bilgisi bulunamadı",
            }

        found_capacity = int(match.group(1))
        found_date = self.normalize_date(match.group(2))

        # 1. Kapasite eşleştirme
        capacity_match = found_capacity >= required_capacity

        # 2. Tarih eşleştirme
        date_match = found_date in preferred_dates

        # 3. Sonuç
        both_match = capacity_match and date_match

        if both_match:
            message = f"✅ Uygun randevu bulundu! {found_capacity} kişilik, {found_date}"
        elif not capacity_match and not date_match:
            message = (
                f"❌ Kapasite ({found_capacity}<{required_capacity}) ve tarih ({found_date}) uyumsuz"
            )
        elif not capacity_match:
            message = f"❌ Yetersiz kapasite: {found_capacity} < {required_capacity}"
        else:
            message = f"❌ Tarih uyumsuz: {found_date} tercih listesinde yok"

        logger.info(message)

        return {
            "match": both_match,
            "capacity_match": capacity_match,
            "date_match": date_match,
            "found_capacity": found_capacity,
            "found_date": found_date,
            "message": message,
        }

    async def fill_applicant_form(self, page: Page, person: Dict[str, Any], index: int = 0) -> None:
        """
        Fill single applicant form.

        Args:
            page: Playwright page
            person: Person data
            index: Person index (0-based)
        """
        logger.info(
            f"Filling form for person {index + 1}: {person['first_name']} {person['last_name']}"
        )

        # Wait for VFS requirement (configurable, default 21 seconds)
        vfs_wait = self.config.get("vfs", {}).get("form_wait_seconds", 21)
        logger.info(f"Waiting {vfs_wait} seconds (VFS requirement)...")
        await asyncio.sleep(vfs_wait)

        # Child checkbox (if applicable)
        if person.get("is_child_with_parent", False):
            checkbox = page.locator(VFS_SELECTORS["child_checkbox"])
            if not await checkbox.is_checked():
                await checkbox.click()
                logger.info("Child checkbox marked")

        # First name
        await self.human_type(page, VFS_SELECTORS["first_name"], person["first_name"].upper())

        # Last name
        await self.human_type(page, VFS_SELECTORS["last_name"], person["last_name"].upper())

        # Gender dropdown
        await page.click(VFS_SELECTORS["gender_dropdown"])
        await asyncio.sleep(0.5)
        gender_selector = (
            VFS_SELECTORS["gender_female"]
            if person["gender"].lower() == "female"
            else VFS_SELECTORS["gender_male"]
        )
        await page.click(gender_selector)

        # Birth date
        await self.human_type(page, VFS_SELECTORS["birth_date"], person["birth_date"])

        # Nationality dropdown - Select Turkey
        await page.click(VFS_SELECTORS["nationality_dropdown"])
        await asyncio.sleep(0.5)
        await page.click(VFS_SELECTORS["nationality_turkey"])

        # Passport number
        await self.human_type(
            page, VFS_SELECTORS["passport_number"], person["passport_number"].upper()
        )

        # Passport expiry
        await self.human_type(
            page, VFS_SELECTORS["passport_expiry"], person["passport_expiry_date"]
        )

        # Phone code
        await page.fill(VFS_SELECTORS["phone_code"], person.get("phone_code", "90"))

        # Phone number
        await self.human_type(page, VFS_SELECTORS["phone_number"], person["phone_number"])

        # Email
        await self.human_type(page, VFS_SELECTORS["email"], person["email"].upper())

        logger.info(f"Form filled for person {index + 1}")

    async def fill_all_applicants(self, page: Page, reservation: Dict[str, Any]) -> None:
        """
        Fill forms for all applicants.

        Args:
            page: Playwright page
            reservation: Reservation data with persons list
        """
        persons = reservation["persons"]
        total = len(persons)

        for index, person in enumerate(persons):
            current = index + 1
            logger.info(f"Processing applicant {current}/{total}...")

            # Fill form
            await self.fill_applicant_form(page, person, index)

            # Wait for overlay
            await self.wait_for_overlay(page)

            # Click Save
            await page.click(VFS_SELECTORS["save_button"])
            logger.info(f"Applicant {current}/{total} saved")

            # Wait for overlay
            await self.wait_for_overlay(page)

            # More persons to add?
            if current < total:
                # Click "Add Another Applicant"
                await page.click(VFS_SELECTORS["add_another_button"])
                await self.wait_for_overlay(page)
                logger.info("Opening form for next applicant...")
            else:
                # Last person - Click Continue
                await page.click(VFS_SELECTORS["continue_button"])
                await self.wait_for_overlay(page)
                logger.info("All applicants saved, continuing...")

        logger.info(f"✅ All {total} applicants processed successfully")

    async def select_appointment_slot(self, page: Page, reservation: Dict[str, Any]) -> bool:
        """
        Select appointment date and time from calendar.

        Args:
            page: Playwright page
            reservation: Reservation data with preferred_dates

        Returns:
            True if slot selected successfully
        """
        logger.info("Selecting appointment slot...")

        await self.wait_for_overlay(page)

        # Check for Captcha
        await self.handle_captcha_if_present(page)

        # Find available dates (green bordered cells)
        available_dates = await page.locator("a.fc-daygrid-day-number").all()

        selected_date = None
        for date_elem in available_dates:
            aria_label = await date_elem.get_attribute("aria-label")
            if aria_label:
                # Check if this date is in preferred dates
                # aria-label format: "23 Ocak 2026"
                await date_elem.click()
                selected_date = aria_label
                logger.info(f"Selected date: {aria_label}")
                break

        if not selected_date:
            logger.error("No available date found")
            return False

        # Wait for time slots to load
        await asyncio.sleep(2)
        await self.wait_for_overlay(page)

        # Select time (preference: 09:00+)
        time_selected = await self.select_preferred_time(page)

        if not time_selected:
            logger.error("No time slot selected")
            return False

        # Click Continue
        await self.wait_for_overlay(page)
        await page.click(VFS_SELECTORS["continue_button"])
        await self.wait_for_overlay(page)

        logger.info("✅ Appointment slot selected")
        return True

    async def select_preferred_time(self, page: Page) -> bool:
        """
        Select first available time slot.

        Note: Current implementation selects first available slot.
        Future enhancement: Implement preference for 09:00+ slots.

        Args:
            page: Playwright page

        Returns:
            True if time selected
        """
        try:
            # Wait for time slots
            await page.wait_for_selector(VFS_SELECTORS["time_slot_button"], timeout=10000)

            # Get all time rows
            time_buttons = await page.locator(VFS_SELECTORS["time_slot_button"]).all()

            if not time_buttons:
                return False

            # Try to find 09:00+ slot
            # For now, just click the first available
            await time_buttons[0].click()
            logger.info("Time slot selected")
            return True

        except Exception as e:
            logger.error(f"Error selecting time: {e}")
            return False

    async def handle_captcha_if_present(self, page: Page) -> bool:
        """
        Handle Captcha popup if present.

        Args:
            page: Playwright page

        Returns:
            True if handled or not present
        """
        try:
            captcha_modal = await page.locator(VFS_SELECTORS["captcha_modal"]).count()

            if captcha_modal == 0:
                return True

            logger.warning("Captcha detected!")

            if self.captcha_solver:
                # Extract sitekey and solve
                sitekey = await page.evaluate(
                    """
                    () => {
                        const widget = document.querySelector('.cf-turnstile, [data-sitekey]');
                        return widget ? widget.getAttribute('data-sitekey') : null;
                    }
                """
                )

                if sitekey:
                    token = await self.captcha_solver.solve_turnstile(page.url, sitekey)
                    if token:
                        # Inject token
                        await page.evaluate(
                            """
                            (token) => {
                                const input = document.querySelector(
                                    '[name="cf-turnstile-response"]'
                                );
                                if (input) input.value = token;
                            }
                        """,
                            token,
                        )

                        # Click submit
                        await page.click(VFS_SELECTORS["captcha_submit"])
                        await self.wait_for_overlay(page)
                        logger.info("Captcha solved")
                        return True

            return False

        except Exception as e:
            logger.error(f"Captcha handling error: {e}")
            return False

    async def skip_services_page(self, page: Page) -> None:
        """
        Skip services page without selecting anything.

        Args:
            page: Playwright page
        """
        logger.info("Services page - skipping...")

        await self.wait_for_overlay(page)
        await page.click(VFS_SELECTORS["continue_button"])
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
        checkboxes = await page.locator(VFS_SELECTORS["terms_checkbox"]).all()

        for i, checkbox in enumerate(checkboxes):
            if not await checkbox.is_checked():
                await checkbox.click()
                logger.info(f"Checkbox {i + 1} checked")

        # Click Online Pay
        await page.click(VFS_SELECTORS["online_pay_button"])
        logger.info("Clicked 'Online Öde'")

        await self.wait_for_overlay(page)

        # Payment disclaimer page - click Continue
        await page.click(VFS_SELECTORS["continue_button"])

        # Random wait 3-7 seconds
        wait_time = random.uniform(3, 7)
        logger.info(f"Waiting {wait_time:.1f} seconds...")
        await asyncio.sleep(wait_time)

        await self.wait_for_overlay(page)

        logger.info("Review and Pay completed")

    async def fill_payment_form(self, page: Page, card_info: Dict[str, str]) -> None:
        """
        Fill bank payment form.

        Args:
            page: Playwright page
            card_info: Card details (card_number, expiry_month, expiry_year, cvv)
        """
        logger.info("Filling payment form...")

        # Card number
        await self.human_type(page, VFS_SELECTORS["card_number"], card_info["card_number"])
        logger.info("Card number entered")

        # Expiry month
        await page.select_option(VFS_SELECTORS["expiry_month"], card_info["expiry_month"])
        logger.info(f"Expiry month selected: {card_info['expiry_month']}")

        # Expiry year
        await page.select_option(VFS_SELECTORS["expiry_year"], card_info["expiry_year"])
        logger.info(f"Expiry year selected: {card_info['expiry_year']}")

        # CVV
        await self.human_type(page, VFS_SELECTORS["cvv"], card_info["cvv"])
        logger.info("CVV entered")

        # Random wait
        await asyncio.sleep(random.uniform(1, 3))

        # Submit
        await page.click(VFS_SELECTORS["payment_submit"])
        logger.info("Payment form submitted")

    async def handle_3d_secure(self, page: Page, phone_number: str) -> bool:
        """
        Handle 3D Secure OTP verification.

        Args:
            page: Playwright page
            phone_number: Phone number to receive OTP

        Returns:
            True if verification successful
        """
        logger.info("3D Secure page detected, waiting for OTP...")

        try:
            # Wait for OTP input
            await page.wait_for_selector(VFS_SELECTORS["otp_input"], timeout=10000)

            # Wait for OTP from webhook
            otp_code = await self.otp_service.wait_for_payment_otp(
                phone_number=phone_number, timeout=120
            )

            if not otp_code:
                logger.error("OTP not received within timeout")
                return False

            # Enter OTP
            await page.fill(VFS_SELECTORS["otp_input"], otp_code)
            logger.info("OTP entered successfully")

            # Small delay
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Click Continue
            await page.click(VFS_SELECTORS["otp_submit"])
            logger.info("OTP submitted")

            # Wait for payment confirmation (configurable, default 60 seconds)
            payment_wait = self.config.get("payment", {}).get("confirmation_wait_seconds", 60)
            logger.info(f"Waiting {payment_wait} seconds for payment confirmation...")
            await asyncio.sleep(payment_wait)

            # Check result
            current_url = page.url
            if "vfsglobal.com" in current_url:
                logger.info("✅ Redirected to VFS - Payment likely successful")
                return True
            else:
                logger.warning(f"Unexpected URL after payment: {current_url}")
                return False

        except Exception as e:
            logger.error(f"3D Secure error: {e}")
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

            # Step 1: Double match check (capacity + date)
            match_result = await self.check_double_match(page, reservation)
            if not match_result["match"]:
                logger.warning(f"Double match failed: {match_result['message']}")
                return False

            # Click Continue to proceed
            await page.click(VFS_SELECTORS["continue_button"])
            await self.wait_for_overlay(page)

            # Step 2: Fill all applicant forms
            await self.fill_all_applicants(page, reservation)

            # Step 3: Select appointment slot
            if not await self.select_appointment_slot(page, reservation):
                logger.error("Failed to select appointment slot")
                return False

            # Step 4: Skip services page
            await self.skip_services_page(page)

            # Step 5: Review and pay
            await self.handle_review_and_pay(page)

            # Step 6: Fill payment form
            if "payment_card" in reservation:
                await self.fill_payment_form(page, reservation["payment_card"])
            else:
                logger.error("No payment card info in reservation")
                return False

            # Step 7: Handle 3D Secure
            phone = reservation["persons"][0]["phone_number"]
            if not await self.handle_3d_secure(page, phone):
                logger.error("3D Secure verification failed")
                return False

            logger.info("=" * 50)
            logger.info("✅ BOOKING FLOW COMPLETED SUCCESSFULLY")
            logger.info("=" * 50)

            return True

        except Exception as e:
            logger.error(f"Booking flow error: {e}", exc_info=True)
            return False

    async def verify_booking_confirmation(self, page: Page) -> Dict[str, Any]:
        """
        Verify booking was successful by checking confirmation elements.
        
        This provides more reliable validation than simple URL checking by looking for:
        - Reference numbers (e.g., ABC123456)
        - Confirmation success messages
        - Booking confirmed indicators
        
        Args:
            page: Playwright page instance
            
        Returns:
            Dictionary with:
                - success: bool - Whether confirmation was verified
                - reference: str or None - Booking reference number if found
                - error: str or None - Error message if verification failed
        """
        try:
            # Try to find reference number
            # Common patterns: ABC123456, XX-123456, etc.
            reference_element = None
            reference = None
            
            try:
                reference_element = await page.wait_for_selector(
                    ".reference-number, [data-testid='reference'], text=/[A-Z]{2,3}\\d{6,}/",
                    timeout=15000
                )
                if reference_element:
                    reference = await reference_element.text_content()
                    if reference:
                        reference = reference.strip()
            except Exception:
                pass  # Reference not found, continue checking other indicators
            
            # Check for success indicators in order of specificity
            success_indicators = [
                ".confirmation-success",
                ".booking-confirmed", 
                "text=/appointment.*confirmed/i",
                "text=/randevu.*onaylandı/i",
                "text=/booking.*successful/i",
                "text=/successfully.*booked/i",
            ]
            
            for indicator in success_indicators:
                try:
                    count = await page.locator(indicator).count()
                    if count > 0:
                        logger.info(f"✅ Booking confirmation verified via indicator: {indicator}")
                        return {
                            "success": True, 
                            "reference": reference,
                            "error": None
                        }
                except Exception:
                    continue
            
            # If we found a reference but no explicit success message, consider it successful
            if reference:
                logger.info(f"✅ Booking reference found: {reference}")
                return {
                    "success": True,
                    "reference": reference,
                    "error": None
                }
            
            # No confirmation found
            logger.warning("⚠️ No booking confirmation elements found")
            return {
                "success": False, 
                "reference": None, 
                "error": "Confirmation elements not found on page"
            }
            
        except Exception as e:
            logger.error(f"Error verifying booking confirmation: {e}")
            return {
                "success": False, 
                "reference": None, 
                "error": str(e)
            }
