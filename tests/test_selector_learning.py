"""Tests for adaptive selector learning system."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.utils.selector_learning import SelectorLearner


@pytest.fixture
def temp_metrics_file(tmp_path):
    """Create a temporary metrics file."""
    metrics_file = tmp_path / "selector_metrics.json"
    return metrics_file


@pytest.fixture
def learner(temp_metrics_file):
    """Create a SelectorLearner instance with temp file."""
    return SelectorLearner(str(temp_metrics_file))


def test_selector_learner_init(learner, temp_metrics_file):
    """Test SelectorLearner initialization."""
    assert learner.metrics_file == temp_metrics_file
    assert isinstance(learner.metrics, dict)
    assert len(learner.metrics) == 0


def test_record_success_primary(learner):
    """Test recording success for primary selector."""
    selector_path = "login.email_input"
    
    learner.record_success(selector_path, 0)
    
    metrics = learner.metrics[selector_path]
    assert metrics["primary_success_count"] == 1
    assert metrics["current_preferred"] == 0


def test_record_success_fallback(learner):
    """Test recording success for fallback selector."""
    selector_path = "login.email_input"
    
    # Record 5 consecutive successes for fallback
    for _ in range(5):
        learner.record_success(selector_path, 1)
    
    metrics = learner.metrics[selector_path]
    fallback_stats = metrics["fallback_stats"]["fallback_0"]
    assert fallback_stats["success_count"] == 5
    assert fallback_stats["consecutive_success"] == 0  # Reset after promotion
    assert metrics["current_preferred"] == 1  # Auto-promoted


def test_auto_promotion_after_5_successes(learner):
    """Test auto-promotion after 5 consecutive successes."""
    selector_path = "login.password_input"
    
    # Record 4 successes - should not promote yet
    for _ in range(4):
        learner.record_success(selector_path, 1)
    
    assert learner.metrics[selector_path]["current_preferred"] == 0
    
    # 5th success should trigger promotion
    learner.record_success(selector_path, 1)
    
    assert learner.metrics[selector_path]["current_preferred"] == 1


def test_record_failure_primary(learner):
    """Test recording failure for primary selector."""
    selector_path = "login.submit_button"
    
    learner.record_failure(selector_path, 0)
    
    metrics = learner.metrics[selector_path]
    assert metrics["primary_fail_count"] == 1
    assert metrics["primary_consecutive_fail"] == 1


def test_auto_demotion_after_3_failures(learner):
    """Test auto-demotion after 3 consecutive failures."""
    selector_path = "appointment.centre_dropdown"
    
    # First, record some fallback successes to have a viable alternative
    for _ in range(3):
        learner.record_success(selector_path, 1)
    
    # Reset to test demotion
    learner.metrics[selector_path]["current_preferred"] = 0
    
    # Record 3 consecutive failures
    for _ in range(3):
        learner.record_failure(selector_path, 0)
    
    metrics = learner.metrics[selector_path]
    assert metrics["primary_consecutive_fail"] == 3
    # Should have demoted primary (preferred should be 1 if fallback has good stats)
    assert metrics["current_preferred"] == 1


def test_record_failure_fallback(learner):
    """Test recording failure for fallback selector."""
    selector_path = "login.email_input"
    
    learner.record_failure(selector_path, 1)
    
    metrics = learner.metrics[selector_path]
    fallback_stats = metrics["fallback_stats"]["fallback_0"]
    assert fallback_stats["fail_count"] == 1
    assert fallback_stats["consecutive_success"] == 0


def test_get_optimized_order_no_metrics(learner):
    """Test get_optimized_order with no existing metrics."""
    selectors = ["primary", "fallback1", "fallback2"]
    result = learner.get_optimized_order("unknown.path", selectors)
    
    # Should return original order
    assert result == selectors


def test_get_optimized_order_with_preferred(learner):
    """Test get_optimized_order with preferred fallback."""
    selector_path = "login.email_input"
    selectors = ["primary", "fallback1", "fallback2"]
    
    # Set preferred to fallback1 (index 1)
    learner.metrics[selector_path] = {
        "current_preferred": 1,
        "primary_success_count": 0,
        "primary_fail_count": 5,
        "fallback_stats": {},
        "last_updated": "2026-01-24T10:00:00Z"
    }
    
    result = learner.get_optimized_order(selector_path, selectors)
    
    # Should put fallback1 first
    assert result[0] == "fallback1"
    assert "primary" in result
    assert "fallback2" in result


def test_get_optimized_order_empty_list(learner):
    """Test get_optimized_order with empty selector list."""
    result = learner.get_optimized_order("any.path", [])
    assert result == []


def test_metrics_persistence(temp_metrics_file):
    """Test that metrics are persisted to disk."""
    learner1 = SelectorLearner(str(temp_metrics_file))
    
    # Record some data
    learner1.record_success("login.email_input", 0)
    learner1.record_success("login.password_input", 1)
    
    # Create new instance to load from disk
    learner2 = SelectorLearner(str(temp_metrics_file))
    
    # Should have loaded the data
    assert "login.email_input" in learner2.metrics
    assert "login.password_input" in learner2.metrics
    assert learner2.metrics["login.email_input"]["primary_success_count"] == 1


def test_get_stats_summary(learner):
    """Test get_stats_summary method."""
    # Record some data
    learner.record_success("login.email_input", 0)
    learner.record_success("login.email_input", 0)
    learner.record_failure("login.email_input", 0)
    
    for _ in range(5):
        learner.record_success("login.password_input", 1)  # Will auto-promote
    
    summary = learner.get_stats_summary()
    
    assert summary["total_selectors"] == 2
    assert summary["selectors_with_promotions"] == 1  # password_input was promoted
    assert summary["total_successes"] == 7
    assert summary["total_failures"] == 1
    assert "login.email_input" in summary["details"]
    assert "login.password_input" in summary["details"]


def test_get_stats_summary_empty(learner):
    """Test get_stats_summary with no metrics."""
    summary = learner.get_stats_summary()
    
    assert summary["total_selectors"] == 0
    assert summary["selectors_with_promotions"] == 0
    assert summary["total_successes"] == 0
    assert summary["total_failures"] == 0
    assert summary["details"] == {}


def test_consecutive_success_reset_on_failure(learner):
    """Test that consecutive success counter resets on failure."""
    selector_path = "login.submit_button"
    
    # Record 3 successes
    for _ in range(3):
        learner.record_success(selector_path, 1)
    
    fallback_stats = learner.metrics[selector_path]["fallback_stats"]["fallback_0"]
    assert fallback_stats["consecutive_success"] == 3
    
    # Record a failure
    learner.record_failure(selector_path, 1)
    
    # Consecutive success should be reset
    assert fallback_stats["consecutive_success"] == 0
    assert fallback_stats["success_count"] == 3  # But total count unchanged


def test_find_best_fallback(learner):
    """Test _find_best_fallback method."""
    metrics = {
        "fallback_stats": {
            "fallback_0": {"success_count": 5, "fail_count": 5},  # 50% success
            "fallback_1": {"success_count": 8, "fail_count": 2},  # 80% success
            "fallback_2": {"success_count": 1, "fail_count": 9},  # 10% success
        }
    }
    
    best_index = learner._find_best_fallback(metrics)
    
    # Should return fallback_1 (index 1) as it has highest success rate
    assert best_index == 1


def test_find_best_fallback_no_stats(learner):
    """Test _find_best_fallback with no stats."""
    metrics = {"fallback_stats": {}}
    
    best_index = learner._find_best_fallback(metrics)
    
    assert best_index is None


def test_multiple_fallback_tracking(learner):
    """Test tracking multiple fallbacks simultaneously."""
    selector_path = "appointment.centre_dropdown"
    
    # Test different fallbacks
    learner.record_success(selector_path, 1)  # fallback_0
    learner.record_success(selector_path, 2)  # fallback_1
    learner.record_failure(selector_path, 3)  # fallback_2
    
    metrics = learner.metrics[selector_path]
    assert "fallback_0" in metrics["fallback_stats"]
    assert "fallback_1" in metrics["fallback_stats"]
    assert "fallback_2" in metrics["fallback_stats"]
    
    assert metrics["fallback_stats"]["fallback_0"]["success_count"] == 1
    assert metrics["fallback_stats"]["fallback_1"]["success_count"] == 1
    assert metrics["fallback_stats"]["fallback_2"]["fail_count"] == 1
