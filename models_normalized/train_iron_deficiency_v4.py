"""
train_iron_deficiency_v4.py
----------------------------
Retrain iron_deficiency model without CBC markers (Hgb, MCV, RDW, MCH).

Background
----------
v3 (39 features) added LBXHGB, LBXMCVSI, LBXRDW, LBXMCHSI to the v2 feature
set, boosting AUC from 0.8094 → 0.8853.  However those 4 markers come from a
full blood count which users cannot self-report; they are unavailable at quiz
time.  v4 reverts to the 35 non-CBC features from v2 and retrains.

Target: iron_deficiency (ferritin < 30 ng/mL AND transferrin_saturation < 20%)
Algorithm: RF+cal  (same as v2/v3)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

# ── Paths ───────────────────────────────────────────────────────────────────────
_DIR  = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _DIR.parent

DATA_PATH   = _ROOT / "data" / "processed" / "nhanes_merged_adults_final_normalized.csv"
MODELS_DIR  = _DIR
MODEL_NAME  = "iron_deficiency_rf_cal_deduped35_v4"

# ── Feature list: v3 features MINUS the 4 CBC markers ──────────────────────────
# (first 35 of the 39 v3 features; CBC markers were appended last)
FEATURES = [
    "age_years",
    "triglycerides_mg_dl",
    "total_cholesterol_mg_dl",
    "fasting_glucose_mg_dl",
    "huq010___general_health_condition",
    "med_count",
    "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "bmi",
    "dpq040___feeling_tired_or_having_little_energy",
    "paq665___moderate_recreational_activities",
    "diq070___take_diabetic_pills_to_lower_blood_sugar",
    "kiq480___how_many_times_urinate_in_night?",
    "paq650___vigorous_recreational_activities",
    "sld013___sleep_hours___weekends",
    "slq030___how_often_do_you_snore?",
    "cdq010___shortness_of_breath_on_stairs/inclines",
    "kiq044___urinated_before_reaching_the_toilet?",
    "mcq053___taking_treatment_for_anemia/past_3_mos",
    "mcq092___ever_receive_blood_transfusion",
    "ocq670___overall_work_schedule_past_3_months",
    "pad680___minutes_sedentary_activity",
    "rhq060___age_at_last_menstrual_period",
    "LBXWBCSI_white_blood_cell_count_1000_cells_ul",
    "education_ord",
    "heq030___ever_told_you_have_hepatitis_c?",
    "huq051___#times_receive_healthcare_over_past_year",
    "kiq010___how_much_urine_lose_each_time?",
    "kiq052___how_much_were_daily_activities_affected?",
    "kiq450___how_frequently_does_this_occur?",
    "mcq010___ever_been_told_you_have_asthma",
    "mcq300c___close_relative_had_diabetes",
    "ocq180___hours_worked_last_week_in_total_all_jobs",
    "paq620___moderate_work_activity",
    "rhq160___how_many_times_have_been_pregnant?",
    "smq020___smoked_at_least_100_cigarettes_in_life",
]

TARGET = "iron_deficiency"

REMOVED_CBC = [
    "LBXHGB_hemoglobin_g_dl",
    "LBXMCVSI_mean_cell_volume_fl",
    "LBXRDW_red_cell_distribution_width",
    "LBXMCHSI_mean_cell_hemoglobin_pg",
]

RECOMMENDED_THRESHOLD = 0.15
PIPELINE_GATE         = 0.35


def build_pipeline(random_state: int = 42) -> Pipeline:
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=10,
        random_state=random_state,
        n_jobs=-1,
    )
    cal = CalibratedClassifierCV(rf, method="isotonic", cv=3)
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf",     cal),
    ])


def main() -> None:
    print("=" * 60)
    print("  Iron Deficiency RF+cal v4  (no CBC features)")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH, low_memory=False)
    print(f"Loaded: {df.shape[0]:,} rows × {df.shape[1]:,} columns")

    # Derive education_ord from the text-label education column
    _EDU_ORDER = {
        "Less than 9th grade":       0,
        "9-11th grade":              1,
        "High school / GED":         2,
        "Some college / AA":         3,
        "College graduate or above": 4,
    }
    if "education" in df.columns:
        df["education_ord"] = df["education"].map(_EDU_ORDER)

    missing = [f for f in FEATURES + [TARGET] if f not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    X = df[FEATURES]
    y = df[TARGET].astype(int)
    prevalence = y.mean()
    print(f"Target: {y.sum()} positives / {len(y)} total  ({prevalence:.3%})")

    # 5-fold stratified CV
    pipe = build_pipeline()
    cv   = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    auc_scores = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc", n_jobs=1)
    ap_scores  = cross_val_score(pipe, X, y, cv=cv, scoring="average_precision", n_jobs=1)

    cv_auc = float(auc_scores.mean())
    cv_ap  = float(ap_scores.mean())
    print(f"5-fold CV AUC:   {cv_auc:.4f} ± {auc_scores.std():.4f}")
    print(f"5-fold CV AUPRC: {cv_ap:.4f} ± {ap_scores.std():.4f}")

    # Final fit on full dataset
    pipe.fit(X, y)
    y_proba = pipe.predict_proba(X)[:, 1]
    full_auc = roc_auc_score(y, y_proba)
    full_ap  = average_precision_score(y, y_proba)
    print(f"Full-train AUC:   {full_auc:.4f}")
    print(f"Full-train AUPRC: {full_ap:.4f}")

    # Save model
    model_path = MODELS_DIR / f"{MODEL_NAME}.joblib"
    meta_path  = MODELS_DIR / f"{MODEL_NAME}_metadata.json"

    joblib.dump(pipe, model_path)

    metadata = {
        "model":       f"{MODEL_NAME}.joblib",
        "version":     "v4",
        "condition":   "iron_deficiency",
        "target_column": TARGET,
        "target_definition": (
            "ferritin < 30 ng/mL AND transferrin_saturation < 20% "
            "(functional iron deficiency)"
        ),
        "algorithm": (
            "RandomForest(n=300, max_depth=6, min_leaf=10) + "
            "CalibratedClassifierCV(isotonic, cv=3)"
        ),
        "data_source":   "nhanes_merged_adults_final_normalized.csv",
        "n_train":       int(len(y)),
        "prevalence":    prevalence,
        "features":      FEATURES,
        "n_features":    len(FEATURES),
        "cv_folds":      5,
        "cv_auc_mean":   round(cv_auc, 4),
        "cv_avg_precision": round(cv_ap, 4),
        "recommended_threshold": RECOMMENDED_THRESHOLD,
        "pipeline_gate": PIPELINE_GATE,
        "pipeline_steps": [
            "SimpleImputer(strategy=median)",
            "CalibratedClassifierCV(RandomForestClassifier, method=isotonic, cv=3)",
        ],
        "leakage_removed": [
            "LBXFER_ferritin_ng_ml (defines target — ferritin<30)",
            "LBDPCT_transferrin_saturation (defines target — tsat<20%)",
            "LBXSIR / LBXIRN serum iron (direct iron panel)",
            "LBDTIB TIBC (direct iron panel)",
            "LBXTFR transferrin receptor (direct iron panel)",
        ],
        "cbc_features_removed_vs_v3": REMOVED_CBC,
        "cbc_removal_reason": (
            "CBC markers (Hgb, MCV, RDW, MCH) cannot be self-reported by users "
            "at quiz time. v4 restores the v2 feature set (35 non-CBC features) "
            "to match what is available in the product."
        ),
        "changes_from_v3": [
            "Removed LBXHGB_hemoglobin_g_dl",
            "Removed LBXMCVSI_mean_cell_volume_fl",
            "Removed LBXRDW_red_cell_distribution_width",
            "Removed LBXMCHSI_mean_cell_hemoglobin_pg",
            f"AUC: 0.8853 (v3) → {cv_auc:.4f} (v4 CV)",
            f"AUPRC: 0.5533 (v3) → {cv_ap:.4f} (v4 CV)",
        ],
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✓ Saved: {model_path}")
    print(f"✓ Saved: {meta_path}")
    print(f"\nSummary: AUC={cv_auc:.4f}  AUPRC={cv_ap:.4f}  features={len(FEATURES)}")


if __name__ == "__main__":
    main()
