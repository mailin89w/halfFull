from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.normalize_final_dataset import AGE_BINS, AGE_LABELS, REFERENCE_SPECS, HybridReferenceNormalizer


INPUT_FILE = ROOT / "data" / "processed" / "nhanes_2017_2018_vitd_real_cohort.csv"
OUTPUT_FILE = ROOT / "data" / "processed" / "normalized" / "nhanes_2017_2018_vitd_real_cohort_normalized.csv"
ACTIONS_FILE = ROOT / "data" / "processed" / "normalized" / "nhanes_2017_2018_vitd_normalization_actions.csv"
REFERENCES_FILE = ROOT / "data" / "processed" / "normalized" / "nhanes_2017_2018_vitd_reference_ranges_used.csv"
METADATA_FILE = ROOT / "data" / "processed" / "normalized" / "nhanes_2017_2018_vitd_hybrid_normalizer_metadata.json"
NORMALIZER_FILE = ROOT / "models" / "nhanes_2017_2018_vitd_hybrid_normalizer.joblib"


def main() -> None:
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    normalizer = HybridReferenceNormalizer(REFERENCE_SPECS).fit(df)
    transformed = normalizer.transform(df)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    NORMALIZER_FILE.parent.mkdir(parents=True, exist_ok=True)

    transformed.to_csv(OUTPUT_FILE, index=False)
    pd.DataFrame(normalizer.actions).sort_values(["action", "column"]).to_csv(ACTIONS_FILE, index=False)
    pd.DataFrame(normalizer.reference_table_rows).drop_duplicates().to_csv(REFERENCES_FILE, index=False)

    metadata = {
        "input_file": str(INPUT_FILE),
        "output_file": str(OUTPUT_FILE),
        "age_bins": AGE_BINS,
        "age_labels": AGE_LABELS,
        "reference_columns": normalizer.reference_columns,
        "zscore_columns": normalizer.zscore_columns,
        "untouched_columns": sorted(set(normalizer.untouched_columns)),
        "zscore_stats": normalizer.zscore_stats,
        "action_counts": pd.DataFrame(normalizer.actions)["action"].value_counts().to_dict(),
        "notes": "Same hybrid normalization logic as scripts/normalize_final_dataset.py, fit on the NHANES 2017-2018 vitamin D cohort.",
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    joblib.dump(normalizer, NORMALIZER_FILE)

    print(f"Saved normalized cohort to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
