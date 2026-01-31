"""PART 2: VFS Otomatik Randevu Alma Servisi."""

import asyncio
import logging
import random
import re
from typing import Dict, Any, List

from playwright.async_api import Page

from .otp_webhook import get_otp_service

logger = logging.getLogger(__name__)


# VFS Form Selectors with Fallback Support
# Each selector can be a string (single selector) or a list (fallback chain)
VFS_SELECTORS = {
    # Detaylar Formu - Başvuru Sahibi
    "first_name": ["#mat-input-3", 'input[formcontrolname="firstName"]', 'input[name="firstName"]'],
    "last_name": ["#mat-input-4", 'input[formcontrolname="lastName"]', 'input[name="lastName"]'],
    "gender_dropdown": ["#mat-select-value-3", 'mat-select[formcontrolname="gender"]'],
    "gender_female": '//mat-option[contains(., "Female")]',
    "gender_male": '//mat-option[contains(., "Male")]',
    "birth_date": [
        "#dateOfBirth",
        'input[formcontrolname="dateOfBirth"]',
        'input[name="dateOfBirth"]',
    ],
    "nationality_dropdown": ["#mat-select-value-4", 'mat-select[formcontrolname="nationality"]'],
    "nationality_turkey": (
        '(//mat-option[contains(., "Turkey")])[1] | ' '(//mat-option[contains(., "Türkiye")])[1]'
    ),
    "passport_number": [
        "#mat-input-5",
        'input[formcontrolname="passportNumber"]',
        'input[name="passportNumber"]',
    ],
    "passport_expiry": [
        "#passportExpirtyDate",
        'input[formcontrolname="passportExpiry"]',
        'input[name="passportExpiry"]',
    ],
    "phone_code": ["#mat-input-6", 'input[formcontrolname="phoneCode"]', 'input[name="phoneCode"]'],
    "phone_number": [
        "#mat-input-7",
        'input[formcontrolname="phoneNumber"]',
        'input[name="phoneNumber"]',
    ],
    "email": [
        "#mat-input-8",
        'input[formcontrolname="email"]',
        'input[name="email"]',
        'input[type="email"]',
    ],
    "child_checkbox": ["#mat-mdc-checkbox-0-input", 'input[formcontrolname="childWithParent"]'],
    # Butonlar
    "save_button": ['//button[contains(., "Kaydet")]', 'button[type="submit"]'],
    "add_another_button": [
        '//button[contains(., "Başka Başvuru ekle")]',
        '//button[contains(., "Add Another")]',
    ],
    "continue_button": [
        '//button[contains(., "Devam et")]',
        '//button[contains(., "Continue")]',
        "button.continue-btn",
    ],
    "back_button": ['//button[contains(., "Geri Dön")]', '//button[contains(., "Back")]'],
    "online_pay_button": ["#trigger", 'button[id*="pay"]', '//button[contains(., "Online")]'],
    # Takvim
    "available_date_cell": [".fc-daygrid-day.available", ".available-date"],
    "time_slot_button": [
        '//button[contains(., "Seç")]',
        '//button[contains(., "Select")]',
        ".time-slot-btn",
    ],
    "load_more_times": [
        '//button[contains(., "Daha Fazla Yükle")]',
        '//button[contains(., "Load More")]',
    ],
    "next_month_button": [
        '//button[contains(@aria-label, "next")]',
        ".next-month",
        "button.fc-next-button",
    ],
    # Checkboxlar (Gözden Geçir ve Öde)
    "terms_checkbox": ['input[type="checkbox"]', ".terms-checkbox"],
    # Ödeme Sayfası (Banka)
    "card_number": ['input[name="pan"]', 'input[name="cardNumber"]', 'input[placeholder*="Card"]'],
    "expiry_month": [
        'select[name="Ecom_Payment_Card_ExpDate_Month"]',
        'select[name="expiryMonth"]',
    ],
    "expiry_year": ['select[name="Ecom_Payment_Card_ExpDate_Year"]', 'select[name="expiryYear"]'],
    "cvv": ['input[name="cv2"]', 'input[name="cvv"]', 'input[placeholder*="CVV"]'],
    "payment_submit": ["#btnSbmt", 'button[type="submit"]', ".payment-submit"],
    # 3D Secure OTP
    "otp_input": ["#sifre3dinput", 'input[name="otp"]', 'input[placeholder*="OTP"]'],
    "otp_submit": ["#DevamEt", 'button[type="submit"]', '//button[contains(., "Submit")]'],
    # Overlay/Spinner
    "overlay": [".ngx-overlay", ".loading-overlay", ".spinner-overlay"],
    # Captcha Modal
    "captcha_modal": ['//*[contains(text(), "Captcha")]', ".captcha-modal"],
    "captcha_submit": ['//button[contains(., "Submit")]', "button.captcha-submit"],
}


