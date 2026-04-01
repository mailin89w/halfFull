from __future__ import annotations

import csv
import json
import math
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROADMAP_CSV = Path("/Users/annaesakova/Downloads/HalfFull roadmap - diseases VS features (3).csv")
DEFAULT_FINAL_FILE = ROOT / "data/processed/nhanes_merged_adults_final.csv"
DEFAULT_DISEASES_FILE = ROOT / "data/processed/nhanes_merged_adults_diseases.csv"
DEFAULT_REF_RANGES_FILE = ROOT / "data/processed/normalized/nhanes_reference_ranges_used.csv"
DEFAULT_ARTIFACT = ROOT / "data/processed/cluster/artifacts/roadmap_knn_inference_pkg.pkl"

RAW_HEADER_ROW_INDEX = 1
MIN_OVERLAP_FEATURES = 8
KNN_K = 50

EDUCATION_ORDINAL = {
    "Less than 9th grade": 0.0,
    "9-11th grade": 1.0,
    "High school / GED": 2.0,
    "Some college / AA": 3.0,
    "College graduate or above": 4.0,
}
PREGNANCY_BINARY = {
    "Pregnant": 1.0,
    "Not pregnant": 0.0,
}
DISEASE_LABEL_COLS = [
    "anemia",
    "thyroid",
    "sleep_disorder",
    "kidney",
    "hepatitis_bc",
    "liver",
    "diabetes",
    "heart_failure",
    "coronary_heart",
    "high_blood_pressure",
    "high_cholesterol",
    "overweight",
    "menopause",
]
TARGET_CONDITION_SPECS = {
    "hepatitis": {"source": "final_label", "column": "hepatitis_bc"},
    "perimenopause": {"source": "final_label", "column": "perimenopause"},
    "anemia": {"source": "final_label", "column": "anemia"},
    "iron_deficiency": {"source": "final_label", "column": "iron_deficiency"},
    "kidney_disease": {"source": "final_label", "column": "kidney"},
    "hypothyroidism": {"source": "final_label", "column": "thyroid"},
    "liver": {"source": "final_label", "column": "liver"},
    "sleep_disorder": {"source": "final_label", "column": "sleep_disorder"},
    "hidden_inflammation": {"source": "final_label", "column": "hidden_inflammation"},
    "electrolyte_imbalance": {"source": "final_label", "column": "electrolyte_imbalance"},
    "prediabetes": {"source": "final_label", "column": "prediabetes"},
    "vitamin_d_deficiency": {"source": "unsupported"},
}
LAB_DISPLAY_TO_DATASET_COL = {
    "Ferritin": "ferritin_ng_ml",
    "Creatinine": "serum_creatinine_mg_dl",
    "Albumin": "serum_albumin_g_dl",
    "Serum Iron": "serum_iron_ug_dl",
    "TIBC (iron binding capacity)": "tibc_ug_dl",
    "Transferrin Saturation": "transferrin_saturation_pct",
    "Total Bilirubin": "total_bilirubin_mg_dl",
    "Total Cholesterol": "total_cholesterol_mg_dl",
    "Triglycerides": "triglycerides_mg_dl",
    "HDL Cholesterol": "hdl_cholesterol_mg_dl",
    "Fasting Glucose": "fasting_glucose_mg_dl",
    "ALT (liver enzyme)": "alt_u_l",
    "AST (liver enzyme)": "ast_u_l",
    "GGT (liver enzyme)": "ggt_u_l",
    "ALP (alkaline phosphatase)": "alp_u_l",
    "BUN (blood urea nitrogen)": "bun_mg_dl",
    "Hemoglobin": "LBXHGB_hemoglobin_g_dl",
    "Hematocrit": "LBXHCT_hematocrit",
    "RBC Count": "LBXRBCSI_red_blood_cell_count_million_cells_ul",
    "MCV (mean cell volume)": "LBXMCVSI_mean_cell_volume_fl",
    "MCH (mean cell hemoglobin)": "LBXMCHSI_mean_cell_hemoglobin_pg",
    "Platelet Count": "LBXPLTSI_platelet_count_1000_cells_ul",
    "WBC Count": "LBXWBCSI_white_blood_cell_count_1000_cells_ul",
    "HbA1c (glycated hemoglobin)": "LBXGH_glycohemoglobin",
    "hsCRP (high-sensitivity CRP)": "LBXHSCRP_hs_c_reactive_protein_mg_l",
    "LDL Cholesterol": "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
    "Bicarbonate": "LBXSC3SI_bicarbonate_mmol_l",
    "Calcium": "LBXSCA_total_calcium_mg_dl",
    "Potassium": "LBXSKSI_potassium_mmol_l",
    "Sodium": "LBXSNASI_sodium_mmol_l",
    "Total Protein": "LBXSTP_total_protein_g_dl",
}


