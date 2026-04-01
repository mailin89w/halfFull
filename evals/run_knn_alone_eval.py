#!/usr/bin/env python3
"""
run_knn_alone_eval.py — KNN layer standalone evaluation (no ML models, no Bayesian).

Scores each profile using only KNNScorer lab-signal output and maps those signals
to conditions via canonical lab-group associations.  Produces the same metric tables
as run_layer1_eval.py for direct layer-by-layer comparison before stacking.

Scoring mechanic
----------------
  condition_score = sum of max-lift signals across the condition's supporting lab groups
  condition_flagged = score > 0  (at least one qualifying KNN signal fires)

Two perspectives per condition
-------------------------------
  as-target   : positive set = profiles where that condition is the primary target
                (matches run_layer1_eval.py definition exactly)
  as-any-label: positive set = profiles where the condition appears anywhere in
                expected_conditions[] (any position, any non-healthy profile type)
                — useful because KNN may surface a secondary condition even when
                  it is not the profile's primary target

KNN coverage gaps (will always score 0 — structural, not a bug)
----------------------------------------------------------------
  hypothyroidism       — TSH is absent from the NHANES KNN anchor feature set
  electrolyte_imbalance — no specific lab group in KNN mapping
  perimenopause        — no specific lab group in KNN mapping
  sleep_disorder       — no specific lab group in KNN mapping
  vitamin_d_deficiency — no specific lab group in KNN mapping

Usage
-----
  python evals/run_knn_alone_eval.py
  python evals/run_knn_alone_eval.py --profiles evals/cohort/nhanes_balanced_760.json
  python evals/run_knn_alone_eval.py --n 100 --seed 7
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EVALS_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from pipeline.profile_loader import ProfileLoader

try:
    from scripts.knn_scorer import KNNScorer
except ImportError as exc:
    print(f"ERROR: Could not import KNNScorer from scripts/: {exc}", file=sys.stderr)
    sys.exit(1)

# Reuse raw-input builders and condition mapping from the layer1 eval
try:
    from run_layer1_eval import (
        CONDITION_TO_MODEL_KEY,
        _build_raw_inputs,
        _build_raw_inputs_from_nhanes,
    )
except ImportError as exc:
    print(
        f"ERROR: Could not import helpers from run_layer1_eval.py: {exc}\n"
        "Make sure evals/run_layer1_eval.py is present.",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROFILES_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"
SCHEMA_PATH   = EVALS_DIR / "schema"  / "profile_schema.json"
RESULTS_DIR   = EVALS_DIR / "results"
REPORTS_DIR   = EVALS_DIR / "reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_knn_alone_eval")

# ---------------------------------------------------------------------------
# Lab-signal → lab-group → condition mappings
# (derived from archive/run_knn_layer_eval.py and knn_condition_reranker.py)
# ---------------------------------------------------------------------------

# KNN lab display name → canonical lab group
KNN_LAB_GROUPS: dict[str, str] = {
    "Ferritin":                          "iron_studies",
    "Serum Iron":                        "iron_studies",
    "TIBC (iron binding capacity)":      "iron_studies",
    "Transferrin Saturation":            "iron_studies",
    "Hemoglobin":                        "cbc",
    "Hematocrit":                        "cbc",
    "RBC Count":                         "cbc",
    "MCV (mean cell volume)":            "cbc",
    "MCH (mean cell hemoglobin)":        "cbc",
    "Platelet Count":                    "cbc",
    "WBC Count":                         "inflammation",
    "HbA1c (glycated hemoglobin)":       "glycemic",
    "Fasting Glucose":                   "glycemic",
    "hsCRP (high-sensitivity CRP)":      "inflammation",
    "Triglycerides":                     "lipids",
    "Total Cholesterol":                 "lipids",
    "HDL Cholesterol":                   "lipids",
    "LDL Cholesterol":                   "lipids",
    "Creatinine":                        "kidney",
    "BUN (blood urea nitrogen)":         "kidney",
    "Bicarbonate":                       "kidney",
    "Albumin":                           "kidney",
    "ALT (liver enzyme)":                "liver_panel",
    "AST (liver enzyme)":                "liver_panel",
    "GGT (liver enzyme)":                "liver_panel",
    "ALP (alkaline phosphatase)":        "liver_panel",
    "Total Bilirubin":                   "liver_panel",
    "Total Protein":                     "liver_panel",
}

# eval condition ID → supporting KNN lab groups
# Notes:
#   hypothyroidism: TSH is absent from the NHANES KNN anchor feature set → no support
#   The lipids group was removed from prediabetes (too non-specific, 2026-03-27)
CONDITION_LAB_GROUPS: dict[str, frozenset[str]] = {
    "anemia":                frozenset({"cbc", "iron_studies"}),
    "electrolyte_imbalance": frozenset(),          # no specific KNN group
    "hepatitis":             frozenset({"liver_panel"}),
    "hypothyroidism":        frozenset(),          # TSH absent from KNN index
    "inflammation":          frozenset({"inflammation"}),
    "iron_deficiency":       frozenset({"cbc", "iron_studies"}),
    "kidney_disease":        frozenset({"kidney"}),
    "liver":                 frozenset({"liver_panel"}),
    "perimenopause":         frozenset(),          # no specific KNN group
    "prediabetes":           frozenset({"glycemic"}),
    "sleep_disorder":        frozenset(),          # no specific KNN group
    "vitamin_d_deficiency":  frozenset(),          # no specific KNN group
}

EVAL_CONDITIONS: tuple[str, ...] = tuple(CONDITION_TO_MODEL_KEY.keys())
COVERED_CONDITIONS: frozenset[str] = frozenset(
    c for c, groups in CONDITION_LAB_GROUPS.items() if groups
)
UNCOVERED_CONDITIONS: frozenset[str] = frozenset(EVAL_CONDITIONS) - COVERED_CONDITIONS


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


# ---------------------------------------------------------------------------
# KNN scoring
# ---------------------------------------------------------------------------

def _knn_score_profile(
    profile: dict,
    scorer: KNNScorer,
) -> dict[str, float] | None:
    """
    Run KNNScorer on one profile and return a {eval_condition: score} dict.

    score = sum of max-lift values across the condition's supporting lab groups.
    Conditions with no KNN lab group support always receive score 0.0.
    Returns None when KNNScorer fails or reports insufficient anchor features.
    """
    try:
        if "nhanes_inputs" in profile:
            raw_inputs = _build_raw_inputs_from_nhanes(profile)
        else:
            raw_inputs = _build_raw_inputs(profile)

        result = scorer.score(raw_inputs)
    except Exception as exc:
        logger.warning(
            "KNN scoring failed for %s: %s",
            profile.get("profile_id", "?"), exc,
        )
        return None

    if result.get("error"):
        logger.debug(
            "KNN returned error for %s: %s",
            profile.get("profile_id", "?"), result["error"],
        )
        return None

    # Build lab_group → max_lift from KNN signals
    group_max_lift: dict[str, float] = defaultdict(float)
    for sig in result.get("lab_signals", []):
        lab_name = sig.get("lab", "")
        lift     = sig.get("lift") or 0.0
        group    = KNN_LAB_GROUPS.get(lab_name)
        if group and lift > 0:
            group_max_lift[group] = max(group_max_lift[group], lift)

    # Condition score = sum of max-lifts for its supporting lab groups
    scores: dict[str, float] = {}
    for cond in EVAL_CONDITIONS:
        supporting = CONDITION_LAB_GROUPS.get(cond, frozenset())
        score = sum(group_max_lift.get(g, 0.0) for g in supporting)
        scores[cond] = round(score, 4)

    return scores


def _eval_profile(
    profile: dict,
    scores: dict[str, float] | None,
) -> dict:
    """Compare KNN scores against ground truth for a single profile."""
    pid              = profile.get("profile_id", "")
    ptype            = profile.get("profile_type", "")
    target_condition = profile.get("target_condition")
    quiz_path        = profile.get("quiz_path", "hybrid")

    ground_truth         = profile.get("ground_truth", {})
    expected             = ground_truth.get("expected_conditions", [])
    gt_primary           = expected[0]["condition_id"] if expected else None
    gt_all_conditions    = frozenset(item["condition_id"] for item in expected)

    null_result = {
        "profile_id":           pid,
        "profile_type":         ptype,
        "target_condition":     target_condition,
        "quiz_path":            quiz_path,
        "scoring_success":      False,
        "knn_top1":             None,
        "knn_top1_score":       None,
        "top1_correct":         None,   # primary-target view
        "top3_hit":             None,   # primary-target view
        "top1_correct_any":     None,   # any-label view
        "top3_hit_any":         None,   # any-label view
        "ground_truth_primary": gt_primary,
        "gt_all_conditions":    sorted(gt_all_conditions),
        "scores":               {},
    }

    if scores is None:
        return null_result

    # Only conditions with KNN lab group support can generate a non-zero score;
    # rank only among those to avoid phantom "wins" by zero-scored conditions
    active = sorted(
        ((c, v) for c, v in scores.items() if c in COVERED_CONDITIONS and v > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    top1 = active[0][0] if active else None
    top3 = frozenset(c for c, _ in active[:3])

    # ── Primary-target view (matches layer1 definition) ────────────────────
    # Eligible only when the primary GT condition is KNN-detectable
    if gt_primary is not None and gt_primary in COVERED_CONDITIONS:
        top1_correct: bool | None = (top1 == gt_primary) if active else False
        top3_hit: bool | None     = gt_primary in top3
    else:
        top1_correct = None
        top3_hit     = None

    # ── Any-label view ─────────────────────────────────────────────────────
    # Eligible when AT LEAST ONE condition the user has is KNN-detectable.
    # A hit means the KNN ranked any of their actual conditions at #1 (or top-3).
    covered_gt = gt_all_conditions & COVERED_CONDITIONS
    if covered_gt:
        top1_correct_any: bool | None = (top1 in gt_all_conditions) if active else False
        top3_hit_any: bool | None     = bool(top3 & gt_all_conditions)
    else:
        top1_correct_any = None   # none of their conditions are KNN-detectable
        top3_hit_any     = None

    return {
        "profile_id":           pid,
        "profile_type":         ptype,
        "target_condition":     target_condition,
        "quiz_path":            quiz_path,
        "scoring_success":      True,
        "knn_top1":             top1,
        "knn_top1_score":       active[0][1] if active else None,
        "top1_correct":         top1_correct,
        "top3_hit":             top3_hit,
        "top1_correct_any":     top1_correct_any,
        "top3_hit_any":         top3_hit_any,
        "ground_truth_primary": gt_primary,
        "gt_all_conditions":    sorted(gt_all_conditions),
        "scores":               scores,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(results: list[dict]) -> dict:
    """Compute cohort-level metrics from per-profile KNN eval dicts."""
    scored  = [r for r in results if r["scoring_success"]]
    healthy = [r for r in scored  if r.get("profile_type") == "healthy"]

    # ── top1_accuracy — primary-target view ───────────────────────────────
    top1_eligible = [r for r in scored if r.get("top1_correct") is not None]
    top1_correct  = sum(1 for r in top1_eligible if r["top1_correct"])
    top1_accuracy = top1_correct / len(top1_eligible) if top1_eligible else 0.0

    pos_eligible = [r for r in top1_eligible if r.get("profile_type") == "positive"]
    pos_correct  = sum(1 for r in pos_eligible if r["top1_correct"])
    pos_top1_acc = pos_correct / len(pos_eligible) if pos_eligible else 0.0

    # ── top3_coverage — primary-target view ───────────────────────────────
    top3_eligible = [r for r in scored if r.get("top3_hit") is not None]
    top3_hits     = sum(1 for r in top3_eligible if r["top3_hit"])
    top3_coverage = top3_hits / len(top3_eligible) if top3_eligible else 0.0

    # ── top1_accuracy — any-label view ────────────────────────────────────
    # Eligible = profiles where at least one of the user's conditions is KNN-detectable
    top1_eligible_any = [r for r in scored if r.get("top1_correct_any") is not None]
    top1_correct_any  = sum(1 for r in top1_eligible_any if r["top1_correct_any"])
    top1_accuracy_any = top1_correct_any / len(top1_eligible_any) if top1_eligible_any else 0.0

    pos_eligible_any = [r for r in top1_eligible_any if r.get("profile_type") == "positive"]
    pos_correct_any  = sum(1 for r in pos_eligible_any if r["top1_correct_any"])
    pos_top1_acc_any = pos_correct_any / len(pos_eligible_any) if pos_eligible_any else 0.0

    # ── top3_coverage — any-label view ────────────────────────────────────
    top3_eligible_any = [r for r in scored if r.get("top3_hit_any") is not None]
    top3_hits_any     = sum(1 for r in top3_eligible_any if r["top3_hit_any"])
    top3_coverage_any = top3_hits_any / len(top3_eligible_any) if top3_eligible_any else 0.0

    # ── over_alert_rate: healthy profile flagged by ANY KNN condition ──────
    over_alerted    = sum(1 for r in healthy if any(v > 0 for v in r.get("scores", {}).values()))
    over_alert_rate = over_alerted / len(healthy) if healthy else 0.0

    # ── by quiz path ───────────────────────────────────────────────────────
    by_quiz_path: dict[str, dict] = {}
    for path in ("full", "hybrid"):
        path_top1     = [r for r in top1_eligible     if r.get("quiz_path") == path]
        path_top3     = [r for r in top3_eligible     if r.get("quiz_path") == path]
        path_top1_any = [r for r in top1_eligible_any if r.get("quiz_path") == path]
        path_top3_any = [r for r in top3_eligible_any if r.get("quiz_path") == path]
        by_quiz_path[path] = {
            "top1_accuracy":     sum(1 for r in path_top1 if r["top1_correct"]) / len(path_top1) if path_top1 else 0.0,
            "top3_coverage":     sum(1 for r in path_top3 if r["top3_hit"])     / len(path_top3) if path_top3 else 0.0,
            "top1_accuracy_any": sum(1 for r in path_top1_any if r["top1_correct_any"]) / len(path_top1_any) if path_top1_any else 0.0,
            "top3_coverage_any": sum(1 for r in path_top3_any if r["top3_hit_any"])     / len(path_top3_any) if path_top3_any else 0.0,
            "n": len([r for r in scored if r.get("quiz_path") == path]),
        }

    # ── per-condition metrics ──────────────────────────────────────────────
    per_condition:         dict[str, dict] = {}
    per_condition_any:     dict[str, dict] = {}
    healthy_per_condition: dict[str, dict] = {}

    for eval_cond in EVAL_CONDITIONS:
        has_support = eval_cond in COVERED_CONDITIONS
        lab_groups  = sorted(CONDITION_LAB_GROUPS.get(eval_cond, frozenset()))

        # Flagged = score > 0 (any KNN signal for this condition's lab groups)
        flagged         = [r for r in scored  if r.get("scores", {}).get(eval_cond, 0.0) > 0]
        healthy_flagged = [r for r in healthy if r.get("scores", {}).get(eval_cond, 0.0) > 0]
        flag_rate       = len(flagged) / len(scored) if scored else 0.0

        # ---- AS TARGET (matches layer1 definition) ----
        target_profiles = [r for r in scored if r.get("target_condition") == eval_cond]
        positive_target = [r for r in target_profiles if r.get("profile_type") == "positive"]

        tp_target = [
            r for r in flagged
            if r.get("target_condition") == eval_cond and r.get("profile_type") == "positive"
        ]
        recall_t    = len(tp_target) / len(positive_target) if positive_target else None
        precision_t = len(tp_target) / len(flagged)         if flagged         else None

        target_scores = [
            r["scores"].get(eval_cond, 0.0)
            for r in positive_target if r.get("scores")
        ]
        mean_score_t = float(np.mean(target_scores)) if target_scores else None

        per_condition[eval_cond] = {
            "has_knn_support":   has_support,
            "lab_groups":        lab_groups,
            "n_target_profiles": len(target_profiles),
            "n_positive_target": len(positive_target),
            "n_flagged":         len(flagged),
            "n_true_positive":   len(tp_target),
            "recall":            round(recall_t,    4) if recall_t    is not None else None,
            "precision":         round(precision_t, 4) if precision_t is not None else None,
            "flag_rate":         round(flag_rate,   4),
            "mean_score":        round(mean_score_t, 4) if mean_score_t is not None else None,
        }

        healthy_per_condition[eval_cond] = {
            "n_healthy_profiles": len(healthy),
            "n_healthy_flagged":  len(healthy_flagged),
            "healthy_flag_rate":  round(len(healthy_flagged) / len(healthy), 4) if healthy else 0.0,
        }

        # ---- AS ANY-LABEL ----
        # Positive = profiles where eval_cond appears anywhere in expected_conditions,
        # regardless of position, but excluding healthy profiles
        any_label_pos = [
            r for r in scored
            if eval_cond in r.get("gt_all_conditions", [])
            and r.get("profile_type") != "healthy"
        ]
        tp_any         = [r for r in flagged if eval_cond in r.get("gt_all_conditions", [])]
        recall_any     = len(tp_any) / len(any_label_pos) if any_label_pos else None
        precision_any  = len(tp_any) / len(flagged)       if flagged       else None

        any_scores = [
            r["scores"].get(eval_cond, 0.0)
            for r in any_label_pos if r.get("scores")
        ]
        mean_score_any = float(np.mean(any_scores)) if any_scores else None

        per_condition_any[eval_cond] = {
            "n_any_label_positive": len(any_label_pos),
            "n_flagged":            len(flagged),
            "n_true_positive":      len(tp_any),
            "recall":               round(recall_any,    4) if recall_any    is not None else None,
            "precision":            round(precision_any, 4) if precision_any is not None else None,
            "flag_rate":            round(flag_rate,     4),
            "mean_score":           round(mean_score_any, 4) if mean_score_any is not None else None,
        }

    return {
        "n_profiles":                  len(results),
        "n_scored":                    len(scored),
        "n_scoring_errors":            len(results) - len(scored),
        # primary-target view
        "n_top1_eligible":             len(top1_eligible),
        "n_top3_eligible":             len(top3_eligible),
        "top1_accuracy":               round(top1_accuracy, 4),
        "positives_top1_accuracy":     round(pos_top1_acc,  4),
        "top3_coverage":               round(top3_coverage,  4),
        # any-label view
        "n_top1_eligible_any":         len(top1_eligible_any),
        "n_top3_eligible_any":         len(top3_eligible_any),
        "top1_accuracy_any":           round(top1_accuracy_any, 4),
        "positives_top1_accuracy_any": round(pos_top1_acc_any,  4),
        "top3_coverage_any":           round(top3_coverage_any,  4),
        # shared
        "over_alert_rate":             round(over_alert_rate, 4),
        "by_quiz_path":                by_quiz_path,
        "per_condition":               per_condition,
        "per_condition_any":           per_condition_any,
        "healthy_per_condition":       healthy_per_condition,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _to_markdown(report: dict, run_id: str, run_meta: dict) -> str:
    lines: list[str] = []

    lines.append(f"# HalfFull KNN-Alone Eval — {run_id}")
    lines.append("")
    lines.append("> KNN lab-signal layer only. No ML models. No Bayesian updating.")
    lines.append("")

    # Run metadata
    lines.append("## Run Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Git SHA | {run_meta.get('git_sha') or 'unknown'} |")
    lines.append(f"| Profiles Path | `{run_meta.get('profiles_path', '')}` |")
    lines.append(f"| Scoring method | KNN lab signals (cosine-NN, k=50, NHANES 7437-row index) |")
    lines.append(f"| Condition score | sum of max-lifts across supporting lab groups |")
    lines.append(f"| Flag threshold | score > 0 (any qualifying KNN signal) |")
    lines.append("")

    # Summary
    n_scored = report["n_scored"]
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Primary-target | Any-label |")
    lines.append("|--------|---------------|-----------|")
    lines.append(f"| Profiles evaluated | {report['n_profiles']} | — |")
    lines.append(f"| Profiles scored    | {report['n_scored']} | — |")
    lines.append(f"| Scoring errors     | {report['n_scoring_errors']} | — |")
    n_t1 = report["n_top1_eligible"]
    n_t1a = report["n_top1_eligible_any"]
    lines.append(
        f"| Top-1 eligible (KNN-detectable) "
        f"| {n_t1} ({n_t1 / n_scored:.0%}) "
        f"| {n_t1a} ({n_t1a / n_scored:.0%}) |"
        if n_scored else f"| Top-1 eligible | {n_t1} | {n_t1a} |"
    )
    lines.append(
        f"| Top-1 Accuracy (all eligible) "
        f"| {report['top1_accuracy']:.1%} "
        f"| {report['top1_accuracy_any']:.1%} |"
    )
    lines.append(
        f"| Top-1 Accuracy (positives only) "
        f"| {report['positives_top1_accuracy']:.1%} "
        f"| {report['positives_top1_accuracy_any']:.1%} |"
    )
    lines.append(
        f"| Top-3 Coverage "
        f"| {report['top3_coverage']:.1%} "
        f"| {report['top3_coverage_any']:.1%} |"
    )
    lines.append(f"| Over-Alert Rate (healthy) | {report['over_alert_rate']:.1%} | — |")
    lines.append(f"| Hallucination Rate | skipped | skipped |")
    lines.append(f"| Parse Success Rate | skipped | skipped |")
    lines.append("")
    lines.append(
        "> **Primary-target**: KNN top-1 (or top-3) matches the profile's single primary GT condition.  "
        "Eligible only when that condition has KNN lab-group support.  "
        "Direct equivalent of `run_layer1_eval.py` metrics."
    )
    lines.append("")
    lines.append(
        "> **Any-label**: KNN top-1 (or top-3) matches *any* condition the user actually has "
        "(full `expected_conditions[]` set).  "
        "Eligible when at least one of their conditions is KNN-detectable.  "
        "Fairer for multi-condition profiles and for a layer whose job is to surface signal, "
        "not to rank a single winner."
    )
    lines.append("")

    # KNN coverage gaps
    uncovered = sorted(UNCOVERED_CONDITIONS)
    covered   = sorted(COVERED_CONDITIONS)
    lines.append("## KNN Coverage")
    lines.append("")
    lines.append(
        f"**Covered ({len(covered)}):** "
        + ", ".join(f"`{c}`" for c in covered)
    )
    lines.append("")
    lines.append(
        f"**Not covered ({len(uncovered)}) — always score 0:** "
        + ", ".join(f"`{c}`" for c in uncovered)
    )
    lines.append("")
    lines.append(
        "> Top-1 accuracy and Top-3 coverage are computed only over profiles whose "
        "ground-truth primary condition is in the covered set. "
        "Profiles targeting uncovered conditions are excluded from those denominators."
    )
    lines.append("")

    # By quiz path
    lines.append("## By Quiz Path")
    lines.append("")
    lines.append(
        "| Path | Top-1 (primary) | Top-1 (any-label) "
        "| Top-3 (primary) | Top-3 (any-label) | N |"
    )
    lines.append("|------|----------------|------------------|----------------|------------------|---|")
    for path, stats in report["by_quiz_path"].items():
        lines.append(
            f"| {path} "
            f"| {stats['top1_accuracy']:.1%} "
            f"| {stats['top1_accuracy_any']:.1%} "
            f"| {stats['top3_coverage']:.1%} "
            f"| {stats['top3_coverage_any']:.1%} "
            f"| {stats['n']} |"
        )
    lines.append("")

    # Per-condition: as target
    lines.append("## Per-Condition Metrics — As Target")
    lines.append("")
    lines.append(
        "> Positive set = profiles where this condition is the **primary target** "
        "and profile type is `positive`.  Matches `run_layer1_eval.py` definition exactly."
    )
    lines.append("")
    lines.append(
        "| Condition | KNN Lab Groups | N target+ | N flagged | Recall | Precision "
        "| Flag Rate | Mean Score |"
    )
    lines.append(
        "|-----------|---------------|-----------|-----------|--------|-----------|"
        "-----------|------------|"
    )
    for cond in sorted(report["per_condition"]):
        s = report["per_condition"][cond]
        groups_str  = ", ".join(s["lab_groups"]) if s["lab_groups"] else "—"
        recall_str  = f"{s['recall']:.1%}"    if s["recall"]    is not None else "—"
        prec_str    = f"{s['precision']:.1%}" if s["precision"] is not None else "—"
        score_str   = f"{s['mean_score']:.3f}" if s["mean_score"] is not None else "—"
        no_support  = " *(no KNN)*" if not s["has_knn_support"] else ""
        lines.append(
            f"| {cond}{no_support} | {groups_str} | {s['n_positive_target']} "
            f"| {s['n_flagged']} | {recall_str} | {prec_str} "
            f"| {s['flag_rate']:.1%} | {score_str} |"
        )
    lines.append("")

    # Per-condition: as any-label
    lines.append("## Per-Condition Metrics — As Any-Label")
    lines.append("")
    lines.append(
        "> Positive set = all non-healthy profiles where this condition appears "
        "**anywhere** in `expected_conditions[]` (primary or secondary).  "
        "Reflects whether KNN can detect the condition when it is clinically present, "
        "regardless of ranking priority."
    )
    lines.append("")
    lines.append(
        "| Condition | N any-label+ | N flagged | Recall | Precision | Flag Rate | Mean Score |"
    )
    lines.append(
        "|-----------|-------------|-----------|--------|-----------|-----------|------------|"
    )
    for cond in sorted(report["per_condition_any"]):
        s = report["per_condition_any"][cond]
        pc = report["per_condition"][cond]
        recall_str = f"{s['recall']:.1%}"    if s["recall"]    is not None else "—"
        prec_str   = f"{s['precision']:.1%}" if s["precision"] is not None else "—"
        score_str  = f"{s['mean_score']:.3f}" if s["mean_score"] is not None else "—"
        no_support = " *(no KNN)*" if not pc["has_knn_support"] else ""
        lines.append(
            f"| {cond}{no_support} | {s['n_any_label_positive']} "
            f"| {s['n_flagged']} | {recall_str} | {prec_str} "
            f"| {s['flag_rate']:.1%} | {score_str} |"
        )
    lines.append("")

    # Healthy false positives
    lines.append("## Healthy False Positives")
    lines.append("")
    lines.append("| Condition | KNN Lab Groups | Healthy Flagged | Healthy Flag Rate |")
    lines.append("|-----------|---------------|-----------------|-------------------|")
    for cond in sorted(report["healthy_per_condition"]):
        s  = report["healthy_per_condition"][cond]
        pc = report["per_condition"][cond]
        groups_str = ", ".join(pc["lab_groups"]) if pc["lab_groups"] else "—"
        lines.append(
            f"| {cond} | {groups_str} "
            f"| {s['n_healthy_flagged']} | {s['healthy_flag_rate']:.1%} |"
        )
    lines.append("")

    # Caveats
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "> **KNN coverage gaps** — The following conditions have no KNN lab-group support and will "
        "never be flagged by the KNN layer alone.  Their recall is structurally 0%, "
        "and they are excluded from top-1 / top-3 denominator calculations: "
        + ", ".join(f"`{c}`" for c in sorted(UNCOVERED_CONDITIONS)) + "."
    )
    lines.append("")
    lines.append(
        "> **Score interpretation** — KNN scores are raw lift-sum values (not probabilities). "
        "A score of 4.0 means the two supporting lab groups each had a neighbourhood lift "
        "of ~2.0×, just above the MIN_LIFT=2.0 gate.  Higher scores indicate stronger "
        "neighbourhood consensus.  Do not compare magnitudes directly to ML model "
        "probabilities in the layer1 report."
    )
    lines.append("")
    lines.append(
        "> **Anemia vs iron_deficiency** — Both conditions share the same lab groups "
        "(`cbc`, `iron_studies`).  KNN cannot distinguish between them from lab signals "
        "alone; they will always receive identical scores."
    )
    lines.append("")
    lines.append(
        "> **Hepatitis vs liver** — Both conditions rely solely on `liver_panel` signals. "
        "Same disambiguation limitation applies."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KNN-alone eval — no ML models, no Bayesian updating.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evals/run_knn_alone_eval.py
  python evals/run_knn_alone_eval.py --profiles evals/cohort/nhanes_balanced_760.json
  python evals/run_knn_alone_eval.py --n 100 --seed 7
        """,
    )
    parser.add_argument("--profiles", type=str, default=str(PROFILES_PATH),
                        help="Path to cohort profiles JSON")
    parser.add_argument("--n",    type=int, default=None,
                        help="Randomly sample N profiles")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None,
                        help="Override results output directory")
    return parser.parse_args()


