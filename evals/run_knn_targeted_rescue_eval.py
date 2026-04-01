#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from compare_ml_vs_bayesian_update_only import (
    BAYES_TO_EVAL,
    DEFAULT_PROFILES,
    EVAL_TO_BAYES,
    REPORTS_DIR,
    RESULTS_DIR,
    _safe_git_sha,
    build_records,
    load_profiles,
    pct,
    score_arm_records,
)
from evals.pipeline import knn_condition_reranker as knn_reranker
from run_quiz_three_arm_eval import ModelRunner
from bayesian.bayesian_updater import BayesianUpdater
from run_layer1_eval import _build_raw_inputs_from_nhanes
from scripts.knn_scorer import KNNScorer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate targeted KNN rescue on top of default ML+Bayes.")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES, help="Cohort JSON path.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="JSON output directory.")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help="Markdown output directory.")
    return parser.parse_args()


def top3_from_scores(score_map: dict[str, float]) -> list[str]:
    return [condition_id for condition_id, _ in sorted(score_map.items(), key=lambda item: item[1], reverse=True)[:3]]


def knn_groups_for_profile(profile: dict[str, Any], scorer: KNNScorer) -> set[str]:
    raw_inputs = _build_raw_inputs_from_nhanes(profile)
    result = scorer.score(raw_inputs)
    groups = set()
    for signal in result.get("lab_signals", []):
        lab = signal.get("lab")
        if lab in {"Creatinine", "BUN (blood urea nitrogen)", "Albumin", "Bicarbonate"}:
            groups.add("kidney")
    return groups


@contextmanager
def targeted_kidney_rescue_config():
    original_group_bonuses = dict(knn_reranker.GROUP_BONUSES)
    original_pair_bonuses = dict(knn_reranker.COMORBIDITY_PAIR_BONUSES)
    original_penalties = dict(knn_reranker.UNSUPPORTED_PENALTIES)
    try:
        knn_reranker.GROUP_BONUSES = {
            "kidney": {"kidney": 0.08},
            "liver": {},
            "hepatitis": {},
            "inflammation": {},
            "prediabetes": {},
            "thyroid": {},
            "iron_deficiency": {},
            "anemia": {},
            "electrolytes": {},
            "sleep_disorder": {},
            "perimenopause": {},
        }
        knn_reranker.COMORBIDITY_PAIR_BONUSES = {}
        knn_reranker.UNSUPPORTED_PENALTIES = {}
        yield
    finally:
        knn_reranker.GROUP_BONUSES = original_group_bonuses
        knn_reranker.COMORBIDITY_PAIR_BONUSES = original_pair_bonuses
        knn_reranker.UNSUPPORTED_PENALTIES = original_penalties


