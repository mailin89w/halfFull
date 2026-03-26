#!/usr/bin/env python3
"""
run_layered_knn_report.py

Generate a detailed layered evaluation report for:
  1. ML models only
  2. ML + Bayesian
  3. ML + Bayesian + KNN

All layers are evaluated on the exact same synthetic users, using explicit
expected lab groups from the hand-authored KNN-focused cohorts.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore")
logging.getLogger("model_runner").setLevel(logging.WARNING)
logging.getLogger("bayesian").setLevel(logging.WARNING)
logging.getLogger("bayesian_updater").setLevel(logging.WARNING)

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.run_bayesian import handle_questions, handle_update
from evals.run_bayesian_eval import simulated_bayesian_answer
from evals.run_knn_layer_eval import (
    CONDITION_TO_LAB_GROUPS,
    KNN_LAB_GROUPS,
    abnormal_lab_groups,
    build_eval_inputs,
)
from evals.run_layer1_eval import ModelRunner
from scripts.knn_scorer import KNNScorer
from scripts.score_answers import _patient_context, _remap_scores

COHORT_PATHS = [
    EVALS_DIR / "cohort" / "knn_overlap_pack.json",
    EVALS_DIR / "cohort" / "knn_liver_pack.json",
]
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def top_k_conditions(scores: dict[str, float], k: int = 3) -> list[str]:
    return [cond for cond, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]]


def layer_groups_from_conditions(conditions: list[str]) -> set[str]:
    groups: set[str] = set()
    for cond in conditions:
        groups.update(CONDITION_TO_LAB_GROUPS.get(cond, set()))
    return groups


def knn_groups(raw_inputs: dict[str, Any], scorer: KNNScorer, max_groups: int | None = None) -> set[str]:
    result = scorer.score(raw_inputs)
    ordered_groups: list[str] = []
    seen = set()
    for sig in result.get("lab_signals", []):
        group = KNN_LAB_GROUPS.get(sig.get("lab"))
        if not group or group in seen:
            continue
        seen.add(group)
        ordered_groups.append(group)
        if max_groups is not None and len(ordered_groups) >= max_groups:
            break
    return set(ordered_groups)


def ml_legacy_scores(profile: dict[str, Any], runner: ModelRunner) -> tuple[dict[str, float], dict[str, Any]]:
    raw_inputs = build_eval_inputs(profile)
    feature_vectors = runner._get_normalizer().build_feature_vectors(raw_inputs)
    raw_scores = runner.run_all_with_context(feature_vectors, patient_context=_patient_context(raw_inputs))
    return _remap_scores(raw_scores), raw_inputs


def bayesian_posteriors(
    profile: dict[str, Any],
    ml_scores: dict[str, float],
    raw_inputs: dict[str, Any],
    updater: BayesianUpdater,
) -> dict[str, float]:
    patient_sex = "female" if raw_inputs.get("gender") == 2 else "male" if raw_inputs.get("gender") == 1 else None

    questions_result = handle_questions(
        {
            "ml_scores": ml_scores,
            "patient_sex": patient_sex,
            "existing_answers": raw_inputs,
        },
        updater,
    )

    answers_by_condition: dict[str, dict[str, str]] = {}
    for group in questions_result.get("condition_questions", []):
        condition = group["condition"]
        for question in group.get("questions", []):
            qid = question["id"]
            answers_by_condition.setdefault(condition, {})[qid] = simulated_bayesian_answer(profile, condition, qid)

    update_result = handle_update(
        {
            "ml_scores": ml_scores,
            "confounder_answers": {},
            "answers_by_condition": answers_by_condition,
            "patient_sex": patient_sex,
            "existing_answers": raw_inputs,
        },
        updater,
    )
    return update_result["posterior_scores"]


def metric_row(pred_groups: set[str], gt_groups: set[str]) -> dict[str, float | bool]:
    intersection = pred_groups & gt_groups
    return {
        "hit": bool(intersection),
        "exact": gt_groups.issubset(pred_groups),
        "recall": safe_div(len(intersection), len(gt_groups)),
        "precision": safe_div(len(intersection), len(pred_groups)),
    }


def aggregate_layer(rows: list[dict[str, Any]], layer_key: str) -> dict[str, Any]:
    hits = sum(1 for row in rows if row[layer_key]["hit"])
    exact = sum(1 for row in rows if row[layer_key]["exact"])
    recalls = [row[layer_key]["recall"] for row in rows]
    precisions = [row[layer_key]["precision"] for row in rows]
    return {
        "hit_rate": round(safe_div(hits, len(rows)), 4),
        "exact_coverage": round(safe_div(exact, len(rows)), 4),
        "mean_recall": round(mean(recalls), 4),
        "mean_precision": round(mean(precisions), 4),
    }


def aggregate_condition_metric(rows: list[dict[str, Any]], score_key: str, topk: int, condition_key: str) -> dict[str, Any]:
    subset = [row for row in rows if row["primary_condition"] == condition_key]
    if not subset:
        return {}
    top1 = sum(1 for row in subset if row[score_key]["top_conditions"][:1] and row[score_key]["top_conditions"][0] == condition_key)
    topk_hits = sum(1 for row in subset if condition_key in row[score_key]["top_conditions"][:topk])
    return {
        "n": len(subset),
        "top1_accuracy": round(safe_div(top1, len(subset)), 4),
        "top3_coverage": round(safe_div(topk_hits, len(subset)), 4),
    }


def aggregate_lab_metric(rows: list[dict[str, Any]], layer_key: str, condition_key: str) -> dict[str, Any]:
    subset = [row for row in rows if row["primary_condition"] == condition_key]
    if not subset:
        return {}
    hits = sum(1 for row in subset if row[layer_key]["hit"])
    exact = sum(1 for row in subset if row[layer_key]["exact"])
    recalls = [row[layer_key]["recall"] for row in subset]
    precisions = [row[layer_key]["precision"] for row in subset]
    return {
        "n": len(subset),
        "hit_rate": round(safe_div(hits, len(subset)), 4),
        "exact_coverage": round(safe_div(exact, len(subset)), 4),
        "mean_recall": round(mean(recalls), 4),
        "mean_precision": round(mean(precisions), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate layered ML/Bayesian/KNN report")
    parser.add_argument("--knn-max-groups", type=int, default=0, help="Cap KNN contribution to top N unique lab groups; 0 = no cap")
    args = parser.parse_args()

    profiles: list[dict[str, Any]] = []
    for path in COHORT_PATHS:
        profiles.extend(json.loads(path.read_text()))

    runner = ModelRunner()
    updater = BayesianUpdater()
    scorer = KNNScorer()

    rows: list[dict[str, Any]] = []
    for profile in profiles:
        gt_groups = abnormal_lab_groups(profile)
        primary_condition = profile["ground_truth"]["expected_conditions"][0]["condition_id"]

        ml_scores, raw_inputs = ml_legacy_scores(profile, runner)
        ml_top = top_k_conditions(ml_scores, 3)
        ml_groups = layer_groups_from_conditions(ml_top)

        bayes_scores = bayesian_posteriors(profile, ml_scores, raw_inputs, updater)
        bayes_top = top_k_conditions(bayes_scores, 3)
        bayes_groups = layer_groups_from_conditions(bayes_top)

        knn_only_groups = knn_groups(raw_inputs, scorer, max_groups=(args.knn_max_groups or None))
        full_groups = bayes_groups | knn_only_groups

        rows.append({
            "profile_id": profile["profile_id"],
            "profile_type": profile["profile_type"],
            "primary_condition": primary_condition,
            "expected_conditions": [item["condition_id"] for item in profile["ground_truth"]["expected_conditions"]],
            "ground_truth_groups": sorted(gt_groups),
            "ml": {
                "top_conditions": ml_top,
                "groups": sorted(ml_groups),
                **metric_row(ml_groups, gt_groups),
            },
            "bayes": {
                "top_conditions": bayes_top,
                "groups": sorted(bayes_groups),
                **metric_row(bayes_groups, gt_groups),
            },
            "full": {
                "top_conditions": bayes_top,
                "groups": sorted(full_groups),
                "knn_groups": sorted(knn_only_groups),
                **metric_row(full_groups, gt_groups),
            },
        })

    summary = {
        "n_profiles": len(rows),
        "ml_only": aggregate_layer(rows, "ml"),
        "ml_plus_bayesian": aggregate_layer(rows, "bayes"),
        "ml_plus_bayesian_plus_knn": aggregate_layer(rows, "full"),
    }
    summary["bayesian_gain_over_ml"] = {
        metric: round(summary["ml_plus_bayesian"][metric] - summary["ml_only"][metric], 4)
        for metric in summary["ml_only"]
    }
    summary["knn_gain_over_ml_plus_bayesian"] = {
        metric: round(summary["ml_plus_bayesian_plus_knn"][metric] - summary["ml_plus_bayesian"][metric], 4)
        for metric in summary["ml_only"]
    }
    summary["total_gain_over_ml"] = {
        metric: round(summary["ml_plus_bayesian_plus_knn"][metric] - summary["ml_only"][metric], 4)
        for metric in summary["ml_only"]
    }

    condition_keys = sorted({row["primary_condition"] for row in rows})
    per_condition = {}
    for condition in condition_keys:
        per_condition[condition] = {
            "condition_routing_ml": aggregate_condition_metric(rows, "ml", 3, condition),
            "condition_routing_bayesian": aggregate_condition_metric(rows, "bayes", 3, condition),
            "lab_coverage_ml": aggregate_lab_metric(rows, "ml", condition),
            "lab_coverage_bayesian": aggregate_lab_metric(rows, "bayes", condition),
            "lab_coverage_full": aggregate_lab_metric(rows, "full", condition),
        }

    improved_by_knn = [
        row for row in rows
        if row["full"]["recall"] > row["bayes"]["recall"]
    ]
    unchanged_after_knn = [
        row for row in rows
        if row["full"]["recall"] <= row["bayes"]["recall"]
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"cap{args.knn_max_groups}" if args.knn_max_groups else "capnone"
    results_path = RESULTS_DIR / f"layered_knn_report_{suffix}_{timestamp}.json"
    report_path = REPORTS_DIR / f"layered_knn_report_{suffix}_{timestamp}.md"

    payload = {
        "cohort_paths": [str(path) for path in COHORT_PATHS],
        "knn_max_groups": args.knn_max_groups,
        "summary": summary,
        "per_condition": per_condition,
        "rows": rows,
        "improved_by_knn": improved_by_knn,
        "unchanged_after_knn": unchanged_after_knn,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(payload, indent=2))

    lines: list[str] = []
    lines.append("# Layered KNN Evaluation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Cohort")
    lines.append("")
    lines.append(f"- Profiles evaluated: `{len(rows)}`")
    lines.append(f"- KNN group cap: `{args.knn_max_groups if args.knn_max_groups else 'none'}`")
    for path in COHORT_PATHS:
        lines.append(f"- Source: `{path}`")
    lines.append("")
    lines.append("## Overall Lab Coverage")
    lines.append("")
    lines.append("| Layer | Hit Rate | Exact Coverage | Mean Recall | Mean Precision |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| ML only | {summary['ml_only']['hit_rate']:.1%} | {summary['ml_only']['exact_coverage']:.1%} | {summary['ml_only']['mean_recall']:.1%} | {summary['ml_only']['mean_precision']:.1%} |"
    )
    lines.append(
        f"| ML + Bayesian | {summary['ml_plus_bayesian']['hit_rate']:.1%} | {summary['ml_plus_bayesian']['exact_coverage']:.1%} | {summary['ml_plus_bayesian']['mean_recall']:.1%} | {summary['ml_plus_bayesian']['mean_precision']:.1%} |"
    )
    lines.append(
        f"| ML + Bayesian + KNN | {summary['ml_plus_bayesian_plus_knn']['hit_rate']:.1%} | {summary['ml_plus_bayesian_plus_knn']['exact_coverage']:.1%} | {summary['ml_plus_bayesian_plus_knn']['mean_recall']:.1%} | {summary['ml_plus_bayesian_plus_knn']['mean_precision']:.1%} |"
    )
    lines.append("")
    lines.append("## Incremental Gain")
    lines.append("")
    lines.append("| Delta | Hit Rate | Exact Coverage | Mean Recall | Mean Precision |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| Bayesian over ML | {summary['bayesian_gain_over_ml']['hit_rate']:+.1%} | {summary['bayesian_gain_over_ml']['exact_coverage']:+.1%} | {summary['bayesian_gain_over_ml']['mean_recall']:+.1%} | {summary['bayesian_gain_over_ml']['mean_precision']:+.1%} |"
    )
    lines.append(
        f"| KNN over ML+Bayesian | {summary['knn_gain_over_ml_plus_bayesian']['hit_rate']:+.1%} | {summary['knn_gain_over_ml_plus_bayesian']['exact_coverage']:+.1%} | {summary['knn_gain_over_ml_plus_bayesian']['mean_recall']:+.1%} | {summary['knn_gain_over_ml_plus_bayesian']['mean_precision']:+.1%} |"
    )
    lines.append(
        f"| Total gain over ML | {summary['total_gain_over_ml']['hit_rate']:+.1%} | {summary['total_gain_over_ml']['exact_coverage']:+.1%} | {summary['total_gain_over_ml']['mean_recall']:+.1%} | {summary['total_gain_over_ml']['mean_precision']:+.1%} |"
    )
    lines.append("")
    lines.append("## Per Condition")
    lines.append("")
    lines.append("| Condition | N | ML Top-1 | Bayesian Top-1 | ML Lab Hit | Bayes Lab Hit | Full Lab Hit | Full Exact |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for condition in condition_keys:
        cond = per_condition[condition]
        ml_route = cond["condition_routing_ml"]
        bayes_route = cond["condition_routing_bayesian"]
        ml_lab = cond["lab_coverage_ml"]
        bayes_lab = cond["lab_coverage_bayesian"]
        full_lab = cond["lab_coverage_full"]
        lines.append(
            f"| {condition} | {full_lab.get('n', 0)} | {ml_route.get('top1_accuracy', 0.0):.1%} | {bayes_route.get('top1_accuracy', 0.0):.1%} | {ml_lab.get('hit_rate', 0.0):.1%} | {bayes_lab.get('hit_rate', 0.0):.1%} | {full_lab.get('hit_rate', 0.0):.1%} | {full_lab.get('exact_coverage', 0.0):.1%} |"
        )
    lines.append("")
    lines.append("## KNN Wins")
    lines.append("")
    lines.append(f"- Profiles improved by KNN over ML+Bayesian: `{len(improved_by_knn)}/{len(rows)}`")
    for row in improved_by_knn[:10]:
        lines.append(
            f"- `{row['profile_id']}` ({row['primary_condition']}): Bayes groups `{row['bayes']['groups']}` -> Full groups `{row['full']['groups']}` vs truth `{row['ground_truth_groups']}`"
        )
    lines.append("")
    lines.append("## Cases Unchanged After KNN")
    lines.append("")
    for row in unchanged_after_knn[:10]:
        lines.append(
            f"- `{row['profile_id']}` ({row['primary_condition']}): Bayes groups `{row['bayes']['groups']}`, KNN added `{row['full']['knn_groups']}`, truth `{row['ground_truth_groups']}`"
        )

    report_path.write_text("\n".join(lines) + "\n")

    print(f"Saved JSON to {results_path}")
    print(f"Saved report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
