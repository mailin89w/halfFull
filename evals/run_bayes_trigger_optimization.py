#!/usr/bin/env python3
"""
Recommend disease-specific Bayesian trigger policies from observed 760-cohort gain.

Inputs
------
- Latest ml_vs_bayesian_update_only comparison artifact
- Balanced 760 cohort profiles

Outputs
-------
- Per-disease table with:
  - ML recall@3
  - default ML+Bayes recall@3
  - full ML+Bayes recall@3
  - full-vs-default lift
  - absent-FP delta
  - default question trigger rate
  - default question load
  - recommended trigger class

Trigger classes
---------------
- aggressive          : lower threshold / broad Bayes routing
- moderate            : lower threshold modestly
- topk_rescue_only    : keep threshold but allow rescue routing
- minimal             : keep conservative / little evidence of incremental value
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
PROFILES_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.run_bayesian import handle_questions
from compare_ml_vs_bayesian_update_only import EVAL_CONDITIONS_12, EVAL_TO_BAYES


def _safe_git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        sha = proc.stdout.strip()
        return sha or None
    except Exception:
        return None


def latest_compare_artifact() -> tuple[Path, dict[str, Any]]:
    path = max(RESULTS_DIR.glob("ml_vs_bayesian_update_only_*.json"), key=lambda p: p.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def load_profiles() -> dict[str, dict[str, Any]]:
    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return {profile["profile_id"]: profile for profile in profiles}


def _recommend_class(
    *,
    lift_pp: float,
    fp_delta_pp: float,
    mean_questions_when_triggered: float,
    trigger_rate: float,
) -> str:
    utility = lift_pp - 0.6 * max(fp_delta_pp, 0.0) - 1.5 * mean_questions_when_triggered
    if lift_pp >= 12.0 and utility >= 6.0:
        return "aggressive"
    if lift_pp >= 5.0 and utility >= 1.5:
        return "moderate"
    if lift_pp >= 1.0 and trigger_rate >= 0.10:
        return "topk_rescue_only"
    return "minimal"


def _reason(
    *,
    recommendation: str,
    lift_pp: float,
    fp_delta_pp: float,
    mean_questions_when_triggered: float,
) -> str:
    if recommendation == "aggressive":
        return (
            f"Large full-vs-default recall@3 lift ({lift_pp:+.1f} pp) with manageable "
            f"question cost ({mean_questions_when_triggered:.1f} questions when triggered)."
        )
    if recommendation == "moderate":
        return (
            f"Material recall@3 lift remains ({lift_pp:+.1f} pp); worth broader Bayes routing, "
            f"but keep some threshold discipline."
        )
    if recommendation == "topk_rescue_only":
        return (
            f"Incremental lift is modest ({lift_pp:+.1f} pp) or offset by FP/question cost; "
            f"prefer rescue logic over aggressive threshold cuts."
        )
    return (
        f"Little observed incremental value ({lift_pp:+.1f} pp) relative to current default "
        f"or question/FP cost."
    )


def build_markdown(
    run_id: str,
    source_artifact: Path,
    payload: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# Bayesian Trigger Optimization — {run_id}")
    lines.append("")
    lines.append(f"- Source compare artifact: `{source_artifact}`")
    lines.append(f"- Cohort: `{PROFILES_PATH}`")
    lines.append("- Objective: optimize trigger policy by observed Bayes lift, not only raw ML confidence.")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("| Condition | Recommendation | Full-default lift | FP delta | Trigger rate | Mean Qs when triggered | Reason |")
    lines.append("|-----------|----------------|-------------------|----------|--------------|------------------------|--------|")
    for row in payload["recommendations"]:
        lines.append(
            f"| {row['condition']} | {row['recommendation']} | {row['full_minus_default_recall_at_3_pp']:+.1f} pp | "
            f"{row['full_minus_default_absent_fp_at_3_pp']:+.1f} pp | {row['default_trigger_rate']:.1%} | "
            f"{row['mean_questions_when_triggered']:.2f} | {row['reason']} |"
        )
    lines.append("")
    lines.append("## Detailed Metrics")
    lines.append("")
    lines.append("| Condition | ML recall@3 | Default recall@3 | Full recall@3 | Full-default lift | Default FP@3 | Full FP@3 | Trigger rate | Mean Qs/profile | Mean Qs/triggered |")
    lines.append("|-----------|-------------|------------------|---------------|-------------------|--------------|-----------|--------------|-----------------|-------------------|")
    for row in payload["recommendations"]:
        lines.append(
            f"| {row['condition']} | {row['ml_recall_at_3']:.1%} | {row['default_recall_at_3']:.1%} | "
            f"{row['full_recall_at_3']:.1%} | {row['full_minus_default_recall_at_3_pp']:+.1f} pp | "
            f"{row['default_absent_fp_at_3']:.1%} | {row['full_absent_fp_at_3']:.1%} | "
            f"{row['default_trigger_rate']:.1%} | {row['mean_questions_per_profile']:.2f} | "
            f"{row['mean_questions_when_triggered']:.2f} |"
        )
    return "\n".join(lines)


def main() -> int:
    source_path, compare = latest_compare_artifact()
    profiles_by_id = load_profiles()
    updater = BayesianUpdater()

    ml_records = {row["profile_id"]: row for row in compare["records_by_arm"]["ml_only"]}
    ml_summary = compare["arms"]["ml_only"]["per_condition"]
    default_summary = compare["arms"]["default_triggered_bayesian"]["per_condition"]
    full_summary = compare["arms"]["bayesian_update_only"]["per_condition"]

    question_counts_by_condition: dict[str, list[int]] = {condition_id: [] for condition_id in EVAL_CONDITIONS_12}
    trigger_counts: dict[str, int] = {condition_id: 0 for condition_id in EVAL_CONDITIONS_12}

    for profile_id, ml_record in ml_records.items():
        profile = profiles_by_id[profile_id]
        legacy_ml_scores = {
            EVAL_TO_BAYES[condition_id]: score
            for condition_id, score in ml_record["score_map"].items()
            if condition_id in EVAL_TO_BAYES
        }
        patient_sex = str(profile.get("demographics", {}).get("sex", "")).lower() or None
        result = handle_questions(
            {
                "ml_scores": legacy_ml_scores,
                "patient_sex": patient_sex,
                "existing_answers": profile.get("nhanes_inputs", {}),
            },
            updater,
        )

        per_profile_counts = {condition_id: 0 for condition_id in EVAL_CONDITIONS_12}
        for block in result.get("condition_questions", []):
            legacy_condition = block.get("condition")
            if not isinstance(legacy_condition, str):
                continue
            eval_condition = next(
                (condition_id for condition_id, bayes_id in EVAL_TO_BAYES.items() if bayes_id == legacy_condition),
                None,
            )
            if eval_condition not in per_profile_counts:
                continue
            q_count = len(block.get("questions", []))
            per_profile_counts[eval_condition] = q_count
            if q_count > 0:
                trigger_counts[eval_condition] += 1

        for condition_id, q_count in per_profile_counts.items():
            question_counts_by_condition[condition_id].append(q_count)

    recommendations: list[dict[str, Any]] = []
    n_profiles = len(ml_records)
    for condition_id in EVAL_CONDITIONS_12:
        ml_row = ml_summary[condition_id]
        default_row = default_summary[condition_id]
        full_row = full_summary[condition_id]
        question_counts = question_counts_by_condition[condition_id]
        triggered_questions = [count for count in question_counts if count > 0]

        lift_pp = (full_row["recall_at_3"] - default_row["recall_at_3"]) * 100
        fp_delta_pp = (full_row["absent_false_positive_rate_at_3"] - default_row["absent_false_positive_rate_at_3"]) * 100
        trigger_rate = trigger_counts[condition_id] / n_profiles if n_profiles else 0.0
        mean_q_profile = statistics.mean(question_counts) if question_counts else 0.0
        mean_q_triggered = statistics.mean(triggered_questions) if triggered_questions else 0.0
        recommendation = _recommend_class(
            lift_pp=lift_pp,
            fp_delta_pp=fp_delta_pp,
            mean_questions_when_triggered=mean_q_triggered,
            trigger_rate=trigger_rate,
        )
        recommendations.append(
            {
                "condition": condition_id,
                "ml_recall_at_3": ml_row["recall_at_3"],
                "default_recall_at_3": default_row["recall_at_3"],
                "full_recall_at_3": full_row["recall_at_3"],
                "full_minus_default_recall_at_3_pp": round(lift_pp, 1),
                "default_absent_fp_at_3": default_row["absent_false_positive_rate_at_3"],
                "full_absent_fp_at_3": full_row["absent_false_positive_rate_at_3"],
                "full_minus_default_absent_fp_at_3_pp": round(fp_delta_pp, 1),
                "default_trigger_rate": round(trigger_rate, 4),
                "mean_questions_per_profile": round(mean_q_profile, 2),
                "mean_questions_when_triggered": round(mean_q_triggered, 2),
                "recommendation": recommendation,
                "reason": _reason(
                    recommendation=recommendation,
                    lift_pp=lift_pp,
                    fp_delta_pp=fp_delta_pp,
                    mean_questions_when_triggered=mean_q_triggered,
                ),
            }
        )

    recommendations.sort(
        key=lambda row: (
            {"aggressive": 0, "moderate": 1, "topk_rescue_only": 2, "minimal": 3}[row["recommendation"]],
            -row["full_minus_default_recall_at_3_pp"],
        )
    )

    run_id = datetime.utcnow().strftime("bayes_trigger_optimization_%Y%m%d_%H%M%S")
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "source_compare_artifact": str(source_path),
        "profiles_path": str(PROFILES_PATH),
        "recommendations": recommendations,
    }

    results_path = RESULTS_DIR / f"{run_id}.json"
    report_path = REPORTS_DIR / f"{run_id}.md"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(build_markdown(run_id, source_path, payload), encoding="utf-8")

    print(f"Saved JSON results: {results_path}")
    print(f"Saved Markdown report: {report_path}")
    for row in recommendations:
        print(
            f"{row['condition']}: {row['recommendation']} "
            f"(lift={row['full_minus_default_recall_at_3_pp']:+.1f} pp, "
            f"trigger_rate={row['default_trigger_rate']:.1%}, "
            f"mean_q={row['mean_questions_when_triggered']:.2f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
