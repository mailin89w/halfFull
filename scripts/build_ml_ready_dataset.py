from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


INPUT_FILE = Path("data/processed/nhanes_merged_adults_final_normalized.csv")
SENTINEL_FLAGS_FILE = Path("data/processed/nhanes_normalized_sentinel_flags.csv")
DUPLICATE_FLAGS_FILE = Path("data/processed/nhanes_normalized_duplicate_columns.csv")
MISSINGNESS_FLAGS_FILE = Path("data/processed/nhanes_normalized_missingness_flags.csv")

OUTPUT_FILE = Path("data/processed/nhanes_merged_adults_final_ml_ready.csv")
SPARSE_LIST_FILE = Path("data/processed/nhanes_ml_ready_sparse_columns.csv")
OPTIONAL_CLUSTER_FILE = Path("data/processed/nhanes_merged_adults_final_cluster_optional.csv")
METADATA_FILE = Path("data/processed/nhanes_ml_ready_metadata.json")

SPARSE_DROP_THRESHOLD = 0.95
VERY_SPARSE_CLUSTER_THRESHOLD = 0.99


def choose_columns_to_drop(duplicate_flags: pd.DataFrame) -> tuple[list[str], list[dict[str, str]]]:
    drop_columns: list[str] = []
    decisions: list[dict[str, str]] = []
    for keep, drop in duplicate_flags[["column", "duplicate_of"]].itertuples(index=False):
        drop_columns.append(drop)
        decisions.append({"keep_column": keep, "drop_column": drop})
    return sorted(set(drop_columns)), decisions


def build_sparse_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        missing_fraction = float(df[column].isna().mean())
        rows.append(
            {
                "column": column,
                "missing_fraction": missing_fraction,
                "drop_for_ml_ready": missing_fraction > SPARSE_DROP_THRESHOLD,
                "drop_for_cluster_optional": missing_fraction > VERY_SPARSE_CLUSTER_THRESHOLD,
            }
        )
    return pd.DataFrame(rows).sort_values(["missing_fraction", "column"], ascending=[False, True])


def main() -> None:
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    sentinel_flags = pd.read_csv(SENTINEL_FLAGS_FILE)
    duplicate_flags = pd.read_csv(DUPLICATE_FLAGS_FILE)

    likely_sentinel = sentinel_flags[sentinel_flags["likely_special_missing_code"]].copy()
    sentinel_map = (
        likely_sentinel.groupby("column")["sentinel_value"]
        .apply(lambda values: sorted({int(v) for v in values}))
        .to_dict()
    )

    cleaned = df.copy()
    sentinel_replacements: list[dict[str, object]] = []
    for column, sentinel_values in sentinel_map.items():
        if column not in cleaned.columns:
            continue
        before_missing = int(cleaned[column].isna().sum())
        cleaned[column] = cleaned[column].replace(sentinel_values, pd.NA)
        after_missing = int(cleaned[column].isna().sum())
        sentinel_replacements.append(
            {
                "column": column,
                "sentinel_values_replaced": sentinel_values,
                "new_missing_values_created": after_missing - before_missing,
            }
        )

    duplicate_drop_columns, duplicate_decisions = choose_columns_to_drop(duplicate_flags)
    cleaned = cleaned.drop(columns=[c for c in duplicate_drop_columns if c in cleaned.columns])

    sparse_table = build_sparse_table(cleaned)
    ml_drop_sparse = sparse_table.loc[sparse_table["drop_for_ml_ready"], "column"].tolist()
    cluster_drop_sparse = sparse_table.loc[sparse_table["drop_for_cluster_optional"], "column"].tolist()

    ml_ready = cleaned.drop(columns=[c for c in ml_drop_sparse if c in cleaned.columns])
    cluster_optional = cleaned.drop(columns=[c for c in cluster_drop_sparse if c in cleaned.columns])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ml_ready.to_csv(OUTPUT_FILE, index=False)
    sparse_table.to_csv(SPARSE_LIST_FILE, index=False)
    cluster_optional.to_csv(OPTIONAL_CLUSTER_FILE, index=False)

    metadata = {
        "input_file": str(INPUT_FILE),
        "output_file_ml_ready": str(OUTPUT_FILE),
        "output_file_cluster_optional": str(OPTIONAL_CLUSTER_FILE),
        "sparse_column_table": str(SPARSE_LIST_FILE),
        "sparse_drop_threshold_ml_ready": SPARSE_DROP_THRESHOLD,
        "sparse_drop_threshold_cluster_optional": VERY_SPARSE_CLUSTER_THRESHOLD,
        "sentinel_replacement_columns": len(sentinel_replacements),
        "sentinel_replacements": sentinel_replacements,
        "duplicate_drop_count": len(duplicate_drop_columns),
        "duplicate_drop_columns": duplicate_drop_columns,
        "duplicate_keep_drop_pairs": duplicate_decisions,
        "ml_ready_shape": [int(ml_ready.shape[0]), int(ml_ready.shape[1])],
        "cluster_optional_shape": [int(cluster_optional.shape[0]), int(cluster_optional.shape[1])],
        "ml_ready_sparse_dropped_count": len(ml_drop_sparse),
        "cluster_optional_sparse_dropped_count": len(cluster_drop_sparse),
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved ML-ready dataset to {OUTPUT_FILE}")
    print(f"Saved cluster-optional dataset to {OPTIONAL_CLUSTER_FILE}")
    print(f"Saved sparse-column table to {SPARSE_LIST_FILE}")
    print(f"Saved metadata to {METADATA_FILE}")


if __name__ == "__main__":
    main()
