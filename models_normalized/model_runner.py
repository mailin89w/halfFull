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

# ── Registry — promoted production artifacts ───────────────────────────────────
#
# Keep promotion decisions explicit here rather than implicitly selecting the
# newest filename on disk. Several newer candidate artifacts exist, but they are
# only promoted after a cohort-level eval confirms the tradeoff is worth it.
#
# Fields:
#   artifact       model file loaded in production / evals
#   status         promoted | retained
#   decision_date  when the current choice was last reviewed
#   basis          short human-readable rationale
#   eval_report    cohort-level evidence when available
#   candidate_held newer artifact intentionally NOT promoted yet

MODEL_REGISTRY_AUDIT: dict[str, dict[str, str]] = {
    "anemia": {
        "artifact": "anemia_lr_symptom_bundle_v6.joblib",
        "status": "promoted",
        "decision_date": "2026-03-31",
        "ticket": "ML-ANEMIA-02",
        "basis": "Promoted for validation: v6 adds symptom-bundle features and lighter hard negatives to recover recall after the v5 bias fix.",
        "candidate_held": "anemia_lr_repro_hist_v5.joblib",
    },
    "electrolyte_imbalance": {
        "artifact": "electrolyte_imbalance_lr_deduped28_L2_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "No newer validated candidate artifact found locally.",
    },
    "kidney": {
        "artifact": "kidney_lr_deduped17_L2_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "ticket": "ML-KIDNEY-01",
        "basis": "Retained v2 after 760-cohort A/B showed v3 hard-neg cut recall too sharply despite lower flag rate.",
        "eval_report": "evals/reports/layer1_20260330_224345.md",
        "candidate_held": "kidney_lr_v3_hard_neg.joblib",
    },
    "liver": {
        "artifact": "liver_rf_cal_deduped19_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "No newer validated candidate artifact found locally.",
    },
    "prediabetes": {
        "artifact": "prediabetes_lr_deduped34_L2_C001_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "Kept v2 until xgb v3 hard-neg gets a clean 760-cohort validation pass.",
        "candidate_held": "prediabetes_xgb_v3_hard_neg.joblib",
    },
    "sleep_disorder": {
        "artifact": "sleep_disorder_lr_trimmed29_L2_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "No newer validated candidate artifact found locally.",
    },
    "thyroid": {
        "artifact": "thyroid_lr_l2_reduced-12feat_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "No newer validated candidate artifact found locally.",
    },
    "hidden_inflammation": {
        "artifact": "hidden_inflammation_lr_deduped26_L2_v3.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "Kept v3 until v4 hard-neg gets a clean 760-cohort validation pass.",
        "candidate_held": "hidden_inflammation_lr_v4_hard_neg.joblib",
    },
    "perimenopause": {
        "artifact": "perimenopause_lr_deduped21_L2_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "No newer validated candidate artifact found locally.",
    },
    "hepatitis_bc": {
        "artifact": "hepatitis_bc_rf_cal_deduped20_v2.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "No newer validated candidate artifact found locally.",
    },
    "iron_deficiency": {
        "artifact": "iron_deficiency_rf_cal_deduped35_v4.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "basis": "Current product-safe no-CBC model; no newer validated runtime-safe candidate artifact found locally.",
    },
    "vitamin_d_deficiency": {
        "artifact": "vitamin_d_deficiency_2017_2018_rf_cal_aligned.joblib",
        "status": "retained",
        "decision_date": "2026-03-31",
        "ticket": "ML-VITD-02",
        "basis": "Retained current aligned artifact, but tightened user-facing threshold to 0.48 after 760-cohort sweep to reduce healthy alerts and overall dominance.",
    },
}

MODEL_REGISTRY = {
    condition: audit["artifact"]
    for condition, audit in MODEL_REGISTRY_AUDIT.items()
}

# Per-model recommended operating thresholds
# (lowest t where OOF precision >= 17%, maximising recall — internal model property)
RECOMMENDED_THRESHOLDS = {
    "anemia":                0.40,
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
    "vitamin_d_deficiency":   0.40,
}

