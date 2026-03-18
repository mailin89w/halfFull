"""
anemia_checkup_v2_model.py
--------------------------
Anemia prediction — v2: core checkup features only (no hepatitis B/C).

Rationale for v2:
  Hepatitis B/C screening is a *one-time* test in the German checkup, not
  routinely repeated. Because it is not reliably available for all users
  at every checkup, it is removed from the feature set to make the model
  deployable for any checkup encounter.

Allowed features (v2 — 8 features):
  - Lipid panel: total cholesterol, LDL, HDL, triglycerides
  - Fasting blood glucose
  - Demographics: age, gender, BMI

Removed vs v1:
  - Hepatitis B: surface antibody, core antibody, surface antigen
  - Hepatitis C: confirmed antibody, RNA

Still not available in dataset:
  - Urine dipstick (protein, glucose, erythrocytes, leukocytes, nitrite)
    — NHANES P_UA.xpt not ingested into the pipeline
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report,
    confusion_matrix
)
from xgboost import XGBClassifier

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "nhanes_merged_adults_final.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ── Feature definitions (v2 — hepatitis removed) ───────────────────────────────
RAW_FEATURE_COLS = [
    "total_cholesterol_mg_dl",
    "hdl_cholesterol_mg_dl",
    "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
    "triglycerides_mg_dl",
    "fasting_glucose_mg_dl",
    "age_years",
    "gender",
    "bmi",
]

TARGET_COL = "anemia"

ENCODED_FEATURE_NAMES = [
    "total_cholesterol_mg_dl",
    "hdl_cholesterol_mg_dl",
    "ldl_cholesterol_mg_dl",
    "triglycerides_mg_dl",
    "fasting_glucose_mg_dl",
    "age_years",
    "gender_female",
    "bmi",
]


# ── Data loading & preparation ─────────────────────────────────────────────────

def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded dataset: {df.shape[0]} rows × {df.shape[1]} columns")
    return df


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Extract and encode features for the v2 German checkup anemia model.
    Hepatitis B/C features are excluded entirely.
    """
    missing_cols = [c for c in RAW_FEATURE_COLS + [TARGET_COL] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Required columns not found in dataset: {missing_cols}")

    subset = df[RAW_FEATURE_COLS + [TARGET_COL]].copy()

    # Gender encoding: Female → 1, Male → 0, NaN preserved
    subset["gender"] = (subset["gender"] == "Female").astype(float)
    subset.loc[df["gender"].isna(), "gender"] = np.nan

    rename_map = dict(zip(RAW_FEATURE_COLS, ENCODED_FEATURE_NAMES))
    subset.rename(columns=rename_map, inplace=True)

    X = subset[ENCODED_FEATURE_NAMES]
    y = subset[TARGET_COL]

    print(f"\nFeature matrix shape: {X.shape}")
    print(f"Target distribution:\n{y.value_counts().to_string()}")
    print(f"\nMissing values per feature (%):")
    print((X.isnull().mean() * 100).round(1).to_string())

    return X, y


def split_data(X: pd.DataFrame, y: pd.Series,
               test_size: float = 0.2,
               random_state: int = 42) -> tuple:
    """Stratified 80/20 train/test split. Same seed as v1 for fair comparison."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    print(f"\nTrain: {X_train.shape[0]} rows | Test: {X_test.shape[0]} rows")
    print(f"Train prevalence: {y_train.mean():.3f} | Test prevalence: {y_test.mean():.3f}")
    return X_train, X_test, y_train, y_test


# ── Model pipelines (identical architecture to v1 for fair comparison) ─────────

def build_lr_pipeline(random_state: int = 42) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
            C=1.0,
        )),
    ])


def build_xgb_pipeline(random_state: int = 42) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            scale_pos_weight=19,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=random_state,
            verbosity=0,
        )),
    ])


# ── Evaluation ─────────────────────────────────────────────────────────────────

def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series,
                   threshold: float = 0.5,
                   model_name: str = "Model") -> dict:
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    metrics = {
        "model": model_name,
        "threshold": threshold,
        "accuracy":  round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall":    round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1":        round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc":   round(roc_auc_score(y_test, y_proba), 4),
    }

    print(f"\n{'='*50}")
    print(f"  {model_name} (threshold={threshold})")
    print(f"{'='*50}")
    for k, v in metrics.items():
        if k not in ("model", "threshold"):
            print(f"  {k:12s}: {v}")
    print(f"\nClassification Report:\n{classification_report(y_test, y_pred, zero_division=0)}")
    print(f"Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

    return metrics


def cross_validate_model(model, X: pd.DataFrame, y: pd.Series,
                          n_splits: int = 5, scoring: str = "roc_auc") -> float:
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring=scoring)
    print(f"  CV {scoring}: {scores.mean():.4f} ± {scores.std():.4f}")
    return scores.mean()


# ── Saving ─────────────────────────────────────────────────────────────────────

def save_model(model, model_name: str, metrics: dict, models_dir: str = MODELS_DIR) -> str:
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f"{model_name}.joblib")
    meta_path  = os.path.join(models_dir, f"{model_name}_metadata.json")

    joblib.dump(model, model_path)

    metadata = {
        "model_name": model_name,
        "version": "v2",
        "feature_names": ENCODED_FEATURE_NAMES,
        "n_features": len(ENCODED_FEATURE_NAMES),
        "target": TARGET_COL,
        "feature_scope": "German checkup (§25 SGB V) — lipid panel, fasting glucose, age, gender, BMI",
        "removed_vs_v1": "Hepatitis B/C features — one-time screening, not reliably available at every checkup",
        "excluded_from_dataset": "Urine dipstick — NHANES P_UA.xpt not ingested",
        "metrics": metrics,
        "trained_at": datetime.now().isoformat(),
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model    → {model_path}")
    print(f"Saved metadata → {meta_path}")
    return model_path


# ── Main entry point ───────────────────────────────────────────────────────────

def run_training_pipeline():
    print("=" * 60)
    print("  Anemia Checkup Model v2 — Training Pipeline")
    print("=" * 60)

    df = load_data()
    X, y = prepare_features(df)
    X_train, X_test, y_train, y_test = split_data(X, y)

    print("\n[1/2] Training Logistic Regression (v2)...")
    lr = build_lr_pipeline()
    lr.fit(X_train, y_train)
    lr_metrics = evaluate_model(lr, X_test, y_test, threshold=0.5, model_name="LR v2")
    save_model(lr, "anemia_checkup_v2_lr", lr_metrics)

    print("\n[2/2] Training XGBoost (v2)...")
    xgb = build_xgb_pipeline()
    xgb.fit(X_train, y_train)
    xgb_metrics = evaluate_model(xgb, X_test, y_test, threshold=0.5, model_name="XGBoost v2")
    save_model(xgb, "anemia_checkup_v2_xgb", xgb_metrics)

    print("\n" + "=" * 60)
    print("  Training Complete")
    print("=" * 60)
    print(pd.DataFrame([lr_metrics, xgb_metrics]).to_string(index=False))

    return lr, xgb, lr_metrics, xgb_metrics


if __name__ == "__main__":
    run_training_pipeline()
