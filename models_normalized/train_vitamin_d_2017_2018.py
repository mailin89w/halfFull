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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline


_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ROOT = _DIR.parent

DATA_PATH = ROOT / "data" / "processed" / "normalized" / "nhanes_2017_2018_vitd_real_cohort_normalized.csv"
OUTPUT_DIR = ROOT / "data" / "processed" / "model_outputs_vitamin_d_2017_2018"
MODELS_DIR = _DIR
TARGET = "vitamin_d_deficiency"
TARGET_DEFINITION = "25(OH) vitamin D < 50 nmol/L"
FEATURES = [
    "age_years",
    "alq130_avg_drinks_per_day",
    "bmi",
    "bpq020_high_bp",
    "bpq080_high_cholesterol",
    "cdq010_sob_stairs",
    "diq010_diabetes",
    "diq050_insulin",
    "diq070_diabetes_pills",
    "dpq040_fatigue",
    "education_ord",
    "gender_female",
    "huq010_general_health",
    "huq071_hospital",
    "kiq005_urinary_leakage_freq",
    "kiq022_weak_kidneys",
    "kiq042_leak_exertion",
    "kiq044_urge_incontinence",
    "kiq480_nocturia",
    "mcq053_anemia_treatment",
    "mcq080_overweight_dx",
    "mcq092_transfusion",
    "mcq160a_arthritis",
    "mcq160b_heart_failure",
    "mcq160l_liver_condition",
    "mcq300c_family_diabetes",
    "med_count",
    "ocq180_hours_worked_week",
    "pregnancy_status_bin",
    "rhq031_regular_periods",
    "rhq060_age_last_period",
    "rhq131_ever_pregnant",
    "rhq540_hormone_use",
    "slq030_snore_freq",
    "slq050_sleep_trouble_doctor",
    "smq040_smoke_now",
    "total_protein_g_dl",
    "wbc_1000_cells_ul",
    "weight_kg",
    "whq040_weight_preference",
    "whq070_tried_to_lose_weight",
]
LEAKAGE_COLUMNS = {"vitamin_d_25oh_nmol_l", "vitamin_d_deficiency"}


def build_lr() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", LogisticRegression(max_iter=4000, solver="liblinear", class_weight="balanced")),
    ])


def build_rf_cal() -> Pipeline:
    rf = RandomForestClassifier(
        n_estimators=400,
        max_depth=6,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    cal = CalibratedClassifierCV(rf, method="isotonic", cv=3)
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", cal),
    ])


def threshold_sweep(y: pd.Series, proba: np.ndarray, model_name: str) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for threshold in np.arange(0.10, 0.91, 0.05):
        pred = proba >= threshold
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
        rows.append({
            "model": model_name,
            "threshold": round(float(threshold), 2),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "flag_count": int(pred.sum()),
            "flag_rate": float(pred.mean()),
        })
    return rows


def train_and_eval(name: str, pipe: Pipeline, X: pd.DataFrame, y: pd.Series, cv: StratifiedKFold) -> tuple[dict, Pipeline]:
    oof = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    auc = roc_auc_score(y, oof)
    ap = average_precision_score(y, oof)
    sweep = threshold_sweep(y, oof, name)
    best = max(sweep, key=lambda row: (row["f1"], row["precision"], row["recall"]))
    pipe.fit(X, y)
    return {
        "model": name,
        "auc": auc,
        "auprc": ap,
        "best_threshold": best["threshold"],
        "best_precision": best["precision"],
        "best_recall": best["recall"],
        "best_f1": best["f1"],
        "sweep": sweep,
    }, pipe


def main() -> None:
    df = pd.read_csv(DATA_PATH, low_memory=False)
    df["gender_female"] = np.where(df["gender"].eq("Female"), 1.0, np.where(df["gender"].isna(), np.nan, 0.0))
    edu = pd.to_numeric(df["education_code"], errors="coerce")
    df["education_ord"] = np.where(edu.between(1, 5), edu - 1, np.nan)
    preg = pd.to_numeric(df["pregnancy_status_code"], errors="coerce")
    df["pregnancy_status_bin"] = np.where(preg.eq(1), 1.0, np.where(preg.eq(2), 0.0, np.nan))

    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    work = df[df[TARGET].notna()].copy()
    X = work[FEATURES]
    y = work[TARGET].astype(int)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    results = []
    trained = {}
    for name, pipe in [("lr", build_lr()), ("rf_cal", build_rf_cal())]:
        metrics, fit_pipe = train_and_eval(name, pipe, X, y, cv)
        results.append(metrics)
        trained[name] = fit_pipe

    best = max(results, key=lambda row: (row["auc"], row["auprc"], row["best_f1"]))
    best_name = best["model"]
    best_pipe = trained[best_name]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model_name = f"vitamin_d_deficiency_2017_2018_{best_name}_aligned"
    model_path = MODELS_DIR / f"{model_name}.joblib"
    meta_path = MODELS_DIR / f"{model_name}_metadata.json"
    comparison_path = OUTPUT_DIR / "vitamin_d_model_comparison_2017_2018.csv"
    sweep_path = OUTPUT_DIR / "vitamin_d_threshold_sweep_2017_2018.csv"

    joblib.dump(best_pipe, model_path)
    pd.DataFrame([{k: v for k, v in row.items() if k != "sweep"} for row in results]).to_csv(comparison_path, index=False)
    pd.DataFrame([s for row in results for s in row["sweep"]]).to_csv(sweep_path, index=False)

    metadata = {
        "model": model_path.name,
        "version": "2017_2018_aligned_v1",
        "condition": TARGET,
        "target_column": TARGET,
        "target_definition": TARGET_DEFINITION,
        "algorithm": best_name,
        "data_source": DATA_PATH.name,
        "n_train": int(len(y)),
        "prevalence": float(y.mean()),
        "features": FEATURES,
        "n_features": len(FEATURES),
        "recommended_threshold": best["best_threshold"],
        "pipeline_gate": best["best_threshold"],
        "auc_oof": round(float(best["auc"]), 4),
        "auprc_oof": round(float(best["auprc"]), 4),
        "best_f1_oof": round(float(best["best_f1"]), 4),
        "leakage_removed": sorted(LEAKAGE_COLUMNS),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(pd.DataFrame([{k: v for k, v in row.items() if k != "sweep"} for row in results]).to_string(index=False))
    print(f"\nSaved best model to {model_path}")
    print(f"Saved metadata to {meta_path}")
    print(f"Saved comparison to {comparison_path}")
    print(f"Saved threshold sweep to {sweep_path}")


if __name__ == "__main__":
    main()
