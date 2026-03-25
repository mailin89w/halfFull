"""
cluster_knn_inference.py

KNN-based neighbour inference for the HalfFull clustering layer.

For a given user's anchor features, finds their K nearest NHANES neighbours
and surfaces labs that are consistently out of clinical reference range
across those neighbours.

No cluster limits — every user gets a fully personalised neighbourhood.

Outputs:
  - knn_lab_signals.json    : per-SEQN neighbour lab abnormality summary (validation run)
  - knn_inference_ready.pkl : prebuilt KNN index + reference range lookup for inference

Usage:
  python scripts/cluster_knn_inference.py           # builds index + runs validation sample
  python scripts/cluster_knn_inference.py --seqn 12345   # run single user by SEQN
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics.pairwise import cosine_distances

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT            = Path(".")
FINAL_FILE      = ROOT / "data/processed/nhanes_merged_adults_final.csv"
NORMALIZED_FILE = ROOT / "data/processed/nhanes_merged_adults_final_normalized.csv"
DISEASES_FILE   = ROOT / "data/processed/nhanes_merged_adults_diseases.csv"
REF_RANGES_FILE = ROOT / "data/processed/normalized/nhanes_reference_ranges_used.csv"
ARTIFACT_DIR    = ROOT / "data/processed/cluster/artifacts"
OUT_DIR         = ROOT / "data/processed/cluster"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KNN_K            = 50      # number of nearest neighbours
# Default: lab must be abnormal in this fraction of neighbours to surface.
# K=50 at 15% = 7-8 neighbours must agree — validated against known-condition users.
MIN_NEIGHBOUR_FRACTION = 0.15

# Lower absolute threshold for liver enzymes (more organ-specific signal per instance)
LAB_SPECIFIC_THRESHOLDS: dict[str, float] = {
    "alt_u_l":               0.10,
    "ast_u_l":               0.10,
    "ggt_u_l":               0.10,
    "alp_u_l":               0.10,
    "total_bilirubin_mg_dl": 0.10,
}

# Lift gate: neighbourhood rate must be >= MIN_LIFT × population baseline rate.
# Prevents common-population findings (high LDL 58%, high glucose 53%, high SBP 45%)
# from surfacing as if they were meaningful neighbourhood signals.
MIN_LIFT = 1.5

# Population baseline rates file (built by cluster_knn_inference.py first pass)
POP_RATES_FILE = ROOT / "data/processed/cluster/artifacts/lab_population_rates.json"

# Ferritin context rules: when ferritin HIGH surfaces alongside other signals,
# interpret it as chronic disease marker rather than iron overload.
# Key = set of co-occurring lab directions that shift the interpretation.
FERRITIN_CHRONIC_DISEASE_CONDITIONS = {
    # If any of these labs are also abnormal in the same neighbourhood,
    # ferritin HIGH is a chronic disease / inflammation marker, not iron overload.
    "serum_creatinine_mg_dl",   # kidney
    "LBXHGB_hemoglobin_g_dl",   # anaemia of chronic disease
    "LBXHCT_hematocrit",
    "alt_u_l",                  # liver
    "ast_u_l",
    "ggt_u_l",
    "LBXGH_glycohemoglobin",    # diabetes
    "fasting_glucose_mg_dl",
}
VALIDATION_SAMPLE_N    = 200   # how many random users to run in the validation pass

CONDITION_COLS = [
    "anemia", "thyroid", "sleep_disorder", "kidney",
    "hepatitis_bc", "liver", "diabetes",
]

SEX_MAP = {1: "Male", 2: "Female", "Male": "Male", "Female": "Female"}

# When the same lab appears under multiple column names, keep only the canonical one.
# Key = column to DROP, Value = canonical column to KEEP instead.
DUPLICATE_LAB_COLS = {
    "LBXFER_ferritin_ng_ml":                    "ferritin_ng_ml",
    "LBXSCR_creatinine_refrigerated_serum_mg_dl": "serum_creatinine_mg_dl",
    "LBXSIR_iron_refrigerated_serum_ug_dl":     "serum_iron_ug_dl",
    "LBXIRN_iron_frozen_serum_ug_dl":           "serum_iron_ug_dl",
    "LBXSAL_albumin_refrigerated_serum_g_dl":   "serum_albumin_g_dl",
    "LBXSTB_total_bilirubin_mg_dl":             "total_bilirubin_mg_dl",
    "LBXTC_total_cholesterol_mg_dl":            "total_cholesterol_mg_dl",
    "LBDTIB_total_iron_binding_capacity_tibc_ug_dl": "tibc_ug_dl",
    "LBXTR_triglyceride_mg_dl":                 "triglycerides_mg_dl",
    "LBDPCT_transferrin_saturation":            "transferrin_saturation_pct",
    "LBXSAPSI_alkaline_phosphatase_alp_iu_l":   "alp_u_l",
    "LBXSASSI_aspartate_aminotransferase_ast_u_l": "ast_u_l",
    "LBXSATSI_alanine_aminotransferase_alt_u_l": "alt_u_l",
    "LBXSGTSI_gamma_glutamyl_transferase_ggt_iu_l": "ggt_u_l",
    "LBXGLU_fasting_glucose_mg_dl":             "fasting_glucose_mg_dl",
    "LBDHDD_direct_hdl_cholesterol_mg_dl":      "hdl_cholesterol_mg_dl",
    # Repeated BP readings — keep only first measurement
    "dbp_2": "dbp_1", "dbp_3": "dbp_1",
    "sbp_2": "sbp_1", "sbp_3": "sbp_1",
}

# Columns that have reference ranges but are not actually labs to surface
NON_LAB_REF_COLS = {"bmi", "waist_cm"}


# ---------------------------------------------------------------------------
# Reference range helpers
# ---------------------------------------------------------------------------

def build_reference_lookup(ref_path: Path) -> dict:
    """
    Build a nested lookup:
      {dataset_column: [(sex, age_min, age_max, lower, upper), ...]}
    Used at inference time to check if a lab value is out of range.
    """
    ref = pd.read_csv(ref_path)
    lookup: dict[str, list] = {}
    for _, row in ref.iterrows():
        col = row["dataset_column"]
        if col not in lookup:
            lookup[col] = []
        lookup[col].append({
            "sex":     row["sex"],
            "age_min": row["age_min"],
            "age_max": row["age_max"],
            "lower":   row["lower"],
            "upper":   row["upper"],
        })
    return lookup


def get_reference_range(lookup: dict, col: str, sex: str, age: float) -> tuple[float, float] | None:
    """Return (lower, upper) for a given column/sex/age, or None if no range available.
    Handles NaN age bounds (treated as open) and NaN sex (treated as any sex)."""
    entries = lookup.get(col)
    if not entries:
        return None
    sex_str = SEX_MAP.get(sex, str(sex))
    for e in entries:
        sex_match = pd.isna(e["sex"]) or e["sex"] == sex_str
        age_min_ok = pd.isna(e["age_min"]) or e["age_min"] <= age
        age_max_ok = pd.isna(e["age_max"]) or age <= e["age_max"]
        if sex_match and age_min_ok and age_max_ok:
            return (e["lower"], e["upper"])
    return None


def check_lab_abnormal(value: float, lower: float, upper: float) -> str | None:
    """Returns 'high', 'low', or None."""
    if pd.isna(value):
        return None
    if value > upper:
        return "high"
    if value < lower:
        return "low"
    return None


# ---------------------------------------------------------------------------
# KNN core
# ---------------------------------------------------------------------------

def build_knn_index(
    norm_df: pd.DataFrame,
    anchor_cols: list[str],
    imputer: SimpleImputer,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Build the normalised anchor feature matrix used for distance computation.
    Returns (X_norm, seqns, available_cols).
    """
    available = [c for c in anchor_cols if c in norm_df.columns]
    X_raw = norm_df[available].values.astype(float)
    X_norm = imputer.transform(X_raw)
    seqns = norm_df.index.to_numpy()
    return X_norm, seqns, available


