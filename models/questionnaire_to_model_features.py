"""
questionnaire_to_model_features.py
----------------------------------
Transforms frontend questionnaire answers into:

1. A flat engineered feature dictionary.
2. Per-condition single-row DataFrames ready for models.model_runner.ModelRunner.

The frontend is expected to submit a flat dict keyed by the field_id values from
assessment_quiz/nhanes_combined_question_flow_v2.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from models.inference_preprocessor import InferencePreprocessor

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
PREPROCESSOR = InferencePreprocessor()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


THYROID_META = _load_json(MODELS_DIR / "thyroid_lr_l2_18feat_metadata.json")
KIDNEY_META = _load_json(MODELS_DIR / "kidney_lr_l2_routine_30feat_metadata.json")
LIVER_META = _load_json(MODELS_DIR / "liver_lr_l2_13feat_metadata.json")
ANEMIA_META = _load_json(MODELS_DIR / "anemia_combined_lr_metadata.json")
IRON_META = _load_json(MODELS_DIR / "iron_deficiency_checkup_lr_metadata.json")
PREDIABETES_META = _load_json(MODELS_DIR / "prediabetes_focused_quiz_demo_med_screening_labs_threshold_045.metadata.json")
SLEEP_META = _load_json(MODELS_DIR / "sleep_disorder_compact_quiz_demo_med_screening_labs_threshold_04.metadata.json")
ELECTROLYTES_META = _load_json(MODELS_DIR / "electrolyte_imbalance_compact_quiz_demo_med_screening_labs_threshold_05.metadata.json")
HEPATITIS_META = _load_json(MODELS_DIR / "hepatitis_rf_cal_33feat_metadata.json")
PERIMENO_META = _load_json(MODELS_DIR / "perimenopause_gradient_boosting_metadata.json")
INFLAMMATION_META = _load_json(MODELS_DIR / "inflammation_lr_l1_45feat_metadata.json")


MODEL_FEATURES = {
    "anemia": list(ANEMIA_META["feature_names"]),
    "iron_deficiency": list(IRON_META["feature_names"]),
    "thyroid": list(THYROID_META["all_features"]),
    "kidney": list(KIDNEY_META["all_features"]),
    "sleep_disorder": list(SLEEP_META["features"]),
    "liver": list(LIVER_META["all_features"]),
    "prediabetes": list(PREDIABETES_META["features"]),
    "inflammation": list(INFLAMMATION_META["feature_names"]),
    "electrolytes": list(ELECTROLYTES_META["features"]),
    "hepatitis": list(HEPATITIS_META["feature_names"]),
    "perimenopause": list(PERIMENO_META["features"]),
}


HELPER_ALIAS_MAP = {
    "avg_drinks_per_day": "alq130___avg_#_alcoholic_drinks/day___past_12_mos",
    "general_health_condition": "huq010___general_health_condition",
    "general_health": "huq010___general_health_condition",
    "told_dr_trouble_sleeping": "slq050___ever_told_doctor_had_trouble_sleeping?",
    "sleep_hours_weekdays": "sld012___sleep_hours___weekdays_or_workdays",
    "ever_told_diabetes": "diq010___doctor_told_you_have_diabetes",
    "diabetes": "diq010___doctor_told_you_have_diabetes",
    "doctor_said_overweight": "mcq080___doctor_ever_said_you_were_overweight",
    "moderate_recreational": "paq665___moderate_recreational_activities",
    "times_urinate_in_night": "kiq480___how_many_times_urinate_in_night?",
    "overall_work_schedule": "ocq670___overall_work_schedule_past_3_months",
    "work_schedule": "ocq670___overall_work_schedule_past_3_months",
    "ever_told_high_cholesterol": "bpq080___doctor_told_you___high_cholesterol_level",
    "told_high_cholesterol": "bpq080___doctor_told_you___high_cholesterol_level",
    "taking_anemia_treatment": "mcq053___taking_treatment_for_anemia/past_3_mos",
    "ever_told_high_bp": "bpq020___ever_told_you_had_high_blood_pressure",
    "taking_bp_prescription": "bpq040a___taking_prescription_for_hypertension",
    "bpq050a___now_taking_prescribed_medicine_for_hbp": "bpq040a___taking_prescription_for_hypertension",
    "education": "dmdeduc2",
    "taking_insulin": "diq050___taking_insulin_now",
    "taking_diabetic_pills": "diq070___take_diabetic_pills_to_lower_blood_sugar",
    "takes_diabetes_pills": "diq070___take_diabetic_pills_to_lower_blood_sugar",
    "how_often_urinary_leakage": "kiq005___how_often_have_urinary_leakage?",
    "urinated_before_toilet": "kiq044___urinated_before_reaching_the_toilet?",
    "ever_had_kidney_stones": "kiq026___ever_had_kidney_stones?",
    "ever_had_blood_transfusion": "mcq092___ever_receive_blood_transfusion",
    "blood_transfusion": "mcq092___ever_receive_blood_transfusion",
    "ever_told_arthritis": "mcq160a___ever_told_you_had_arthritis",
    "times_healthcare_past_year": "huq051___#times_receive_healthcare_over_past_year",
    "feeling_tired_little_energy": "dpq040___feeling_tired_or_having_little_energy",
    "overnight_hospital": "huq071___overnight_hospital_patient_in_last_year",
    "hospitalized_lastyear": "huq071___overnight_hospital_patient_in_last_year",
    "liver_condition": "mcq160l___ever_told_you_had_any_liver_condition",
    "kidney_disease": "kiq022___ever_told_you_had_weak/failing_kidneys?",
    "regular_periods": "rhq031___had_regular_periods_in_past_12_months",
    "hours_worked_per_week": "ocq180___hours_worked_last_week_in_total_all_jobs",
    "smoking_now": "smq040___do_you_now_smoke_cigarettes?",
    "cigarettes_per_day": "smd650___avg_#_cigarettes/day_during_past_30_days",
    "avg_cigarettes_per_day": "smd650___avg_#_cigarettes/day_during_past_30_days",
    "sedentary_minutes": "pad680___minutes_sedentary_activity",
    "cdq010_sob_stairs": "cdq010___shortness_of_breath_on_stairs/inclines",
    "abdominal_pain": "mcq520___abdominal_pain_during_past_12_months?",
    "saw_dr_for_pain": "mcq540___ever_seen_a_dr_about_this_pain",
    "ever_hepatitis_c": "heq030___ever_told_you_have_hepatitis_c?",
    "heart_failure": "mcq160b___ever_told_you_had_congestive_heart_failure",
    "ever_told_heart_failure": "mcq160b___ever_told_you_had_congestive_heart_failure",
    "ever_told_heart_attack": "mcq160e___ever_told_you_had_heart_attack",
    "ever_told_stroke": "mcq160f___ever_told_you_had_stroke",
    "rhq540_ever_hormones": "rhq540___ever_use_female_hormones?",
}


LAB_ALIAS_MAP = {
    "total_cholesterol_mg_dl": "total_cholesterol_mg_dl",
    "hdl_cholesterol_mg_dl": "hdl_cholesterol_mg_dl",
    "ldl_cholesterol_mg_dl": "ldl_cholesterol_mg_dl",
    "triglycerides_mg_dl": "triglycerides_mg_dl",
    "fasting_glucose_mg_dl": "fasting_glucose_mg_dl",
    "uacr_mg_g": "uacr_mg_g",
    "glucose": "glucose_mg_dl",
    "fasting_glucose": "fasting_glucose_mg_dl",
    "serum_glucose": "glucose_mg_dl",
    "total_cholesterol": "total_cholesterol_mg_dl",
    "cholesterol": "total_cholesterol_mg_dl",
    "hdl_cholesterol": "hdl_cholesterol_mg_dl",
    "hdl": "hdl_cholesterol_mg_dl",
    "ldl_cholesterol": "ldl_cholesterol_mg_dl",
    "triglycerides": "triglycerides_mg_dl",
    "total_protein": "total_protein_g_dl",
    "wbc": "wbc_1000_cells_ul",
}


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _clean(value: Any) -> Any:
    if _blank(value):
        return np.nan
    return value


def _to_binary_yes(code: Any) -> float:
    code = _clean(code)
    if pd.isna(code):
        return np.nan
    if int(code) == 1:
        return 1.0
    if int(code) in {2, 3}:
        return 0.0
    return np.nan


def _derive_heavy_drinker(answers: dict[str, Any]) -> float:
    alq151 = _clean(answers.get("alq151___ever_have_4/5_or_more_drinks_every_day?"))
    alq170 = _clean(answers.get("alq170_helper_times_4_5_drinks_one_occasion_30d"))
    if not pd.isna(alq151) and int(alq151) == 1:
        return 1.0
    if not pd.isna(alq170) and float(alq170) > 0:
        return 1.0
    if not pd.isna(alq151) and int(alq151) == 2 and (pd.isna(alq170) or float(alq170) == 0):
        return 0.0
    return np.nan


def _derive_alcohol_risk(answers: dict[str, Any], gender: Any) -> float:
    alq111 = _clean(answers.get("alq111___ever_had_a_drink_of_any_kind_of_alcohol"))
    alq130 = _clean(answers.get("alq130___avg_#_alcoholic_drinks/day___past_12_mos"))
    alq151 = _clean(answers.get("alq151___ever_have_4/5_or_more_drinks_every_day?"))
    alq170 = _clean(answers.get("alq170_helper_times_4_5_drinks_one_occasion_30d"))

    if not pd.isna(alq151) and int(alq151) == 1:
        return 1.0
    if not pd.isna(alq170) and float(alq170) > 0:
        return 1.0
    if not pd.isna(alq130):
        threshold = 4 if gender == 1 else 3
        if float(alq130) >= threshold:
            return 1.0
    if not pd.isna(alq111) and int(alq111) == 2:
        return 0.0
    if not pd.isna(alq111) and int(alq111) == 1 and not pd.isna(alq130) and float(alq130) == 0:
        return 0.0
    return np.nan


def _build_feature_dict(
    answers: dict[str, Any],
    *,
    normalized_for_retrained_models: bool = False,
) -> dict[str, Any]:
    source_row = PREPROCESSOR.prepare_feature_source(
        answers,
        normalized_for_retrained_models=normalized_for_retrained_models,
    )
    raw = {k: _clean(v) for k, v in source_row.items()}
    feat: dict[str, Any] = dict(raw)

    gender = raw.get("gender")
    feat["gender_female"] = 1.0 if gender == 2 else 0.0 if gender == 1 else np.nan

    for alias, source in HELPER_ALIAS_MAP.items():
        feat[alias] = raw.get(source, np.nan)

    for alias, source in LAB_ALIAS_MAP.items():
        feat[alias] = raw.get(source, np.nan)

    feat["ever_told_diabetes"] = _to_binary_yes(raw.get("diq010___doctor_told_you_have_diabetes"))
    feat["diabetes"] = feat["ever_told_diabetes"]
    feat["taking_insulin"] = _to_binary_yes(raw.get("diq050___taking_insulin_now"))
    feat["taking_diabetic_pills"] = _to_binary_yes(raw.get("diq070___take_diabetic_pills_to_lower_blood_sugar"))
    feat["takes_diabetes_pills"] = feat["taking_diabetic_pills"]
    feat["taking_bp_prescription"] = _to_binary_yes(raw.get("bpq040a___taking_prescription_for_hypertension"))
    feat["smoking_now"] = 1.0 if raw.get("smq040___do_you_now_smoke_cigarettes?") in {1, 2} else 0.0 if raw.get("smq040___do_you_now_smoke_cigarettes?") == 3 else np.nan
    feat["ever_heavy_drinker"] = _derive_heavy_drinker(raw)
    feat["alcohol_any_risk_signal"] = _derive_alcohol_risk(raw, gender)
    feat["moderate_exercise"] = (
        1.0 if raw.get("paq620___moderate_work_activity") == 1 or raw.get("paq665___moderate_recreational_activities") == 1
        else 0.0 if raw.get("paq620___moderate_work_activity") in {2} and raw.get("paq665___moderate_recreational_activities") in {2}
        else np.nan
    )
    feat["vigorous_exercise"] = (
        1.0 if raw.get("paq605___vigorous_work_activity") == 1 or raw.get("paq650___vigorous_recreational_activities") == 1
        else 0.0 if raw.get("paq605___vigorous_work_activity") in {2} and raw.get("paq650___vigorous_recreational_activities") in {2}
        else np.nan
    )

    # Model-specific short aliases
    feat["dpq040_tired_little_energy"] = raw.get("dpq040___feeling_tired_or_having_little_energy", np.nan)
    feat["huq010_general_health"] = raw.get("huq010___general_health_condition", np.nan)
    feat["sld012_sleep_hours_weekday"] = raw.get("sld012___sleep_hours___weekdays_or_workdays", np.nan)
    feat["sld013_sleep_hours_weekend"] = raw.get("sld013___sleep_hours___weekends", np.nan)
    feat["slq050_told_trouble_sleeping"] = raw.get("slq050___ever_told_doctor_had_trouble_sleeping?", np.nan)
    feat["pad680_sedentary_minutes"] = raw.get("pad680___minutes_sedentary_activity", np.nan)
    feat["rhq031_regular_periods"] = raw.get("rhq031___had_regular_periods_in_past_12_months", np.nan)
    feat["rhq060_age_last_period"] = raw.get("rhq060___age_at_last_menstrual_period", np.nan)
    feat["rhq540_ever_hormones"] = raw.get("rhq540___ever_use_female_hormones?", np.nan)
    feat["cdq010_sob_stairs"] = raw.get("cdq010___shortness_of_breath_on_stairs/inclines", np.nan)
    feat["total_protein_g_dl"] = raw.get("total_protein_g_dl", np.nan)
    feat["wbc_1000_cells_ul"] = raw.get("wbc_1000_cells_ul", np.nan)

    return feat


def _add_miss_flags(features: dict[str, Any], expected_features: list[str]) -> dict[str, Any]:
    out = dict(features)
    for col in expected_features:
        if not col.endswith("_miss"):
            continue
        base = col[:-5]
        base_value = out.get(base, np.nan)
        out[col] = 1 if _blank(base_value) or pd.isna(base_value) else 0
    return out


def _build_condition_row(condition: str, feature_dict: dict[str, Any]) -> dict[str, Any]:
    expected = MODEL_FEATURES[condition]
    enriched = _add_miss_flags(feature_dict, expected)
    row: dict[str, Any] = {}
    for col in expected:
        row[col] = enriched.get(col, np.nan)
    return row


def build_feature_vectors(
    answers: dict[str, Any],
    *,
    normalized_for_retrained_models: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Convert frontend questionnaire answers into per-condition feature vectors.

    Parameters
    ----------
    answers : dict
        Flat dictionary keyed by field_id from nhanes_combined_question_flow_v2.json.

    Returns
    -------
    dict[str, pd.DataFrame]
        One single-row DataFrame per condition, ready for ModelRunner.
    """
    features = _build_feature_dict(
        answers,
        normalized_for_retrained_models=normalized_for_retrained_models,
    )
    return {
        condition: pd.DataFrame([_build_condition_row(condition, features)])
        for condition in MODEL_FEATURES
    }


