"""Page state detection and handling system for VFS bot.

This module provides intelligent page/screen detection with automatic recovery,
enabling the bot to handle unexpected states like CAPTCHA, session expiry,
maintenance pages, etc.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger
from playwright.async_api import Page

from src.core.exceptions import VFSBotError


class PageState(Enum):
    """Known VFS page/screen states."""

    # Normal flow states
    LOGIN_PAGE = "login_page"
    DASHBOARD = "dashboard"
    APPLICATION_DETAILS = "application_details"
    APPOINTMENT_SELECTION = "appointment_selection"
    APPLICANT_FORM = "applicant_form"
    SERVICES_PAGE = "services_page"
    REVIEW_AND_PAY = "review_and_pay"
    PAYMENT_PAGE = "payment_page"
    BOOKING_CONFIRMATION = "booking_confirmation"

    # Waitlist states
    WAITLIST_MODE = "waitlist_mode"
    WAITLIST_SUCCESS = "waitlist_success"

    # Authentication/verification states
    CAPTCHA_PAGE = "captcha_page"
    OTP_VERIFICATION = "otp_verification"

    # Challenge/protection states
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    SESSION_EXPIRED = "session_expired"
    MAINTENANCE_PAGE = "maintenance_page"
    RATE_LIMITED = "rate_limited"

    # Information states
    NO_APPOINTMENTS = "no_appointments"
    ERROR_PAGE = "error_page"

    # UI states
    POPUP_MODAL = "popup_modal"

    # Unknown/fallback
    UNKNOWN = "unknown"


@dataclass
class StateHandlerResult:
    """Result of handling a page state."""

    success: bool
    state: PageState
    next_state: Optional[PageState] = None
    action_taken: str = ""
    should_retry: bool = False
    should_abort: bool = False
    metadata: Optional[Dict[str, Any]] = None


class PageStateDetector:
    """Detects page states and handles recovery strategies."""

    def __init__(
        self,
        states_config_path: str = "config/page_states.yaml",
        forensic_logger: Optional[Any] = None,
        notifier: Optional[Any] = None,
        auth_service: Optional[Any] = None,
        cloudflare_handler: Optional[Any] = None,
        captcha_solver: Optional[Any] = None,
        waitlist_handler: Optional[Any] = None,
        ai_analyzer: Optional[Any] = None,
        learned_store: Optional[Any] = None,
    ):
        """
        Initialize page state detector.

        Args:
            states_config_path: Path to page states configuration file
            forensic_logger: Optional ForensicLogger for incident capture
            notifier: Optional NotificationService for alerts
            auth_service: Optional AuthService for re-login
            cloudflare_handler: Optional CloudflareHandler for challenges
            captcha_solver: Optional CAPTCHA solver
            waitlist_handler: Optional WaitlistHandler
            ai_analyzer: Optional AIPageAnalyzer for unknown page analysis
            learned_store: Optional LearnedStateStore for persistent learning
        """
        self.states_config_path = states_config_path
        self.forensic_logger = forensic_logger
        self.notifier = notifier
        self.auth_service = auth_service
        self.cloudflare_handler = cloudflare_handler
        self.captcha_solver = captcha_solver
        self.waitlist_handler = waitlist_handler
        self.ai_analyzer = ai_analyzer
        self.learned_store = learned_store

        # Load page state indicators from config
        self.indicators = self._load_indicators()

        # State transition history for debugging
        self.transition_history: List[Dict[str, Any]] = []

    def _load_indicators(self) -> Dict[str, Any]:
        """
        Load page state indicators from config file.

        Returns:
            Dictionary of page state indicators
        """
        config_file = Path(self.states_config_path)
        if not config_file.exists():
            logger.warning(
                f"Page states config not found at {self.states_config_path}, using defaults"
            )
            return self._get_default_indicators()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info(f"✅ Loaded page states config from {self.states_config_path}")
                return config.get("states", {})
        except Exception as e:
            logger.error(f"Failed to load page states config: {e}")
            return self._get_default_indicators()

    def _get_default_indicators(self) -> Dict[str, Any]:
        """
        Get default page state indicators (fallback if config missing).

        Returns:
            Default indicators dictionary
        """
        return {
            "login_page": {
                "url_patterns": ["/login", "/signin"],
                "text_indicators": ["Email", "Password", "Giriş Yap", "Login"],
                "css_selectors": ["input[type='email']", "input[type='password']"],
            },
            "dashboard": {
                "url_patterns": ["/dashboard", "/appointment"],
                "text_indicators": ["Dashboard", "Randevu"],
                "css_selectors": ["#appointmentSection"],
            },
            "captcha_page": {
                "css_selectors": [".g-recaptcha", "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']"],
            },
            "cloudflare_challenge": {
                "title_patterns": ["just a moment", "waiting room"],
                "css_selectors": [
                    "iframe[src*='challenges.cloudflare.com']",
                    "iframe[src*='cloudflare.com/cdn-cgi/challenge-platform']",
                ],
            },
            "session_expired": {
                "text_indicators": ["session expired", "oturum süresi doldu", "please login again"],
                "url_patterns": ["/login"],
            },
            "maintenance_page": {
                "text_indicators": ["under maintenance", "bakım", "maintenance mode"],
                "title_patterns": ["maintenance"],
            },
            "waitlist_mode": {
                "text_indicators": ["Bekleme Listesi", "Waitlist", "bekleme listesi", "waitlist"],
            },
            "waitlist_success": {
                "text_indicators": ["Bekleme Listesinde", "İşlem Özeti", "Waitlist"],
            },
            "otp_verification": {
                "css_selectors": ["input[name='otp']"],
                "text_indicators": ["OTP", "Verification Code", "Doğrulama Kodu"],
            },
        }

    async def detect(self, page: Page) -> PageState:
        """
        Detect current page state.

        Detection priority:
        1. URL patterns
        2. Popup/modal overlays
        3. Text indicators
        4. CSS selectors
        5. Title patterns

        Args:
            page: Playwright page object

        Returns:
            Detected PageState
        """
        try:
            # Get page information
            url = page.url.lower()
            title = (await page.title()).lower()
            
            # Check each state in priority order
            # Higher priority states first (challenges, errors)
            
            # 1. Cloudflare challenge (highest priority)
            if await self._check_state(page, "cloudflare_challenge", url, title):
                logger.info("🔍 Page state detected: CLOUDFLARE_CHALLENGE")
                return PageState.CLOUDFLARE_CHALLENGE
            
            # 2. Maintenance page
            if await self._check_state(page, "maintenance_page", url, title):
                logger.info("🔍 Page state detected: MAINTENANCE_PAGE")
                return PageState.MAINTENANCE_PAGE
            
            # 3. Session expired
            if await self._check_state(page, "session_expired", url, title):
                logger.info("🔍 Page state detected: SESSION_EXPIRED")
                return PageState.SESSION_EXPIRED
            
            # 4. CAPTCHA
            if await self._check_state(page, "captcha_page", url, title):
                logger.info("🔍 Page state detected: CAPTCHA_PAGE")
                return PageState.CAPTCHA_PAGE
            
            # 5. OTP verification
            if await self._check_state(page, "otp_verification", url, title):
                logger.info("🔍 Page state detected: OTP_VERIFICATION")
                return PageState.OTP_VERIFICATION
            
            # 6. Waitlist states
            if await self._check_state(page, "waitlist_success", url, title):
                logger.info("🔍 Page state detected: WAITLIST_SUCCESS")
                return PageState.WAITLIST_SUCCESS
            
            if await self._check_state(page, "waitlist_mode", url, title):
                logger.info("🔍 Page state detected: WAITLIST_MODE")
                return PageState.WAITLIST_MODE
            
            # 7. Normal flow states
            if await self._check_state(page, "dashboard", url, title):
                logger.info("🔍 Page state detected: DASHBOARD")
                return PageState.DASHBOARD
            
            if await self._check_state(page, "login_page", url, title):
                logger.info("🔍 Page state detected: LOGIN_PAGE")
                return PageState.LOGIN_PAGE
            
            # Default: Unknown state
            logger.warning(f"🔍 Page state UNKNOWN - URL: {url[:100]}")
            return PageState.UNKNOWN

        except Exception as e:
            logger.error(f"Error detecting page state: {e}")
            return PageState.UNKNOWN

    async def _check_state(
        self, page: Page, state_key: str, url: str, title: str
    ) -> bool:
        """
        Check if page matches a specific state.

        Args:
            page: Playwright page object
            state_key: State key in indicators config
            url: Current page URL (lowercase)
            title: Current page title (lowercase)

        Returns:
            True if state matches
        """
        if state_key not in self.indicators:
            return False

        indicators = self.indicators[state_key]

        # Check URL patterns
        url_patterns = indicators.get("url_patterns", [])
        for pattern in url_patterns:
            if pattern.lower() in url:
                return True

        # Check title patterns
        title_patterns = indicators.get("title_patterns", [])
        for pattern in title_patterns:
            if pattern.lower() in title:
                return True

        # Check text indicators
        text_indicators = indicators.get("text_indicators", [])
        for text in text_indicators:
            try:
                count = await page.locator(f"text={text}").count()
                if count > 0:
                    return True
            except Exception:
                pass

        # Check CSS selectors
        css_selectors = indicators.get("css_selectors", [])
        for selector in css_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    return True
            except Exception:
                pass

        return False

    async def assert_state(
        self, page: Page, expected: PageState, timeout: int = 5000
    ) -> bool:
        """
        Assert that page is in expected state.

        Args:
            page: Playwright page object
            expected: Expected PageState
            timeout: Timeout in milliseconds

        Returns:
            True if in expected state, False otherwise
        """
        start_time = asyncio.get_event_loop().time()
        deadline = start_time + (timeout / 1000)

        while asyncio.get_event_loop().time() < deadline:
            actual = await self.detect(page)
            
            if actual == expected:
                logger.info(f"✅ State assertion passed: {expected.value}")
                return True
            
            await asyncio.sleep(0.5)

        actual = await self.detect(page)
        if actual != expected:
            logger.warning(
                f"❌ State assertion failed - Expected: {expected.value}, Actual: {actual.value}"
            )
            return False

        return True

    async def handle_state(
        self, page: Page, state: PageState, context: Optional[Dict[str, Any]] = None
    ) -> StateHandlerResult:
        """
        Handle detected page state with appropriate action.

        Args:
            page: Playwright page object
            state: Detected PageState
            context: Optional context dictionary (user info, etc.)

        Returns:
            StateHandlerResult with action outcome
        """
        context = context or {}
        
        # Log state transition
        self._log_transition(state, context)

        # Route to appropriate handler
        if state == PageState.SESSION_EXPIRED:
            return await self._handle_session_expired(page, context)
        
        elif state == PageState.CLOUDFLARE_CHALLENGE:
            return await self._handle_cloudflare_challenge(page, context)
        
        elif state == PageState.CAPTCHA_PAGE:
            return await self._handle_captcha(page, context)
        
        elif state == PageState.MAINTENANCE_PAGE:
            return await self._handle_maintenance_page(page, context)
        
        elif state == PageState.RATE_LIMITED:
            return await self._handle_rate_limited(page, context)
        
        elif state == PageState.UNKNOWN:
            return await self._handle_unknown_state(page, context)
        
        else:
            # For normal states, just return success
            return StateHandlerResult(
                success=True,
                state=state,
                action_taken=f"State {state.value} recognized (no action needed)",
            )

    def _log_transition(self, state: PageState, context: Dict[str, Any]) -> None:
        """
        Log state transition for debugging.

        Args:
            state: Current PageState
            context: Context dictionary
        """
        transition = {
            "timestamp": asyncio.get_event_loop().time(),
            "state": state.value,
            "context": context,
        }
        self.transition_history.append(transition)
        logger.info(f"📍 State transition: {state.value}")

    async def _handle_session_expired(
        self, page: Page, context: Dict[str, Any]
    ) -> StateHandlerResult:
        """Handle session expired state - trigger re-login."""
        logger.warning("⚠️ Session expired detected - triggering re-login")

        if not self.auth_service:
            logger.error("AuthService not available for re-login")
            return StateHandlerResult(
                success=False,
                state=PageState.SESSION_EXPIRED,
                action_taken="Session expired but no AuthService available",
                should_abort=True,
            )

        try:
            # Get user credentials from context
            email = context.get("email")
            password = context.get("password")

            if not email or not password:
                logger.error("Missing credentials for re-login")
                return StateHandlerResult(
                    success=False,
                    state=PageState.SESSION_EXPIRED,
                    action_taken="Missing credentials for re-login",
                    should_abort=True,
                )

            # Attempt re-login
            success = await self.auth_service.login(page, email, password)

            if success:
                logger.info("✅ Re-login successful")
                return StateHandlerResult(
                    success=True,
                    state=PageState.SESSION_EXPIRED,
                    next_state=PageState.DASHBOARD,
                    action_taken="Re-login successful",
                    should_retry=True,
                )
            else:
                logger.error("❌ Re-login failed")
                return StateHandlerResult(
                    success=False,
                    state=PageState.SESSION_EXPIRED,
                    action_taken="Re-login failed",
                    should_abort=True,
                )

        except Exception as e:
            logger.error(f"Error during re-login: {e}")
            return StateHandlerResult(
                success=False,
                state=PageState.SESSION_EXPIRED,
                action_taken=f"Re-login error: {str(e)}",
                should_abort=True,
            )

    async def _handle_cloudflare_challenge(
        self, page: Page, context: Dict[str, Any]
    ) -> StateHandlerResult:
        """Handle Cloudflare challenge."""
        logger.warning("⚠️ Cloudflare challenge detected")

        if not self.cloudflare_handler:
            logger.error("CloudflareHandler not available")
            return StateHandlerResult(
                success=False,
                state=PageState.CLOUDFLARE_CHALLENGE,
                action_taken="Cloudflare challenge but no handler available",
                should_abort=True,
            )

        try:
            # Detect challenge type
            challenge_type = await self.cloudflare_handler.detect_cloudflare_challenge(page)
            
            if not challenge_type:
                logger.info("No Cloudflare challenge detected")
                return StateHandlerResult(
                    success=True,
                    state=PageState.CLOUDFLARE_CHALLENGE,
                    action_taken="False positive - no actual challenge",
                    should_retry=True,
                )

            # Handle the challenge
            success = await self.cloudflare_handler.handle_challenge(page)

            if success:
                logger.info("✅ Cloudflare challenge bypassed")
                return StateHandlerResult(
                    success=True,
                    state=PageState.CLOUDFLARE_CHALLENGE,
                    action_taken=f"Bypassed {challenge_type} challenge",
                    should_retry=True,
                )
            else:
                logger.error("❌ Failed to bypass Cloudflare challenge")
                return StateHandlerResult(
                    success=False,
                    state=PageState.CLOUDFLARE_CHALLENGE,
                    action_taken=f"Failed to bypass {challenge_type}",
                    should_abort=True,
                )

        except Exception as e:
            logger.error(f"Error handling Cloudflare challenge: {e}")
            return StateHandlerResult(
                success=False,
                state=PageState.CLOUDFLARE_CHALLENGE,
                action_taken=f"Challenge handling error: {str(e)}",
                should_abort=True,
            )

    async def _handle_captcha(
        self, page: Page, context: Dict[str, Any]
    ) -> StateHandlerResult:
        """Handle CAPTCHA page."""
        logger.warning("⚠️ CAPTCHA detected")

        # Send notification
        if self.notifier:
            try:
                await self.notifier.send_alert(
                    "🔐 CAPTCHA detected - manual intervention may be required"
                )
            except Exception:
                pass

        # If captcha_solver available, try to solve
        if self.captcha_solver:
            try:
                success = await self.captcha_solver.solve(page)
                if success:
                    logger.info("✅ CAPTCHA solved")
                    return StateHandlerResult(
                        success=True,
                        state=PageState.CAPTCHA_PAGE,
                        action_taken="CAPTCHA solved automatically",
                        should_retry=True,
                    )
            except Exception as e:
                logger.error(f"CAPTCHA solver error: {e}")

        # Cannot solve automatically
        logger.warning("⚠️ CAPTCHA requires manual intervention")
        return StateHandlerResult(
            success=False,
            state=PageState.CAPTCHA_PAGE,
            action_taken="CAPTCHA detected - manual intervention required",
            should_abort=True,
        )

    async def _handle_maintenance_page(
        self, page: Page, context: Dict[str, Any]
    ) -> StateHandlerResult:
        """Handle maintenance page - wait and retry."""
        logger.warning("⚠️ Maintenance page detected")

        # Send notification
        if self.notifier:
            try:
                await self.notifier.send_alert("🔧 VFS site under maintenance - will retry")
            except Exception:
                pass

        # Wait for configurable period (default 5 minutes)
        wait_time = context.get("maintenance_wait_time", 300)
        logger.info(f"⏱️ Waiting {wait_time}s before retry...")
        await asyncio.sleep(wait_time)

        return StateHandlerResult(
            success=True,
            state=PageState.MAINTENANCE_PAGE,
            action_taken=f"Waited {wait_time}s for maintenance to complete",
            should_retry=True,
        )

    async def _handle_rate_limited(
        self, page: Page, context: Dict[str, Any]
    ) -> StateHandlerResult:
        """Handle rate limiting - exponential backoff."""
        logger.warning("⚠️ Rate limited")

        # Get retry count from context
        retry_count = context.get("rate_limit_retry_count", 0)
        
        # Exponential backoff: 2^retry_count seconds (max 300s)
        wait_time = min(2 ** retry_count, 300)
        
        logger.info(f"⏱️ Rate limited - waiting {wait_time}s (retry {retry_count})...")
        await asyncio.sleep(wait_time)

        return StateHandlerResult(
            success=True,
            state=PageState.RATE_LIMITED,
            action_taken=f"Waited {wait_time}s for rate limit cooldown",
            should_retry=True,
            metadata={"retry_count": retry_count + 1},
        )

    async def _apply_action(
        self, page: Page, action_type: str, target_selector: str = "", fill_value: str = ""
    ) -> bool:
        """
        Execute an action on the page.

        Args:
            page: Playwright page object
            action_type: Type of action (CLICK, WAIT, FILL, DISMISS, NAVIGATE_BACK, REFRESH)
            target_selector: CSS selector for target element (if applicable)
            fill_value: Value to fill (if action is FILL)

        Returns:
            True if action was successful, False otherwise
        """
        try:
            action_type = action_type.lower()

            if action_type == "click":
                if not target_selector:
                    logger.error("CLICK action requires target_selector")
                    return False
                logger.info(f"🖱️ Clicking element: {target_selector}")
                await page.locator(target_selector).click(timeout=10000)
                await page.wait_for_load_state("networkidle", timeout=5000)
                return True

            elif action_type == "wait":
                logger.info("⏱️ Waiting for page to change...")
                await asyncio.sleep(3)
                return True

            elif action_type == "fill":
                if not target_selector:
                    logger.error("FILL action requires target_selector")
                    return False
                logger.info(f"✍️ Filling element: {target_selector}")
                await page.locator(target_selector).fill(fill_value, timeout=10000)
                return True

            elif action_type == "dismiss":
                if target_selector:
                    logger.info(f"❌ Dismissing element: {target_selector}")
                    await page.locator(target_selector).click(timeout=10000)
                else:
                    # Try to find and close common modal close buttons
                    close_selectors = [
                        'button[aria-label*="close" i]',
                        'button[class*="close" i]',
                        '.modal-close',
                        '[data-dismiss="modal"]',
                    ]
                    for selector in close_selectors:
                        if await page.locator(selector).count() > 0:
                            logger.info(f"❌ Dismissing modal with: {selector}")
                            await page.locator(selector).first.click(timeout=5000)
                            return True
                    logger.warning("No dismiss target found")
                    return False
                return True

            elif action_type == "navigate_back":
                logger.info("⬅️ Navigating back...")
                await page.go_back(wait_until="networkidle", timeout=10000)
                return True

            elif action_type == "refresh":
                logger.info("🔄 Refreshing page...")
                await page.reload(wait_until="networkidle", timeout=10000)
                return True

            else:
                logger.error(f"Unknown action type: {action_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to execute action {action_type}: {e}")
            return False

    async def _handle_unknown_state(
        self, page: Page, context: Dict[str, Any]
    ) -> StateHandlerResult:
        """Handle unknown state with AI-powered learning."""
        logger.error("❌ Unknown page state detected")
        
        url = page.url
        
        # Step 1: Check learned states first
        if self.learned_store:
            try:
                html_content = await page.content()
                learned = self.learned_store.get_learned_action(url, html_content)
                if learned:
                    # We've seen this before! Apply saved action directly
                    logger.info(
                        f"🧠 Applying learned action for state '{learned.state_name}': "
                        f"{learned.action_type}"
                    )
                    success = await self._apply_action(
                        page,
                        learned.action_type,
                        learned.target_selector,
                        learned.fill_value,
                    )
                    if success:
                        return StateHandlerResult(
                            success=True,
                            state=PageState.UNKNOWN,
                            action_taken=f"Applied learned action: {learned.action_type}",
                            should_retry=True,
                        )
                    else:
                        logger.warning(
                            f"⚠️ Learned action failed for state '{learned.state_name}'"
                        )
            except Exception as e:
                logger.error(f"Failed to apply learned action: {e}")

        # Step 2: Ask AI to analyze the page
        if self.ai_analyzer:
            try:
                # Capture screenshot for forensic evidence
                screenshot_path = None
                if self.forensic_logger:
                    try:
                        await self.forensic_logger.capture_incident(
                            page,
                            VFSBotError("Unknown page state - requesting AI analysis"),
                            context={
                                "reason": "unknown_page_state_ai_analysis",
                                "url": url,
                                **context,
                            },
                        )
                        # Note: Screenshot path would be available from forensic logger
                        # but we'll proceed without it for now
                    except Exception as e:
                        logger.warning(f"Failed to capture forensic evidence: {e}")

                html_content = await page.content()
                analysis = await self.ai_analyzer.analyze_page(
                    html_content, url, screenshot_path
                )

                if analysis and analysis.suggested_action.value != "abort":
                    # Step 3: Apply AI's suggestion
                    logger.info(
                        f"🤖 AI suggests: {analysis.suggested_action.value} "
                        f"for '{analysis.page_purpose}'"
                    )
                    success = await self._apply_action(
                        page,
                        analysis.suggested_action.value,
                        analysis.target_selector,
                        analysis.fill_value,
                    )

                    if success:
                        # Wait a bit for page to transition
                        await asyncio.sleep(1)

                        # Step 4: Verify - detect state again
                        new_state = await self.detect(page)
                        
                        if new_state != PageState.UNKNOWN:
                            # Step 5: SUCCESS! Save to learned states
                            if self.learned_store:
                                try:
                                    self.learned_store.save_learned_state(
                                        analysis.suggested_state_name,
                                        analysis.suggested_indicators,
                                        {
                                            "action": analysis.suggested_action.value,
                                            "selector": analysis.target_selector,
                                            "fill_value": analysis.fill_value,
                                        },
                                    )
                                    logger.success(
                                        f"🎓 Learned new state: {analysis.suggested_state_name}"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to save learned state: {e}")

                            return StateHandlerResult(
                                success=True,
                                state=PageState.UNKNOWN,
                                next_state=new_state,
                                action_taken=f"AI solved unknown state: {analysis.page_purpose}",
                                should_retry=True,
                            )
                        else:
                            logger.warning(
                                "⚠️ AI action didn't transition to known state"
                            )
                    else:
                        logger.warning(f"⚠️ AI suggested action failed")
                else:
                    if analysis:
                        logger.info(f"🤖 AI recommends abort: {analysis.reasoning}")
                    else:
                        logger.warning("AI analysis returned no result")

            except Exception as e:
                logger.error(f"AI page analysis failed: {e}")

        # Step 6: Fallback - original abort behavior
        logger.error("❌ Unable to handle unknown state, aborting")

        # Capture forensic evidence (if not already captured)
        if self.forensic_logger and not self.ai_analyzer:
            try:
                await self.forensic_logger.capture_incident(
                    page,
                    VFSBotError("Unknown page state encountered"),
                    context={
                        "reason": "unknown_page_state",
                        "url": url,
                        **context,
                    },
                )
                logger.info("📸 Forensic evidence captured")
            except Exception as e:
                logger.error(f"Failed to capture forensic evidence: {e}")

        # Send notification
        if self.notifier:
            try:
                await self.notifier.send_alert(
                    f"⚠️ Unknown page state encountered - URL: {url[:100]}"
                )
            except Exception:
                pass

        return StateHandlerResult(
            success=False,
            state=PageState.UNKNOWN,
            action_taken="Forensic capture completed, manual review required",
            should_abort=True,
        )

    async def handle_unexpected_state(
        self, page: Page, actual: PageState, expected: PageState
    ) -> StateHandlerResult:
        """
        Handle unexpected state transition.

        Args:
            page: Playwright page object
            actual: Actual detected PageState
            expected: Expected PageState

        Returns:
            StateHandlerResult from handling the unexpected state
        """
        logger.warning(
            f"⚠️ Unexpected state - Expected: {expected.value}, Actual: {actual.value}"
        )

        # Delegate to handle_state for recovery
        return await self.handle_state(page, actual)
