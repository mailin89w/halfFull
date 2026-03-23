"""
model_runner.py
---------------
Ticket 2 — ML pipeline: model runner.

Loads all 11 disease models on startup and scores caller-supplied feature
vectors in parallel, returning a ranked shortlist of flagged conditions.

Contract with Ticket 1 (feature engineering)
--------------------------------------------
Ticket 1 must produce a ``feature_vectors`` dict::

    {
        "anemia":         pd.DataFrame,   # 1 row, model's encoded feature cols
        "iron_deficiency": pd.DataFrame,
        ...
    }

Each DataFrame has exactly one row (the current patient) and columns that
match the downstream model's expected feature set.  The runner passes each
DataFrame directly to ``pipeline.predict_proba()`` — no further encoding
is performed here.

Until Ticket 1 is available, the ``__main__`` block provides a mock.

Usage
-----
    from models.model_runner import ModelRunner

    runner   = ModelRunner()                        # loads all 11 models once
    shortlist = runner.score(feature_vectors)       # full pipeline
    # → [{"condition": "anemia", "probability": 0.72}, ...]

    # or step by step:
    scores    = runner.run_all(feature_vectors)     # {condition: probability}
    shortlist = runner.filter_and_rank(scores)      # top-N above threshold
"""

import os
import logging
import warnings
import concurrent.futures
from typing import Optional

import pandas as pd

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("model_runner")

_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Registry ───────────────────────────────────────────────────────────────────

MODEL_REGISTRY = {
    "anemia":          "anemia_combined_lr.joblib",
    "iron_deficiency": "iron_deficiency_checkup_lr.joblib",
    "thyroid":         "thyroid_lr_l2_18feat.joblib",
    "kidney":          "kidney_lr_l2_routine_30feat.joblib",
    "sleep_disorder":  "sleep_disorder_compact_quiz_demo_med_screening_labs_threshold_04.joblib",
    "liver":           "liver_lr_l2_13feat.joblib",
    "prediabetes":     "prediabetes_focused_quiz_demo_med_screening_labs_threshold_045.joblib",
    "inflammation":    "inflammation_lr_l1_45feat.joblib",
    "electrolytes":    "electrolyte_imbalance_compact_quiz_demo_med_screening_labs_threshold_05.joblib",
    "hepatitis":       "hepatitis_rf_cal_33feat.joblib",
    "perimenopause":   "perimenopause_gradient_boosting.joblib",
}


# ── ModelRunner ────────────────────────────────────────────────────────────────

