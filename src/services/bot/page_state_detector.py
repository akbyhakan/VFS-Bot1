"""Centralized page state detection for VFS browser automation.

Determines the current page state by inspecting DOM elements, page title,
and content — NOT relying solely on URL which can be stale or misleading.

Key design decisions:
- Element-first: DOM inspection, not URL matching
- Visibility-aware: Critical error states check is_visible(), not just count()
- Stable-state support: wait_for_stable_state() polls until page settles
- Confidence scoring: Multiple matching elements increase confidence
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from loguru import logger
from playwright.async_api import Page

from ...utils.anti_detection.cloudflare_handler import CloudflareHandler


class PageState(Enum):
    """All possible page states the bot may encounter."""

    # Normal flow states
    LOGIN_PAGE = auto()
    DASHBOARD = auto()
    APPOINTMENT_PAGE = auto()
    APPOINTMENT_LOADING = auto()
    BOOKING_FORM = auto()
    REVIEW_PAGE = auto()
    PAYMENT_PAGE = auto()
    SUCCESS_PAGE = auto()
    WAITLIST_PAGE = auto()

    # OTP states
    OTP_LOGIN = auto()
    OTP_3D_SECURE = auto()

    # Error/interruption states
    SESSION_EXPIRED = auto()
    CLOUDFLARE_CHALLENGE = auto()
    MAINTENANCE = auto()
    ERROR_PAGE = auto()
    CAPTCHA_REQUIRED = auto()
    RATE_LIMITED = auto()

    # Unknown
    UNKNOWN = auto()


@dataclass
class PageStateResult:
    """Result of a page state detection."""

    state: PageState
    confidence: float
    url: str
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """Page is in a state where bot actions can proceed."""
        return self.state in _ACTIONABLE_STATES

    @property
    def needs_recovery(self) -> bool:
        """Page needs intervention before bot can continue."""
        return self.state in _RECOVERY_STATES

    @property
    def is_on_appointment_page(self) -> bool:
        return self.state == PageState.APPOINTMENT_PAGE

    @property
    def is_waiting_for_otp(self) -> bool:
        return self.state in (PageState.OTP_LOGIN, PageState.OTP_3D_SECURE)

    @property
    def is_loading(self) -> bool:
        return self.state == PageState.APPOINTMENT_LOADING


# ── State groups ──

_ACTIONABLE_STATES: FrozenSet[PageState] = frozenset(
    {
        PageState.LOGIN_PAGE,
        PageState.DASHBOARD,
        PageState.APPOINTMENT_PAGE,
        PageState.BOOKING_FORM,
        PageState.REVIEW_PAGE,
        PageState.PAYMENT_PAGE,
        PageState.WAITLIST_PAGE,
        PageState.OTP_LOGIN,
        PageState.OTP_3D_SECURE,
    }
)

_RECOVERY_STATES: FrozenSet[PageState] = frozenset(
    {
        PageState.SESSION_EXPIRED,
        PageState.CLOUDFLARE_CHALLENGE,
        PageState.MAINTENANCE,
        PageState.ERROR_PAGE,
        PageState.CAPTCHA_REQUIRED,
        PageState.RATE_LIMITED,
    }
)

_PRIORITY_STATES: FrozenSet[PageState] = frozenset(
    {
        PageState.SESSION_EXPIRED,
        PageState.MAINTENANCE,
        PageState.RATE_LIMITED,
        PageState.CLOUDFLARE_CHALLENGE,
        PageState.CAPTCHA_REQUIRED,
        PageState.OTP_LOGIN,
        PageState.OTP_3D_SECURE,
    }
)


# ──────────────────────────────────────────────────────────────────────
# Detection rules: (selector, PageState, confidence, requires_visible)
#
# requires_visible=True → element must be VISIBLE (not just in DOM)
# This prevents false positives from hidden modals/overlays.
# ──────────────────────────────────────────────────────────────────────

_DETECTION_RULES: List[Tuple[str, PageState, float, bool]] = [
    # ━━━ ERROR / INTERRUPTION STATES ━━━
    # These MUST check visibility — VFS keeps error modals hidden in DOM
    (
        "text=/session.*expired|oturum.*sona.*erdi|session.*timeout/i",
        PageState.SESSION_EXPIRED,
        0.95,
        True,
    ),
    ('.session-expired-modal, .modal:has-text("session")', PageState.SESSION_EXPIRED, 0.90, True),
    ("text=/maintenance|bakım|temporarily unavailable/i", PageState.MAINTENANCE, 0.90, True),
    ("text=/too many requests|çok fazla istek|rate limit/i", PageState.RATE_LIMITED, 0.90, True),
    # Captcha — visible challenge frame (not hidden widget)
    (
        ".cf-turnstile:visible, [data-sitekey]:visible, .g-recaptcha:visible",
        PageState.CAPTCHA_REQUIRED,
        0.85,
        True,
    ),
    # ━━━ OTP STATES ━━━
    # OTP input must be visible — VFS might have hidden OTP forms in DOM
    ('input[name="otp"]', PageState.OTP_LOGIN, 0.85, True),
    # ━━━ LOADING / OVERLAY STATES ━━━
    # Spinners/overlays — must be visible to count
    (
        ".cdk-overlay-container .mat-spinner, .loading-overlay, .spinner",
        PageState.APPOINTMENT_LOADING,
        0.80,
        True,
    ),
    # ━━━ NORMAL FLOW STATES ━━━
    # These use count() (existence check) — always present when on right page
    ('input[name="email"], input[type="email"]', PageState.LOGIN_PAGE, 0.40, False),
    ('input[name="password"], input[type="password"]', PageState.LOGIN_PAGE, 0.40, False),
    ("text=/dashboard|hoş geldiniz|welcome/i", PageState.DASHBOARD, 0.60, True),
    ('mat-sidenav, .dashboard-container, a[href*="appointment"]', PageState.DASHBOARD, 0.40, False),
    (
        'select#centres, select[name*="centre"], select[name*="center"]',
        PageState.APPOINTMENT_PAGE,
        0.80,
        False,
    ),
    ('input[name="first_name"], input[name="firstName"]', PageState.BOOKING_FORM, 0.70, False),
    ('input[name="last_name"], input[name="lastName"]', PageState.BOOKING_FORM, 0.20, False),
    (
        'input[value="consent.checkbox_value.vas_term_condition"]',
        PageState.REVIEW_PAGE,
        0.80,
        False,
    ),
    ('button:has-text("Onayla"), button:has-text("Confirm")', PageState.REVIEW_PAGE, 0.20, True),
    (
        'input[name*="card"], input[name*="kart"], input[name*="cardNumber"]',
        PageState.PAYMENT_PAGE,
        0.70,
        False,
    ),
    ('input[name*="cvv"], input[name*="cvc"]', PageState.PAYMENT_PAGE, 0.20, False),
    ("text=/Bekleme Listesi|Waitlist/i", PageState.WAITLIST_PAGE, 0.60, True),
    (
        'mat-checkbox:has-text("Waitlist"), mat-checkbox:has-text("Bekleme Listesi")',
        PageState.WAITLIST_PAGE,
        0.30,
        False,
    ),
    ("text=/başarılı|successful|confirmed|onaylandı/i", PageState.SUCCESS_PAGE, 0.65, True),
    ("text=/İşlem Özeti|Referans Numarası|Reference Number/i", PageState.SUCCESS_PAGE, 0.30, True),
]


class PageStateDetector:
    """
    Detect current page state using DOM element inspection.

    Single source of truth for "which screen are we on?"
    """

    def __init__(
        self,
        config: Dict[str, Any],
        cloudflare_handler: Optional[CloudflareHandler] = None,
    ):
        self.config = config
        self.cloudflare_handler = cloudflare_handler
        self._last_state: Optional[PageStateResult] = None

    @property
    def last_state(self) -> Optional[PageStateResult]:
        """Get the last detected state without re-scanning."""
        return self._last_state

    # ──────────────────────────────────────────────────────────────
    # Core detection
    # ──────────────────────────────────────────────────────────────

    async def detect(self, page: Page, timeout: float = 3000) -> PageStateResult:
        """
        Detect the current page state by inspecting DOM elements.

        Args:
            page: Playwright page object
            timeout: Max time for element checks (ms) — currently unused,
                     reserved for future wait_for_selector integration

        Returns:
            PageStateResult with detected state and confidence
        """
        url = page.url
        scores: Dict[PageState, float] = {}
        details: Dict[str, Any] = {"url": url, "matched_rules": []}

        # Step 1: Cloudflare (dedicated handler, fast path)
        if self.cloudflare_handler:
            challenge = await self.cloudflare_handler.detect_cloudflare_challenge(page)
            if challenge:
                result = PageStateResult(
                    state=PageState.CLOUDFLARE_CHALLENGE,
                    confidence=0.95,
                    url=url,
                    details={"challenge_type": challenge},
                )
                self._last_state = result
                return result

        # Step 2: Run all element checks concurrently
        check_tasks = [
            self._check_element(page, selector, state, confidence, requires_visible)
            for selector, state, confidence, requires_visible in _DETECTION_RULES
        ]

        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        for check_result in results:
            if isinstance(check_result, Exception) or check_result is None:
                continue
            state, confidence, selector = check_result
            current = scores.get(state, 0.0)
            scores[state] = min(current + confidence, 1.0)
            details["matched_rules"].append(
                {
                    "selector": selector,
                    "state": state.name,
                    "confidence": confidence,
                }
            )

        # Step 3: Resolve ambiguities
        if scores:
            scores = await self._resolve_ambiguities(page, scores, details)

        # Step 4: Pick highest confidence state
        if scores:
            best_state = max(
                scores,
                key=lambda s: (scores[s], 1 if s in _PRIORITY_STATES else 0),
            )
            result = PageStateResult(
                state=best_state,
                confidence=scores[best_state],
                url=url,
                details=details,
            )
        else:
            state = await self._fallback_detection(page)
            result = PageStateResult(
                state=state,
                confidence=0.30,
                url=url,
                details={**details, "method": "fallback"},
            )

        self._last_state = result
        logger.debug(
            f"Page state: {result.state.name} " f"(confidence: {result.confidence:.0%}, url: {url})"
        )
        return result

    # ──────────────────────────────────────────────────────────────
    # Stable state waiting — THE FIX for post-navigation UNKNOWN
    # ──────────────────────────────────────────────────────────────

    async def wait_for_stable_state(
        self,
        page: Page,
        *,
        max_wait: float = 15.0,
        poll_interval: float = 1.0,
        min_confidence: float = 0.60,
        consecutive_required: int = 2,
        expected_states: Optional[FrozenSet[PageState]] = None,
    ) -> PageStateResult:
        """
        Poll detect() until the page settles into a stable, confident state.

        Use this AFTER navigation actions (login, page.goto, button clicks)
        where the page needs time to render Angular components.

        Args:
            page: Playwright page object
            max_wait: Maximum total wait time in seconds
            poll_interval: Time between detection attempts in seconds
            min_confidence: Minimum confidence to accept a state
            consecutive_required: How many consecutive identical detections
                                  needed to consider state "stable"
            expected_states: If provided, only accept these states.
                             Useful when you know what should come next
                             (e.g., after login → expect DASHBOARD or APPOINTMENT_PAGE)

        Returns:
            PageStateResult — either stable state or best effort after timeout
        """
        import time

        start = time.monotonic()
        consecutive_count = 0
        last_detected: Optional[PageState] = None
        best_result: Optional[PageStateResult] = None

        while time.monotonic() - start < max_wait:
            result = await self.detect(page)

            # Track best result seen so far
            if best_result is None or result.confidence > best_result.confidence:
                best_result = result

            # Check if this detection meets our criteria
            meets_confidence = result.confidence >= min_confidence
            meets_expected = expected_states is None or result.state in expected_states
            is_not_unknown = result.state != PageState.UNKNOWN

            if meets_confidence and meets_expected and is_not_unknown:
                # Count consecutive identical detections
                if result.state == last_detected:
                    consecutive_count += 1
                else:
                    consecutive_count = 1
                    last_detected = result.state

                if consecutive_count >= consecutive_required:
                    logger.debug(
                        f"Stable state reached: {result.state.name} "
                        f"({consecutive_count}x consecutive, "
                        f"confidence: {result.confidence:.0%}, "
                        f"waited: {time.monotonic() - start:.1f}s)"
                    )
                    return result
            else:
                # Reset consecutive count
                consecutive_count = 0
                last_detected = result.state

            # Early exit for high-priority error states (no need to wait)
            if result.state in _RECOVERY_STATES and result.confidence >= 0.85:
                logger.warning(
                    f"Error state detected during stabilization: {result.state.name} "
                    f"(confidence: {result.confidence:.0%})"
                )
                return result

            await asyncio.sleep(poll_interval)

        # Timeout — return best result we saw
        elapsed = time.monotonic() - start
        final = best_result or PageStateResult(
            state=PageState.UNKNOWN,
            confidence=0.0,
            url=page.url,
            details={"timeout": True},
        )

        logger.warning(
            f"Stable state timeout after {elapsed:.1f}s — "
            f"returning best: {final.state.name} "
            f"(confidence: {final.confidence:.0%})"
        )
        return final

    # ──────────────────────────────────────────────────────────────
    # Element checking — visibility-aware
    # ──────────────────────────────────────────────────────────────

    async def _check_element(
        self,
        page: Page,
        selector: str,
        state: PageState,
        confidence: float,
        requires_visible: bool,
    ) -> Optional[Tuple[PageState, float, str]]:
        """
        Check if a selector exists on the page.

        Args:
            requires_visible: If True, element must be visible (not just in DOM).
                              Critical for error modals that live hidden in the DOM.
        """
        try:
            locator = page.locator(selector)

            if requires_visible:
                # is_visible() checks CSS visibility, display, opacity
                # Returns False for display:none, visibility:hidden, opacity:0
                # This is THE fix for hidden modal false positives
                first = locator.first
                if await first.is_visible():
                    return (state, confidence, selector)
            else:
                # count() checks DOM existence only — fine for form inputs
                # that are always visible when the page is correct
                if await locator.count() > 0:
                    return (state, confidence, selector)
        except Exception:
            # Element not found, timeout, or page navigated away
            pass
        return None

    # ──────────────────────────────────────────────────────────────
    # Ambiguity resolution
    # ──────────────────────────────────────────────────────────────

    async def _resolve_ambiguities(
        self,
        page: Page,
        scores: Dict[PageState, float],
        details: Dict[str, Any],
    ) -> Dict[PageState, float]:
        """Resolve cases where multiple states have high scores."""
        resolved = dict(scores)

        # ── OTP: login vs 3D Secure ──
        if PageState.OTP_LOGIN in resolved:
            is_payment_context = False
            try:
                vfs_base = self.config.get("vfs", {}).get("base_url", "vfsglobal.com")
                if vfs_base not in page.url:
                    is_payment_context = True

                payment_nearby = await page.locator(
                    'input[name*="card"], .payment-form, text=/3D Secure/i'
                ).count()
                if payment_nearby > 0:
                    is_payment_context = True
            except Exception:
                pass

            if is_payment_context:
                otp_score = resolved.pop(PageState.OTP_LOGIN, 0.0)
                resolved[PageState.OTP_3D_SECURE] = min(
                    resolved.get(PageState.OTP_3D_SECURE, 0.0) + otp_score, 1.0
                )
                details["otp_resolution"] = "3d_secure"
            else:
                details["otp_resolution"] = "login_otp"

        # ── APPOINTMENT vs APPOINTMENT_LOADING ──
        if PageState.APPOINTMENT_PAGE in resolved and PageState.APPOINTMENT_LOADING in resolved:
            resolved[PageState.APPOINTMENT_LOADING] = max(
                resolved[PageState.APPOINTMENT_LOADING],
                resolved[PageState.APPOINTMENT_PAGE],
            )
            del resolved[PageState.APPOINTMENT_PAGE]
            details["loading_resolution"] = "spinner visible, not ready"

        # ── LOGIN_PAGE confidence gate ──
        if PageState.LOGIN_PAGE in resolved and resolved[PageState.LOGIN_PAGE] < 0.70:
            details["login_note"] = "partial match — only one of email/password"

        # ── Error states always win ──
        priority_found = [s for s in resolved if s in _PRIORITY_STATES and resolved[s] >= 0.80]
        if priority_found:
            for ps in priority_found:
                resolved[ps] = min(resolved[ps] + 0.10, 1.0)

        return resolved

    # ──────────────────────────────────────────────────────────────
    # Fallback detection (title-based)
    # ──────────────────────────────────────────────────────────────

    async def _fallback_detection(self, page: Page) -> PageState:
        """Last resort: check page title."""
        try:
            title = (await page.title()).lower()
            if "login" in title or "giriş" in title:
                return PageState.LOGIN_PAGE
            if "appointment" in title or "randevu" in title:
                return PageState.APPOINTMENT_PAGE
            if "dashboard" in title:
                return PageState.DASHBOARD
            if "payment" in title or "ödeme" in title:
                return PageState.PAYMENT_PAGE
            if "error" in title or "hata" in title:
                return PageState.ERROR_PAGE
            if "403" in title or "503" in title:
                return PageState.ERROR_PAGE
        except Exception:
            pass
        return PageState.UNKNOWN

    # ──────────────────────────────────────────────────────────────
    # Convenience methods
    # ──────────────────────────────────────────────────────────────

    async def is_on_appointment_page(self, page: Page) -> bool:
        result = await self.detect(page)
        return result.is_on_appointment_page and result.confidence >= 0.70

    async def needs_login(self, page: Page) -> bool:
        result = await self.detect(page)
        return result.state in (PageState.LOGIN_PAGE, PageState.SESSION_EXPIRED)

    async def is_blocked(self, page: Page) -> bool:
        result = await self.detect(page)
        return result.state in (
            PageState.CLOUDFLARE_CHALLENGE,
            PageState.RATE_LIMITED,
            PageState.MAINTENANCE,
        )

    async def is_waiting_for_otp(self, page: Page) -> bool:
        result = await self.detect(page)
        return result.is_waiting_for_otp

    async def get_otp_type(self, page: Page) -> Optional[PageState]:
        result = await self.detect(page)
        if result.state in (PageState.OTP_LOGIN, PageState.OTP_3D_SECURE):
            return result.state
        return None
