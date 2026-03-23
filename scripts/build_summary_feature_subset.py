from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/annaesakova/aipm/halfFull")
FINAL_PATH = ROOT / "data/processed/nhanes_merged_adults_final.csv"
MATRIX_PATH = ROOT / "data/processed/HalfFull roadmap - diseases VS features.updated.csv"
OUT_PATH = ROOT / "data/processed/nhanes_merged_adults_summary_features.csv"
REPORT_PATH = ROOT / "data/processed/nhanes_merged_adults_summary_features_report.json"


SUMMARY_TO_DATASET_TAG = {
    "perimenopause": "menopause",
    "thyroid": "thyroid",
    "kidney": "kidney",
    "sleep_disorder": "sleep_disorder",
    "anemia": "anemia",
    "liver": "liver",
    "prediabetes": "prediabetes",
    "hidden_inflammation": "infection_inflammation",
    "electrolytes": "electrolyte_imbalance",
    "hepatitis_bc": "hepatitis_bc",
    "iron_deficiency": "iron_deficiency",
}


def main() -> None:
    matrix = pd.read_csv(MATRIX_PATH, header=1)
    final = pd.read_csv(FINAL_PATH)

    summary_feature_rows = matrix[matrix["sum"].fillna(0).astype(int) > 0].copy()
    requested_features = summary_feature_rows["canonical_feature"].tolist()

    dataset_columns = set(final.columns.tolist())

    disease_tags = ["SEQN"]
    for dataset_tag in SUMMARY_TO_DATASET_TAG.values():
        if dataset_tag in dataset_columns and dataset_tag not in disease_tags:
            disease_tags.append(dataset_tag)

    present_features = [col for col in requested_features if col in dataset_columns]
    missing_features = [col for col in requested_features if col not in dataset_columns]

    selected_columns = disease_tags + present_features
    subset = final[selected_columns].copy()
    subset.to_csv(OUT_PATH, index=False)

    report = {
        "source_final": str(FINAL_PATH),
        "source_matrix": str(MATRIX_PATH),
        "output_file": str(OUT_PATH),
        "row_count": int(len(subset)),
        "selected_column_count": int(len(selected_columns)),
        "id_columns": ["SEQN"],
        "disease_tag_columns_kept": disease_tags[1:],
        "summary_to_dataset_tag_map": SUMMARY_TO_DATASET_TAG,
        "requested_summary_feature_count": int(len(requested_features)),
        "present_summary_feature_count": int(len(present_features)),
        "missing_summary_feature_count": int(len(missing_features)),
        "missing_summary_features": missing_features,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2))

    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({
        "rows": len(subset),
        "selected_columns": len(selected_columns),
        "present_features": len(present_features),
        "missing_features": len(missing_features),
    }, indent=2))


if __name__ == "__main__":
    main()
