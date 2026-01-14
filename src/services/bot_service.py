import asyncio
import logging
from datetime import datetime
from typing import Optional

from playwright.async_api import Page, Browser, Playwright, async_playwright

from src.config import settings
from src.services.vfs_service import VFSService
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BotService:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.vfs_service: Optional[VFSService] = None
        self.notification_service = NotificationService()
        self.is_running = False
        self.check_count = 0
        self.last_check_time: Optional[datetime] = None

    async def initialize(self):
        """Initialize the browser and services."""
        logger.info("Initializing bot service...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.HEADLESS_MODE,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self.page = await self.browser.new_page()
        self.vfs_service = VFSService(self.page)
        logger.info("Bot service initialized successfully")

    async def cleanup(self):
        """Clean up browser resources."""
        logger.info("Cleaning up bot service...")
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Bot service cleaned up")

    async def run(self):
        """Main bot loop."""
        self.is_running = True
        logger.info("Starting bot main loop...")

        try:
            await self.initialize()
            await self.vfs_service.login(settings.VFS_EMAIL, settings.VFS_PASSWORD)

            while self.is_running:
                try:
                    await self.check_appointments()
                    self.check_count += 1
                    self.last_check_time = datetime.now()
                    logger.info(
                        f"Check #{self.check_count} completed at {self.last_check_time}"
                    )
                    await asyncio.sleep(settings.SELECTOR_HEALTH_CHECK_INTERVAL)
                except Exception as e:
                    logger.error(f"Error during appointment check: {e}")
                    await self.notification_service.send_error_notification(str(e))
                    await asyncio.sleep(60)

        finally:
            await self.cleanup()

    async def check_appointments(self):
        """Check for available appointments."""
        logger.info("Checking for available appointments...")

        # Navigate to appointment page and check availability
        available_slots = await self.vfs_service.get_available_slots()

        if available_slots:
            logger.info(f"Found {len(available_slots)} available slots!")
            await self.notification_service.send_availability_notification(
                available_slots
            )

            if settings.AUTO_BOOK:
                await self.vfs_service.book_appointment(available_slots[0])
                await self.notification_service.send_booking_confirmation(
                    available_slots[0]
                )
        else:
            logger.info("No available appointments found")

    async def stop(self):
        """Stop the bot."""
        logger.info("Stopping bot...")
        self.is_running = False
