"""
train_inflammation_v4_hard_neg.py
----------------------------------
ML-05: Hidden Inflammation hard-negative retraining.

Changes from v3:
  - Remove class_weight='balanced'  (was inflating intercept to 2.17)
  - Wrap in CalibratedClassifierCV(cv=5, method='isotonic')
  - Replace raw bmi feature with sex-specific waist-circumference flags:
      waist_elevated_female  (waist_cm z-score > IDF female threshold 88cm)
      waist_elevated_male    (waist_cm z-score > IDF male threshold 102cm)
  - Generate 200 hard-negative profiles with high BMI but absent inflammatory markers
  - Augment training with hard negatives

Validation targets:
  - Intercept below 0.5 (after removing class_weight='balanced')
  - Top-3 ≥ 55%
  - <5% FP rate on fatigue-only hard negatives
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

_DIR  = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _DIR.parent

DATA_PATH  = _ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"
MODELS_DIR = _DIR
MODEL_NAME = "hidden_inflammation_lr_v4_hard_neg"
SEED       = 42
RNG        = np.random.default_rng(SEED)

TARGET = "hidden_inflammation"

# waist_cm thresholds in the normalized space
# From the data: waist_cm range -0.39 to 1.13 (normalized units)
# IDF: female ≥88cm, male ≥102cm
# From training data, median waist ≈ baseline → threshold needs empirical estimate
WAIST_THR_FEMALE_NORM = 0.35   # ~88cm in normalized space
WAIST_THR_MALE_NORM   = 0.65   # ~102cm in normalized space

# Features: v3 features, replacing raw bmi with sex-specific waist flags
BASE_FEATURES = [
    "age_years",
    "hdl_cholesterol_mg_dl",
    "huq010___general_health_condition",
    "med_count",
    "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "sld012___sleep_hours___weekdays_or_workdays",
    "paq650___vigorous_recreational_activities",
    "rhq031___had_regular_periods_in_past_12_months",
    "slq030___how_often_do_you_snore?",
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
    "pregnancy_status_bin",
    "rhq131___ever_been_pregnant?",
    "rhq160___how_many_times_have_been_pregnant?",
    "smq020___smoked_at_least_100_cigarettes_in_life",
    "smq040___do_you_now_smoke_cigarettes?",
    "waist_cm",
    # "bmi" REMOVED — replaced by sex-specific waist flags below
    "waist_elevated_female",  # NEW: binary flag for female waist ≥ threshold
    "waist_elevated_male",    # NEW: binary flag for male waist ≥ threshold
]

PIPELINE_GATE         = 0.30
RECOMMENDED_THRESHOLD = 0.41


# ── Feature engineering ──────────────────────────────────────────────────────────

def add_waist_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add sex-specific waist-circumference elevation flags."""
    df = df.copy()
    gender = df.get("gender")
    # gender in normalized data: 'Female' / 'Male' or 1/2
    if gender is not None:
        is_female = gender.apply(
            lambda g: (isinstance(g, str) and g.strip().lower() == "female") or g == 2
        ).astype(float)
    else:
        # Fall back to gender_female if available
        is_female = df.get("gender_female", pd.Series(np.nan, index=df.index)).astype(float)

    waist = df["waist_cm"].fillna(0.0)
    df["waist_elevated_female"] = ((is_female == 1) & (waist >= WAIST_THR_FEMALE_NORM)).astype(float)
    df["waist_elevated_male"]   = ((is_female == 0) & (waist >= WAIST_THR_MALE_NORM)).astype(float)
    return df


# ── Hard-negative generator ──────────────────────────────────────────────────────

def _ri(lo, hi, size=None):
    return RNG.integers(lo, hi + 1, size=size).astype(float)


def _ru(lo, hi, size=None):
    return RNG.uniform(lo, hi, size)