# Per-disease user-facing filtering criteria
# ─────────────────────────────────────────────────────────────────────────────
# A model score at or above this value is considered worth:
#   (a) surfacing in user recommendations.
#
# All models always run regardless of this value — it only controls which
# scores are elevated to the user-visible shortlist.
#
# Bayesian question triggering now uses a separate, lower threshold map so
# borderline-but-plausible conditions can still enter follow-up questions
# without automatically being surfaced to the user.
#
# Calibration rationale (severity × test cost × model precision × flag rate):
#   0.10  liver / hepatitis_bc  — serious diseases, cheap confirmatory tests,
#                                  low flag rate; borderline scores still warrant Bayesian update
#   0.20  iron_deficiency       — optional stricter cleanup from 2026-03-26 sweep
#   0.20  kidney                — serious; lower filter lets Bayesian work on
#                                  borderline CKD signals before surfacing
#   0.40  hidden_inflammation   — current 600-profile benchmark showed a clear
#                                  quick win at 0.40 vs 0.30: much lower flag burden
#                                  and healthy over-alert with only modest recall loss
#   0.40  anemia                — v6 symptom-bundle model: lower than v5's 0.60
#                                  to recover recall while still staying far below
#                                  the old spammy alert burden
#   0.35  prediabetes / thyroid — reversible / manageable; weakest models in group;
#                                  need reasonable confidence before surfacing
#   0.40  electrolyte_imbalance / perimenopause
#                               — weakest model (EI AUC 0.717) or high cohort base
#                                  rate (perimenopause 23%) → need clearer signal
#   0.75  sleep_disorder        — optional stricter cleanup from 2026-03-26 sweep;
#                                  (polysomnography); only surface strong signals
#   0.48  vitamin_d_deficiency   — raised from 0.40 on 2026-03-31 after
#                                  latest 760 sweep: first threshold that brought
#                                  healthy flag rate below 5%; recall cost remains
#                                  material, so keep Bayesian trigger lower
USER_FACING_THRESHOLDS = {
    "hepatitis_bc":          0.10,
    "liver":                 0.07,
    "iron_deficiency":       0.20,
    "kidney":                0.35,   # raised 0.25→0.35 on 2026-03-27 second-pass tightening: trade recall for materially lower user-facing alert burden
    "anemia":                0.40,   # v6 symptom-bundle model promoted 2026-03-31 to recover recall after bias fix; local 760 tests held healthy FP at 2%
    "hidden_inflammation":   0.40,   # raised 0.30→0.40 on 2026-03-26 quick-win sweep: precision 6.3%→8.2%, flag 55.3%→36.5%, recall 46.7%→40.0%
    "prediabetes":           0.45,   # raised 0.40→0.45 on 2026-03-27 second-pass tightening: high-recall yellow model still over-flagged
    "thyroid":               0.75,   # raised 0.60→0.75 on 2026-03-27: eval shows 5/12 healthy FP suppressed; tradeoff is 7/58 TP lost (85%→75% recall) — model produces 0.85-0.95 saturated scores that cannot be separated by threshold alone; proper fix is ML-02 recalibration
    "electrolyte_imbalance": 0.46,   # raised 0.40→0.46: flag 54%→34%, recall 40%→15%
    "perimenopause":         0.40,
    "sleep_disorder":        0.75,   # raised 0.70→0.75 on 2026-03-26 optional cleanup: precision 10.9%→13.1%, flag 24.5%→16.5%, recall 25.0%→20.3%
    "vitamin_d_deficiency":   0.48,
}

# Lower thresholds used only to decide which conditions enter Bayesian review.
# This keeps borderline cases alive for follow-up questions without forcing
# them into the user-facing shortlist.
BAYESIAN_TRIGGER_THRESHOLDS = {
    "hepatitis_bc":          0.10,
    "liver":                 0.10,
    "iron_deficiency":       0.15,
    "kidney":                0.25,
    "anemia":                0.35,
    "hidden_inflammation":   0.30,
    "prediabetes":           0.40,
    "thyroid":               0.50,
    "electrolyte_imbalance": 0.46,
    "perimenopause":         0.40,
    "sleep_disorder":        0.70,
    "vitamin_d_deficiency":   0.20,
}

# Backward-compatible alias: existing eval/report code expects FILTER_CRITERIA
# to mean the user-facing surfacing threshold.
FILTER_CRITERIA = USER_FACING_THRESHOLDS