class ModelRunner:
    """
    Loads all disease models on construction and scores feature vectors in parallel.

    One broken or missing model file never crashes the runner — failures are
    caught per-model and logged individually at WARNING level.

    Parameters
    ----------
    models_dir : str, optional
        Directory containing .joblib files.  Defaults to the same directory
        as this module (models/).
    max_workers : int, optional
        ThreadPoolExecutor pool size.  Defaults to None (Python chooses based
        on CPU count).

    Attributes
    ----------
    failed_models : list[str]
        Condition names whose .joblib files failed to load at startup.
    """

    def __init__(self, models_dir: str = _DIR, max_workers: Optional[int] = None):
        import joblib

        self._models_dir = models_dir
        self._max_workers = max_workers
        self._pipelines: dict = {}
        self.failed_models: list = []

        log.info("Loading %d disease models from %s", len(MODEL_REGISTRY), models_dir)

        for condition, filename in MODEL_REGISTRY.items():
            path = os.path.join(models_dir, filename)
            try:
                self._pipelines[condition] = joblib.load(path)
                log.info("  OK  %-20s  %s", condition, filename)
            except FileNotFoundError:
                log.warning("  FAIL  %-20s  file not found: %s", condition, path)
                self.failed_models.append(condition)
            except Exception as exc:
                log.error("  FAIL  %-20s  load error: %s", condition, exc)
                self.failed_models.append(condition)

        log.info(
            "Loaded %d / %d models  (%d failed: %s)",
            len(self._pipelines),
            len(MODEL_REGISTRY),
            len(self.failed_models),
            self.failed_models or "none",
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def run_all(self, feature_vectors: dict) -> dict:
        """
        Score all loaded models in parallel using ThreadPoolExecutor.

        Parameters
        ----------
        feature_vectors : dict[str, pd.DataFrame]
            {condition: DataFrame} — one single-row DataFrame per condition.
            Columns must match that model's expected feature set (Ticket 1 output).
            Conditions absent from this dict are skipped with a WARNING log.

        Returns
        -------
        dict[str, float]
            {condition: probability} for every successfully scored model.
            Conditions that error during inference are omitted; a WARNING is logged
            for each failure so the caller can inspect partial results safely.
        """
        results: dict = {}

        def _score_one(condition: str) -> tuple:
            if condition not in feature_vectors:
                log.warning(
                    "No feature vector supplied for '%s' — skipping", condition
                )
                return condition, None
            X = feature_vectors[condition]
            try:
                pipeline = self._pipelines[condition]
                # Some rebuilt models are packaged as dicts with the estimator
                # stored under "model" plus metadata such as threshold/features.
                if isinstance(pipeline, dict) and "model" in pipeline:
                    pipeline = pipeline["model"]
                prob = float(
                    pipeline.predict_proba(X)[:, 1][0]
                )
                return condition, prob
            except Exception as exc:
                log.warning("Inference error for '%s': %s", condition, exc)
                return condition, None

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers
        ) as pool:
            futures = {
                pool.submit(_score_one, cond): cond
                for cond in self._pipelines   # only successfully loaded models
            }
            for future in concurrent.futures.as_completed(futures):
                condition, prob = future.result()
                if prob is not None:
                    results[condition] = round(prob, 4)

        return results

    def filter_and_rank(
        self,
        scores: dict,
        threshold: float = 0.35,
        top_n: int = 3,
    ) -> list:
        """
        Filter scores by threshold, rank descending, return top N.

        Parameters
        ----------
        scores : dict[str, float]
            Raw output of run_all().
        threshold : float
            Minimum probability to include a condition (default 0.35).
        top_n : int
            Maximum number of conditions to return (default 3).

        Returns
        -------
        list[dict]
            [{"condition": str, "probability": float}, ...] sorted descending.
            Empty list when no condition clears the threshold.
        """
        above = [
            {"condition": cond, "probability": prob}
            for cond, prob in scores.items()
            if prob >= threshold
        ]
        ranked = sorted(above, key=lambda x: x["probability"], reverse=True)
        return ranked[:top_n]

    def score(
        self,
        feature_vectors: dict,
        threshold: float = 0.35,
        top_n: int = 3,
    ) -> list:
        """
        Convenience method: run_all → filter_and_rank → return shortlist.

        Parameters
        ----------
        feature_vectors : dict[str, pd.DataFrame]
            {condition: DataFrame} — same input contract as run_all().
        threshold : float
            Passed to filter_and_rank() (default 0.35).
        top_n : int
            Passed to filter_and_rank() (default 3).

        Returns
        -------
        list[dict]
            [{"condition": str, "probability": float}, ...] top-N ranked shortlist.
        """
        scores = self.run_all(feature_vectors)
        return self.filter_and_rank(scores, threshold=threshold, top_n=top_n)


# ── Standalone mock (Ticket 1 not yet available) ───────────────────────────────