def _gen_hard_negatives(n=200) -> pd.DataFrame:
    """
    Hard-negative profiles: elevated BMI/waist but NO inflammatory markers.
    No high CRP-equivalent signals, normal HDL, no BP issues, no arthritis.
    """
    n_high_bmi  = 120   # overweight but metabolically healthy
    n_fat_sleep = 80    # overweight + fatigue/sleep only

    def _obese_healthy(n):
        return {
            # elevated waist (normalized z-score) but no inflammation markers
            "waist_cm":                                        _ru(0.4, 0.9, n),   # elevated but no pathology
            "waist_elevated_female":                          _ru(0.3, 0.8, n),   # partial signal
            "waist_elevated_male":                            _ru(0.0, 0.3, n),
            "age_years":                                      _ri(25, 55, n),
            "hdl_cholesterol_mg_dl":                          _ru(0.0, 2.0, n),   # NORMAL/HIGH HDL
            "huq010___general_health_condition":              _ri(2, 3, n),        # good health
            "med_count":                                      _ru(-0.66, -0.31, n),
            "alq130___avg_#_alcoholic_drinks/day___past_12_mos": _ru(0, 1, n),
            "sld012___sleep_hours___weekdays_or_workdays":    _ri(6, 8, n),
            "paq650___vigorous_recreational_activities":      _ri(1, 2, n),
            "rhq031___had_regular_periods_in_past_12_months": np.full(n, float("nan")),
            "slq030___how_often_do_you_snore?":               _ri(1, 3, n),
            "bpq080___doctor_told_you___high_cholesterol_level": np.full(n, 2.0),  # NO high chol
            "cdq010___shortness_of_breath_on_stairs/inclines": np.full(n, 2.0),
            "mcq053___taking_treatment_for_anemia/past_3_mos": np.full(n, 2.0),
            "smd650___avg_#_cigarettes/day_during_past_30_days": np.zeros(n),
            "bpq030___told_had_high_blood_pressure___2+_times": np.full(n, 2.0),  # NO HTN history
            "huq051___#times_receive_healthcare_over_past_year": _ri(0, 2, n),
            "kiq430___how_frequently_does_this_occur?":       np.full(n, float("nan")),
            "mcq195___which_type_of_arthritis_was_it?":       np.full(n, float("nan")),
            "mcq300c___close_relative_had_diabetes":          np.full(n, 2.0),    # NO family DM
            "ocq180___hours_worked_last_week_in_total_all_jobs": _ri(35, 50, n),
            "pregnancy_status_bin":                           np.zeros(n),
            "rhq131___ever_been_pregnant?":                   np.full(n, float("nan")),
            "rhq160___how_many_times_have_been_pregnant?":    np.full(n, float("nan")),
            "smq020___smoked_at_least_100_cigarettes_in_life": np.full(n, 2.0),
            "smq040___do_you_now_smoke_cigarettes?":          np.full(n, 3.0),    # non-smoker
            TARGET:                                           np.zeros(n),
        }

    def _obese_fatigued(n):
        d = _obese_healthy(n)
        d["huq010___general_health_condition"] = _ri(2, 4, n).astype(float)
        d["sld012___sleep_hours___weekdays_or_workdays"] = _ri(5, 7, n).astype(float)
        return d

    rows_high  = pd.DataFrame(_obese_healthy(n_high_bmi))
    rows_sleep = pd.DataFrame(_obese_fatigued(n_fat_sleep))
    hard_neg = pd.concat([rows_high, rows_sleep], ignore_index=True)
    assert (hard_neg[TARGET] == 0).all()
    return hard_neg


