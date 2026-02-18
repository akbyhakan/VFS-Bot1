"""Browser fingerprint rotation for enhanced anti-detection."""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from loguru import logger


@dataclass
class FingerprintProfile:
    """Complete fingerprint profile with consistent parameters."""

    user_agent: str
    viewport_width: int
    viewport_height: int
    timezone: str
    language: str
    platform: str
    webgl_vendor: str
    webgl_renderer: str
    canvas_noise_r: int
    canvas_noise_g: int
    canvas_noise_b: int
    canvas_noise_a: int
    hardware_concurrency: int = 4
    device_memory: int = 8
    screen_width: int = 1920
    screen_height: int = 1080


class FingerprintRotator:
    """
    Manages browser fingerprint rotation with consistent profiles.

    Features:
    - Predefined realistic profiles
    - Periodic rotation based on page count or time
    - Profile history to prevent repeats
    - Consistent parameter combinations (UA ↔ platform ↔ vendor)
    """

    # Predefined realistic profiles
    PROFILE_POOL: List[Tuple[str, str, str, str, str]] = [
        # (user_agent, platform, timezone, webgl_vendor, webgl_renderer)
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Win32",
            "Europe/Istanbul",
            "Google Inc. (Intel)",
            "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Win32",
            "Europe/Istanbul",
            "Google Inc. (NVIDIA)",
            "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti Direct3D11 vs_5_0 ps_5_0)",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/135.0.0.0",
            "Win32",
            "Europe/Istanbul",
            "Google Inc. (AMD)",
            "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0)",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "MacIntel",
            "Europe/Istanbul",
            "Apple Inc.",
            "Apple M1",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
            "MacIntel",
            "Europe/Istanbul",
            "Apple Inc.",
            "Apple GPU",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
            "Win32",
            "Europe/Istanbul",
            "Intel Inc.",
            "Intel(R) UHD Graphics 630",
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Linux x86_64",
            "Europe/Istanbul",
            "Google Inc. (Intel)",
            "ANGLE (Intel, Mesa Intel(R) UHD Graphics 630 (CML GT2), OpenGL 4.6)",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Win32",
            "Europe/London",
            "Google Inc. (Intel)",
            "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "MacIntel",
            "Europe/Berlin",
            "Apple Inc.",
            "Apple M2",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Win32",
            "Europe/Paris",
            "Google Inc. (NVIDIA)",
            "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
        ),
    ]

    LANGUAGES = ["tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7", "en-US,en;q=0.9", "tr-TR,tr;q=0.9"]

    VIEWPORTS = [
        (1920, 1080),
        (1366, 768),
        (1536, 864),
        (1440, 900),
        (1280, 720),
    ]

    def __init__(
        self,
        rotation_interval_pages: int = 50,
        rotation_interval_minutes: int = 30,
        max_history: int = 5,
    ):
        """
        Initialize fingerprint rotator.

        Args:
            rotation_interval_pages: Rotate after this many pages (default: 50)
            rotation_interval_minutes: Rotate after this many minutes (default: 30)
            max_history: Maximum profiles to keep in history (default: 5)
        """
        self.rotation_interval_pages = rotation_interval_pages
        self.rotation_interval_minutes = rotation_interval_minutes
        self.max_history = max_history

        self._current_profile: Optional[FingerprintProfile] = None
        self._profile_history: List[int] = []  # Store profile indices
        self._page_count = 0
        self._last_rotation = datetime.now(timezone.utc)

        # Initialize with first profile
        self._current_profile = self._generate_profile()
        logger.info(
            f"FingerprintRotator initialized (rotation: {rotation_interval_pages} pages "
            f"or {rotation_interval_minutes} minutes)"
        )

    def _generate_profile(self, force_index: Optional[int] = None) -> FingerprintProfile:
        """
        Generate a consistent, realistic fingerprint profile.

        Args:
            force_index: Force specific profile index (for testing)

        Returns:
            FingerprintProfile with consistent parameters
        """
        # Select profile from pool, avoiding recent ones
        available_indices = [
            i
            for i in range(len(self.PROFILE_POOL))
            if i not in self._profile_history[-self.max_history :]
        ]

        if not available_indices:
            # If all profiles were used recently, reset history
            self._profile_history = []
            available_indices = list(range(len(self.PROFILE_POOL)))

        if force_index is not None and 0 <= force_index < len(self.PROFILE_POOL):
            profile_idx = force_index
        else:
            profile_idx = random.choice(available_indices)

        # Track profile usage
        self._profile_history.append(profile_idx)
        if len(self._profile_history) > self.max_history:
            self._profile_history.pop(0)

        # Get profile components
        user_agent, platform, timezone, webgl_vendor, webgl_renderer = self.PROFILE_POOL[
            profile_idx
        ]

        # Select consistent viewport
        viewport_width, viewport_height = random.choice(self.VIEWPORTS)

        # Select language
        language = random.choice(self.LANGUAGES)

        # Generate canvas noise parameters (small values to avoid detection)
        canvas_noise_r = random.randint(-5, 5)
        canvas_noise_g = random.randint(-5, 5)
        canvas_noise_b = random.randint(-5, 5)
        canvas_noise_a = random.randint(-2, 2)

        # Hardware specs based on platform
        if "Mac" in platform:
            hardware_concurrency = random.choice([8, 10, 12])
            device_memory = random.choice([8, 16])
            screen_width, screen_height = random.choice([(2560, 1600), (1920, 1080), (3024, 1964)])
        elif "Linux" in platform:
            hardware_concurrency = random.choice([4, 8, 16])
            device_memory = random.choice([8, 16, 32])
            screen_width, screen_height = random.choice([(1920, 1080), (2560, 1440)])
        else:  # Windows
            hardware_concurrency = random.choice([4, 6, 8, 12])
            device_memory = random.choice([8, 16, 32])
            screen_width, screen_height = random.choice([(1920, 1080), (2560, 1440), (1366, 768)])

        profile = FingerprintProfile(
            user_agent=user_agent,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            timezone=timezone,
            language=language,
            platform=platform,
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            canvas_noise_r=canvas_noise_r,
            canvas_noise_g=canvas_noise_g,
            canvas_noise_b=canvas_noise_b,
            canvas_noise_a=canvas_noise_a,
            hardware_concurrency=hardware_concurrency,
            device_memory=device_memory,
            screen_width=screen_width,
            screen_height=screen_height,
        )

        logger.debug(
            f"Generated fingerprint profile: {platform} | {webgl_vendor} | {viewport_width}x{viewport_height}"
        )
        return profile

    def get_current_profile(self) -> FingerprintProfile:
        """
        Get the current active fingerprint profile.

        Returns:
            Current FingerprintProfile
        """
        if self._current_profile is None:
            self._current_profile = self._generate_profile()
        return self._current_profile

    def should_rotate(self, increment_page_count: bool = True) -> bool:
        """
        Check if fingerprint should be rotated based on page count or time.

        Args:
            increment_page_count: Whether to increment page counter (default: True)

        Returns:
            True if rotation is needed, False otherwise
        """
        if increment_page_count:
            self._page_count += 1

        # Check page count threshold
        if self._page_count >= self.rotation_interval_pages:
            logger.info(f"Fingerprint rotation triggered by page count ({self._page_count})")
            return True

        # Check time threshold
        elapsed = datetime.now(timezone.utc) - self._last_rotation
        elapsed_minutes = elapsed.total_seconds() / 60

        if elapsed_minutes >= self.rotation_interval_minutes:
            logger.info(f"Fingerprint rotation triggered by time ({elapsed_minutes:.1f} minutes)")
            return True

        return False

    def rotate(self, force_index: Optional[int] = None) -> FingerprintProfile:
        """
        Rotate to a new fingerprint profile.

        Args:
            force_index: Force specific profile index (for testing)

        Returns:
            New FingerprintProfile
        """
        self._current_profile = self._generate_profile(force_index=force_index)
        self._page_count = 0
        self._last_rotation = datetime.now(timezone.utc)

        logger.info(
            f"Fingerprint rotated: {self._current_profile.platform} | "
            f"{self._current_profile.webgl_vendor}"
        )
        return self._current_profile

    def reset_counters(self) -> None:
        """Reset page count and last rotation time."""
        self._page_count = 0
        self._last_rotation = datetime.now(timezone.utc)
        logger.debug("Fingerprint rotation counters reset")

    def get_stats(self) -> dict:
        """
        Get rotation statistics.

        Returns:
            Dictionary with rotation stats
        """
        elapsed = datetime.now(timezone.utc) - self._last_rotation
        elapsed_minutes = elapsed.total_seconds() / 60

        return {
            "page_count": self._page_count,
            "minutes_since_rotation": round(elapsed_minutes, 1),
            "pages_until_rotation": max(0, self.rotation_interval_pages - self._page_count),
            "minutes_until_rotation": max(
                0, round(self.rotation_interval_minutes - elapsed_minutes, 1)
            ),
            "current_platform": self._current_profile.platform if self._current_profile else None,
            "profile_history_size": len(self._profile_history),
        }
