"""
validate_inflammation_v4.py
----------------------------
ML-INFLAM-02 — Step 1: Validate the v4 Hard-Neg Candidate on the 760-Cohort

The current production model (v3) has 4.1% recall on the 760-cohort.
The v4 candidate (hidden_inflammation_lr_v4_hard_neg.joblib) was built in ML-05
but never received a formal 760-cohort pass.

This script runs both models against all 760 profiles and reports:
  - Recall, Precision, Flag Rate, Healthy FP Rate
  - Score distributions for true positives vs negatives
  - A "v4 promotion recommendation" based on whether recall comes "off the floor"

Data flow (follows the same path as the live eval scripts):
  raw nhanes_inputs
    → InputNormalizer.build_feature_vectors()   [z-score + derived cols]
    → runner.run_all_with_context()             [v3 production score]
    → v4_score_from_normalized_fvec()           [same normalization, v4 model]

For v4 specifically, we add waist_elevated_female / _male flags from the
normalized waist_cm (already in the v3 hidden_inflammation feature vector)
and the raw gender field before scoring with the v4 model.

Decision rule:
  recall >= 15%  → "improved, recommend promotion review"
  recall <  15%  → "still dead, proceed to missed-positive audit"

Outputs:
  results/inflammation_v4_validation.json
  results/inflammation_v4_validation.md
"""
from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_MODELS_DIR = _ROOT / "models_normalized"
sys.path.insert(0, str(_MODELS_DIR))

COHORT_PATH = _ROOT / "evals" / "cohort" / "nhanes_balanced_760.json"
RESULTS_DIR = _HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

THRESHOLD_V3 = 0.40
THRESHOLD_V4 = 0.40
RECALL_OFF_FLOOR = 0.15

# Waist z-score thresholds (from train_inflammation_v4_hard_neg.py)
WAIST_THR_FEMALE_NORM = 0.35
WAIST_THR_MALE_NORM   = 0.65

# Condition ID in the cohort  →  model registry key
CONDITION_TO_MODEL_KEY = {"inflammation": "hidden_inflammation"}