# ── Score normalization for fair cross-model ranking ───────────────────────────
#
# Each model's raw probability operates in a different range.  iron_deficiency
# outputs 0.63–0.97 for ALL female profiles regardless of symptoms because 91%
# of training positives are women — a structural demographic bias baked into the
# RF model.  perimenopause max output is ~0.40, well below iron_deficiency's
# female floor of 0.63.  Ranking by raw probability makes iron_deficiency the
# perpetual #1 for every female profile even when the clinical signal is minimal.
#
# Fix: normalize each model's score to its empirically observed range before
# sorting so the rank reflects *where within its own distribution* a score sits,
# not its absolute value.  Raw probabilities are NEVER modified — they appear
# unchanged in all outputs and drive Bayesian update thresholds.  Normalization
# only changes sort order inside filter_and_rank().
#
# For iron_deficiency a sex-specific floor is used:
#   Female floor 0.630 → score 0.65 normalises to 0.06 (near-zero signal above floor)
#   Female floor 0.630 → score 0.90 normalises to 0.79 (genuinely strong signal)
#   Male   floor 0.150 → score 0.40 normalises to 0.31 (modest but real signal)
#
# Observed ranges come from the 600-profile validation cohort
# (evals/cohort/profiles.json, evals/score_profiles.py).
#
# Set RANK_NORMALIZE = False to revert to legacy raw-probability ordering.

RANK_NORMALIZE: bool = True

SCORE_RANGES: dict[str, tuple[float, float]] = {
    # (observed_max) only — used as the upper bound in mean-floor normalisation.
    # The floor is taken from SCORE_MEANS so the rank key measures how far
    # *above the population baseline* a score sits.
    # Observed across 600-profile eval cohort (evals/cohort/profiles.json).
    # v3 models (anemia, iron_deficiency, hidden_inflammation) re-calibrated 2026-03-23.
    # All other models re-calibrated 2026-03-26 (eval obs max/min updated for v3 pipeline).
    "anemia":                (0.025, 0.991),   # v3 — C=0.05, 38 feats
    "electrolyte_imbalance": (0.213, 0.740),   # updated: eval max was 0.690, obs max now 0.730
    "kidney":                (0.059, 0.925),   # updated: eval max was 0.882, obs max now 0.916
    "liver":                 (0.007, 0.553),
    "prediabetes":           (0.267, 0.820),   # updated: eval max was 0.758, obs max now 0.815
    "sleep_disorder":        (0.346, 0.995),
    "thyroid":               (0.078, 0.965),
    "hidden_inflammation":   (0.043, 0.750),   # v3 — 26 feats + bmi; max from eval (0.737)
    "perimenopause":         (0.000, 0.988),
    "hepatitis_bc":          (0.005, 0.524),
    "iron_deficiency":       (0.006, 0.451),   # v4 — 35 feats, no CBC markers (600-profile cohort: min 0.0056, max 0.4511)
    "vitamin_d_deficiency":   (0.000, 0.942),  # NHANES 2017-2018 aligned RF+cal model
}

# Population-mean score across ALL profiles (positive + negative + healthy).
# Used as the "no-signal baseline" in mean-floor normalisation:
#   rank_key = (score - mean) / (max - mean)
# This removes each model's inherent population baseline before cross-model
# comparison.  Models that fire broadly for demographic reasons
# (sleep_disorder mean=0.755, thyroid mean=0.643) are correctly de-weighted
# relative to models with lower baselines and higher discriminating power.
SCORE_MEANS: dict[str, float] = {
    "anemia":                0.498,   # v3 — eval cohort mean (600 profiles); was 0.478 v2
    "electrolyte_imbalance": 0.491,  # updated 2026-03-26: was 0.458
    "kidney":                0.426,  # updated 2026-03-26: was 0.380
    "liver":                 0.072,  # updated 2026-03-26: was 0.060
    "prediabetes":           0.557,  # updated 2026-03-26: was 0.523
    "sleep_disorder":        0.781,  # updated 2026-03-26: was 0.755; dominant — mean-floor correction critical
    "thyroid":               0.662,  # updated 2026-03-26: was 0.643; dominant — mean-floor correction critical
    "hidden_inflammation":   0.217,  # v3 — eval cohort mean; was 0.104 v2 (bmi raises NHANES baseline to 0.423 but eval mean is lower)
    "perimenopause":         0.306,  # updated 2026-03-26: was 0.297
    "hepatitis_bc":          0.044,
    "iron_deficiency":       0.082,  # v4 — 600-profile cohort mean (was 0.038 v3 with CBC features)
    "vitamin_d_deficiency":   0.283,  # NHANES 2017-2018 aligned RF+cal model mean score
}

