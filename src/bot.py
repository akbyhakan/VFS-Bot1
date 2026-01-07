"""Main bot logic with Playwright automation for VFS appointment booking."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential

from .captcha_solver import CaptchaSolver
from .notification import NotificationService
from .database import Database
from .centre_fetcher import CentreFetcher

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
        
        # Initialize components
        self.captcha_solver = CaptchaSolver(
            provider=config['captcha']['provider'],
            api_key=config['captcha'].get('api_key', ''),
            manual_timeout=config['captcha'].get('manual_timeout', 120)
        )
        
        self.centre_fetcher = CentreFetcher(
            base_url=config['vfs']['base_url'],
            country=config['vfs']['country'],
            mission=config['vfs']['mission']
        )
        
        logger.info("VFSBot initialized")
    
    async def start(self) -> None:
        """Start the bot."""
        self.running = True
        logger.info("Starting VFS-Bot...")
        await self.notifier.notify_bot_started()
        
        async with async_playwright() as playwright:
            # Launch browser
            self.browser = await playwright.chromium.launch(
                headless=self.config['bot'].get('headless', False),
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # Create context with stealth settings
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Add stealth scripts
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            try:
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
                check_interval = self.config['bot'].get('check_interval', 30)
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
        
        page = await self.context.new_page()
        
        try:
            # Login
            if not await self.login_vfs(page, user['email'], user['password']):
                logger.error(f"Login failed for {user['email']}")
                return
            
            # Check slots
            centres = user['centre'].split(',')
            for centre in centres:
                centre = centre.strip()
                slot = await self.check_slots(page, centre, user['category'], user['subcategory'])
                
                if slot:
                    await self.notifier.notify_slot_found(centre, slot['date'], slot['time'])
                    
                    # Get personal details
                    details = await self.db.get_personal_details(user['id'])
                    if details:
                        # Fill details and book
                        if await self.fill_personal_details(page, details):
                            reference = await self.book_appointment(page, slot['date'], slot['time'])
                            if reference:
                                await self.db.add_appointment(
                                    user['id'], centre, user['category'],
                                    user['subcategory'], slot['date'], slot['time'], reference
                                )
                                await self.notifier.notify_booking_success(
                                    centre, slot['date'], slot['time'], reference
                                )
                    break
        except Exception as e:
            logger.error(f"Error processing user {user['email']}: {e}")
            if self.config['bot'].get('screenshot_on_error', True):
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
            url = f"{self.config['vfs']['base_url']}/{self.config['vfs']['country']}/{self.config['vfs']['mission']}/en/login"
            logger.info(f"Navigating to login page: {url}")
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Fill login form
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            
            # Handle captcha if present
            captcha_present = await page.locator('.g-recaptcha').count() > 0
            if captcha_present:
                site_key = await page.get_attribute('.g-recaptcha', 'data-sitekey')
                token = await self.captcha_solver.solve_recaptcha(page, site_key, page.url)
                if token:
                    await self.captcha_solver.inject_captcha_solution(page, token)
            
            # Submit login
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Check if login successful
            if 'dashboard' in page.url or 'appointment' in page.url:
                logger.info("Login successful")
                return True
            else:
                logger.error("Login failed - not redirected to dashboard")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    async def check_slots(self, page: Page, centre: str, category: str, 
                         subcategory: str) -> Optional[Dict[str, str]]:
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
            # Navigate to appointment page
            appointment_url = f"{self.config['vfs']['base_url']}/{self.config['vfs']['country']}/{self.config['vfs']['mission']}/en/appointment"
            await page.goto(appointment_url, wait_until="networkidle", timeout=30000)
            
            # Select centre, category, subcategory
            await page.select_option('select#centres', label=centre)
            await asyncio.sleep(2)
            
            await page.select_option('select#categories', label=category)
            await asyncio.sleep(2)
            
            await page.select_option('select#subcategories', label=subcategory)
            await asyncio.sleep(2)
            
            # Click to check slots
            await page.click('button#check-slots')
            await asyncio.sleep(3)
            
            # Check if slots are available
            slots_available = await page.locator('.available-slot').count() > 0
            
            if slots_available:
                # Get first available slot
                date = await page.locator('.slot-date').first.text_content()
                time = await page.locator('.slot-time').first.text_content()
                
                logger.info(f"Slot found! Date: {date}, Time: {time}")
                return {'date': date.strip(), 'time': time.strip()}
            else:
                logger.info(f"No slots available for {centre}/{category}/{subcategory}")
                return None
                
        except Exception as e:
            logger.error(f"Error checking slots: {e}")
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
            await page.wait_for_selector('input#first_name', timeout=10000)
            
            # Fill form fields
            await page.fill('input#first_name', details.get('first_name', ''))
            await page.fill('input#last_name', details.get('last_name', ''))
            await page.fill('input#passport_number', details.get('passport_number', ''))
            await page.fill('input#email', details.get('email', ''))
            
            if details.get('mobile_number'):
                await page.fill('input#mobile', details.get('mobile_number', ''))
            
            if details.get('date_of_birth'):
                await page.fill('input#dob', details.get('date_of_birth', ''))
            
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
            # Click continue/book button
            await page.click('button#book-appointment')
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Wait for confirmation page
            await page.wait_for_selector('.confirmation', timeout=10000)
            
            # Extract reference number
            reference = await page.locator('.reference-number').text_content()
            
            logger.info(f"Appointment booked! Reference: {reference}")
            return reference.strip()
            
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