def build_engineered_feature_dict(
    answers: dict[str, Any],
    *,
    normalized_for_retrained_models: bool = False,
) -> dict[str, Any]:
    """
    Return the flat engineered feature dictionary before condition-specific slicing.
    """
    features = _build_feature_dict(
        answers,
        normalized_for_retrained_models=normalized_for_retrained_models,
    )
    all_expected = sorted({c for cols in MODEL_FEATURES.values() for c in cols})
    return _add_miss_flags(features, all_expected)


if __name__ == "__main__":
    sample_answers = {
        "age_years": 48,
        "gender": 2,
        "huq010___general_health_condition": 3,
        "slq050___ever_told_doctor_had_trouble_sleeping?": 1,
        "alq111___ever_had_a_drink_of_any_kind_of_alcohol": 1,
        "alq130___avg_#_alcoholic_drinks/day___past_12_mos": 1,
        "bpq020___ever_told_you_had_high_blood_pressure": 1,
        "bpq040a___taking_prescription_for_hypertension": 1,
        "diq010___doctor_told_you_have_diabetes": 2,
        "dpq040___feeling_tired_or_having_little_energy": 1,
        "sld012___sleep_hours___weekdays_or_workdays": 6,
        "sld013___sleep_hours___weekends": 7,
        "slq030___how_often_do_you_snore?": 3,
        "weight_kg": 72,
        "waist_cm": 88,
        "bmi": 27.5,
    }

    vectors = build_feature_vectors(sample_answers)
    print("Built conditions:", list(vectors.keys()))
    print(vectors["thyroid"].to_string(index=False))
