"""Main bot logic with Playwright automation for VFS appointment booking."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from .captcha_solver import CaptchaSolver
from .centre_fetcher import CentreFetcher
from .notification import NotificationService
from ..models.database import Database
from ..utils.anti_detection.cloudflare_handler import CloudflareHandler
from ..utils.anti_detection.fingerprint_bypass import FingerprintBypass
from ..utils.anti_detection.human_simulator import HumanSimulator
from ..utils.anti_detection.stealth_config import StealthConfig
from ..utils.security.header_manager import HeaderManager
from ..utils.security.proxy_manager import ProxyManager
from ..utils.security.session_manager import SessionManager
from ..utils.security.rate_limiter import get_rate_limiter
from ..utils.error_capture import ErrorCapture

logger = logging.getLogger(__name__)


class VFSBot:
    """VFS appointment booking bot using Playwright."""

    def __init__(self, config: Dict[str, Any], db: Database, notifier: NotificationService):
        """
        Initialize VFS bot.

        Args:
            config: Bot configuration dictionary
            db: Database instance
            notifier: Notification service instance
        """
        self.config = config
        self.db = db
        self.notifier = notifier
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.running = False
        self.health_checker = None  # Will be set by main.py if enabled

        # Initialize rate limiter
        self.rate_limiter = get_rate_limiter()

        # Initialize error capture
        self.error_capture = ErrorCapture()

        # Initialize components
        self.captcha_solver = CaptchaSolver(
            provider=config["captcha"]["provider"],
            api_key=config["captcha"].get("api_key", ""),
            manual_timeout=config["captcha"].get("manual_timeout", 120),
        )

        self.centre_fetcher = CentreFetcher(
            base_url=config["vfs"]["base_url"],
            country=config["vfs"]["country"],
            mission=config["vfs"]["mission"],
        )

        # Initialize anti-detection components
        anti_detection_config = config.get("anti_detection", {})
        self.anti_detection_enabled = anti_detection_config.get("enabled", True)

        if self.anti_detection_enabled:
            # Human behavior simulator
            self.human_sim: Optional[HumanSimulator] = HumanSimulator(config.get("human_behavior", {}))

            # Header manager
            self.header_manager: Optional[HeaderManager] = HeaderManager()

            # Session manager
            session_config = config.get("session", {})
            self.session_manager: Optional[SessionManager] = SessionManager(
                session_file=session_config.get("save_file", "data/session.json"),
                token_refresh_buffer=session_config.get("token_refresh_buffer", 5),
            )

            # Cloudflare handler
            self.cloudflare_handler: Optional[CloudflareHandler] = CloudflareHandler(config.get("cloudflare", {}))

            # Proxy manager
            self.proxy_manager: Optional[ProxyManager] = ProxyManager(config.get("proxy", {}))

            logger.info("Anti-detection features initialized")
        else:
            self.human_sim = None
            self.header_manager = None
            self.session_manager = None
            self.cloudflare_handler = None
            self.proxy_manager = None
            logger.info("Anti-detection features disabled")

        logger.info("VFSBot initialized")

    async def start(self) -> None:
        """Start the bot."""
        self.running = True
        logger.info("Starting VFS-Bot...")
        await self.notifier.notify_bot_started()

        async with async_playwright() as playwright:
            # Get proxy configuration if enabled
            proxy_config = None
            if self.anti_detection_enabled and self.proxy_manager and self.proxy_manager.enabled:
                proxy_config = self.proxy_manager.get_playwright_proxy()
                if proxy_config:
                    logger.info(f"Using proxy: {proxy_config['server']}")

            # Get User-Agent from header manager or use default
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            if self.anti_detection_enabled and self.header_manager:
                user_agent = self.header_manager.get_user_agent()

            # Launch browser
            launch_options = {
                "headless": self.config["bot"].get("headless", False),
                "args": ["--disable-blink-features=AutomationControlled"],
            }

            if proxy_config:
                # Note: proxy must be set on context, not browser
                pass

            self.browser = await playwright.chromium.launch(**launch_options)

            # Create context with stealth settings
            context_options: Dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": user_agent,
            }

            if proxy_config:
                context_options["proxy"] = proxy_config

            self.context = await self.browser.new_context(**context_options)

            # Apply stealth configuration if enabled
            if self.anti_detection_enabled and self.config.get("anti_detection", {}).get(
                "stealth_mode", True
            ):
                # The old stealth script is now replaced by StealthConfig
                # which will be applied per-page
                pass
            else:
                # Add basic stealth script for backwards compatibility
                await self.context.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
                )

            try:
                # Start health checker if configured
                if self.health_checker and self.browser:
                    asyncio.create_task(self.health_checker.run_continuous(self.browser))
                    logger.info("Selector health monitoring started")

                await self.run_bot_loop()
            finally:
                await self.stop()

    async def stop(self) -> None:
        """Stop the bot."""
        self.running = False
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        await self.notifier.notify_bot_stopped()
        logger.info("VFS-Bot stopped")

    async def run_bot_loop(self) -> None:
        """Main bot loop to check for slots."""
        while self.running:
            try:
                # Get active users
                users = await self.db.get_active_users()
                logger.info(f"Processing {len(users)} active users")

                for user in users:
                    if not self.running:
                        break

                    await self.process_user(user)

                # Wait before next check
                check_interval = self.config["bot"].get("check_interval", 30)
                logger.info(f"Waiting {check_interval}s before next check...")
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                await self.notifier.notify_error("Bot Loop Error", str(e))
                await asyncio.sleep(60)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def process_user(self, user: Dict[str, Any]) -> None:
        """
        Process a single user's appointment booking.

        Args:
            user: User dictionary from database
        """
        logger.info(f"Processing user: {user['email']}")

        if self.context is None:
            logger.error("Browser context is not initialized")
            return

        page = await self.context.new_page()

        try:
            # Apply anti-detection to new page
            if self.anti_detection_enabled:
                anti_config = self.config.get("anti_detection", {})

                # Apply stealth configuration
                if anti_config.get("stealth_mode", True):
                    await StealthConfig.apply_stealth(page)

                # Apply fingerprint bypass
                if anti_config.get("fingerprint_bypass", True):
                    await FingerprintBypass.apply_all(page)

            # Login
            if not await self.login_vfs(page, user["email"], user["password"]):
                logger.error(f"Login failed for {user['email']}")
                return

            # Check slots
            centres = user["centre"].split(",")
            for centre in centres:
                centre = centre.strip()
                slot = await self.check_slots(page, centre, user["category"], user["subcategory"])

                if slot:
                    await self.notifier.notify_slot_found(centre, slot["date"], slot["time"])

                    # Get personal details
                    details = await self.db.get_personal_details(user["id"])
                    if details:
                        # Fill details and book
                        if await self.fill_personal_details(page, details):
                            reference = await self.book_appointment(
                                page, slot["date"], slot["time"]
                            )
                            if reference:
                                await self.db.add_appointment(
                                    user["id"],
                                    centre,
                                    user["category"],
                                    user["subcategory"],
                                    slot["date"],
                                    slot["time"],
                                    reference,
                                )
                                await self.notifier.notify_booking_success(
                                    centre, slot["date"], slot["time"], reference
                                )
                    break
        except Exception as e:
            logger.error(f"Error processing user {user['email']}: {e}")
            if self.config["bot"].get("screenshot_on_error", True):
                await self.take_screenshot(page, f"error_{user['id']}_{datetime.now().timestamp()}")
        finally:
            await page.close()

    async def login_vfs(self, page: Page, email: str, password: str) -> bool:
        """
        Login to VFS website.

        Args:
            page: Playwright page object
            email: User email
            password: User password

        Returns:
            True if login successful
        """
        try:
            base = self.config["vfs"]["base_url"]
            country = self.config["vfs"]["country"]
            mission = self.config["vfs"]["mission"]
            url = f"{base}/{country}/{mission}/en/login"
            logger.info(f"Navigating to login page: {url}")

            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Check for Cloudflare challenge
            if self.anti_detection_enabled and self.cloudflare_handler:
                if not await self.cloudflare_handler.handle_challenge(page):
                    logger.error("Failed to bypass Cloudflare challenge")
                    return False

            # Fill login form with human simulation
            try:
                if self.anti_detection_enabled and self.human_sim:
                    await self.human_sim.human_type(page, 'input[name="email"]', email)
                    await asyncio.sleep(0.5)
                    await self.human_sim.human_type(page, 'input[name="password"]', password)
                else:
                    await page.fill('input[name="email"]', email)
                    await page.fill('input[name="password"]', password)
            except Exception as e:
                # Capture error with failed selector
                await self.error_capture.capture(
                    page,
                    e,
                    context={"step": "login", "action": "filling login form"},
                    element_selector='input[name="email"]',
                )
                raise

            # Handle captcha if present
            captcha_present = await page.locator(".g-recaptcha").count() > 0
            if captcha_present:
                site_key = await page.get_attribute(".g-recaptcha", "data-sitekey")
                if site_key:
                    token = await self.captcha_solver.solve_recaptcha(page, site_key, page.url)
                    if token:
                        await self.captcha_solver.inject_captcha_solution(page, token)

            # Submit login with human click
            if self.anti_detection_enabled and self.human_sim:
                await self.human_sim.human_click(page, 'button[type="submit"]')
            else:
                await page.click('button[type="submit"]')

            await page.wait_for_load_state("networkidle", timeout=30000)

            # Check if login successful
            if "dashboard" in page.url or "appointment" in page.url:
                logger.info("Login successful")
                return True
            else:
                logger.error("Login failed - not redirected to dashboard")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def check_slots(
        self, page: Page, centre: str, category: str, subcategory: str
    ) -> Optional[Dict[str, str]]:
        """
        Check for available appointment slots.

        Args:
            page: Playwright page object
            centre: VFS centre name
            category: Visa category
            subcategory: Visa subcategory

        Returns:
            Slot information if available, None otherwise
        """
        try:
            # Apply rate limiting before making requests
            await self.rate_limiter.acquire()

            # Navigate to appointment page
            base = self.config["vfs"]["base_url"]
            country = self.config["vfs"]["country"]
            mission = self.config["vfs"]["mission"]
            appointment_url = f"{base}/{country}/{mission}/en/appointment"
            await page.goto(appointment_url, wait_until="networkidle", timeout=30000)

            # Check for Cloudflare challenge
            if self.anti_detection_enabled and self.cloudflare_handler:
                await self.cloudflare_handler.handle_challenge(page)

            # Select centre, category, subcategory
            await page.select_option("select#centres", label=centre)
            await asyncio.sleep(2)

            await page.select_option("select#categories", label=category)
            await asyncio.sleep(2)

            await page.select_option("select#subcategories", label=subcategory)
            await asyncio.sleep(2)

            # Click to check slots with human simulation
            if self.anti_detection_enabled and self.human_sim:
                await self.human_sim.human_click(page, "button#check-slots")
            else:
                await page.click("button#check-slots")
            await asyncio.sleep(3)

            # Check if slots are available
            slots_available = await page.locator(".available-slot").count() > 0

            if slots_available:
                # Get first available slot
                date_content = await page.locator(".slot-date").first.text_content()
                time_content = await page.locator(".slot-time").first.text_content()
                
                date = date_content.strip() if date_content else ""
                time = time_content.strip() if time_content else ""

                logger.info(f"Slot found! Date: {date}, Time: {time}")
                return {"date": date, "time": time}
            else:
                logger.info(f"No slots available for {centre}/{category}/{subcategory}")
                return None

        except Exception as e:
            logger.error(f"Error checking slots: {e}")
            # Capture error with context
            await self.error_capture.capture(
                page,
                e,
                context={
                    "step": "check_slots",
                    "centre": centre,
                    "category": category,
                    "subcategory": subcategory,
                    "action": "checking availability",
                },
            )
            return None

    async def fill_personal_details(self, page: Page, details: Dict[str, Any]) -> bool:
        """
        Fill personal details form.

        Args:
            page: Playwright page object
            details: Personal details dictionary

        Returns:
            True if successful
        """
        try:
            # Wait for form to load
            await page.wait_for_selector("input#first_name", timeout=10000)

            # Fill form fields with human simulation
            if self.anti_detection_enabled and self.human_sim:
                await self.human_sim.human_type(
                    page, "input#first_name", details.get("first_name", "")
                )
                await self.human_sim.human_type(
                    page, "input#last_name", details.get("last_name", "")
                )
                await self.human_sim.human_type(
                    page, "input#passport_number", details.get("passport_number", "")
                )
                await self.human_sim.human_type(page, "input#email", details.get("email", ""))

                if details.get("mobile_number"):
                    await self.human_sim.human_type(
                        page, "input#mobile", details.get("mobile_number", "")
                    )

                if details.get("date_of_birth"):
                    await self.human_sim.human_type(
                        page, "input#dob", details.get("date_of_birth", "")
                    )
            else:
                await page.fill("input#first_name", details.get("first_name", ""))
                await page.fill("input#last_name", details.get("last_name", ""))
                await page.fill("input#passport_number", details.get("passport_number", ""))
                await page.fill("input#email", details.get("email", ""))

                if details.get("mobile_number"):
                    await page.fill("input#mobile", details.get("mobile_number", ""))

                if details.get("date_of_birth"):
                    await page.fill("input#dob", details.get("date_of_birth", ""))

            logger.info("Personal details filled successfully")
            return True

        except Exception as e:
            logger.error(f"Error filling personal details: {e}")
            return False

    async def book_appointment(self, page: Page, date: str, time: str) -> Optional[str]:
        """
        Complete appointment booking.

        Args:
            page: Playwright page object
            date: Appointment date
            time: Appointment time

        Returns:
            Reference number if successful
        """
        try:
            # Click continue/book button with human simulation
            if self.anti_detection_enabled and self.human_sim:
                await self.human_sim.human_click(page, "button#book-appointment")
            else:
                await page.click("button#book-appointment")
            await page.wait_for_load_state("networkidle", timeout=30000)

            # Wait for confirmation page
            await page.wait_for_selector(".confirmation", timeout=10000)

            # Extract reference number
            reference_text = await page.locator(".reference-number").text_content()
            reference: str = reference_text.strip() if reference_text else ""

            logger.info(f"Appointment booked! Reference: {reference}")
            return reference if reference else None

        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return None

    async def take_screenshot(self, page: Page, name: str) -> None:
        """
        Take a screenshot.

        Args:
            page: Playwright page object
            name: Screenshot filename (without extension)
        """
        try:
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)

            filepath = screenshots_dir / f"{name}.png"
            await page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
