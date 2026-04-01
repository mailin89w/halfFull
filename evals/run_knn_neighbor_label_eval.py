#!/usr/bin/env python3
"""
run_knn_neighbor_label_eval.py — KNN neighbor-label evaluation.

Scores each profile by finding its 50 nearest NHANES neighbors (same cosine-distance
index as KNNScorer) and reading their **actual disease labels** from
nhanes_merged_adults_diseases.csv — instead of inferring conditions from the lab-signal
intermediary used in run_knn_alone_eval.py.

condition_score  = fraction of 50 neighbors carrying that disease label
condition_flagged = score ≥ 2 × population_prevalence  (lift ≥ 2, matching MIN_LIFT gate)

NHANES label → eval condition mapping
--------------------------------------
  anemia        → anemia, iron_deficiency  (no separate iron_def label; identical scores)
  diabetes      → prediabetes              (NHANES "diabetes" includes T2D + borderline)
  thyroid       → hypothyroidism           ← gains coverage vs lab-signal approach
  sleep_disorder→ sleep_disorder           ← gains coverage vs lab-signal approach
  kidney        → kidney_disease
  hepatitis_bc  → hepatitis
  liver         → liver
  menopause     → perimenopause            ← approximate; NHANES menopause ≠ perimenopause exactly

Still no label available (score = 0 always):
  electrolyte_imbalance, inflammation, vitamin_d_deficiency

Usage
-----
  python evals/run_knn_neighbor_label_eval.py
  python evals/run_knn_neighbor_label_eval.py --n 100 --seed 7
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import random
import subprocess
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_distances

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
    from run_layer1_eval import (
        CONDITION_TO_MODEL_KEY,
        _build_raw_inputs,
        _build_raw_inputs_from_nhanes,
    )
except ImportError as exc:
    print(f"ERROR: Could not import helpers from run_layer1_eval.py: {exc}", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROFILES_PATH  = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"
SCHEMA_PATH    = EVALS_DIR / "schema"  / "profile_schema.json"
RESULTS_DIR    = EVALS_DIR / "results"
REPORTS_DIR    = EVALS_DIR / "reports"
KNN_PKG_PATH   = PROJECT_ROOT / "data/processed/cluster/artifacts/knn_inference_pkg.pkl"
DISEASES_PATH  = PROJECT_ROOT / "data/processed/nhanes_merged_adults_diseases.csv"

KNN_K = 50

# ---------------------------------------------------------------------------
# Per-condition flag thresholds
# ---------------------------------------------------------------------------
# Each threshold is set to the first discrete neighbor-fraction value that lies
# ABOVE the 95th percentile of healthy-profile scores, calibrated on the 760-
# profile cohort.  This keeps per-condition healthy FP rate ≤ ~5% and lets the
# recall numbers honestly reflect whether the KNN has any discriminative signal.
#
# Derivation (healthy P95 → threshold):
#   anemia         P95=0.060 → 0.16   (next discrete value; only 1% of healthy reach it)
#   hepatitis      P95=0.060 → 0.12   (healthy: 98% at 0.06, 1% at 0.10, 1% at 0.12)
#   hypothyroidism P95=0.100 → 0.12   (1% of healthy at 0.12)
#   iron_deficiency→ 0.16   (shares anemia label — identical distribution)
#   kidney_disease P95=0.060 → 0.16   (99% at 0.06, one 0.26 outlier)
#   liver          P95=0.100 → 0.10   (no discrete step above 0.10 exists; best available)
#   perimenopause  P95=0.260 → 0.44   (healthy max=0.26; positive-only zone ≥ 0.46)
#   prediabetes    P95=0.360 → 0.40   (healthy P99=0.38, one outlier at 0.44)
#   sleep_disorder P95=0.420 → 0.45   (NO signal: positive max=0.42, healthy max=0.44 — disabled)
#
# Note: liver is the only condition with meaningful separation.  All others have
# fully or near-fully overlapping healthy/positive distributions at these thresholds.
CONDITION_THRESHOLDS: dict[str, float] = {
    "anemia":            0.16,
    "hepatitis":         0.12,
    "hypothyroidism":    0.12,
    "iron_deficiency":   0.16,
    "kidney_disease":    0.16,
    "liver":             0.10,
    "perimenopause":     0.44,
    "prediabetes":       0.40,
    "sleep_disorder":    0.45,   # effectively disabled — distributions inverted
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_knn_neighbor_label_eval")

# ---------------------------------------------------------------------------
# NHANES disease label → eval condition(s) mapping
# ---------------------------------------------------------------------------

# label_col → list of eval condition IDs it covers
LABEL_TO_EVAL_CONDITIONS: dict[str, list[str]] = {
    "anemia":         ["anemia", "iron_deficiency"],  # no separate iron_def label
    "diabetes":       ["prediabetes"],
    "thyroid":        ["hypothyroidism"],
    "sleep_disorder": ["sleep_disorder"],
    "kidney":         ["kidney_disease"],
    "hepatitis_bc":   ["hepatitis"],
    "liver":          ["liver"],
    "menopause":      ["perimenopause"],
}

# eval condition → its source NHANES label column (reverse map, one-to-one)
EVAL_CONDITION_TO_LABEL: dict[str, str | None] = {}
for label, conds in LABEL_TO_EVAL_CONDITIONS.items():
    for c in conds:
        EVAL_CONDITION_TO_LABEL[c] = label

EVAL_CONDITIONS: tuple[str, ...] = tuple(CONDITION_TO_MODEL_KEY.keys())

# Conditions with no NHANES label — always score 0
LABEL_COLS = list(LABEL_TO_EVAL_CONDITIONS.keys())
COVERED_CONDITIONS: frozenset[str] = frozenset(EVAL_CONDITION_TO_LABEL.keys())
UNCOVERED_CONDITIONS: frozenset[str] = frozenset(EVAL_CONDITIONS) - COVERED_CONDITIONS

# Conditions that share the same NHANES label — identical scores by construction
SHARED_LABEL_GROUPS: list[list[str]] = [
    conds for conds in LABEL_TO_EVAL_CONDITIONS.values() if len(conds) > 1
]


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
# Load artifacts
# ---------------------------------------------------------------------------

def load_knn_index() -> dict:
    """Load the KNN inference package (index, imputer, anchor_cols)."""
    logger.info("Loading KNN inference package from %s …", KNN_PKG_PATH)
    with open(KNN_PKG_PATH, "rb") as f:
        pkg = pickle.load(f)
    logger.info(
        "KNN index loaded: %d rows × %d anchor features",
        pkg["X_index"].shape[0], pkg["X_index"].shape[1],
    )
    return pkg


def load_disease_labels(pkg: dict) -> tuple[np.ndarray, dict[str, float]]:
    """
    Load binary disease labels for every SEQN in the KNN index.

    Returns
    -------
    label_matrix : ndarray of shape (n_index_rows, n_label_cols)
        Rows are in the same order as pkg["index_seqns"].
    population_prevalence : dict  label_col → float  (fraction with label=1)
    """
    logger.info("Loading disease labels from %s …", DISEASES_PATH)
    df = pd.read_csv(DISEASES_PATH, usecols=["SEQN"] + LABEL_COLS, low_memory=False)
    df = df.set_index("SEQN")

    index_seqns = pkg["index_seqns"]

    # Align: reindex to KNN index order (fill missing with 0)
    df_aligned = df.reindex(index_seqns, fill_value=0)

    label_matrix = df_aligned[LABEL_COLS].values.astype(np.float32)  # (N, n_labels)
    population_prevalence = {col: float(df[col].mean()) for col in LABEL_COLS}

    logger.info(
        "Disease labels loaded. %d rows, %d conditions. Coverage: %d/%d SEQNs aligned.",
        label_matrix.shape[0], label_matrix.shape[1],
        df_aligned.notna().all(axis=1).sum(), len(index_seqns),
    )
    for col, rate in population_prevalence.items():
        logger.debug("  %-20s prevalence=%.3f", col, rate)

    return label_matrix, population_prevalence


# ---------------------------------------------------------------------------
# Per-profile scoring
# ---------------------------------------------------------------------------

def _build_user_vector(
    raw_inputs: dict,
    anchor_cols: list[str],
    imputer: Any,
) -> np.ndarray | None:
    """Build the imputed anchor-feature vector for a profile."""
    row = []
    n_present = 0
    for col in anchor_cols:
        val = raw_inputs.get(col)
        if val is not None:
            try:
                row.append(float(val))
                n_present += 1
            except (TypeError, ValueError):
                row.append(np.nan)
        else:
            row.append(np.nan)

    if n_present < 5:
        return None   # too few anchor features to place user meaningfully

    arr = np.array(row, dtype=float).reshape(1, -1)
    return imputer.transform(arr)


def _knn_score_profile(
    profile: dict,
    pkg: dict,
    label_matrix: np.ndarray,
    population_prevalence: dict[str, float],
) -> dict[str, float] | None:
    """
    Find 50 nearest NHANES neighbors and score conditions by neighbor label fraction.

    score = fraction of 50 neighbors with that disease label (0.0–1.0)
    A condition is considered "flagged" when score ≥ MIN_LIFT × population_prevalence.
    """
    try:
        if "nhanes_inputs" in profile:
            raw_inputs = _build_raw_inputs_from_nhanes(profile)
        else:
            raw_inputs = _build_raw_inputs(profile)
    except Exception as exc:
        logger.warning("Input construction failed for %s: %s",
                       profile.get("profile_id", "?"), exc)
        return None

    user_vec = _build_user_vector(raw_inputs, pkg["anchor_cols"], pkg["imputer"])
    if user_vec is None:
        logger.debug("Insufficient anchor features for %s", profile.get("profile_id", "?"))
        return None

    # Find k nearest neighbors
    dists    = cosine_distances(user_vec, pkg["X_index"])[0]   # (N,)
    top_k    = np.argsort(dists)[:KNN_K]                       # (k,) indices
    nb_labels = label_matrix[top_k]                            # (k, n_labels)

    # neighbor_fraction per label
    nb_fractions: dict[str, float] = {
        col: float(nb_labels[:, i].mean())
        for i, col in enumerate(LABEL_COLS)
    }

    # Map to eval condition scores
    scores: dict[str, float] = {}
    for eval_cond in EVAL_CONDITIONS:
        label_col = EVAL_CONDITION_TO_LABEL.get(eval_cond)
        if label_col is None:
            scores[eval_cond] = 0.0
        else:
            scores[eval_cond] = round(nb_fractions[label_col], 4)

    return scores


def _is_flagged(
    score: float,
    eval_cond: str,
) -> bool:
    """Flag a condition when its neighbor fraction meets the calibrated threshold."""
    threshold = CONDITION_THRESHOLDS.get(eval_cond)
    if threshold is None:
        return False   # uncovered condition — no threshold defined
    return score >= threshold


# ---------------------------------------------------------------------------
# Profile eval
# ---------------------------------------------------------------------------

def _eval_profile(
    profile: dict,
    scores: dict[str, float] | None,
    population_prevalence: dict[str, float],
) -> dict:
    """Compare KNN neighbor-label scores against ground truth for a single profile."""
    pid              = profile.get("profile_id", "")
    ptype            = profile.get("profile_type", "")
    target_condition = profile.get("target_condition")
    quiz_path        = profile.get("quiz_path", "hybrid")

    ground_truth      = profile.get("ground_truth", {})
    expected          = ground_truth.get("expected_conditions", [])
    gt_primary        = expected[0]["condition_id"] if expected else None
    gt_all_conditions = frozenset(item["condition_id"] for item in expected)

    null_result = {
        "profile_id":           pid,
        "profile_type":         ptype,
        "target_condition":     target_condition,
        "quiz_path":            quiz_path,
        "scoring_success":      False,
        "knn_top1":             None,
        "knn_top1_score":       None,
        "top1_correct":         None,
        "top3_hit":             None,
        "top1_correct_any":     None,
        "top3_hit_any":         None,
        "ground_truth_primary": gt_primary,
        "gt_all_conditions":    sorted(gt_all_conditions),
        "scores":               {},
        "flagged":              [],
    }

    if scores is None:
        return null_result

    # Flagged conditions (calibrated per-condition threshold)
    flagged_set = frozenset(
        cond for cond in EVAL_CONDITIONS
        if _is_flagged(scores.get(cond, 0.0), cond)
    )

    # Rank only covered conditions with score > 0 to avoid spurious wins
    active = sorted(
        ((c, v) for c, v in scores.items() if c in COVERED_CONDITIONS and v > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    top1 = active[0][0] if active else None
    top3 = frozenset(c for c, _ in active[:3])

    # Primary-target view
    if gt_primary is not None and gt_primary in COVERED_CONDITIONS:
        top1_correct: bool | None = (top1 == gt_primary) if active else False
        top3_hit: bool | None     = gt_primary in top3
    else:
        top1_correct = None
        top3_hit     = None

    # Any-label view
    covered_gt = gt_all_conditions & COVERED_CONDITIONS
    if covered_gt:
        top1_correct_any: bool | None = (top1 in gt_all_conditions) if active else False
        top3_hit_any: bool | None     = bool(top3 & gt_all_conditions)
    else:
        top1_correct_any = None
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
        "flagged":              sorted(flagged_set),
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(
    results: list[dict],
    population_prevalence: dict[str, float],
) -> dict:
    """Compute cohort-level metrics from per-profile eval dicts."""
    scored  = [r for r in results if r["scoring_success"]]
    healthy = [r for r in scored  if r.get("profile_type") == "healthy"]

    # ── top1 / top3 — primary-target view ─────────────────────────────────
    top1_eligible = [r for r in scored if r.get("top1_correct") is not None]
    top1_correct  = sum(1 for r in top1_eligible if r["top1_correct"])
    top1_accuracy = top1_correct / len(top1_eligible) if top1_eligible else 0.0

    pos_eligible = [r for r in top1_eligible if r.get("profile_type") == "positive"]
    pos_correct  = sum(1 for r in pos_eligible if r["top1_correct"])
    pos_top1_acc = pos_correct / len(pos_eligible) if pos_eligible else 0.0

    top3_eligible = [r for r in scored if r.get("top3_hit") is not None]
    top3_hits     = sum(1 for r in top3_eligible if r["top3_hit"])
    top3_coverage = top3_hits / len(top3_eligible) if top3_eligible else 0.0

    # ── top1 / top3 — any-label view ──────────────────────────────────────
    top1_eligible_any = [r for r in scored if r.get("top1_correct_any") is not None]
    top1_correct_any  = sum(1 for r in top1_eligible_any if r["top1_correct_any"])
    top1_accuracy_any = top1_correct_any / len(top1_eligible_any) if top1_eligible_any else 0.0

    pos_eligible_any = [r for r in top1_eligible_any if r.get("profile_type") == "positive"]
    pos_correct_any  = sum(1 for r in pos_eligible_any if r["top1_correct_any"])
    pos_top1_acc_any = pos_correct_any / len(pos_eligible_any) if pos_eligible_any else 0.0

    top3_eligible_any = [r for r in scored if r.get("top3_hit_any") is not None]
    top3_hits_any     = sum(1 for r in top3_eligible_any if r["top3_hit_any"])
    top3_coverage_any = top3_hits_any / len(top3_eligible_any) if top3_eligible_any else 0.0

    # ── over_alert_rate ────────────────────────────────────────────────────
    # A healthy profile is over-alerted if ANY condition is flagged (lift ≥ 2)
    over_alerted    = sum(1 for r in healthy if r.get("flagged"))
    over_alert_rate = over_alerted / len(healthy) if healthy else 0.0

    # ── by quiz path ───────────────────────────────────────────────────────
    by_quiz_path: dict[str, dict] = {}
    for path in ("full", "hybrid"):
        pt1  = [r for r in top1_eligible     if r.get("quiz_path") == path]
        pt3  = [r for r in top3_eligible     if r.get("quiz_path") == path]
        pt1a = [r for r in top1_eligible_any if r.get("quiz_path") == path]
        pt3a = [r for r in top3_eligible_any if r.get("quiz_path") == path]
        by_quiz_path[path] = {
            "top1_accuracy":     sum(1 for r in pt1 if r["top1_correct"]) / len(pt1)   if pt1  else 0.0,
            "top3_coverage":     sum(1 for r in pt3 if r["top3_hit"])     / len(pt3)   if pt3  else 0.0,
            "top1_accuracy_any": sum(1 for r in pt1a if r["top1_correct_any"]) / len(pt1a) if pt1a else 0.0,
            "top3_coverage_any": sum(1 for r in pt3a if r["top3_hit_any"])     / len(pt3a) if pt3a else 0.0,
            "n": len([r for r in scored if r.get("quiz_path") == path]),
        }

    # ── per-condition metrics ──────────────────────────────────────────────
    per_condition:         dict[str, dict] = {}
    per_condition_any:     dict[str, dict] = {}
    healthy_per_condition: dict[str, dict] = {}

    for eval_cond in EVAL_CONDITIONS:
        label_col   = EVAL_CONDITION_TO_LABEL.get(eval_cond)
        has_support = label_col is not None
        pop_rate    = population_prevalence.get(label_col, 0.0) if label_col else 0.0
        cond_thresh = CONDITION_THRESHOLDS.get(eval_cond)

        # Flagged = score ≥ calibrated threshold
        flagged = [
            r for r in scored
            if _is_flagged(r.get("scores", {}).get(eval_cond, 0.0), eval_cond)
        ]
        healthy_flagged = [
            r for r in healthy
            if _is_flagged(r.get("scores", {}).get(eval_cond, 0.0), eval_cond)
        ]
        flag_rate = len(flagged) / len(scored) if scored else 0.0

        # ---- AS TARGET ----
        target_profiles = [r for r in scored if r.get("target_condition") == eval_cond]
        positive_target = [r for r in target_profiles if r.get("profile_type") == "positive"]

        tp_target   = [r for r in flagged
                       if r.get("target_condition") == eval_cond and r.get("profile_type") == "positive"]
        recall_t    = len(tp_target) / len(positive_target) if positive_target else None
        precision_t = len(tp_target) / len(flagged)         if flagged         else None

        target_scores = [r["scores"].get(eval_cond, 0.0) for r in positive_target if r.get("scores")]
        mean_score_t  = float(np.mean(target_scores)) if target_scores else None

        per_condition[eval_cond] = {
            "has_label":         has_support,
            "label_col":         label_col,
            "population_rate":   round(pop_rate, 4),
            "flag_threshold":    round(cond_thresh, 4) if cond_thresh is not None else None,
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
        any_label_pos = [
            r for r in scored
            if eval_cond in r.get("gt_all_conditions", [])
            and r.get("profile_type") != "healthy"
        ]
        tp_any        = [r for r in flagged if eval_cond in r.get("gt_all_conditions", [])]
        recall_any    = len(tp_any) / len(any_label_pos) if any_label_pos else None
        precision_any = len(tp_any) / len(flagged)       if flagged       else None

        any_scores     = [r["scores"].get(eval_cond, 0.0) for r in any_label_pos if r.get("scores")]
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
        "n_top1_eligible":             len(top1_eligible),
        "n_top3_eligible":             len(top3_eligible),
        "top1_accuracy":               round(top1_accuracy, 4),
        "positives_top1_accuracy":     round(pos_top1_acc,  4),
        "top3_coverage":               round(top3_coverage,  4),
        "n_top1_eligible_any":         len(top1_eligible_any),
        "n_top3_eligible_any":         len(top3_eligible_any),
        "top1_accuracy_any":           round(top1_accuracy_any, 4),
        "positives_top1_accuracy_any": round(pos_top1_acc_any,  4),
        "top3_coverage_any":           round(top3_coverage_any,  4),
        "over_alert_rate":             round(over_alert_rate, 4),
        "by_quiz_path":                by_quiz_path,
        "per_condition":               per_condition,
        "per_condition_any":           per_condition_any,
        "healthy_per_condition":       healthy_per_condition,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _to_markdown(
    report: dict,
    run_id: str,
    run_meta: dict,
    population_prevalence: dict[str, float],
) -> str:
    lines: list[str] = []
    n_scored = report["n_scored"]

    lines.append(f"# HalfFull KNN Neighbor-Label Eval — {run_id}")
    lines.append("")
    lines.append(
        "> KNN neighbor disease-label voting. No ML models. No Bayesian updating.  "
        "Condition score = fraction of 50 nearest NHANES neighbors carrying that disease label."
    )
    lines.append("")

    # Metadata
    lines.append("## Run Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Git SHA | {run_meta.get('git_sha') or 'unknown'} |")
    lines.append(f"| Profiles Path | `{run_meta.get('profiles_path', '')}` |")
    lines.append(f"| KNN index | cosine-NN, k={KNN_K}, NHANES {report['n_scored']}-profile anchor |")
    lines.append(f"| Condition score | fraction of {KNN_K} neighbors with disease label = 1 |")
    lines.append(f"| Flag threshold | per-condition calibrated threshold (see table below) |")
    lines.append("")

    # NHANES label mapping
    lines.append("## NHANES Label → Eval Condition Mapping")
    lines.append("")
    lines.append("| NHANES label | Eval condition(s) | Pop. prevalence | Flag threshold |")
    lines.append("|-------------|------------------|----------------|----------------|")
    for label, conds in LABEL_TO_EVAL_CONDITIONS.items():
        pop_rate = population_prevalence.get(label, 0.0)
        note     = " *(approx)*" if label == "menopause" else ""
        note     = " *(shared label)*" if len(conds) > 1 else note
        thresh_parts = []
        for c in conds:
            t = CONDITION_THRESHOLDS.get(c)
            if t is not None:
                thresh_parts.append(f"≥ {t:.0%}")
        thresh_str = ", ".join(thresh_parts) if thresh_parts else "—"
        lines.append(
            f"| `{label}` | "
            + ", ".join(f"`{c}`" for c in conds)
            + f"{note} | {pop_rate:.1%} | {thresh_str} |"
        )
    uncovered_eval = sorted(UNCOVERED_CONDITIONS)
    lines.append(
        f"| *no label* | "
        + ", ".join(f"`{c}`" for c in uncovered_eval)
        + " | — | — |"
    )
    lines.append("")

    # Summary
    n_t1  = report["n_top1_eligible"]
    n_t1a = report["n_top1_eligible_any"]
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Primary-target | Any-label |")
    lines.append("|--------|---------------|-----------|")
    lines.append(f"| Profiles evaluated | {report['n_profiles']} | — |")
    lines.append(f"| Profiles scored    | {report['n_scored']} | — |")
    lines.append(f"| Scoring errors     | {report['n_scoring_errors']} | — |")
    lines.append(
        f"| Top-1 eligible (label-covered GT) "
        f"| {n_t1} ({n_t1 / n_scored:.0%}) "
        f"| {n_t1a} ({n_t1a / n_scored:.0%}) |"
        if n_scored else f"| Top-1 eligible | {n_t1} | {n_t1a} |"
    )
    lines.append(
        f"| Top-1 Accuracy (all eligible) "
        f"| {report['top1_accuracy']:.1%} | {report['top1_accuracy_any']:.1%} |"
    )
    lines.append(
        f"| Top-1 Accuracy (positives only) "
        f"| {report['positives_top1_accuracy']:.1%} | {report['positives_top1_accuracy_any']:.1%} |"
    )
    lines.append(
        f"| Top-3 Coverage "
        f"| {report['top3_coverage']:.1%} | {report['top3_coverage_any']:.1%} |"
    )
    lines.append(f"| Over-Alert Rate (healthy) | {report['over_alert_rate']:.1%} | — |")
    lines.append(f"| Hallucination Rate | skipped | skipped |")
    lines.append(f"| Parse Success Rate | skipped | skipped |")
    lines.append("")
    lines.append(
        "> **Primary-target**: KNN top-1 (or top-3) matches the profile's single primary GT condition. "
        "Eligible only when that condition has a NHANES disease label.  "
        "Direct equivalent of `run_layer1_eval.py` metrics."
    )
    lines.append("")
    lines.append(
        "> **Any-label**: KNN top-1 (or top-3) matches *any* condition the user actually has "
        "(full `expected_conditions[]`).  Eligible when at least one of their conditions has a label."
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
        "and profile type is `positive`.  Matches `run_layer1_eval.py` definition."
    )
    lines.append("")
    lines.append(
        "| Condition | NHANES Label | Pop. Prevalence | Flag Threshold "
        "| N target+ | N flagged | Recall | Precision | Flag Rate | Mean Score |"
    )
    lines.append(
        "|-----------|-------------|----------------|---------------|"
        "-----------|-----------|--------|-----------|-----------|------------|"
    )
    for cond in sorted(report["per_condition"]):
        s         = report["per_condition"][cond]
        label_str = f"`{s['label_col']}`" if s["label_col"] else "—"
        thresh_s  = f"{s['flag_threshold']:.0%}" if s["flag_threshold"] is not None else "—"
        pop_s     = f"{s['population_rate']:.1%}"
        recall_s  = f"{s['recall']:.1%}"    if s["recall"]    is not None else "—"
        prec_s    = f"{s['precision']:.1%}" if s["precision"] is not None else "—"
        score_s   = f"{s['mean_score']:.3f}" if s["mean_score"] is not None else "—"
        no_lbl    = " *(no label)*" if not s["has_label"] else ""
        lines.append(
            f"| {cond}{no_lbl} | {label_str} | {pop_s} | {thresh_s} "
            f"| {s['n_positive_target']} | {s['n_flagged']} "
            f"| {recall_s} | {prec_s} | {s['flag_rate']:.1%} | {score_s} |"
        )
    lines.append("")

    # Per-condition: as any-label
    lines.append("## Per-Condition Metrics — As Any-Label")
    lines.append("")
    lines.append(
        "> Positive set = all non-healthy profiles where this condition appears "
        "**anywhere** in `expected_conditions[]`."
    )
    lines.append("")
    lines.append(
        "| Condition | N any-label+ | N flagged | Recall | Precision | Flag Rate | Mean Score |"
    )
    lines.append(
        "|-----------|-------------|-----------|--------|-----------|-----------|------------|"
    )
    for cond in sorted(report["per_condition_any"]):
        s      = report["per_condition_any"][cond]
        pc     = report["per_condition"][cond]
        recall_s = f"{s['recall']:.1%}"    if s["recall"]    is not None else "—"
        prec_s   = f"{s['precision']:.1%}" if s["precision"] is not None else "—"
        score_s  = f"{s['mean_score']:.3f}" if s["mean_score"] is not None else "—"
        no_lbl   = " *(no label)*" if not pc["has_label"] else ""
        lines.append(
            f"| {cond}{no_lbl} | {s['n_any_label_positive']} "
            f"| {s['n_flagged']} | {recall_s} | {prec_s} "
            f"| {s['flag_rate']:.1%} | {score_s} |"
        )
    lines.append("")

    # Healthy false positives
    lines.append("## Healthy False Positives")
    lines.append("")
    lines.append("| Condition | NHANES Label | Flag Threshold | Healthy Flagged | Healthy Flag Rate |")
    lines.append("|-----------|-------------|---------------|-----------------|-------------------|")
    for cond in sorted(report["healthy_per_condition"]):
        s  = report["healthy_per_condition"][cond]
        pc = report["per_condition"][cond]
        lbl_s    = f"`{pc['label_col']}`" if pc["label_col"] else "—"
        thresh_s = f"{pc['flag_threshold']:.0%}" if pc["flag_threshold"] is not None else "—"
        lines.append(
            f"| {cond} | {lbl_s} | {thresh_s} "
            f"| {s['n_healthy_flagged']} | {s['healthy_flag_rate']:.1%} |"
        )
    lines.append("")

    # Caveats
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "> **No NHANES label** — The following conditions have no binary label in "
        "`nhanes_merged_adults_diseases.csv` and always score 0. "
        "Excluded from top-1 / top-3 denominators: "
        + ", ".join(f"`{c}`" for c in sorted(UNCOVERED_CONDITIONS)) + "."
    )
    lines.append("")
    for group in SHARED_LABEL_GROUPS:
        conds_str = " and ".join(f"`{c}`" for c in sorted(group))
        lines.append(
            f"> **Shared label** — {conds_str} both map to the same NHANES label and will "
            f"always receive identical scores. KNN label voting cannot distinguish between them."
        )
        lines.append("")
    lines.append(
        "> **`menopause` → `perimenopause`** — The NHANES `menopause` label (prevalence 17.1%) "
        "covers all post-menopausal women, which is broader than the product's `perimenopause` "
        "definition (females 35–55 with irregular periods). "
        "Expect inflated recall and potentially inflated false-positive rates on younger profiles."
    )
    lines.append("")
    lines.append(
        "> **`diabetes` → `prediabetes`** — The NHANES `diabetes` label (prevalence 22.1%) "
        "includes both type-2 diabetes and borderline cases. "
        "Neighbor-fraction scores for `prediabetes` reflect the full diabetes+prediabetes "
        "spectrum, not just the pre-diabetic subgroup."
    )
    lines.append("")
    lines.append(
        "> **Score interpretation** — Scores are raw neighbor fractions (0.0–1.0), not "
        "probabilities. A score of 0.10 means 5 of 50 nearest NHANES neighbors carry that label. "
        "Do not compare magnitudes directly to ML model probabilities in the layer1 report."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KNN neighbor-label eval — score conditions from neighbor disease labels.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--profiles", type=str, default=str(PROFILES_PATH))
    parser.add_argument("--n",    type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    return parser.parse_args()


def main() -> int:
    args          = _parse_args()
    profiles_path = Path(args.profiles)
    results_dir   = Path(args.output) if args.output else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load artifacts
    pkg = load_knn_index()
    label_matrix, population_prevalence = load_disease_labels(pkg)

    # Load profiles
    loader = ProfileLoader(profiles_path, SCHEMA_PATH)
    try:
        profiles = loader.load_all()
        logger.info("Loaded %d profiles from %s", len(profiles), profiles_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    if args.n is not None and args.n < len(profiles):
        rng      = random.Random(args.seed)
        profiles = rng.sample(profiles, args.n)
        logger.info("Sampled %d profiles (seed=%d)", args.n, args.seed)

    # Score
    results: list[dict] = []
    n_errors = 0
    for i, profile in enumerate(profiles):
        if i % 100 == 0 and i > 0:
            logger.info("  %d / %d profiles scored …", i, len(profiles))

        scores  = _knn_score_profile(profile, pkg, label_matrix, population_prevalence)
        result  = _eval_profile(profile, scores, population_prevalence)
        results.append(result)
        if not result["scoring_success"]:
            n_errors += 1

    logger.info("Scoring complete: %d/%d succeeded, %d errors",
                len(results) - n_errors, len(results), n_errors)

    report   = _aggregate(results, population_prevalence)
    run_meta = {"git_sha": _safe_git_sha(), "profiles_path": str(profiles_path)}

    # Stdout summary
    print()
    print("=" * 70)
    print(" KNN Neighbor-Label Eval Summary")
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
    print(f"  {'Condition':<25} {'Label':<15} {'Pop%':>5}  {'Thr%':>5}  {'N+':>4}  {'Recall':>7}  {'Prec':>7}  {'Flag%':>6}  {'Score':>6}")
    print("  " + "-" * 90)
    for cond in sorted(report["per_condition"]):
        s       = report["per_condition"][cond]
        lbl     = s["label_col"] or "—"
        pop_s   = f"{s['population_rate']:.1%}"
        thr_s   = f"{s['flag_threshold']:.0%}" if s["flag_threshold"] is not None else "  —  "
        recall_s = f"{s['recall']:.1%}"    if s["recall"]    is not None else "  —   "
        prec_s   = f"{s['precision']:.1%}" if s["precision"] is not None else "  —   "
        score_s  = f"{s['mean_score']:.3f}" if s["mean_score"] is not None else "  —  "
        print(
            f"  {cond:<25} {lbl:<15} {pop_s:>5}  {thr_s:>5}  {s['n_positive_target']:>4}  "
            f"{recall_s:>7}  {prec_s:>7}  {s['flag_rate']:.1%}  {score_s:>6}"
        )
    print("=" * 70)
    print()

    # Save
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id    = f"knn_neighbor_label_{timestamp}"

    results_path = results_dir / f"{run_id}.json"
    report_path  = REPORTS_DIR / f"{run_id}.md"

    results_path.write_text(
        json.dumps({"run_id": run_id, "run_metadata": run_meta, "report": report, "profiles": results}, indent=2)
    )
    report_path.write_text(_to_markdown(report, run_id, run_meta, population_prevalence))

    logger.info("Results JSON : %s", results_path)
    logger.info("Report MD   : %s", report_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
