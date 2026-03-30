#!/usr/bin/env python3
"""
run_knn_layer_eval.py

Offline A/B evaluator for the KNN lab-signal layer using the synthetic cohort.

Control:
  Standard condition-driven lab panel inferred from top ML conditions only.

Treatment:
  Same condition-driven panel plus canonical lab groups surfaced by KNN.

Ground truth:
  Abnormal synthetic labs present on the profile itself, collapsed into a small
  set of canonical lab groups (cbc, iron_studies, thyroid, glycemic,
  inflammation, lipids, kidney, liver_panel), or explicit expected_lab_groups
  when a hand-authored cohort provides them.

This is intentionally narrower than the full product claim. The current
synthetic cohort does not contain kidney/liver ground-truth labs, so this eval
should be read as a provisional offline screen rather than a final KNN verdict.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore")

from scripts.knn_scorer import KNNScorer
from evals.run_layer1_eval import (
    CONDITION_TO_MODEL_KEY,
    MODEL_KEY_TO_CONDITION,
    ModelRunner,
    _build_raw_inputs,
)

DEFAULT_PROFILES = EVALS_DIR / "cohort" / "profiles_v2_latent.json"
DEFAULT_OUTPUT = EVALS_DIR / "results" / "knn_layer_eval_latest.json"

# Ground-truth conditions we can evaluate reasonably with current synthetic labs.
EVALUABLE_CONDITIONS = {
    "anemia",
    "iron_deficiency",
    "hypothyroidism",
    "prediabetes",
    "inflammation",
    "kidney_disease",
    "hepatitis",
    "liver",
}

# Simple literature-style control mapping from suspected conditions to lab groups.
CONDITION_TO_LAB_GROUPS: dict[str, set[str]] = {
    "anemia": {"cbc", "iron_studies"},
    "iron_deficiency": {"cbc", "iron_studies"},
    "hypothyroidism": {"thyroid"},
    "prediabetes": {"glycemic", "lipids"},
    "inflammation": {"inflammation"},
    "kidney_disease": {"kidney"},
    "hepatitis": {"liver_panel"},
    "liver": {"liver_panel"},
}

# KNN surfaced lab -> canonical lab group.
KNN_LAB_GROUPS: dict[str, str] = {
    "Ferritin": "iron_studies",
    "Serum Iron": "iron_studies",
    "TIBC (iron binding capacity)": "iron_studies",
    "Transferrin Saturation": "iron_studies",
    "Hemoglobin": "cbc",
    "Hematocrit": "cbc",
    "RBC Count": "cbc",
    "MCV (mean cell volume)": "cbc",
    "MCH (mean cell hemoglobin)": "cbc",
    "Platelet Count": "cbc",
    "WBC Count": "inflammation",
    "HbA1c (glycated hemoglobin)": "glycemic",
    "Fasting Glucose": "glycemic",
    "hsCRP (high-sensitivity CRP)": "inflammation",
    "Triglycerides": "lipids",
    "Total Cholesterol": "lipids",
    "HDL Cholesterol": "lipids",
    "LDL Cholesterol": "lipids",
    "Creatinine": "kidney",
    "BUN (blood urea nitrogen)": "kidney",
    "Bicarbonate": "kidney",
    "Albumin": "kidney",
    "ALT (liver enzyme)": "liver_panel",
    "AST (liver enzyme)": "liver_panel",
    "GGT (liver enzyme)": "liver_panel",
    "ALP (alkaline phosphatase)": "liver_panel",
    "Total Bilirubin": "liver_panel",
    "Total Protein": "liver_panel",
}


def abnormal_lab_groups(profile: dict[str, Any]) -> set[str]:
    """Collapse abnormal synthetic labs into canonical groups."""
    explicit = profile.get("ground_truth", {}).get("expected_lab_groups")
    if explicit:
        return {str(group) for group in explicit}

    labs = profile.get("lab_values") or {}
    demo = profile.get("demographics") or {}
    sex = str(demo.get("sex", "F"))
    groups: set[str] = set()

    hemoglobin = labs.get("hemoglobin")
    if hemoglobin is not None:
        low_cutoff = 13.5 if sex == "M" else 11.1
        high_cutoff = 17.5 if sex == "M" else 15.4
        if hemoglobin < low_cutoff or hemoglobin > high_cutoff:
            groups.add("cbc")

    ferritin = labs.get("ferritin")
    if ferritin is not None and (ferritin < 30 or ferritin > 300):
        groups.add("iron_studies")

    tsh = labs.get("tsh")
    if tsh is not None and (tsh < 0.4 or tsh > 4.0):
        groups.add("thyroid")

    fasting_glucose = labs.get("fasting_glucose_mg_dl", labs.get("fasting_glucose"))
    hba1c = labs.get("hba1c")
    if (fasting_glucose is not None and fasting_glucose >= 100) or (hba1c is not None and hba1c >= 5.7):
        groups.add("glycemic")

    crp = labs.get("crp")
    wbc = labs.get("wbc_1000_cells_ul", labs.get("wbc"))
    if (crp is not None and crp >= 3.0) or (wbc is not None and (wbc < 4.5 or wbc > 11.0)):
        groups.add("inflammation")

    total_chol = labs.get("total_cholesterol_mg_dl", labs.get("total_cholesterol"))
    trig = labs.get("triglycerides_mg_dl", labs.get("triglycerides"))
    if (total_chol is not None and total_chol >= 200) or (trig is not None and trig >= 150):
        groups.add("lipids")

    creatinine = labs.get("creatinine", labs.get("serum_creatinine_mg_dl"))
    bun = labs.get("bun", labs.get("bun_mg_dl"))
    bicarbonate = labs.get("bicarbonate", labs.get("bicarbonate_mmol_l"))
    if (
        (creatinine is not None and ((sex == "M" and creatinine > 1.2) or (sex != "M" and creatinine > 1.1)))
        or (bun is not None and bun > 20)
        or (bicarbonate is not None and bicarbonate < 22)
    ):
        groups.add("kidney")

    alt = labs.get("alt", labs.get("alt_u_l"))
    ast = labs.get("ast", labs.get("ast_u_l"))
    ggt = labs.get("ggt", labs.get("ggt_u_l"))
    bilirubin = labs.get("bilirubin", labs.get("total_bilirubin_mg_dl"))
    alp = labs.get("alp", labs.get("alp_u_l"))
    if (
        (alt is not None and alt > 40)
        or (ast is not None and ast > 40)
        or (ggt is not None and ggt > 50)
        or (bilirubin is not None and bilirubin > 1.2)
        or (alp is not None and alp > 120)
    ):
        groups.add("liver_panel")

    return groups


def expected_condition_groups(profile: dict[str, Any]) -> set[str]:
    groups: set[str] = set()
    expected = profile.get("ground_truth", {}).get("expected_conditions", [])
    for cond in expected:
        cond_id = cond.get("condition_id")
        if cond_id in CONDITION_TO_LAB_GROUPS:
            groups.update(CONDITION_TO_LAB_GROUPS[cond_id])
    return groups


def top_condition_groups(raw_inputs: dict[str, Any], runner: ModelRunner) -> tuple[list[str], set[str]]:
    norm = runner._get_normalizer()
    vectors = norm.build_feature_vectors(raw_inputs)
    raw_scores = runner.run_all(vectors)
    ranked = sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)

    top_conditions: list[str] = []
    groups: set[str] = set()
    for model_key, _score in ranked[:3]:
        cond_id = MODEL_KEY_TO_CONDITION.get(model_key)
        if cond_id is None and model_key == "liver":
            cond_id = "liver"
        if not cond_id:
            continue
        top_conditions.append(cond_id)
        groups.update(CONDITION_TO_LAB_GROUPS.get(cond_id, set()))
    return top_conditions, groups


def knn_groups(raw_inputs: dict[str, Any], scorer: KNNScorer) -> set[str]:
    result = scorer.score(raw_inputs)
    groups = set()
    for sig in result.get("lab_signals", []):
        group = KNN_LAB_GROUPS.get(sig.get("lab"))
        if group:
            groups.add(group)
    return groups


def profile_is_evaluable(profile: dict[str, Any]) -> tuple[bool, str]:
    explicit_groups = profile.get("ground_truth", {}).get("expected_lab_groups") or []
    if explicit_groups:
        return True, "ok"

    expected = profile.get("ground_truth", {}).get("expected_conditions", [])
    condition_ids = [item.get("condition_id") for item in expected]
    if not condition_ids:
        return False, "no_expected_conditions"
    if not any(cond in EVALUABLE_CONDITIONS for cond in condition_ids):
        return False, "unsupported_conditions"
    if not abnormal_lab_groups(profile):
        return False, "no_abnormal_ground_truth_labs"
    return True, "ok"


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def build_eval_inputs(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Build NHANES-style raw inputs, then apply any hand-authored overrides for
    targeted evaluation packs.
    """
    raw_inputs = _build_raw_inputs(profile)
    overrides = profile.get("raw_input_overrides") or {}
    for key, value in overrides.items():
        raw_inputs[key] = value
    return raw_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline KNN layer A/B evaluator")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=0, help="Evaluate first N profiles only")
    args = parser.parse_args()

    profiles = json.loads(args.profiles.read_text())
    if args.limit > 0:
        profiles = profiles[: args.limit]

    logging.getLogger("model_runner").setLevel(logging.WARNING)

    runner = ModelRunner()
    scorer = KNNScorer()

    skip_reasons = Counter()
    evaluated = []

    for profile in profiles:
        ok, reason = profile_is_evaluable(profile)
        if not ok:
            skip_reasons[reason] += 1
            continue

        raw_inputs = build_eval_inputs(profile)
        gt_groups = abnormal_lab_groups(profile)
        expected_groups = expected_condition_groups(profile)
        top_conditions, control_groups = top_condition_groups(raw_inputs, runner)
        knn_only_groups = knn_groups(raw_inputs, scorer)
        treatment_groups = control_groups | knn_only_groups

        evaluated.append({
            "profile_id": profile["profile_id"],
            "profile_type": profile.get("profile_type"),
            "expected_conditions": [c["condition_id"] for c in profile["ground_truth"]["expected_conditions"]],
            "top_conditions": top_conditions,
            "ground_truth_groups": sorted(gt_groups),
            "expected_groups": sorted(expected_groups),
            "control_groups": sorted(control_groups),
            "knn_groups": sorted(knn_only_groups),
            "treatment_groups": sorted(treatment_groups),
        })

    def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        control_hits = 0
        treatment_hits = 0
        control_exact = 0
        treatment_exact = 0
        control_recalls = []
        treatment_recalls = []
        control_precisions = []
        treatment_precisions = []
        knn_added_signal = 0
        improved = 0

        by_type: dict[str, dict[str, int]] = defaultdict(lambda: {
            "count": 0,
            "control_hit": 0,
            "treatment_hit": 0,
            "improved": 0,
        })

        for row in rows:
            gt = set(row["ground_truth_groups"])
            control = set(row["control_groups"])
            treatment = set(row["treatment_groups"])
            knn_groups_set = set(row["knn_groups"])

            control_intersection = control & gt
            treatment_intersection = treatment & gt

            control_hit = bool(control_intersection)
            treatment_hit = bool(treatment_intersection)
            control_exact_hit = gt.issubset(control)
            treatment_exact_hit = gt.issubset(treatment)

            control_hits += int(control_hit)
            treatment_hits += int(treatment_hit)
            control_exact += int(control_exact_hit)
            treatment_exact += int(treatment_exact_hit)
            knn_added_signal += int(bool(knn_groups_set))
            improved += int(len(treatment_intersection) > len(control_intersection))

            control_recalls.append(safe_div(len(control_intersection), len(gt)))
            treatment_recalls.append(safe_div(len(treatment_intersection), len(gt)))
            control_precisions.append(safe_div(len(control_intersection), len(control)))
            treatment_precisions.append(safe_div(len(treatment_intersection), len(treatment)))

            bucket = by_type[row["profile_type"]]
            bucket["count"] += 1
            bucket["control_hit"] += int(control_hit)
            bucket["treatment_hit"] += int(treatment_hit)
            bucket["improved"] += int(len(treatment_intersection) > len(control_intersection))

        summary = {
            "n_profiles": len(rows),
            "control_hit_rate": round(safe_div(control_hits, len(rows)), 4),
            "treatment_hit_rate": round(safe_div(treatment_hits, len(rows)), 4),
            "delta_hit_rate": round(safe_div(treatment_hits - control_hits, len(rows)), 4),
            "control_exact_coverage": round(safe_div(control_exact, len(rows)), 4),
            "treatment_exact_coverage": round(safe_div(treatment_exact, len(rows)), 4),
            "delta_exact_coverage": round(safe_div(treatment_exact - control_exact, len(rows)), 4),
            "control_mean_recall": round(mean(control_recalls), 4) if rows else 0.0,
            "treatment_mean_recall": round(mean(treatment_recalls), 4) if rows else 0.0,
            "delta_mean_recall": round((mean(treatment_recalls) - mean(control_recalls)), 4) if rows else 0.0,
            "control_mean_precision": round(mean(control_precisions), 4) if rows else 0.0,
            "treatment_mean_precision": round(mean(treatment_precisions), 4) if rows else 0.0,
            "delta_mean_precision": round((mean(treatment_precisions) - mean(control_precisions)), 4) if rows else 0.0,
            "profiles_with_knn_signal": knn_added_signal,
            "profiles_improved_by_knn": improved,
            "by_profile_type": {
                key: {
                    "count": value["count"],
                    "control_hit_rate": round(safe_div(value["control_hit"], value["count"]), 4),
                    "treatment_hit_rate": round(safe_div(value["treatment_hit"], value["count"]), 4),
                    "improved_rate": round(safe_div(value["improved"], value["count"]), 4),
                }
                for key, value in sorted(by_type.items())
            },
        }
        return summary

    summary = aggregate(evaluated)

    out = {
        "profiles_path": str(args.profiles),
        "skip_reasons": dict(skip_reasons),
        "summary": summary,
        "sample_improvements": [
            row for row in evaluated
            if len(set(row["treatment_groups"]) & set(row["ground_truth_groups"]))
            > len(set(row["control_groups"]) & set(row["ground_truth_groups"]))
        ][:20],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"\nSaved detailed results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