# Sex-specific floors for iron_deficiency.
# In v2 the iron_deficiency RF model removed gender_female from its feature list,
# eliminating the v1 sex-bias floor (0.63 for all females).  Retained for
# forward-compatibility; the effect is negligible (v2 max is 0.155).
IRON_DEF_SEX_FLOORS: dict[str, float] = {
    # v3 — per-sex baseline from eval cohort (non-iron profiles only, 2026-03-23)
    # v2 was Female=0.010, Male=0.004 (v2 model max 0.155); v3 CBC features push range to 0.85
    "Female": 0.009,
    "Male":   0.006,
}

def rank_score(condition: str, prob: float, gender: str | None = None) -> float:
    """
    Compute a normalised ranking key for a single model score.

    Uses **mean-floor normalisation**::

        rank_key = (prob − population_mean) / (observed_max − population_mean)

    This maps each model's score to "how far above the population baseline is
    this score, relative to the maximum possible signal?"  Models that fire
    broadly across all demographics (sleep_disorder mean=0.755, thyroid
    mean=0.643) are correctly de-weighted when their score is only at baseline.

    For ``iron_deficiency`` a sex-specific floor replaces ``population_mean``
    to account for any residual demographic bias (minimal in v2 RF model).

    This value is ONLY used for sort ordering in ``filter_and_rank``.
    Raw probabilities are preserved in all output dicts.

    Parameters
    ----------
    condition : str
        Model registry key (e.g. ``"sleep_disorder"``).
    prob : float
        Raw model output probability (0–1).
    gender : str or None
        ``"Female"``, ``"Male"``, or ``None``.

    Returns
    -------
    float
        Mean-floor normalised rank score.  Negative values mean the score is
        below the population baseline (weak signal).  1.0 means at the observed
        maximum.  Returned value may exceed 1.0 for out-of-sample highs.
    """
    _lo, hi = SCORE_RANGES.get(condition, (0.0, 1.0))
    mean = SCORE_MEANS.get(condition, _lo)

    # Sex-specific iron_deficiency floor (replaces population mean as lower bound)
    if condition == "iron_deficiency" and gender in IRON_DEF_SEX_FLOORS:
        mean = IRON_DEF_SEX_FLOORS[gender]

    span = hi - mean
    return (prob - mean) / span if span > 0.0 else prob


