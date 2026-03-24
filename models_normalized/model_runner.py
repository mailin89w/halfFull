"""
model_runner.py
---------------
Loads all 11 v2 disease models on startup and scores caller-supplied inputs,
returning a ranked shortlist of flagged conditions.

Raw-input path (recommended for production)
-------------------------------------------
Pass the raw user dict straight from the questionnaire / lab results:

    runner   = ModelRunner()
    shortlist = runner.score_raw(
        raw_inputs      = {"age_years": 42, "gender": "Female", ...},
        patient_context = {"age_years": 42, "gender": "Female"},
    )

``score_raw`` applies the full normalization pipeline automatically:
  1. Sentinel cleanup  — replaces NHANES refusal/unknown codes with NaN
  2. HybridReferenceNormalizer.transform()  — reference-interval scoring for
     lab values; sex-/age-group z-score for all other numeric columns
  3. Derived columns  — ``gender_female``, ``education_ord``,
     ``pregnancy_status_bin``
  4. Per-model feature slicing  — builds one single-row DataFrame per model
     using the feature list stored in each model's metadata JSON

Pre-built feature-vector path (advanced / testing)
---------------------------------------------------
If you have already prepared normalized DataFrames you can use the lower-level
``score()`` / ``run_all_with_context()`` directly:

    scores    = runner.run_all_with_context(feature_vectors, patient_context)
    shortlist = runner.filter_and_rank(scores)

Perimenopause gate
------------------
Perimenopause is only scored for patients who are:
  - gender == "Female"
  - 35 <= age_years <= 55

Without context, or outside the eligibility window, perimenopause returns 0.0.
"""

from __future__ import annotations

import json
import logging
import os
import warnings
import concurrent.futures
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("model_runner")

_DIR  = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _DIR.parent

# ── Registry — v2 normalised models ────────────────────────────────────────────

MODEL_REGISTRY = {
    "anemia":                "anemia_lr_deduped36_L2_v2.joblib",
    "electrolyte_imbalance": "electrolyte_imbalance_lr_deduped28_L2_v2.joblib",
    "kidney":                "kidney_lr_deduped17_L2_v2.joblib",
    "liver":                 "liver_rf_cal_deduped19_v2.joblib",
    "prediabetes":           "prediabetes_lr_deduped34_L2_C001_v2.joblib",
    "sleep_disorder":        "sleep_disorder_lr_trimmed29_L2_v2.joblib",
    "thyroid":               "thyroid_lr_l2_reduced-12feat_v2.joblib",
    "hidden_inflammation":   "hidden_inflammation_lr_deduped25_L2_v2.joblib",
    "perimenopause":         "perimenopause_lr_deduped21_L2_v2.joblib",
    "hepatitis_bc":          "hepatitis_bc_rf_cal_deduped20_v2.joblib",
    "iron_deficiency":       "iron_deficiency_rf_cal_deduped35_v2.joblib",
}

# Per-model recommended operating thresholds
# (lowest t where OOF precision >= 17%, maximising recall — internal model property)
RECOMMENDED_THRESHOLDS = {
    "anemia":                0.35,
    "electrolyte_imbalance": 0.60,
    "kidney":                0.66,
    "liver":                 0.10,
    "prediabetes":           0.53,
    "sleep_disorder":        0.55,
    "thyroid":               0.60,
    "hidden_inflammation":   0.41,
    "perimenopause":         0.55,
    "hepatitis_bc":          0.15,
    "iron_deficiency":       0.15,
}

