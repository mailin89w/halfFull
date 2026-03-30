from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_real_nhanes_2003_2006_cohort import RENAME_MAP

DATA_PATH = ROOT / "data" / "processed" / "normalized" / "nhanes_2003_2006_real_cohort_normalized.csv"
DEFAULT_ROADMAP_PATH = Path("/Users/annaesakova/Downloads/HalfFull roadmap - diseases VS features (3).csv")
FALLBACK_ROADMAP_PATH = ROOT / "data" / "processed" / "HalfFull roadmap - diseases VS features.updated.csv"
OUTPUT_DIR = ROOT / "data" / "processed" / "model_outputs_vitamins_2003_2006"
MODELS_DIR = _DIR

TARGETS = {
    "vitamin_b12_deficiency": "Serum vitamin B12 < 200 pg/mL",
    "vitamin_d_deficiency": "25(OH) vitamin D < 50 nmol/L",
    "vitamin_deficiency_any": "Serum vitamin B12 < 200 pg/mL OR 25(OH) vitamin D < 50 nmol/L",
}

LEAKAGE_COLUMNS = {
    "vitamin_b12_serum_pg_ml",
    "vitamin_b12_serum_pmol_l",
    "vitamin_d_25oh_nmol_l",
    "vitamin_b12_deficiency",
    "vitamin_d_deficiency",
    "vitamin_deficiency_any",
}

EXACT_FEATURE_ALIASES = {
    "age_years": "age_years",
    "med_count": "med_count",
    "weight_kg": "weight_kg",
    "bmi": "bmi",
    "gender_female": "gender_female",
    "education_ord": "education_ord",
    "pregnancy_status_bin": "pregnancy_status_bin",
}


def load_roadmap(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, header=1)


def derive_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["gender_female"] = np.where(out["gender"].eq("Female"), 1.0, 0.0)
    out.loc[out["gender"].isna(), "gender_female"] = np.nan

    edu_code = pd.to_numeric(out.get("education_code"), errors="coerce")
    out["education_ord"] = np.where(edu_code.between(1, 5), edu_code - 1, np.nan)

    preg_code = pd.to_numeric(out.get("pregnancy_status_code"), errors="coerce")
    out["pregnancy_status_bin"] = np.where(preg_code.eq(1), 1.0, np.where(preg_code.eq(2), 0.0, np.nan))
    return out


def reverse_code_map() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for nhanes_code, cohort_name in RENAME_MAP.items():
        reverse.setdefault(nhanes_code, cohort_name)
    return reverse


def match_roadmap_features(roadmap: pd.DataFrame, available_columns: set[str]) -> pd.DataFrame:
    reverse_map = reverse_code_map()
    rows: list[dict[str, Any]] = []

    for row in roadmap.to_dict(orient="records"):
        canonical = row.get("canonical_feature")
        mapped = row.get("mapped_dataset_column")
        code = row.get("nhanes_code_match")
        chosen = None
        strategy = None

        if mapped in EXACT_FEATURE_ALIASES and EXACT_FEATURE_ALIASES[mapped] in available_columns:
            chosen = EXACT_FEATURE_ALIASES[mapped]
            strategy = "derived_or_exact"
        elif isinstance(mapped, str) and mapped in available_columns:
            chosen = mapped
            strategy = "exact"
        elif isinstance(code, str) and code in reverse_map and reverse_map[code] in available_columns:
            chosen = reverse_map[code]
            strategy = "nhanes_code"

        included = chosen is not None and chosen not in LEAKAGE_COLUMNS
        rows.append(
            {
                "canonical_feature": canonical,
                "mapped_dataset_column": mapped,
                "nhanes_code_match": code,
                "chosen_cohort_column": chosen,
                "match_strategy": strategy,
                "included_in_model": included,
            }
        )

    return pd.DataFrame(rows)


def make_lr_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    solver="lbfgs",
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )


def make_rf_cal_pipeline() -> Pipeline:
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    cal = CalibratedClassifierCV(rf, method="isotonic", cv=3)
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("clf", cal)])


def threshold_table(y_true: np.ndarray, proba: np.ndarray, target: str, model_name: str) -> pd.DataFrame:
    rows = []
    for threshold in np.arange(0.10, 0.91, 0.05):
        pred = (proba >= threshold).astype(int)
        n_flags = int(pred.sum())
        tp = int(((pred == 1) & (y_true == 1)).sum())
        fp = int(((pred == 1) & (y_true == 0)).sum())
        fn = int(((pred == 0) & (y_true == 1)).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        rows.append(
            {
                "target": target,
                "model_name": model_name,
                "threshold": round(float(threshold), 2),
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "flags_n": n_flags,
                "flags_pct": n_flags / len(y_true),
            }
        )
    return pd.DataFrame(rows)


def choose_cv(y: pd.Series) -> StratifiedKFold:
    class_counts = y.astype(int).value_counts()
    min_class = int(class_counts.min())
    n_splits = max(3, min(5, min_class))
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)


