#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from compare_ml_vs_bayesian_update_only import (
    DEFAULT_PROFILES,
    REPORTS_DIR,
    RESULTS_DIR,
    _safe_git_sha,
    build_records,
    load_profiles,
    pct,
    score_arm_records,
)
from run_quiz_three_arm_eval import ModelRunner
from bayesian.bayesian_updater import BayesianUpdater
from scripts.roadmap_knn_scorer import RoadmapKNNScorer


SUPPORTED_CONDITIONS = [
    "anemia",
    "electrolyte_imbalance",
    "hepatitis",
    "hidden_inflammation",
    "hypothyroidism",
    "iron_deficiency",
    "kidney_disease",
    "liver",
    "perimenopause",
    "prediabetes",
    "sleep_disorder",
]
RESCUE_RANK_MAX = 6
RESCUE_MIN_KNN_SCORE = 0.06
RESCUE_MAX_GAP_TO_TOP3 = 0.18
BONUS_SCALE = 0.55
MAX_BONUS = 0.12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Condition-by-condition roadmap KNN rescue eval.")
    parser.add_argument("--profiles", type=Path, default=Path("evals/cohort/nhanes_balanced_800.json"))
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    return parser.parse_args()


def top3_from_scores(score_map: dict[str, float]) -> list[str]:
    return [condition_id for condition_id, _ in sorted(score_map.items(), key=lambda item: item[1], reverse=True)[:3]]


