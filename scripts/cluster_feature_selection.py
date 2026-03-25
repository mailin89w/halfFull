"""
cluster_feature_selection.py

Runs two Random Forest sweeps to produce:
  1. Anchor feature ranking  -- which of the 78 product-time features matter most
  2. Enrichment discovery    -- which NHANES-only features should populate cluster fingerprints

Outputs (written to data/processed/cluster/):
  anchor_feature_ranking.csv      -- 78 anchor features ranked by mean RF importance
  enrichment_feature_ranking.csv  -- top non-anchor NHANES features ranked by mean RF importance
  feature_selection_report.md     -- plain-language summary for review

Usage:
  python scripts/cluster_feature_selection.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(".")
FINAL_FILE        = ROOT / "data/processed/nhanes_merged_adults_final.csv"
NORMALIZED_FILE   = ROOT / "data/processed/nhanes_merged_adults_final_normalized.csv"
DISEASES_FILE     = ROOT / "data/processed/nhanes_merged_adults_diseases.csv"
ROADMAP_FILE      = ROOT / "Downloads/HalfFull roadmap - diseases VS features (3).csv"
OUT_DIR           = ROOT / "data/processed/cluster"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONDITION_LABELS = [
    "anemia",
    "thyroid",
    "sleep_disorder",
    "kidney",
    "hepatitis_bc",
    "liver",
    "diabetes",
]

# dpq040 is used as a separate ordinal target (0-3 severity scale, dropping codes 7/9)
# This captures the fatigue severity gradient, not just a binary flag
DPQ040_COL = "dpq040___feeling_tired_or_having_little_energy"
DPQ040_VALID_VALUES = {0.0, 1.0, 2.0, 3.0}

# Columns to always exclude from RF features (admin, weights, IDs, labels)
ALWAYS_DROP = [
    "SEQN", "SEQN.1",
    "SDMVPSU", "SDMVSTRA", "WTMECPRP", "WTINTPRP", "WTFOLPRP__p_folfms",
    "WTSAPRP__p_uhg",
    "cluster", "nan_count", "nan_group",
    # condition labels themselves
    "fatigue_binary", "anemia", "diabetes", "thyroid", "sleep_disorder",
    "kidney", "hepatitis_bc", "liver", "heart_failure", "coronary_heart",
    "emphysema_lungs", "high_blood_pressure", "high_cholesterol",
    "menopause", "overweight", "alcohol",
    # raw medication text columns (high cardinality, no signal)
    "rxddrug", "rxddrgid", "rxdrsc1", "rxdrsc2", "rxdrsc3",
    "rxdrsd1", "rxdrsd2", "rxdrsd3",
    "mcq230a", "mcq230b", "mcq230c",
]

RF_PARAMS = dict(
    n_estimators=300,
    max_depth=8,
    min_samples_leaf=20,
    max_features="sqrt",
    n_jobs=-1,
    random_state=42,
    class_weight="balanced",
)

# How many enrichment features to keep in the output report
TOP_ENRICHMENT_N = 60

# Minimum importance threshold to include in enrichment candidates
MIN_IMPORTANCE = 0.002


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_anchor_feature_names(roadmap_path: Path) -> list[str]:
    """
    Read the roadmap CSV and return the mapped_dataset_column values for all
    anchor_candidate rows.  Falls back to canonical_feature if mapped is blank.
    The CSV has real column headers in the first data row, not the pandas header row.
    """
    df = pd.read_csv(roadmap_path, header=None)
    # Row 1 (not row 0) contains the actual column names; row 0 is disease totals
    df.columns = df.iloc[1]
    df = df.iloc[2:].reset_index(drop=True)
    mask = df["anchor_v1"] == "anchor_candidate"
    cols = df.loc[mask, "mapped_dataset_column"].fillna(df.loc[mask, "canonical_feature"])
    return cols.dropna().str.strip().tolist()


def load_labels(diseases_path: Path, label_cols: list[str]) -> pd.DataFrame:
    needed = ["SEQN"] + label_cols + [DPQ040_COL]
    available = needed  # let pandas warn if any missing
    df = pd.read_csv(diseases_path, usecols=lambda c: c in available)
    # Clean dpq040: set refusal/don't-know codes to NaN
    if DPQ040_COL in df.columns:
        df[DPQ040_COL] = df[DPQ040_COL].where(df[DPQ040_COL].isin(DPQ040_VALID_VALUES))
    return df


def prepare_features(df: pd.DataFrame, drop_cols: list[str]) -> pd.DataFrame:
    """Drop unwanted columns, keep only numeric, drop all-NaN columns, impute median."""
    drop = [c for c in drop_cols if c in df.columns]
    df = df.drop(columns=drop)
    df = df.select_dtypes(include=[np.number])
    # Drop columns that are entirely NaN — imputer cannot handle them
    df = df.dropna(axis=1, how="all")
    imputer = SimpleImputer(strategy="median")
    arr = imputer.fit_transform(df)
    return pd.DataFrame(arr, columns=df.columns, index=df.index)


def run_rf_sweep(X: pd.DataFrame, labels: pd.DataFrame, label_cols: list[str]) -> pd.DataFrame:
    """
    Train one RF per label (binary conditions) + one RF for dpq040 ordinal severity.
    dpq040 is treated as a 4-class ordinal target (0/1/2/3) to capture fatigue severity
    gradient rather than just a binary flag.
    Returns a DataFrame ranked by mean_importance across all targets.
    """
    importance_records: dict[str, list[float]] = {feat: [] for feat in X.columns}

    # --- binary condition targets ---
    for label in label_cols:
        if label not in labels.columns:
            print(f"  Skipping {label}: column not found")
            continue
        y = labels[label].reindex(X.index)
        valid = y.notna()
        if valid.sum() < 200 or y[valid].nunique() < 2:
            print(f"  Skipping {label}: insufficient data")
            continue

        print(f"  Training RF for {label}  (positives: {int(y[valid].sum())})")
        clf = RandomForestClassifier(**RF_PARAMS)
        clf.fit(X[valid], y[valid])
        for feat, imp in zip(X.columns, clf.feature_importances_):
            importance_records[feat].append(imp)

    # --- dpq040 ordinal fatigue severity (0/1/2/3) ---
    if DPQ040_COL in labels.columns:
        y_dpq = labels[DPQ040_COL].reindex(X.index)
        valid_dpq = y_dpq.notna()
        n_valid = valid_dpq.sum()
        n_classes = y_dpq[valid_dpq].nunique()
        print(f"  Training RF for dpq040 fatigue severity  "
              f"(n={n_valid}, classes={sorted(y_dpq[valid_dpq].unique().tolist())})")
        clf_dpq = RandomForestClassifier(**RF_PARAMS)
        clf_dpq.fit(X[valid_dpq], y_dpq[valid_dpq])
        # Weight dpq040 the same as one binary label (not double-counted)
        for feat, imp in zip(X.columns, clf_dpq.feature_importances_):
            importance_records[feat].append(imp)
    else:
        print(f"  dpq040 column not found in labels, skipping fatigue severity sweep")

    rows = []
    for feat, imps in importance_records.items():
        if imps:
            rows.append({"feature": feat, "mean_importance": np.mean(imps), "n_labels": len(imps)})
        else:
            rows.append({"feature": feat, "mean_importance": 0.0, "n_labels": 0})

    return pd.DataFrame(rows).sort_values("mean_importance", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== HalfFull Cluster Feature Selection ===\n")

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    print("Loading _final_normalized (anchor sweep)...")
    norm_df = pd.read_csv(NORMALIZED_FILE)
    norm_df = norm_df.set_index("SEQN") if "SEQN" in norm_df.columns else norm_df

    print("Loading _final (enrichment sweep)...")
    final_df = pd.read_csv(FINAL_FILE)
    final_df = final_df.set_index("SEQN") if "SEQN" in final_df.columns else final_df

    print("Loading condition labels...")
    labels_df = load_labels(DISEASES_FILE, CONDITION_LABELS)
    labels_df = labels_df.set_index("SEQN")

    # ------------------------------------------------------------------
    # 2. Anchor feature set from roadmap
    # ------------------------------------------------------------------
    print("\nReading anchor feature list from roadmap...")
    roadmap_path = Path("/Users/annaesakova") / "Downloads/HalfFull roadmap - diseases VS features (3).csv"
    if not roadmap_path.exists():
        # fallback: look in data/processed
        roadmap_path = ROOT / "data/processed/HalfFull roadmap - diseases VS features.updated.csv"

    anchor_names_raw = load_anchor_feature_names(roadmap_path)

    # Match roadmap names against actual columns in _final_normalized
    norm_cols = set(norm_df.columns)
    anchor_cols = [c for c in anchor_names_raw if c in norm_cols]
    missing_anchor = [c for c in anchor_names_raw if c not in norm_cols]

    print(f"  Anchor candidates from roadmap: {len(anchor_names_raw)}")
    print(f"  Found in _final_normalized:     {len(anchor_cols)}")
    if missing_anchor:
        print(f"  Not found (check column names): {missing_anchor[:10]}")

    # ------------------------------------------------------------------
    # 3. Sweep 1 — anchor feature ranking
    # ------------------------------------------------------------------
    print("\n--- Sweep 1: Anchor feature ranking ---")
    anchor_df = norm_df[anchor_cols].copy()
    anchor_drop = [c for c in ALWAYS_DROP if c in anchor_df.columns]
    X_anchor = prepare_features(anchor_df, anchor_drop)
    X_anchor.index = norm_df.index

    # Align labels
    shared_idx = X_anchor.index.intersection(labels_df.index)
    X_anchor = X_anchor.loc[shared_idx]
    labels_anchor = labels_df.loc[shared_idx]

    anchor_ranking = run_rf_sweep(X_anchor, labels_anchor, CONDITION_LABELS)
    anchor_ranking["in_anchor_set"] = True

    anchor_out = OUT_DIR / "anchor_feature_ranking.csv"
    anchor_ranking.to_csv(anchor_out, index=False)
    print(f"\nAnchor ranking saved: {anchor_out}")
    print("\nTop 20 anchor features:")
    print(anchor_ranking.head(20).to_string(index=False))

    # ------------------------------------------------------------------
    # 4. Sweep 2 — enrichment discovery from full _final
    # ------------------------------------------------------------------
    print("\n--- Sweep 2: Enrichment discovery (full _final) ---")
    X_full = prepare_features(final_df.copy(), ALWAYS_DROP)
    X_full.index = final_df.index

    shared_idx_full = X_full.index.intersection(labels_df.index)
    X_full = X_full.loc[shared_idx_full]
    labels_full = labels_df.loc[shared_idx_full]

    full_ranking = run_rf_sweep(X_full, labels_full, CONDITION_LABELS)

    # Split: anchor features vs enrichment-only features
    anchor_col_set = set(anchor_cols)
    full_ranking["in_anchor_set"] = full_ranking["feature"].isin(anchor_col_set)

    enrichment_ranking = (
        full_ranking[~full_ranking["in_anchor_set"]]
        .query("mean_importance >= @MIN_IMPORTANCE")
        .head(TOP_ENRICHMENT_N)
        .reset_index(drop=True)
    )

    enrich_out = OUT_DIR / "enrichment_feature_ranking.csv"
    enrichment_ranking.to_csv(enrich_out, index=False)
    print(f"\nEnrichment ranking saved: {enrich_out}")
    print(f"\nTop 30 enrichment (non-anchor) features:")
    print(enrichment_ranking.head(30).to_string(index=False))

    # ------------------------------------------------------------------
    # 5. Report
    # ------------------------------------------------------------------
    top_anchor = anchor_ranking.head(50)
    dpq040_row = anchor_ranking[anchor_ranking["feature"].str.contains("dpq040", case=False)]

    report_lines = [
        "# Cluster Feature Selection Report",
        "",
        "## Anchor Feature Sweep",
        f"- Features evaluated: {len(anchor_ranking)}",
        f"- dpq040 rank: {dpq040_row.index[0] + 1 if len(dpq040_row) else 'not found'} "
        f"(importance: {dpq040_row['mean_importance'].values[0]:.4f})" if len(dpq040_row) else "- dpq040: not found in anchor set",
        "",
        "### Top 50 anchor features (recommended for UMAP input):",
        top_anchor[["feature", "mean_importance"]].to_string(index=False),
        "",
        "## Enrichment Feature Sweep",
        f"- Non-anchor NHANES features with importance >= {MIN_IMPORTANCE}: {len(enrichment_ranking)}",
        "",
        "### Top enrichment features (recommended for cluster fingerprints):",
        enrichment_ranking[["feature", "mean_importance"]].head(30).to_string(index=False),
        "",
        "## Recommended Next Step",
        "1. Review the top-50 anchor list — manually protect dpq040 and any clinically critical features",
        "   before cutting to your final ~45 for UMAP.",
        "2. Review the enrichment list — exclude anything that is a near-duplicate of an anchor feature",
        "   or that would be unavailable in the NHANES enrichment step.",
        "3. Proceed to cluster_train.py with the finalized anchor set.",
    ]

    report_path = OUT_DIR / "feature_selection_report.md"
    report_path.write_text("\n".join(report_lines))
    print(f"\nReport saved: {report_path}")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
