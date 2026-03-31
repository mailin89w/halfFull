"""
audit_kidney_fps.py
--------------------
ML-KIDNEY-02 — Step 1: False-Positive Audit

Loads the current production kidney v2 model, scores every profile in the
760-cohort at the live threshold (0.35), then classifies each false positive
into one of four buckets:

  healthy       — no conditions at all
  metabolic     — prediabetes, iron_deficiency, vitamin_d_deficiency
  hypertensive  — electrolyte_imbalance, cardiovascular overlap patterns
  other         — everything else (hypothyroidism, sleep_disorder, etc.)

Outputs:
  results/kidney_fp_audit.json   — raw per-profile FP records
  results/kidney_fp_summary.md   — human-readable breakdown table
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

import logging
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_MODELS_DIR = _ROOT / "models_normalized"
sys.path.insert(0, str(_MODELS_DIR))

COHORT_PATH = _ROOT / "evals" / "cohort" / "nhanes_balanced_760.json"
RESULTS_DIR = _HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

KIDNEY_THRESHOLD = 0.35  # live USER_FACING_THRESHOLD

# Condition buckets for FP classification
METABOLIC_CONDITIONS = {
    "prediabetes", "iron_deficiency", "vitamin_d_deficiency", "anemia",
}
HYPERTENSIVE_CONDITIONS = {
    "electrolyte_imbalance", "cardiovascular",
}


def classify_fp(expected_conditions: list[str]) -> str:
    """Return one of: healthy | metabolic | hypertensive | other."""
    conds = set(c.lower() for c in expected_conditions)
    if not conds:
        return "healthy"
    if conds & HYPERTENSIVE_CONDITIONS:
        return "hypertensive"
    if conds & METABOLIC_CONDITIONS:
        return "metabolic"
    return "other"


def load_cohort(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("profiles", [])


def get_expected_conditions(profile: dict) -> list[str]:
    """Read condition_ids from ground_truth (canonical location in 760-cohort)."""
    gt = profile.get("ground_truth", {})
    return [c["condition_id"] for c in gt.get("expected_conditions", [])]


def main():
    from model_runner import ModelRunner

    print("=" * 60)
    print("  Kidney FP Audit  (ML-KIDNEY-02)")
    print("=" * 60)

    profiles = load_cohort(COHORT_PATH)
    print(f"Loaded {len(profiles)} profiles from 760-cohort")

    runner = ModelRunner()

    fp_records = []
    all_kidney_scores = []

    normalizer = runner._get_normalizer()

    for profile in profiles:
        raw_inputs = profile.get("nhanes_inputs", {})
        # Conditions live in ground_truth in the 760-cohort
        expected = get_expected_conditions(profile)

        try:
            feature_vectors = normalizer.build_feature_vectors(raw_inputs)
            scores = runner.run_all_with_context(
                feature_vectors,
                patient_context={"gender": raw_inputs.get("gender"), "age_years": raw_inputs.get("age_years")},
            )
        except Exception as exc:
            print(f"  WARN: scoring failed for profile {profile.get('id', '?')}: {exc}")
            continue

        kidney_score = scores.get("kidney", 0.0)
        all_kidney_scores.append(kidney_score)

        # Match baseline: only profile_type=="positive" with target_condition=="kidney_disease"
        is_kidney_positive = (
            profile.get("target_condition") == "kidney_disease"
            and profile.get("profile_type") == "positive"
        )
        fires = kidney_score >= KIDNEY_THRESHOLD

        if fires and not is_kidney_positive:
            fp_records.append({
                "profile_id":          profile.get("profile_id", "unknown"),
                "profile_type":        profile.get("profile_type", "unknown"),
                "target_condition":    profile.get("target_condition", "none"),
                "kidney_score":        round(kidney_score, 4),
                "expected_conditions": expected,
                "fp_bucket":           classify_fp(expected),
                "n_conditions":        len(expected),
            })

    # ── Summary stats ────────────────────────────────────────────────────────
    bucket_counts = Counter(r["fp_bucket"] for r in fp_records)
    bucket_details: dict[str, list[str]] = defaultdict(list)
    for r in fp_records:
        bucket_details[r["fp_bucket"]].append(
            f"  score={r['kidney_score']:.3f}  conds={r['expected_conditions']}"
        )

    total_profiles  = len(profiles)
    total_fps       = len(fp_records)
    fp_rate         = total_fps / total_profiles if total_profiles else 0
    mean_score_all  = float(np.mean(all_kidney_scores)) if all_kidney_scores else 0
    pct_above_thr   = sum(1 for s in all_kidney_scores if s >= KIDNEY_THRESHOLD) / len(all_kidney_scores) if all_kidney_scores else 0

    print(f"\nOverall flag rate  : {pct_above_thr:.1%} ({int(pct_above_thr * total_profiles)}/{total_profiles})")
    print(f"Total FPs          : {total_fps}  ({fp_rate:.1%})")
    print(f"Mean kidney score  : {mean_score_all:.4f}")
    print(f"\nFP Buckets:")
    for bucket, count in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        pct = count / total_fps * 100 if total_fps else 0
        print(f"  {bucket:<14} {count:>3}  ({pct:.0f}%)")

    # ── Bucket detail: most common confounders ───────────────────────────────
    print("\nTop confounding conditions (non-kidney, high-scoring):")
    confounder_counter: Counter = Counter()
    for r in fp_records:
        for c in r["expected_conditions"]:
            if c.lower() not in {"kidney", "kidney_disease", "ckd"}:
                confounder_counter[c.lower()] += 1
    for cond, cnt in confounder_counter.most_common(10):
        print(f"  {cond:<32} {cnt}")

    # ── Save raw records ─────────────────────────────────────────────────────
    audit_result = {
        "summary": {
            "total_profiles":  total_profiles,
            "total_fps":       total_fps,
            "fp_rate":         round(fp_rate, 4),
            "threshold_used":  KIDNEY_THRESHOLD,
            "mean_score_all":  round(mean_score_all, 4),
            "flag_rate_all":   round(pct_above_thr, 4),
            "bucket_counts":   dict(bucket_counts),
            "top_confounders": confounder_counter.most_common(10),
        },
        "fp_records": fp_records,
    }
    out_json = RESULTS_DIR / "kidney_fp_audit.json"
    out_json.write_text(json.dumps(audit_result, indent=2))
    print(f"\nSaved → {out_json}")

    # ── Human-readable markdown summary ──────────────────────────────────────
    lines = [
        "# Kidney FP Audit — ML-KIDNEY-02",
        "",
        f"**Cohort:** 760-profile NHANES balanced  |  **Threshold:** {KIDNEY_THRESHOLD}",
        "",
        "## Overall",
        f"- Total FPs: **{total_fps}** ({fp_rate:.1%} of all profiles)",
        f"- Flag rate across all profiles: {pct_above_thr:.1%}",
        f"- Mean kidney score (all profiles): {mean_score_all:.4f}",
        "",
        "## FP Breakdown by Bucket",
        "",
        "| Bucket | Count | % of FPs | Description |",
        "|--------|-------|----------|-------------|",
        f"| healthy      | {bucket_counts.get('healthy', 0)} | {bucket_counts.get('healthy', 0) / total_fps * 100:.0f}% | No conditions, model still fires |",
        f"| metabolic    | {bucket_counts.get('metabolic', 0)} | {bucket_counts.get('metabolic', 0) / total_fps * 100:.0f}% | Prediabetes / anemia / iron / vit-D |",
        f"| hypertensive | {bucket_counts.get('hypertensive', 0)} | {bucket_counts.get('hypertensive', 0) / total_fps * 100:.0f}% | Electrolyte / cardiovascular overlap |",
        f"| other        | {bucket_counts.get('other', 0)} | {bucket_counts.get('other', 0) / total_fps * 100:.0f}% | Sleep, thyroid, or mixed patterns |",
        "",
        "## Top Confounding Conditions",
        "",
        "| Condition | Times a Confounder |",
        "|-----------|-------------------|",
    ]
    for cond, cnt in confounder_counter.most_common(10):
        lines.append(f"| {cond} | {cnt} |")

    lines += [
        "",
        "## Implication for v4",
        "",
        "- **Healthy FPs** → pure noise; hard-negative anchors from v3 already target this.",
        "- **Metabolic FPs** → shared symptom burden (fatigue, frequent urination); "
        "soft-weighting the hard negatives should help without suppressing borderline CKD.",
        "- **Hypertensive FPs** → HTN is a legitimate CKD risk factor; "
        "do NOT over-penalise these — Bayesian layer should disambiguate.",
        "- **Other FPs** → thyroid/sleep overlap; already captured in v3 hard-neg set.",
    ]
    out_md = RESULTS_DIR / "kidney_fp_summary.md"
    out_md.write_text("\n".join(lines))
    print(f"Saved → {out_md}")
    print("\nDone.")


if __name__ == "__main__":
    main()
