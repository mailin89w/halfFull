"""
train_anemia_v6.py
------------------
ML-ANEMIA-02: raise recall after the v5 bias fix.

Strategy:
  - keep `gender_female` absent
  - keep the reproductive-history features from v5
  - add a few anemia-specific derived bundle features so positives can score
    higher from symptom/history combinations instead of a demographic shortcut
  - keep hard negatives, but lighter than v5 so the model is not over-suppressed
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
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline

_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _DIR.parent

DATA_PATH = _ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"
MODELS_DIR = _DIR
MODEL_NAME = "anemia_lr_symptom_bundle_v6"
TARGET = "anemia"
SEED = 42
RNG = np.random.default_rng(SEED)

BASE_FEATURES = [
    "age_years",
    "total_cholesterol_mg_dl",
    "fasting_glucose_mg_dl",
    "uacr_mg_g",
    "LBXSTP_total_protein_g_dl",
    "LBXWBCSI_white_blood_cell_count_1000_cells_ul",
    "huq010___general_health_condition",
    "huq071___overnight_hospital_patient_in_last_year",
    "med_count",
    "weight_kg",
    "dpq040___feeling_tired_or_having_little_energy",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "diq070___take_diabetic_pills_to_lower_blood_sugar",
    "bpq030___told_had_high_blood_pressure___2+_times",
    "mcq092___ever_receive_blood_transfusion",
    "mcq160a___ever_told_you_had_arthritis",
    "mcq160e___ever_told_you_had_heart_attack",
    "mcq160f___ever_told_you_had_stroke",
    "mcq160l___ever_told_you_had_any_liver_condition",
    "mcq010___ever_been_told_you_have_asthma",
    "mcq300c___close_relative_had_diabetes",
    "mcq366d___doctor_told_to_reduce_fat_in_diet",
    "mcq540___ever_seen_a_dr_about_this_pain",
    "kiq010___how_much_urine_lose_each_time?",
    "kiq042___leak_urine_during_physical_activities?",
    "kiq430___how_frequently_does_this_occur?",
    "alq111___ever_had_a_drink_of_any_kind_of_alcohol",
    "alq151___ever_have_4/5_or_more_drinks_every_day?",
    "smq020___smoked_at_least_100_cigarettes_in_life",
    "smq040___do_you_now_smoke_cigarettes?",
    "paq620___moderate_work_activity",
    "ocq180___hours_worked_last_week_in_total_all_jobs",
    "rhq131___ever_been_pregnant?",
    "whq040___like_to_weigh_more,_less_or_same",
    "whq070___tried_to_lose_weight_in_past_year",
    "rhq031___had_regular_periods_in_past_12_months",
    "rhq060___age_at_last_menstrual_period",
    "rhd143___are_you_pregnant_now?",
]

DERIVED_FEATURES = [
    "anemia_symptom_burden",
    "fatigue_sob_combo",
    "female_repro_signal",
]

FEATURES = BASE_FEATURES + DERIVED_FEATURES

PIPELINE_GATE = 0.35
RECOMMENDED_THRESHOLD = 0.40


def _ri(lo: int, hi: int, size: int) -> np.ndarray:
    return RNG.integers(lo, hi + 1, size=size).astype(float)


def _ru(lo: float, hi: float, size: int) -> np.ndarray:
    return RNG.uniform(lo, hi, size)


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    fat = out["dpq040___feeling_tired_or_having_little_energy"].fillna(0)
    sob = out["cdq010___shortness_of_breath_on_stairs/inclines"].fillna(9)
    health = out["huq010___general_health_condition"].fillna(3)
    hosp = out["huq071___overnight_hospital_patient_in_last_year"].fillna(2)
    reg_periods = out["rhq031___had_regular_periods_in_past_12_months"].fillna(9)
    preg_now = out["rhd143___are_you_pregnant_now?"].fillna(9)

    out["anemia_symptom_burden"] = (
        (fat >= 1).astype(float)
        + (sob <= 2).astype(float)
        + (health >= 3).astype(float)
        + (hosp == 1).astype(float)
    )
    out["fatigue_sob_combo"] = ((fat >= 1) & (sob <= 2)).astype(float)
    out["female_repro_signal"] = ((reg_periods == 1) | (preg_now == 1)).astype(float)
    return out


def _female_fatigue_negatives(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age_years": _ri(22, 48, n),
            "total_cholesterol_mg_dl": _ru(-0.5, 0.8, n),
            "fasting_glucose_mg_dl": _ru(-0.6, 0.4, n),
            "uacr_mg_g": _ru(-0.5, 0.5, n),
            "LBXSTP_total_protein_g_dl": _ru(-0.5, 0.4, n),
            "LBXWBCSI_white_blood_cell_count_1000_cells_ul": _ru(-0.3, 0.7, n),
            "huq010___general_health_condition": _ri(2, 4, n),
            "huq071___overnight_hospital_patient_in_last_year": np.full(n, 2.0),
            "med_count": _ru(-0.8, -0.15, n),
            "weight_kg": _ru(-0.4, 0.6, n),
            "dpq040___feeling_tired_or_having_little_energy": _ri(1, 3, n),
            "cdq010___shortness_of_breath_on_stairs/inclines": _ri(1, 2, n),
            "diq070___take_diabetic_pills_to_lower_blood_sugar": np.full(n, 2.0),
            "bpq030___told_had_high_blood_pressure___2+_times": np.full(n, 2.0),
            "mcq092___ever_receive_blood_transfusion": np.full(n, 2.0),
            "mcq160a___ever_told_you_had_arthritis": np.full(n, 2.0),
            "mcq160e___ever_told_you_had_heart_attack": np.full(n, 2.0),
            "mcq160f___ever_told_you_had_stroke": np.full(n, 2.0),
            "mcq160l___ever_told_you_had_any_liver_condition": np.full(n, 2.0),
            "mcq010___ever_been_told_you_have_asthma": _ri(1, 2, n),
            "mcq300c___close_relative_had_diabetes": _ri(1, 2, n),
            "mcq366d___doctor_told_to_reduce_fat_in_diet": np.full(n, 2.0),
            "mcq540___ever_seen_a_dr_about_this_pain": np.full(n, 2.0),
            "kiq010___how_much_urine_lose_each_time?": _ri(1, 3, n),
            "kiq042___leak_urine_during_physical_activities?": _ri(1, 2, n),
            "kiq430___how_frequently_does_this_occur?": _ri(1, 3, n),
            "alq111___ever_had_a_drink_of_any_kind_of_alcohol": _ri(1, 2, n),
            "alq151___ever_have_4/5_or_more_drinks_every_day?": np.full(n, 2.0),
            "smq020___smoked_at_least_100_cigarettes_in_life": _ri(1, 2, n),
            "smq040___do_you_now_smoke_cigarettes?": _ri(1, 2, n),
            "paq620___moderate_work_activity": _ri(1, 2, n),
            "ocq180___hours_worked_last_week_in_total_all_jobs": _ru(-0.5, 0.5, n),
            "rhq131___ever_been_pregnant?": _ri(1, 2, n),
            "whq040___like_to_weigh_more,_less_or_same": _ri(2, 3, n),
            "whq070___tried_to_lose_weight_in_past_year": _ri(1, 2, n),
            "rhq031___had_regular_periods_in_past_12_months": np.full(n, 1.0),
            "rhq060___age_at_last_menstrual_period": _ru(-0.3, 0.3, n),
            "rhd143___are_you_pregnant_now?": np.full(n, 2.0),
            TARGET: np.zeros(n),
        }
    )


def _perimenopause_like_negatives(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age_years": _ri(40, 55, n),
            "total_cholesterol_mg_dl": _ru(-0.5, 0.8, n),
            "fasting_glucose_mg_dl": _ru(-0.6, 0.4, n),
            "uacr_mg_g": _ru(-0.5, 0.5, n),
            "LBXSTP_total_protein_g_dl": _ru(-0.2, 0.5, n),
            "LBXWBCSI_white_blood_cell_count_1000_cells_ul": _ru(-0.2, 0.8, n),
            "huq010___general_health_condition": _ri(2, 4, n),
            "huq071___overnight_hospital_patient_in_last_year": np.full(n, 2.0),
            "med_count": _ru(-0.5, 0.3, n),
            "weight_kg": _ru(0.1, 1.0, n),
            "dpq040___feeling_tired_or_having_little_energy": _ri(1, 3, n),
            "cdq010___shortness_of_breath_on_stairs/inclines": _ri(1, 2, n),
            "diq070___take_diabetic_pills_to_lower_blood_sugar": np.full(n, 2.0),
            "bpq030___told_had_high_blood_pressure___2+_times": _ri(1, 2, n),
            "mcq092___ever_receive_blood_transfusion": np.full(n, 2.0),
            "mcq160a___ever_told_you_had_arthritis": _ri(1, 2, n),
            "mcq160e___ever_told_you_had_heart_attack": np.full(n, 2.0),
            "mcq160f___ever_told_you_had_stroke": np.full(n, 2.0),
            "mcq160l___ever_told_you_had_any_liver_condition": np.full(n, 2.0),
            "mcq010___ever_been_told_you_have_asthma": _ri(1, 2, n),
            "mcq300c___close_relative_had_diabetes": _ri(1, 2, n),
            "mcq366d___doctor_told_to_reduce_fat_in_diet": np.full(n, 2.0),
            "mcq540___ever_seen_a_dr_about_this_pain": np.full(n, 2.0),
            "kiq010___how_much_urine_lose_each_time?": _ri(1, 3, n),
            "kiq042___leak_urine_during_physical_activities?": _ri(1, 2, n),
            "kiq430___how_frequently_does_this_occur?": _ri(1, 3, n),
            "alq111___ever_had_a_drink_of_any_kind_of_alcohol": _ri(1, 2, n),
            "alq151___ever_have_4/5_or_more_drinks_every_day?": np.full(n, 2.0),
            "smq020___smoked_at_least_100_cigarettes_in_life": _ri(1, 2, n),
            "smq040___do_you_now_smoke_cigarettes?": _ri(1, 2, n),
            "paq620___moderate_work_activity": _ri(1, 2, n),
            "ocq180___hours_worked_last_week_in_total_all_jobs": _ru(-0.5, 0.5, n),
            "rhq131___ever_been_pregnant?": np.full(n, 1.0),
            "whq040___like_to_weigh_more,_less_or_same": _ri(2, 3, n),
            "whq070___tried_to_lose_weight_in_past_year": _ri(1, 2, n),
            "rhq031___had_regular_periods_in_past_12_months": np.full(n, 2.0),
            "rhq060___age_at_last_menstrual_period": _ru(0.8, 2.0, n),
            "rhd143___are_you_pregnant_now?": np.full(n, 2.0),
            TARGET: np.zeros(n),
        }
    )


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imp", SimpleImputer(strategy="median", add_indicator=True)),
            ("clf", LogisticRegression(class_weight="balanced", C=1.5, max_iter=3000, random_state=SEED)),
        ]
    )


def main() -> None:
    print("=" * 60)
    print("  Anemia LR v6 — Symptom Bundle + Lighter Hard Negatives")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH, low_memory=False)
    missing = [c for c in BASE_FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X_real = _add_derived_columns(df[BASE_FEATURES])
    y_real = df[TARGET].fillna(0).astype(int)
    prevalence = float(y_real.mean())
    print(f"Loaded: {len(df):,} rows")
    print(f"Target prevalence: {prevalence:.3%} ({int(y_real.sum())}/{len(y_real)})")

    hard_neg = pd.concat(
        [_female_fatigue_negatives(100), _perimenopause_like_negatives(80)],
        ignore_index=True,
    )
    X_hard = _add_derived_columns(hard_neg[BASE_FEATURES])
    y_hard = hard_neg[TARGET].astype(int)
    print(f"Hard negatives: {len(hard_neg):,}")

    X = pd.concat([X_real, X_hard], ignore_index=True)
    y = pd.concat([y_real, y_hard], ignore_index=True)

    pipe = build_pipeline()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)

    auc_scores = cross_val_score(pipe, X[FEATURES], y, cv=cv, scoring="roc_auc", n_jobs=1)
    ap_scores = cross_val_score(pipe, X[FEATURES], y, cv=cv, scoring="average_precision", n_jobs=1)
    oof = cross_val_predict(pipe, X[FEATURES], y, cv=cv, method="predict_proba", n_jobs=1)[:, 1]

    pipe.fit(X[FEATURES], y)
    train_proba = pipe.predict_proba(X[FEATURES])[:, 1]

    recall_gate = float(((train_proba[: len(y_real)] >= PIPELINE_GATE) & (y_real == 1)).sum() / max(int(y_real.sum()), 1))
    recall_rec = float(((train_proba[: len(y_real)] >= RECOMMENDED_THRESHOLD) & (y_real == 1)).sum() / max(int(y_real.sum()), 1))

    model_path = MODELS_DIR / f"{MODEL_NAME}.joblib"
    meta_path = MODELS_DIR / f"{MODEL_NAME}_metadata.json"

    joblib.dump(pipe, model_path)

    metadata = {
        "model": f"{MODEL_NAME}.joblib",
        "version": "v6",
        "condition": "anemia",
        "ml_ticket": "ML-ANEMIA-02",
        "algorithm": "LogisticRegression L2 C=1.5 class_weight=balanced",
        "data_source": "nhanes_merged_adults_final_normalized.csv + lighter female hard negatives",
        "n_train_original": int(len(y_real)),
        "n_hard_negatives": int(len(y_hard)),
        "n_train_augmented": int(len(y)),
        "n_positives": int(y_real.sum()),
        "prevalence": prevalence,
        "features": FEATURES,
        "base_features": BASE_FEATURES,
        "derived_features": DERIVED_FEATURES,
        "n_features": len(FEATURES),
        "cv_folds": 5,
        "cv_auc_mean": round(float(auc_scores.mean()), 4),
        "cv_auc_std": round(float(auc_scores.std()), 4),
        "cv_avg_precision": round(float(ap_scores.mean()), 4),
        "oof_mean_score": round(float(oof.mean()), 4),
        "full_train_auc": round(float(roc_auc_score(y, train_proba)), 4),
        "full_train_auprc": round(float(average_precision_score(y, train_proba)), 4),
        "recall_at_pipeline_gate": round(recall_gate, 4),
        "recall_at_recommended_thr": round(recall_rec, 4),
        "pipeline_gate": PIPELINE_GATE,
        "recommended_threshold": RECOMMENDED_THRESHOLD,
        "pipeline_steps": [
            "SimpleImputer(strategy=median, add_indicator=True)",
            "LogisticRegression(L2, class_weight=balanced, C=1.5)",
        ],
        "gender_bias_fix": "gender_female absent; symptom bundle + reproductive proxies replace demographic shortcut",
        "changes_from_v5": [
            "Added anemia_symptom_burden derived feature",
            "Added fatigue_sob_combo derived feature",
            "Added female_repro_signal derived feature",
            "Reduced hard-negative pressure vs v5 to recover recall",
            "Lowered recommended threshold from 0.60 to 0.40",
        ],
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"5-fold CV AUC:   {auc_scores.mean():.4f} ± {auc_scores.std():.4f}")
    print(f"5-fold CV AUPRC: {ap_scores.mean():.4f}")
    print(f"Recall @0.35: {recall_gate:.4f}")
    print(f"Recall @0.40: {recall_rec:.4f}")
    print(f"\nSaved: {model_path}")
    print(f"Saved: {meta_path}")


if __name__ == "__main__":
    main()