def main() -> int:
    args          = _parse_args()
    profiles_path = Path(args.profiles)
    results_dir   = Path(args.output) if args.output else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load profiles
    loader = ProfileLoader(profiles_path, SCHEMA_PATH)
    try:
        profiles = loader.load_all()
        logger.info("Loaded %d profiles from %s", len(profiles), profiles_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    if not profiles:
        logger.error("No profiles found.")
        return 1

    if args.n is not None and args.n < len(profiles):
        rng      = random.Random(args.seed)
        profiles = rng.sample(profiles, args.n)
        logger.info("Sampled %d profiles (seed=%d)", args.n, args.seed)

    # Load KNNScorer once
    logger.info("Loading KNNScorer (7437-row NHANES index) …")
    try:
        scorer = KNNScorer()
    except Exception as exc:
        logger.error("Failed to load KNNScorer: %s", exc)
        return 1

    # Score profiles
    results: list[dict] = []
    n_errors = 0
    for i, profile in enumerate(profiles):
        if i % 100 == 0 and i > 0:
            logger.info("  %d / %d profiles scored …", i, len(profiles))

        scores  = _knn_score_profile(profile, scorer)
        result  = _eval_profile(profile, scores)
        results.append(result)
        if not result["scoring_success"]:
            n_errors += 1

    logger.info(
        "Scoring complete: %d/%d succeeded, %d errors",
        len(results) - n_errors, len(results), n_errors,
    )

    # Aggregate
    report = _aggregate(results)

    # Run metadata
    run_meta = {
        "git_sha":      _safe_git_sha(),
        "profiles_path": str(profiles_path),
    }

    # Print summary to stdout
    print()
    print("=" * 70)
    print(" KNN-Alone Eval Summary")
    print("=" * 70)
    print(f"  Profiles evaluated        : {report['n_profiles']}")
    print(f"  Scoring errors            : {report['n_scoring_errors']}")
    print(f"  {'Metric':<30}  {'Primary-target':>15}  {'Any-label':>10}")
    print("  " + "-" * 60)
    print(f"  {'Top-1 eligible':<30}  {report['n_top1_eligible']:>15}  {report['n_top1_eligible_any']:>10}")
    print(f"  {'Top-1 Accuracy (all)':<30}  {report['top1_accuracy']:>15.1%}  {report['top1_accuracy_any']:>10.1%}")
    print(f"  {'Top-1 Accuracy (pos only)':<30}  {report['positives_top1_accuracy']:>15.1%}  {report['positives_top1_accuracy_any']:>10.1%}")
    print(f"  {'Top-3 Coverage':<30}  {report['top3_coverage']:>15.1%}  {report['top3_coverage_any']:>10.1%}")
    print(f"  {'Over-Alert (healthy)':<30}  {report['over_alert_rate']:>15.1%}  {'—':>10}")
    print()
    print("  Per-Condition (as target):")
    print(f"  {'Condition':<25} {'N+':>4}  {'Recall':>7}  {'Prec':>7}  {'Flag%':>6}  {'Score':>6}")
    print("  " + "-" * 65)
    for cond in sorted(report["per_condition"]):
        s = report["per_condition"][cond]
        recall_s = f"{s['recall']:.1%}"    if s["recall"]    is not None else "  —   "
        prec_s   = f"{s['precision']:.1%}" if s["precision"] is not None else "  —   "
        score_s  = f"{s['mean_score']:.3f}" if s["mean_score"] is not None else "  — "
        print(
            f"  {cond:<25} {s['n_positive_target']:>4}  {recall_s:>7}  "
            f"{prec_s:>7}  {s['flag_rate']:.1%}  {score_s:>6}"
        )
    print("=" * 60)
    print()

    # Save results JSON and Markdown report
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id    = f"knn_alone_{timestamp}"

    results_path = results_dir / f"{run_id}.json"
    report_path  = REPORTS_DIR / f"{run_id}.md"

    results_path.write_text(
        json.dumps({"run_id": run_id, "run_metadata": run_meta, "report": report, "profiles": results}, indent=2)
    )
    report_path.write_text(_to_markdown(report, run_id, run_meta))

    logger.info("Results JSON : %s", results_path)
    logger.info("Report MD   : %s", report_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
