"""
train_anemia_v5.py
------------------
ML-ANEMIA-01: remove residual sex-driven shortcut from anemia ranking.

Goals:
  - keep `gender_female` fully absent from the feature set
  - restore female-specific anemia signal through reproductive/history proxies
  - suppress false positives on female fatigue/perimenopause-like negatives

Validation target on the 760 cohort at the current anemia threshold (0.60):
  - precision should improve materially vs. v4
  - flag rate should drop below 20%
  - top-1 should not regress
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
MODEL_NAME = "anemia_lr_repro_hist_v5"
TARGET = "anemia"
SEED = 42
RNG = np.random.default_rng(SEED)

FEATURES = [
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

PIPELINE_GATE = 0.35
RECOMMENDED_THRESHOLD = 0.60


def _ri(lo: int, hi: int, size: int) -> np.ndarray:
    return RNG.integers(lo, hi + 1, size=size).astype(float)


def _ru(lo: float, hi: float, size: int) -> np.ndarray:
    return RNG.uniform(lo, hi, size)


def _female_fatigue_negatives(n: int) -> pd.DataFrame:
    """
    Non-anemia females with fatigue and mild overlap features.
    Intended to stop the model from treating "female + tired" as anemia.
    """
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
    """
    Female 40-55 fatigue/cycle-change profiles that should not become anemia.
    """
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


def _male_fatigue_negatives(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age_years": _ri(28, 60, n),
            "total_cholesterol_mg_dl": _ru(-0.5, 0.8, n),
            "fasting_glucose_mg_dl": _ru(-0.6, 0.4, n),
            "uacr_mg_g": _ru(-0.5, 0.5, n),
            "LBXSTP_total_protein_g_dl": _ru(-0.4, 0.5, n),
            "LBXWBCSI_white_blood_cell_count_1000_cells_ul": _ru(-0.3, 0.8, n),
            "huq010___general_health_condition": _ri(2, 4, n),
            "huq071___overnight_hospital_patient_in_last_year": np.full(n, 2.0),
            "med_count": _ru(-0.8, 0.2, n),
            "weight_kg": _ru(-0.1, 1.2, n),
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
            "rhq131___ever_been_pregnant?": np.full(n, np.nan),
            "whq040___like_to_weigh_more,_less_or_same": _ri(2, 3, n),
            "whq070___tried_to_lose_weight_in_past_year": _ri(1, 2, n),
            "rhq031___had_regular_periods_in_past_12_months": np.full(n, np.nan),
            "rhq060___age_at_last_menstrual_period": np.full(n, np.nan),
            "rhd143___are_you_pregnant_now?": np.full(n, np.nan),
            TARGET: np.zeros(n),
        }
    )


def generate_hard_negatives() -> pd.DataFrame:
    frames = [
        _female_fatigue_negatives(140),
        _perimenopause_like_negatives(120),
        _male_fatigue_negatives(60),
    ]
    hard_neg = pd.concat(frames, ignore_index=True)
    assert (hard_neg[TARGET] == 0).all()
    return hard_neg


def build_pipeline() -> Pipeline:
    lr = LogisticRegression(
        class_weight="balanced",
        C=1.0,
        max_iter=2000,
        random_state=SEED,
    )
    return Pipeline(
        [
            ("imp", SimpleImputer(strategy="median", add_indicator=True)),
            ("clf", lr),
        ]
    )


def main() -> None:
    print("=" * 60)
    print("  Anemia LR v5 — Reproductive History + Hard Negatives")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH, low_memory=False)
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X_real = df[FEATURES]
    y_real = df[TARGET].fillna(0).astype(int)
    prevalence = float(y_real.mean())
    print(f"Loaded: {len(df):,} rows")
    print(f"Target prevalence: {prevalence:.3%} ({int(y_real.sum())}/{len(y_real)})")

    hard_neg = generate_hard_negatives()
    X_aug = pd.concat([X_real, hard_neg[FEATURES]], ignore_index=True)
    y_aug = pd.concat([y_real, hard_neg[TARGET].astype(int)], ignore_index=True)
    print(f"Augmented train size: {len(y_aug):,} rows ({len(hard_neg)} hard negatives)")

    pipe = build_pipeline()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    auc_cv = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="roc_auc", n_jobs=1)
    ap_cv = cross_val_score(pipe, X_aug, y_aug, cv=cv, scoring="average_precision", n_jobs=1)
    oof = cross_val_predict(pipe, X_aug, y_aug, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    print(f"5-fold CV AUC:   {auc_cv.mean():.4f} ± {auc_cv.std():.4f}")
    print(f"5-fold CV AUPRC: {ap_cv.mean():.4f} ± {ap_cv.std():.4f}")

    pipe.fit(X_aug, y_aug)

    y_proba = pipe.predict_proba(X_real)[:, 1]
    hard_neg_pred = pipe.predict_proba(hard_neg[FEATURES])[:, 1]
    full_auc = roc_auc_score(y_real, y_proba)
    full_ap = average_precision_score(y_real, y_proba)
    recall_gate = float((y_proba[y_real == 1] >= PIPELINE_GATE).mean())
    recall_rec = float((y_proba[y_real == 1] >= RECOMMENDED_THRESHOLD).mean())
    hard_fp_060 = float((hard_neg_pred >= RECOMMENDED_THRESHOLD).mean())

    print(f"Full-train AUC:   {full_auc:.4f}")
    print(f"Full-train AUPRC: {full_ap:.4f}")
    print(f"Recall @{PIPELINE_GATE:.2f}: {recall_gate:.4f}")
    print(f"Recall @{RECOMMENDED_THRESHOLD:.2f}: {recall_rec:.4f}")
    print(f"Hard neg >= {RECOMMENDED_THRESHOLD:.2f}: {hard_fp_060:.1%}")

    out_model = MODELS_DIR / f"{MODEL_NAME}.joblib"
    out_meta = MODELS_DIR / f"{MODEL_NAME}_metadata.json"
    joblib.dump(pipe, out_model)

    metadata = {
        "model": f"{MODEL_NAME}.joblib",
        "version": "v5",
        "condition": "anemia",
        "ml_ticket": "ML-ANEMIA-01",
        "algorithm": "LogisticRegression L2 C=1.0 class_weight=balanced",
        "data_source": "nhanes_merged_adults_final_normalized.csv + female/male hard negatives",
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
        "oof_mean_score": round(float(np.mean(oof)), 4),
        "full_train_auc": round(float(full_auc), 4),
        "full_train_auprc": round(float(full_ap), 4),
        "recall_at_pipeline_gate": round(recall_gate, 4),
        "recall_at_recommended_thr": round(recall_rec, 4),
        "pipeline_gate": PIPELINE_GATE,
        "recommended_threshold": RECOMMENDED_THRESHOLD,
        "hard_neg_validation": {
            "pct_above_recommended_threshold": round(hard_fp_060, 4),
            "mean_score": round(float(np.mean(hard_neg_pred)), 4),
            "max_score": round(float(np.max(hard_neg_pred)), 4),
        },
        "pipeline_steps": [
            "SimpleImputer(strategy=median, add_indicator=True)",
            "LogisticRegression(L2, class_weight=balanced, C=1.0)",
        ],
        "gender_bias_fix": "gender_female absent; reproductive proxies + female hard negatives used instead",
        "new_features_vs_v4": [
            "rhq031___had_regular_periods_in_past_12_months",
            "rhq060___age_at_last_menstrual_period",
            "rhd143___are_you_pregnant_now?",
        ],
        "removed_v4_features": [
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    out_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved model → {out_model}")
    print(f"Saved metadata → {out_meta}")


if __name__ == "__main__":
    main()
