"""Detect and bypass Cloudflare protections."""

import logging
import asyncio
from typing import Optional, Tuple
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CloudflareHandler:
    """Handle Cloudflare challenge detection and bypass."""
    
    CHALLENGE_TYPES = {
        'waiting_room': 'Waiting Room',
        'turnstile': 'Turnstile',
        'browser_check': 'Browser Check',
        'blocked': 'Blocked'
    }
    
    def __init__(self, config: dict = None):
        """
        Initialize Cloudflare handler.
        
        Args:
            config: Configuration dictionary with Cloudflare settings
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.max_wait_time = self.config.get('max_wait_time', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.manual_captcha = self.config.get('manual_captcha', False)
    
    async def detect_cloudflare_challenge(self, page: Page) -> Optional[str]:
        """
        Identify Cloudflare challenge type.
        
        Returns:
            Challenge type or None if no challenge detected
        """
        try:
            # Get page title and content
            title = await page.title()
            content = await page.content()
            
            # Check for Waiting Room
            if 'waiting room' in title.lower() or 'waiting room' in content.lower():
                logger.info("Detected Cloudflare Waiting Room")
                return 'waiting_room'
            
            # Check for "Just a moment"
            if 'just a moment' in title.lower():
                logger.info("Detected Cloudflare Browser Check")
                return 'browser_check'
            
            # Check for Turnstile challenge
            turnstile = await page.locator('iframe[src*="challenges.cloudflare.com"]').count()
            if turnstile > 0:
                logger.info("Detected Cloudflare Turnstile challenge")
                return 'turnstile'
            
            # Check for blocked page
            if '403 forbidden' in content.lower() or '503 service unavailable' in content.lower():
                if 'cloudflare' in content.lower():
                    logger.info("Detected Cloudflare block (403/503)")
                    return 'blocked'
            
            # No challenge detected
            return None
            
        except Exception as e:
            logger.error(f"Error detecting Cloudflare challenge: {e}")
            return None
    
    async def handle_waiting_room(self, page: Page) -> bool:
        """
        Wait up to max_wait_time seconds for clearance.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if cleared waiting room
        """
        logger.info(f"Handling Waiting Room (max wait: {self.max_wait_time}s)")
        
        try:
            # Wait for page to change or timeout
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # Check if we've waited too long
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > self.max_wait_time:
                    logger.warning("Waiting Room timeout")
                    return False
                
                # Check if still in waiting room
                title = await page.title()
                if 'waiting room' not in title.lower():
                    logger.info("Cleared Waiting Room")
                    return True
                
                # Wait before checking again
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Error handling Waiting Room: {e}")
            return False
    
    async def handle_turnstile(self, page: Page) -> bool:
        """
        Handle Turnstile challenge (auto-solve or manual).
        
        Args:
            page: Playwright page object
            
        Returns:
            True if challenge passed
        """
        logger.info("Handling Turnstile challenge")
        
        try:
            if self.manual_captcha:
                # Wait for manual solving
                logger.info(f"Waiting for manual Turnstile solve ({self.max_wait_time}s)")
                await asyncio.sleep(self.max_wait_time)
            else:
                # Wait for auto-solve
                logger.info("Waiting for Turnstile auto-solve")
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > self.max_wait_time:
                        logger.warning("Turnstile timeout")
                        return False
                    
                    # Check if turnstile is still present
                    turnstile = await page.locator('iframe[src*="challenges.cloudflare.com"]').count()
                    if turnstile == 0:
                        logger.info("Turnstile challenge passed")
                        return True
                    
                    await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling Turnstile: {e}")
            return False
    
    async def handle_browser_check(self, page: Page) -> bool:
        """
        Wait for auto-redirect from browser check.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if check passed
        """
        logger.info("Handling Browser Check")
        
        try:
            # Wait for page to change
            start_time = asyncio.get_event_loop().time()
            
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > self.max_wait_time:
                    logger.warning("Browser Check timeout")
                    return False
                
                # Check if still on challenge page
                title = await page.title()
                if 'just a moment' not in title.lower():
                    logger.info("Browser Check passed")
                    return True
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error handling Browser Check: {e}")
            return False
    
    async def handle_challenge(self, page: Page) -> bool:
        """
        Main dispatcher for all Cloudflare challenges.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if challenge handled successfully
        """
        if not self.enabled:
            logger.debug("Cloudflare handler disabled")
            return True
        
        try:
            # Detect challenge type
            challenge_type = await self.detect_cloudflare_challenge(page)
            
            if not challenge_type:
                # No challenge detected
                return True
            
            logger.info(f"Handling Cloudflare challenge: {self.CHALLENGE_TYPES.get(challenge_type, 'Unknown')}")
            
            # Handle based on type
            if challenge_type == 'waiting_room':
                return await self.handle_waiting_room(page)
            elif challenge_type == 'turnstile':
                return await self.handle_turnstile(page)
            elif challenge_type == 'browser_check':
                return await self.handle_browser_check(page)
            elif challenge_type == 'blocked':
                logger.error("Page blocked by Cloudflare")
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling Cloudflare challenge: {e}")
            return False
    
    async def retry_with_backoff(self, func, *args, **kwargs):
        """
        Retry function with exponential backoff (1s, 2s, 4s).
        
        Args:
            func: Async function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or None on failure
        """
        for attempt in range(self.max_retries):
            try:
                result = await func(*args, **kwargs)
                if result:
                    return result
                
                # Exponential backoff
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s, 4s
                    logger.info(f"Retry attempt {attempt + 1}/{self.max_retries}, waiting {delay}s")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error in retry attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt
                    await asyncio.sleep(delay)
        
        logger.error(f"All {self.max_retries} retry attempts failed")
        return None
