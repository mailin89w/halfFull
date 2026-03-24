"""
metrics_aggregator.py — Aggregates per-profile results into cohort-level metrics.

Computes DoD (Definition of Done) checks and generates Markdown reports.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from pipeline.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DoD targets — all four must pass for CI green
# ---------------------------------------------------------------------------
DOD_TARGETS: dict[str, float] = {
    "cohort_top1_accuracy": 0.70,   # must be AT OR ABOVE
    "hallucination_rate":   0.05,   # must be BELOW
    "parse_success_rate":   0.95,   # must be AT OR ABOVE
    "over_alert_rate":      0.10,   # must be BELOW
}

# Metrics where LOWER is better (checked as < target)
_LOWER_IS_BETTER = {"hallucination_rate", "over_alert_rate"}


class MetricsAggregator:
    """
    Aggregates scoring results into a full metrics report dict
    and generates Markdown output.
    """

    def aggregate(
        self,
        results: list[dict],
        scoring_engine: ScoringEngine,
    ) -> dict:
        """
        Compute cohort-level metrics and DoD checks.

        Args:
            results: List of per-profile result dicts from ScoringEngine.
            scoring_engine: ScoringEngine instance for metric computation.

        Returns:
            Full metrics report dict.
        """
        run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
        n_profiles = len(results)

        # Core metrics
        cohort_top1    = scoring_engine.top1_accuracy(results)
        positives_top1 = scoring_engine.top1_accuracy(results, filter_type="positive")
        hall_rate       = scoring_engine.hallucination_rate(results)
        parse_rate      = scoring_engine.parse_success_rate(results)
        alert_rate      = scoring_engine.over_alert_rate(results)
        per_condition   = scoring_engine.per_condition_breakdown(results)

        # By quiz path
        full_results   = [r for r in results if r.get("quiz_path") == "full"]
        hybrid_results = [r for r in results if r.get("quiz_path") == "hybrid"]

        by_quiz_path = {
            "full": {
                "top1_accuracy": scoring_engine.top1_accuracy(full_results),
                "n": len(full_results),
            },
            "hybrid": {
                "top1_accuracy": scoring_engine.top1_accuracy(hybrid_results),
                "n": len(hybrid_results),
            },
        }

        # DoD checks
        actuals = {
            "cohort_top1_accuracy": cohort_top1,
            "hallucination_rate":   hall_rate,
            "parse_success_rate":   parse_rate,
            "over_alert_rate":      alert_rate,
        }

        dod_checks: dict[str, dict] = {}
        for metric, target in DOD_TARGETS.items():
            actual = actuals[metric]
            if metric in _LOWER_IS_BETTER:
                passed = actual < target
            else:
                passed = actual >= target
            dod_checks[metric] = {
                "target": target,
                "actual": round(actual, 4),
                "pass":   passed,
            }

        dod_pass = all(v["pass"] for v in dod_checks.values())

        return {
            "run_id":                  run_id,
            "n_profiles":              n_profiles,
            "cohort_top1_accuracy":    round(cohort_top1, 4),
            "positives_top1_accuracy": round(positives_top1, 4),
            "hallucination_rate":      round(hall_rate, 4),
            "parse_success_rate":      round(parse_rate, 4),
            "over_alert_rate":         round(alert_rate, 4),
            "per_condition":           per_condition,
            "by_quiz_path":            by_quiz_path,
            "dod_pass":                dod_pass,
            "dod_checks":              dod_checks,
        }

    def to_markdown(self, report: dict) -> str:
        """Generate a human-readable Markdown eval report."""
        lines: list[str] = []

        lines.append(f"# HalfFull Eval Report — {report['run_id']}")
        lines.append("")

        # -- Cohort Summary -----------------------------------------------
        lines.append("## Cohort Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Profiles evaluated | {report['n_profiles']} |")
        lines.append(f"| Cohort Top-1 Accuracy | {report['cohort_top1_accuracy']:.1%} |")
        lines.append(f"| Positives Top-1 Accuracy | {report['positives_top1_accuracy']:.1%} |")
        lines.append(f"| Hallucination Rate | {report['hallucination_rate']:.1%} |")
        lines.append(f"| Parse Success Rate | {report['parse_success_rate']:.1%} |")
        lines.append(f"| Over-Alert Rate (healthy) | {report['over_alert_rate']:.1%} |")
        lines.append("")

        # -- DoD Checks ---------------------------------------------------
        lines.append("## Definition of Done (DoD)")
        lines.append("")
        overall = "ALL PASSED" if report["dod_pass"] else "SOME FAILED"
        lines.append(f"**Overall: {overall}**")
        lines.append("")
        lines.append("| Metric | Target | Actual | Status |")
        lines.append("|--------|--------|--------|--------|")

        for metric, check in report["dod_checks"].items():
            symbol = "PASS" if check["pass"] else "FAIL"
            direction = "< " if metric in _LOWER_IS_BETTER else ">= "
            lines.append(
                f"| {metric} | {direction}{check['target']:.0%} "
                f"| {check['actual']:.1%} | {symbol} |"
            )
        lines.append("")

        # -- Per-Condition Breakdown ---------------------------------------
        lines.append("## Per-Condition Breakdown")
        lines.append("")
        lines.append("| Condition | Top-1 Acc. | N Profiles | N Correct |")
        lines.append("|-----------|-----------|------------|-----------|")

        for cond, stats in sorted(report["per_condition"].items()):
            acc = stats.get("top1_accuracy", 0.0)
            n   = stats.get("n_profiles", 0)
            nc  = stats.get("n_correct", 0)
            lines.append(f"| {cond} | {acc:.1%} | {n} | {nc} |")
        lines.append("")

        # -- By Quiz Path -------------------------------------------------
        lines.append("## By Quiz Path")
        lines.append("")
        lines.append("| Quiz Path | Top-1 Acc. | N Profiles |")
        lines.append("|-----------|-----------|------------|")

        for path, stats in report["by_quiz_path"].items():
            acc = stats.get("top1_accuracy", 0.0)
            n   = stats.get("n", 0)
            lines.append(f"| {path} | {acc:.1%} | {n} |")
        lines.append("")

        return "\n".join(lines)