@dataclass(frozen=True)
class RoadmapFeature:
    canonical_feature: str
    mapped_dataset_column: str
    input_bucket: str
    ask_logic: str
    anchor_tag: str
    cluster_role: str
    display_label: str


def load_roadmap_features(csv_path: Path = DEFAULT_ROADMAP_CSV) -> list[RoadmapFeature]:
    rows: list[RoadmapFeature] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        raw_rows = list(reader)
    header = raw_rows[RAW_HEADER_ROW_INDEX]
    for raw in raw_rows[RAW_HEADER_ROW_INDEX + 1:]:
        if not any(cell.strip() for cell in raw):
            continue
        padded = raw + [""] * (len(header) - len(raw))
        row = dict(zip(header, padded))
        if row.get("anchor_v1", "").strip() != "anchor_candidate":
            continue
        rows.append(
            RoadmapFeature(
                canonical_feature=row.get("canonical_feature", "").strip(),
                mapped_dataset_column=row.get("mapped_dataset_column", "").strip(),
                input_bucket=row.get("input_bucket_v1", "").strip(),
                ask_logic=row.get("ask_logic_v1", "").strip(),
                anchor_tag=row.get("anchor_v1", "").strip(),
                cluster_role=row.get("cluster_role_v1", "").strip(),
                display_label=row.get("display_label", "").strip(),
            )
        )
    return rows


def _to_float(value: Any) -> float:
    if value in (None, "", "nan"):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _derive_series(df: pd.DataFrame, feature_name: str) -> pd.Series:
    if feature_name == "gender_female":
        if "gender" in df.columns:
            return df["gender"].map({"Female": 1.0, "Male": 0.0}).astype(float)
        return pd.Series(np.nan, index=df.index)
    if feature_name == "education_ord":
        if "education" in df.columns:
            return df["education"].map(EDUCATION_ORDINAL).astype(float)
        return pd.Series(np.nan, index=df.index)
    if feature_name == "pregnancy_status_bin":
        if "pregnancy_status" in df.columns:
            return df["pregnancy_status"].map(PREGNANCY_BINARY).astype(float)
        return pd.Series(np.nan, index=df.index)
    raise KeyError(feature_name)


def build_feature_frame(
    final_df: pd.DataFrame,
    features: list[RoadmapFeature],
) -> pd.DataFrame:
    data: dict[str, pd.Series] = {}
    for feature in features:
        column = feature.mapped_dataset_column
        if column in final_df.columns:
            data[column] = pd.to_numeric(final_df[column], errors="coerce")
        else:
            data[column] = _derive_series(final_df, column)
    return pd.DataFrame(data, index=final_df.index)