# Per-disease filtering criteria
# ─────────────────────────────────────────────────────────────────────────────
# A model score at or above this value is considered worth:
#   (a) passing to the Bayesian update step, and
#   (b) potentially surfacing in user recommendations.
#
# All 11 models always run regardless of this value — it only controls which
# scores are elevated to the next pipeline stage.
#
# Calibration rationale (severity × test cost × model precision × flag rate):
#   0.10  liver / hepatitis_bc  — serious diseases, cheap confirmatory tests,
#                                  low flag rate; borderline scores still warrant Bayesian update
#   0.15  iron_deficiency       — common (esp. women), trivial test, Bayesian refines
#   0.20  kidney                — serious; lower filter lets Bayesian work on
#                                  borderline CKD signals before surfacing
#   0.30  anemia / hidden_inflammation
#                               — moderate severity, very cheap tests; anemia flags
#                                  41% at rec_thr so small downward nudge; inflammation
#                                  is a risk marker — Bayesian adds value at lower scores
#   0.35  prediabetes / thyroid — reversible / manageable; weakest models in group;
#                                  need reasonable confidence before surfacing
#   0.40  electrolyte_imbalance / perimenopause
#                               — weakest model (EI AUC 0.717) or high cohort base
#                                  rate (perimenopause 23%) → need clearer signal
#   0.55  sleep_disorder        — 32% prevalence + expensive downstream test
#                                  (polysomnography); only surface strong signals
FILTER_CRITERIA = {
    "hepatitis_bc":          0.10,
    "liver":                 0.10,
    "iron_deficiency":       0.15,
    "kidney":                0.20,
    "anemia":                0.30,
    "hidden_inflammation":   0.30,
    "prediabetes":           0.35,
    "thyroid":               0.35,
    "electrolyte_imbalance": 0.40,
    "perimenopause":         0.40,
    "sleep_disorder":        0.55,
}

# Education ordinal encoding (mirrors training setup)
_EDU_ORDER = {
    "Less than 9th grade":      0,
    "9-11th grade":             1,
    "High school / GED":        2,
    "Some college / AA":        3,
    "College graduate or above": 4,
}

# ── Quiz field-id aliases ────────────────────────────────────────────────────
# The assessment quiz (nhanes_combined_question_flow_v2.json) was updated in
# v2.1.0 to use the full NHANES column names as field_ids for these lab values.
# This map provides backward compatibility for frontends still sending the old
# human-readable names, and is applied BEFORE normalization.
QUIZ_FIELD_ALIASES: dict[str, str] = {
    # old quiz name                   →  model / normalizer column name
    "ldl_cholesterol_mg_dl":           "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
    "total_protein_g_dl":              "LBXSTP_total_protein_g_dl",
    "wbc_1000_cells_ul":               "LBXWBCSI_white_blood_cell_count_1000_cells_ul",
    # dbp_mean / sbp_mean removed from quiz — kept here so stale submissions
    # are silently dropped rather than passed through to the normalizer
    "dbp_mean":                        None,
    "sbp_mean":                        None,
    "glucose_mg_dl":                   None,
    "bpq040a___taking_prescription_for_hypertension": None,
    "mcq040___had_asthma_attack_in_past_year":        None,
    "paq605___vigorous_work_activity":                None,
    "alq170_helper_times_4_5_drinks_one_occasion_30d": None,
}

# NHANES numeric gender codes → canonical text labels used by _add_derived_columns
_GENDER_CODES: dict[int, str] = {1: "Male", 2: "Female"}

# NHANES numeric education codes → canonical text labels
_EDU_CODES: dict[int, str] = {
    1: "Less than 9th grade",
    2: "9-11th grade",
    3: "High school / GED",
    4: "Some college / AA",
    5: "College graduate or above",
}

# NHANES pregnancy_status numeric codes → canonical text labels
_PREGNANCY_CODES: dict[int, str] = {
    1: "Yes, pregnant",
    2: "No, not pregnant",
    3: "Not sure",
}


# ── InputNormalizer ─────────────────────────────────────────────────────────────

