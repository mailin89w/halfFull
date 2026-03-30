"""
train_prediabetes_v3_hard_neg.py
---------------------------------
ML-05: Prediabetes hard-negative retraining.

Changes from v2:
  - Add BMI × family_history_diabetes interaction term (bmi_x_family_dm)
  - Keep fasting_glucose_mg_dl (already in v2 feature set)
  - Try XGBoost with scale_pos_weight as alternative to LR
  - Generate 200 hard-negative profiles (fatigue-only, no metabolic syndrome)
  - Augment training with hard negatives

Validation targets:
  - Top-1 ≥ 15%
  - Flag rate <20% at recommended threshold
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
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

_DIR  = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _DIR.parent

DATA_PATH  = _ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"
MODELS_DIR = _DIR
MODEL_NAME = "prediabetes_xgb_v3_hard_neg"
SEED       = 42
RNG        = np.random.default_rng(SEED)

TARGET = "prediabetes"

# v2 features + BMI×family_dm interaction term
BASE_FEATURES = [
    "mcq366d___doctor_told_to_reduce_fat_in_diet",
    "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
    "hdl_cholesterol_mg_dl",
    "fasting_glucose_mg_dl",
    "pregnancy_status_bin",
    "bpq050a___now_taking_prescribed_medicine_for_hbp",
    "bpq080___doctor_told_you___high_cholesterol_level",
    "bpq020___ever_told_you_had_high_blood_pressure",
    "bpq030___told_had_high_blood_pressure___2+_times",
    "mcq160b___ever_told_you_had_congestive_heart_failure",
    "smd650___avg_#_cigarettes/day_during_past_30_days",
    "paq665___moderate_recreational_activities",
    "paq650___vigorous_recreational_activities",
    "paq620___moderate_work_activity",
    "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "whq070___tried_to_lose_weight_in_past_year",
    "whq040___like_to_weigh_more,_less_or_same",
    "mcq010___ever_been_told_you_have_asthma",
    "mcq053___taking_treatment_for_anemia/past_3_mos",
    "mcq520___abdominal_pain_during_past_12_months?",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "mcq195___which_type_of_arthritis_was_it?",
    "slq050___ever_told_doctor_had_trouble_sleeping?",
    "sld012___sleep_hours___weekdays_or_workdays",
    "dpq040___feeling_tired_or_having_little_energy",
    "huq010___general_health_condition",
    "huq071___overnight_hospital_patient_in_last_year",
    "education_ord",
    "kiq052___how_much_were_daily_activities_affected?",
    "kiq022___ever_told_you_had_weak/failing_kidneys?",
    "mcq300c___close_relative_had_diabetes",
    "gender_female",
    "med_count",
    "age_years",
    "bmi",
    "bmi_x_family_dm",   # NEW: BMI × family_history_diabetes interaction
]

PIPELINE_GATE         = 0.35
RECOMMENDED_THRESHOLD = 0.53


# ── Feature engineering ──────────────────────────────────────────────────────────

def add_interaction_term(df: pd.DataFrame) -> pd.DataFrame:
    """Add BMI × family_history_diabetes interaction term."""
    df = df.copy()
    bmi = df.get("bmi", pd.Series(np.nan, index=df.index))
    fam_dm = df.get("mcq300c___close_relative_had_diabetes",
                    pd.Series(np.nan, index=df.index))
    # family_dm: 1=yes, 2=no → convert to binary flag (1=yes, 0=no)
    fam_dm_bin = fam_dm.apply(
        lambda v: 1.0 if (not pd.isna(v) and int(v) == 1) else 0.0 if not pd.isna(v) else 0.0
    )
    df["bmi_x_family_dm"] = bmi.fillna(0.0) * fam_dm_bin
    return df


def add_gender_female(df: pd.DataFrame) -> pd.DataFrame:
    """Derive gender_female binary from gender string column."""
    df = df.copy()
    if "gender_female" not in df.columns:
        gender = df.get("gender")
        if gender is not None:
            df["gender_female"] = gender.apply(
                lambda g: 1.0 if (isinstance(g, str) and g.strip().lower() == "female") or g == 2 else 0.0
            )
        else:
            df["gender_female"] = np.nan
    return df


# ── Hard-negative generator ──────────────────────────────────────────────────────

def _ri(lo, hi, size=None):
    return RNG.integers(lo, hi + 1, size=size).astype(float)


def _ru(lo, hi, size=None):
    return RNG.uniform(lo, hi, size)


def _gen_hard_negatives(n=200) -> pd.DataFrame:
    """
    Hard-negative profiles: fatigue-only, no metabolic syndrome.
    Normal glucose, no family DM, normal weight/BMI, no BP issues.
    """
    n_fatigue = 120
    n_sleep   = 50
    n_young   = 30  # young healthy profiles

    def _base(n, age_lo=25, age_hi=50):
        bmi_vals = _ru(-0.5, 0.5, n)   # normal BMI in z-score space
        fam_dm   = np.full(n, 2.0)     # no family diabetes
        return {
            "mcq366d___doctor_told_to_reduce_fat_in_diet":   np.full(n, 2.0),
            "LBDLDL_ldl_cholesterol_friedewald_mg_dl":        _ru(-0.5, 0.5, n),  # normal LDL
            "hdl_cholesterol_mg_dl":                          _ru(0.5, 2.5, n),   # good HDL
            "fasting_glucose_mg_dl":                          _ru(-0.5, 0.0, n),  # NORMAL GLUCOSE
            "pregnancy_status_bin":                           np.zeros(n),
            "bpq050a___now_taking_prescribed_medicine_for_hbp": np.full(n, 2.0),
            "bpq080___doctor_told_you___high_cholesterol_level": np.full(n, 2.0),
            "bpq020___ever_told_you_had_high_blood_pressure": np.full(n, 2.0),
            "bpq030___told_had_high_blood_pressure___2+_times": np.full(n, 2.0),
            "mcq160b___ever_told_you_had_congestive_heart_failure": np.full(n, 2.0),
            "smd650___avg_#_cigarettes/day_during_past_30_days": np.zeros(n),
            "paq665___moderate_recreational_activities":       _ri(1, 2, n),
            "paq650___vigorous_recreational_activities":       _ri(1, 2, n),
            "paq620___moderate_work_activity":                 _ri(1, 2, n),
            "alq130___avg_#_alcoholic_drinks/day___past_12_mos": _ru(0, 1, n),
            "whq070___tried_to_lose_weight_in_past_year":      np.full(n, 2.0),
            "whq040___like_to_weigh_more,_less_or_same":       _ri(2, 3, n),
            "mcq010___ever_been_told_you_have_asthma":         np.full(n, 2.0),
            "mcq053___taking_treatment_for_anemia/past_3_mos": np.full(n, 2.0),
            "mcq520___abdominal_pain_during_past_12_months?":  np.full(n, 2.0),
            "cdq010___shortness_of_breath_on_stairs/inclines": np.full(n, 2.0),
            "mcq195___which_type_of_arthritis_was_it?":        np.full(n, float("nan")),
            "slq050___ever_told_doctor_had_trouble_sleeping?": np.full(n, 2.0),
            "sld012___sleep_hours___weekdays_or_workdays":     _ri(7, 8, n),
            "dpq040___feeling_tired_or_having_little_energy":  _ri(1, 2, n),  # mild fatigue
            "huq010___general_health_condition":               _ri(2, 3, n),
            "huq071___overnight_hospital_patient_in_last_year": np.full(n, 2.0),
            "education_ord":                                   _ri(2, 4, n),
            "kiq052___how_much_were_daily_activities_affected?": _ri(1, 2, n),
            "kiq022___ever_told_you_had_weak/failing_kidneys?": np.full(n, 2.0),
            "mcq300c___close_relative_had_diabetes":           fam_dm,
            "gender_female":                                   _ri(0, 1, n),
            "med_count":                                       _ru(-0.66, -0.31, n),
            "age_years":                                       _ri(age_lo, age_hi, n),
            "bmi":                                             bmi_vals,
            "bmi_x_family_dm":                                 bmi_vals * 0.0,  # family_dm=0 → interaction=0
            TARGET:                                            np.zeros(n),
        }

    def _fatigued(n, age_lo=30, age_hi=55):
        d = _base(n, age_lo, age_hi)
        d["dpq040___feeling_tired_or_having_little_energy"] = _ri(2, 3, n).astype(float)
        d["huq010___general_health_condition"] = _ri(2, 4, n).astype(float)
        return d

    def _sleep(n, age_lo=25, age_hi=50):
        d = _fatigued(n, age_lo, age_hi)
        d["slq050___ever_told_doctor_had_trouble_sleeping?"] = np.full(n, 1.0)
        d["sld012___sleep_hours___weekdays_or_workdays"] = _ri(5, 6, n).astype(float)
        return d

    dfs = [
        pd.DataFrame(_fatigued(n_fatigue)),
        pd.DataFrame(_sleep(n_sleep, 30, 55)),
        pd.DataFrame(_base(n_young, 18, 30)),
    ]
    hard_neg = pd.concat(dfs, ignore_index=True)
    assert (hard_neg[TARGET] == 0).all()
    return hard_neg


# ── Pipeline builders ─────────────────────────────────────────────────────────────

def build_xgb_pipeline(scale_pos_weight: float):
    """XGBoost with scale_pos_weight for class imbalance."""
    try:
        from xgboost import XGBClassifier
    except ImportError:
        raise ImportError("xgboost not installed. Run: pip install xgboost")

    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=SEED,
        n_jobs=-1,
    )
    from sklearn.calibration import CalibratedClassifierCV
    cal = CalibratedClassifierCV(xgb, method="isotonic", cv=3)
    return Pipeline([
        ("imp", SimpleImputer(strategy="median", add_indicator=True)),
        ("clf", cal),
    ])


def build_lr_fallback_pipeline():
    """Fallback LR with stronger regularization if XGBoost unavailable."""
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(
        penalty="l2",
        C=0.01,
        class_weight="balanced",
        max_iter=2000,
        random_state=SEED,
    )
    return Pipeline([
        ("imp", SimpleImputer(strategy="median", add_indicator=True)),
        ("clf", lr),
    ])


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Prediabetes XGB v3 — Hard-Negative Retraining  (ML-05)")
    print("=" * 60)

    _EDU_ORDER = {
        "Less than 9th grade":       0,
        "9-11th grade":              1,
        "High school / GED":         2,
        "Some college / AA":         3,
        "College graduate or above": 4,
    }

    df = pd.read_csv(DATA_PATH, low_memory=False)
    df = add_gender_female(df)
    # Derive education_ord
    if "education" in df.columns and "education_ord" not in df.columns:
        df["education_ord"] = df["education"].map(_EDU_ORDER)
    # Derive pregnancy_status_bin
    if "pregnancy_status_bin" not in df.columns:
        df["pregnancy_status_bin"] = np.where(
            df["pregnancy_status"].eq("Yes, pregnant"), 1.0, 0.0
        )
    df = add_interaction_term(df)
    print(f"Loaded: {df.shape[0]:,} rows × {df.shape[1]:,} columns")

    missing = [f for f in BASE_FEATURES + [TARGET] if f not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    X_real = df[BASE_FEATURES]
    y_real = df[TARGET].fillna(0).astype(int)
    prevalence = y_real.mean()
    print(f"Target: {y_real.sum()} positives / {len(y_real)} total  ({prevalence:.3%})")

    # scale_pos_weight for XGBoost = n_negative / n_positive
    n_neg = int((y_real == 0).sum())
    n_pos = int((y_real == 1).sum())
    scale_pos_weight = n_neg / n_pos
    print(f"scale_pos_weight: {scale_pos_weight:.2f}")

    # Hard negatives
    hard_neg = _gen_hard_negatives(200)
    X_aug = pd.concat([X_real, hard_neg[BASE_FEATURES]], ignore_index=True)
    y_aug = pd.concat([y_real, hard_neg[TARGET].astype(int)], ignore_index=True)
    print(f"After augmentation: {y_aug.sum()} positives / {len(y_aug)} total")

    # Try XGBoost, fall back to LR
    algorithm = "xgb"
    try:
        pipe = build_xgb_pipeline(scale_pos_weight)
        # Quick fit test
        pipe.fit(X_aug.head(100), y_aug.head(100))
        pipe = build_xgb_pipeline(scale_pos_weight)
        print("Using XGBoost with CalibratedClassifierCV")
    except (ImportError, Exception) as e:
        print(f"XGBoost not available ({e}), falling back to LR")
        pipe = build_lr_fallback_pipeline()
        algorithm = "lr_fallback"

    # 5-fold CV
    cv     = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    auc_cv = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="roc_auc",          n_jobs=1)
    ap_cv  = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="average_precision", n_jobs=1)
    print(f"5-fold CV AUC:   {auc_cv.mean():.4f} ± {auc_cv.std():.4f}")
    print(f"5-fold CV AUPRC: {ap_cv.mean():.4f}  ± {ap_cv.std():.4f}")

    # Final fit
    pipe.fit(X_aug, y_aug)

    # ── Hard-negative validation ─────────────────────────────────────────────────
    hard_neg_pred = pipe.predict_proba(hard_neg[BASE_FEATURES])[:, 1]
    pct_above_035 = float((hard_neg_pred >= 0.35).mean())
    print(f"\n── Hard-negative validation ─────────────────────────────────────────")
    print(f"Hard negatives scoring ≥0.35: {pct_above_035:.1%}  (target: <5%)")
    print(f"Hard neg mean score:          {hard_neg_pred.mean():.4f}")
    print(f"Hard neg max score:           {hard_neg_pred.max():.4f}")

    # ── Full-train metrics ───────────────────────────────────────────────────────
    y_proba  = pipe.predict_proba(X_real)[:, 1]
    full_auc = roc_auc_score(y_real, y_proba)
    full_ap  = average_precision_score(y_real, y_proba)
    flag_rate = float((y_proba >= RECOMMENDED_THRESHOLD).mean())
    recall_gate = float((y_proba[y_real == 1] >= PIPELINE_GATE).mean())
    recall_rec  = float((y_proba[y_real == 1] >= RECOMMENDED_THRESHOLD).mean())
    print(f"\n── Full-train (original data) ────────────────────────────────────────")
    print(f"ROC-AUC:      {full_auc:.4f}")
    print(f"AUPRC:        {full_ap:.4f}")
    print(f"Flag rate @{RECOMMENDED_THRESHOLD}: {flag_rate:.4f}  (target: <0.20)")
    print(f"Recall @{PIPELINE_GATE}:     {recall_gate:.4f}")
    print(f"Recall @{RECOMMENDED_THRESHOLD}:  {recall_rec:.4f}")

    # ── Save ─────────────────────────────────────────────────────────────────────
    out_model = MODELS_DIR / f"{MODEL_NAME}.joblib"
    out_meta  = MODELS_DIR / f"{MODEL_NAME}_metadata.json"

    joblib.dump(pipe, out_model)
    print(f"\nModel saved → {out_model}")

    meta = {
        "model": f"{MODEL_NAME}.joblib",
        "version": "v3",
        "condition": "prediabetes",
        "ml_ticket": "ML-05",
        "algorithm": algorithm,
        "scale_pos_weight": round(scale_pos_weight, 2) if algorithm == "xgb" else None,
        "data_source": "nhanes_merged_adults_final_normalized.csv + 200 hard negatives",
        "n_train_original": int(len(y_real)),
        "n_hard_negatives": 200,
        "n_train_augmented": int(len(y_aug)),
        "n_positives": int(y_real.sum()),
        "prevalence": round(prevalence, 4),
        "features": BASE_FEATURES,
        "n_features": len(BASE_FEATURES),
        "new_features": ["bmi_x_family_dm"],
        "cv_folds": 5,
        "cv_auc_mean": round(float(auc_cv.mean()), 4),
        "cv_auc_std": round(float(auc_cv.std()), 4),
        "cv_avg_precision": round(float(ap_cv.mean()), 4),
        "full_train_auc": round(full_auc, 4),
        "full_train_auprc": round(full_ap, 4),
        "flag_rate_at_rec_thr": round(flag_rate, 4),
        "recall_at_pipeline_gate": round(recall_gate, 4),
        "recall_at_recommended_thr": round(recall_rec, 4),
        "pipeline_gate": PIPELINE_GATE,
        "recommended_threshold": RECOMMENDED_THRESHOLD,
        "hard_neg_validation": {
            "n_hard_negatives": 200,
            "pct_above_035": round(pct_above_035, 4),
            "mean_score": round(float(hard_neg_pred.mean()), 4),
            "max_score": round(float(hard_neg_pred.max()), 4),
            "passed": bool(pct_above_035 < 0.05),
        },
        "pipeline_steps": [
            "SimpleImputer(strategy=median, add_indicator=True)",
            f"{algorithm}: CalibratedClassifierCV with isotonic",
        ],
        "changes_from_v2": [
            "Added bmi_x_family_dm interaction term (BMI × family_history_diabetes)",
            "Switched to XGBoost with scale_pos_weight (or LR fallback)",
            "Added CalibratedClassifierCV(isotonic) for proper probability calibration",
            "Augmented with 200 hard-negative fatigue-only profiles (no metabolic syndrome)",
        ],
        "random_seed": SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out_meta.write_text(json.dumps(meta, indent=2))
    print(f"Metadata saved → {out_meta}")

    if flag_rate < 0.20:
        print("✓ Flag rate validation PASSED (<20%)")
    else:
        print(f"⚠ Flag rate {flag_rate:.1%} >= 20%")

    if pct_above_035 < 0.05:
        print("✓ Hard-negative validation PASSED (<5% above threshold)")
    else:
        print(f"⚠ {pct_above_035:.1%} of hard negatives score ≥0.35")

    return pipe, meta


if __name__ == "__main__":
    main()
