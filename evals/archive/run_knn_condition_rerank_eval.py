#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import random
import sys
import warnings
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
from evals.pipeline.knn_condition_reranker import rerank_condition_scores_with_knn
from evals.pipeline.profile_loader import ProfileLoader
from evals.run_bayesian_eval import simulated_bayesian_answer
from evals.run_knn_layer_eval import KNN_LAB_GROUPS, build_eval_inputs
from evals.run_layer1_eval import CONDITION_TO_MODEL_KEY, ModelRunner, SCHEMA_PATH
from models_normalized.model_runner import USER_FACING_THRESHOLDS
from scripts.knn_scorer import KNNScorer
from scripts.score_answers import _patient_context, _remap_scores

PROFILES_PATH = EVALS_DIR / "cohort" / "profiles_v3_three_layer.json"
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"

EVAL_TO_LEGACY = {
    "anemia": "anemia",
    "electrolyte_imbalance": "electrolytes",
    "hepatitis": "hepatitis",
    "hypothyroidism": "thyroid",
    "inflammation": "inflammation",
    "iron_deficiency": "iron_deficiency",
    "kidney_disease": "kidney",
    "liver": "liver",
    "perimenopause": "perimenopause",
    "prediabetes": "prediabetes",
    "sleep_disorder": "sleep_disorder",
}


def knn_groups(raw_inputs: dict[str, Any], scorer: KNNScorer) -> set[str]:
    result = scorer.score(raw_inputs)
    groups = set()
    for sig in result.get("lab_signals", []):
        group = KNN_LAB_GROUPS.get(sig.get("lab"))
        if group:
            groups.add(group)
    return groups


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


def surfaced_conditions(scores: dict[str, float], ranked_top3: list[str]) -> list[str]:
    surfaced: list[str] = []
    for cond in ranked_top3:
        threshold = USER_FACING_THRESHOLDS.get(cond)
        if threshold is None:
            continue
        if scores.get(cond, 0.0) >= threshold:
            surfaced.append(cond)
    return surfaced


