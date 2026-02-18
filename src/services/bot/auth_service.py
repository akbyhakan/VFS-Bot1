"""VFS authentication service for login and OTP handling."""

import asyncio
import random
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from ...constants import Delays, Timeouts
from ...core.exceptions import LoginError
from ...utils.anti_detection.cloudflare_handler import CloudflareHandler
from ...utils.anti_detection.human_simulator import HumanSimulator
from ...utils.error_capture import ErrorCapture
from ...utils.helpers import safe_navigate, smart_click, smart_fill
from ..captcha_solver import CaptchaSolver


class AuthService:
    """Handles VFS authentication operations including login and OTP verification."""

    def __init__(
        self,
        config: Dict[str, Any],
        captcha_solver: CaptchaSolver,
        human_sim: Optional[HumanSimulator] = None,
        cloudflare_handler: Optional[CloudflareHandler] = None,
        error_capture: Optional[ErrorCapture] = None,
        otp_service: Optional[Any] = None,
    ):
        """
        Initialize authentication service.

        Args:
            config: Bot configuration dictionary
            captcha_solver: CaptchaSolver instance for solving captchas
            human_sim: Optional HumanSimulator for realistic interactions
            cloudflare_handler: Optional CloudflareHandler for bypassing challenges
            error_capture: Optional ErrorCapture for capturing errors
            otp_service: Optional OTP service for receiving OTP codes
        """
        self.config = config
        self.captcha_solver = captcha_solver
        self.human_sim = human_sim
        self.cloudflare_handler = cloudflare_handler
        self.error_capture = error_capture or ErrorCapture()
        self.otp_service = otp_service

    async def login(self, page: Page, email: str, password: str) -> bool:
        """
        Login to VFS website with automatic OTP verification handling.

        This method performs the login flow including filling credentials, solving
        captcha if present, submitting the form, and handling OTP verification if
        required by the VFS system.

        Args:
            page: Playwright page object
            email: User email
            password: User password (plaintext - decrypted from database)

        Returns:
            True if login successful (including OTP verification if required),
            False otherwise
        """
        mission = self.config["vfs"]["mission"]
        return await self.login_for_mission(page, email, password, mission)

    async def login_for_mission(
        self, page: Page, email: str, password: str, mission_code: str
    ) -> bool:
        """
        Login to VFS website for a specific mission/country portal.

        This method performs the login flow including filling credentials, solving
        captcha if present, submitting the form, and handling OTP verification if
        required by the VFS system.

        Args:
            page: Playwright page object
            email: User email
            password: User password (plaintext - decrypted from database)
            mission_code: Mission code (e.g., 'fra', 'bgr') for country-specific login

        Returns:
            True if login successful (including OTP verification if required),
            False otherwise
        """
        try:
            base = self.config["vfs"]["base_url"]
            country = self.config["vfs"]["country"]
            language = self.config["vfs"].get("language", "tr")
            url = f"{base}/{country}/{language}/{mission_code}/login"
            logger.info(f"Navigating to login page: {url}")

            if not await safe_navigate(page, url, timeout=Timeouts.NAVIGATION):
                logger.error(f"Failed to navigate to login page: {url}")
                return False

            # Check for Cloudflare challenge
            if self.cloudflare_handler:
                if not await self.cloudflare_handler.handle_challenge(page):
                    logger.error("Failed to bypass Cloudflare challenge")
                    return False

            # Fill login form with human simulation
            try:
                await smart_fill(page, 'input[name="email"]', email, self.human_sim)
                await asyncio.sleep(random.uniform(*Delays.AFTER_LOGIN_FIELD))
                await smart_fill(page, 'input[name="password"]', password, self.human_sim)
            except Exception as e:
                # Sanitize error message to prevent password leakage
                safe_error = str(e)
                if password and password in safe_error:
                    safe_error = safe_error.replace(password, "[REDACTED]")

                # Create sanitized exception for error capture
                sanitized_exception = LoginError(f"Login form error: {safe_error}")

                # Capture error with sanitized exception
                await self.error_capture.capture(
                    page,
                    sanitized_exception,
                    context={"step": "login", "action": "filling login form"},
                    element_selector='input[name="email"]',
                )
                # Raise with sanitized message and suppress original traceback
                raise LoginError(f"Failed to fill login form: {safe_error}") from None

            # Handle captcha if present
            captcha_present = await page.locator(".g-recaptcha").count() > 0
            if captcha_present:
                site_key = await page.get_attribute(".g-recaptcha", "data-sitekey")
                if site_key:
                    token = await self.captcha_solver.solve_recaptcha(page, site_key, page.url)
                    if token:
                        await self.captcha_solver.inject_captcha_solution(page, token)

            # Submit login with human click
            await smart_click(page, 'button[type="submit"]', self.human_sim)
            await page.wait_for_load_state("networkidle", timeout=Timeouts.NETWORK_IDLE)

            # Check for OTP verification
            logger.info("Checking for OTP verification...")
            if not await self.handle_otp_verification(page):
                logger.error("OTP verification failed")
                return False

            # Wait for page to reload after OTP (if OTP was required)
            await page.wait_for_load_state("networkidle", timeout=Timeouts.NETWORK_IDLE)

            # Check if login successful
            # SPA NOTE: URL is not reliable in SPA — check DOM elements instead
            login_still_visible = await page.locator(
                'input[name="email"], input[name="password"]'
            ).count()
            dashboard_indicators = await page.locator(
                'mat-sidenav, .dashboard-container, a[href*="appointment"], '
                "text=/dashboard|hoş geldiniz|welcome/i"
            ).count()

            if dashboard_indicators > 0 and login_still_visible == 0:
                logger.info("Login successful (verified via DOM)")
                return True
            else:
                logger.error("Login failed - dashboard elements not found")
                return False

        except LoginError:
            # Already sanitized, just re-raise
            raise
        except Exception as e:
            # Sanitize password in error message before logging
            safe_error = str(e)
            if password and password in safe_error:
                safe_error = safe_error.replace(password, "[REDACTED]")
            logger.error(f"Login error: {safe_error}")
            return False

    async def handle_otp_verification(self, page: Page, timeout: int = 120) -> bool:
        """
        Handle OTP verification if required.

        Args:
            page: Playwright page object
            timeout: Maximum time to wait for OTP (default: 120 seconds)

        Returns:
            True if OTP verification successful or not required, False otherwise
        """
        try:
            # Check if OTP input is present
            otp_input = await page.locator('input[name="otp"]').count()

            if otp_input > 0:
                logger.info("OTP verification required, waiting for SMS...")

                if not self.otp_service:
                    logger.error("OTP service not available")
                    return False

                otp_code = await self.otp_service.wait_for_otp(timeout=timeout)

                if otp_code:
                    await smart_fill(page, 'input[name="otp"]', otp_code, self.human_sim)
                    await smart_click(page, 'button[type="submit"]', self.human_sim)
                    logger.info("OTP verification completed")
                    return True
                else:
                    logger.error("OTP not received within timeout")
                    return False

            return True  # No OTP required

        except Exception as e:
            logger.error(f"OTP verification error: {e}")
            return False