def train_one(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    target_definition: str,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame]]:
    target_df = df[df[target].notna()].copy()
    X = target_df[features]
    y = target_df[target].astype(int)
    cv = choose_cv(y)

    results: list[dict[str, Any]] = []
    threshold_frames: list[pd.DataFrame] = []

    for model_key, builder in (("lr", make_lr_pipeline), ("rf_cal", make_rf_cal_pipeline)):
        pipe = builder()
        oof_proba = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
        auc = roc_auc_score(y, oof_proba)
        ap = average_precision_score(y, oof_proba)
        threshold_frames.append(threshold_table(y.to_numpy(), oof_proba, target, model_key))

        pipe.fit(X, y)
        model_stub = f"{target}_2003_2006_{model_key}_roadmap"
        model_path = MODELS_DIR / f"{model_stub}.joblib"
        meta_path = MODELS_DIR / f"{model_stub}_metadata.json"
        joblib.dump(pipe, model_path)

        metadata = {
            "model": model_path.name,
            "version": "v1",
            "condition": target,
            "target_column": target,
            "target_definition": target_definition,
            "algorithm": "LogisticRegression L2 C=1.0" if model_key == "lr" else "RandomForest(n=300, max_depth=6, min_leaf=10) + CalibratedClassifierCV(isotonic, cv=3)",
            "data_source": DATA_PATH.name,
            "n_train": int(len(y)),
            "prevalence": float(y.mean()),
            "features": features,
            "n_features": len(features),
            "cv_folds": cv.n_splits,
            "cv_auc_mean": round(float(auc), 4),
            "cv_avg_precision": round(float(ap), 4),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "feature_policy": "Limited to roadmap-mapped features that could be matched into the 2003-2006 cohort.",
            "leakage_removed": sorted(LEAKAGE_COLUMNS),
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        results.append(
            {
                "target": target,
                "model_name": model_key,
                "n_rows": int(len(y)),
                "prevalence": float(y.mean()),
                "n_features": len(features),
                "cv_folds": cv.n_splits,
                "auc_oof": float(auc),
                "auprc_oof": float(ap),
                "model_path": str(model_path),
                "metadata_path": str(meta_path),
            }
        )

    return results, threshold_frames


def resolve_roadmap_path(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    if DEFAULT_ROADMAP_PATH.exists():
        return DEFAULT_ROADMAP_PATH
    return FALLBACK_ROADMAP_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Train vitamin deficiency models on NHANES 2003-2006 using the roadmap-constrained feature subset.")
    parser.add_argument("--roadmap", type=str, default=None, help="Optional roadmap CSV path.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = derive_columns(pd.read_csv(DATA_PATH, low_memory=False))
    roadmap_path = resolve_roadmap_path(args.roadmap)
    roadmap = load_roadmap(roadmap_path)
    mapping = match_roadmap_features(roadmap, set(df.columns))
    mapping_path = OUTPUT_DIR / "roadmap_feature_mapping_2003_2006.csv"

    candidate_features = sorted(mapping.loc[mapping["included_in_model"], "chosen_cohort_column"].dropna().unique().tolist())
    features = [col for col in candidate_features if df[col].notna().any()]
    mapping["feature_non_null"] = mapping["chosen_cohort_column"].map(
        lambda col: int(df[col].notna().sum()) if isinstance(col, str) and col in df.columns else 0
    )
    mapping["included_in_model"] = mapping["included_in_model"] & mapping["feature_non_null"].gt(0)
    mapping.to_csv(mapping_path, index=False)
    if not features:
        raise ValueError("No roadmap features could be matched into the normalized 2003-2006 cohort.")

    comparison_rows: list[dict[str, Any]] = []
    threshold_frames: list[pd.DataFrame] = []

    for target, definition in TARGETS.items():
        target_results, target_thresholds = train_one(df, features, target, definition)
        comparison_rows.extend(target_results)
        threshold_frames.extend(target_thresholds)

    comparison_df = pd.DataFrame(comparison_rows).sort_values(["target", "auc_oof"], ascending=[True, False])
    threshold_df = pd.concat(threshold_frames, ignore_index=True)

    comparison_path = OUTPUT_DIR / "vitamin_model_comparison_2003_2006.csv"
    threshold_path = OUTPUT_DIR / "vitamin_threshold_sweep_2003_2006.csv"
    feature_list_path = OUTPUT_DIR / "vitamin_model_features_2003_2006.json"

    comparison_df.to_csv(comparison_path, index=False)
    threshold_df.to_csv(threshold_path, index=False)
    feature_list_path.write_text(json.dumps({"features": features, "n_features": len(features)}, indent=2), encoding="utf-8")

    print(f"Matched roadmap features: {len(features)}")
    print(f"Saved feature mapping to {mapping_path}")
    print(f"Saved model comparison to {comparison_path}")
    print(f"Saved threshold sweep to {threshold_path}")


if __name__ == "__main__":
    main()
