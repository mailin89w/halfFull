"""
cluster_train.py

Trains the HalfFull clustering layer:
  1. Loads finalized anchor feature set from feature selection rankings
  2. Runs UMAP (12D for clustering, 2D for visualization checkpoint)
  3. Runs HDBSCAN on the 12D embedding
  4. Saves all artifacts needed for inference and fingerprint generation

Outputs (written to data/processed/cluster/):
  cluster_assignments.csv          -- SEQN + cluster_id + umap_x + umap_y + membership_strength
  umap_2d_coords.csv               -- SEQN + x + y for visualization
  cluster_summary.csv              -- cluster sizes and label distributions
  artifacts/umap_12d.joblib        -- fitted UMAP (12D) for inference
  artifacts/hdbscan_model.joblib   -- fitted HDBSCAN for approximate_predict
  artifacts/anchor_features.json   -- ordered list of anchor feature names used
  artifacts/enrichment_features.json -- enrichment feature names for fingerprinting

Usage:
  python scripts/cluster_train.py
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import umap
import hdbscan
from sklearn.impute import SimpleImputer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT             = Path(".")
NORMALIZED_FILE  = ROOT / "data/processed/nhanes_merged_adults_final_normalized.csv"
DISEASES_FILE    = ROOT / "data/processed/nhanes_merged_adults_diseases.csv"
ANCHOR_RANKING   = ROOT / "data/processed/cluster/anchor_feature_ranking.csv"
ENRICHMENT_RANKING = ROOT / "data/processed/cluster/enrichment_feature_ranking.csv"
OUT_DIR          = ROOT / "data/processed/cluster"
ARTIFACT_DIR     = OUT_DIR / "artifacts"

OUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Feature selection config
# ---------------------------------------------------------------------------

# Anchor features to always protect regardless of RF rank
PROTECTED_ANCHOR = [
    "dpq040___feeling_tired_or_having_little_energy",  # primary fatigue signal
    "age_years",                                        # clinical context
    "bmi",                                              # metabolic context
]

# Anchor features to drop even if they rank above the cutoff
# (redundant, admin, or too granular to be meaningful for clustering)
ANCHOR_EXCLUDE = {
    # Redundant blood pressure sub-questions (bpq020 already captures hypertension)
    "bpq030___told_had_high_blood_pressure___2+_times",
    "bpq050a___now_taking_prescribed_medicine_for_hbp",
    # Granular urinary incontinence follow-ups (kiq022 captures the main signal)
    "kiq430___how_frequently_does_this_occur?",
    "kiq450___how_frequently_does_this_occur?",
    "kiq044___urinated_before_reaching_the_toilet?",
    "kiq010___how_much_urine_lose_each_time?",
    # Too specific / low n
    "smq078___how_soon_after_waking_do_you_smoke",
    "mcq540___ever_seen_a_dr_about_this_pain",
    "rhq131___ever_been_pregnant?",              # rhq160 (n pregnancies) is more informative
    "mcq195___which_type_of_arthritis_was_it?",  # follow-up to mcq160a
    "alq111___ever_had_a_drink_of_any_kind_of_alcohol",  # redundant with alq130
}

# Importance threshold: features below this are cut unless in PROTECTED_ANCHOR
ANCHOR_IMPORTANCE_CUTOFF = 0.004

# Enrichment features to drop (dpq040 derivatives, condition labels, duplicates, weak)
ENRICHMENT_EXCLUDE = {
    # dpq040 derivatives — not independent signals
    "fatigue_ordinal",
    "fatigue_binary_lenient",
    "fatigue_binary_strict",
    # Condition label — not an enrichment feature
    "prediabetes",
    # Duplicate units — keeping mg/dl versions below
    "LBDSCRSI_creatinine_refrigerated_serum_umol_l",   # dup of LBXSCR
    "LBDSGLSI_glucose_refrigerated_serum_mmol_l",       # dup of LBXSGL
    "URXUMA_albumin_urine_ug_ml",                       # dup of URXUMS
    "LBDBCDSI_blood_cadmium_nmol_l",                    # dup of LBXBCD
    "LBDBPBSI_blood_lead_umol_l",                       # dup of LBXBPB
    "LBXFER_ferritin_ng_ml",                            # dup of ferritin_ng_ml
    "LBDFERSI_ferritin_ug_l",                           # dup of ferritin_ng_ml
    # Binary flag redundant with rxdcount
    "rxduse___taken_prescription_medicine,_past_month",
    # Diagnosis age — weak clustering enrichment signal
    "mcd180l___age_when_told_you_had_liver_condition",
    "mcd180m___age_when_told_you_had_thyroid_problem",
    # Patient-reported BP values — noisy
    "diq300d___what_was_your_recent_dbp",
    "diq300s___what_was_your_recent_sbp",
    # Generic lifestyle advice (not informative for what the cluster has)
    "mcq366a___doctor_told_to_control_weight",
    "mcq366b___doctor_told_to_increase_exercise",
    "mcq366c___doctor_told_to_reduce_salt",
    "height_cm",                                        # not clinically interesting as enrichment
}

# UMAP config
# cosine metric outperforms euclidean/manhattan for this mixed ordinal+continuous dataset:
# it measures symptom *pattern* similarity (angle) rather than absolute distance,
# producing 7 stable clusters with 1-2% noise vs 3 clusters with euclidean.
UMAP_ND_PARAMS = dict(
    n_components=12,
    n_neighbors=50,
    min_dist=0.0,
    metric="cosine",
    random_state=42,
    low_memory=False,
)

UMAP_2D_PARAMS = dict(
    n_components=2,
    n_neighbors=50,
    min_dist=0.1,
    metric="cosine",
    random_state=42,
    low_memory=False,
)

# HDBSCAN config
# min_cluster_size=20 produces 7 clinically meaningful clusters with ~1.6% noise.
# Smaller values (5-15) create excessive noise (43-46%); larger values collapse to 3 clusters.
# The largest cluster (~90% of data) is the "general population" bucket —
# inference uses KNN within this cluster rather than a fixed fingerprint.
HDBSCAN_PARAMS = dict(
    min_cluster_size=20,
    min_samples=5,
    cluster_selection_method="eom",
    prediction_data=True,   # needed for approximate_predict at inference
)

# KNN fallback: number of nearest neighbours to use for users landing in the general cluster
KNN_FALLBACK_K = 50

# Condition label columns (for cluster summary only — not used in training)
CONDITION_COLS = [
    "anemia", "thyroid", "sleep_disorder", "kidney",
    "hepatitis_bc", "liver", "diabetes",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def select_anchor_features(ranking_path: Path) -> list[str]:
    df = pd.read_csv(ranking_path)
    keep = []
    for _, row in df.iterrows():
        feat = row["feature"]
        imp  = row["mean_importance"]
        if feat in ANCHOR_EXCLUDE:
            continue
        if imp >= ANCHOR_IMPORTANCE_CUTOFF or feat in PROTECTED_ANCHOR:
            keep.append(feat)
    return keep


def select_enrichment_features(ranking_path: Path) -> list[str]:
    df = pd.read_csv(ranking_path)
    keep = []
    for _, row in df.iterrows():
        feat = row["feature"]
        if feat not in ENRICHMENT_EXCLUDE:
            keep.append(feat)
    return keep


def load_and_align(norm_path: Path, diseases_path: Path,
                   anchor_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    norm_df = pd.read_csv(norm_path, low_memory=False)
    norm_df = norm_df.set_index("SEQN") if "SEQN" in norm_df.columns else norm_df

    # Keep only anchor columns that exist in the file
    available = [c for c in anchor_cols if c in norm_df.columns]
    missing   = [c for c in anchor_cols if c not in norm_df.columns]
    if missing:
        print(f"  Warning: {len(missing)} anchor features not found in normalized file: {missing}")
    X = norm_df[available].copy()

    labels_df = pd.read_csv(diseases_path, usecols=["SEQN"] + CONDITION_COLS, low_memory=False)
    labels_df = labels_df.set_index("SEQN")

    shared = X.index.intersection(labels_df.index)
    return X.loc[shared], labels_df.loc[shared]


def impute(X: pd.DataFrame) -> tuple[np.ndarray, SimpleImputer]:
    imp = SimpleImputer(strategy="median")
    arr = imp.fit_transform(X)
    return arr, imp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== HalfFull Cluster Training ===\n")

    # ------------------------------------------------------------------
    # 1. Select features
    # ------------------------------------------------------------------
    print("Selecting anchor features...")
    anchor_cols = select_anchor_features(ANCHOR_RANKING)
    print(f"  Anchor features selected: {len(anchor_cols)}")
    for f in anchor_cols:
        print(f"    {f}")

    print("\nSelecting enrichment features...")
    enrichment_cols = select_enrichment_features(ENRICHMENT_RANKING)
    print(f"  Enrichment features selected: {len(enrichment_cols)}")

    # Save feature lists
    (ARTIFACT_DIR / "anchor_features.json").write_text(
        json.dumps(anchor_cols, indent=2)
    )
    (ARTIFACT_DIR / "enrichment_features.json").write_text(
        json.dumps(enrichment_cols, indent=2)
    )
    print(f"\nFeature lists saved to {ARTIFACT_DIR}/")

    # ------------------------------------------------------------------
    # 2. Load and prepare data
    # ------------------------------------------------------------------
    print("\nLoading normalized data...")
    X_df, labels_df = load_and_align(NORMALIZED_FILE, DISEASES_FILE, anchor_cols)
    print(f"  Shape: {X_df.shape}")

    X, imp = impute(X_df)
    print(f"  Missing values imputed. Feature matrix ready: {X.shape}")

    # ------------------------------------------------------------------
    # 3. UMAP — 12D for clustering
    # ------------------------------------------------------------------
    print("\nFitting UMAP (12D)...")
    reducer_12d = umap.UMAP(**UMAP_ND_PARAMS)
    embedding_12d = reducer_12d.fit_transform(X)
    print(f"  12D embedding shape: {embedding_12d.shape}")

    joblib.dump(reducer_12d, ARTIFACT_DIR / "umap_12d.joblib")
    print(f"  Saved: {ARTIFACT_DIR}/umap_12d.joblib")

    # Save embedding matrix for fingerprint script (avoids re-running UMAP)
    np.save(ARTIFACT_DIR / "embedding_12d.npy", embedding_12d)
    # Save imputer for consistent inference-time preprocessing
    joblib.dump(imp, ARTIFACT_DIR / "anchor_imputer.joblib")
    print(f"  Saved: {ARTIFACT_DIR}/embedding_12d.npy + anchor_imputer.joblib")

    # ------------------------------------------------------------------
    # 4. UMAP — 2D for visualization checkpoint
    # ------------------------------------------------------------------
    print("\nFitting UMAP (2D visualization)...")
    reducer_2d = umap.UMAP(**UMAP_2D_PARAMS)
    embedding_2d = reducer_2d.fit_transform(X)

    umap_2d_df = pd.DataFrame({
        "SEQN": X_df.index,
        "umap_x": embedding_2d[:, 0],
        "umap_y": embedding_2d[:, 1],
    })
    umap_2d_path = OUT_DIR / "umap_2d_coords.csv"
    umap_2d_df.to_csv(umap_2d_path, index=False)
    print(f"  Saved: {umap_2d_path}")

    # ------------------------------------------------------------------
    # 5. HDBSCAN on 12D embedding
    # ------------------------------------------------------------------
    print("\nFitting HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(**HDBSCAN_PARAMS)
    cluster_labels = clusterer.fit_predict(embedding_12d)

    n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
    n_noise    = (cluster_labels == -1).sum()
    print(f"  Clusters found:  {n_clusters}")
    print(f"  Noise points:    {n_noise} ({n_noise/len(cluster_labels)*100:.1f}%)")

    joblib.dump(clusterer, ARTIFACT_DIR / "hdbscan_model.joblib")
    print(f"  Saved: {ARTIFACT_DIR}/hdbscan_model.joblib")

    # Membership strength (soft clustering probabilities)
    membership_strength = hdbscan.membership_vector(clusterer, embedding_12d)
    # For assigned points use their cluster's probability; noise points get max across all clusters
    strength_scores = np.array([
        clusterer.probabilities_[i] if cluster_labels[i] != -1
        else float(membership_strength[i].max()) if membership_strength[i].sum() > 0
        else 0.0
        for i in range(len(cluster_labels))
    ])

    # ------------------------------------------------------------------
    # 6. Save cluster assignments
    # ------------------------------------------------------------------
    assignments_df = pd.DataFrame({
        "SEQN":               X_df.index,
        "cluster_id":         cluster_labels,
        "membership_strength": strength_scores,
        "umap_x":             embedding_2d[:, 0],
        "umap_y":             embedding_2d[:, 1],
    })
    # Merge condition labels for summary
    assignments_df = assignments_df.join(labels_df, on="SEQN")

    assignments_path = OUT_DIR / "cluster_assignments.csv"
    assignments_df.to_csv(assignments_path, index=False)
    print(f"\nCluster assignments saved: {assignments_path}")

    # ------------------------------------------------------------------
    # 7. Cluster summary
    # ------------------------------------------------------------------
    print("\n--- Cluster Summary ---")
    summary_rows = []
    for cid in sorted(assignments_df["cluster_id"].unique()):
        subset = assignments_df[assignments_df["cluster_id"] == cid]
        n = len(subset)
        row = {"cluster_id": cid, "size": n, "pct_of_total": round(n / len(assignments_df) * 100, 1)}
        for col in CONDITION_COLS:
            if col in subset.columns:
                row[f"pct_{col}"] = round(subset[col].mean() * 100, 1)
        row["mean_membership_strength"] = round(subset["membership_strength"].mean(), 3)
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_path = OUT_DIR / "cluster_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print(summary_df.to_string(index=False))

    # ------------------------------------------------------------------
    # 8. Quick validation: label consistency per cluster
    # ------------------------------------------------------------------
    print("\n--- Neighbour Label Consistency Check ---")
    named_clusters = assignments_df[assignments_df["cluster_id"] != -1]
    consistency_rows = []
    for cid in sorted(named_clusters["cluster_id"].unique()):
        subset = named_clusters[named_clusters["cluster_id"] == cid]
        # Find dominant condition
        cond_rates = {col: subset[col].mean() for col in CONDITION_COLS if col in subset.columns}
        dominant = max(cond_rates, key=cond_rates.get)
        dominant_rate = cond_rates[dominant]
        consistency_rows.append({
            "cluster_id": cid,
            "size": len(subset),
            "dominant_condition": dominant,
            "dominant_condition_pct": round(dominant_rate * 100, 1),
            "mean_strength": round(subset["membership_strength"].mean(), 3),
        })

    consistency_df = pd.DataFrame(consistency_rows)
    consistency_path = OUT_DIR / "cluster_label_consistency.csv"
    consistency_df.to_csv(consistency_path, index=False)
    print(consistency_df.to_string(index=False))

    overall_consistency = (consistency_df["dominant_condition_pct"] >= 60).mean() * 100
    print(f"\nClusters meeting >=60% label consistency: {overall_consistency:.0f}%")
    print("(Target: as many as possible — this is the neighbour label consistency metric)")

    print("\n=== Done ===")
    print(f"\nAll outputs in: {OUT_DIR}")
    print("Next step: run cluster_fingerprints.py to build per-cluster JSON fingerprints")


if __name__ == "__main__":
    main()
