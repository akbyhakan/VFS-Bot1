"""Adaptive selector learning system for auto-promotion and optimization."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SelectorLearner:
    """Track selector performance and auto-promote successful fallbacks."""

    def __init__(self, metrics_file: str = "data/selector_metrics.json"):
        """
        Initialize selector learner.

        Args:
            metrics_file: Path to metrics JSON file
        """
        self.metrics_file = Path(metrics_file)
        self.metrics: Dict[str, Any] = {}
        self._load_metrics()
        self._ensure_data_directory()

    def _ensure_data_directory(self) -> None:
        """Ensure data directory exists."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_metrics(self) -> None:
        """Load metrics from JSON file."""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    self.metrics = json.load(f)
                logger.debug(f"Loaded selector metrics from {self.metrics_file}")
            else:
                logger.info("No existing metrics file, starting fresh")
                self.metrics = {}
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            self.metrics = {}

    def _save_metrics(self) -> None:
        """Save metrics to JSON file."""
        try:
            self._ensure_data_directory()
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, indent=2)
            logger.debug(f"Saved selector metrics to {self.metrics_file}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _get_selector_metrics(self, selector_path: str) -> Dict[str, Any]:
        """
        Get or create metrics for a selector path.

        Args:
            selector_path: Dot-separated selector path

        Returns:
            Metrics dictionary for the selector
        """
        if selector_path not in self.metrics:
            self.metrics[selector_path] = {
                "primary_success_count": 0,
                "primary_fail_count": 0,
                "fallback_stats": {},
                "current_preferred": 0,  # 0 = primary, 1+ = fallback index
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        result: Dict[str, Any] = self.metrics[selector_path]
        return result

    def record_success(self, selector_path: str, selector_index: int) -> None:
        """
        Record successful selector usage.

        Args:
            selector_path: Dot-separated selector path
            selector_index: Index of selector (0=primary, 1+=fallback)
        """
        metrics = self._get_selector_metrics(selector_path)

        if selector_index == 0:
            # Primary selector succeeded
            metrics["primary_success_count"] += 1
            # Reset consecutive failures
            if "primary_consecutive_fail" in metrics:
                metrics["primary_consecutive_fail"] = 0
        else:
            # Fallback selector succeeded
            fallback_key = f"fallback_{selector_index - 1}"
            if fallback_key not in metrics["fallback_stats"]:
                metrics["fallback_stats"][fallback_key] = {
                    "success_count": 0,
                    "fail_count": 0,
                    "consecutive_success": 0,
                }

            fallback_stats = metrics["fallback_stats"][fallback_key]
            fallback_stats["success_count"] += 1
            fallback_stats["consecutive_success"] = (
                fallback_stats.get("consecutive_success", 0) + 1
            )

            # Auto-promote after 5 consecutive successes
            if fallback_stats["consecutive_success"] >= 5:
                if metrics["current_preferred"] != selector_index:
                    logger.warning(
                        f"♻️ LEARNING: Auto-promoting fallback #{selector_index - 1} "
                        f"for '{selector_path}' (5 consecutive successes)"
                    )
                    metrics["current_preferred"] = selector_index
                    fallback_stats["consecutive_success"] = 0  # Reset after promotion

        metrics["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save_metrics()

    def record_failure(self, selector_path: str, selector_index: int) -> None:
        """
        Record selector failure.

        Args:
            selector_path: Dot-separated selector path
            selector_index: Index of selector (0=primary, 1+=fallback)
        """
        metrics = self._get_selector_metrics(selector_path)

        if selector_index == 0:
            # Primary selector failed
            metrics["primary_fail_count"] += 1
            metrics["primary_consecutive_fail"] = (
                metrics.get("primary_consecutive_fail", 0) + 1
            )

            # Demote after 3 consecutive failures
            if metrics["primary_consecutive_fail"] >= 3 and metrics["current_preferred"] == 0:
                logger.warning(
                    f"♻️ LEARNING: Demoting primary selector for '{selector_path}' "
                    f"(3 consecutive failures)"
                )
                # Try to find a working fallback
                best_fallback = self._find_best_fallback(metrics)
                if best_fallback is not None:
                    metrics["current_preferred"] = best_fallback + 1  # +1 because 0 is primary
        else:
            # Fallback selector failed
            fallback_key = f"fallback_{selector_index - 1}"
            if fallback_key not in metrics["fallback_stats"]:
                metrics["fallback_stats"][fallback_key] = {
                    "success_count": 0,
                    "fail_count": 0,
                    "consecutive_success": 0,
                }

            fallback_stats = metrics["fallback_stats"][fallback_key]
            fallback_stats["fail_count"] += 1
            fallback_stats["consecutive_success"] = 0  # Reset consecutive success

        metrics["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save_metrics()

    def _find_best_fallback(self, metrics: Dict[str, Any]) -> Optional[int]:
        """
        Find the best performing fallback selector.

        Args:
            metrics: Selector metrics

        Returns:
            Index of best fallback or None
        """
        best_index = None
        best_ratio = 0.0

        for fallback_key, stats in metrics["fallback_stats"].items():
            success = stats.get("success_count", 0)
            fail = stats.get("fail_count", 0)
            total = success + fail

            if total > 0:
                ratio = success / total
                if ratio > best_ratio:
                    best_ratio = ratio
                    # Extract index from "fallback_N"
                    best_index = int(fallback_key.split("_")[1])

        return best_index

    def get_optimized_order(self, selector_path: str, selectors: List[str]) -> List[str]:
        """
        Get selectors reordered based on performance.

        Args:
            selector_path: Dot-separated selector path
            selectors: Original list of selectors (primary first, then fallbacks)

        Returns:
            Reordered list with best-performing selector first
        """
        if not selectors:
            return []

        if selector_path not in self.metrics:
            # No metrics yet, return original order
            return selectors

        metrics = self.metrics[selector_path]
        preferred_index = metrics.get("current_preferred", 0)

        if preferred_index == 0 or preferred_index >= len(selectors):
            # Primary is preferred or invalid index, return original order
            return selectors

        # Reorder: put preferred selector first
        reordered = [selectors[preferred_index]]
        for i, selector in enumerate(selectors):
            if i != preferred_index:
                reordered.append(selector)

        logger.debug(
            f"♻️ Optimized selector order for '{selector_path}': "
            f"Using fallback #{preferred_index - 1} first"
        )

        return reordered

    def get_stats_summary(self) -> Dict[str, Any]:
        """
        Get performance dashboard data.

        Returns:
            Summary statistics for all tracked selectors
        """
        summary = {
            "total_selectors": len(self.metrics),
            "selectors_with_promotions": 0,
            "total_successes": 0,
            "total_failures": 0,
            "details": {},
        }

        for path, metrics in self.metrics.items():
            primary_success = metrics.get("primary_success_count", 0)
            primary_fail = metrics.get("primary_fail_count", 0)

            fallback_success = sum(
                stats.get("success_count", 0)
                for stats in metrics.get("fallback_stats", {}).values()
            )
            fallback_fail = sum(
                stats.get("fail_count", 0) for stats in metrics.get("fallback_stats", {}).values()
            )

            total_success = primary_success + fallback_success
            total_fail = primary_fail + fallback_fail

            summary["total_successes"] += total_success
            summary["total_failures"] += total_fail

            if metrics.get("current_preferred", 0) != 0:
                selectors_with_promotions: int = summary["selectors_with_promotions"]
                summary["selectors_with_promotions"] = selectors_with_promotions + 1

            details_dict: Dict[str, Any] = summary["details"]
            details_dict[path] = {
                "success_rate": (
                    total_success / (total_success + total_fail)
                    if (total_success + total_fail) > 0
                    else 0.0
                ),
                "preferred_index": metrics.get("current_preferred", 0),
                "last_updated": metrics.get("last_updated"),
            }

        return summary
