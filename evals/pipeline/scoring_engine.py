"""
scoring_engine.py — Computes per-profile and cohort-level evaluation metrics.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config import CONDITION_IDS
    VALID_CONDITION_IDS = set(CONDITION_IDS)
except ImportError:
    VALID_CONDITION_IDS = {
        "menopause", "perimenopause", "hypothyroidism", "kidney_disease",
        "sleep_disorder", "anemia", "iron_deficiency", "hepatitis",
        "prediabetes", "inflammation", "electrolyte_imbalance",
    }

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    Computes per-profile scores and cohort-level aggregate metrics.
    """

    def score_profile(
        self,
        profile: dict,
        model_output: dict | None,
        parse_success: bool,
    ) -> dict:
        """
        Compute per-profile result dict.

        Args:
            profile: Validated synthetic profile.
            model_output: Parsed MedGemma response dict, or None.
            parse_success: Whether JSON parsing succeeded.

        Returns:
            Per-profile result dict with accuracy and hallucination fields.
        """
        profile_id = profile.get("profile_id", "")
        profile_type = profile.get("profile_type", "")
        target_condition = profile.get("target_condition", "") or None
        quiz_path = profile.get("quiz_path", "full")

        # Ground truth primary condition
        ground_truth = profile.get("ground_truth", {})
        expected = ground_truth.get("expected_conditions", [])
        ground_truth_primary = (
            expected[0]["condition_id"] if expected else None
        )

        # Model outputs
        model_top1: str | None = None
        model_top1_confidence: float | None = None
        top1_correct: bool | None = None
        hallucinated_ids: list[str] = []

        if parse_success and model_output is not None:
            top_conditions = model_output.get("top_conditions", [])

            if top_conditions:
                top1 = top_conditions[0]
                model_top1 = top1.get("condition_id")
                model_top1_confidence = top1.get("confidence")

                # Check top-1 correctness
                if ground_truth_primary is not None and model_top1 is not None:
                    top1_correct = (model_top1 == ground_truth_primary)
                elif profile_type == "healthy":
                    # For healthy profiles, no condition should be flagged
                    # top1_correct = True only if confidence < 0.5
                    top1_correct = (model_top1_confidence or 0.0) < 0.5
                else:
                    top1_correct = None

            # Detect hallucinated condition IDs
            for cond in top_conditions:
                cid = cond.get("condition_id", "")
                if cid and cid not in VALID_CONDITION_IDS:
                    hallucinated_ids.append(cid)

        return {
            "profile_id":            profile_id,
            "profile_type":          profile_type,
            "target_condition":      target_condition,
            "quiz_path":             quiz_path,
            "parse_success":         parse_success,
            "model_top1":            model_top1,
            "model_top1_confidence": model_top1_confidence,
            "top1_correct":          top1_correct,
            "hallucinated_ids":      hallucinated_ids,
            "ground_truth_primary":  ground_truth_primary,
            # Store full output for report detail
            "_model_output":         model_output,
        }

    # ------------------------------------------------------------------
    # Aggregate metric methods
    # ------------------------------------------------------------------

    def top1_accuracy(
        self,
        results: list[dict],
        filter_type: str | None = None,
    ) -> float:
        """
        Compute top-1 accuracy over results.

        Args:
            filter_type: If set, only consider profiles of this type.
        """
        filtered = results
        if filter_type:
            filtered = [r for r in results if r.get("profile_type") == filter_type]

        # Only count profiles where top1_correct is not None (excludes parse failures)
        scorable = [r for r in filtered if r.get("top1_correct") is not None]
        if not scorable:
            return 0.0

        correct = sum(1 for r in scorable if r.get("top1_correct") is True)
        return correct / len(scorable)

    def hallucination_rate(self, results: list[dict]) -> float:
        """
        Fraction of profiles where at least one hallucinated condition ID appears.
        """
        if not results:
            return 0.0
        hallucinated = sum(
            1 for r in results if r.get("hallucinated_ids")
        )
        return hallucinated / len(results)

    def parse_success_rate(self, results: list[dict]) -> float:
        """Fraction of profiles where JSON parsing succeeded."""
        if not results:
            return 0.0
        succeeded = sum(1 for r in results if r.get("parse_success"))
        return succeeded / len(results)

    def over_alert_rate(self, results: list[dict]) -> float:
        """
        On healthy profiles only: fraction where any condition confidence > 0.5.
        """
        healthy = [r for r in results if r.get("profile_type") == "healthy"]
        if not healthy:
            return 0.0

        over_alerted = 0
        for r in healthy:
            output = r.get("_model_output") or {}
            top_conditions = output.get("top_conditions", [])
            if any((c.get("confidence") or 0.0) > 0.5 for c in top_conditions):
                over_alerted += 1

        return over_alerted / len(healthy)

    def per_condition_breakdown(
        self, results: list[dict]
    ) -> dict[str, dict]:
        """
        Per-condition top-1 accuracy breakdown.

        Returns:
            {condition_id: {"top1_accuracy": float, "n_profiles": int, "n_correct": int}}
        """
        by_condition: dict[str, list[dict]] = {}
        for r in results:
            target = r.get("target_condition")
            if target:
                by_condition.setdefault(target, []).append(r)

        breakdown: dict[str, dict] = {}
        for condition, cond_results in by_condition.items():
            scorable = [r for r in cond_results if r.get("top1_correct") is not None]
            n_correct = sum(1 for r in scorable if r.get("top1_correct") is True)
            breakdown[condition] = {
                "top1_accuracy": n_correct / len(scorable) if scorable else 0.0,
                "n_profiles":    len(cond_results),
                "n_correct":     n_correct,
                "n_scorable":    len(scorable),
            }

        return breakdown