def get_selector_with_fallback(selector_name: str) -> List[str]:
    """
    Get selector(s) for a given name, ensuring it's always a list for fallback support.

    Args:
        selector_name: Name of the selector in VFS_SELECTORS

    Returns:
        List of selector strings to try in order
    """
    selector = VFS_SELECTORS.get(selector_name)
    if selector is None:
        raise ValueError(f"Unknown selector name: {selector_name}")

    # Ensure we always return a list
    if isinstance(selector, list):
        return [str(s) for s in selector]
    else:
        return [str(selector)]


async def try_selectors(
    page: Page, selectors: List[str], action: str = "click", text: str | None = None, timeout: int = 5000
) -> bool:
    """
    Try multiple selectors in order until one works.

    Args:
        page: Playwright page
        selectors: List of CSS/XPath selectors to try
        action: 'click', 'fill', 'wait', 'count'
        text: Text to fill (for 'fill' action)
        timeout: Timeout per selector in ms

    Returns:
        True if action succeeded, False otherwise

    Raises:
        SelectorNotFoundError: If no selector works
    """
    from ..core.exceptions import SelectorNotFoundError

    _last_error = None
    for selector in selectors:
        try:
            element = page.locator(selector)

            if action == "click":
                await element.click(timeout=timeout)
                return True
            elif action == "fill":
                await element.fill(text or "", timeout=timeout)
                return True
            elif action == "wait":
                await element.wait_for(timeout=timeout)
                return True
            elif action == "count":
                count = await element.count()
                return bool(count > 0)
            elif action == "wait_hidden":
                await element.wait_for(state="hidden", timeout=timeout)
                return True

        except Exception as e:
            _last_error = e
            continue

    # No selector worked
    raise SelectorNotFoundError(
        selector_name=str(selectors[0]) if selectors else "unknown", tried_selectors=selectors
    )


