#!/usr/bin/env python3
"""
score_profiles.py — Direct ML model scoring of synthetic cohort profiles.

Phase 4 optimization tool: loads evals/cohort/profiles.json, converts each
profile's symptom_vector + demographics + lab_values into the feature format
expected by each model, runs ModelRunner.run_all(), and reports per-condition
top-1 accuracy.

Feature Construction Strategy
------------------------------
The symptom_vector uses normalized [0-1] floats. Each model expects specific
NHANES feature columns. The mapping is:

  fatigue_severity   → dpq040 [0-3]: score * 3.0
  sleep_quality      → slq050 [1=trouble, 2=no]: low quality = 1
                     → sld012/sld013 hours: low quality = fewer hours
                     → slq030 snoring: low quality = more snoring
  post_exert_malaise → cdq010 [1=Yes SOB, 2=No]: high PEM = 1
                     → pad680 sedentary minutes: high PEM = more sedentary
  joint_pain         → mcq160a arthritis [1=Yes, 2=No]: high = 1
  cognitive          → dpq030 [0-3]: score * 3.0
  depressive_mood    → dpq010/dpq020 [0-3]: score * 3.0
  digestive          → mcq520 abdominal_pain [1=Yes, 2=No]: high = 1
  heat_intolerance   → general_health [1-5]: proxy for symptom burden
                     → weight_kg / waist_cm: higher for hypothyroid/perimenopause
  weight_change      → whq040 [1=more, 2=less, 3=same]; bmi; doctor_said_overweight

Key insight: ALL features must be provided (not NaN) to avoid GBM/LR
imputing defaults that inflate scores for the wrong conditions.
The perimenopause GBM scores ~0.65 for all-NaN inputs (its imputed default);
populating all features with healthy values drops it to ~0.06.

Usage:
    cd /path/to/halfFull
    python evals/score_profiles.py

Output:
    - Per-condition accuracy summary (stdout)
    - evals/cohort/scoring_results.json  (machine-readable)
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Path setup ─────────────────────────────────────────────────────────────────
EVALS_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
PROFILES_PATH = EVALS_DIR / "cohort" / "profiles.json"
RESULTS_PATH  = EVALS_DIR / "cohort" / "scoring_results.json"

sys.path.insert(0, str(PROJECT_ROOT))

from models.model_runner import ModelRunner, MODEL_REGISTRY  # noqa: E402
from models.questionnaire_to_model_features import MODEL_FEATURES  # noqa: E402

# ── Condition name mapping (generator IDs → model registry keys) ───────────────
CONDITION_TO_MODEL_KEY: dict[str, str | None] = {
    "menopause":             "perimenopause",  # no separate menopause model
    "perimenopause":         "perimenopause",
    "hypothyroidism":        "thyroid",
    "kidney_disease":        "kidney",
    "sleep_disorder":        "sleep_disorder",
    "anemia":                "anemia",
    "iron_deficiency":       "iron_deficiency",
    "hepatitis":             "hepatitis",
    "prediabetes":           "prediabetes",
    "inflammation":          "inflammation",
    "electrolyte_imbalance": "electrolytes",
}


def _build_answers(profile: dict) -> dict:
    """
    Convert profile (symptom_vector + demographics + lab_values) into a flat
    NHANES-keyed answers dict, providing explicit values for ALL model features
    so that no feature is left NaN (which causes model imputation artifacts).

    The full population of non-NaN defaults prevents the perimenopause GBM
    from returning its all-NaN default of ~0.65, and prevents iron_deficiency
    from over-firing due to missing rhq fields.
    """
    sv   = profile.get("symptom_vector", {})
    demo = profile.get("demographics", {})
    labs = profile.get("lab_values") or {}

    fat = float(sv.get("fatigue_severity", 0.25))
    slp = float(sv.get("sleep_quality", 0.18))           # HIGH = GOOD sleep
    pem = float(sv.get("post_exertional_malaise", 0.17))
    jnt = float(sv.get("joint_pain", 0.14))
    cog = float(sv.get("cognitive_impairment", 0.15))
    dep = float(sv.get("depressive_mood", 0.15))
    dig = float(sv.get("digestive_symptoms", 0.12))
    het = float(sv.get("heat_intolerance", 0.12))
    wgt = float(sv.get("weight_change", 0.0))

    age     = int(demo.get("age", 45))
    sex     = str(demo.get("sex", "F"))
    bmi     = float(demo.get("bmi", 28.0))
    smoking = str(demo.get("smoking_status", "never"))
    activity = str(demo.get("activity_level", "moderate"))

    gender_code = 1.0 if sex == "M" else 2.0
    gender_female = 1.0 if sex == "F" else 0.0
    # Approximate weight from bmi (168cm reference height)
    weight_kg = float(bmi * (1.68 ** 2))

    # ── Derived NHANES ordinal values from symptom scores ──────────────────
    # dpq040 [0-3]: fatigue
    dpq040 = float(np.clip(fat * 3.0, 0.0, 3.0))

    # slq050 [1=Yes trouble, 2=No trouble]: low sleep quality = 1
    slq050 = 1.0 if slp < 0.35 else 2.0

    # sld012/sld013 [hours]: low sleep quality → fewer hours (map 0→4h, 1→9h)
    sld012 = float(np.clip(4.0 + slp * 5.0, 4.0, 9.5))
    sld013 = float(np.clip(5.0 + slp * 5.0, 5.0, 10.0))

    # slq030 [0-4 snoring]: low sleep quality → more snoring
    snore = float(np.clip((1.0 - slp) * 4.0, 0.0, 4.0))

    # cdq010 [1=Yes SOB, 2=No]: high PEM → 1
    cdq010 = 1.0 if pem > 0.45 else 2.0

    # pad680 sedentary minutes: high PEM → more sedentary
    pad680 = float(np.clip(200.0 + pem * 500.0, 100.0, 900.0))

    # mcq160a [1=Yes arthritis, 2=No]: high joint pain → 1
    arthritis = 1.0 if jnt > 0.50 else 2.0

    # dpq030 [0-3] cognitive
    dpq030 = float(np.clip(cog * 3.0, 0.0, 3.0))

    # dpq010/dpq020 [0-3] depressive
    dpq010 = float(np.clip(dep * 3.0, 0.0, 3.0))
    dpq020 = float(np.clip(dep * 3.0, 0.0, 3.0))

    # abdominal pain [1=Yes, 2=No]: high digestive → 1
    abdom = 1.0 if dig > 0.50 else 2.0

    # general health [1=Excellent, 5=Poor]: worst symptom determines
    worst = max(fat, het, pem, dep)
    gen_health = float(np.clip(1.0 + worst * 4.0, 1.0, 5.0))

    # whq040 [1=want more, 2=want less, 3=same]:
    if wgt > 0.25:
        whq040 = 2.0   # want less weight
    elif wgt < -0.25:
        whq040 = 1.0   # want more weight
    else:
        whq040 = 3.0   # satisfied

    # med_count: correlated with symptom burden
    med_count = float(np.clip(0.5 + (fat + het + dep) * 2.0, 0.0, 8.0))

    # sbp/dbp: elevated for high heat_intolerance/fatigue
    sbp = 135.0 if (het > 0.65 or fat > 0.75) else 125.0 if (het > 0.45 or fat > 0.55) else 118.0
    dbp = 85.0 if (het > 0.65 or fat > 0.75) else 80.0 if (het > 0.45 or fat > 0.55) else 74.0

    # waist_cm: correlates with weight_change and bmi
    # For female: higher waist for perimenopause/inflammation profiles
    waist = float(np.clip(weight_kg * 0.55 + wgt * 15.0, 65.0, 130.0))

    # Nocturia: relates to kidney/electrolyte features
    nocturia = float(np.clip((1.0 - slp) * 2.5 + fat * 1.0, 0.0, 5.0))

    # urinary leakage: pelvic floor proxy via digestive/perimenopause
    # Higher dig/het = more leakage; [1=very often → 5=never]
    leakage_freq = float(np.clip(5.0 - (dig + het) * 2.5, 1.0, 5.0))

    # Alcohol: modest default; higher for hepatitis profiles
    avg_drinks = 1.5 if dig > 0.65 else 0.3

    # ── Smoking codes ──────────────────────────────────────────────────────
    if smoking == "current":
        smq040   = 1.0
        smoking_now_code = 1.0
        cigs_per_day = 10.0
        smoked_100 = 1.0
    elif smoking == "former":
        smq040   = 3.0
        smoking_now_code = 0.0
        cigs_per_day = 0.0
        smoked_100 = 1.0
    else:
        smq040   = 3.0
        smoking_now_code = 0.0
        cigs_per_day = 0.0
        smoked_100 = 2.0

    # ── Activity codes ─────────────────────────────────────────────────────
    if activity == "sedentary":
        vigorous_work  = 2.0
        vigorous_rec   = 2.0
        moderate_work  = 2.0
        moderate_rec   = 2.0
        vigorous_ex    = 2.0
        moderate_ex    = 2.0
        hours_worked   = 35.0
    elif activity == "high":
        vigorous_work  = 1.0
        vigorous_rec   = 1.0
        moderate_work  = 1.0
        moderate_rec   = 1.0
        vigorous_ex    = 1.0
        moderate_ex    = 1.0
        hours_worked   = 45.0
    elif activity == "moderate":
        vigorous_work  = 2.0
        vigorous_rec   = 2.0
        moderate_work  = 2.0
        moderate_rec   = 1.0
        vigorous_ex    = 2.0
        moderate_ex    = 1.0
        hours_worked   = 40.0
    else:  # low
        vigorous_work  = 2.0
        vigorous_rec   = 2.0
        moderate_work  = 2.0
        moderate_rec   = 2.0
        vigorous_ex    = 2.0
        moderate_ex    = 2.0
        hours_worked   = 38.0

    # ── Reproductive history (female) ─────────────────────────────────────
    if sex == "F":
        ever_pregnant  = 1.0
        n_pregnancies  = 2.0
        if age >= 55:
            regular_periods = 2.0    # No regular periods (post-menopausal)
            age_last_period = 51.0
            ever_hormones   = 1.0 if het > 0.55 else 2.0
        elif 40 <= age < 55:
            regular_periods = 2.0    # No regular periods (perimenopausal range)
            age_last_period = float(age - 2)
            ever_hormones   = 1.0 if het > 0.65 else 2.0
        else:
            regular_periods = 1.0    # Yes, regular periods
            age_last_period = 50.0
            ever_hormones   = 2.0
    else:
        ever_pregnant  = 2.0
        n_pregnancies  = 0.0
        regular_periods = 2.0
        age_last_period = 50.0
        ever_hormones   = 2.0

    # ── BP / medication history ────────────────────────────────────────────
    has_hbp = 1.0 if (het > 0.65 or fat > 0.75) else 2.0
    bp_rx   = 1.0 if (het > 0.70 or fat > 0.80) else 2.0

    # ── Lab values ────────────────────────────────────────────────────────
    chol = float(labs.get("total_cholesterol", 185.8))
    hdl  = float(labs.get("hdl", labs.get("hdl_cholesterol", 53.0)))
    ldl  = float(labs.get("ldl", labs.get("ldl_cholesterol", 110.0)))
    trig = float(labs.get("triglycerides", 108.0))
    gluc = float(labs.get("fasting_glucose", labs.get("glucose", 100.0)))
    wbc  = float(labs.get("wbc", 7.0))
    tp   = float(labs.get("total_protein", 7.0))

    # Derived signals from lab presence
    uacr = 5.0  # default normal

    # ── Assemble complete answers dict ─────────────────────────────────────
    answers = {
        # Demographics
        "age_years":   float(age),
        "gender":      gender_code,
        "gender_female": gender_female,
        "bmi":         bmi,
        "weight_kg":   weight_kg,
        "waist_cm":    waist,

        # Labs
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
        "glucose_mg_dl":            gluc,
        "uacr_mg_g":                uacr,
        "wbc_1000_cells_ul":        wbc,
        "wbc":                      wbc,
        "total_protein_g_dl":       tp,
        "total_protein":            tp,
        "sbp_mean":                 sbp,
        "dbp_mean":                 dbp,

        # Questionnaire — sleep
        "dpq040___feeling_tired_or_having_little_energy": dpq040,
        "dpq040_tired_little_energy":      dpq040,
        "feeling_tired_little_energy":     dpq040,
        "slq050___ever_told_doctor_had_trouble_sleeping?": slq050,
        "slq050_told_trouble_sleeping":    slq050,
        "told_dr_trouble_sleeping":        slq050,
        "trouble_sleeping":                slq050,
        "sld012___sleep_hours___weekdays_or_workdays": sld012,
        "sld012_sleep_hours_weekday":      sld012,
        "sleep_hours_weekdays":            sld012,
        "sld013___sleep_hours___weekends": sld013,
        "sld013_sleep_hours_weekend":      sld013,
        "slq030___how_often_do_you_snore?": snore,
        "pad680___minutes_sedentary_activity": pad680,
        "pad680_sedentary_minutes":        pad680,
        "sedentary_minutes":               pad680,

        # Questionnaire — fatigue/exertion
        "cdq010___shortness_of_breath_on_stairs/inclines": cdq010,
        "cdq010_sob_stairs":               cdq010,
        "huq010___general_health_condition": gen_health,
        "huq010_general_health":           gen_health,
        "general_health_condition":        gen_health,
        "general_health":                  gen_health,

        # Questionnaire — joints/pain
        "mcq160a___ever_told_you_had_arthritis": arthritis,
        "ever_told_arthritis":             arthritis,
        "mcq195___which_type_of_arthritis_was_it?": 2.0 if jnt > 0.50 else 3.0,

        # Questionnaire — cognitive/depressive
        "dpq030": dpq030,
        "dpq010": dpq010,
        "dpq020": dpq020,

        # Questionnaire — digestive/liver
        "mcq520___abdominal_pain_during_past_12_months?": abdom,
        "abdominal_pain":                  abdom,
        "mcq540___ever_seen_a_dr_about_this_pain": 1.0 if dig > 0.50 else 2.0,
        "saw_dr_for_pain":                 1.0 if dig > 0.50 else 2.0,
        "mcq160l___ever_told_you_had_any_liver_condition": 1.0 if dig > 0.65 else 2.0,
        "liver_condition":                 1.0 if dig > 0.65 else 2.0,
        "heq030___ever_told_you_have_hepatitis_c?": 1.0 if dig > 0.75 else 2.0,
        "ever_hepatitis_c":                1.0 if dig > 0.75 else 2.0,

        # Questionnaire — weight
        "whq040___like_to_weigh_more,_less_or_same": whq040,
        "mcq080___doctor_ever_said_you_were_overweight": 1.0 if wgt > 0.40 else 2.0,
        "doctor_said_overweight":          1.0 if wgt > 0.40 else 2.0,
        "dr_said_reduce_fat":              1.0 if wgt > 0.40 else 2.0,
        "tried_to_lose_weight":            1.0 if wgt > 0.30 else 2.0,

        # Medications
        "med_count":                       med_count,
        "mcq053___taking_treatment_for_anemia/past_3_mos": 2.0,
        "taking_anemia_treatment":         2.0,

        # Smoking
        "smq040___do_you_now_smoke_cigarettes?": smq040,
        "smoking_now":                     smoking_now_code,
        "smd650___avg_#_cigarettes/day_during_past_30_days": cigs_per_day,
        "avg_cigarettes_per_day":          cigs_per_day,
        "cigarettes_per_day":              cigs_per_day,
        "smq078___how_soon_after_waking_do_you_smoke": 4.0,  # N/A
        "smoked_100_cigs":                 smoked_100,

        # Alcohol
        "alq111___ever_had_a_drink_of_any_kind_of_alcohol": 1.0,
        "alq130___avg_#_alcoholic_drinks/day___past_12_mos": avg_drinks,
        "alq151___ever_have_4/5_or_more_drinks_every_day?": 2.0,
        "avg_drinks_per_day":              avg_drinks,
        "ever_heavy_drinker":              2.0,
        "ever_heavy_drinker_daily":        2.0,
        "alcohol_any_risk_signal":         0.0,

        # Activity
        "paq605___vigorous_work_activity": vigorous_work,
        "paq620___moderate_work_activity": moderate_work,
        "paq650___vigorous_recreational_activities": vigorous_rec,
        "paq665___moderate_recreational_activities": moderate_rec,
        "vigorous_exercise":               vigorous_ex,
        "moderate_exercise":               moderate_ex,
        "moderate_recreational":           moderate_rec,
        "ocq180___hours_worked_last_week_in_total_all_jobs": hours_worked,
        "hours_worked_per_week":           hours_worked,
        "ocq670___overall_work_schedule_past_3_months": 1.0,
        "overall_work_schedule":           1.0,
        "work_schedule":                   1.0,

        # Blood pressure
        "bpq020___ever_told_you_had_high_blood_pressure": has_hbp,
        "ever_told_high_bp":               has_hbp,
        "bpq030___told_had_high_blood_pressure___2+_times": has_hbp,
        "bpq040a___taking_prescription_for_hypertension": bp_rx,
        "bpq050a___now_taking_prescribed_medicine_for_hbp": bp_rx,
        "taking_bp_prescription":          bp_rx,
        "bpq080___doctor_told_you___high_cholesterol_level": 2.0,
        "ever_told_high_cholesterol":      2.0,
        "told_high_cholesterol":           2.0,

        # Diabetes
        "diq010___doctor_told_you_have_diabetes": 2.0,
        "ever_told_diabetes":              2.0,
        "diabetes":                        2.0,
        "diq050___taking_insulin_now":     2.0,
        "taking_insulin":                  2.0,
        "diq070___take_diabetic_pills_to_lower_blood_sugar": 2.0,
        "taking_diabetic_pills":           2.0,
        "takes_diabetes_pills":            2.0,
        "mcq300c___close_relative_had_diabetes": 2.0,

        # Cardiac history
        "mcq160b___ever_told_you_had_congestive_heart_failure": 2.0,
        "heart_failure":                   2.0,
        "ever_told_heart_failure":         2.0,
        "mcq160e___ever_told_you_had_heart_attack": 2.0,
        "ever_told_heart_attack":          2.0,
        "mcq160f___ever_told_you_had_stroke": 2.0,
        "ever_told_stroke":                2.0,

        # Asthma
        "mcq010___ever_been_told_you_have_asthma": 2.0,
        "mcq040___had_asthma_attack_in_past_year": 2.0,

        # Urinary/kidney
        "kiq480___how_many_times_urinate_in_night?": nocturia,
        "times_urinate_in_night":          nocturia,
        "kiq005___how_often_have_urinary_leakage?": leakage_freq,
        "how_often_urinary_leakage":       max(1.0, 5.0 - dig * 4.0),
        "kiq010___how_much_urine_lose_each_time?": 3.0,
        "kiq022___ever_told_you_had_weak/failing_kidneys?": 2.0,
        "kidney_disease":                  2.0,
        "kiq026___ever_had_kidney_stones?": 2.0,
        "ever_had_kidney_stones":          2.0,
        "kiq042___leak_urine_during_physical_activities?": 1.0 if dig > 0.45 else 2.0,
        "kiq044___urinated_before_reaching_the_toilet?": 1.0 if (1.0 - slp) > 0.55 else 2.0,
        "urinated_before_toilet":          1.0 if (1.0 - slp) > 0.55 else 2.0,
        "kiq052___how_much_were_daily_activities_affected?": 1.0 if pem > 0.55 else 4.0,
        "kiq430___how_frequently_does_this_occur?": max(1.0, leakage_freq),
        "kiq450___how_frequently_does_this_occur?": max(1.0, leakage_freq),

        # Blood transfusion / hepatitis
        "mcq092___ever_receive_blood_transfusion": 2.0,
        "ever_had_blood_transfusion":      2.0,
        "blood_transfusion":               2.0,

        # Reproductive
        "rhq031___had_regular_periods_in_past_12_months": regular_periods,
        "rhq031_regular_periods":          regular_periods,
        "regular_periods":                 regular_periods,
        "rhq060___age_at_last_menstrual_period": age_last_period,
        "rhq060_age_last_period":          age_last_period,
        "rhq540___ever_use_female_hormones?": ever_hormones,
        "rhq540_ever_hormones":            ever_hormones,
        "rhq131___ever_been_pregnant?":    ever_pregnant,
        "rhq160___how_many_times_have_been_pregnant?": n_pregnancies,
        "pregnancy_status":                2.0,  # not currently pregnant

        # Healthcare utilization
        "huq051___#times_receive_healthcare_over_past_year": float(np.clip(1.0 + med_count * 1.5, 0.0, 16.0)),
        "times_healthcare_past_year": float(np.clip(1.0 + med_count * 1.5, 0.0, 16.0)),
        "huq071___overnight_hospital_patient_in_last_year": 1.0 if dig > 0.70 else 2.0,
        "overnight_hospital":              1.0 if dig > 0.70 else 2.0,
        "hospitalized_lastyear":           1.0 if dig > 0.70 else 2.0,

        # Education / demographics
        "dmdeduc2":                        3.0,
        "education":                       3.0,
    }

    return answers


def _build_feature_vectors(profile: dict) -> dict[str, pd.DataFrame]:
    """
    Build per-condition DataFrames for ModelRunner.run_all().
    Uses build_feature_vectors() from questionnaire_to_model_features for the
    standard pipeline, then adds liver-specific aliases that the pipeline misses.
    """
    from models.questionnaire_to_model_features import (
        build_feature_vectors,
        _build_feature_dict,
        _build_condition_row,
    )

    answers = _build_answers(profile)
    vectors = build_feature_vectors(answers)

    # Liver model uses non-standard aliases not handled by the standard pipeline.
    # Build liver row manually with the custom alias values.
    feature_dict = _build_feature_dict(answers)
    for k, v in answers.items():
        feature_dict.setdefault(k, v)
    liver_row = _build_condition_row("liver", feature_dict)
    vectors["liver"] = pd.DataFrame([liver_row])

    return vectors


# ── Main scoring loop ──────────────────────────────────────────────────────────

def score_profiles(profiles_path: Path = PROFILES_PATH) -> dict:
    """Load profiles, score each through ML models, compute accuracy."""
    print(f"\nLoading profiles from {profiles_path} ...")
    with profiles_path.open() as f:
        profiles = json.load(f)

    print(f"Loaded {len(profiles)} profiles.")
    print("Loading models ...")
    runner = ModelRunner()
    print()

    results = []
    failed_count = 0

    for i, profile in enumerate(profiles):
        pid   = profile["profile_id"]
        ptype = profile["profile_type"]
        target = profile.get("target_condition")

        try:
            vectors = _build_feature_vectors(profile)
            scores  = runner.run_all(vectors)
        except Exception as exc:
            print(f"  ERROR scoring {pid}: {exc}")
            failed_count += 1
            continue

        # Rank all model outputs
        sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True) if scores else []
        top1_key = sorted_keys[0] if sorted_keys else None
        top3_keys = set(sorted_keys[:3])

        model_key = CONDITION_TO_MODEL_KEY.get(target) if target else None
        target_prob = scores.get(model_key) if model_key else None
        target_rank = sorted_keys.index(model_key) + 1 if (model_key and model_key in sorted_keys) else None
        is_top1 = (top1_key == model_key) if (model_key and top1_key) else False
        is_top3 = (model_key in top3_keys) if model_key else False

        results.append({
            "profile_id":       pid,
            "profile_type":     ptype,
            "target_condition": target,
            "model_key":        model_key,
            "scores":           scores,
            "top1_model":       top1_key,
            "target_prob":      target_prob,
            "target_rank":      target_rank,
            "is_top1":          is_top1,
            "is_top3":          is_top3,
        })

        if (i + 1) % 50 == 0:
            print(f"  ... scored {i+1}/{len(profiles)} profiles")

    print(f"\nScored {len(results)} profiles ({failed_count} errors)\n")

    # ── Per-condition accuracy ─────────────────────────────────────────────
    from collections import defaultdict
    positive_results = [r for r in results if r["profile_type"] == "positive"]
    by_condition: dict[str, list] = defaultdict(list)
    for r in positive_results:
        if r["target_condition"]:
            by_condition[r["target_condition"]].append(r)

    condition_stats: dict[str, dict] = {}

    print("=" * 100)
    print(f"  {'Condition':<25} {'N':>4}  {'Top-1 Acc':>9}  {'Top-3 Acc':>9}  {'Mean P(target)':>14}  {'Mean Rank':>9}  Status")
    print("=" * 100)

    for cond in sorted(by_condition.keys()):
        recs  = by_condition[cond]
        valid = [r for r in recs if r["target_prob"] is not None]
        top1  = [r for r in valid if r["is_top1"]]
        top3  = [r for r in valid if r["is_top3"]]
        acc   = len(top1) / len(valid) if valid else 0.0
        acc3  = len(top3) / len(valid) if valid else 0.0
        mean_p = float(np.mean([r["target_prob"] for r in valid])) if valid else 0.0
        ranks  = [r["target_rank"] for r in valid if r["target_rank"] is not None]
        mean_rank = float(np.mean(ranks)) if ranks else float("nan")

        if acc < 0.60:
            status = "UNDERFIT"
        elif acc > 0.95:
            status = "OVERFIT"
        else:
            status = "OK"

        print(f"  {cond:<25} {len(recs):>4}   {acc:>7.1%}   {acc3:>7.1%}   {mean_p:>12.4f}   {mean_rank:>7.1f}   {status}")

        condition_stats[cond] = {
            "n_positive":        len(recs),
            "n_with_model":      len(valid),
            "top1_accuracy":     round(acc, 4),
            "top3_accuracy":     round(acc3, 4),
            "mean_target_prob":  round(mean_p, 4),
            "mean_target_rank":  round(mean_rank, 2),
            "n_top1_correct":    len(top1),
            "n_top3_correct":    len(top3),
            "status":            status,
        }

    print("=" * 100)

    # ── Healthy profile check ──────────────────────────────────────────────
    healthy = [r for r in results if r["profile_type"] == "healthy"]
    healthy_flagged = []
    if healthy:
        print(f"\nHealthy profile check ({len(healthy)} profiles):")
        for r in healthy:
            high = {k: v for k, v in r["scores"].items() if v > 0.40}
            if high:
                top_c = max(high, key=lambda k: high[k])
                healthy_flagged.append({
                    "profile_id":  r["profile_id"],
                    "top_condition": top_c,
                    "top_score":   high[top_c],
                    "all_high":    high,
                })
        if healthy_flagged:
            for h in healthy_flagged:
                print(f"  {h['profile_id']}: {h['top_condition']}={h['top_score']:.3f}")
            print(f"  {len(healthy_flagged)}/{len(healthy)} healthy profiles had a condition > 0.40")
        else:
            print("  All healthy profiles scored < 0.40 on all conditions. PASS")

    # ── Overall model score means ──────────────────────────────────────────
    print("\n--- Model mean scores across ALL profiles ---")
    for mk in sorted(MODEL_REGISTRY.keys()):
        vals = [r["scores"][mk] for r in results if mk in r.get("scores", {})]
        if vals:
            print(f"  {mk:<22}  mean={np.mean(vals):.4f}  max={max(vals):.4f}  min={min(vals):.4f}")

    return {
        "n_profiles":       len(profiles),
        "n_scored":         len(results),
        "n_failed":         failed_count,
        "condition_stats":  condition_stats,
        "healthy_flagged":  healthy_flagged,
        "profile_results":  results,
    }


if __name__ == "__main__":
    summary = score_profiles()

    output = {
        "n_profiles":      summary["n_profiles"],
        "n_scored":        summary["n_scored"],
        "n_failed":        summary["n_failed"],
        "condition_stats": summary["condition_stats"],
        "healthy_flagged": summary["healthy_flagged"],
    }
    with RESULTS_PATH.open("w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {RESULTS_PATH}")
