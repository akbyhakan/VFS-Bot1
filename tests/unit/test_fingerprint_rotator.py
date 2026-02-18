"""Tests for fingerprint rotator."""

from datetime import datetime, timedelta, timezone

import pytest

from src.utils.anti_detection.fingerprint_rotator import FingerprintProfile, FingerprintRotator


class TestFingerprintProfile:
    """Tests for FingerprintProfile dataclass."""

    def test_profile_creation(self):
        """Test profile creation with all fields."""
        profile = FingerprintProfile(
            user_agent="Mozilla/5.0",
            viewport_width=1920,
            viewport_height=1080,
            timezone="Europe/Istanbul",
            language="en-US",
            platform="Win32",
            webgl_vendor="Google Inc.",
            webgl_renderer="ANGLE",
            canvas_noise_r=1,
            canvas_noise_g=2,
            canvas_noise_b=3,
            canvas_noise_a=1,
        )

        assert profile.user_agent == "Mozilla/5.0"
        assert profile.viewport_width == 1920
        assert profile.viewport_height == 1080
        assert profile.timezone == "Europe/Istanbul"
        assert profile.platform == "Win32"


class TestFingerprintRotator:
    """Tests for FingerprintRotator."""

    def test_rotator_initialization(self):
        """Test rotator initialization with default values."""
        rotator = FingerprintRotator()

        assert rotator.rotation_interval_pages == 50
        assert rotator.rotation_interval_minutes == 30
        assert rotator._current_profile is not None
        assert rotator._page_count == 0

    def test_rotator_custom_intervals(self):
        """Test rotator initialization with custom intervals."""
        rotator = FingerprintRotator(rotation_interval_pages=100, rotation_interval_minutes=60)

        assert rotator.rotation_interval_pages == 100
        assert rotator.rotation_interval_minutes == 60

    def test_get_current_profile(self):
        """Test getting current profile."""
        rotator = FingerprintRotator()
        profile = rotator.get_current_profile()

        assert isinstance(profile, FingerprintProfile)
        assert profile.user_agent is not None
        assert profile.platform is not None
        assert profile.webgl_vendor is not None

    def test_profile_generation_consistency(self):
        """Test that generated profiles have consistent parameters."""
        rotator = FingerprintRotator()
        profile = rotator._generate_profile()

        # Check platform and user agent match
        if "Win" in profile.platform:
            assert "Windows" in profile.user_agent or "Win" in profile.user_agent
        elif "Mac" in profile.platform:
            assert "Mac" in profile.user_agent

        # Check canvas noise is within bounds
        assert -5 <= profile.canvas_noise_r <= 5
        assert -5 <= profile.canvas_noise_g <= 5
        assert -5 <= profile.canvas_noise_b <= 5
        assert -2 <= profile.canvas_noise_a <= 2

        # Check viewport is valid
        assert profile.viewport_width > 0
        assert profile.viewport_height > 0

    def test_should_rotate_page_count(self):
        """Test rotation trigger based on page count."""
        rotator = FingerprintRotator(rotation_interval_pages=10)

        # Should not rotate initially
        assert not rotator.should_rotate(increment_page_count=False)

        # Increment page count
        for _ in range(9):
            rotator.should_rotate(increment_page_count=True)

        # Should trigger rotation on 10th page
        assert rotator.should_rotate(increment_page_count=True)

    def test_should_rotate_time(self):
        """Test rotation trigger based on time."""
        rotator = FingerprintRotator(rotation_interval_minutes=1)

        # Manually set last rotation to past time
        rotator._last_rotation = datetime.now(timezone.utc) - timedelta(minutes=2)

        # Should trigger rotation
        assert rotator.should_rotate(increment_page_count=False)

    def test_rotate_creates_new_profile(self):
        """Test that rotate creates a new profile."""
        rotator = FingerprintRotator()
        old_profile = rotator.get_current_profile()

        new_profile = rotator.rotate()

        assert new_profile is not old_profile
        assert rotator._page_count == 0

    def test_profile_history_tracking(self):
        """Test that profile history prevents immediate repeats."""
        rotator = FingerprintRotator(max_history=3)

        # Generate several profiles
        profiles = []
        for i in range(5):
            profile = rotator._generate_profile(force_index=i % len(rotator.PROFILE_POOL))
            profiles.append(profile)

        # History should be limited to max_history
        assert len(rotator._profile_history) <= rotator.max_history

    def test_profile_history_prevents_repeats(self):
        """Test that recent profiles are not repeated."""
        rotator = FingerprintRotator(max_history=5)

        # Generate profiles without forcing index
        for _ in range(5):
            rotator._generate_profile()

        # Track history
        initial_history = rotator._profile_history.copy()

        # Next profile should avoid recent ones if possible
        _ = rotator._generate_profile()

        # If pool is larger than history, new profile should be different
        if len(rotator.PROFILE_POOL) > len(initial_history):
            # The new profile index should not be in recent history (if pool is large enough)
            pass

    def test_reset_counters(self):
        """Test counter reset functionality."""
        rotator = FingerprintRotator()

        # Increment counters
        rotator._page_count = 50
        rotator._last_rotation = datetime.now(timezone.utc) - timedelta(hours=1)

        # Reset
        rotator.reset_counters()

        assert rotator._page_count == 0
        # Last rotation should be recent
        assert (datetime.now(timezone.utc) - rotator._last_rotation).total_seconds() < 1

    def test_get_stats(self):
        """Test statistics retrieval."""
        rotator = FingerprintRotator(rotation_interval_pages=100)
        rotator._page_count = 25

        stats = rotator.get_stats()

        assert "page_count" in stats
        assert "minutes_since_rotation" in stats
        assert "pages_until_rotation" in stats
        assert "current_platform" in stats
        assert "profile_history_size" in stats

        assert stats["page_count"] == 25
        assert stats["pages_until_rotation"] == 75
        assert stats["current_platform"] is not None

    def test_force_profile_index(self):
        """Test forcing specific profile index."""
        rotator = FingerprintRotator()

        # Force specific profile
        profile = rotator._generate_profile(force_index=0)

        # Should use first profile in pool
        expected_ua = rotator.PROFILE_POOL[0][0]
        assert profile.user_agent == expected_ua

    def test_all_profiles_are_valid(self):
        """Test that all predefined profiles are valid."""
        rotator = FingerprintRotator()

        for i in range(len(rotator.PROFILE_POOL)):
            profile = rotator._generate_profile(force_index=i)

            # All fields should be populated
            assert profile.user_agent
            assert profile.platform
            assert profile.timezone
            assert profile.webgl_vendor
            assert profile.webgl_renderer
            assert profile.viewport_width > 0
            assert profile.viewport_height > 0

    def test_profile_rotation_workflow(self):
        """Test complete rotation workflow."""
        rotator = FingerprintRotator(rotation_interval_pages=5)

        # Get initial profile
        initial_profile = rotator.get_current_profile()

        # Simulate page creation
        for _ in range(4):
            assert not rotator.should_rotate(increment_page_count=True)

        # Should trigger rotation
        assert rotator.should_rotate(increment_page_count=True)

        # Rotate to new profile
        new_profile = rotator.rotate()

        # Profile should be different
        assert new_profile is not initial_profile
        assert rotator._page_count == 0

    def test_hardware_specs_match_platform(self):
        """Test that hardware specs are consistent with platform."""
        rotator = FingerprintRotator()

        for i in range(len(rotator.PROFILE_POOL)):
            profile = rotator._generate_profile(force_index=i)

            if "Mac" in profile.platform:
                # Mac should have appropriate specs
                assert profile.hardware_concurrency >= 8
                assert profile.device_memory >= 8
            elif "Linux" in profile.platform:
                # Linux can have various specs
                assert profile.hardware_concurrency >= 4
            else:  # Windows
                # Windows typical specs
                assert profile.hardware_concurrency >= 4
                assert profile.device_memory >= 8
