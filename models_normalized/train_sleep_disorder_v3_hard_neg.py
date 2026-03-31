"""
train_sleep_disorder_v3_hard_neg.py
-----------------------------------
ML-SLEEP-02: rebuild the sleep disorder model around a narrower phenotype.

Intent:
  - separate true sleep-pathology anchors from generic tiredness
  - keep the feature set runtime-safe and product-usable
  - add explicit fatigue-lookalike hard negatives
  - shrink reliance on broad "feeling unwell" signal

This script trains a compact Logistic Regression model on the normalized NHANES
training set plus synthetic hard negatives that mimic common false-positive
profiles:
  - generic fatigue
  - thyroid-like fatigue
  - anemia-like fatigue
  - perimenopause-like disrupted sleep
  - poor sleep hygiene without stronger pathology anchors
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _DIR.parent

DATA_PATH = _ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"
MODELS_DIR = _DIR
MODEL_NAME = "sleep_disorder_lr_v3_hard_neg"
SEED = 42
RNG = np.random.default_rng(SEED)

TARGET = "sleep_disorder"

# Runtime-safe, sleep-phenotype-focused features only.
FEATURES = [
    "gender_female",
    "age_years",
    "bmi",
    "med_count",
    "slq030___how_often_do_you_snore?",
    "sld012___sleep_hours___weekdays_or_workdays",
    "sld013___sleep_hours___weekends",
    "kiq480___how_many_times_urinate_in_night?",
    "dpq040___feeling_tired_or_having_little_energy",
    "huq010___general_health_condition",
    "bpq020___ever_told_you_had_high_blood_pressure",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "mcq010___ever_been_told_you_have_asthma",
    "huq071___overnight_hospital_patient_in_last_year",
]

PIPELINE_GATE = 0.60
RECOMMENDED_THRESHOLD = 0.70


def _ri(lo: int, hi: int, size: int) -> np.ndarray:
    return RNG.integers(lo, hi + 1, size=size).astype(float)


def _ru(lo: float, hi: float, size: int) -> np.ndarray:
    return RNG.uniform(lo, hi, size)


def add_gender_female(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "gender_female" not in df.columns:
        gender = df.get("gender")
        if gender is not None:
            df["gender_female"] = gender.apply(
                lambda value: 1.0
                if (isinstance(value, str) and value.strip().lower() == "female") or value == 2
                else 0.0
            )
        else:
            df["gender_female"] = np.nan
    return df


def _base_profile(n: int, *, age_lo: int, age_hi: int, female_bias: float = 0.5) -> dict[str, np.ndarray]:
    female = RNG.binomial(1, female_bias, n).astype(float)
    return {
        "gender_female": female,
        "age_years": _ri(age_lo, age_hi, n),
        "bmi": _ru(-0.6, 0.8, n),
        "med_count": _ru(-0.7, -0.15, n),
        "slq030___how_often_do_you_snore?": _ri(0, 1, n),
        "sld012___sleep_hours___weekdays_or_workdays": _ru(6.5, 8.2, n),
        "sld013___sleep_hours___weekends": _ru(7.0, 9.0, n),
        "kiq480___how_many_times_urinate_in_night?": _ri(0, 1, n),
        "dpq040___feeling_tired_or_having_little_energy": _ri(1, 2, n),
        "huq010___general_health_condition": _ri(2, 3, n),
        "bpq020___ever_told_you_had_high_blood_pressure": np.full(n, 2.0),
        "cdq010___shortness_of_breath_on_stairs/inclines": np.full(n, 2.0),
        "mcq010___ever_been_told_you_have_asthma": np.full(n, 2.0),
        "huq071___overnight_hospital_patient_in_last_year": np.full(n, 2.0),
        TARGET: np.zeros(n),
    }


def _fatigue_lookalike(n: int) -> pd.DataFrame:
    d = _base_profile(n, age_lo=25, age_hi=55)
    d["dpq040___feeling_tired_or_having_little_energy"] = _ri(2, 3, n)
    d["huq010___general_health_condition"] = _ri(3, 4, n)
    return pd.DataFrame(d)


def _thyroid_like(n: int) -> pd.DataFrame:
    d = _base_profile(n, age_lo=30, age_hi=60, female_bias=0.75)
    d["dpq040___feeling_tired_or_having_little_energy"] = _ri(2, 3, n)
    d["huq010___general_health_condition"] = _ri(3, 4, n)
    d["sld012___sleep_hours___weekdays_or_workdays"] = _ru(6.8, 8.5, n)
    d["sld013___sleep_hours___weekends"] = _ru(7.2, 9.2, n)
    d["bmi"] = _ru(-0.2, 1.0, n)
    d["med_count"] = _ru(-0.4, 0.2, n)
    return pd.DataFrame(d)


def _anemia_like(n: int) -> pd.DataFrame:
    d = _base_profile(n, age_lo=22, age_hi=48, female_bias=0.8)
    d["dpq040___feeling_tired_or_having_little_energy"] = _ri(2, 3, n)
    d["huq010___general_health_condition"] = _ri(3, 4, n)
    d["cdq010___shortness_of_breath_on_stairs/inclines"] = RNG.choice([1.0, 2.0], size=n, p=[0.65, 0.35])
    d["slq030___how_often_do_you_snore?"] = _ri(0, 1, n)
    d["sld012___sleep_hours___weekdays_or_workdays"] = _ru(6.8, 8.2, n)
    d["sld013___sleep_hours___weekends"] = _ru(7.0, 9.0, n)
    return pd.DataFrame(d)


def _perimenopause_like(n: int) -> pd.DataFrame:
    d = _base_profile(n, age_lo=40, age_hi=55, female_bias=1.0)
    d["dpq040___feeling_tired_or_having_little_energy"] = _ri(2, 3, n)
    d["sld012___sleep_hours___weekdays_or_workdays"] = _ru(5.2, 6.5, n)
    d["sld013___sleep_hours___weekends"] = _ru(6.0, 7.5, n)
    d["kiq480___how_many_times_urinate_in_night?"] = _ri(0, 2, n)
    d["slq030___how_often_do_you_snore?"] = _ri(0, 1, n)
    d["huq010___general_health_condition"] = _ri(2, 4, n)
    d["med_count"] = _ru(-0.4, 0.25, n)
    return pd.DataFrame(d)


def _poor_sleep_hygiene(n: int) -> pd.DataFrame:
    d = _base_profile(n, age_lo=18, age_hi=45)
    d["sld012___sleep_hours___weekdays_or_workdays"] = _ru(4.8, 6.0, n)
    d["sld013___sleep_hours___weekends"] = _ru(7.5, 10.0, n)
    d["dpq040___feeling_tired_or_having_little_energy"] = _ri(1, 2, n)
    d["slq030___how_often_do_you_snore?"] = _ri(0, 1, n)
    d["kiq480___how_many_times_urinate_in_night?"] = np.zeros(n)
    d["bpq020___ever_told_you_had_high_blood_pressure"] = np.full(n, 2.0)
    d["cdq010___shortness_of_breath_on_stairs/inclines"] = np.full(n, 2.0)
    d["mcq010___ever_been_told_you_have_asthma"] = np.full(n, 2.0)
    return pd.DataFrame(d)


def generate_hard_negatives() -> pd.DataFrame:
    frames = [
        _fatigue_lookalike(90),
        _thyroid_like(60),
        _anemia_like(60),
        _perimenopause_like(50),
        _poor_sleep_hygiene(70),
    ]
    hard_neg = pd.concat(frames, ignore_index=True)
    assert (hard_neg[TARGET] == 0).all()
    return hard_neg


def build_pipeline() -> Pipeline:
    lr = LogisticRegression(
        penalty="l2",
        C=0.15,
        class_weight="balanced",
        max_iter=2000,
        random_state=SEED,
    )
    return Pipeline([
        ("imp", SimpleImputer(strategy="median", add_indicator=True)),
        ("lr", lr),
    ])


def main():
    print("=" * 60)
    print("  Sleep Disorder LR v3 - Hard-Negative Retraining (ML-SLEEP-02)")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH, low_memory=False)
    df = add_gender_female(df)
    print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]:,} columns")

    missing = [feature for feature in FEATURES + [TARGET] if feature not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    X_real = df[FEATURES]
    y_real = df[TARGET].fillna(0).astype(int)
    prevalence = float(y_real.mean())
    print(f"Target: {int(y_real.sum())} positives / {len(y_real)} total ({prevalence:.3%})")

    hard_neg = generate_hard_negatives()
    X_aug = pd.concat([X_real, hard_neg[FEATURES]], ignore_index=True)
    y_aug = pd.concat([y_real, hard_neg[TARGET].astype(int)], ignore_index=True)
    print(f"After augmentation: {int(y_aug.sum())} positives / {len(y_aug)} total")

    pipe = build_pipeline()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    auc_cv = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="roc_auc", n_jobs=1)
    ap_cv = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="average_precision", n_jobs=1)
    print(f"5-fold CV AUC:   {auc_cv.mean():.4f} +/- {auc_cv.std():.4f}")
    print(f"5-fold CV AUPRC: {ap_cv.mean():.4f} +/- {ap_cv.std():.4f}")

    pipe.fit(X_aug, y_aug)

    hard_neg_pred = pipe.predict_proba(hard_neg[FEATURES])[:, 1]
    pct_above_gate = float((hard_neg_pred >= PIPELINE_GATE).mean())
    pct_above_rec = float((hard_neg_pred >= RECOMMENDED_THRESHOLD).mean())
    print("\n-- Hard-negative validation --")
    print(f"Hard negatives >= {PIPELINE_GATE:.2f}: {pct_above_gate:.1%}")
    print(f"Hard negatives >= {RECOMMENDED_THRESHOLD:.2f}: {pct_above_rec:.1%}")
    print(f"Hard neg mean score: {hard_neg_pred.mean():.4f}")
    print(f"Hard neg max score:  {hard_neg_pred.max():.4f}")

    y_proba = pipe.predict_proba(X_real)[:, 1]
    full_auc = roc_auc_score(y_real, y_proba)
    full_ap = average_precision_score(y_real, y_proba)
    flag_rate_gate = float((y_proba >= PIPELINE_GATE).mean())
    flag_rate_rec = float((y_proba >= RECOMMENDED_THRESHOLD).mean())
    recall_gate = float((y_proba[y_real == 1] >= PIPELINE_GATE).mean())
    recall_rec = float((y_proba[y_real == 1] >= RECOMMENDED_THRESHOLD).mean())
    print("\n-- Full-train metrics on original data --")
    print(f"ROC-AUC: {full_auc:.4f}")
    print(f"AUPRC:   {full_ap:.4f}")
    print(f"Flag rate @ {PIPELINE_GATE:.2f}: {flag_rate_gate:.4f}")
    print(f"Flag rate @ {RECOMMENDED_THRESHOLD:.2f}: {flag_rate_rec:.4f}")
    print(f"Recall @ {PIPELINE_GATE:.2f}: {recall_gate:.4f}")
    print(f"Recall @ {RECOMMENDED_THRESHOLD:.2f}: {recall_rec:.4f}")

    out_model = MODELS_DIR / f"{MODEL_NAME}.joblib"
    out_meta = MODELS_DIR / f"{MODEL_NAME}_metadata.json"
    joblib.dump(pipe, out_model)
    print(f"\nModel saved -> {out_model}")

    meta = {
        "model": f"{MODEL_NAME}.joblib",
        "version": "v3",
        "condition": "sleep_disorder",
        "ml_ticket": "ML-SLEEP-02",
        "algorithm": "LogisticRegression L2 C=0.15 class_weight=balanced",
        "data_source": "nhanes_merged_adults_final_normalized.csv + 330 hard negatives",
        "n_train_original": int(len(y_real)),
        "n_hard_negatives": int(len(hard_neg)),
        "n_train_augmented": int(len(y_aug)),
        "n_positives": int(y_real.sum()),
        "prevalence": round(prevalence, 4),
        "features": FEATURES,
        "n_features": len(FEATURES),
        "cv_folds": 5,
        "cv_auc_mean": round(float(auc_cv.mean()), 4),
        "cv_auc_std": round(float(auc_cv.std()), 4),
        "cv_avg_precision": round(float(ap_cv.mean()), 4),
        "full_train_auc": round(float(full_auc), 4),
        "full_train_auprc": round(float(full_ap), 4),
        "flag_rate_at_pipeline_gate": round(flag_rate_gate, 4),
        "flag_rate_at_recommended_thr": round(flag_rate_rec, 4),
        "recall_at_pipeline_gate": round(recall_gate, 4),
        "recall_at_recommended_thr": round(recall_rec, 4),
        "pipeline_gate": PIPELINE_GATE,
        "recommended_threshold": RECOMMENDED_THRESHOLD,
        "hard_neg_validation": {
            "n_hard_negatives": int(len(hard_neg)),
            "pct_above_pipeline_gate": round(pct_above_gate, 4),
            "pct_above_recommended_thr": round(pct_above_rec, 4),
            "mean_score": round(float(hard_neg_pred.mean()), 4),
            "max_score": round(float(hard_neg_pred.max()), 4),
            "passed": bool(pct_above_rec <= 0.05),
        },
        "pipeline_steps": [
            "SimpleImputer(strategy=median, add_indicator=True)",
            "LogisticRegression(L2, class_weight=balanced, C=0.15)",
        ],
        "changes_from_v2": [
            "Dropped broad metabolic and unrelated disease proxy features",
            "Kept compact sleep-phenotype anchors only",
            "Added 330 hard negatives for fatigue, thyroid-like, anemia-like, perimenopause-like, and poor-sleep-hygiene lookalikes",
            "Retuned thresholding for a narrower, less generic sleep signal",
        ],
        "random_seed": SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out_meta.write_text(json.dumps(meta, indent=2))
    print(f"Metadata saved -> {out_meta}")


if __name__ == "__main__":
    main()
