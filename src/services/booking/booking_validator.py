"""Booking validation utilities for VFS booking system."""

import re
from typing import Any, Dict

from loguru import logger
from playwright.async_api import Page

from ...core.exceptions import SelectorNotFoundError
from .selector_utils import DOUBLE_MATCH_PATTERNS


class BookingValidator:
    """Handles booking validation for VFS booking system."""

    def __init__(self):
        """Initialize booking validator."""
        pass

    def normalize_date(self, date_str: str) -> str:
        """
        Normalize date format to DD/MM/YYYY.

        Handles:
        - DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY  → DD/MM/YYYY
        - YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD  → DD/MM/YYYY

        Args:
            date_str: Date string

        Returns:
            Normalized date string in DD/MM/YYYY format
        """
        normalized = date_str.strip().replace("-", "/").replace(".", "/")
        parts = normalized.split("/")
        if len(parts) == 3 and len(parts[0]) == 4:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return normalized

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
        required_capacity = reservation.get("person_count")
        if required_capacity is None:
            logger.error("Missing 'person_count' in reservation data")
            return {
                "match": False,
                "capacity_match": False,
                "date_match": False,
                "found_capacity": 0,
                "found_date": None,
                "message": "Missing person_count in reservation data",
            }
        preferred_dates_raw = reservation.get("preferred_dates")
        if not preferred_dates_raw:
            logger.error("Missing 'preferred_dates' in reservation data")
            return {
                "match": False,
                "capacity_match": False,
                "date_match": False,
                "found_capacity": 0,
                "found_date": None,
                "message": "Missing preferred_dates in reservation data",
            }
        preferred_dates = [self.normalize_date(d) for d in preferred_dates_raw]

        page_content = await page.content()

        # Try Turkish pattern first, then English
        match = None
        for pattern in DOUBLE_MATCH_PATTERNS:
            match = re.search(pattern, page_content)
            if match:
                break

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
                raise SelectorNotFoundError(
                    "double_match_pattern", tried_selectors=DOUBLE_MATCH_PATTERNS
                )

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

        try:
            found_capacity = int(match.group(1))
            found_date = self.normalize_date(match.group(2))
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse regex match groups: {e}. Match: {match.group(0)}")
            return {
                "match": False,
                "capacity_match": False,
                "date_match": False,
                "found_capacity": 0,
                "found_date": None,
                "message": f"Failed to parse appointment data: {e}",
            }

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
                f"❌ Kapasite ({found_capacity}<{required_capacity}) ve "
                f"tarih ({found_date}) uyumsuz"
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