class InputNormalizer:
    """
    Converts a flat raw-input dict into a normalized dict[condition → pd.DataFrame]
    ready for ModelRunner.

    Steps
    -----
    1. Build a single-row DataFrame from raw inputs.
    2. Replace NHANES sentinel codes (refused / unknown) with NaN.
    3. Run HybridReferenceNormalizer.transform():
         - Lab columns  → reference-interval score
         - Other numeric → sex-/age-group z-score (fallback: sex-only, global)
         - String / binary / ordinal cols → passed through unchanged
    4. Add derived columns:
         - ``gender_female``       (float 0/1)
         - ``education_ord``       (int 0–4, NaN if unknown)
         - ``pregnancy_status_bin`` (float 0/1, NaN if question not answered)
    5. Slice one single-row DataFrame per model using the feature list from
       each model's *_metadata.json file.

    Parameters
    ----------
    models_dir : Path
        Directory containing v2 .joblib and _metadata.json files.
    normalizer_path : Path
        Path to the fitted HybridReferenceNormalizer .joblib.
    sentinel_meta_path : Path
        Path to nhanes_ml_ready_metadata.json containing sentinel_replacements.
    """

    def __init__(
        self,
        models_dir: Path,
        normalizer_path: Path,
        sentinel_meta_path: Path,
    ) -> None:
        import joblib
        import sys

        # The HybridReferenceNormalizer class is defined in scripts/, so ensure
        # the project root is on sys.path so joblib can deserialise it.
        root_str = str(_ROOT)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        log.info("Loading HybridReferenceNormalizer from %s", normalizer_path)
        self._normalizer = joblib.load(normalizer_path)

        # Build sentinel map: {column: [bad_codes, ...]}
        with open(sentinel_meta_path) as f:
            meta = json.load(f)
        self._sentinel_map: dict[str, list] = {
            item["column"]: item["sentinel_values_replaced"]
            for item in meta.get("sentinel_replacements", [])
        }

        # Load per-model feature lists from metadata JSONs
        self._model_features: dict[str, list[str]] = {}
        for condition, filename in MODEL_REGISTRY.items():
            meta_path = models_dir / filename.replace(".joblib", "_metadata.json")
            try:
                with open(meta_path) as f:
                    m = json.load(f)
                self._model_features[condition] = m["features"]
            except (FileNotFoundError, KeyError) as e:
                log.warning("Could not load feature list for '%s': %s", condition, e)
                self._model_features[condition] = []

        log.info("InputNormalizer ready — %d models, %d sentinel rules",
                 len(self._model_features), len(self._sentinel_map))

    # ── Internal helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Add gender_female, education_ord, pregnancy_status_bin."""
        out = df.copy()

        # gender_female
        if "gender" in out.columns:
            out["gender_female"] = (out["gender"] == "Female").astype(float)
        else:
            out["gender_female"] = np.nan

        # education_ord
        if "education" in out.columns:
            out["education_ord"] = out["education"].map(_EDU_ORDER)
        else:
            out["education_ord"] = np.nan

        # pregnancy_status_bin
        if "pregnancy_status" in out.columns:
            out["pregnancy_status_bin"] = (
                out["pregnancy_status"] == "Yes, pregnant"
            ).astype(float)
            out.loc[out["pregnancy_status"].isna(), "pregnancy_status_bin"] = np.nan
        else:
            out["pregnancy_status_bin"] = np.nan

        return out

    def _apply_sentinels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replace NHANES sentinel codes with NaN."""
        out = df.copy()
        for col, bad_codes in self._sentinel_map.items():
            if col in out.columns:
                out[col] = out[col].replace(bad_codes, np.nan)
        return out

    # ── Public API ──────────────────────────────────────────────────────────────

    def build_feature_vectors(
        self, raw_inputs: dict[str, Any]
    ) -> dict[str, pd.DataFrame]:
        """
        Normalize raw user inputs and slice per-model feature DataFrames.

        Parameters
        ----------
        raw_inputs : dict
            Flat dict of field_name → value as submitted by the user / frontend.
            String values for ``gender``, ``education``, ``pregnancy_status``
            must use the canonical NHANES text labels.

        Returns
        -------
        dict[str, pd.DataFrame]
            {condition: single-row DataFrame} for every registered model.
            Missing features are filled with NaN (the model's internal
            SimpleImputer handles these at inference time).
        """
        # Step 1 — single-row DataFrame, applying quiz field aliases first
        resolved: dict[str, Any] = {}
        for k, v in raw_inputs.items():
            if k in QUIZ_FIELD_ALIASES:
                target = QUIZ_FIELD_ALIASES[k]
                if target is None:
                    log.debug("Dropping deprecated quiz field '%s'", k)
                    continue           # silently drop removed fields
                log.debug("Remapping quiz field '%s' → '%s'", k, target)
                resolved[target] = v
            else:
                resolved[k] = v

        # Decode NHANES numeric codes to text labels expected by _add_derived_columns
        if "gender" in resolved and isinstance(resolved["gender"], (int, float)):
            resolved["gender"] = _GENDER_CODES.get(int(resolved["gender"]), resolved["gender"])
        if "education" in resolved and isinstance(resolved["education"], (int, float)):
            resolved["education"] = _EDU_CODES.get(int(resolved["education"]), resolved["education"])
        if "pregnancy_status" in resolved and isinstance(resolved["pregnancy_status"], (int, float)):
            resolved["pregnancy_status"] = _PREGNANCY_CODES.get(
                int(resolved["pregnancy_status"]), resolved["pregnancy_status"]
            )

        df = pd.DataFrame([resolved])

        # Step 2 — sentinel cleanup
        df = self._apply_sentinels(df)

        # Step 3 — normalize (reference intervals + z-score)
        df_norm = self._normalizer.transform(df)

        # Step 4 — derived columns
        df_norm = self._add_derived_columns(df_norm)

        # Step 5 — slice per-model feature vectors
        feature_vectors: dict[str, pd.DataFrame] = {}
        norm_row = df_norm.iloc[0]
        for condition, feats in self._model_features.items():
            row_dict = {f: norm_row.get(f, np.nan) for f in feats}
            feature_vectors[condition] = pd.DataFrame([row_dict])

        return feature_vectors


# ── ModelRunner ─────────────────────────────────────────────────────────────────

class ModelRunner:
    """
    Loads all v2 disease models on construction and scores inputs in parallel.

    Recommended usage via ``score_raw()`` which handles normalization
    automatically.  Lower-level ``score()`` / ``run_all_with_context()`` accept
    pre-built normalized feature vectors (useful for testing / notebooks).

    Parameters
    ----------
    models_dir : str or Path, optional
        Directory containing v2 .joblib and _metadata.json files.
        Defaults to the same directory as this module (models_normalized/).
    max_workers : int, optional
        ThreadPoolExecutor pool size.  None = Python default (CPU-based).

    Attributes
    ----------
    failed_models : list[str]
        Condition names whose .joblib files failed to load at startup.
    normalizer : InputNormalizer
        Normalization helper (loaded lazily on first call to score_raw()).
    """

    _NORMALIZER_PATH    = _ROOT / "models" / "nhanes_hybrid_normalizer.joblib"
    _SENTINEL_META_PATH = _ROOT / "data" / "processed" / "normalized" / "nhanes_ml_ready_metadata.json"

    def __init__(
        self,
        models_dir: str | Path = _DIR,
        max_workers: Optional[int] = None,
    ) -> None:
        import joblib

        self._models_dir  = Path(models_dir)
        self._max_workers = max_workers
        self._pipelines:  dict = {}
        self._normalizer: Optional[InputNormalizer] = None
        self.failed_models: list = []

        log.info("Loading %d disease models from %s", len(MODEL_REGISTRY), self._models_dir)

        for condition, filename in MODEL_REGISTRY.items():
            path = self._models_dir / filename
            try:
                self._pipelines[condition] = joblib.load(path)
                log.info("  OK  %-22s  %s", condition, filename)
            except FileNotFoundError:
                log.warning("  FAIL  %-22s  file not found: %s", condition, path)
                self.failed_models.append(condition)
            except Exception as exc:
                log.error("  FAIL  %-22s  load error: %s", condition, exc)
                self.failed_models.append(condition)

        log.info(
            "Loaded %d / %d models  (%d failed: %s)",
            len(self._pipelines), len(MODEL_REGISTRY),
            len(self.failed_models), self.failed_models or "none",
        )

    # ── Lazy normalizer ─────────────────────────────────────────────────────────

    def _get_normalizer(self) -> InputNormalizer:
        if self._normalizer is None:
            self._normalizer = InputNormalizer(
                models_dir        = self._models_dir,
                normalizer_path   = self._NORMALIZER_PATH,
                sentinel_meta_path = self._SENTINEL_META_PATH,
            )
        return self._normalizer

    # ── Eligibility gate ────────────────────────────────────────────────────────

    def _is_perimenopause_eligible(self, patient_context: dict[str, Any] | None) -> bool:
        """
        Returns True only if patient is confirmed female AND aged 35-55.
        Defaults to False when context is absent or incomplete.
        """
        if not patient_context:
            return False

        age    = patient_context.get("age_years")
        gender = patient_context.get("gender")

        if age is None or gender is None:
            return False

        try:
            age = float(age)
        except (TypeError, ValueError):
            return False

        if isinstance(gender, str):
            is_female = gender.strip().lower() == "female"
        else:
            is_female = (gender == 2)

        return is_female and 35.0 <= age <= 55.0

    # ── Core scoring ────────────────────────────────────────────────────────────

    def run_all_with_context(
        self,
        feature_vectors: dict[str, pd.DataFrame],
        patient_context: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """
        Score all loaded models in parallel using pre-built feature DataFrames.

        Hard gates
        ----------
        - ``perimenopause``: returns 0.0 for ineligible patients (not female 35-55).

        Parameters
        ----------
        feature_vectors : dict[str, pd.DataFrame]
            {condition: single-row DataFrame} with normalized values.
        patient_context : dict, optional
            Must contain at least ``{"gender": str, "age_years": float}``
            to unlock perimenopause for eligible patients.

        Returns
        -------
        dict[str, float]
            {condition: probability}.  Ineligible perimenopause → 0.0.
            Inference errors are omitted and logged at WARNING level.
        """
        results: dict[str, float] = {}

        def _score_one(condition: str) -> tuple[str, float | None]:
            # Perimenopause hard gate
            if condition == "perimenopause":
                if not self._is_perimenopause_eligible(patient_context):
                    log.info("perimenopause ineligible (not female 35-55) — returning 0.0")
                    return condition, 0.0

            if condition not in feature_vectors:
                log.warning("No feature vector for '%s' — skipping", condition)
                return condition, None

            X = feature_vectors[condition]
            try:
                pipeline = self._pipelines[condition]
                if isinstance(pipeline, dict) and "model" in pipeline:
                    pipeline = pipeline["model"]
                prob = float(pipeline.predict_proba(X)[:, 1][0])
                return condition, prob
            except Exception as exc:
                log.warning("Inference error for '%s': %s", condition, exc)
                return condition, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(_score_one, cond): cond for cond in self._pipelines}
            for future in concurrent.futures.as_completed(futures):
                condition, prob = future.result()
                if prob is not None:
                    results[condition] = round(prob, 4)

        return results

    def run_all(self, feature_vectors: dict[str, pd.DataFrame]) -> dict[str, float]:
        """Score without patient context (perimenopause returns 0.0)."""
        return self.run_all_with_context(feature_vectors, patient_context=None)

    # ── Ranking ─────────────────────────────────────────────────────────────────

    def filter_and_rank(
        self,
        scores: dict[str, float],
        top_n: int = 3,
    ) -> list[dict]:
        """
        Apply per-disease filtering criteria, rank descending, return top N.

        Each disease has its own minimum score (FILTER_CRITERIA) that reflects
        disease severity, confirmatory test cost, model precision, and flag rate.
        All 11 model scores are always computed before this step — filtering only
        controls which scores advance to Bayesian update / user display.

        Parameters
        ----------
        scores : dict[str, float]
            Raw output of run_all_with_context() — all 11 scores.
        top_n : int
            Maximum conditions to return (default 3).

        Returns
        -------
        list[dict]
            [{"condition": str,
              "probability": float,
              "filter_criterion": float,
              "recommended_threshold": float}, ...]
            Sorted descending by probability.  Empty list when no condition
            clears its per-disease criterion.
        """
        above = [
            {
                "condition":             cond,
                "probability":           prob,
                "filter_criterion":      FILTER_CRITERIA.get(cond, 0.35),
                "recommended_threshold": RECOMMENDED_THRESHOLDS.get(cond),
            }
            for cond, prob in scores.items()
            if prob >= FILTER_CRITERIA.get(cond, 0.35)
        ]
        return sorted(above, key=lambda x: x["probability"], reverse=True)[:top_n]

    # ── Public entry points ─────────────────────────────────────────────────────

    def score_raw(
        self,
        raw_inputs: dict[str, Any],
        patient_context: dict[str, Any] | None = None,
        top_n: int = 3,
    ) -> list[dict]:
        """
        **Primary production entry point.**

        Normalizes raw user inputs, scores all models, applies per-disease
        filtering criteria, returns ranked shortlist.

        Parameters
        ----------
        raw_inputs : dict
            Raw questionnaire + lab values as submitted by the user.
            Keys are NHANES column names (or frontend field IDs that map to them).
            ``gender`` must be ``"Male"`` or ``"Female"``.
            ``education`` must be one of the five canonical NHANES text labels.
            ``pregnancy_status`` must be ``"Yes, pregnant"`` or similar text.
        patient_context : dict, optional
            ``{"gender": str, "age_years": float}`` — used for the perimenopause
            eligibility check.  If omitted, inferred from raw_inputs automatically.
        top_n : int
            Maximum conditions to return (default 3).

        Returns
        -------
        list[dict]
            [{"condition": str, "probability": float,
              "recommended_threshold": float}, ...]
        """
        # Infer patient_context from raw_inputs if not supplied separately
        if patient_context is None:
            patient_context = {
                "gender":    raw_inputs.get("gender"),
                "age_years": raw_inputs.get("age_years"),
            }

        feature_vectors = self._get_normalizer().build_feature_vectors(raw_inputs)
        scores          = self.run_all_with_context(feature_vectors, patient_context)
        return self.filter_and_rank(scores, top_n=top_n)

    def score(
        self,
        feature_vectors: dict[str, pd.DataFrame],
        patient_context: dict[str, Any] | None = None,
        top_n: int = 3,
    ) -> list[dict]:
        """
        Score pre-built normalized feature vectors (advanced / testing use).

        For production use prefer ``score_raw()`` which handles normalization.
        """
        scores = self.run_all_with_context(feature_vectors, patient_context=patient_context)
        return self.filter_and_rank(scores, top_n=top_n)


# ── Standalone smoke-test ───────────────────────────────────────────────────────

if __name__ == "__main__":
    models_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    print("\n" + "=" * 65)
    print("  ModelRunner — smoke test")
    print("=" * 65)

    runner = ModelRunner(models_dir=models_dir)

    # ── Test A: all raw scores + per-disease filtering ───────────────────────
    print("\n-- All 11 scores (female 42, minimal input) --")
    raw_minimal = {"gender": "Female", "age_years": 42}
    norm   = runner._get_normalizer()
    fvecs  = norm.build_feature_vectors(raw_minimal)
    ctx_f42 = {"gender": "Female", "age_years": 42}
    all_scores = runner.run_all_with_context(fvecs, patient_context=ctx_f42)

    print(f"  {'Disease':<24}  {'Score':>7}  {'Filter':>7}  {'Pass?':>6}")
    print("  " + "-" * 52)
    for cond, prob in sorted(all_scores.items(), key=lambda x: x[1], reverse=True):
        criterion = FILTER_CRITERIA.get(cond, 0.35)
        passes    = "✓" if prob >= criterion else "·"
        print(f"  {cond:<24}  {prob:>7.4f}  {criterion:>7.2f}  {passes:>6}")

    print("\n-- filter_and_rank (per-disease criteria, top_n=3) --")
    shortlist = runner.filter_and_rank(all_scores, top_n=3)
    if shortlist:
        for rank, item in enumerate(shortlist, 1):
            print(f"  #{rank}  {item['condition']:<24}  p={item['probability']:.4f}"
                  f"  filter={item['filter_criterion']}  rec_thr={item['recommended_threshold']}")
    else:
        print("  No condition cleared its per-disease criterion.")

    # ── Test B: perimenopause eligibility checks ─────────────────────────────
    print("\n-- perimenopause eligibility --")
    no_ctx   = runner.run_all_with_context(fvecs, patient_context=None)
    male_ctx = runner.run_all_with_context(fvecs, patient_context={"gender": "Male",   "age_years": 42})
    f60_ctx  = runner.run_all_with_context(fvecs, patient_context={"gender": "Female", "age_years": 60})

    print(f"  no context            → {no_ctx.get('perimenopause')}  (expect 0.0)")
    print(f"  Male 42               → {male_ctx.get('perimenopause')}  (expect 0.0)")
    print(f"  Female 42             → {all_scores.get('perimenopause')}  (expect scored)")
    print(f"  Female 60 (too old)   → {f60_ctx.get('perimenopause')}  (expect 0.0)")

    if runner.failed_models:
        print(f"\nFailed to load: {runner.failed_models}")