def load_cohort(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("profiles", [])


def get_expected_conditions(profile: dict) -> list[str]:
    """Return list of condition_ids from ground_truth."""
    gt = profile.get("ground_truth", {})
    return [c["condition_id"] for c in gt.get("expected_conditions", [])]


def is_primary_positive(profile: dict, target: str = "inflammation") -> bool:
    """True only for single-condition positive-type profiles (matches baseline eval counting)."""
    return (
        profile.get("target_condition") == target
        and profile.get("profile_type") == "positive"
    )


def is_healthy(profile: dict) -> bool:
    return profile.get("profile_type") == "healthy"


def _gender_female_from_raw(raw: dict) -> float:
    """Return 1.0 for Female, 0.0 for Male, NaN if unknown."""
    g = raw.get("gender")
    if g is None:
        return float("nan")
    if isinstance(g, str):
        return 1.0 if g.strip().lower() == "female" else 0.0
    # NHANES code: 1=Male, 2=Female
    code = int(g)
    if code == 2:
        return 1.0
    if code == 1:
        return 0.0
    return float("nan")


def build_v4_feature_vector(
    v3_fvec: pd.DataFrame,
    raw_inputs: dict,
    v4_features: list[str],
) -> pd.DataFrame:
    """
    Build a v4 feature vector from the normalized v3 feature vector.
    The v3 fvec already contains waist_cm (z-scored) and most shared features.
    We add the two binary waist flags and then slice to v4_features.
    """
    row = v3_fvec.iloc[0].to_dict()

    # Derive waist flags from normalized waist_cm + raw gender
    waist_norm = float(row.get("waist_cm", float("nan")))
    g_female   = _gender_female_from_raw(raw_inputs)

    if np.isnan(g_female) or np.isnan(waist_norm):
        row["waist_elevated_female"] = float("nan")
        row["waist_elevated_male"]   = float("nan")
    else:
        row["waist_elevated_female"] = float(g_female == 1.0 and waist_norm >= WAIST_THR_FEMALE_NORM)
        row["waist_elevated_male"]   = float(g_female == 0.0 and waist_norm >= WAIST_THR_MALE_NORM)

    # Slice to exactly v4_features (NaN for any missing columns)
    sliced = {f: row.get(f, float("nan")) for f in v4_features}
    return pd.DataFrame([sliced])


def main():
    from model_runner import ModelRunner

    print("=" * 60)
    print("  Inflammation v4 Validation  (ML-INFLAM-02)")
    print("=" * 60)

    profiles = load_cohort(COHORT_PATH)
    print(f"Loaded {len(profiles)} profiles")

    runner = ModelRunner()
    norm   = runner._get_normalizer()

    # Load v4 model and its feature list
    v4_model_path = _MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg.joblib"
    v4_meta_path  = _MODELS_DIR / "hidden_inflammation_lr_v4_hard_neg_metadata.json"

    if not v4_model_path.exists():
        print(f"ERROR: v4 model not found at {v4_model_path}")
        return

    v4_model    = joblib.load(v4_model_path)
    v4_features = json.loads(v4_meta_path.read_text())["features"] if v4_meta_path.exists() else None
    if v4_features is None:
        # fallback to known feature list from training script
        v4_features = [
            "age_years", "hdl_cholesterol_mg_dl", "huq010___general_health_condition",
            "med_count", "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
            "sld012___sleep_hours___weekdays_or_workdays", "paq650___vigorous_recreational_activities",
            "rhq031___had_regular_periods_in_past_12_months", "slq030___how_often_do_you_snore?",
            "bpq080___doctor_told_you___high_cholesterol_level",
            "cdq010___shortness_of_breath_on_stairs/inclines",
            "mcq053___taking_treatment_for_anemia/past_3_mos",
            "smd650___avg_#_cigarettes/day_during_past_30_days",
            "bpq030___told_had_high_blood_pressure___2+_times",
            "huq051___#times_receive_healthcare_over_past_year",
            "kiq430___how_frequently_does_this_occur?",
            "mcq195___which_type_of_arthritis_was_it?",
            "mcq300c___close_relative_had_diabetes",
            "ocq180___hours_worked_last_week_in_total_all_jobs",
            "pregnancy_status_bin", "rhq131___ever_been_pregnant?",
            "rhq160___how_many_times_have_been_pregnant?",
            "smq020___smoked_at_least_100_cigarettes_in_life",
            "smq040___do_you_now_smoke_cigarettes?",
            "waist_cm", "waist_elevated_female", "waist_elevated_male",
        ]

    print(f"v4 features: {len(v4_features)}")

    # ── Score all profiles ────────────────────────────────────────────────────
    results_v3 = []
    results_v4 = []
    errors = 0

    for profile in profiles:
        raw_inputs = profile.get("nhanes_inputs", {})
        expected   = get_expected_conditions(profile)

        is_pos     = is_primary_positive(profile)
        is_hlthy   = is_healthy(profile)

        try:
            fvecs     = norm.build_feature_vectors(raw_inputs)
            all_scores = runner.run_all_with_context(
                fvecs,
                patient_context={
                    "gender":    raw_inputs.get("gender"),
                    "age_years": raw_inputs.get("age_years"),
                },
            )
            score_v3 = all_scores.get("hidden_inflammation", float("nan"))
        except Exception as exc:
            score_v3 = float("nan")
            errors += 1

        try:
            v3_fvec  = fvecs.get("hidden_inflammation", pd.DataFrame())
            v4_fvec  = build_v4_feature_vector(v3_fvec, raw_inputs, v4_features)
            score_v4 = float(v4_model.predict_proba(v4_fvec)[0, 1])
        except Exception as exc:
            score_v4 = float("nan")

        results_v3.append({"is_pos": is_pos, "is_healthy": is_hlthy, "score": score_v3})
        results_v4.append({"is_pos": is_pos, "is_healthy": is_hlthy, "score": score_v4})

    if errors:
        print(f"  WARN: {errors} profiles failed normalizer — excluded from metrics")

    # ── Compute metrics ───────────────────────────────────────────────────────
    def metrics(results: list[dict], threshold: float) -> dict:
        tp = fp = fn = healthy_fp = healthy_total = 0
        pos_scores, neg_scores = [], []

        for r in results:
            s = r["score"]
            if np.isnan(s):
                continue
            fires = s >= threshold
            if r["is_pos"]:
                pos_scores.append(s)
                if fires:
                    tp += 1
                else:
                    fn += 1
            else:
                neg_scores.append(s)
                if fires:
                    fp += 1
            if r["is_healthy"]:
                healthy_total += 1
                if fires:
                    healthy_fp += 1

        recall    = tp / (tp + fn)   if (tp + fn) > 0   else 0.0
        precision = tp / (tp + fp)   if (tp + fp) > 0   else 0.0
        flag_rate = (tp + fp) / len(results) if results else 0.0
        h_fpr     = healthy_fp / healthy_total if healthy_total else 0.0

        return {
            "threshold": threshold, "tp": tp, "fp": fp, "fn": fn,
            "recall":           round(recall, 4),
            "precision":        round(precision, 4),
            "flag_rate":        round(flag_rate, 4),
            "healthy_fp_n":     healthy_fp,
            "healthy_fp_rate":  round(h_fpr, 4),
            "mean_score_pos":   round(float(np.mean(pos_scores)), 4) if pos_scores else None,
            "mean_score_neg":   round(float(np.mean(neg_scores)), 4) if neg_scores else None,
            "p50_pos":          round(float(np.percentile(pos_scores, 50)), 4) if pos_scores else None,
            "p50_neg":          round(float(np.percentile(neg_scores, 50)), 4) if neg_scores else None,
        }

    m3 = metrics(results_v3, THRESHOLD_V3)
    m4 = metrics(results_v4, THRESHOLD_V4)

    # ── Print comparison ──────────────────────────────────────────────────────
    print(f"\n{'Metric':<25} {'v3 (prod)':>12} {'v4 (cand)':>12} {'Delta':>10}")
    print("-" * 62)
    for key in ["recall", "precision", "flag_rate", "healthy_fp_rate", "mean_score_pos", "mean_score_neg"]:
        v3_val = m3.get(key)
        v4_val = m4.get(key)
        if v3_val is not None and v4_val is not None:
            delta = v4_val - v3_val
            print(f"  {key:<23} {v3_val:>12.1%} {v4_val:>12.1%} {delta:>+10.1%}"
                  if isinstance(v3_val, float) and v3_val <= 1.0
                  else f"  {key:<23} {str(v3_val):>12} {str(v4_val):>12} {delta:>+10.4f}")
        else:
            print(f"  {key:<23} {'—':>12} {'—':>12}")

    # ── Decision ──────────────────────────────────────────────────────────────
    recall_v4 = m4["recall"]
    off_floor = recall_v4 >= RECALL_OFF_FLOOR

    print()
    if off_floor:
        recommendation = "PROMOTE_CANDIDATE"
        print(f"✓ v4 recall {recall_v4:.1%} >= {RECALL_OFF_FLOOR:.0%} floor — recommend promotion review")
    else:
        recommendation = "PROCEED_TO_MISSED_POSITIVE_AUDIT"
        print(f"✗ v4 recall {recall_v4:.1%} still < {RECALL_OFF_FLOOR:.0%} — model still dead")
        print("  → Run audit_inflammation_missed.py next")

    # ── Save ─────────────────────────────────────────────────────────────────
    out = {
        "summary": {
            "total_profiles":       len(profiles),
            "errors":               errors,
            "recall_off_floor_thr": RECALL_OFF_FLOOR,
            "recommendation":       recommendation,
        },
        "v3_production": m3,
        "v4_candidate":  m4,
    }
    out_json = RESULTS_DIR / "inflammation_v4_validation.json"
    out_json.write_text(json.dumps(out, indent=2))
    print(f"\nSaved → {out_json}")

    # ── Markdown report ───────────────────────────────────────────────────────
    def fmt_pct(v):
        return f"{v:.1%}" if v is not None else "—"

    lines = [
        "# Inflammation v4 Validation — ML-INFLAM-02",
        "",
        "**Cohort:** 760-profile NHANES balanced  |  **Date:** 2026-03-31",
        "",
        "## Results",
        "",
        f"| Metric | v3 (production) | v4 (candidate) | Delta |",
        f"|--------|----------------|----------------|-------|",
        f"| Recall        | {fmt_pct(m3['recall'])} | {fmt_pct(m4['recall'])} | {m4['recall'] - m3['recall']:+.1%} |",
        f"| Precision     | {fmt_pct(m3['precision'])} | {fmt_pct(m4['precision'])} | — |",
        f"| Flag Rate     | {fmt_pct(m3['flag_rate'])} | {fmt_pct(m4['flag_rate'])} | — |",
        f"| Healthy FPR   | {fmt_pct(m3['healthy_fp_rate'])} | {fmt_pct(m4['healthy_fp_rate'])} | — |",
        f"| Mean Score (pos) | {m3.get('mean_score_pos') or '—'} | {m4.get('mean_score_pos') or '—'} | — |",
        f"| Mean Score (neg) | {m3.get('mean_score_neg') or '—'} | {m4.get('mean_score_neg') or '—'} | — |",
        "",
        "## Recommendation",
        "",
    ]

    if recommendation == "PROMOTE_CANDIDATE":
        lines += [
            f"**v4 passed the recall floor ({RECALL_OFF_FLOOR:.0%}).** Proceed with full eval review.",
            "",
            "Next steps:",
            "1. Run the full layer1 eval with v4 wired into `model_runner.py`.",
            "2. Confirm healthy FPR stays under 5%.",
            "3. Update `MODEL_REGISTRY_AUDIT` and promote.",
        ]
    else:
        lines += [
            f"**v4 recall is still below the floor ({RECALL_OFF_FLOOR:.0%}).**",
            "The calibration and waist-flag changes alone are not enough.",
            "",
            "Next steps:",
            "1. Run `audit_inflammation_missed.py` to characterise what the model misses.",
            "2. Assess whether the `hidden_inflammation` label is too fuzzy for the current feature set.",
            "3. Consider a feature redesign that separates generic illness from true inflammation.",
        ]

    out_md = RESULTS_DIR / "inflammation_v4_validation.md"
    out_md.write_text("\n".join(lines))
    print(f"Saved → {out_md}")
    print(f"\nRecommendation: {recommendation}")


if __name__ == "__main__":
    main()