def main() -> int:
    loader = ProfileLoader(PROFILES_PATH, SCHEMA_PATH)
    profiles = loader.load_all()
    rng = random.Random(42)
    profiles = rng.sample(profiles, 600)

    runner = ModelRunner()
    updater = BayesianUpdater()
    scorer = KNNScorer()

    rows: list[dict[str, Any]] = []
    for profile in profiles:
        raw_inputs = build_eval_inputs(profile)
        feature_vectors = runner._get_normalizer().build_feature_vectors(raw_inputs)
        raw_scores = runner.run_all_with_context(feature_vectors, patient_context=_patient_context(raw_inputs))
        ml_scores = _remap_scores(raw_scores)
        bayes_scores = bayesian_posteriors(profile, ml_scores, raw_inputs, updater)
        bayes_top3 = [cond for cond, _ in sorted(bayes_scores.items(), key=lambda item: item[1], reverse=True)[:3]]

        groups = knn_groups(raw_inputs, scorer)
        reranked = rerank_condition_scores_with_knn(bayes_scores, groups)
        knn_top3 = reranked["top_conditions"]

        expected_eval = [item["condition_id"] for item in profile.get("ground_truth", {}).get("expected_conditions", [])]
        expected_legacy = [EVAL_TO_LEGACY[c] for c in expected_eval if c in EVAL_TO_LEGACY]
        primary_legacy = expected_legacy[0] if expected_legacy else None
        secondary_legacy = expected_legacy[1:]

        bayes_surfaced = surfaced_conditions(bayes_scores, bayes_top3)
        knn_surfaced = surfaced_conditions(reranked["adjusted_scores"], knn_top3)

        rows.append({
            "profile_id": profile["profile_id"],
            "profile_type": profile["profile_type"],
            "expected_eval": expected_eval,
            "expected_legacy": expected_legacy,
            "primary_legacy": primary_legacy,
            "secondary_legacy": secondary_legacy,
            "bayes_top3": bayes_top3,
            "knn_top3": knn_top3,
            "bayes_surfaced": bayes_surfaced,
            "knn_surfaced": knn_surfaced,
            "knn_groups": sorted(groups),
            "bonuses": reranked["bonuses"],
        })

    labeled = [r for r in rows if r["primary_legacy"]]
    multi = [r for r in labeled if r["secondary_legacy"]]
    healthy = [r for r in rows if r["profile_type"] == "healthy"]

    bayes_top3_hit = mean(1.0 if r["primary_legacy"] in r["bayes_top3"] else 0.0 for r in labeled)
    knn_top3_hit = mean(1.0 if r["primary_legacy"] in r["knn_top3"] else 0.0 for r in labeled)

    bayes_secondary_hit = mean(1.0 if any(c in r["bayes_top3"] for c in r["secondary_legacy"]) else 0.0 for r in multi) if multi else 0.0
    knn_secondary_hit = mean(1.0 if any(c in r["knn_top3"] for c in r["secondary_legacy"]) else 0.0 for r in multi) if multi else 0.0

    bayes_over_alert = mean(1.0 if r["bayes_surfaced"] else 0.0 for r in healthy) if healthy else 0.0
    knn_over_alert = mean(1.0 if r["knn_surfaced"] else 0.0 for r in healthy) if healthy else 0.0

    added_conditions = []
    removed_conditions = []
    top1_changed = 0
    profiles_improved = []
    for r in labeled:
        bayes_set = set(r["bayes_top3"])
        knn_set = set(r["knn_top3"])
        added = sorted(knn_set - bayes_set)
        removed = sorted(bayes_set - knn_set)
        if r["bayes_top3"][:1] != r["knn_top3"][:1]:
            top1_changed += 1
        for cond in added:
            added_conditions.append({"condition": cond, "is_ground_truth": cond in r["expected_legacy"], "profile_id": r["profile_id"]})
        for cond in removed:
            removed_conditions.append({"condition": cond, "is_ground_truth": cond in r["expected_legacy"], "profile_id": r["profile_id"]})
        if (r["primary_legacy"] in r["knn_top3"]) and (r["primary_legacy"] not in r["bayes_top3"]):
            profiles_improved.append(r)

    added_precision = (sum(1 for x in added_conditions if x["is_ground_truth"]) / len(added_conditions)) if added_conditions else 0.0
    removed_precision = (sum(1 for x in removed_conditions if x["is_ground_truth"]) / len(removed_conditions)) if removed_conditions else 0.0

    summary = {
        "n_profiles": len(rows),
        "n_labeled": len(labeled),
        "n_multi_condition": len(multi),
        "n_healthy": len(healthy),
        "top3_condition_hit_rate_bayesian": round(bayes_top3_hit, 4),
        "top3_condition_hit_rate_bayes_plus_knn": round(knn_top3_hit, 4),
        "delta_top3_condition_hit_rate": round(knn_top3_hit - bayes_top3_hit, 4),
        "secondary_condition_recovery_bayesian": round(bayes_secondary_hit, 4),
        "secondary_condition_recovery_bayes_plus_knn": round(knn_secondary_hit, 4),
        "delta_secondary_condition_recovery": round(knn_secondary_hit - bayes_secondary_hit, 4),
        "healthy_over_alert_bayesian": round(bayes_over_alert, 4),
        "healthy_over_alert_bayes_plus_knn": round(knn_over_alert, 4),
        "delta_healthy_over_alert": round(knn_over_alert - bayes_over_alert, 4),
        "added_conditions_count": len(added_conditions),
        "added_conditions_ground_truth_rate": round(added_precision, 4),
        "removed_conditions_count": len(removed_conditions),
        "removed_conditions_ground_truth_rate": round(removed_precision, 4),
        "top1_changed_profiles": top1_changed,
        "profiles_improved_on_primary_top3": len(profiles_improved),
    }
    summary["success_checks"] = {
        "top3_condition_hit_rate_non_decreasing": summary["delta_top3_condition_hit_rate"] >= 0.0,
        "secondary_condition_recovery_non_decreasing": summary["delta_secondary_condition_recovery"] >= 0.0,
        "healthy_over_alert_non_increasing": summary["delta_healthy_over_alert"] <= 0.0,
        "added_conditions_more_truthful_than_removed": summary["added_conditions_ground_truth_rate"] >= summary["removed_conditions_ground_truth_rate"],
        "top1_unchanged": summary["top1_changed_profiles"] == 0,
    }
    summary["overall_goal_met"] = all(summary["success_checks"].values())

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"knn_condition_rerank_{timestamp}"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"{run_id}.json"
    report_path = REPORTS_DIR / f"{run_id}.md"

    payload = {
        "summary": summary,
        "rows": rows,
        "improved_profiles": profiles_improved[:25],
        "sample_added_conditions": added_conditions[:50],
        "sample_removed_conditions": removed_conditions[:50],
    }
    results_path.write_text(json.dumps(payload, indent=2))

    lines = [
        "# KNN Condition Rerank Eval",
        "",
        f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z",
        "",
        "## Summary",
        "",
        f"- Profiles evaluated: `{summary['n_profiles']}`",
        f"- Labeled profiles: `{summary['n_labeled']}`",
        f"- Multi-condition profiles: `{summary['n_multi_condition']}`",
        f"- Healthy profiles: `{summary['n_healthy']}`",
        "",
        "## Success Criteria",
        "",
        f"- Top-3 condition hit rate: `{summary['top3_condition_hit_rate_bayesian']:.1%}` -> `{summary['top3_condition_hit_rate_bayes_plus_knn']:.1%}` (`{summary['delta_top3_condition_hit_rate']:+.1%}`)",
        f"- Secondary-condition recovery: `{summary['secondary_condition_recovery_bayesian']:.1%}` -> `{summary['secondary_condition_recovery_bayes_plus_knn']:.1%}` (`{summary['delta_secondary_condition_recovery']:+.1%}`)",
        f"- Healthy over-alert: `{summary['healthy_over_alert_bayesian']:.1%}` -> `{summary['healthy_over_alert_bayes_plus_knn']:.1%}` (`{summary['delta_healthy_over_alert']:+.1%}`)",
        f"- Added-condition ground-truth rate: `{summary['added_conditions_ground_truth_rate']:.1%}` across `{summary['added_conditions_count']}` additions",
        f"- Removed-condition ground-truth rate: `{summary['removed_conditions_ground_truth_rate']:.1%}` across `{summary['removed_conditions_count']}` removals",
        f"- Top-1 changed profiles: `{summary['top1_changed_profiles']}`",
        "",
        "## Goal Check",
        "",
        f"- Overall: `{'PASS' if summary['overall_goal_met'] else 'FAIL'}`",
        f"- KNN did not invent new top conditions from scratch: `{'PASS' if summary['success_checks']['top1_unchanged'] else 'FAIL'}`",
        f"- KNN improved or preserved top-3 condition hit rate: `{'PASS' if summary['success_checks']['top3_condition_hit_rate_non_decreasing'] else 'FAIL'}`",
        f"- KNN improved or preserved comorbidity recovery: `{'PASS' if summary['success_checks']['secondary_condition_recovery_non_decreasing'] else 'FAIL'}`",
        f"- KNN avoided worsening healthy over-alert: `{'PASS' if summary['success_checks']['healthy_over_alert_non_increasing'] else 'FAIL'}`",
        f"- KNN-added conditions were more often true than the conditions they displaced: `{'PASS' if summary['success_checks']['added_conditions_more_truthful_than_removed'] else 'FAIL'}`",
        "",
        "## Sample Improved Profiles",
        "",
    ]
    for row in profiles_improved[:10]:
        lines.append(
            f"- `{row['profile_id']}`: expected `{row['expected_legacy']}`, Bayes top-3 `{row['bayes_top3']}`, KNN top-3 `{row['knn_top3']}`, bonuses `{row['bonuses']}`"
        )
    report_path.write_text("\n".join(lines) + "\n")

    print(f"Saved JSON to {results_path}")
    print(f"Saved report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
