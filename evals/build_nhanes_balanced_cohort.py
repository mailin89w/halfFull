#!/usr/bin/env python3
"""
build_nhanes_balanced_cohort.py

Builds a balanced 650-profile benchmark cohort from the pre-computed
NHANES 2003-2006 CSV (data/processed/nhanes_2003_2006_real_cohort.csv).

Key differences from the raw build script:
  - Vitamin D deficiency threshold tightened: < 50 → < 30 nmol/L
    (aligns with clinical "deficiency" vs the looser "insufficiency" cut)
  - Healthy profiles (0 conditions) are included and sampled
  - Output is balanced: up to TARGET_PER_CONDITION per condition,
    TARGET_HEALTHY healthy profiles, seed-stable

Output: evals/cohort/nhanes_balanced_650.json   (~650 profiles)
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

EVALS_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import helpers that build Bayesian answers from the CSV row
from scripts.build_real_nhanes_2003_2006_cohort import (
    EVAL_CONDITION_LABELS,
    derive_activity_level,
    derive_smoking_status,
    fill_bayesian_answers,
    symptom_vector_from_row,  # still needed to generate bayesian_answers at build time
)

CSV_PATH    = PROJECT_ROOT / "data" / "processed" / "nhanes_2003_2006_real_cohort.csv"
OUTPUT_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_650.json"

# ── Sampling targets ──────────────────────────────────────────────────────────
TARGET_PER_CONDITION = 55   # per-condition cap (some rare conds have < 55)
TARGET_HEALTHY       = 100  # profiles with 0 conditions
SEED                 = 42

# ── Vitamin D threshold (tightened from the raw build's < 50) ─────────────────
VITD_THRESHOLD_NMOL_L = 30.0   # clinical "deficiency" — < 30 nmol/L = < 12 ng/mL

# Condition-to-canonical-id, inheriting from build script but adding vitamin_d
CONDITION_MAP: dict[str, str] = {
    "anemia":                    "anemia",
    "thyroid":                   "hypothyroidism",
    "sleep_disorder":            "sleep_disorder",
    "kidney":                    "kidney_disease",
    "hepatitis_bc":              "hepatitis",
    "liver":                     "liver",
    "menopause":                 "perimenopause",   # same thing
    "iron_deficiency":           "iron_deficiency",
    "electrolyte_imbalance":     "electrolyte_imbalance",
    "hidden_inflammation":       "inflammation",
    "prediabetes":               "prediabetes",
    "perimenopause_proxy_probable": "perimenopause",
    # vitamin_d re-evaluated below with tighter threshold
}

SMOKING_MAP: dict[str, str] = {
    "never":      "never",
    "not_at_all": "never",
    "former":     "former",
    "current":    "current",
    "daily":      "current",
    "some_days":  "current",
    "unknown":    "unknown",
}

# ── SLQ_D sleep hours: load once at module level ─────────────────────────────
# SLD010H = total hours of sleep on weekday nights (cycle D only; not in processed CSV)
_SLQ_D_PATH = PROJECT_ROOT / "data" / "raw" / "nhanes_2003_2006" / "D" / "questionnaire" / "SLQ_D.XPT"
_SLQ_HOURS: dict[int, float] = {}
try:
    _slq_d = pd.read_sas(str(_SLQ_D_PATH), format="xport")
    for _, r in _slq_d.iterrows():
        seqn = int(r["SEQN"])
        h = r.get("SLD010H")
        if pd.notna(h) and 2 <= float(h) <= 14:
            _SLQ_HOURS[seqn] = float(h)
except Exception:
    pass   # if file missing, imputation falls back to condition-based estimate


# ── Deterministic noise helper ────────────────────────────────────────────────
def _unit_noise(seqn: int, key: str) -> float:
    """Stable pseudo-random float in [0, 1] keyed by (seqn, key). Same as synthetic_answer_sampler."""
    digest = hashlib.sha256(f"{seqn}:{key}".encode()).hexdigest()
    return int(digest[:12], 16) / float(16 ** 12 - 1)


# ── Feature imputation helpers ────────────────────────────────────────────────
def _impute_phq(row: pd.Series, seqn: int) -> dict[str, float]:
    """
    Impute PHQ-9 items when null (cycle C 100% missing; cycle D ~53% missing).
    Estimates are condition-aware: a person with anemia will score higher on
    fatigue than a healthy person. Bounded noise keeps values on the 0–3 ordinal
    scale without making them perfectly predictable from condition flags alone.
    """
    anemia  = float(_num(row, "anemia") or 0.0)
    thyroid = float(_num(row, "thyroid") or 0.0)
    sleep_d = float(_num(row, "sleep_disorder") or 0.0)
    inflam  = float(_num(row, "hidden_inflammation") or 0.0)
    kidney  = float(_num(row, "kidney") or 0.0)
    iron    = float(_num(row, "iron_deficiency") or 0.0)
    peri    = float(max(_num(row, "perimenopause_proxy_probable") or 0.0,
                        _num(row, "menopause") or 0.0))
    huq     = float(_num(row, "huq010_general_health") or 3.0)
    health_burden = (huq - 1.0) / 4.0   # 0 = excellent, 1 = poor

    def jitter(key: str, spread: float = 0.8) -> float:
        return (_unit_noise(seqn, f"phq_{key}") - 0.5) * spread

    # dpq040: tiredness / little energy
    dpq040 = round(max(0.0, min(3.0,
        0.2 + 1.2 * anemia + 0.9 * thyroid + 0.8 * sleep_d
        + 0.6 * inflam + 0.4 * kidney + 0.3 * iron
        + 0.4 * health_burden + jitter("040"))), 1)

    # dpq010: anhedonia / dpq020: depressed mood
    mood_signal = 0.1 + 0.8 * sleep_d + 0.5 * peri + 0.4 * thyroid + 0.5 * health_burden
    dpq010 = round(max(0.0, min(3.0, mood_signal + jitter("010"))), 1)
    dpq020 = round(max(0.0, min(3.0, mood_signal * 0.9 + jitter("020"))), 1)

    # dpq030: trouble sleeping (PHQ-9 item, not same as SLQ direct measure)
    dpq030 = round(max(0.0, min(3.0,
        0.1 + 1.4 * sleep_d + 0.6 * peri + 0.3 * inflam
        + 0.3 * health_burden + jitter("030"))), 1)

    # dpq070: concentration difficulty
    dpq070 = round(max(0.0, min(3.0,
        0.1 + 0.8 * sleep_d + 0.7 * thyroid + 0.4 * anemia
        + 0.3 * iron + 0.3 * health_burden + jitter("070"))), 1)

    return {
        "dpq040_fatigue":        dpq040,
        "dpq010_anhedonia":      dpq010,
        "dpq020_depressed":      dpq020,
        "dpq030_sleep":          dpq030,
        "dpq070_concentration":  dpq070,
    }


def _impute_slq(row: pd.Series, seqn: int, bmi: float, sex_f: bool) -> dict[str, float]:
    """
    Fill SLQ (sleep questionnaire) items when null.

    For cycle D participants measured in SLQ_D.XPT, real sleep hours (SLD010H)
    are used directly.  For cycle C or unmeasured cycle D participants, sleep
    hours are estimated from condition flags + age.  Snoring / stop-breathing /
    sleep-trouble-doctor are estimated from sleep_disorder flag + BMI + sex.
    """
    sleep_d = float(_num(row, "sleep_disorder") or 0.0)
    age     = float(_num(row, "age_years") or 45.0)

    def jitter(key: str, spread: float = 0.6) -> float:
        return (_unit_noise(seqn, f"slq_{key}") - 0.5) * spread

    # slq030: snoring (NHANES scale: 0=never, 1=rarely, 2=sometimes, 3=frequently/always)
    snore_signal = (0.1 + 1.8 * sleep_d
                    + 0.7 * (1.0 if bmi >= 30 else 0.4 if bmi >= 27 else 0.0)
                    + 0.4 * (0.0 if sex_f else 1.0))
    slq030 = round(max(0.0, min(3.0, snore_signal + jitter("030", 0.6))), 1)

    # slq040: stop breathing (same 0-3 scale; rarer than snoring)
    apnea_signal = 0.05 + 1.3 * sleep_d + 0.5 * (1.0 if bmi >= 30 else 0.0)
    slq040 = round(max(0.0, min(3.0, apnea_signal + jitter("040", 0.5))), 1)

    # slq050: ever told doctor about sleep trouble (1=yes, 2=no)
    doc_prob = min(0.90, max(0.03, 0.05 + 0.65 * sleep_d + 0.15 * (1.0 if bmi >= 30 else 0.0)))
    slq050 = 1.0 if _unit_noise(seqn, "slq050_doc") < doc_prob else 2.0

    # sleep hours: real SLQ_D value if available, otherwise impute
    real_hours = _SLQ_HOURS.get(seqn)
    if real_hours is not None:
        sld012 = real_hours
        sld013 = round(min(11.0, real_hours + 0.5 + _unit_noise(seqn, "sld013") * 0.8), 1)
    else:
        base_h = 7.0 - 0.8 * sleep_d - 0.01 * max(0, age - 50)
        sld012 = round(max(4.0, min(10.0, base_h + jitter("sld012", 0.9))), 1)
        sld013 = round(min(11.0, sld012 + 0.5 + _unit_noise(seqn, "sld013") * 0.8), 1)

    return {
        "slq030_snore_freq":           slq030,
        "slq040_stop_breathing_freq":  slq040,
        "slq050_sleep_trouble_doctor": slq050,
        "sld012_sleep_hours_weekday":  sld012,
        "sld013_sleep_hours_weekend":  sld013,
    }


def get_conditions(row: pd.Series) -> list[str]:
    """Return canonical condition IDs for a CSV row using tightened vitamin D threshold."""
    found: list[str] = []
    seen: set[str] = set()

    for csv_col, canon_id in CONDITION_MAP.items():
        val = row.get(csv_col)
        if pd.notna(val) and float(val) >= 0.5 and canon_id not in seen:
            found.append(canon_id)
            seen.add(canon_id)

    # Vitamin D — re-evaluate with tight threshold
    vd = row.get("vitamin_d_25oh_nmol_l")
    if pd.notna(vd) and float(vd) < VITD_THRESHOLD_NMOL_L:
        canon = "vitamin_d_deficiency"
        if canon not in seen:
            found.append(canon)

    return found


def _nhanes_inputs(row: pd.Series, activity: str, smoking_raw: str) -> dict[str, Any]:
    """
    Build the quiz-feature dict for a profile.

    Priority order for each field:
      1. Real NHANES value if measured and non-null
      2. Condition-aware imputation with bounded noise (for PHQ-9 / SLQ items
         that were not administered to this participant)
      3. Population-neutral default (for features not in NHANES 2003-2006 at all)

    PHQ-9 items (dpq040, dpq010, dpq020, dpq030, dpq070): null for 100% of
    cycle C and ~53% of cycle D — imputed from condition flags + general health.

    SLQ items (slq030, slq040, slq050): null for 100% of cycle C and ~41% of
    cycle D — imputed from sleep_disorder flag + BMI + sex.
    Sleep hours (sld012): real SLD010H from SLQ_D.XPT where available,
    otherwise imputed from condition flags + age.
    """
    seqn  = int(row["SEQN"]) if pd.notna(row.get("SEQN")) else 0
    bmi   = _num(row, "bmi") or 27.0
    sex_f = str(row.get("gender", "")).lower() in ("female", "f")

    bpx_sy = [_num(row, f"BPXSY{i}") for i in (1, 2, 3)]
    bpx_di = [_num(row, f"BPXDI{i}") for i in (1, 2, 3)]
    sbp = round(sum(v for v in bpx_sy if v) / max(sum(1 for v in bpx_sy if v), 1), 1) if any(bpx_sy) else 118.0
    dbp = round(sum(v for v in bpx_di if v) / max(sum(1 for v in bpx_di if v), 1), 1) if any(bpx_di) else 74.0

    # ── PHQ-9: use real value if present, impute if null ─────────────────────
    phq_real = {
        "dpq040_fatigue":        _num(row, "dpq040_fatigue"),
        "dpq010_anhedonia":      _num(row, "dpq010_anhedonia"),
        "dpq020_depressed":      _num(row, "dpq020_depressed"),
        "dpq030_sleep":          _num(row, "dpq030_sleep"),
        "dpq070_concentration":  _num(row, "dpq070_concentration"),
    }
    phq_imp = _impute_phq(row, seqn)
    phq = {k: (v if v is not None else phq_imp[k]) for k, v in phq_real.items()}

    # ── SLQ: use real value if present and valid, impute if null/refused ────────
    # NHANES codes 7 (refused) and 9 (don't know) are treated as missing.
    # Values ≈ 0 (represented as ~5.4e-79 in the XPT float encoding) are valid = "never".
    def _slq_valid(col: str) -> float | None:
        v = _num(row, col)
        if v is None:
            return None
        if v >= 7.0:    # refused (7) or don't know (9)
            return None
        return round(v, 1)   # keeps the ~0 values as 0.0

    slq_real = {
        "slq030_snore_freq":           _slq_valid("slq030_snore_freq"),
        "slq040_stop_breathing_freq":  _slq_valid("slq040_stop_breathing_freq"),
        "slq050_sleep_trouble_doctor": _slq_valid("slq050_sleep_trouble_doctor"),
        "sld012_sleep_hours_weekday":  None,   # not in processed CSV — always from SLQ_D or imputed
        "sld013_sleep_hours_weekend":  None,
    }
    slq_imp = _impute_slq(row, seqn, bmi, sex_f)
    slq = {k: (v if v is not None else slq_imp[k]) for k, v in slq_real.items()}

    # Sedentary minutes: PAD680 was not collected in 2003-2006 NHANES.
    # Estimate from activity_level so it's at least directionally consistent.
    _act_to_sed = {"sedentary": 540, "low": 360, "moderate": 240, "high": 120, "unknown": 300}
    pad680 = _act_to_sed.get(activity, 300) + int((_unit_noise(seqn, "pad680") - 0.5) * 120)

    chol = _num(row, "total_cholesterol_mg_dl") or 185.8
    hdl = _num(row, "hdl_cholesterol_mg_dl") or 53.0
    ldl = _num(row, "ldl_cholesterol_mg_dl") or 110.0
    trig = _num(row, "triglycerides_mg_dl") or 108.0
    gluc = _num(row, "fasting_glucose_mg_dl") or 100.0
    uacr = _num(row, "uacr_mg_g") or 5.0
    wbc = _num(row, "wbc_1000_cells_ul") or 7.0
    total_protein = _num(row, "total_protein_g_dl") or 7.0

    smq040 = _num(row, "smq040_smoke_now") or 3.0
    huq071 = _num(row, "huq071_hospital") or 2.0
    whq070 = _num(row, "whq070_tried_to_lose_weight") or 2.0
    bpq080 = _num(row, "bpq080_high_cholesterol") or 2.0
    diq050 = _num(row, "diq050_insulin") or 2.0
    diq070 = _num(row, "diq070_diabetes_pills") or 2.0
    mcq080 = _num(row, "mcq080_overweight_dx") or 2.0
    mcq160b = _num(row, "mcq160b_heart_failure") or 2.0
    mcq300c = _num(row, "mcq300c_family_diabetes") or 2.0
    kiq005 = _num(row, "kiq005_urinary_leakage_freq") or 0.0
    kiq042 = _num(row, "kiq042_leak_exertion") or 2.0
    kiq044 = _num(row, "kiq044_urge_incontinence") or 2.0
    ocq180 = _num(row, "ocq180_hours_worked_week") or 40.0
    rhq131 = _num(row, "rhq131_ever_pregnant") or 2.0
    rhq540 = _num(row, "rhq540_hormone_use") or 2.0
    rhq060 = _num(row, "rhq060_age_last_period") or 0.0
    rhq031 = _num(row, "rhq031_regular_periods") or 2.0
    pregnant_now = _num(row, "rhd143_pregnant_now")
    preg_code = _num(row, "pregnancy_status_code")

    current_smoker = 1.0 if smoking_raw == "current" else 2.0
    smoked_100 = 1.0 if smoking_raw in {"current", "former"} else 2.0
    cigs_day = 10.0 if smoking_raw == "current" else 0.0
    ever_drank = _num(row, "ALQ110") or (1.0 if (_num(row, "alq130_avg_drinks_per_day") or 0.0) > 0 else 2.0)
    heavy_daily_cutoff = 4.0 if sex_f else 5.0
    heavy_daily = 1.0 if (_num(row, "alq130_avg_drinks_per_day") or 0.0) >= heavy_daily_cutoff else 2.0
    education_code = _num(row, "education_code")
    education_ord = {1.0: 0.0, 2.0: 1.0, 3.0: 2.0, 4.0: 3.0, 5.0: 4.0}.get(education_code, 2.0)
    pregnancy_status_bin = 1.0 if (preg_code == 1.0 or pregnant_now == 1.0) else 0.0
    pain = 2.0
    saw_dr_for_pain = 1.0 if pain == 1.0 else 2.0
    kiq430 = 2.0 if kiq042 == 1.0 else 0.0
    kiq450 = 2.0 if kiq044 == 1.0 else 0.0
    kiq010 = 1.0 if kiq005 > 0 else 0.0
    kiq052 = 1.0 if kiq005 > 0 else 0.0
    rhq160 = 2.0 if rhq131 == 1.0 else 0.0
    smq078 = 3.0 if smoking_raw == "current" else 0.0
    paq620 = 1.0 if ocq180 >= 20 else 2.0
    paq650 = 1.0 if activity == "high" else 2.0
    paq665 = 1.0 if activity in {"moderate", "high"} else 2.0
    work_schedule = _num(row, "ocq670_work_schedule") or 1.0
    ever_hepatitis_c = 1.0 if (_num(row, "hepatitis_bc") or 0.0) >= 0.5 else 2.0
    ever_kidney_stones = _num(row, "kiq026_kidney_stones") or 2.0
    ever_heart_attack = _num(row, "mcq160e_heart_attack") or 2.0
    ever_stroke = _num(row, "mcq160f_stroke") or 2.0
    mcq195 = 2.0 if (_num(row, "mcq160a_arthritis") or 2.0) == 1.0 else 3.0

    out = {
        # ── Demographics ──────────────────────────────────────────────────────
        "age_years":         _num(row, "age_years") or 45.0,
        "gender":            2.0 if sex_f else 1.0,
        "gender_code":       2.0 if sex_f else 1.0,
        "gender_female":     1.0 if sex_f else 0.0,
        "bmi":               bmi,
        "weight_kg":         round(bmi * (1.68 ** 2), 1),
        "waist_cm":          round(max(65.0, min(140.0, 75.0 + (bmi - 23.0) * 2.5)), 1),
        "activity_level":    activity,
        "smq040_smoke_now":  smq040,

        # ── PHQ-9 (real or condition-aware imputed) ───────────────────────────
        "dpq040_fatigue":        phq["dpq040_fatigue"],
        "dpq030_sleep":          phq["dpq030_sleep"],
        "dpq070_concentration":  phq["dpq070_concentration"],

        # ── Sleep questionnaire (real or condition-aware imputed) ─────────────
        "slq030_snore_freq":           slq["slq030_snore_freq"],
        "slq050_sleep_trouble_doctor": slq["slq050_sleep_trouble_doctor"],
        "sld012_sleep_hours_weekday":  slq["sld012_sleep_hours_weekday"],
        "sld013_sleep_hours_weekend":  slq["sld013_sleep_hours_weekend"],

        # ── Exertion / SOB ────────────────────────────────────────────────────
        "cdq010_sob_stairs":          _num(row, "cdq010_sob_stairs") or 2.0,
        # Sedentary minutes: not in NHANES 2003-2006 — estimated from activity level
        "pad680_sedentary_minutes":   float(pad680),
        # Joints
        "mcq160a_arthritis":          _num(row, "mcq160a_arthritis") or 2.0,   # 2 = no
        # General health self-rating (1–5)
        "huq010_general_health":      _num(row, "huq010_general_health") or 3.0,
        # Nocturia (frequency per night)
        "kiq480_nocturia":            _num(row, "kiq480_nocturia") or 0.0,
        # Alcohol (avg drinks per day)
        "alq130_avg_drinks_per_day":  _num(row, "alq130_avg_drinks_per_day") or 0.0,
        # Weight preference (1=lose, 2=gain, 3=stay same)
        "whq040_weight_preference":   _num(row, "whq040_weight_preference") or 3.0,
        # Medical history / diagnosed conditions (1=yes, 2=no)
        "bpq020_high_bp":             _num(row, "bpq020_high_bp") or 2.0,
        "bpq040a_bp_meds":            _num(row, "bpq040a_bp_meds") or 2.0,
        "diq010_diabetes":            _num(row, "diq010_diabetes") or 2.0,
        "diq160_prediabetes":         _num(row, "diq160_prediabetes") or 2.0,
        "mcq092_transfusion":         _num(row, "mcq092_transfusion") or 2.0,
        "mcq053_anemia_treatment":    _num(row, "mcq053_anemia_treatment") or 2.0,
        "mcq160m_ever_thyroid":       _num(row, "mcq160m_ever_thyroid") or 2.0,
        "mcq170m_active_thyroid":     _num(row, "mcq170m_active_thyroid") or 2.0,
        "mcq160l_liver_condition":    _num(row, "mcq160l_liver_condition") or 2.0,
        "mcq170l_active_liver":       _num(row, "mcq170l_active_liver") or 2.0,
        "kiq022_weak_kidneys":        _num(row, "kiq022_weak_kidneys") or 2.0,
        # Abdominal pain not in 2003-2006 → no
        "mcq520_abdominal_pain":      2.0,   # [default: not measured in this cycle]
        # Reproductive (females only)
        "rhq031_regular_periods":     _num(row, "rhq031_regular_periods") or 2.0,
        "rhq060_age_last_period":     rhq060,
        "rhq131_ever_pregnant":       rhq131,
        "rhq540_hormone_use":         rhq540,
        # BP (measured)
        "sbp_mean":  sbp,
        "dbp_mean":  dbp,
        # Med count
        "med_count":                  _num(row, "med_count") or 0.0,
        "rxd_disease_list":           str(row.get("rxd_disease_list") or ""),
        # ── Lab values ────────────────────────────────────────────────────────
        # Users upload a standard Clinical Chemistry & Urinalysis report that
        # contains ONLY: lipid panel (total cholesterol, LDL, HDL, triglycerides),
        # fasting glucose, and urine dipstick (protein, glucose, RBC, WBC, nitrite).
        # All other clinical chemistry values (ferritin, HbA1c, creatinine, CRP,
        # liver enzymes, electrolytes, vitamin D, vitamin B12, etc.) are NOT
        # provided and must be set to null — the model cannot see them.
        # The NHANES 2003-2006 processed CSV contains a subset of these user-visible
        # labs (lipids, LDL, fasting glucose, UACR, WBC, total protein). Thread
        # those real values through when present for this SEQN.
        # Urine dipstick fields are still unavailable in NHANES here and remain null.
        # Ground-truth labels (anemia, iron_deficiency, etc.) were derived from the
        # raw NHANES lab files during preprocessing — those derivations are kept as
        # ground truth but the raw values are intentionally withheld here.
        "total_cholesterol_mg_dl":    chol,
        "ldl_mg_dl":                  ldl,
        "ldl_cholesterol_mg_dl":      ldl,
        "hdl_mg_dl":                  hdl,
        "hdl_cholesterol_mg_dl":      hdl,
        "triglycerides_mg_dl":        trig,
        "fasting_glucose_mg_dl":      gluc,
        "uacr_mg_g":                  uacr,
        "wbc_1000_cells_ul":          wbc,
        "total_protein_g_dl":         total_protein,
        # ── Condition flags (used by KNN scorer + Bayesian sampler) ───────────
        "thyroid":              _num(row, "thyroid") or 0.0,
        "kidney":               _num(row, "kidney") or 0.0,
        "sleep_disorder":       _num(row, "sleep_disorder") or 0.0,
        "anemia":               _num(row, "anemia") or 0.0,
        "iron_deficiency":      _num(row, "iron_deficiency") or 0.0,
        "hidden_inflammation":  _num(row, "hidden_inflammation") or 0.0,
        "hepatitis_bc":         _num(row, "hepatitis_bc") or 0.0,
        "liver":                _num(row, "liver") or 0.0,
        "prediabetes":          _num(row, "prediabetes") or 0.0,
        "menopause":            _num(row, "menopause") or 0.0,
        "electrolyte_imbalance":_num(row, "electrolyte_imbalance") or 0.0,
        "perimenopause_proxy_probable": _num(row, "perimenopause_proxy_probable") or 0.0,
        "ocq180_hours_worked_week": ocq180,
    }

    out.update({
        "general_health": out["huq010_general_health"],
        "general_health_condition": out["huq010_general_health"],
        "huq010___general_health_condition": out["huq010_general_health"],
        "alq130___avg_#_alcoholic_drinks/day___past_12_mos": out["alq130_avg_drinks_per_day"],
        "avg_drinks_per_day": out["alq130_avg_drinks_per_day"],
        "cdq010___shortness_of_breath_on_stairs/inclines": out["cdq010_sob_stairs"],
        "hdl": hdl,
        "hdl_cholesterol": hdl,
        "kiq480___how_many_times_urinate_in_night?": out["kiq480_nocturia"],
        "times_urinate_in_night": out["kiq480_nocturia"],
        "smoked_100_cigs": smoked_100,
        "hospitalized_lastyear": huq071,
        "huq071___overnight_hospital_patient_in_last_year": huq071,
        "overnight_hospital": huq071,
        "fasting_glucose": gluc,
        "glucose": gluc,
        "slq050_told_trouble_sleeping": out["slq050_sleep_trouble_doctor"],
        "told_dr_trouble_sleeping": out["slq050_sleep_trouble_doctor"],
        "trouble_sleeping": out["slq050_sleep_trouble_doctor"],
        "dpq040___feeling_tired_or_having_little_energy": out["dpq040_fatigue"],
        "dpq040_tired_little_energy": out["dpq040_fatigue"],
        "feeling_tired_little_energy": out["dpq040_fatigue"],
        "diq070___take_diabetic_pills_to_lower_blood_sugar": diq070,
        "takes_diabetes_pills": diq070,
        "taking_diabetic_pills": diq070,
        "paq650___vigorous_recreational_activities": paq650,
        "slq030___how_often_do_you_snore?": out["slq030_snore_freq"],
        "ever_told_arthritis": out["mcq160a_arthritis"],
        "mcq160a___ever_told_you_had_arthritis": out["mcq160a_arthritis"],
        "avg_cigarettes_per_day": cigs_day,
        "cigarettes_per_day": cigs_day,
        "wbc": wbc,
        "alq151___ever_have_4/5_or_more_drinks_every_day?": heavy_daily,
        "ever_heavy_drinker_daily": heavy_daily,
        "bpq030___told_had_high_blood_pressure___2+_times": out["bpq020_high_bp"],
        "mcq010___ever_been_told_you_have_asthma": 2.0,
        "mcq300c___close_relative_had_diabetes": mcq300c,
        "education_ord": education_ord,
        "triglycerides": trig,
        "doctor_said_overweight": mcq080,
        "mcq080___doctor_ever_said_you_were_overweight": mcq080,
        "moderate_recreational": paq665,
        "paq665___moderate_recreational_activities": paq665,
        "ever_told_high_cholesterol": bpq080,
        "told_high_cholesterol": bpq080,
        "taking_anemia_treatment": out["mcq053_anemia_treatment"],
        "blood_transfusion": out["mcq092_transfusion"],
        "ever_had_blood_transfusion": out["mcq092_transfusion"],
        "mcq092___ever_receive_blood_transfusion": out["mcq092_transfusion"],
        "overall_work_schedule": work_schedule,
        "work_schedule": work_schedule,
        "ever_hepatitis_c": ever_hepatitis_c,
        "paq620___moderate_work_activity": paq620,
        "smoking_now": current_smoker,
        "tried_to_lose_weight": whq070,
        "pregnancy_status_bin": pregnancy_status_bin,
        "cholesterol": chol,
        "total_cholesterol": chol,
        "SLD012": out["sld012_sleep_hours_weekday"],
        "sld012___sleep_hours___weekdays_or_workdays": out["sld012_sleep_hours_weekday"],
        "sleep_hours_weekday": out["sld012_sleep_hours_weekday"],
        "sleep_hours_weekdays": out["sld012_sleep_hours_weekday"],
        "bpq020___ever_told_you_had_high_blood_pressure": out["bpq020_high_bp"],
        "ever_told_high_bp": out["bpq020_high_bp"],
        "liver_condition": out["mcq160l_liver_condition"],
        "sedentary_minutes": out["pad680_sedentary_minutes"],
        "total_protein": total_protein,
        "times_healthcare_past_year": 1.0 if huq071 == 1.0 else 0.0,
        "kiq450___how_frequently_does_Urinated before reaching the toilet_occur?": kiq450,
        "kiq450___how_frequently_does_this_occur?": kiq450,
        "mcq195___which_type_of_arthritis_was_it?": mcq195,
        "dr_said_reduce_fat": 1.0 if mcq080 == 1.0 else 2.0,
        "abdominal_pain": pain,
        "mcq520___abdominal_pain_during_past_12_months?": pain,
        "hours_worked_per_week": ocq180,
        "whq040___like_to_weigh_more,_less_or_same": out["whq040_weight_preference"],
        "ldl_cholesterol": ldl,
        "how_often_urinary_leakage": kiq005,
        "kiq005___how_often_have_urinary_leakage?": kiq005,
        "regular_periods": rhq031,
        "rhq031___had_regular_periods_in_past_12_months": rhq031,
        "sld013___sleep_hours___weekends": out["sld013_sleep_hours_weekend"],
        "sleep_hours_weekend": out["sld013_sleep_hours_weekend"],
        "kidney_disease": out["kiq022_weak_kidneys"],
        "kiq022___ever_told_you_had_weak/failing_kidneys?": out["kiq022_weak_kidneys"],
        "ever_had_kidney_stones": ever_kidney_stones,
        "kiq026___ever_had_kidney_stones?": ever_kidney_stones,
        "kiq044___urinated_before_reaching_the_toilet?": kiq044,
        "urinated_before_toilet": kiq044,
        "ever_told_heart_failure": mcq160b,
        "heart_failure": mcq160b,
        "rhq540_ever_hormones": rhq540,
        "alq111___ever_had_a_drink_of_any_kind_of_alcohol": ever_drank,
        "bpq050a___now_taking_prescribed_medicine_for_hbp": out["bpq040a_bp_meds"],
        "taking_insulin": diq050,
        "kiq010___how_much_urine_lose_each_time?": kiq010,
        "kiq042___leak_urine_during_physical_activities?": kiq042,
        "kiq052___how_much_were_daily_activities_affected?": kiq052,
        "kiq430___how_frequently_does_Leak urine during physical activities_this_occur?": kiq430,
        "kiq430___how_frequently_does_this_occur?": kiq430,
        "ever_told_heart_attack": ever_heart_attack,
        "rhq131___ever_been_pregnant?": rhq131,
        "rhq160___how_many_times_have_been_pregnant?": rhq160,
        "smq078___how_soon_after_waking_do_you_smoke": smq078,
        "diabetes": out["diq010_diabetes"],
        "ever_told_diabetes": out["diq010_diabetes"],
        "ever_told_stroke": ever_stroke,
        "mcq540___ever_seen_a_dr_about_this_pain": saw_dr_for_pain,
        "saw_dr_for_pain": saw_dr_for_pain,
    })

    return out

def build_profile(row: pd.Series, conditions: list[str]) -> dict[str, Any]:
    """Convert one CSV row + its condition list to the standard profile format."""
    activity    = derive_activity_level(row)
    raw_smoking = derive_smoking_status(row)
    smoking     = SMOKING_MAP.get(raw_smoking, "unknown")
    seqn        = int(row["SEQN"]) if pd.notna(row.get("SEQN")) else 0

    # ── Compute nhanes_inputs first (includes condition-aware imputation) ────
    nhanes_in = _nhanes_inputs(row, activity, raw_smoking)

    # ── Bayesian answer generation ────────────────────────────────────────────
    # Create a merged row that overlays the imputed PHQ-9 / SLQ values onto the
    # original CSV row before computing the symptom vector and Bayesian answers.
    # Without this, cycle C profiles (100% null PHQ-9/SLQ) would use 0.15 fatigue
    # and 0.2 sleep-debt defaults, producing unrealistically healthy symptom vectors
    # for people who have anemia, sleep disorders, etc.
    # Clinical labs (ferritin, HbA1c, etc.) stay as the real CSV values — they
    # feed the Bayesian latent-state computation at build time even though they are
    # withheld from nhanes_inputs for inference.
    bridge_values = {
        **_impute_phq(row, seqn),
        **_impute_slq(
            row,
            seqn,
            _num(row, "bmi") or 27.0,
            str(row.get("gender", "")).lower() in ("female", "f"),
        ),
    }
    _QUIZ_BRIDGE_KEYS = (
        "dpq040_fatigue", "dpq010_anhedonia", "dpq020_depressed",
        "dpq030_sleep", "dpq070_concentration",
        "slq030_snore_freq", "slq040_stop_breathing_freq",
        "slq050_sleep_trouble_doctor", "sld012_sleep_hours_weekday",
    )
    bayes_row = row.copy()
    for k in _QUIZ_BRIDGE_KEYS:
        if pd.isna(bayes_row.get(k)):
            if nhanes_in.get(k) is not None:
                bayes_row[k] = nhanes_in[k]
            elif k in bridge_values:
                bayes_row[k] = bridge_values[k]

    _sv_for_bayes = symptom_vector_from_row(bayes_row)
    bayesian_answers = fill_bayesian_answers(bayes_row, _sv_for_bayes)

    cycle      = str(row.get("cycle", "?"))
    profile_id = f"NHANES-{cycle}-{seqn:05d}"

    # ── Ground truth: always list ALL conditions present ──────────────────────
    # "positive" = exactly one condition; "multi" = two or more.
    # For both types, every condition is listed — the primary (first) is is_primary=True.
    # Healthy profiles have an empty list.
    if not conditions:
        profile_type     = "healthy"
        target_condition = None
        expected_conditions: list[dict] = []
    else:
        profile_type     = "positive" if len(conditions) == 1 else "multi"
        target_condition = conditions[0]
        expected_conditions = [
            {"condition_id": c, "is_primary": i == 0, "confidence": "high"}
            for i, c in enumerate(conditions)
        ]

    return {
        "profile_id":       profile_id,
        "profile_type":     profile_type,
        "target_condition": target_condition,
        "source":           "real_nhanes_2003_2006",
        "seqn":             seqn,
        "demographics": {
            "age":            max(1, int(row["age_years"])) if pd.notna(row.get("age_years")) else 30,
            "sex":            "F" if str(row.get("gender", "")).lower() in ("female", "f") else "M",
            "bmi":            round(float(row["bmi"]), 2) if pd.notna(row.get("bmi")) else None,
            "smoking_status": smoking,
            "activity_level": activity,
        },
        # Quiz-feature values: real NHANES where measured, condition-aware
        # imputed where not (PHQ-9 / SLQ null for cycle C and subsampled cycle D).
        "nhanes_inputs":    nhanes_in,
        # lab_values: only what the user's Clinical Chemistry & Urinalysis report
        # actually provides. All other labs are null — they are not available.
        "lab_values": {
            "total_cholesterol_mg_dl": nhanes_in["total_cholesterol_mg_dl"],
            "ldl_mg_dl":               nhanes_in["ldl_mg_dl"],
            "ldl_cholesterol_mg_dl":   nhanes_in["ldl_cholesterol_mg_dl"],
            "hdl_mg_dl":               nhanes_in["hdl_mg_dl"],
            "hdl_cholesterol_mg_dl":   nhanes_in["hdl_cholesterol_mg_dl"],
            "triglycerides_mg_dl":     nhanes_in["triglycerides_mg_dl"],
            "fasting_glucose_mg_dl":   nhanes_in["fasting_glucose_mg_dl"],
            "uacr_mg_g":               nhanes_in["uacr_mg_g"],
            "wbc_1000_cells_ul":       nhanes_in["wbc_1000_cells_ul"],
            "total_protein_g_dl":      nhanes_in["total_protein_g_dl"],
        },
        "quiz_path": "hybrid",
        "bayesian_answers": bayesian_answers,
        "ground_truth": {
            "expected_conditions": expected_conditions,
        },
        "metadata": {
            "cycle":          cycle,
            "vitd_threshold": VITD_THRESHOLD_NMOL_L,
            "source_basis":   "real_nhanes_2003_2006",
        },
    }


def _num(row: pd.Series, col: str) -> float | None:
    v = row.get(col)
    return None if pd.isna(v) else round(float(v), 2)


def main() -> int:
    print(f"Reading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"  {len(df):,} rows loaded")

    # ── Classify rows ─────────────────────────────────────────────────────────
    print("Classifying conditions (vitamin D threshold < 30 nmol/L) ...")
    df["_conditions"] = df.apply(get_conditions, axis=1)
    df["_n_conds"]    = df["_conditions"].apply(len)

    labeled_df  = df[df["_n_conds"] > 0].copy()
    healthy_df  = df[df["_n_conds"] == 0].copy()

    print(f"  Labeled rows  : {len(labeled_df):,}")
    print(f"  Healthy rows  : {len(healthy_df):,}")

    # ── Sample balanced labeled profiles ──────────────────────────────────────
    rng = random.Random(SEED)

    # Group by primary condition
    by_condition: dict[str, list[int]] = defaultdict(list)
    for idx, row in labeled_df.iterrows():
        conds = row["_conditions"]
        if conds:
            by_condition[conds[0]].append(idx)

    print()
    print("Sampling labeled profiles:")
    sampled_indices: list[int] = []
    for cond in sorted(by_condition):
        pool = by_condition[cond]
        n    = min(TARGET_PER_CONDITION, len(pool))
        chosen = rng.sample(pool, n)
        sampled_indices.extend(chosen)
        print(f"  {cond:35s} available={len(pool):5,}  sampled={n}")

    # ── Sample healthy profiles ───────────────────────────────────────────────
    healthy_pool = list(healthy_df.index)
    n_healthy    = min(TARGET_HEALTHY, len(healthy_pool))
    healthy_chosen = rng.sample(healthy_pool, n_healthy)
    print(f"\n  {'healthy':35s} available={len(healthy_pool):5,}  sampled={n_healthy}")

    # ── Build profile objects ─────────────────────────────────────────────────
    print("\nBuilding profile objects ...")
    all_selected = df.loc[sampled_indices + healthy_chosen]
    profiles: list[dict[str, Any]] = []
    for _, row in all_selected.iterrows():
        try:
            p = build_profile(row, row["_conditions"])
            profiles.append(p)
        except Exception as e:
            print(f"  WARN: skipping SEQN={row.get('SEQN')} — {e}")

    rng.shuffle(profiles)

    # ── Summary ───────────────────────────────────────────────────────────────
    from collections import Counter
    type_counts = Counter(p["profile_type"] for p in profiles)
    cond_counts = Counter(p["target_condition"] for p in profiles if p["target_condition"])

    print()
    print("Final cohort:")
    print(f"  Total   : {len(profiles):,}")
    print(f"  Types   : {dict(sorted(type_counts.items()))}")
    print(f"  Conditions (primary):")
    for c, n in sorted(cond_counts.items(), key=lambda x: -x[1]):
        print(f"    {c:35s} {n}")

    # ── Write output ──────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(profiles, indent=2))
    mb = OUTPUT_PATH.stat().st_size / 1_048_576
    print(f"\nWrote {OUTPUT_PATH.name}  ({mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
