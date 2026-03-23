from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"

NORMALIZER_FILE = MODELS_DIR / "nhanes_hybrid_normalizer.joblib"


def _resolve_artifact(filename: str) -> Path:
    candidates = [
        DATA_DIR / filename,
        DATA_DIR / "normalized" / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


class InferencePreprocessor:
    """
    Reuses saved preprocessing artifacts at inference time.

    Important:
    - Current production models were trained on `nhanes_merged_adults_final.csv`,
      so raw-value cleanup is applied by default.
    - Reference/z-score normalization is available as an opt-in mode for future
      models retrained on the normalized dataset.
    """

    def __init__(self) -> None:
        self.ml_ready_metadata_file = _resolve_artifact("nhanes_ml_ready_metadata.json")
        self.sparse_table_file = _resolve_artifact("nhanes_ml_ready_sparse_columns.csv")
        metadata = json.loads(self.ml_ready_metadata_file.read_text(encoding="utf-8"))
        self.metadata = metadata
        self.sentinel_map = {
            item["column"]: item["sentinel_values_replaced"]
            for item in metadata.get("sentinel_replacements", [])
        }
        self.duplicate_pairs = metadata.get("duplicate_keep_drop_pairs", [])
        self.duplicate_drop_columns = metadata.get("duplicate_drop_columns", [])
        self.sparse_drop_columns = self._load_sparse_drop_columns()
        self._normalizer = None

    def _load_sparse_drop_columns(self) -> list[str]:
        if not self.sparse_table_file.exists():
            return []
        df = pd.read_csv(self.sparse_table_file)
        return df.loc[df["drop_for_ml_ready"], "column"].tolist()

    def _ensure_normalizer(self):
        if self._normalizer is None:
            import joblib
            from scripts import normalize_final_dataset  # noqa: F401

            self._normalizer = joblib.load(NORMALIZER_FILE)
        return self._normalizer

    @staticmethod
    def _coerce_missingable_value(value: Any) -> Any:
        if value is None:
            return np.nan
        return value

    def prepare_raw_dataframe(self, answers: dict[str, Any]) -> pd.DataFrame:
        df = pd.DataFrame([{k: self._coerce_missingable_value(v) for k, v in answers.items()}])

        # Preserve canonical columns when a duplicate alias arrives from the frontend.
        for item in self.duplicate_pairs:
            keep_column = item["keep_column"]
            drop_column = item["drop_column"]
            if keep_column not in df.columns and drop_column in df.columns:
                df[keep_column] = df[drop_column]

        return df

    def apply_raw_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()

        for column, sentinel_values in self.sentinel_map.items():
            if column in cleaned.columns:
                cleaned[column] = cleaned[column].replace(sentinel_values, np.nan)

        cleaned = cleaned.drop(columns=[c for c in self.duplicate_drop_columns if c in cleaned.columns], errors="ignore")
        cleaned = cleaned.drop(columns=[c for c in self.sparse_drop_columns if c in cleaned.columns], errors="ignore")
        return cleaned

    def apply_normalized_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        pre_normalized = df.copy()
        for column, sentinel_values in self.sentinel_map.items():
            if column in pre_normalized.columns:
                pre_normalized[column] = pre_normalized[column].replace(sentinel_values, np.nan)

        normalized = self._ensure_normalizer().transform(pre_normalized)
        normalized = normalized.drop(columns=[c for c in self.duplicate_drop_columns if c in normalized.columns], errors="ignore")
        normalized = normalized.drop(columns=[c for c in self.sparse_drop_columns if c in normalized.columns], errors="ignore")
        return normalized

    def prepare_feature_source(
        self,
        answers: dict[str, Any],
        *,
        normalized_for_retrained_models: bool = False,
    ) -> dict[str, Any]:
        df = self.prepare_raw_dataframe(answers)
        if normalized_for_retrained_models:
            cleaned = self.apply_normalized_cleanup(df)
        else:
            cleaned = self.apply_raw_cleanup(df)
        return cleaned.iloc[0].to_dict()
