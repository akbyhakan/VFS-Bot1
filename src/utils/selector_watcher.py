"""Selector health monitoring service."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from playwright.async_api import Browser, Page

from src.services.notification import NotificationService
from src.utils.selectors import CountryAwareSelectorManager

logger = logging.getLogger(__name__)


class SelectorHealthCheck:
    """Monitor selector health and detect changes."""

    def __init__(
        self,
        selector_manager: CountryAwareSelectorManager,
        notifier: Optional[NotificationService] = None,
        check_interval: int = 3600,  # 1 hour default
    ):
        self.selector_manager = selector_manager
        self.notifier = notifier
        self.check_interval = check_interval
        self.health_status: Dict[str, Any] = {}
        self.last_check: Optional[datetime] = None

    async def validate_selector(
        self, page: Page, selector_path: str, timeout: int = 5000
    ) -> Dict[str, Any]:
        """
        Validate a single selector.

        Args:
            page: Playwright page object
            selector_path: Selector path (e.g., "login.email_input")
            timeout: Timeout in milliseconds

        Returns:
            Validation result with status and details
        """
        result = {
            "selector_path": selector_path,
            "valid": False,
            "found": False,
            "fallback_used": False,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Get primary selector
            selector = self.selector_manager.get(selector_path)

            if not selector:
                result["error"] = "Selector not found in config"
                return result

            # Try primary selector
            try:
                element = await page.wait_for_selector(selector, timeout=timeout, state="attached")
                if element:
                    result["valid"] = True
                    result["found"] = True
                    logger.debug(f"✓ Selector valid: {selector_path}")
                    return result
            except Exception as e:
                logger.warning(f"Primary selector failed: {selector_path} - {e}")

                # Try fallback selectors
                fallbacks = self.selector_manager.get_fallbacks(selector_path)
                if fallbacks:
                    for i, fallback in enumerate(fallbacks):
                        try:
                            element = await page.wait_for_selector(
                                fallback, timeout=timeout, state="attached"
                            )
                            if element:
                                result["valid"] = True
                                result["found"] = True
                                result["fallback_used"] = True
                                result["fallback_index"] = i
                                logger.info(f"✓ Fallback {i} worked: {selector_path}")

                                # Send alert about primary selector failure
                                await self._send_alert(
                                    f"⚠️ Selector changed: {selector_path}\n"
                                    f"Primary selector failed, fallback #{i} is working.\n"
                                    "Please update config/selectors.yaml"
                                )
                                return result
                        except Exception as e:
                            logger.debug(f"Fallback selector {i} failed for {selector_path}: {e}")
                            continue

                result["error"] = f"All selectors failed: {str(e)}"
                return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Validation error for {selector_path}: {e}")

        return result

    async def check_all_selectors(
        self, browser: Browser, vfs_url: str = "https://visa.vfsglobal.com/tur/en/deu"
    ) -> Dict[str, Any]:
        """
        Check all selectors in config.

        Args:
            browser: Playwright browser instance
            vfs_url: VFS website URL

        Returns:
            Health check results
        """
        logger.info("Starting selector health check...")

        results: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "fallback_used": 0,
            "selectors": {},
        }

        # Define critical selectors to check
        critical_selectors = [
            "login.email_input",
            "login.password_input",
            "login.submit_button",
            "appointment.centre_dropdown",
            "appointment.date_picker",
            "captcha.recaptcha_frame",
        ]

        page = await browser.new_page()

        try:
            await page.goto(vfs_url, wait_until="networkidle")

            for selector_path in critical_selectors:
                result = await self.validate_selector(page, selector_path)
                results["selectors"][selector_path] = result
                total_count: int = results["total"]
                results["total"] = total_count + 1

                if result["valid"]:
                    valid_count: int = results["valid"]
                    results["valid"] = valid_count + 1
                    if result["fallback_used"]:
                        fallback_count: int = results["fallback_used"]
                        results["fallback_used"] = fallback_count + 1
                else:
                    invalid_count: int = results["invalid"]
                    results["invalid"] = invalid_count + 1

            # Update health status
            self.health_status = results
            self.last_check = datetime.now(timezone.utc)

            # Send alert if critical failures
            if results["invalid"] > 0:
                await self._send_critical_alert(results)

            logger.info(f"Health check complete: {results['valid']}/{results['total']} valid")

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            results["error"] = str(e)
        finally:
            await page.close()

        return results

    async def _send_alert(self, message: str) -> None:
        """Send alert notification."""
        if self.notifier:
            try:
                await self.notifier.send_notification("Selector Alert", message)
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

    async def _send_critical_alert(self, results: Dict[str, Any]) -> None:
        """Send critical alert for selector failures."""
        invalid_count = results["invalid"]
        total_count = results["total"]

        message = "🚨 CRITICAL: Selector Health Check Failed\n\n"
        message += f"Invalid selectors: {invalid_count}/{total_count}\n\n"
        message += "Failed selectors:\n"

        for path, result in results["selectors"].items():
            if not result["valid"]:
                message += f"  ❌ {path}: {result.get('error', 'Unknown')}\n"

        message += "\n⚠️ Bot may fail! Update selectors immediately."

        await self._send_alert(message)

    async def run_continuous(self, browser: Browser) -> None:
        """Run health checks continuously."""
        logger.info(f"Starting continuous health monitoring (interval: {self.check_interval}s)")

        while True:
            try:
                await self.check_all_selectors(browser)
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