def _gender_from_context(patient_context: dict | None) -> str | None:
    """Extract canonical gender string (``'Female'`` / ``'Male'``) from context."""
    if not patient_context:
        return None
    g = patient_context.get("gender")
    if g is None:
        return None
    if isinstance(g, str):
        label = g.strip().title()
        return label if label in ("Female", "Male") else None
    # NHANES numeric: 1=Male, 2=Female
    return {1: "Male", 2: "Female"}.get(int(g))


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
    # quiz education field → canonical name expected by _add_derived_columns
    "dmdeduc2":                        "education",
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
         - ``gender_female``        (float 0/1)
         - ``education_ord``        (int 0–4, NaN if unknown)
         - ``pregnancy_status_bin`` (float 0/1, NaN if question not answered)
         - anemia-specific symptom/reproductive bundle features
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
        """Add derived features consumed by the production model set."""
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

        # anemia symptom bundle: helps the newer anemia model reward the
        # combination of fatigue + shortness of breath + poor health burden,
        # rather than requiring a single dominant demographic shortcut.
        fat = out.get(
            "dpq040___feeling_tired_or_having_little_energy",
            pd.Series(0.0, index=out.index),
        ).fillna(0)
        sob = out.get(
            "cdq010___shortness_of_breath_on_stairs/inclines",
            pd.Series(9.0, index=out.index),
        ).fillna(9)
        health = out.get(
            "huq010___general_health_condition",
            pd.Series(3.0, index=out.index),
        ).fillna(3)
        hosp = out.get(
            "huq071___overnight_hospital_patient_in_last_year",
            pd.Series(2.0, index=out.index),
        ).fillna(2)
        reg_periods = out.get(
            "rhq031___had_regular_periods_in_past_12_months",
            pd.Series(9.0, index=out.index),
        ).fillna(9)
        preg_now = out.get(
            "rhd143___are_you_pregnant_now?",
            pd.Series(9.0, index=out.index),
        ).fillna(9)

        out["anemia_symptom_burden"] = (
            (fat >= 1).astype(float)
            + (sob <= 2).astype(float)
            + (health >= 3).astype(float)
            + (hosp == 1).astype(float)
        )
        out["fatigue_sob_combo"] = ((fat >= 1) & (sob <= 2)).astype(float)
        out["female_repro_signal"] = ((reg_periods == 1) | (preg_now == 1)).astype(float)

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
        skip_conditions: set[str] | None = None,
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
            # Skip models for conditions the user already confirmed
            if skip_conditions and condition in skip_conditions:
                log.info("Skipping '%s' — already confirmed by user", condition)
                return condition, None

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

        results = self._apply_post_score_gates(results, feature_vectors, patient_context)
        return results

    # ── Post-score gates ─────────────────────────────────────────────────────────

    @staticmethod
    def _apply_post_score_gates(
        scores: dict[str, float],
        feature_vectors: dict[str, pd.DataFrame],
        patient_context: dict[str, Any] | None,
    ) -> dict[str, float]:
        """
        Apply rule-based adjustments to raw model probabilities after scoring.

        Each gate is independent: a missing value for any required column causes
        that gate to be skipped (conservative — no spurious downweighting).
        Raw probabilities are modified in-place on the shallow copy; the original
        caller dict is never mutated.

        Iron-deficiency demographic gates
        ------------------------------
        The iron_deficiency model has strong gender_female signal from the NHANES
        training data (menstrual blood loss is the primary iron-loss mechanism in
        women).  This causes it to score high for *all* female profiles, often
        displacing the true top-1 for other female-skewed conditions.

        Gate: if female AND age > 45 AND regular_periods == No (encoded 2.0),
        the main menstrual blood-loss pathway is not active.  Downweight ×0.4.
        NaN for regular_periods (question not answered / male) → gate not applied.

        A second cleanup gate handles the remaining low-confidence male alerts.
        In the 760-profile benchmark, most residual healthy false positives after
        the menstrual gate are male, while true iron-deficiency positives remain
        overwhelmingly female.  Male iron deficiency is clinically real but much
        rarer, so low-confidence male scores should not surface without stronger
        evidence.  Gate: if male AND score < 0.30, downweight ×0.25.

        Prediabetes gate
        ----------------
        Prediabetes is driven by insulin resistance, which correlates strongly
        with BMI, fasting glucose, and family history.  In lean users (BMI < 23)
        with normal fasting glucose (< 95 mg/dL) and no first-degree relative
        with diabetes, risk is very low even when non-specific symptoms overlap
        with other conditions.  Downweight ×0.3.

        Thyroid gate
        ------------
        Thyroid disorders are uncommon before age 25 and typically present with
        fatigue as a cardinal symptom.  Young users (age < 25) without meaningful
        fatigue (dpq040 < 2 on the PHQ-4 energy item, scored 0–3) are very
        unlikely to have a clinically significant thyroid disorder.  Downweight ×0.4.

        Electrolyte gate
        ----------------
        Electrolyte imbalance in ambulatory adults is most commonly driven by GI
        losses (vomiting / diarrhoea), extreme physical exertion, or severe
        malnutrition.  When GI urgency symptoms are absent (kiq044 ≠ 1), BMI is
        in a healthy range (> 18), and the user reports no vigorous recreational
        activity (paq650 ≠ 1), the risk profile is low.  Downweight ×0.3.
        """
        scores = dict(scores)  # shallow copy — do not mutate caller's dict
        ctx = patient_context or {}

        # Helper: read a scalar from the first feature vector that contains the
        # column.  Returns None when the column is absent or the value is NaN.
        # All feature vectors are built from the same raw inputs, so any vector
        # that carries the column will return the same value.
        def _fv(col: str) -> float | None:
            for df in feature_vectors.values():
                if col in df.columns:
                    v = df[col].iloc[0]
                    if pd.notna(v):
                        return float(v)
            return None

        # ── Iron-deficiency menstrual gate ──────────────────────────────────────
        if "iron_deficiency" in scores:
            female = str(ctx.get("gender", "")).lower() == "female"
            male   = str(ctx.get("gender", "")).lower() == "male"
            age    = float(ctx.get("age_years", 0) or 0)
            if female and age > 45:
                # Read rhq031 from patient_context (threaded in by score_raw from
                # raw_inputs). Raw NHANES encoding: 1 = yes (regular), 2 = no.
                # None / NaN = not answered → gate not applied (unknown ≠ no).
                rhq031_raw = ctx.get("rhq031_regular_periods_raw")
                if rhq031_raw is not None:
                    try:
                        rhq031_val: float | None = float(rhq031_raw)
                        # Gate fires only when periods explicitly answered No (code 2)
                        if rhq031_val == 2.0:
                            original = scores["iron_deficiency"]
                            scores["iron_deficiency"] = round(original * 0.4, 4)
                            log.debug(
                                "iron_deficiency menstrual gate applied (female, age=%.0f, "
                                "no regular periods): %.4f → %.4f",
                                age, original, scores["iron_deficiency"],
                            )
                    except (TypeError, ValueError):
                        pass

            if male:
                original = scores["iron_deficiency"]
                if original < 0.30:
                    scores["iron_deficiency"] = round(original * 0.25, 4)
                    log.debug(
                        "iron_deficiency male cleanup gate applied (score < 0.30): "
                        "%.4f → %.4f",
                        original, scores["iron_deficiency"],
                    )

        # ── Prediabetes gate ────────────────────────────────────────────────────
        # Only suppress for users who are both very lean (BMI < 21) AND have
        # clearly normal fasting glucose (< 85 mg/dL) — a small, low-risk subset
        # where insulin resistance is very unlikely.  Single missing value skips.
        # Raw values are read from patient_context (threaded in by score_raw)
        # because the normalizer z-scores these columns in feature_vectors,
        # making clinical-unit threshold comparisons impossible there.
        if "prediabetes" in scores:
            try:
                raw_bmi = float(ctx.get("raw_bmi") or 0) or None
            except (TypeError, ValueError):
                raw_bmi = None
            try:
                raw_glucose = float(ctx.get("raw_fasting_glucose") or 0) or None
            except (TypeError, ValueError):
                raw_glucose = None
            if raw_bmi is not None and raw_bmi < 21.0 and raw_glucose is not None and raw_glucose < 85.0:
                original = scores["prediabetes"]
                scores["prediabetes"] = round(original * 0.5, 4)
                log.debug(
                    "prediabetes gate applied (raw_bmi=%.1f, raw_glucose=%.1f): %.4f → %.4f",
                    raw_bmi, raw_glucose, original, scores["prediabetes"],
                )

        # ── Thyroid gate ────────────────────────────────────────────────────────
        # Young age + absent fatigue makes clinically significant thyroid disease
        # very unlikely.  dpq040 is PHQ-4 item "feeling tired or having little
        # energy" (0 = not at all, 1 = several days, 2 = more than half the days,
        # 3 = nearly every day).  Values < 2 indicate absent/mild fatigue only.
        if "thyroid" in scores:
            age    = float(ctx.get("age_years", 0) or 0)
            dpq040 = _fv("dpq040___feeling_tired_or_having_little_energy")
            if age < 25.0 and dpq040 is not None and dpq040 < 2.0:
                original = scores["thyroid"]
                scores["thyroid"] = round(original * 0.4, 4)
                log.debug(
                    "thyroid gate applied (age=%.0f, dpq040=%.1f): %.4f → %.4f",
                    age, dpq040, original, scores["thyroid"],
                )

        # ── Electrolyte gate ────────────────────────────────────────────────────
        # Only suppress borderline electrolyte scores for users who explicitly
        # answered "no" to urinary/GI urgency (kiq044 == 2.0, NHANES code 2=No).
        # The score < 0.35 guard ensures high-confidence positives are never
        # suppressed — only profiles below the FILTER_CRITERIA threshold are
        # affected.  kiq044 is a raw NHANES code (not normalised by the pipeline).
        if "electrolyte_imbalance" in scores:
            kiq044 = _fv("kiq044___urinated_before_reaching_the_toilet?")
            elec_score = scores["electrolyte_imbalance"]
            if kiq044 is not None and kiq044 == 2.0 and elec_score < 0.35:
                scores["electrolyte_imbalance"] = round(elec_score * 0.3, 4)
                log.debug(
                    "electrolyte gate applied (kiq044=%.0f, score=%.4f): %.4f → %.4f",
                    kiq044, elec_score, elec_score, scores["electrolyte_imbalance"],
                )

        return scores

    def run_all(self, feature_vectors: dict[str, pd.DataFrame]) -> dict[str, float]:
        """Score without patient context (perimenopause returns 0.0)."""
        return self.run_all_with_context(feature_vectors, patient_context=None)

    # ── Ranking ─────────────────────────────────────────────────────────────────

    def filter_and_rank(
        self,
        scores: dict[str, float],
        top_n: int = 3,
        patient_context: dict[str, Any] | None = None,
    ) -> list[dict]:
        """
        Apply per-disease user-facing filtering criteria, rank descending, return top N.

        Each disease has its own minimum score (USER_FACING_THRESHOLDS / FILTER_CRITERIA) that reflects
        disease severity, confirmatory test cost, model precision, and flag rate.
        All 11 model scores are always computed before this step — filtering only
        controls which scores advance to the user-visible shortlist. Bayesian
        question triggering uses BAYESIAN_TRIGGER_THRESHOLDS separately.

        When ``RANK_NORMALIZE`` is ``True`` (default), sorting uses a per-model
        normalised rank key rather than the raw probability.  This corrects for
        iron_deficiency's structural sex bias (0.63–0.97 floor for all females)
        which would otherwise block every other condition from ranking first on
        female profiles.  Raw ``probability`` values in the returned dicts are
        never modified.

        Parameters
        ----------
        scores : dict[str, float]
            Raw output of run_all_with_context() — all 11 scores.
        top_n : int
            Maximum conditions to return (default 3).
        patient_context : dict, optional
            ``{"gender": str, "age_years": float}`` — used to apply sex-specific
            floor for iron_deficiency normalisation.

        Returns
        -------
        list[dict]
            [{"condition": str,
              "probability": float,
              "rank_score": float,
              "filter_criterion": float,
              "recommended_threshold": float}, ...]
            Sorted descending by rank_score (normalised) or probability (legacy).
            Empty list when no condition clears its per-disease criterion.
        """
        gender = _gender_from_context(patient_context)

        above = []
        for cond, prob in scores.items():
            if prob < FILTER_CRITERIA.get(cond, 0.35):
                continue
            rs = rank_score(cond, prob, gender) if RANK_NORMALIZE else prob
            above.append({
                "condition":             cond,
                "probability":           prob,
                "rank_score":            round(rs, 4),
                "filter_criterion":      FILTER_CRITERIA.get(cond, 0.35),
                "recommended_threshold": RECOMMENDED_THRESHOLDS.get(cond),
            })

        return sorted(above, key=lambda x: x["rank_score"], reverse=True)[:top_n]

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

        # Thread raw values that gates need but cannot read from feature vectors
        # (the normalizer z-scores continuous measurements, making threshold
        # comparisons in raw clinical units impossible from feature_vectors).
        patient_context = dict(patient_context)  # don't mutate caller's dict
        patient_context["rhq031_regular_periods_raw"] = raw_inputs.get(
            "rhq031___had_regular_periods_in_past_12_months"
        )
        patient_context["raw_bmi"] = raw_inputs.get("bmi")
        patient_context["raw_fasting_glucose"] = raw_inputs.get("fasting_glucose_mg_dl")

        feature_vectors = self._get_normalizer().build_feature_vectors(raw_inputs)
        scores          = self.run_all_with_context(feature_vectors, patient_context)
        return self.filter_and_rank(scores, top_n=top_n, patient_context=patient_context)

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
        return self.filter_and_rank(scores, top_n=top_n, patient_context=patient_context)


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