def build_targeted_knn_records(
    profiles: list[dict[str, Any]],
    default_records: list[dict[str, Any]],
    scorer: KNNScorer,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    promoted_kidney = 0
    top1_changed = 0

    with targeted_kidney_rescue_config():
        for profile, default in zip(profiles, default_records, strict=True):
            groups = knn_groups_for_profile(profile, scorer)
            legacy_scores = {
                EVAL_TO_BAYES.get(condition_id, condition_id): score
                for condition_id, score in default["score_map"].items()
            }
            reranked = knn_reranker.rerank_condition_scores_with_knn(
                legacy_scores,
                groups,
                min_prior=0.20,
                max_bonus=0.10,
                max_candidate_rank=6,
                max_distance_from_top3=0.18,
                freeze_top1=True,
                top1_confidence_threshold=0.0,
                top_n=3,
            )
            adjusted_eval_scores = {
                BAYES_TO_EVAL.get(condition_id, condition_id): score
                for condition_id, score in reranked["adjusted_scores"].items()
            }
            top3_predictions = [
                BAYES_TO_EVAL.get(condition_id, condition_id)
                for condition_id in reranked["top_conditions"]
            ]
            if default["top1_prediction"] != (top3_predictions[0] if top3_predictions else None):
                top1_changed += 1
            if "kidney_disease" in default.get("expected_conditions", []):
                if "kidney_disease" in top3_predictions and "kidney_disease" not in default["top3_predictions"]:
                    promoted_kidney += 1

            records.append({
                **default,
                "score_map": adjusted_eval_scores,
                "top1_prediction": top3_predictions[0] if top3_predictions else None,
                "top3_predictions": top3_predictions,
                "knn_groups": sorted(groups),
                "knn_bonuses": reranked["bonuses"],
                "knn_penalties": reranked["penalties"],
            })

    debug = {
        "promoted_kidney_profiles": promoted_kidney,
        "top1_changed_profiles": top1_changed,
    }
    return records, debug


def build_markdown(
    run_id: str,
    profiles_path: Path,
    default_summary: dict[str, Any],
    targeted_summary: dict[str, Any],
    debug: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# Targeted KNN Rescue Eval — {run_id}")
    lines.append("")
    lines.append(f"- Cohort: `{profiles_path}`")
    lines.append(f"- Profiles evaluated: `{default_summary['n_profiles']}`")
    lines.append("- KNN mode: `kidney-only rescue`, `top-1 frozen`, `slot-2/3 only`")
    lines.append("")
    lines.append("## Headline Metrics")
    lines.append("")
    lines.append("| Metric | Default ML+Bayes | + Targeted KNN rescue | Delta |")
    lines.append("|--------|------------------|-----------------------|-------|")
    for metric_id, label in (
        ("top3_contains_any_true_condition", "Top-3 contains any true condition"),
        ("top1_primary_accuracy", "Top-1 primary accuracy"),
        ("top3_primary_coverage", "Top-3 primary coverage"),
        ("healthy_over_alert_rate", "Healthy over-alert rate"),
    ):
        before = default_summary[metric_id]
        after = targeted_summary[metric_id]
        lines.append(f"| {label} | {pct(before)} | {pct(after)} | {(after - before) * 100:+.1f} pp |")
    lines.append("")
    lines.append("## KNN Checks")
    lines.append("")
    lines.append(f"- Kidney rescued into top-3 on `{debug['promoted_kidney_profiles']}` profiles")
    lines.append(f"- Top-1 changed profiles: `{debug['top1_changed_profiles']}`")
    lines.append("")
    lines.append("## Kidney Focus")
    lines.append("")
    lines.append("| Metric | Default ML+Bayes | + Targeted KNN rescue | Delta |")
    lines.append("|--------|------------------|-----------------------|-------|")
    default_kidney = default_summary["per_condition"]["kidney_disease"]
    targeted_kidney = targeted_summary["per_condition"]["kidney_disease"]
    for key, label in (
        ("recall_at_3", "Kidney recall@3"),
        ("absent_false_positive_rate_at_3", "Kidney absent FP@3"),
        ("healthy_flag_rate", "Kidney healthy flag rate"),
    ):
        before = default_kidney[key]
        after = targeted_kidney[key]
        delta = "-" if before is None or after is None else f"{(after - before) * 100:+.1f} pp"
        lines.append(f"| {label} | {pct(before)} | {pct(after)} | {delta} |")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles(args.profiles)
    runner = ModelRunner(max_workers=1)
    updater = BayesianUpdater()
    scorer = KNNScorer()

    _, _, default_records = build_records(profiles, runner, updater)
    targeted_records, debug = build_targeted_knn_records(profiles, default_records, scorer)

    run_id = datetime.utcnow().strftime("knn_targeted_rescue_%Y%m%d_%H%M%S")
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "profiles_path": str(args.profiles),
        "arms": {
            "default_ml_bayes": score_arm_records(default_records),
            "default_ml_bayes_plus_targeted_knn": score_arm_records(targeted_records),
        },
        "debug": debug,
        "records_by_arm": {
            "default_ml_bayes": default_records,
            "default_ml_bayes_plus_targeted_knn": targeted_records,
        },
    }

    results_path = args.output_dir / f"{run_id}.json"
    report_path = args.reports_dir / f"{run_id}.md"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(
        build_markdown(
            run_id,
            args.profiles,
            payload["arms"]["default_ml_bayes"],
            payload["arms"]["default_ml_bayes_plus_targeted_knn"],
            payload["debug"],
        ),
        encoding="utf-8",
    )

    print(f"Saved JSON results: {results_path}")
    print(f"Saved Markdown report: {report_path}")
    print(f"Default ML+Bayes top3_any_true: {payload['arms']['default_ml_bayes']['top3_contains_any_true_condition']:.1%}")
    print(f"+ Targeted KNN rescue top3_any_true: {payload['arms']['default_ml_bayes_plus_targeted_knn']['top3_contains_any_true_condition']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