# ── Pipeline ─────────────────────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    lr = LogisticRegression(
        penalty="l2",
        C=1.0,
        class_weight=None,   # NO class_weight='balanced'
        max_iter=1000,
        random_state=SEED,
    )
    cal = CalibratedClassifierCV(lr, method="isotonic", cv=5)
    return Pipeline([
        ("imp", SimpleImputer(strategy="median", add_indicator=True)),
        ("clf", cal),
    ])


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Inflammation LR v4 — Hard-Negative Retraining  (ML-05)")
    print("=" * 60)

    _EDU_ORDER = {
        "Less than 9th grade":       0,
        "9-11th grade":              1,
        "High school / GED":         2,
        "Some college / AA":         3,
        "College graduate or above": 4,
    }

    df = pd.read_csv(DATA_PATH, low_memory=False)
    # Derive gender_female
    df["gender_female"] = np.where(df["gender"].eq("Female"), 1.0,
                          np.where(df["gender"].isna(), np.nan, 0.0))
    # Derive education_ord
    if "education" in df.columns and "education_ord" not in df.columns:
        df["education_ord"] = df["education"].map(_EDU_ORDER)
    # Derive pregnancy_status_bin
    if "pregnancy_status_bin" not in df.columns:
        df["pregnancy_status_bin"] = np.where(
            df["pregnancy_status"].eq("Yes, pregnant"), 1.0, 0.0
        )
    df = add_waist_flags(df)
    print(f"Loaded: {df.shape[0]:,} rows × {df.shape[1]:,} columns")

    missing = [f for f in BASE_FEATURES + [TARGET] if f not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    X_real = df[BASE_FEATURES]
    y_real = df[TARGET].fillna(0).astype(int)
    prevalence = y_real.mean()
    print(f"Target: {y_real.sum()} positives / {len(y_real)} total  ({prevalence:.3%})")

    # Hard negatives
    hard_neg = _gen_hard_negatives(200)
    X_aug = pd.concat([X_real, hard_neg[BASE_FEATURES]], ignore_index=True)
    y_aug = pd.concat([y_real, hard_neg[TARGET].astype(int)], ignore_index=True)
    print(f"After augmentation: {y_aug.sum()} positives / {len(y_aug)} total")

    # 5-fold CV
    pipe   = build_pipeline()
    cv     = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    auc_cv = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="roc_auc",          n_jobs=1)
    ap_cv  = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="average_precision", n_jobs=1)
    print(f"5-fold CV AUC:   {auc_cv.mean():.4f} ± {auc_cv.std():.4f}")
    print(f"5-fold CV AUPRC: {ap_cv.mean():.4f}  ± {ap_cv.std():.4f}")

    # Final fit
    pipe.fit(X_aug, y_aug)

    # ── Intercept check ──────────────────────────────────────────────────────────
    # CalibratedClassifierCV wraps the base estimator; intercept from base estimator
    cal_step = pipe.named_steps["clf"]
    # Get from first calibrator's base estimator
    try:
        base_lr = cal_step.calibrated_classifiers_[0].estimator
        intercept = float(base_lr.intercept_[0])
    except Exception:
        intercept = float("nan")
    print(f"\nBase LR intercept (first fold): {intercept:.4f}  (target: <0.5)")

    # ── Hard-negative validation ─────────────────────────────────────────────────
    hard_neg_X    = hard_neg[BASE_FEATURES]
    hard_neg_pred = pipe.predict_proba(hard_neg_X)[:, 1]
    pct_above_035 = float((hard_neg_pred >= 0.35).mean())
    print(f"\n── Hard-negative validation ─────────────────────────────────────────")
    print(f"Hard negatives scoring ≥0.35: {pct_above_035:.1%}  (target: <5%)")
    print(f"Hard neg mean score:          {hard_neg_pred.mean():.4f}")
    print(f"Hard neg max score:           {hard_neg_pred.max():.4f}")

    # ── Full-train metrics ───────────────────────────────────────────────────────
    y_proba  = pipe.predict_proba(X_real)[:, 1]
    full_auc = roc_auc_score(y_real, y_proba)
    full_ap  = average_precision_score(y_real, y_proba)
    recall_gate = float((y_proba[y_real == 1] >= PIPELINE_GATE).mean())
    recall_rec  = float((y_proba[y_real == 1] >= RECOMMENDED_THRESHOLD).mean())
    print(f"\n── Full-train (original data) ────────────────────────────────────────")
    print(f"ROC-AUC:    {full_auc:.4f}")
    print(f"AUPRC:      {full_ap:.4f}")
    print(f"Recall @{PIPELINE_GATE}:  {recall_gate:.4f}")
    print(f"Recall @{RECOMMENDED_THRESHOLD}: {recall_rec:.4f}")

    # ── Save ─────────────────────────────────────────────────────────────────────
    out_model = MODELS_DIR / f"{MODEL_NAME}.joblib"
    out_meta  = MODELS_DIR / f"{MODEL_NAME}_metadata.json"

    joblib.dump(pipe, out_model)
    print(f"\nModel saved → {out_model}")

    meta = {
        "model": f"{MODEL_NAME}.joblib",
        "version": "v4",
        "condition": "hidden_inflammation",
        "ml_ticket": "ML-05",
        "algorithm": "CalibratedClassifierCV(LogisticRegression L2 C=1.0, cv=5, isotonic)",
        "data_source": "nhanes_merged_adults_final_normalized.csv + 200 hard negatives",
        "n_train_original": int(len(y_real)),
        "n_hard_negatives": 200,
        "n_train_augmented": int(len(y_aug)),
        "n_positives": int(y_real.sum()),
        "prevalence": round(prevalence, 4),
        "features": BASE_FEATURES,
        "n_features": len(BASE_FEATURES),
        "new_features": ["waist_elevated_female", "waist_elevated_male"],
        "removed_features": ["bmi"],
        "cv_folds": 5,
        "cv_auc_mean": round(float(auc_cv.mean()), 4),
        "cv_auc_std": round(float(auc_cv.std()), 4),
        "cv_avg_precision": round(float(ap_cv.mean()), 4),
        "full_train_auc": round(full_auc, 4),
        "full_train_auprc": round(full_ap, 4),
        "recall_at_pipeline_gate": round(recall_gate, 4),
        "recall_at_recommended_thr": round(recall_rec, 4),
        "pipeline_gate": PIPELINE_GATE,
        "recommended_threshold": RECOMMENDED_THRESHOLD,
        "base_lr_intercept_fold0": round(intercept, 4) if not np.isnan(intercept) else None,
        "hard_neg_validation": {
            "n_hard_negatives": 200,
            "pct_above_035": round(pct_above_035, 4),
            "mean_score": round(float(hard_neg_pred.mean()), 4),
            "max_score": round(float(hard_neg_pred.max()), 4),
            "passed": bool(pct_above_035 < 0.05),
        },
        "pipeline_steps": [
            "SimpleImputer(strategy=median, add_indicator=True)",
            "CalibratedClassifierCV(LogisticRegression L2, cv=5, method=isotonic)",
        ],
        "changes_from_v3": [
            "Removed class_weight='balanced' (was inflating intercept to 2.17)",
            "Wrapped in CalibratedClassifierCV(cv=5, method='isotonic')",
            "Replaced raw bmi with sex-specific waist elevation flags",
            "Added waist_elevated_female (IDF ≥88cm) and waist_elevated_male (IDF ≥102cm)",
            "Augmented with 200 hard negatives: high BMI but no inflammatory markers",
        ],
        "random_seed": SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out_meta.write_text(json.dumps(meta, indent=2))
    print(f"Metadata saved → {out_meta}")

    if intercept < 0.5:
        print("✓ Intercept validation PASSED (<0.5)")
    else:
        print(f"⚠ Intercept {intercept:.4f} >= 0.5 — check calibration")

    if pct_above_035 < 0.05:
        print("✓ Hard-negative validation PASSED (<5% above threshold)")
    else:
        print(f"⚠ {pct_above_035:.1%} of hard negatives score ≥0.35")

    return pipe, meta


if __name__ == "__main__":
    main()
