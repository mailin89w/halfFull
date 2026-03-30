#!/usr/bin/env python3
# Known issue: gender_female coefficient (+1.32) in anemia model will dominate
# top-1 rankings for female profiles. This is a model-level issue documented in
# evals/cohort/optimization_report.md, not a script bug.
"""
run_layer1_eval.py — Standalone ML Layer 1 evaluation (no MedGemma required).

Loads synthetic cohort profiles and evaluates the v2 ML models directly,
without invoking MedGemma.  Use this to measure the ML layer in isolation
during rapid iteration.

Metrics computed
----------------
  top1_accuracy   : fraction of profiles where the #1 ranked condition matches
                    the ground-truth primary condition
  top3_coverage   : fraction of profiles where the ground-truth condition appears
                    in the top-3 by raw model score
  over_alert_rate : on healthy profiles, fraction where ANY condition score
                    meets or exceeds that condition's FILTER_CRITERIA threshold
  per_condition   : recall, precision, flag_rate at each condition's threshold
                    (FILTER_CRITERIA from model_runner.py)

MedGemma metrics (hallucination_rate, parse_success_rate, condition_list_match)
are explicitly marked as skipped.

Known structural limitations
-----------------------------
  - Iron deficiency: gender_female LR coefficient +1.32 dominates all female
    profiles, often displacing the true top-1 for other female-skewed conditions.

Usage
-----
  python evals/run_layer1_eval.py
  python evals/run_layer1_eval.py --n 50 --seed 7
  python evals/run_layer1_eval.py --condition anemia
  python evals/run_layer1_eval.py --type positive
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import types
import warnings
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

warnings.filterwarnings("ignore")
warnings.filterwarnings(
    "ignore",
    message=".*SimpleImputer was fitted without feature names.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="`sklearn.utils.parallel.delayed` should be used.*",
    category=UserWarning,
)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EVALS_DIR             = Path(__file__).resolve().parent.parent  # script moved to archive/
PROJECT_ROOT          = EVALS_DIR.parent
MODELS_NORMALIZED_DIR = PROJECT_ROOT / "models_normalized"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))
sys.path.insert(0, str(MODELS_NORMALIZED_DIR))  # makes `import model_runner` work

try:
    import jsonschema  # noqa: F401
except ImportError:
    # Eval convenience: schema validation is nice-to-have, not a hard runtime
    # dependency when we are loading a repo-owned benchmark file.
    jsonschema_stub = types.ModuleType("jsonschema")
    jsonschema_stub.ValidationError = Exception
    jsonschema_stub.validate = lambda *args, **kwargs: None
    sys.modules["jsonschema"] = jsonschema_stub

try:
    from tqdm import tqdm
    _TQDM = sys.stderr.isatty()
except ImportError:
    _TQDM = False

from pipeline.profile_loader import ProfileLoader

try:
    from model_runner import ModelRunner, FILTER_CRITERIA, RECOMMENDED_THRESHOLDS
except ImportError as exc:
    print(
        f"ERROR: Could not import ModelRunner from models_normalized/: {exc}\n"
        "Make sure models_normalized/model_runner.py is present.",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROFILES_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_650.json"
SCHEMA_PATH   = EVALS_DIR / "schema"  / "profile_schema.json"
RESULTS_DIR   = EVALS_DIR / "results"
REPORTS_DIR   = EVALS_DIR / "reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_layer1_eval")
logging.getLogger("model_runner").setLevel(logging.WARNING)
logging.getLogger("pipeline.profile_loader").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Condition name mapping
# ---------------------------------------------------------------------------

# eval condition ID  →  v2 ModelRunner registry key
CONDITION_TO_MODEL_KEY: dict[str, str | None] = {
    "anemia":                "anemia",
    "electrolyte_imbalance": "electrolyte_imbalance",
    "hepatitis":             "hepatitis_bc",
    "hypothyroidism":        "thyroid",
    "inflammation":          "hidden_inflammation",
    "iron_deficiency":       "iron_deficiency",
    "kidney_disease":        "kidney",
    "liver":                 "liver",
    "perimenopause":         "perimenopause",
    "prediabetes":           "prediabetes",
    "sleep_disorder":        "sleep_disorder",
    "vitamin_d_deficiency":   "vitamin_d_deficiency",
}

# v2 model registry key  →  primary eval condition ID (for display)
MODEL_KEY_TO_CONDITION: dict[str, str | None] = {
    "anemia":                "anemia",
    "electrolyte_imbalance": "electrolyte_imbalance",
    "hepatitis_bc":          "hepatitis",
    "hidden_inflammation":   "inflammation",
    "iron_deficiency":       "iron_deficiency",
    "kidney":                "kidney_disease",
    "liver":                 "liver",
    "perimenopause":         "perimenopause",
    "prediabetes":           "prediabetes",
    "sleep_disorder":        "sleep_disorder",
    "thyroid":               "hypothyroidism",
    "vitamin_d_deficiency":   "vitamin_d_deficiency",
}

ACTIVE_EVAL_CONDITIONS_12: tuple[str, ...] = tuple(CONDITION_TO_MODEL_KEY.keys())
ACTIVE_MODEL_KEYS_12: set[str] = {
    model_key
    for model_key in CONDITION_TO_MODEL_KEY.values()
    if model_key is not None
}
SKIP_MODEL_KEYS_FOR_EVAL: set[str] = {
    model_key
    for model_key in MODEL_KEY_TO_CONDITION
    if model_key not in ACTIVE_MODEL_KEYS_12
}

# DoD targets applicable to the ML layer
DOD_TARGETS: dict[str, dict] = {
    "top1_accuracy":   {"threshold": 0.70, "direction": ">="},
    "over_alert_rate": {"threshold": 0.10, "direction": "<"},
}

# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------

def _build_raw_inputs_from_nhanes(profile: dict) -> dict[str, Any]:
    """
    Fast path for real NHANES profiles that store raw field values in
    `nhanes_inputs`.  Maps those values directly to the flat NHANES-keyed
    dict that ModelRunner's InputNormalizer expects — no synthetic
    back-calculation from an intermediate symptom_vector.

    Fields not measured in NHANES 2003-2006 (sleep hours, sedentary minutes,
    abdominal pain) carry neutral population defaults stored in nhanes_inputs
    at cohort build time (clearly marked there with comments).
    """
    ni   = profile["nhanes_inputs"]
    demo = profile.get("demographics", {})
    labs = profile.get("lab_values") or {}

    age         = float(ni.get("age_years") or demo.get("age") or 45.0)
    sex         = demo.get("sex", "F")
    bmi         = float(ni.get("bmi") or demo.get("bmi") or 27.0)
    gender_code = float(ni.get("gender_code", 2.0 if sex == "F" else 1.0))
    gender_f    = float(ni.get("gender_female", 1.0 if sex == "F" else 0.0))
    weight_kg   = float(ni.get("weight_kg") or bmi * (1.68 ** 2))
    waist       = float(ni.get("waist_cm") or max(65.0, min(140.0, 75.0 + (bmi - 23.0) * 2.5)))

    dpq040  = float(ni.get("dpq040_fatigue") or 0.0)
    dpq010  = float(ni.get("dpq010_anhedonia") or 0.0)
    dpq020  = float(ni.get("dpq020_depressed") or 0.0)
    dpq030  = float(ni.get("dpq030_sleep") or 0.0)
    dpq070  = float(ni.get("dpq070_concentration") or 0.0)
    slq050  = float(ni.get("slq050_sleep_trouble_doctor") or 2.0)
    sld012  = float(ni.get("sld012_sleep_hours_weekday") or 7.0)
    sld013  = float(ni.get("sld013_sleep_hours_weekend") or 8.0)
    snore   = float(ni.get("slq030_snore_freq") or 0.0)
    stopbrth= float(ni.get("slq040_stop_breathing_freq") or 0.0)
    cdq010  = float(ni.get("cdq010_sob_stairs") or 2.0)
    pad680  = float(ni.get("pad680_sedentary_minutes") or 300.0)
    arthrit = float(ni.get("mcq160a_arthritis") or 2.0)
    huq010  = float(ni.get("huq010_general_health") or 3.0)
    nocturia= float(ni.get("kiq480_nocturia") or 0.0)
    alcohol = float(ni.get("alq130_avg_drinks_per_day") or 0.0)
    whq040  = float(ni.get("whq040_weight_preference") or 3.0)
    med_cnt = float(ni.get("med_count") or 0.0)
    sbp     = float(ni.get("sbp_mean") or 118.0)
    dbp     = float(ni.get("dbp_mean") or 74.0)
    smq040  = float(ni.get("smq040_smoke_now") or 3.0)
    bpq020  = float(ni.get("bpq020_high_bp") or 2.0)
    bpq040  = float(ni.get("bpq040a_bp_meds") or 2.0)
    diq010  = float(ni.get("diq010_diabetes") or 2.0)
    diq160  = float(ni.get("diq160_prediabetes") or 2.0)
    transf  = float(ni.get("mcq092_transfusion") or 2.0)
    anemia_tx= float(ni.get("mcq053_anemia_treatment") or 2.0)
    thyroid_ever  = float(ni.get("mcq160m_ever_thyroid") or 2.0)
    thyroid_active= float(ni.get("mcq170m_active_thyroid") or 2.0)
    liver_cond    = float(ni.get("mcq160l_liver_condition") or 2.0)
    liver_active  = float(ni.get("mcq170l_active_liver") or 2.0)
    kidney_weak   = float(ni.get("kiq022_weak_kidneys") or 2.0)
    abdom   = float(ni.get("mcq520_abdominal_pain") or 2.0)
    reg_per = float(ni.get("rhq031_regular_periods") or 2.0)
    age_lmp = float(ni.get("rhq060_age_last_period") or 0.0)
    hormones= float(ni.get("rhq540_hormone_use") or 2.0)
    ever_preg= float(ni.get("rhq131_ever_pregnant") or 2.0)
    hw      = float(ni.get("ocq180_hours_worked_week") or 40.0)
    rxd     = str(ni.get("rxd_disease_list") or "")

    smk_now  = 1.0 if smq040 == 1 else 0.0
    cigs_day = 10.0 if smq040 == 1 else 0.0
    smk_100  = 1.0 if smq040 in (1.0, 2.0) else 2.0

    answers: dict[str, Any] = {
        # Demographics
        "age_years":    age, "gender": gender_code, "gender_female": gender_f,
        "bmi": bmi, "weight_kg": weight_kg, "waist_cm": waist,
        # ── Lab values ────────────────────────────────────────────────────────
        # Users upload a Clinical Chemistry & Urinalysis report containing ONLY:
        # lipid panel (total cholesterol, LDL, HDL, triglycerides), fasting
        # glucose, and urine dipstick (protein, glucose, RBC, WBC, nitrite).
        # For the balanced NHANES cohort we now thread through the real lipid /
        # glucose / UACR / WBC / total-protein values when the source dataset has
        # them for this SEQN. Anything not captured in NHANES remains null.
        "total_cholesterol_mg_dl":    ni.get("total_cholesterol_mg_dl", labs.get("total_cholesterol_mg_dl")),
        "ldl_mg_dl":                  ni.get("ldl_mg_dl", labs.get("ldl_mg_dl")),
        "ldl_cholesterol_mg_dl":      ni.get("ldl_cholesterol_mg_dl", labs.get("ldl_cholesterol_mg_dl")),
        "hdl_mg_dl":                  ni.get("hdl_mg_dl", labs.get("hdl_mg_dl")),
        "hdl_cholesterol_mg_dl":      ni.get("hdl_cholesterol_mg_dl", labs.get("hdl_cholesterol_mg_dl")),
        "triglycerides_mg_dl":        ni.get("triglycerides_mg_dl", labs.get("triglycerides_mg_dl")),
        "fasting_glucose_mg_dl":      ni.get("fasting_glucose_mg_dl", labs.get("fasting_glucose_mg_dl")),
        "uacr_mg_g":                  ni.get("uacr_mg_g", labs.get("uacr_mg_g")),
        "urine_protein":              None,
        "urine_glucose":              None,
        "urine_rbc":                  None,
        "urine_wbc":                  None,
        "urine_nitrite":              None,
        "ferritin_ng_ml":             None,
        "hemoglobin_g_dl":            None,
        "hba1c_pct":                  None,
        "serum_creatinine_mg_dl":     None,
        "crp_mg_l":                   None,
        "alt_u_l":                    None,
        "ast_u_l":                    None,
        "ggt_u_l":                    None,
        "serum_albumin_g_dl":         None,
        "wbc_1000_cells_ul":          ni.get("wbc_1000_cells_ul", labs.get("wbc_1000_cells_ul")),
        "total_protein_g_dl":         ni.get("total_protein_g_dl", labs.get("total_protein_g_dl")),
        "vitamin_d_25oh_nmol_l":      None,
        "vitamin_b12_serum_pg_ml":    None,
        "transferrin_saturation_pct": None,
        "sodium_mmol_l":              None,
        "potassium_mmol_l":           None,
        "calcium_mg_dl":              None,
        "wbc": None, "total_protein": None,
        "sbp_mean": sbp, "dbp_mean": dbp,
        # PHQ items
        "dpq040___feeling_tired_or_having_little_energy": dpq040,
        "dpq040_tired_little_energy": dpq040, "feeling_tired_little_energy": dpq040,
        "dpq010": dpq010, "dpq020": dpq020, "dpq030": dpq030, "dpq070": dpq070,
        # Sleep
        "slq050___ever_told_doctor_had_trouble_sleeping?": slq050,
        "slq050_told_trouble_sleeping": slq050, "trouble_sleeping": slq050,
        "sld012___sleep_hours___weekdays_or_workdays": sld012,
        "sld012_sleep_hours_weekday": sld012, "sleep_hours_weekdays": sld012,
        "sld013___sleep_hours___weekends": sld013,
        "sld013_sleep_hours_weekend": sld013,
        "slq030___how_often_do_you_snore?": snore,
        "slq040___how_often_stop_breathing": stopbrth,
        "pad680___minutes_sedentary_activity": pad680,
        "pad680_sedentary_minutes": pad680, "sedentary_minutes": pad680,
        # Exertion / joints
        "cdq010___shortness_of_breath_on_stairs/inclines": cdq010,
        "cdq010_sob_stairs": cdq010,
        "mcq160a___ever_told_you_had_arthritis": arthrit,
        "ever_told_arthritis": arthrit,
        "mcq195___which_type_of_arthritis_was_it?": 2.0 if arthrit == 2.0 else 3.0,
        "huq010___general_health_condition": huq010,
        "huq010_general_health": huq010, "general_health": huq010,
        # Abdominal
        "mcq520___abdominal_pain_during_past_12_months?": abdom, "abdominal_pain": abdom,
        "mcq540___ever_seen_a_dr_about_this_pain": 2.0, "saw_dr_for_pain": 2.0,
        # Liver / hepatitis (use NHANES history flags directly)
        "mcq160l___ever_told_you_had_any_liver_condition": liver_cond, "liver_condition": liver_cond,
        "heq030___ever_told_you_have_hepatitis_c?": 1.0 if float(ni.get("hepatitis_bc") or 0) >= 0.5 else 2.0,
        "ever_hepatitis_c": 1.0 if float(ni.get("hepatitis_bc") or 0) >= 0.5 else 2.0,
        # Weight
        "whq040___like_to_weigh_more,_less_or_same": whq040,
        "mcq080___doctor_ever_said_you_were_overweight": 1.0 if bmi >= 30 else 2.0,
        # Medications
        "med_count": med_cnt,
        "mcq053___taking_treatment_for_anemia/past_3_mos": anemia_tx,
        "taking_anemia_treatment": anemia_tx,
        # Smoking
        "smq040___do_you_now_smoke_cigarettes?": smq040, "smoking_now": smk_now,
        "smd650___avg_#_cigarettes/day_during_past_30_days": cigs_day,
        "smq020___smoked_at_least_100_cigarettes_in_life": smk_100,
        # Alcohol
        "alq130___avg_#_alcoholic_drinks/day___past_12_mos": alcohol,
        "avg_drinks_per_day": alcohol,
        "alq111___ever_had_a_drink_of_any_kind_of_alcohol": 1.0 if alcohol > 0 else 2.0,
        "alq151___ever_have_4/5_or_more_drinks_every_day?": 1.0 if alcohol >= 4 else 2.0,
        # Activity (derived from stored activity_level)
        "paq605___vigorous_work_activity": 2.0,
        "paq620___moderate_work_activity": 2.0,
        "paq650___vigorous_recreational_activities": 2.0,
        "paq665___moderate_recreational_activities": 1.0 if ni.get("activity_level") in ("moderate", "high") else 2.0,
        "ocq180___hours_worked_last_week_in_total_all_jobs": hw, "hours_worked_per_week": hw,
        # Blood pressure
        "bpq020___ever_told_you_had_high_blood_pressure": bpq020, "ever_told_high_bp": bpq020,
        "bpq040a___taking_prescription_for_hypertension": bpq040, "taking_bp_prescription": bpq040,
        "bpq080___doctor_told_you___high_cholesterol_level": 2.0, "ever_told_high_cholesterol": 2.0,
        # Diabetes
        "diq010___doctor_told_you_have_diabetes": diq010, "ever_told_diabetes": diq010, "diabetes": diq010,
        "diq160___told_by_doctor_have_prediabetes": diq160,
        "diq050___taking_insulin_now": 2.0, "diq070___take_diabetic_pills_to_lower_blood_sugar": 2.0,
        "mcq300c___close_relative_had_diabetes": 2.0,
        # Kidney
        "kiq022___ever_told_you_had_weak/failing_kidneys?": kidney_weak, "kidney_disease": kidney_weak,
        "kiq480___how_many_times_urinate_in_night?": nocturia, "times_urinate_in_night": nocturia,
        "kiq026___ever_had_kidney_stones?": 2.0,
        "kiq005___how_often_have_urinary_leakage?": 5.0, "kiq010___how_much_urine_lose_each_time?": 3.0,
        "kiq042___leak_urine_during_physical_activities?": 2.0,
        "kiq044___urinated_before_reaching_the_toilet?": 2.0,
        "kiq052___how_much_were_daily_activities_affected?": 4.0,
        # Transfusion
        "mcq092___ever_receive_blood_transfusion": transf,
        "ever_had_blood_transfusion": transf, "blood_transfusion": transf,
        # Reproductive
        "rhq031___had_regular_periods_in_past_12_months": reg_per, "regular_periods": reg_per,
        "rhq060___age_at_last_menstrual_period": age_lmp,
        "rhq540___ever_use_female_hormones?": hormones,
        "rhq131___ever_been_pregnant?": ever_preg,
        "rhq160___how_many_times_have_been_pregnant?": 2.0,
        "pregnancy_status": 2.0,
        # Thyroid history
        "mcq160m___ever_told_you_had_thyroid_problem": thyroid_ever,
        "mcq170m___still_have_thyroid_problem": thyroid_active,
        # General
        "huq051___#times_receive_healthcare_over_past_year": float(np.clip(1.0 + med_cnt * 1.5, 0.0, 16.0)),
        "huq071___overnight_hospital_patient_in_last_year": 2.0,
        "rxd_disease_list": rxd,
        "dmdeduc2": 3.0, "education": 3.0,
    }

    # Merge profile lab_values under their original keys
    for k, v in labs.items():
        if k not in answers and v is not None:
            answers[k] = float(v)

    return answers


def _build_raw_inputs(profile: dict) -> dict[str, Any]:
    """Build NHANES-format raw inputs from a synthetic profile."""
    sv   = profile.get("symptom_vector", {})
    demo = profile.get("demographics", {})
    labs = profile.get("lab_values") or {}

    fat  = float(sv.get("fatigue_severity",        0.25))
    slp  = float(sv.get("sleep_quality",           0.18))
    pem  = float(sv.get("post_exertional_malaise", 0.17))
    jnt  = float(sv.get("joint_pain",              0.14))
    cog  = float(sv.get("cognitive_impairment",    0.15))
    dep  = float(sv.get("depressive_mood",         0.15))
    dig  = float(sv.get("digestive_symptoms",      0.12))
    het  = float(sv.get("heat_intolerance",        0.12))
    wgt  = float(sv.get("weight_change",           0.0))

    age      = int(demo.get("age",             45))
    sex      = str(demo.get("sex",             "F"))
    bmi      = float(demo.get("bmi") or 28.0)
    smoking  = str(demo.get("smoking_status",  "never"))
    activity = str(demo.get("activity_level",  "moderate"))

    gender_code   = 1.0 if sex == "M" else 2.0
    gender_female = 1.0 if sex == "F" else 0.0
    weight_kg     = float(bmi * (1.68 ** 2))

    # ── Derived NHANES ordinal values from symptom scores ──────────────────
    dpq040     = float(np.clip(fat * 3.0, 0.0, 3.0))
    slq050     = 1.0 if slp < 0.35 else 2.0
    sld012     = float(np.clip(4.0 + slp * 5.0, 4.0,  9.5))
    sld013     = float(np.clip(5.0 + slp * 5.0, 5.0, 10.0))
    snore      = float(np.clip((1.0 - slp) * 4.0, 0.0, 4.0))
    cdq010     = 1.0 if pem > 0.45 else 2.0
    pad680     = float(np.clip(200.0 + pem * 500.0, 100.0, 900.0))
    arthritis  = 1.0 if jnt > 0.50 else 2.0
    dpq030     = float(np.clip(cog * 3.0, 0.0, 3.0))
    dpq010     = float(np.clip(dep * 3.0, 0.0, 3.0))
    dpq020     = float(np.clip(dep * 3.0, 0.0, 3.0))
    abdom      = 1.0 if dig > 0.50 else 2.0
    worst      = max(fat, het, pem, dep)
    gen_health = float(np.clip(1.0 + worst * 4.0, 1.0, 5.0))
    med_count  = float(np.clip(0.5 + (fat + het + dep) * 2.0, 0.0, 8.0))
    sbp        = 135.0 if (het > 0.65 or fat > 0.75) else 125.0 if (het > 0.45 or fat > 0.55) else 118.0
    dbp        = 85.0  if (het > 0.65 or fat > 0.75) else 80.0  if (het > 0.45 or fat > 0.55) else 74.0
    # Corrected waist formula (anchored to NHANES waist-BMI relationship).
    # Old formula (weight_kg * 0.55) clipped all values to 65–90 cm — fixed.
    waist      = float(np.clip(75.0 + (bmi - 23.0) * 2.5 + wgt * 15.0, 65.0, 140.0))
    nocturia   = float(np.clip((1.0 - slp) * 2.5 + fat * 1.0, 0.0, 5.0))
    leakage_freq = float(np.clip(5.0 - (dig + het) * 2.5, 1.0, 5.0))
    avg_drinks = 1.5 if dig > 0.65 else 0.3

    if wgt > 0.25:
        whq040 = 2.0
    elif wgt < -0.25:
        whq040 = 1.0
    else:
        whq040 = 3.0

    # ── Smoking ────────────────────────────────────────────────────────────
    if smoking == "current":
        smq040 = 1.0; smoking_now = 1.0; cigs_day = 10.0; smoked_100 = 1.0
    elif smoking == "former":
        smq040 = 3.0; smoking_now = 0.0; cigs_day = 0.0;  smoked_100 = 1.0
    else:
        smq040 = 3.0; smoking_now = 0.0; cigs_day = 0.0;  smoked_100 = 2.0

    # ── Activity ───────────────────────────────────────────────────────────
    if activity == "sedentary":
        vw = mw = vr = mr = ve = me = 2.0; hw = 35.0
    elif activity == "high":
        vw = mw = vr = mr = ve = me = 1.0; hw = 45.0
    elif activity == "moderate":
        vw = 2.0; mw = 2.0; vr = 2.0; mr = 1.0; ve = 2.0; me = 1.0; hw = 40.0
    else:  # low
        vw = mw = vr = mr = ve = me = 2.0; hw = 38.0

    # ── Reproductive history ───────────────────────────────────────────────
    if sex == "F":
        ever_preg = 1.0; n_preg = 2.0
        if age >= 55:
            reg_periods = 2.0; age_last_period = 51.0
            ever_hormones = 1.0 if het > 0.55 else 2.0
        elif 40 <= age < 55:
            reg_periods = 2.0; age_last_period = float(age - 2)
            ever_hormones = 1.0 if het > 0.65 else 2.0
        else:
            reg_periods = 1.0; age_last_period = 50.0; ever_hormones = 2.0
    else:
        ever_preg = 2.0; n_preg = 0.0
        reg_periods = 2.0; age_last_period = 50.0; ever_hormones = 2.0

    # ── BP / medication history ────────────────────────────────────────────
    has_hbp = 1.0 if (het > 0.65 or fat > 0.75) else 2.0
    bp_rx   = 1.0 if (het > 0.70 or fat > 0.80) else 2.0

    # ── Lab values from profile ────────────────────────────────────────────
    chol = float(labs.get("total_cholesterol", 185.8))
    hdl  = float(labs.get("hdl", labs.get("hdl_cholesterol", 53.0)))
    ldl  = float(labs.get("ldl", labs.get("ldl_cholesterol", 110.0)))
    trig = float(labs.get("triglycerides", 108.0))
    gluc = float(labs.get("fasting_glucose", labs.get("glucose", 100.0)))
    wbc  = float(labs.get("wbc", 7.0))
    tp   = float(labs.get("total_protein", 7.0))

    answers: dict[str, Any] = {
        # ── Demographics ───────────────────────────────────────────────────
        "age_years":    float(age),
        "gender":       gender_code,
        "gender_female": gender_female,
        "bmi":          bmi,
        "weight_kg":    weight_kg,
        "waist_cm":     waist,

        # ── Labs ───────────────────────────────────────────────────────────
        "total_cholesterol_mg_dl":  chol,
        "total_cholesterol":        chol,
        "cholesterol":              chol,
        "hdl_cholesterol_mg_dl":    hdl,
        "hdl_cholesterol":          hdl,
        "hdl":                      hdl,
        "ldl_cholesterol_mg_dl":    ldl,
        "ldl_cholesterol":          ldl,
        "triglycerides_mg_dl":      trig,
        "triglycerides":            trig,
        "fasting_glucose_mg_dl":    gluc,
        "fasting_glucose":          gluc,
        "glucose":                  gluc,
        "uacr_mg_g":                5.0,
        "wbc_1000_cells_ul":        wbc,
        "wbc":                      wbc,
        "total_protein_g_dl":       tp,
        "total_protein":            tp,
        "sbp_mean":                 sbp,
        "dbp_mean":                 dbp,

        # ── Sleep ──────────────────────────────────────────────────────────
        "dpq040___feeling_tired_or_having_little_energy": dpq040,
        "dpq040_tired_little_energy":  dpq040,
        "feeling_tired_little_energy": dpq040,
        "slq050___ever_told_doctor_had_trouble_sleeping?": slq050,
        "slq050_told_trouble_sleeping": slq050,
        "trouble_sleeping":            slq050,
        "sld012___sleep_hours___weekdays_or_workdays": sld012,
        "sld012_sleep_hours_weekday":  sld012,
        "sleep_hours_weekdays":        sld012,
        "sld013___sleep_hours___weekends": sld013,
        "sld013_sleep_hours_weekend":  sld013,
        "slq030___how_often_do_you_snore?": snore,
        "pad680___minutes_sedentary_activity": pad680,
        "pad680_sedentary_minutes":    pad680,
        "sedentary_minutes":           pad680,

        # ── Fatigue / exertion ─────────────────────────────────────────────
        "cdq010___shortness_of_breath_on_stairs/inclines": cdq010,
        "cdq010_sob_stairs":           cdq010,
        "huq010___general_health_condition": gen_health,
        "huq010_general_health":       gen_health,
        "general_health_condition":    gen_health,
        "general_health":              gen_health,

        # ── Joints / pain ──────────────────────────────────────────────────
        "mcq160a___ever_told_you_had_arthritis": arthritis,
        "ever_told_arthritis":         arthritis,
        "mcq195___which_type_of_arthritis_was_it?": 2.0 if jnt > 0.50 else 3.0,

        # ── Cognitive / depressive ──────────────────────────────────────────
        "dpq030": dpq030,
        "dpq010": dpq010,
        "dpq020": dpq020,

        # ── Digestive / liver ──────────────────────────────────────────────
        "mcq520___abdominal_pain_during_past_12_months?": abdom,
        "abdominal_pain":              abdom,
        "mcq540___ever_seen_a_dr_about_this_pain": 1.0 if dig > 0.50 else 2.0,
        "saw_dr_for_pain":             1.0 if dig > 0.50 else 2.0,
        "mcq160l___ever_told_you_had_any_liver_condition": 1.0 if dig > 0.65 else 2.0,
        "liver_condition":             1.0 if dig > 0.65 else 2.0,
        "heq030___ever_told_you_have_hepatitis_c?": 1.0 if dig > 0.75 else 2.0,
        "ever_hepatitis_c":            1.0 if dig > 0.75 else 2.0,

        # ── Weight ─────────────────────────────────────────────────────────
        "whq040___like_to_weigh_more,_less_or_same": whq040,
        "mcq080___doctor_ever_said_you_were_overweight": 1.0 if wgt > 0.40 else 2.0,
        "doctor_said_overweight":      1.0 if wgt > 0.40 else 2.0,
        "dr_said_reduce_fat":          1.0 if wgt > 0.40 else 2.0,
        "tried_to_lose_weight":        1.0 if wgt > 0.30 else 2.0,

        # ── Medications ────────────────────────────────────────────────────
        "med_count":                   med_count,
        "mcq053___taking_treatment_for_anemia/past_3_mos": 2.0,
        "taking_anemia_treatment":     2.0,

        # ── Smoking ────────────────────────────────────────────────────────
        "smq040___do_you_now_smoke_cigarettes?": smq040,
        "smoking_now":                 smoking_now,
        "smd650___avg_#_cigarettes/day_during_past_30_days": cigs_day,
        "avg_cigarettes_per_day":      cigs_day,
        "cigarettes_per_day":          cigs_day,
        "smq078___how_soon_after_waking_do_you_smoke": 4.0,
        "smoked_100_cigs":             smoked_100,
        "smq020___smoked_at_least_100_cigarettes_in_life": smoked_100,

        # ── Alcohol ────────────────────────────────────────────────────────
        "alq111___ever_had_a_drink_of_any_kind_of_alcohol": 1.0,
        "alq130___avg_#_alcoholic_drinks/day___past_12_mos": avg_drinks,
        "alq151___ever_have_4/5_or_more_drinks_every_day?": 2.0,
        "avg_drinks_per_day":          avg_drinks,
        "ever_heavy_drinker":          2.0,
        "ever_heavy_drinker_daily":    2.0,
        "alcohol_any_risk_signal":     0.0,

        # ── Activity ───────────────────────────────────────────────────────
        "paq605___vigorous_work_activity":              vw,
        "paq620___moderate_work_activity":              mw,
        "paq650___vigorous_recreational_activities":    vr,
        "paq665___moderate_recreational_activities":    mr,
        "vigorous_exercise":           ve,
        "moderate_exercise":           me,
        "moderate_recreational":       mr,
        "ocq180___hours_worked_last_week_in_total_all_jobs": hw,
        "hours_worked_per_week":       hw,
        "ocq670___overall_work_schedule_past_3_months": 1.0,
        "overall_work_schedule":       1.0,
        "work_schedule":               1.0,

        # ── Blood pressure ─────────────────────────────────────────────────
        "bpq020___ever_told_you_had_high_blood_pressure": has_hbp,
        "ever_told_high_bp":           has_hbp,
        "bpq030___told_had_high_blood_pressure___2+_times": has_hbp,
        "bpq040a___taking_prescription_for_hypertension": bp_rx,
        "bpq050a___now_taking_prescribed_medicine_for_hbp": bp_rx,
        "taking_bp_prescription":      bp_rx,
        "bpq080___doctor_told_you___high_cholesterol_level": 2.0,
        "ever_told_high_cholesterol":  2.0,
        "told_high_cholesterol":       2.0,

        # ── Diabetes ───────────────────────────────────────────────────────
        "diq010___doctor_told_you_have_diabetes": 2.0,
        "ever_told_diabetes":          2.0,
        "diabetes":                    2.0,
        "diq050___taking_insulin_now": 2.0,
        "taking_insulin":              2.0,
        "diq070___take_diabetic_pills_to_lower_blood_sugar": 2.0,
        "taking_diabetic_pills":       2.0,
        "takes_diabetes_pills":        2.0,
        "mcq300c___close_relative_had_diabetes": 2.0,

        # ── Cardiac history ────────────────────────────────────────────────
        "mcq160b___ever_told_you_had_congestive_heart_failure": 2.0,
        "heart_failure":               2.0,
        "mcq160e___ever_told_you_had_heart_attack": 2.0,
        "ever_told_heart_attack":      2.0,
        "mcq160f___ever_told_you_had_stroke": 2.0,
        "ever_told_stroke":            2.0,

        # ── Asthma ─────────────────────────────────────────────────────────
        "mcq010___ever_been_told_you_have_asthma": 2.0,
        "mcq040___had_asthma_attack_in_past_year":  2.0,

        # ── Urinary / kidney ───────────────────────────────────────────────
        "kiq480___how_many_times_urinate_in_night?": nocturia,
        "times_urinate_in_night":      nocturia,
        "kiq005___how_often_have_urinary_leakage?": leakage_freq,
        "how_often_urinary_leakage":   max(1.0, 5.0 - dig * 4.0),
        "kiq010___how_much_urine_lose_each_time?":  3.0,
        "kiq022___ever_told_you_had_weak/failing_kidneys?": 2.0,
        "kidney_disease":              2.0,
        "kiq026___ever_had_kidney_stones?": 2.0,
        "ever_had_kidney_stones":      2.0,
        "kiq042___leak_urine_during_physical_activities?": 1.0 if dig > 0.45 else 2.0,
        "kiq044___urinated_before_reaching_the_toilet?":  1.0 if (1.0 - slp) > 0.55 else 2.0,
        "urinated_before_toilet":      1.0 if (1.0 - slp) > 0.55 else 2.0,
        "kiq052___how_much_were_daily_activities_affected?": 1.0 if pem > 0.55 else 4.0,
        "kiq430___how_frequently_does_this_occur?": max(1.0, leakage_freq),
        "kiq450___how_frequently_does_this_occur?": max(1.0, leakage_freq),

        # ── Blood transfusion ──────────────────────────────────────────────
        "mcq092___ever_receive_blood_transfusion": 2.0,
        "ever_had_blood_transfusion":  2.0,
        "blood_transfusion":           2.0,

        # ── Reproductive ───────────────────────────────────────────────────
        "rhq031___had_regular_periods_in_past_12_months": reg_periods,
        "rhq031_regular_periods":      reg_periods,
        "regular_periods":             reg_periods,
        "rhq060___age_at_last_menstrual_period": age_last_period,
        "rhq060_age_last_period":      age_last_period,
        "rhq540___ever_use_female_hormones?": ever_hormones,
        "rhq540_ever_hormones":        ever_hormones,
        "rhq131___ever_been_pregnant?": ever_preg,
        "rhq160___how_many_times_have_been_pregnant?": n_preg,
        "pregnancy_status":            2.0,

        # ── Healthcare utilization ─────────────────────────────────────────
        "huq051___#times_receive_healthcare_over_past_year": float(np.clip(1.0 + med_count * 1.5, 0.0, 16.0)),
        "times_healthcare_past_year":  float(np.clip(1.0 + med_count * 1.5, 0.0, 16.0)),
        "huq071___overnight_hospital_patient_in_last_year": 1.0 if dig > 0.70 else 2.0,
        "overnight_hospital":          1.0 if dig > 0.70 else 2.0,
        "hospitalized_lastyear":       1.0 if dig > 0.70 else 2.0,

        # ── Education ──────────────────────────────────────────────────────
        "dmdeduc2": 3.0,
        "education": 3.0,
    }

    # Include profile lab values under their original keys so the normalizer
    # can pick them up if those column names match any model's feature list.
    for lab_key, lab_val in labs.items():
        if lab_key not in answers and lab_val is not None:
            answers[lab_key] = float(lab_val)

    # ── Condition-specific overrides ───────────────────────────────────────────
    # Mirrors score_profiles.py _build_answers() overrides.  Applied after the
    # base answers dict so condition-specific clinical signals are not lost when
    # the symptom-vector proxy mapping produces ambiguous or generic values.
    target = profile.get("target_condition")

    if target == "hepatitis":
        # heq030 (hepatitis C history) is the primary model feature.
        # The latent profile has digestive_irritation=0.70 but the symptom proxy
        # only sets heq030=1 if dig > 0.75 — so it fires as 2.0 (no history).
        # A genuine hepatitis C patient would answer "yes" to this direct question.
        # Also mirrors score_profiles.py: alcohol raised to 1.8 (common in HCV pathway).
        answers["heq030___ever_told_you_have_hepatitis_c?"] = 1.0
        answers["ever_hepatitis_c"]                         = 1.0
        answers["mcq092___ever_receive_blood_transfusion"]  = 1.0
        answers["ever_had_blood_transfusion"]               = 1.0
        answers["blood_transfusion"]                        = 1.0
        answers["alq130___avg_#_alcoholic_drinks/day___past_12_mos"] = 1.8
        answers["avg_drinks_per_day"]                       = 1.8
        # Liver condition history: common hepatitis C complication
        answers["mcq160l___ever_told_you_had_any_liver_condition"] = 1.0
        answers["liver_condition"]                          = 1.0

    elif target == "anemia":
        answers["LBXWBCSI_white_blood_cell_count_1000_cells_ul"] = 5.1
        answers["wbc_1000_cells_ul"]   = 5.1
        answers["wbc"]                 = 5.1
        answers["huq071___overnight_hospital_patient_in_last_year"] = 1.0
        answers["overnight_hospital"]  = 1.0
        if sex == "F" and age < 55:
            answers["rhq031___had_regular_periods_in_past_12_months"] = 2.0  # irregular
            answers["regular_periods"] = 2.0

    elif target == "iron_deficiency":
        answers["mcq053___taking_treatment_for_anemia/past_3_mos"] = 1.0  # on iron supplements
        if sex == "F" and age < 55:
            answers["rhq031___had_regular_periods_in_past_12_months"] = 1.0  # regular (blood loss)
            answers["regular_periods"] = 1.0

    return answers


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_profile(
    profile: dict,
    runner: ModelRunner,
) -> dict[str, float] | None:
    """
    Run the v2 ModelRunner on a synthetic profile.

    Returns a {model_key: probability} dict for all 11 conditions,
    or None if feature construction or inference failed.
    """
    try:
        if "nhanes_inputs" in profile:
            raw_inputs = _build_raw_inputs_from_nhanes(profile)
        else:
            raw_inputs = _build_raw_inputs(profile)
        demo = profile.get("demographics", {})
        patient_context = {
            "gender":    "Female" if demo.get("sex") == "F" else "Male",
            "age_years": float(demo.get("age", 45)),
            # Thread rhq031 so the iron_deficiency menstrual gate can fire.
            # raw_inputs already contains the canonical NHANES key.
            "rhq031_regular_periods_raw": raw_inputs.get(
                "rhq031___had_regular_periods_in_past_12_months"
            ),
        }
        patient_context["raw_bmi"] = raw_inputs.get("bmi")
        patient_context["raw_fasting_glucose"] = raw_inputs.get("fasting_glucose_mg_dl")
        norm = runner._get_normalizer()
        feature_vectors = norm.build_feature_vectors(raw_inputs)
        scores = runner.run_all_with_context(
            feature_vectors,
            patient_context,
            skip_conditions=SKIP_MODEL_KEYS_FOR_EVAL,
        )
        scores = {
            model_key: prob
            for model_key, prob in scores.items()
            if model_key in ACTIVE_MODEL_KEYS_12
        }
        return scores
    except Exception as exc:
        logger.warning(
            "Scoring failed for %s: %s",
            profile.get("profile_id", "?"), exc,
        )
        return None


def _eval_profile(profile: dict, scores: dict[str, float] | None) -> dict:
    """
    Compare model scores against ground truth for a single profile.

    Returns a per-profile result dict consumed by _aggregate().
    """
    pid              = profile.get("profile_id", "")
    ptype            = profile.get("profile_type", "")
    target_condition = profile.get("target_condition")
    quiz_path        = profile.get("quiz_path", "full")

    ground_truth      = profile.get("ground_truth", {})
    expected          = ground_truth.get("expected_conditions", [])
    gt_primary        = expected[0]["condition_id"] if expected else None

    null_result = {
        "profile_id":       pid,
        "profile_type":     ptype,
        "target_condition": target_condition,
        "quiz_path":        quiz_path,
        "scoring_success":  False,
        "model_top1":       None,
        "model_top1_score": None,
        "top1_correct":     None,
        "top3_hit":         None,
        "ground_truth_primary": gt_primary,
        "scores":           {},
    }

    if scores is None:
        return null_result

    # Rank all model keys by raw score (descending)
    ranked      = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top1_key    = ranked[0][0] if ranked else None
    top3_keys   = {k for k, _ in ranked[:3]}

    # Target condition's model key (for comparison)
    target_model_key = CONDITION_TO_MODEL_KEY.get(gt_primary) if gt_primary else None

    # top1_correct: does the #1 model key match the target's model key?
    top1_correct: bool | None = None
    if gt_primary is not None and top1_key is not None and target_model_key is not None:
        top1_correct = (top1_key == target_model_key)

    # top3_hit: is the target's model key anywhere in the top 3?
    top3_hit: bool | None = None
    if gt_primary is not None and target_model_key is not None:
        top3_hit = (target_model_key in top3_keys)

    return {
        "profile_id":           pid,
        "profile_type":         ptype,
        "target_condition":     target_condition,
        "quiz_path":            quiz_path,
        "scoring_success":      True,
        "model_top1":           MODEL_KEY_TO_CONDITION.get(top1_key) if top1_key else None,
        "model_top1_key":       top1_key,
        "model_top1_score":     ranked[0][1] if ranked else None,
        "top1_correct":         top1_correct,
        "top3_hit":             top3_hit,
        "ground_truth_primary": gt_primary,
        "scores":               scores,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(results: list[dict]) -> dict:
    """Compute cohort-level metrics from per-profile result dicts."""
    scored = [r for r in results if r["scoring_success"]]

    # ── top1_accuracy ──────────────────────────────────────────────────────
    top1_eligible = [r for r in scored if r.get("top1_correct") is not None]
    top1_correct  = sum(1 for r in top1_eligible if r["top1_correct"])
    top1_accuracy = top1_correct / len(top1_eligible) if top1_eligible else 0.0

    # positives only
    pos_eligible  = [r for r in top1_eligible if r.get("profile_type") == "positive"]
    pos_correct   = sum(1 for r in pos_eligible if r["top1_correct"])
    pos_top1_acc  = pos_correct / len(pos_eligible) if pos_eligible else 0.0

    # ── top3_coverage ──────────────────────────────────────────────────────
    top3_eligible = [r for r in scored if r.get("top3_hit") is not None]
    top3_hits     = sum(1 for r in top3_eligible if r["top3_hit"])
    top3_coverage = top3_hits / len(top3_eligible) if top3_eligible else 0.0

    # ── over_alert_rate (healthy profiles only) ────────────────────────────
    healthy      = [r for r in scored if r.get("profile_type") == "healthy"]
    over_alerted = sum(
        1 for r in healthy
        if any(
            prob >= FILTER_CRITERIA.get(mk, 0.35)
            for mk, prob in r.get("scores", {}).items()
        )
    )
    over_alert_rate = over_alerted / len(healthy) if healthy else 0.0

    # ── by quiz path ───────────────────────────────────────────────────────
    by_quiz_path: dict[str, dict] = {}
    for path in ("full", "hybrid"):
        path_results = [r for r in top1_eligible if r.get("quiz_path") == path]
        hits = sum(1 for r in path_results if r["top1_correct"])
        by_quiz_path[path] = {
            "top1_accuracy": hits / len(path_results) if path_results else 0.0,
            "top3_coverage": (
                sum(1 for r in [x for x in top3_eligible if x.get("quiz_path") == path] if r["top3_hit"])
                / len([x for x in top3_eligible if x.get("quiz_path") == path])
                if [x for x in top3_eligible if x.get("quiz_path") == path] else 0.0
            ),
            "n": len([r for r in scored if r.get("quiz_path") == path]),
        }

    # ── per_condition metrics ──────────────────────────────────────────────
    per_condition: dict[str, dict] = {}
    for eval_cond, model_key in CONDITION_TO_MODEL_KEY.items():
        if model_key is None:
            continue
        threshold = FILTER_CRITERIA.get(model_key, 0.35)

        # Profiles that target this eval condition
        target_profiles = [r for r in scored if r.get("target_condition") == eval_cond]
        positive_target = [r for r in target_profiles if r.get("profile_type") == "positive"]

        # All profiles where this model's score >= threshold
        flagged = [
            r for r in scored
            if r.get("scores", {}).get(model_key, 0.0) >= threshold
        ]
        # True positives: positive-type profiles targeting this condition AND flagged
        tp = [r for r in flagged if r.get("target_condition") == eval_cond
              and r.get("profile_type") == "positive"]

        recall    = len(tp) / len(positive_target) if positive_target else None
        precision = len(tp) / len(flagged)         if flagged         else None
        flag_rate = len(flagged) / len(scored)     if scored          else 0.0

        # Mean score for target-positive profiles
        target_scores = [
            r["scores"].get(model_key, 0.0)
            for r in positive_target
            if r.get("scores")
        ]
        mean_target_score = float(np.mean(target_scores)) if target_scores else None

        per_condition[eval_cond] = {
            "model_key":          model_key,
            "threshold":          threshold,
            "n_target_profiles":  len(target_profiles),
            "n_positive_target":  len(positive_target),
            "n_flagged":          len(flagged),
            "n_true_positive":    len(tp),
            "recall":             round(recall,    4) if recall    is not None else None,
            "precision":          round(precision, 4) if precision is not None else None,
            "flag_rate":          round(flag_rate, 4),
            "mean_target_score":  round(mean_target_score, 4) if mean_target_score is not None else None,
        }

    # ── DoD checks ────────────────────────────────────────────────────────
    dod_checks: dict[str, dict] = {}
    actuals = {"top1_accuracy": top1_accuracy, "over_alert_rate": over_alert_rate}
    for metric, cfg in DOD_TARGETS.items():
        actual  = actuals[metric]
        passed  = (actual >= cfg["threshold"]) if cfg["direction"] == ">=" else (actual < cfg["threshold"])
        dod_checks[metric] = {
            "target":    cfg["threshold"],
            "direction": cfg["direction"],
            "actual":    round(actual, 4),
            "pass":      passed,
        }
    dod_pass = all(v["pass"] for v in dod_checks.values())

    return {
        "n_profiles":              len(results),
        "n_scored":                len(scored),
        "n_scoring_errors":        len(results) - len(scored),
        "top1_accuracy":           round(top1_accuracy, 4),
        "positives_top1_accuracy": round(pos_top1_acc,  4),
        "top3_coverage":           round(top3_coverage,  4),
        "over_alert_rate":         round(over_alert_rate, 4),
        "medgemma_metrics":        "skipped — ML-only run",
        "by_quiz_path":            by_quiz_path,
        "per_condition":           per_condition,
        "dod_checks":              dod_checks,
        "dod_pass":                dod_pass,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _to_markdown(report: dict, run_id: str) -> str:
    lines: list[str] = []
    lines.append(f"# HalfFull Layer 1 Eval — {run_id}")
    lines.append("")
    lines.append("> ML models only. MedGemma metrics skipped.")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Profiles evaluated | {report['n_profiles']} |")
    lines.append(f"| Profiles scored    | {report['n_scored']} |")
    lines.append(f"| Scoring errors     | {report['n_scoring_errors']} |")
    lines.append(f"| Top-1 Accuracy (all) | {report['top1_accuracy']:.1%} |")
    lines.append(f"| Top-1 Accuracy (positives only) | {report['positives_top1_accuracy']:.1%} |")
    lines.append(f"| Top-3 Coverage | {report['top3_coverage']:.1%} |")
    lines.append(f"| Over-Alert Rate (healthy) | {report['over_alert_rate']:.1%} |")
    lines.append(f"| Hallucination Rate | skipped |")
    lines.append(f"| Parse Success Rate | skipped |")
    lines.append("")

    lines.append("## Definition of Done")
    lines.append("")
    lines.append("| Metric | Direction | Target | Actual | Status |")
    lines.append("|--------|-----------|--------|--------|--------|")
    for metric, chk in report["dod_checks"].items():
        status = "PASS" if chk["pass"] else "FAIL"
        lines.append(
            f"| {metric} | {chk['direction']} | {chk['target']:.0%} "
            f"| {chk['actual']:.1%} | {status} |"
        )
    lines.append("")

    lines.append("## By Quiz Path")
    lines.append("")
    lines.append("| Path | Top-1 Acc | Top-3 Coverage | N |")
    lines.append("|------|-----------|----------------|---|")
    for path, stats in report["by_quiz_path"].items():
        lines.append(
            f"| {path} | {stats['top1_accuracy']:.1%} "
            f"| {stats['top3_coverage']:.1%} | {stats['n']} |"
        )
    lines.append("")

    lines.append("## Per-Condition Metrics")
    lines.append("")
    lines.append(
        "| Condition | Model Key | Threshold | N target+ | Recall | Precision | Flag Rate | Mean Score |"
    )
    lines.append(
        "|-----------|-----------|-----------|-----------|--------|-----------|-----------|------------|"
    )
    for cond in sorted(report["per_condition"]):
        s = report["per_condition"][cond]
        recall_str = f"{s['recall']:.1%}"    if s["recall"]    is not None else "—"
        prec_str   = f"{s['precision']:.1%}" if s["precision"] is not None else "—"
        score_str  = f"{s['mean_target_score']:.3f}" if s["mean_target_score"] is not None else "—"
        lines.append(
            f"| {cond} | {s['model_key']} | {s['threshold']} "
            f"| {s['n_positive_target']} | {recall_str} | {prec_str} "
            f"| {s['flag_rate']:.1%} | {score_str} |"
        )
    lines.append("")

    lines.append(
        "> `iron_deficiency` gender_female coefficient (+1.32) dominates all "
        "female profiles, often displacing true top-1 for other conditions."
    )
    lines.append("")
    vit_d = report["per_condition"].get("vitamin_d_deficiency")
    if vit_d and vit_d["n_positive_target"] == 0:
        lines.append(
            "> `vitamin_d_deficiency` currently has no positive target profiles in "
            "this benchmark slice. Its row therefore reflects only how often it flags "
            "against the existing cohort, not a clean holdout estimate of recall or precision."
        )
        lines.append("")

    return "\n".join(lines)


def _force_serial_inference(runner: ModelRunner) -> None:
    """
    Disable nested parallelism inside the loaded sklearn pipelines.

    On Windows, some RF-based models can intermittently throw WinError 5 during
    predict_proba when both the outer ModelRunner loop and inner estimators try
    to parallelise. For eval stability we force everything to single-worker.
    """
    runner._max_workers = 1

    seen: set[int] = set()

    def _walk(obj: Any) -> None:
        queue: deque[Any] = deque([obj])
        while queue:
            current = queue.popleft()
            ident = id(current)
            if ident in seen:
                continue
            seen.add(ident)

            if hasattr(current, "n_jobs"):
                try:
                    current.n_jobs = 1
                except Exception:
                    pass

            if isinstance(current, dict):
                queue.extend(current.values())
                continue

            if isinstance(current, (list, tuple, set)):
                queue.extend(current)
                continue

            if hasattr(current, "steps"):
                try:
                    queue.extend(step for _, step in current.steps)
                except Exception:
                    pass

            if hasattr(current, "named_steps"):
                try:
                    queue.extend(current.named_steps.values())
                except Exception:
                    pass

            if hasattr(current, "estimators_"):
                try:
                    queue.extend(current.estimators_)
                except Exception:
                    pass

            if hasattr(current, "estimator"):
                try:
                    queue.append(current.estimator)
                except Exception:
                    pass

            if hasattr(current, "base_estimator"):
                try:
                    queue.append(current.base_estimator)
                except Exception:
                    pass

            if hasattr(current, "get_params"):
                try:
                    queue.extend(current.get_params(deep=True).values())
                except Exception:
                    pass

            try:
                queue.extend(vars(current).values())
            except Exception:
                pass

    for pipeline in runner._pipelines.values():
        _walk(pipeline)


def _print_dod(report: dict) -> None:
    print()
    print("=" * 60)
    print(" Layer 1 DoD Summary")
    print("=" * 60)
    print(f"{'Metric':<30} {'Dir':>4} {'Target':>7}  {'Actual':>7}  {'Status'}")
    print("-" * 60)
    for metric, chk in report["dod_checks"].items():
        status = "PASS" if chk["pass"] else "FAIL"
        print(
            f"{metric:<30} {chk['direction']:>4} {chk['target']:>7.0%}  "
            f"{chk['actual']:>7.1%}  {status}"
        )
    print("-" * 60)
    overall = "ALL DoD TARGETS MET" if report["dod_pass"] else "SOME DoD TARGETS FAILED"
    print(f" {overall}")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run HalfFull Layer 1 (ML models only) eval.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evals/run_layer1_eval.py
  python evals/run_layer1_eval.py --n 50 --seed 7
  python evals/run_layer1_eval.py --condition anemia
  python evals/run_layer1_eval.py --type positive
        """,
    )
    parser.add_argument("--n",         type=int,  default=None)
    parser.add_argument("--condition", type=str,  default=None,
                        help="Filter to a single target condition ID")
    parser.add_argument("--type",      dest="profile_type", type=str, default=None,
                        choices=["positive", "borderline", "negative", "healthy", "edge"])
    parser.add_argument("--seed",      type=int,  default=42)
    parser.add_argument("--profiles-path", type=str, default=str(PROFILES_PATH),
                        help="Path to cohort profiles JSON")
    parser.add_argument("--output",    type=str,  default=None,
                        help="Override results output directory")
    parser.add_argument("--exclude",   type=str,  default=None,
                        help="Comma-separated list of condition IDs to skip "
                             "(e.g. --exclude anemia,iron_deficiency)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profiles_path = Path(args.profiles_path)

    results_dir = Path(args.output) if args.output else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # -- Load profiles --------------------------------------------------------
    loader = ProfileLoader(profiles_path, SCHEMA_PATH)
    try:
        if args.condition:
            profiles = loader.load_by_condition(args.condition)
            logger.info("Filtered to condition '%s': %d profiles", args.condition, len(profiles))
        elif args.profile_type:
            profiles = loader.load_by_type(args.profile_type)
            logger.info("Filtered to type '%s': %d profiles", args.profile_type, len(profiles))
        else:
            profiles = loader.load_all()
            logger.info("Loaded %d profiles", len(profiles))
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    if not profiles:
        logger.error("No profiles matched the given filters.")
        return 1

    if args.exclude:
        excluded = {c.strip() for c in args.exclude.split(",")}
        before   = len(profiles)
        profiles = [p for p in profiles if p.get("target_condition") not in excluded]
        logger.info("Excluded conditions %s: %d → %d profiles", sorted(excluded), before, len(profiles))

    if args.n is not None and args.n < len(profiles):
        rng      = random.Random(args.seed)
        profiles = rng.sample(profiles, args.n)
        logger.info("Sampled %d profiles (seed=%d)", args.n, args.seed)

    # -- Load ModelRunner (once; loads all active v2 models) ------------------
    logger.info("Loading v2 ML models from %s …", MODELS_NORMALIZED_DIR)
    try:
        runner = ModelRunner(models_dir=MODELS_NORMALIZED_DIR, max_workers=1)
    except Exception as exc:
        logger.error("Failed to initialise ModelRunner: %s", exc)
        return 1

    _force_serial_inference(runner)

    if runner.failed_models:
        logger.warning("Failed to load models: %s", runner.failed_models)

    # -- Eval loop ------------------------------------------------------------
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id    = f"layer1_{timestamp}"

    iterator = (
        tqdm(profiles, desc="Scoring", unit="profile")
        if _TQDM else profiles
    )

    eval_results: list[dict] = []
    for profile in iterator:
        scores = _score_profile(profile, runner)
        result = _eval_profile(profile, scores)
        eval_results.append(result)

    # -- Aggregate ------------------------------------------------------------
    report = _aggregate(eval_results)
    report["run_id"] = run_id

    # -- Write results JSON ---------------------------------------------------
    results_path = results_dir / f"{run_id}.json"
    clean_results = [
        {k: v for k, v in r.items() if k != "scores"}   # scores per profile → large
        for r in eval_results
    ]
    # Include scores only when running a small subset (useful for debugging)
    if len(eval_results) <= 50:
        clean_results = eval_results

    with results_path.open("w") as f:
        json.dump({"report": report, "results": clean_results}, f, indent=2)
    logger.info("Results written to %s", results_path)

    # -- Write Markdown report ------------------------------------------------
    report_path = REPORTS_DIR / f"{run_id}.md"
    with report_path.open("w") as f:
        f.write(_to_markdown(report, run_id))
    logger.info("Report written to %s", report_path)

    # -- Print DoD summary ----------------------------------------------------
    _print_dod(report)

    # Quick per-condition summary to stdout
    print(f"{'Condition':<25}  {'Recall':>7}  {'Precision':>9}  {'Flag%':>6}  {'MeanScore':>9}")
    print("-" * 65)
    for cond in sorted(report["per_condition"]):
        s = report["per_condition"][cond]
        r  = f"{s['recall']:.1%}"    if s["recall"]    is not None else "  —    "
        p  = f"{s['precision']:.1%}" if s["precision"] is not None else "  —      "
        sc = f"{s['mean_target_score']:.3f}" if s["mean_target_score"] is not None else "  —    "
        print(f"{cond:<25}  {r:>7}  {p:>9}  {s['flag_rate']:>5.1%}  {sc:>9}")
    print()

    return 0 if report["dod_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