def find_neighbours(
    user_vec: np.ndarray,      # shape (1, n_features) — already imputed & normalised
    X_index: np.ndarray,       # shape (N, n_features)
    index_seqns: np.ndarray,   # shape (N,)
    k: int = KNN_K,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (neighbour_seqns, distances) for the k nearest neighbours.
    Uses cosine distance to match training metric.
    """
    dists = cosine_distances(user_vec, X_index)[0]   # shape (N,)
    top_k_idx = np.argsort(dists)[:k]
    return index_seqns[top_k_idx], dists[top_k_idx]


def get_neighbour_lab_signals(
    neighbour_seqns: np.ndarray,
    neighbour_dists: np.ndarray,
    final_df: pd.DataFrame,
    ref_lookup: dict,
    sex: str,
    age: float,
    pop_rates: dict,
    min_fraction: float = MIN_NEIGHBOUR_FRACTION,
) -> list[dict]:
    """
    For each lab with a reference range, check how many neighbours have it
    out of range. Surface labs where the fraction exceeds min_fraction.

    Returns a list of dicts sorted by neighbour_fraction descending:
      {lab_col, direction, neighbour_fraction, n_abnormal, n_checked,
       median_value, lower, upper, display_name}
    """
    # Deduplicate: remove alias columns and non-lab reference entries
    lab_cols = [
        c for c in ref_lookup
        if c in final_df.columns
        and c not in DUPLICATE_LAB_COLS
        and c not in NON_LAB_REF_COLS
    ]
    extra_cols = [c for c in ["gender", "age_years"] if c in final_df.columns]
    neighbours = final_df.loc[final_df.index.isin(neighbour_seqns), lab_cols + extra_cols]

    results = []
    for col in lab_cols:
        col_vals = neighbours[col].dropna()
        if len(col_vals) == 0:
            continue

        abnormal_high = 0
        abnormal_low  = 0
        n_checked     = 0

        for seqn, row in neighbours.iterrows():
            val = row.get(col)
            if pd.isna(val):
                continue
            # Use the neighbour's own sex/age for their reference range
            nb_sex = row.get("gender", sex)
            nb_age = row.get("age_years", age)
            ref = get_reference_range(ref_lookup, col, nb_sex, nb_age)
            if ref is None:
                # Fallback: use the querying user's sex/age
                ref = get_reference_range(ref_lookup, col, sex, age)
            if ref is None:
                continue
            status = check_lab_abnormal(val, ref[0], ref[1])
            n_checked += 1
            if status == "high":
                abnormal_high += 1
            elif status == "low":
                abnormal_low += 1

        if n_checked == 0:
            continue

        # Determine dominant direction
        if abnormal_high >= abnormal_low:
            n_abnormal = abnormal_high
            direction  = "high"
        else:
            n_abnormal = abnormal_low
            direction  = "low"

        fraction = n_abnormal / n_checked
        effective_threshold = LAB_SPECIFIC_THRESHOLDS.get(col, min_fraction)
        if fraction < effective_threshold:
            continue

        # Lift gate: only surface if neighbourhood rate meaningfully exceeds population baseline
        pop_direction_rate = pop_rates.get(col, {}).get(direction, 0.0) / 100.0
        if pop_direction_rate > 0:
            lift = fraction / pop_direction_rate
            if lift < MIN_LIFT:
                continue
        else:
            lift = None   # no baseline available — allow through

        ref_user = get_reference_range(ref_lookup, col, sex, age)
        results.append({
            "lab_col":            col,
            "direction":          direction,
            "neighbour_fraction": round(fraction, 3),
            "n_abnormal":         int(n_abnormal),
            "n_checked":          int(n_checked),
            "median_value":       round(float(col_vals.median()), 3),
            "lower":              ref_user[0] if ref_user else None,
            "upper":              ref_user[1] if ref_user else None,
            "population_rate":    round(pop_direction_rate, 3),
            "lift":               round(lift, 2) if lift is not None else None,
            "context":            None,   # filled in below for ferritin
        })

    results.sort(key=lambda x: x["neighbour_fraction"], reverse=True)

    # Ferritin context: distinguish chronic disease marker from iron overload
    surfaced_cols = {r["lab_col"] for r in results}
    for r in results:
        if r["lab_col"] == "ferritin_ng_ml" and r["direction"] == "high":
            co_occurring = surfaced_cols & FERRITIN_CHRONIC_DISEASE_CONDITIONS
            if co_occurring:
                r["context"] = (
                    "Elevated ferritin here likely reflects chronic inflammation or "
                    "an ongoing condition (e.g. kidney, liver, or metabolic disease) "
                    "rather than iron overload — note the co-occurring signals: "
                    + ", ".join(sorted(co_occurring)) + "."
                )
            else:
                r["context"] = (
                    "Elevated ferritin without clear co-occurring disease signals — "
                    "could reflect iron overload, recent illness, or subclinical inflammation. "
                    "Worth checking alongside serum iron and transferrin saturation."
                )

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(target_seqn: int | None = None) -> None:
    print("=== HalfFull KNN Neighbour Inference ===\n")

    # ------------------------------------------------------------------
    # 1. Load artifacts from cluster_train.py
    # ------------------------------------------------------------------
    anchor_cols = json.loads((ARTIFACT_DIR / "anchor_features.json").read_text())
    imputer     = joblib.load(ARTIFACT_DIR / "anchor_imputer.joblib")

    # ------------------------------------------------------------------
    # 2. Load data
    # ------------------------------------------------------------------
    print("Loading normalised anchor data...")
    norm_df = pd.read_csv(NORMALIZED_FILE, low_memory=False)
    norm_df = norm_df.set_index("SEQN") if "SEQN" in norm_df.columns else norm_df

    print("Loading full NHANES data (for lab values)...")
    final_df = pd.read_csv(FINAL_FILE, low_memory=False)
    final_df = final_df.set_index("SEQN") if "SEQN" in final_df.columns else final_df

    print("Loading condition labels...")
    labels_df = pd.read_csv(DISEASES_FILE, usecols=["SEQN"] + CONDITION_COLS,
                             low_memory=False).set_index("SEQN")

    print("Loading reference ranges...")
    ref_lookup = build_reference_lookup(REF_RANGES_FILE)
    print(f"  Reference ranges loaded for {len(ref_lookup)} lab columns")

    print("Loading population baseline rates...")
    if POP_RATES_FILE.exists():
        with open(POP_RATES_FILE) as f:
            pop_rates = json.load(f)
        print(f"  Loaded baseline rates for {len(pop_rates)} labs")
    else:
        print("  WARNING: population rates file not found — lift gate disabled")
        pop_rates = {}

    # ------------------------------------------------------------------
    # 3. Build KNN index
    # ------------------------------------------------------------------
    print("\nBuilding KNN index...")
    X_index, index_seqns, available_cols = build_knn_index(norm_df, anchor_cols, imputer)
    print(f"  Index size: {X_index.shape} (rows x anchor features)")

    # Build the lab values subset for all index rows.
    # Baking this into the pkl makes knn_scorer.py fully self-contained at
    # runtime — no 20 MB NHANES CSV needed on the production server.
    lab_cols_for_pkg = [
        c for c in ref_lookup
        if c in final_df.columns
        and c not in DUPLICATE_LAB_COLS
        and c not in NON_LAB_REF_COLS
    ]
    extra_cols_for_pkg = [c for c in ["gender", "age_years"] if c in final_df.columns]
    lab_df = final_df[lab_cols_for_pkg + extra_cols_for_pkg].copy()

    # Save reusable inference package
    inference_pkg = {
        "X_index":       X_index,
        "index_seqns":   index_seqns,
        "anchor_cols":   available_cols,
        "imputer":       imputer,
        "ref_lookup":    ref_lookup,
        "lab_df":        lab_df,   # (7437 × ~57) lab values — eliminates CSV dep at runtime
    }
    pkg_path = ARTIFACT_DIR / "knn_inference_pkg.pkl"
    with open(pkg_path, "wb") as f:
        pickle.dump(inference_pkg, f)
    print(f"  KNN inference package saved: {pkg_path} (includes lab_df — no CSV needed at runtime)")

    # ------------------------------------------------------------------
    # 4. Run: single user or validation sample
    # ------------------------------------------------------------------
    if target_seqn:
        seqns_to_run = [target_seqn]
        print(f"\nRunning single user SEQN={target_seqn}")
    else:
        rng = np.random.default_rng(42)
        seqns_to_run = rng.choice(index_seqns, size=VALIDATION_SAMPLE_N, replace=False).tolist()
        print(f"\nRunning validation sample: {VALIDATION_SAMPLE_N} random users")

    all_results = []
    for seqn in seqns_to_run:
        if seqn not in norm_df.index:
            continue

        user_row = norm_df.loc[[seqn], available_cols].values.astype(float)
        user_row_imp = imputer.transform(user_row)

        # Sex and age for reference range lookup
        sex = final_df.loc[seqn, "gender"] if seqn in final_df.index else "Female"
        age = final_df.loc[seqn, "age_years"] if seqn in final_df.index else 40.0

        nb_seqns, nb_dists = find_neighbours(user_row_imp, X_index, index_seqns, k=KNN_K)
        lab_signals = get_neighbour_lab_signals(
            nb_seqns, nb_dists, final_df, ref_lookup, sex, age, pop_rates
        )

        conditions = {c: int(labels_df.loc[seqn, c]) for c in CONDITION_COLS
                      if seqn in labels_df.index} if seqn in labels_df.index else {}

        result = {
            "seqn":        int(seqn),
            "sex":         SEX_MAP.get(sex, str(sex)),
            "age":         float(age),
            "conditions":  conditions,
            "k":           KNN_K,
            "lab_signals": lab_signals,
        }
        all_results.append(result)

        if target_seqn:
            print(f"\nUser SEQN={seqn}  sex={SEX_MAP.get(sex)}  age={age:.0f}")
            print(f"True conditions: {[k for k,v in conditions.items() if v]}")
            print(f"\nNeighbour lab signals (≥{MIN_NEIGHBOUR_FRACTION*100:.0f}% of {KNN_K} neighbours):")
            if lab_signals:
                for sig in lab_signals:
                    print(f"  {sig['lab_col']:50s}  {sig['direction']:4s}  "
                          f"{sig['n_abnormal']}/{sig['n_checked']} neighbours  "
                          f"(median={sig['median_value']}  ref=[{sig['lower']}, {sig['upper']}])")
            else:
                print("  No consistently abnormal labs found in neighbourhood.")

    # ------------------------------------------------------------------
    # 5. Save validation output
    # ------------------------------------------------------------------
    out_path = OUT_DIR / "knn_lab_signals.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved: {out_path}")

    # ------------------------------------------------------------------
    # 6. Validation summary (only for batch run)
    # ------------------------------------------------------------------
    if not target_seqn:
        print("\n--- Validation Summary ---")
        total_with_signals = sum(1 for r in all_results if r["lab_signals"])
        print(f"Users with ≥1 neighbour lab signal: {total_with_signals}/{len(all_results)} "
              f"({total_with_signals/len(all_results)*100:.0f}%)")

        # Most commonly flagged labs across the validation cohort
        from collections import Counter
        lab_counts = Counter()
        for r in all_results:
            for sig in r["lab_signals"]:
                lab_counts[f"{sig['lab_col']} ({sig['direction']})"] += 1

        print(f"\nTop 15 most frequently surfaced labs across {len(all_results)} users:")
        for lab, count in lab_counts.most_common(15):
            print(f"  {count:4d}  {lab}")

        # Check: do users with known conditions get relevant lab flags?
        print("\nCondition → lab signal hit rate (does having condition X → relevant abnormal lab?):")
        for cond in CONDITION_COLS:
            cond_users = [r for r in all_results if r["conditions"].get(cond) == 1]
            if not cond_users:
                continue
            with_signals = sum(1 for r in cond_users if r["lab_signals"])
            print(f"  {cond:20s}: {len(cond_users):3d} users, "
                  f"{with_signals}/{len(cond_users)} have ≥1 lab signal "
                  f"({with_signals/len(cond_users)*100:.0f}%)")

    print("\n=== Done ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seqn", type=int, default=None,
                        help="Run for a single SEQN (default: validation batch)")
    args = parser.parse_args()
    main(target_seqn=args.seqn)