def feature_stats(feature_frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    means = feature_frame.mean(skipna=True)
    stds = feature_frame.std(skipna=True).replace(0, 1.0).fillna(1.0)
    return means, stds


def normalize_feature_frame(feature_frame: pd.DataFrame, means: pd.Series, stds: pd.Series) -> pd.DataFrame:
    return (feature_frame - means) / stds


def build_query_vector(
    answers: dict[str, Any],
    feature_names: list[str],
    means: dict[str, float],
    stds: dict[str, float],
) -> np.ndarray:
    gender_value = answers.get("gender")
    if gender_value is None and "gender_code" in answers:
        gender_value = "Female" if _to_float(answers.get("gender_code")) == 2.0 else "Male"

    education_value = answers.get("education")
    pregnancy_value = answers.get("pregnancy_status")

    values: list[float] = []
    for feature in feature_names:
        if feature == "gender_female":
            raw = 1.0 if str(gender_value) == "Female" else 0.0 if str(gender_value) == "Male" else math.nan
        elif feature == "education_ord":
            raw = EDUCATION_ORDINAL.get(str(education_value), math.nan)
        elif feature == "pregnancy_status_bin":
            raw = PREGNANCY_BINARY.get(str(pregnancy_value), math.nan)
        else:
            raw = _to_float(answers.get(feature))
        if math.isnan(raw):
            values.append(math.nan)
            continue
        mean = float(means.get(feature, 0.0))
        std = float(stds.get(feature, 1.0)) or 1.0
        values.append((raw - mean) / std)
    return np.asarray(values, dtype=float)


def masked_cosine_distances(
    query_vec: np.ndarray,
    index_matrix: np.ndarray,
    *,
    min_overlap_features: int = MIN_OVERLAP_FEATURES,
) -> tuple[np.ndarray, np.ndarray]:
    query_present = ~np.isnan(query_vec)
    common = (~np.isnan(index_matrix)) & query_present[None, :]
    overlap_counts = common.sum(axis=1)

    query_filled = np.where(query_present, query_vec, 0.0)
    index_filled = np.where(np.isnan(index_matrix), 0.0, index_matrix)
    masked_index = np.where(common, index_filled, 0.0)
    masked_query = np.where(common, query_filled[None, :], 0.0)

    numerator = np.sum(masked_index * masked_query, axis=1)
    query_norm = np.sqrt(np.sum(masked_query * masked_query, axis=1))
    index_norm = np.sqrt(np.sum(masked_index * masked_index, axis=1))
    denom = query_norm * index_norm

    cosine_similarity = np.zeros(index_matrix.shape[0], dtype=float)
    valid = (denom > 0) & (overlap_counts >= min_overlap_features)
    cosine_similarity[valid] = numerator[valid] / denom[valid]

    distances = np.ones(index_matrix.shape[0], dtype=float)
    distances[valid] = 1.0 - cosine_similarity[valid]
    distances[~valid] = np.inf
    return distances, overlap_counts


def build_artifact(
    roadmap_csv: Path = DEFAULT_ROADMAP_CSV,
    final_file: Path = DEFAULT_FINAL_FILE,
    diseases_file: Path = DEFAULT_DISEASES_FILE,
    ref_ranges_file: Path = DEFAULT_REF_RANGES_FILE,
    artifact_path: Path = DEFAULT_ARTIFACT,
) -> dict[str, Any]:
    features = load_roadmap_features(roadmap_csv)
    final_df = pd.read_csv(final_file, low_memory=False)
    final_df = final_df.set_index("SEQN") if "SEQN" in final_df.columns else final_df
    diseases_df = pd.read_csv(diseases_file, low_memory=False)
    diseases_df = diseases_df.set_index("SEQN") if "SEQN" in diseases_df.columns else diseases_df
    ref_ranges = pd.read_csv(ref_ranges_file)

    feature_frame = build_feature_frame(final_df, features)
    shared_index = feature_frame.index.intersection(diseases_df.index)
    feature_frame = feature_frame.loc[shared_index]
    final_df = final_df.loc[shared_index]
    diseases_df = diseases_df.loc[shared_index]

    means, stds = feature_stats(feature_frame)
    normalized = normalize_feature_frame(feature_frame, means, stds)

    disease_cols = [col for col in DISEASE_LABEL_COLS if col in diseases_df.columns]
    disease_matrix = diseases_df[disease_cols].fillna(0).astype(float).to_numpy()

    target_condition_vectors: dict[str, np.ndarray] = {}
    target_condition_sources: dict[str, str] = {}
    for target_condition, spec in TARGET_CONDITION_SPECS.items():
        source = str(spec["source"])
        target_condition_sources[target_condition] = source
        if source == "final_label":
            col = str(spec["column"])
            if col in final_df.columns:
                target_condition_vectors[target_condition] = pd.to_numeric(final_df[col], errors="coerce").fillna(0).astype(float).to_numpy()
        elif source == "direct":
            col = str(spec["column"])
            if col in diseases_df.columns:
                target_condition_vectors[target_condition] = diseases_df[col].fillna(0).astype(float).to_numpy()
        elif source == "questionnaire_binary":
            col = str(spec["column"])
            source_df = diseases_df if col in diseases_df.columns else final_df
            if col in source_df.columns:
                vals = pd.to_numeric(source_df[col], errors="coerce")
                target_condition_vectors[target_condition] = vals.eq(1).astype(float).to_numpy()

    lab_cols = [col for col in LAB_DISPLAY_TO_DATASET_COL.values() if col in final_df.columns]
    extra_cols = [col for col in ["gender", "age_years"] if col in final_df.columns]
    lab_df = final_df[lab_cols + extra_cols].copy()

    ref_lookup: dict[str, list[dict[str, Any]]] = {}
    for _, row in ref_ranges.iterrows():
        ref_lookup.setdefault(row["dataset_column"], []).append({
            "sex": row["sex"],
            "age_min": row["age_min"],
            "age_max": row["age_max"],
            "lower": row["lower"],
            "upper": row["upper"],
        })

    artifact = {
        "index_seqns": normalized.index.to_numpy(),
        "feature_names": list(normalized.columns),
        "index_matrix": normalized.to_numpy(dtype=float),
        "feature_means": means.to_dict(),
        "feature_stds": stds.to_dict(),
        "feature_metadata": [feature.__dict__ for feature in features],
        "disease_cols": disease_cols,
        "disease_matrix": disease_matrix,
        "target_condition_vectors": target_condition_vectors,
        "target_condition_sources": target_condition_sources,
        "lab_df": lab_df,
        "ref_lookup": ref_lookup,
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("wb") as f:
        pickle.dump(artifact, f)
    return artifact


def load_artifact(artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    with artifact_path.open("rb") as f:
        return pickle.load(f)


def nearest_neighbours(
    answers: dict[str, Any],
    artifact: dict[str, Any],
    *,
    k: int = KNN_K,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    query_vec = build_query_vector(
        answers,
        artifact["feature_names"],
        artifact["feature_means"],
        artifact["feature_stds"],
    )
    distances, overlap_counts = masked_cosine_distances(query_vec, artifact["index_matrix"])
    top_idx = np.argsort(distances)[:k]
    return top_idx, distances[top_idx], overlap_counts[top_idx]


def disease_scores_from_neighbours(
    neighbour_idx: np.ndarray,
    distances: np.ndarray,
    artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(neighbour_idx) == 0:
        return []
    weights = 1.0 / np.maximum(distances, 1e-6)
    weights = weights / weights.sum() if weights.sum() > 0 else np.full(len(distances), 1.0 / len(distances))
    rows = []
    for condition, source in artifact.get("target_condition_sources", {}).items():
        vector = artifact.get("target_condition_vectors", {}).get(condition)
        if vector is None:
            continue
        subset = np.asarray(vector)[neighbour_idx]
        weighted = float((subset * weights).sum())
        raw = float(subset.mean())
        rows.append({
            "condition": condition,
            "weighted_neighbor_fraction": round(weighted, 4),
            "neighbor_fraction": round(raw, 4),
            "neighbor_count_positive": int(subset.sum()),
            "source": source,
        })
    rows.sort(key=lambda item: item["weighted_neighbor_fraction"], reverse=True)
    return rows


def get_reference_range(lookup: dict[str, list[dict[str, Any]]], col: str, sex: str, age: float) -> tuple[float, float] | None:
    entries = lookup.get(col)
    if not entries:
        return None
    for entry in entries:
        sex_match = pd.isna(entry["sex"]) or entry["sex"] == sex
        age_min_ok = pd.isna(entry["age_min"]) or entry["age_min"] <= age
        age_max_ok = pd.isna(entry["age_max"]) or age <= entry["age_max"]
        if sex_match and age_min_ok and age_max_ok:
            return (entry["lower"], entry["upper"])
    return None


def abnormal_direction(value: float, lower: float, upper: float) -> str | None:
    if pd.isna(value):
        return None
    if value > upper:
        return "high"
    if value < lower:
        return "low"
    return None


def recommend_missing_labs(
    answers: dict[str, Any],
    neighbour_idx: np.ndarray,
    artifact: dict[str, Any],
    *,
    min_fraction: float = 0.20,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lab_df = artifact["lab_df"].iloc[neighbour_idx]
    sex = str(answers.get("gender") or "Female")
    age = _to_float(answers.get("age_years") or 40)
    all_signals: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    for display_name, col in LAB_DISPLAY_TO_DATASET_COL.items():
        if col not in lab_df.columns:
            continue
        values = lab_df[col].dropna()
        if values.empty:
            continue
        high = 0
        low = 0
        checked = 0
        for _, row in lab_df.iterrows():
            value = row.get(col)
            if pd.isna(value):
                continue
            ref = get_reference_range(
                artifact["ref_lookup"],
                col,
                str(row.get("gender", sex)),
                float(row.get("age_years", age)),
            )
            if ref is None:
                continue
            status = abnormal_direction(float(value), ref[0], ref[1])
            checked += 1
            if status == "high":
                high += 1
            elif status == "low":
                low += 1
        if checked == 0:
            continue
        abnormal = max(high, low)
        direction = "high" if high >= low else "low"
        fraction = abnormal / checked
        if fraction < min_fraction:
            continue
        item = {
            "lab": display_name,
            "dataset_column": col,
            "direction": direction,
            "neighbor_fraction": round(fraction, 4),
            "neighbor_count_abnormal": int(abnormal),
            "neighbor_count_checked": int(checked),
        }
        all_signals.append(item)
        if answers.get(col) in (None, "", []):
            recommendations.append(item)
    all_signals.sort(key=lambda item: item["neighbor_fraction"], reverse=True)
    recommendations.sort(key=lambda item: item["neighbor_fraction"], reverse=True)
    return all_signals, recommendations
