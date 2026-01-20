"""Tests for token utility functions."""

import pytest
from src.utils.token_utils import calculate_effective_expiry


class TestCalculateEffectiveExpiry:
    """Test suite for calculate_effective_expiry function."""

    def test_normal_expiry_with_buffer(self):
        """Test normal expiry with buffer."""
        # 60 min expiry, 5 min buffer -> 55 min effective
        result = calculate_effective_expiry(60, 5)
        assert result == 55

    def test_short_expiry_uses_half_buffer(self):
        """Test short expiry uses 50% buffer."""
        # 2 min expiry, 5 min buffer -> 1 min effective (50% of expiry)
        result = calculate_effective_expiry(2, 5)
        assert result == 1

    def test_zero_expiry_returns_min(self):
        """Test zero expiry returns minimum value."""
        result = calculate_effective_expiry(0, 5)
        assert result == 1

    def test_negative_expiry_returns_min(self):
        """Test negative expiry returns minimum value."""
        result = calculate_effective_expiry(-10, 5)
        assert result == 1

    def test_buffer_larger_than_expiry(self):
        """Test buffer larger than expiry is capped."""
        # 10 min expiry, 15 min buffer -> 1 min effective (capped at expiry - 1)
        result = calculate_effective_expiry(10, 15)
        assert result == 1

    def test_very_small_expiry(self):
        """Test very small expiry (1 min)."""
        # 1 min expiry -> 1 min effective (minimum)
        result = calculate_effective_expiry(1, 5)
        assert result == 1

    def test_large_expiry(self):
        """Test large expiry value."""
        # 3600 min (60 hours) expiry, 5 min buffer -> 3595 min effective
        result = calculate_effective_expiry(3600, 5)
        assert result == 3595

    def test_expiry_equals_buffer_plus_one(self):
        """Test expiry equals buffer + 1."""
        # 6 min expiry, 5 min buffer -> 1 min effective
        result = calculate_effective_expiry(6, 5)
        assert result == 1

    def test_custom_min_expiry(self):
        """Test custom minimum expiry."""
        # With custom min_expiry of 5
        result = calculate_effective_expiry(0, 5, min_expiry=5)
        assert result == 5

    def test_edge_case_expiry_2_min(self):
        """Test edge case at 2 min expiry boundary."""
        # At exactly 2 min, uses 50% buffer
        result = calculate_effective_expiry(2, 10)
        assert result == 1

    def test_edge_case_expiry_3_min(self):
        """Test edge case just above 2 min expiry boundary."""
        # At 3 min, uses normal buffer logic
        result = calculate_effective_expiry(3, 10)
        assert result == 1  # min(10, 3-1) = 2, max(1, 3-2) = 1