def apply_knn_rescue(
    base_scores: dict[str, float],
    knn_scores: dict[str, float],
    allowed_conditions: set[str],
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    ranked = sorted(base_scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return {}, {}
    top1_condition = ranked[0][0]
    top3_cutoff = ranked[min(2, len(ranked) - 1)][1]

    adjusted = dict(base_scores)
    applied: dict[str, dict[str, Any]] = {}
    for rank, (condition, score) in enumerate(ranked, start=1):
        if condition == top1_condition:
            continue
        if condition not in allowed_conditions:
            continue
        if rank > RESCUE_RANK_MAX:
            continue

        knn_score = float(knn_scores.get(condition, 0.0))
        gap = top3_cutoff - score
        if knn_score < RESCUE_MIN_KNN_SCORE:
            continue
        if gap > RESCUE_MAX_GAP_TO_TOP3:
            continue

        bonus = min(MAX_BONUS, knn_score * BONUS_SCALE)
        if bonus <= 0:
            continue
        adjusted[condition] = round(min(0.99, score + bonus), 4)
        applied[condition] = {
            "rank_before": rank,
            "base_score": round(score, 4),
            "knn_score": round(knn_score, 4),
            "gap_to_top3": round(gap, 4),
            "bonus": round(bonus, 4),
            "adjusted_score": adjusted[condition],
        }

    # Freeze top1 explicitly.
    top1_score = adjusted[top1_condition]
    for condition, score in list(adjusted.items()):
        if condition != top1_condition and score > top1_score:
            adjusted[condition] = round(min(score, top1_score - 0.0001), 4)
    return adjusted, applied


def build_arm_records(
    default_records: list[dict[str, Any]],
    knn_scores_by_profile: dict[str, dict[str, float]],
    allowed_conditions: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    promoted = 0
    improved_primary = 0
    for record in default_records:
        knn_scores = knn_scores_by_profile.get(record["profile_id"], {})
        adjusted_scores, applied = apply_knn_rescue(record["score_map"], knn_scores, allowed_conditions)
        top3 = top3_from_scores(adjusted_scores)
        if set(top3) != set(record["top3_predictions"]):
            promoted += 1
        gt_primary = record.get("ground_truth_primary")
        if gt_primary and gt_primary in top3 and gt_primary not in record["top3_predictions"]:
            improved_primary += 1
        records.append({
            **record,
            "score_map": adjusted_scores,
            "top1_prediction": top3[0] if top3 else None,
            "top3_predictions": top3,
            "knn_rescue_applied": applied,
        })
    return records, {"profiles_with_top3_change": promoted, "primary_rescues": improved_primary}


def build_markdown(
    run_id: str,
    profiles_path: Path,
    summary: dict[str, Any],
) -> str:
    default = summary["arms"]["default_ml_bayes"]
    all_supported = summary["arms"]["roadmap_knn_all_supported"]
    lines: list[str] = []
    lines.append(f"# Roadmap KNN Condition Rescue Eval — {run_id}")
    lines.append("")
    lines.append(f"- Cohort: `{profiles_path}`")
    lines.append(f"- Profiles evaluated: `{default['n_profiles']}`")
    lines.append("- KNN policy: `top-1 frozen`, `rank 2-6 only`, `small rescue bonus`")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Metric | Default ML+Bayes | + KNN all supported | Delta |")
    lines.append("|--------|------------------|---------------------|-------|")
    for metric_id, label in (
        ("top3_contains_any_true_condition", "Top-3 contains any true condition"),
        ("top1_primary_accuracy", "Top-1 primary accuracy"),
        ("top3_primary_coverage", "Top-3 primary coverage"),
        ("healthy_over_alert_rate", "Healthy over-alert rate"),
    ):
        before = default[metric_id]
        after = all_supported[metric_id]
        lines.append(f"| {label} | {pct(before)} | {pct(after)} | {(after - before) * 100:+.1f} pp |")
    lines.append("")
    lines.append("## Condition Arms")
    lines.append("")
    lines.append("| Condition | Top-3 any true | Delta | Top-1 primary | Delta | Healthy over-alert | Delta |")
    lines.append("|-----------|----------------|-------|---------------|-------|--------------------|-------|")
    for condition in SUPPORTED_CONDITIONS:
        arm = summary["arms"][f"roadmap_knn_{condition}"]
        lines.append(
            f"| {condition} | {pct(arm['top3_contains_any_true_condition'])} | "
            f"{(arm['top3_contains_any_true_condition'] - default['top3_contains_any_true_condition']) * 100:+.1f} pp | "
            f"{pct(arm['top1_primary_accuracy'])} | "
            f"{(arm['top1_primary_accuracy'] - default['top1_primary_accuracy']) * 100:+.1f} pp | "
            f"{pct(arm['healthy_over_alert_rate'])} | "
            f"{(arm['healthy_over_alert_rate'] - default['healthy_over_alert_rate']) * 100:+.1f} pp |"
        )
    lines.append("")
    lines.append("## Rescue Counts")
    lines.append("")
    for arm_name, debug in summary["debug"].items():
        lines.append(f"- `{arm_name}`: top-3 changed on `{debug['profiles_with_top3_change']}` profiles; primary rescues `{debug['primary_rescues']}`")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles(args.profiles)
    runner = ModelRunner(max_workers=1)
    updater = BayesianUpdater()
    knn = RoadmapKNNScorer()

    _, _, default_records = build_records(profiles, runner, updater)

    knn_scores_by_profile: dict[str, dict[str, float]] = {}
    for profile in profiles:
        result = knn.score(profile.get("nhanes_inputs", {}))
        knn_scores_by_profile[profile["profile_id"]] = {
            row["condition"]: float(row["weighted_neighbor_fraction"])
            for row in result.get("disease_scores", [])
        }

    arms: dict[str, Any] = {
        "default_ml_bayes": score_arm_records(default_records),
    }
    debug: dict[str, Any] = {}

    all_records, all_debug = build_arm_records(default_records, knn_scores_by_profile, set(SUPPORTED_CONDITIONS))
    arms["roadmap_knn_all_supported"] = score_arm_records(all_records)
    debug["roadmap_knn_all_supported"] = all_debug

    for condition in SUPPORTED_CONDITIONS:
        records, arm_debug = build_arm_records(default_records, knn_scores_by_profile, {condition})
        arms[f"roadmap_knn_{condition}"] = score_arm_records(records)
        debug[f"roadmap_knn_{condition}"] = arm_debug

    run_id = datetime.utcnow().strftime("roadmap_knn_condition_rescue_%Y%m%d_%H%M%S")
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "profiles_path": str(args.profiles),
        "policy": {
            "supported_conditions": SUPPORTED_CONDITIONS,
            "rescue_rank_max": RESCUE_RANK_MAX,
            "rescue_min_knn_score": RESCUE_MIN_KNN_SCORE,
            "rescue_max_gap_to_top3": RESCUE_MAX_GAP_TO_TOP3,
            "bonus_scale": BONUS_SCALE,
            "max_bonus": MAX_BONUS,
            "top1_frozen": True,
        },
        "arms": arms,
        "debug": debug,
    }

    results_path = args.output_dir / f"{run_id}.json"
    report_path = args.reports_dir / f"{run_id}.md"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(build_markdown(run_id, args.profiles, payload), encoding="utf-8")

    print(f"Saved JSON results: {results_path}")
    print(f"Saved Markdown report: {report_path}")
    print(f"Default ML+Bayes top3_any_true: {payload['arms']['default_ml_bayes']['top3_contains_any_true_condition']:.1%}")
    print(f"+ Roadmap KNN all-supported top3_any_true: {payload['arms']['roadmap_knn_all_supported']['top3_contains_any_true_condition']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