if __name__ == "__main__":
    # MOCK: replace with Ticket 1 output
    # -------------------------------------------------------------------------
    # Ticket 1 (feature engineering) will produce feature_vectors as a dict of
    # {condition: pd.DataFrame} — one single-row DataFrame per model with that
    # model's encoded feature columns already prepared.
    #
    # The feature sets below are taken directly from the corresponding model
    # modules.  Conditions whose feature columns are not yet documented here
    # receive a placeholder DataFrame — they will fail gracefully at inference
    # and log a WARNING, demonstrating the runner's per-model fault isolation.
    # -------------------------------------------------------------------------

    # Known feature sets — sourced from model module ENCODED_FEATURE_NAMES constants

    # anemia_combined_model.py — 18 features
    ANEMIA_FEATURES = [
        "total_cholesterol_mg_dl", "hdl_cholesterol_mg_dl", "ldl_cholesterol_mg_dl",
        "triglycerides_mg_dl", "fasting_glucose_mg_dl", "age_years", "gender_female", "bmi",
        "dpq040_tired_little_energy", "huq010_general_health", "cdq010_sob_stairs",
        "sld012_sleep_hours_weekday", "sld013_sleep_hours_weekend",
        "slq050_told_trouble_sleeping", "pad680_sedentary_minutes",
        "rhq031_regular_periods", "rhq060_age_last_period", "rhq540_ever_hormones",
    ]

    # iron_deficiency_checkup_model.py — 12 features (Group A excluded by design)
    IRON_DEF_FEATURES = [
        "total_cholesterol_mg_dl", "hdl_cholesterol_mg_dl", "ldl_cholesterol_mg_dl",
        "triglycerides_mg_dl", "fasting_glucose_mg_dl", "age_years", "gender_female",
        "sld013_sleep_hours_weekend", "slq050_told_trouble_sleeping",
        "rhq031_regular_periods", "rhq060_age_last_period", "rhq540_ever_hormones",
    ]

    # predict.py (ThyroidPredictor) — 18 base features (missingness flags added by pipeline)
    THYROID_FEATURES = [
        "age_years", "gender", "med_count", "avg_drinks_per_day",
        "general_health_condition", "doctor_said_overweight",
        "told_dr_trouble_sleeping", "tried_to_lose_weight", "avg_cigarettes_per_day",
        "weight_kg", "pregnancy_status", "moderate_recreational",
        "times_urinate_in_night", "overall_work_schedule", "ever_told_high_cholesterol",
        "ever_told_diabetes", "taking_anemia_treatment", "sleep_hours_weekdays",
    ]

    # MOCK: replace with Ticket 1 output
    feature_vectors = {
        # Fully documented — all-zero mock rows
        "anemia":          pd.DataFrame([{f: 0.0 for f in ANEMIA_FEATURES}]),
        "iron_deficiency": pd.DataFrame([{f: 0.0 for f in IRON_DEF_FEATURES}]),
        "thyroid":         pd.DataFrame([{f: 0.0 for f in THYROID_FEATURES}]),
        # Feature columns not yet documented — placeholder rows.
        # These will raise an inference error and log a WARNING (expected behaviour).
        # Replace with correct DataFrames once Ticket 1 is implemented.
        "kidney":         pd.DataFrame([{"placeholder": 0.0}]),
        "sleep_disorder": pd.DataFrame([{"placeholder": 0.0}]),
        "liver":          pd.DataFrame([{"placeholder": 0.0}]),
        "prediabetes":    pd.DataFrame([{"placeholder": 0.0}]),
        "inflammation":   pd.DataFrame([{"placeholder": 0.0}]),
        "electrolytes":   pd.DataFrame([{"placeholder": 0.0}]),
        "hepatitis":      pd.DataFrame([{"placeholder": 0.0}]),
        "perimenopause":  pd.DataFrame([{"placeholder": 0.0}]),
    }

    print("\n" + "=" * 60)
    print("  ModelRunner -- standalone mock")
    print("  (Ticket 1 not yet available; known models use all-zero inputs)")
    print("=" * 60)

    runner = ModelRunner()

    print("\n-- run_all() " + "-" * 47)
    all_scores = runner.run_all(feature_vectors)
    if all_scores:
        print("Raw scores (scored models only):")
        for cond, prob in sorted(all_scores.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cond:22s}  {prob:.4f}")
    else:
        print("  No models scored (all failed to load or infer).")

    print("\n-- filter_and_rank(threshold=0.35, top_n=3) " + "-" * 16)
    shortlist = runner.filter_and_rank(all_scores, threshold=0.35, top_n=3)
    if shortlist:
        print("Flagged conditions:")
        for rank, item in enumerate(shortlist, 1):
            print(f"  #{rank}  {item['condition']:22s}  p={item['probability']:.4f}")
    else:
        print("  No condition cleared the threshold.")
        print("  (Expected with all-zero mock inputs -- models are biased toward")
        print("   the negative class at the mean feature values.)")

    print("\n-- score() convenience method " + "-" * 30)
    result = runner.score(feature_vectors, threshold=0.35, top_n=3)
    print(f"Shortlist: {result}")

    if runner.failed_models:
        print(f"\nFailed to load: {runner.failed_models}")
        print("(Models not yet trained will be missing -- train them first.)")
