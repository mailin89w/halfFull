#!/usr/bin/env python3
"""
Offline disease-refinement cluster prototype.

This is intentionally separate from the production KNN layer. The goal is to test
whether a symptom/questionnaire-focused neighbor space can help disease refinement
better than the existing lab-heavy KNN setup.

Prototype design
----------------
1. Build a cosine-neighbor index from a symptom/demographic feature subset only.
2. Use real NHANES disease labels from nhanes_merged_adults_diseases.csv.
3. Score each eval profile by neighbor disease-label fraction.
4. Calibrate per-condition flag thresholds from the eval healthy subset.

This is an offline experiment only, not a production scoring path.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics.pairwise import cosine_distances

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
PROFILES_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"
NORMALIZED_PATH = PROJECT_ROOT / "data/processed/nhanes_merged_adults_final_normalized.csv"
DISEASES_PATH = PROJECT_ROOT / "data/processed/nhanes_merged_adults_diseases.csv"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from run_layer1_eval import _build_raw_inputs_from_nhanes  # noqa: E402

K = 50
STEP = 1.0 / K

# Deliberately symptom / questionnaire oriented. Excludes direct disease-history
# items, treatments, and labs so the neighbor space reflects clinical pattern
# rather than already-labeled disease state.
REFINEMENT_FEATURES = [
    "dpq040___feeling_tired_or_having_little_energy",
    "slq050___ever_told_doctor_had_trouble_sleeping?",
    "age_years",
    "huq051___#times_receive_healthcare_over_past_year",
    "huq010___general_health_condition",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "bmi",
    "weight_kg",
    "sld012___sleep_hours___weekdays_or_workdays",
    "pad680___minutes_sedentary_activity",
    "mcq160a___ever_told_you_had_arthritis",
    "ocq180___hours_worked_last_week_in_total_all_jobs",
    "sld013___sleep_hours___weekends",
    "rhq031___had_regular_periods_in_past_12_months",
    "slq030___how_often_do_you_snore?",
    "mcq520___abdominal_pain_during_past_12_months?",
    "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "kiq005___how_often_have_urinary_leakage?",
    "smq020___smoked_at_least_100_cigarettes_in_life",
    "rhq060___age_at_last_menstrual_period",
    "kiq480___how_many_times_urinate_in_night?",
    "smd650___avg_#_cigarettes/day_during_past_30_days",
    "rhq160___how_many_times_have_been_pregnant?",
    "ocq670___overall_work_schedule_past_3_months",
    "smq040___do_you_now_smoke_cigarettes?",
]

LABEL_TO_EVAL_CONDITIONS: dict[str, list[str]] = {
    "anemia": ["anemia", "iron_deficiency"],
    "diabetes": ["prediabetes"],
    "thyroid": ["hypothyroidism"],
    "sleep_disorder": ["sleep_disorder"],
    "kidney": ["kidney_disease"],
    "hepatitis_bc": ["hepatitis"],
    "liver": ["liver"],
    "menopause": ["perimenopause"],
}
LABEL_COLS = list(LABEL_TO_EVAL_CONDITIONS.keys())
EVAL_CONDITIONS = [
    "anemia",
    "electrolyte_imbalance",
    "hepatitis",
    "hypothyroidism",
    "inflammation",
    "iron_deficiency",
    "kidney_disease",
    "liver",
    "perimenopause",
    "prediabetes",
    "sleep_disorder",
    "vitamin_d_deficiency",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run disease-refinement cluster prototype eval.")
    parser.add_argument("--profiles", type=Path, default=PROFILES_PATH, help="Cohort JSON path.")
    parser.add_argument("--k", type=int, default=K, help="Neighbor count.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="JSON output directory.")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help="Markdown output directory.")
    return parser.parse_args()


def _safe_git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() or None
    except Exception:
        return None


def load_profiles(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_index() -> tuple[np.ndarray, SimpleImputer, np.ndarray, dict[str, float]]:
    norm = pd.read_csv(NORMALIZED_PATH, usecols=["SEQN", *REFINEMENT_FEATURES], low_memory=False).drop_duplicates(subset=["SEQN"])
    diseases = pd.read_csv(DISEASES_PATH, usecols=["SEQN", *LABEL_COLS], low_memory=False).drop_duplicates(subset=["SEQN"])
    merged = norm.merge(diseases, on="SEQN", how="inner")
    x_df = merged[REFINEMENT_FEATURES].apply(pd.to_numeric, errors="coerce")
    imputer = SimpleImputer(strategy="median")
    x_index = imputer.fit_transform(x_df)
    label_matrix = merged[LABEL_COLS].fillna(0).astype(float).values
    population_prevalence = {label: float(merged[label].fillna(0).mean()) for label in LABEL_COLS}
    return x_index, imputer, label_matrix, population_prevalence


def build_user_vector(profile: dict[str, Any], imputer: SimpleImputer) -> np.ndarray | None:
    raw_inputs = _build_raw_inputs_from_nhanes(profile)
    row = []
    present = 0
    for feature in REFINEMENT_FEATURES:
        value = raw_inputs.get(feature)
        if value is None:
            row.append(np.nan)
            continue
        try:
            row.append(float(value))
            if not math.isnan(float(value)):
                present += 1
        except (TypeError, ValueError):
            row.append(np.nan)
    if present < 5:
        return None
    return imputer.transform(np.array(row, dtype=float).reshape(1, -1))


def score_profile(
    profile: dict[str, Any],
    x_index: np.ndarray,
    imputer: SimpleImputer,
    label_matrix: np.ndarray,
    k: int,
) -> dict[str, float]:
    user_vec = build_user_vector(profile, imputer)
    if user_vec is None:
        return {condition: 0.0 for condition in EVAL_CONDITIONS}
    dists = cosine_distances(user_vec, x_index)[0]
    neighbor_idx = np.argpartition(dists, k)[:k]
    neighbor_labels = label_matrix[neighbor_idx]
    label_scores = {label: float(neighbor_labels[:, i].mean()) for i, label in enumerate(LABEL_COLS)}
    eval_scores = {condition: 0.0 for condition in EVAL_CONDITIONS}
    for label, conditions in LABEL_TO_EVAL_CONDITIONS.items():
        for condition in conditions:
            eval_scores[condition] = label_scores[label]
    return eval_scores


def top3_from_scores(scores: dict[str, float]) -> list[str]:
    return [condition for condition, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:3] if score > 0]


def expected_condition_ids(profile: dict[str, Any]) -> list[str]:
    expected = profile.get("ground_truth", {}).get("expected_conditions", [])
    out: list[str] = []
    for item in expected:
        condition_id = item.get("condition_id")
        if condition_id:
            out.append(condition_id)
    return out


def primary_condition(profile: dict[str, Any]) -> str | None:
    expected = profile.get("ground_truth", {}).get("expected_conditions", [])
    for item in expected:
        if item.get("is_primary"):
            return item.get("condition_id")
    return expected[0].get("condition_id") if expected else None


def calibrate_thresholds(records: list[dict[str, Any]], population_prevalence: dict[str, float]) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    healthy = [record for record in records if not record["expected_conditions"]]
    for condition in EVAL_CONDITIONS:
        label = next((label for label, conds in LABEL_TO_EVAL_CONDITIONS.items() if condition in conds), None)
        if label is None:
            thresholds[condition] = 1.0
            continue
        healthy_scores = sorted(record["score_map"].get(condition, 0.0) for record in healthy)
        if healthy_scores:
            p95 = healthy_scores[min(len(healthy_scores) - 1, int(0.95 * len(healthy_scores)))]
        else:
            p95 = 0.0
        base = max(2.0 * population_prevalence[label], p95)
        thresholds[condition] = round(min(math.ceil(base / STEP) * STEP, 1.0), 2)
    return thresholds


def evaluate(records: list[dict[str, Any]], thresholds: dict[str, float]) -> dict[str, Any]:
    positives = [record for record in records if record["primary_condition"] is not None]
    healthy = [record for record in records if record["primary_condition"] is None]

    top3_any_hits = sum(bool(set(record["top3_predictions"]) & set(record["expected_conditions"])) for record in records)
    top1_primary_hits = sum(record["top1_prediction"] == record["primary_condition"] for record in positives)
    top3_primary_hits = sum(record["primary_condition"] in record["top3_predictions"] for record in positives)
    healthy_alerts = 0
    for record in healthy:
        if any(record["score_map"].get(condition, 0.0) >= thresholds[condition] for condition in EVAL_CONDITIONS):
            healthy_alerts += 1

    per_condition: dict[str, dict[str, float | int]] = {}
    for condition in EVAL_CONDITIONS:
        positives_any = [record for record in records if condition in record["expected_conditions"]]
        flagged = [record for record in records if record["score_map"].get(condition, 0.0) >= thresholds[condition]]
        recall = (
            sum(condition in record["top3_predictions"] for record in positives_any) / len(positives_any)
            if positives_any else 0.0
        )
        healthy_fp = (
            sum(record["score_map"].get(condition, 0.0) >= thresholds[condition] for record in healthy) / len(healthy)
            if healthy else 0.0
        )
        per_condition[condition] = {
            "n_any_positive": len(positives_any),
            "recall_at_3": round(recall, 4),
            "healthy_flag_rate": round(healthy_fp, 4),
            "threshold": thresholds[condition],
        }

    return {
        "top3_contains_any_true_condition": round(top3_any_hits / len(records), 4),
        "top1_primary_accuracy": round(top1_primary_hits / len(positives), 4) if positives else 0.0,
        "top3_primary_coverage": round(top3_primary_hits / len(positives), 4) if positives else 0.0,
        "healthy_over_alert_rate": round(healthy_alerts / len(healthy), 4) if healthy else 0.0,
        "per_condition": per_condition,
    }


def build_markdown(run_id: str, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Disease-Refinement Cluster Prototype — {run_id}",
        "",
        "> Symptom/questionnaire-focused neighbor voting prototype. Offline only.",
        "",
        "## Setup",
        "",
        f"- Cohort: `{payload['profiles_path']}`",
        f"- NHANES index rows: `{payload['index_rows']}`",
        f"- Neighbor count: `{payload['k']}`",
        f"- Refinement features: `{len(payload['refinement_features'])}`",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Top-3 contains any true condition | {summary['top3_contains_any_true_condition']:.1%} |",
        f"| Top-1 primary accuracy | {summary['top1_primary_accuracy']:.1%} |",
        f"| Top-3 primary coverage | {summary['top3_primary_coverage']:.1%} |",
        f"| Healthy over-alert rate | {summary['healthy_over_alert_rate']:.1%} |",
        "",
        "## Per Condition",
        "",
        "| Condition | Recall@3 | Healthy flag rate | Threshold | N any-label+ |",
        "|-----------|----------|-------------------|-----------|--------------|",
    ]
    for condition in EVAL_CONDITIONS:
        row = summary["per_condition"][condition]
        lines.append(
            f"| {condition} | {row['recall_at_3']:.1%} | {row['healthy_flag_rate']:.1%} | {row['threshold']:.2f} | {row['n_any_positive']} |"
        )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles(args.profiles)
    x_index, imputer, label_matrix, population_prevalence = load_index()

    records: list[dict[str, Any]] = []
    for profile in profiles:
        score_map = score_profile(profile, x_index, imputer, label_matrix, args.k)
        records.append(
            {
                "profile_id": profile["profile_id"],
                "primary_condition": primary_condition(profile),
                "expected_conditions": expected_condition_ids(profile),
                "score_map": score_map,
                "top1_prediction": next(iter(sorted(score_map, key=score_map.get, reverse=True)), None),
                "top3_predictions": top3_from_scores(score_map),
            }
        )

    thresholds = calibrate_thresholds(records, population_prevalence)
    summary = evaluate(records, thresholds)

    run_id = datetime.utcnow().strftime("disease_refinement_cluster_%Y%m%d_%H%M%S")
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "profiles_path": str(args.profiles),
        "k": args.k,
        "index_rows": int(x_index.shape[0]),
        "refinement_features": REFINEMENT_FEATURES,
        "population_prevalence": population_prevalence,
        "summary": summary,
    }
    json_path = args.output_dir / f"{run_id}.json"
    md_path = args.reports_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(run_id, payload), encoding="utf-8")

    print(f"Saved JSON results: {json_path}")
    print(f"Saved Markdown report: {md_path}")
    print(f"Top-3 any true: {summary['top3_contains_any_true_condition']:.1%}")
    print(f"Healthy over-alert: {summary['healthy_over_alert_rate']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