def resolve_selector(selector_key: str) -> List[str]:
    """
    Resolve a selector key to a list of selectors.
    Always returns a list for consistent handling.

    Args:
        selector_key: Key in VFS_SELECTORS or direct selector string

    Returns:
        List of selector strings
    """
    if selector_key in VFS_SELECTORS:
        value = VFS_SELECTORS[selector_key]
        return [str(v) for v in value] if isinstance(value, list) else [str(value)]
    return [selector_key]


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
        Tries multiple overlay selectors.

        Args:
            page: Playwright page
            timeout: Maximum wait time in ms
        """
        try:
            selectors = resolve_selector("overlay")
            for selector in selectors:
                try:
                    overlay = page.locator(selector)
                    if await overlay.count() > 0:
                        await overlay.wait_for(state="hidden", timeout=timeout)
                        logger.debug(f"Overlay disappeared: {selector}")
                        return
                except Exception:
                    continue
        except Exception:
            pass  # Overlay might not exist, continue

    async def human_type(self, page: Page, selector_key: str, text: str) -> None:
        """
        Type text with human-like delays and fallback selector support.

        Args:
            page: Playwright page
            selector_key: Selector key in VFS_SELECTORS or direct selector
            text: Text to type

        Raises:
            SelectorNotFoundError: If no selector works
        """
        from ..core.exceptions import SelectorNotFoundError

        selectors = resolve_selector(selector_key)
        _last_error = None

        for selector in selectors:
            try:
                await page.click(selector)
                await page.fill(selector, "")  # Clear first

                for char in text:
                    await page.type(selector, char, delay=random.randint(50, 150))
                    if random.random() < 0.1:  # 10% chance of small pause
                        await asyncio.sleep(random.uniform(0.1, 0.3))

                logger.debug(f"Successfully typed into: {selector}")
                return  # Success

            except Exception as e:
                _last_error = e
                logger.debug(f"Selector '{selector}' failed: {e}, trying next...")
                continue

        # No selector worked
        raise SelectorNotFoundError(selector_key, selectors)

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
        With improved error detection for page structure changes.

        Args:
            page: Playwright page
            reservation: Reservation data with person_count and preferred_dates

        Returns:
            Dict with match status and details
        """
        from ..core.exceptions import SelectorNotFoundError

        required_capacity = reservation["person_count"]
        preferred_dates = [self.normalize_date(d) for d in reservation["preferred_dates"]]

        page_content = await page.content()

        # Pattern: "X Başvuru sahipleri .... : DD-MM-YYYY"
        pattern = r"(\d+)\s*Başvuru sahipleri.*?:\s*(\d{2}-\d{2}-\d{4})"
        match = re.search(pattern, page_content)

        if not match:
            # Check if page structure might have changed
            expected_keywords = ["Başvuru", "applicant", "appointment", "randevu"]
            has_expected_content = any(
                kw.lower() in page_content.lower() for kw in expected_keywords
            )

            if not has_expected_content:
                # Page structure likely changed - this is a critical error
                logger.error(
                    "CRITICAL: Page structure may have changed - "
                    "expected keywords not found. Manual review required."
                )
                raise SelectorNotFoundError("double_match_pattern", tried_selectors=[pattern])

            # Keywords found but pattern didn't match - might be no availability
            logger.warning("Appointment info pattern not found, but page seems valid")
            return {
                "match": False,
                "capacity_match": False,
                "date_match": False,
                "found_capacity": 0,
                "found_date": None,
                "message": "Randevu bilgisi bulunamadı (sayfa yapısı kontrol edildi)",
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
        Fill single applicant form with fallback selector support.

        Args:
            page: Playwright page
            person: Person data
            index: Person index (0-based)
        """
        logger.info(
            f"Filling form for person {index + 1}: {person['first_name']} {person['last_name']}"
        )

        # Wait for VFS requirement - optimized for subsequent forms
        if index == 0:
            vfs_wait = self.config.get("vfs", {}).get("form_wait_seconds", 21)
        else:
            vfs_wait = self.config.get("vfs", {}).get("subsequent_form_wait_seconds", 5)

        logger.info(f"Waiting {vfs_wait} seconds (VFS requirement)...")
        await asyncio.sleep(vfs_wait)

        # Child checkbox (if applicable)
        if person.get("is_child_with_parent", False):
            selectors = resolve_selector("child_checkbox")
            for selector in selectors:
                try:
                    checkbox = page.locator(selector)
                    if await checkbox.count() > 0 and not await checkbox.is_checked():
                        await checkbox.click()
                        logger.info("Child checkbox marked")
                        break
                except Exception:
                    continue

        # First name
        await self.human_type(page, "first_name", person["first_name"].upper())

        # Last name
        await self.human_type(page, "last_name", person["last_name"].upper())

        # Gender dropdown
        gender_dropdown_selectors = resolve_selector("gender_dropdown")
        await try_selectors(page, gender_dropdown_selectors, action="click")
        await asyncio.sleep(0.5)

        gender_option = "gender_female" if person["gender"].lower() == "female" else "gender_male"
        gender_selectors = resolve_selector(gender_option)
        await try_selectors(page, gender_selectors, action="click")

        # Birth date
        await self.human_type(page, "birth_date", person["birth_date"])

        # Nationality dropdown - Select Turkey
        nationality_selectors = resolve_selector("nationality_dropdown")
        await try_selectors(page, nationality_selectors, action="click")
        await asyncio.sleep(0.5)

        turkey_selectors = resolve_selector("nationality_turkey")
        await try_selectors(page, turkey_selectors, action="click")

        # Passport number
        await self.human_type(page, "passport_number", person["passport_number"].upper())

        # Passport expiry
        await self.human_type(page, "passport_expiry", person["passport_expiry_date"])

        # Phone code
        phone_code_selectors = resolve_selector("phone_code")
        for selector in phone_code_selectors:
            try:
                await page.fill(selector, person.get("phone_code", "90"))
                break
            except Exception:
                continue

        # Phone number
        await self.human_type(page, "phone_number", person["phone_number"])

        # Email
        await self.human_type(page, "email", person["email"].upper())

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
        await self.human_type(page, "card_number", card_info["card_number"])
        logger.info("Card number entered")

        # Expiry month
        await page.select_option(VFS_SELECTORS["expiry_month"], card_info["expiry_month"])
        logger.info("Expiry month selected: **")

        # Expiry year
        await page.select_option(VFS_SELECTORS["expiry_year"], card_info["expiry_year"])
        logger.info("Expiry year selected: ****")

        # CVV
        await self.human_type(page, "cvv", card_info["cvv"])
        logger.info("CVV entered")

        # Random wait
        await asyncio.sleep(random.uniform(1, 3))

        # Submit
        await page.click(VFS_SELECTORS["payment_submit"])
        logger.info("Payment form submitted")

    async def handle_3d_secure(self, page: Page, phone_number: str) -> bool:
        """
        Handle 3D Secure OTP verification with optimized waiting.

        Args:
            page: Playwright page
            phone_number: Phone number to receive OTP

        Returns:
            True if verification successful
        """
        logger.info("3D Secure page detected, waiting for OTP...")

        try:
            # Wait for OTP input
            otp_selectors = resolve_selector("otp_input")
            await try_selectors(page, otp_selectors, action="wait", timeout=10000)

            # Wait for OTP from webhook
            otp_code = await self.otp_service.wait_for_payment_otp(
                phone_number=phone_number, timeout=120
            )

            if not otp_code:
                logger.error("OTP not received within timeout")
                return False

            # Enter OTP
            await try_selectors(page, otp_selectors, action="fill", text=otp_code)
            logger.info("OTP entered successfully")

            # Small delay
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Click Continue
            submit_selectors = resolve_selector("otp_submit")
            await try_selectors(page, submit_selectors, action="click")
            logger.info("OTP submitted")

            # Wait for payment confirmation with polling (not fixed sleep)
            confirmation_result = await self._wait_for_payment_confirmation(page)
            return confirmation_result

        except Exception as e:
            logger.error(f"3D Secure error: {e}")
            return False

    async def _wait_for_payment_confirmation(
        self, page: Page, max_wait: int = 60, check_interval: float = 2.0
    ) -> bool:
        """
        Wait for payment confirmation with early exit polling.

        Args:
            page: Playwright page
            max_wait: Maximum wait time in seconds
            check_interval: How often to check in seconds

        Returns:
            True if payment confirmed, False otherwise
        """
        import time

        start_time = time.time()

        while time.time() - start_time < max_wait:
            # Check 1: Redirected to VFS
            current_url = page.url
            if "vfsglobal.com" in current_url:
                logger.info("✅ Redirected to VFS - Payment successful")
                return True

            # Check 2: Success indicators on page
            success_indicators = [
                ".payment-success",
                ".confirmation-message",
                "text=/payment.*successful/i",
                "text=/ödeme.*başarılı/i",
            ]

            for indicator in success_indicators:
                try:
                    count = await page.locator(indicator).count()
                    if count > 0:
                        logger.info(f"✅ Payment success indicator found: {indicator}")
                        return True
                except Exception:
                    continue

            # Check 3: Error indicators
            error_indicators = [
                ".payment-error",
                ".payment-failed",
                "text=/payment.*failed/i",
                "text=/ödeme.*başarısız/i",
            ]

            for indicator in error_indicators:
                try:
                    count = await page.locator(indicator).count()
                    if count > 0:
                        logger.error(f"❌ Payment failed - error indicator: {indicator}")
                        return False
                except Exception:
                    continue

            await asyncio.sleep(check_interval)

        logger.warning(f"Payment confirmation timeout after {max_wait}s")
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
            # Try to find reference number with multiple selector approaches
            # Common patterns: ABC123456, XX-123456, etc.
            reference_element = None
            reference = None

            # Try different selector strategies
            reference_selectors = [
                ".reference-number",
                "[data-testid='reference']",
                "text=/[A-Z]{2,3}\\d{6,}/",
            ]

            for selector in reference_selectors:
                try:
                    reference_element = await page.wait_for_selector(selector, timeout=5000)
                    if reference_element:
                        reference = await reference_element.text_content()
                        if reference:
                            reference = reference.strip()
                            break
                except Exception:
                    continue  # Try next selector

            if not reference_element:
                # Final attempt with longer timeout on first selector
                try:
                    reference_element = await page.wait_for_selector(
                        ".reference-number", timeout=15000
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
                        return {"success": True, "reference": reference, "error": None}
                except Exception:
                    continue

            # If we found a reference but no explicit success message, consider it successful
            if reference:
                logger.info(f"✅ Booking reference found: {reference}")
                return {"success": True, "reference": reference, "error": None}

            # No confirmation found
            logger.warning("⚠️ No booking confirmation elements found")
            return {
                "success": False,
                "reference": None,
                "error": "Confirmation elements not found on page",
            }

        except Exception as e:
            logger.error(f"Error verifying booking confirmation: {e}")
            return {"success": False, "reference": None, "error": str(e)}
