from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path("/Users/annaesakova/aipm/halfFull")
sys.path.insert(0, str(ROOT))

from scripts.build_nhanes_feature_artifacts import (  # noqa: E402
    ALIAS_MAP,
    load_dataset_columns,
    load_lab_names,
    load_question_labels,
    resolve_feature,
)


SOURCE_MATRIX = Path("/Users/annaesakova/Downloads/HalfFull roadmap - diseases VS features.csv")
WORKSPACE_OUT = ROOT / "data/processed/HalfFull roadmap - diseases VS features.updated.csv"


EXTRA_ALIAS_MAP: dict[str, dict[str, Any]] = {
    "ldl_cholesterol_mg_dl": {
        "canonical_key": "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
        "mapped_dataset_column": "LBDLDL_ldl_cholesterol_friedewald_mg_dl",
        "nhanes_code": "LBDLDL",
        "feature_type": "lab",
        "notes": "Alias normalized to calculated LDL cholesterol.",
    },
    "dpq040_tired_little_energy": {
        "canonical_key": "dpq040___feeling_tired_or_having_little_energy",
        "mapped_dataset_column": "dpq040___feeling_tired_or_having_little_energy",
        "nhanes_code": "DPQ040",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to fatigue item.",
    },
    "huq010_general_health": {
        "canonical_key": "huq010___general_health_condition",
        "mapped_dataset_column": "huq010___general_health_condition",
        "nhanes_code": "HUQ010",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to general health item.",
    },
    "cdq010_sob_stairs": {
        "canonical_key": "cdq010___shortness_of_breath_on_stairs/inclines",
        "mapped_dataset_column": "cdq010___shortness_of_breath_on_stairs/inclines",
        "nhanes_code": "CDQ010",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to shortness-of-breath-on-stairs item.",
    },
    "sld012_sleep_hours_weekday": {
        "canonical_key": "sld012___sleep_hours___weekdays_or_workdays",
        "mapped_dataset_column": "sld012___sleep_hours___weekdays_or_workdays",
        "nhanes_code": "SLD012",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to weekday sleep hours.",
    },
    "sld013_sleep_hours_weekend": {
        "canonical_key": "sld013___sleep_hours___weekends",
        "mapped_dataset_column": "sld013___sleep_hours___weekends",
        "nhanes_code": "SLD013",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to weekend sleep hours.",
    },
    "slq050_told_trouble_sleeping": {
        "canonical_key": "slq050___ever_told_doctor_had_trouble_sleeping?",
        "mapped_dataset_column": "slq050___ever_told_doctor_had_trouble_sleeping?",
        "nhanes_code": "SLQ050",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to doctor-told-trouble-sleeping item.",
    },
    "pad680_sedentary_minutes": {
        "canonical_key": "pad680___minutes_sedentary_activity",
        "mapped_dataset_column": "pad680___minutes_sedentary_activity",
        "nhanes_code": "PAD680",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to sedentary minutes.",
    },
    "rhq031_regular_periods": {
        "canonical_key": "rhq031___had_regular_periods_in_past_12_months",
        "mapped_dataset_column": "rhq031___had_regular_periods_in_past_12_months",
        "nhanes_code": "RHQ031",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to regular periods item.",
    },
    "rhq060_age_last_period": {
        "canonical_key": "rhq060___age_at_last_menstrual_period",
        "mapped_dataset_column": "rhq060___age_at_last_menstrual_period",
        "nhanes_code": "RHQ060",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to age at last menstrual period.",
    },
    "rhq540_ever_hormones": {
        "canonical_key": "rhq540___ever_use_female_hormones?",
        "mapped_dataset_column": "rhq540___ever_use_female_hormones?",
        "nhanes_code": "RHQ540",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to female hormone use item.",
    },
    "trouble_sleeping": {
        "canonical_key": "slq050___ever_told_doctor_had_trouble_sleeping?",
        "mapped_dataset_column": "slq050___ever_told_doctor_had_trouble_sleeping?",
        "nhanes_code": "SLQ050",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to trouble sleeping item.",
    },
    "takes_diabetes_pills": {
        "canonical_key": "diq070___take_diabetic_pills_to_lower_blood_sugar",
        "mapped_dataset_column": "diq070___take_diabetic_pills_to_lower_blood_sugar",
        "nhanes_code": "DIQ070",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to diabetic pills item.",
    },
    "ever_heavy_drinker_daily": {
        "canonical_key": "alq151___ever_have_4/5_or_more_drinks_every_day?",
        "mapped_dataset_column": "alq151___ever_have_4/5_or_more_drinks_every_day?",
        "nhanes_code": "ALQ151",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to daily heavy drinking item.",
    },
    "dr_said_reduce_fat": {
        "canonical_key": "mcq366d___doctor_told_to_reduce_fat_in_diet",
        "mapped_dataset_column": "mcq366d___doctor_told_to_reduce_fat_in_diet",
        "nhanes_code": "MCQ366D",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to doctor-advised reduce-fat item.",
    },
    "saw_dr_for_pain": {
        "canonical_key": "mcq540___ever_seen_a_dr_about_this_pain",
        "mapped_dataset_column": "mcq540___ever_seen_a_dr_about_this_pain",
        "nhanes_code": "MCQ540",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to saw-doctor-for-pain item.",
    },
    "abdominal_pain": {
        "canonical_key": "mcq520___abdominal_pain_during_past_12_months?",
        "mapped_dataset_column": "mcq520___abdominal_pain_during_past_12_months?",
        "nhanes_code": "MCQ520",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to abdominal pain item.",
    },
    "overnight_hospital": {
        "canonical_key": "huq071___overnight_hospital_patient_in_last_year",
        "mapped_dataset_column": "huq071___overnight_hospital_patient_in_last_year",
        "nhanes_code": "HUQ071",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to overnight hospitalization item.",
    },
    "ever_hepatitis_c": {
        "canonical_key": "heq030___ever_told_you_have_hepatitis_c?",
        "mapped_dataset_column": "heq030___ever_told_you_have_hepatitis_c?",
        "nhanes_code": "HEQ030",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to hepatitis C history item.",
    },
    "heart_failure": {
        "canonical_key": "mcq160b___ever_told_you_had_congestive_heart_failure",
        "mapped_dataset_column": "mcq160b___ever_told_you_had_congestive_heart_failure",
        "nhanes_code": "MCQ160B",
        "feature_type": "questionnaire",
        "notes": "Alias normalized to heart failure item.",
    },
    "alcohol_any_risk_signal": {
        "canonical_key": "alcohol_any_risk_signal",
        "mapped_dataset_column": "alcohol_any_risk_signal",
        "nhanes_code": "ALQ111/130/151/170-derived",
        "feature_type": "derived-questionnaire",
        "notes": "Derived alcohol-risk composite used by compact electrolyte model.",
    },
}


MODEL_CONFIG = {
    "thyroid": ("models/thyroid_lr_l2_18feat_metadata.json", "base_features"),
    "kidney": ("models/kidney_lr_l2_routine_30feat_metadata.json", "all_features"),
    "sleep_disorder": ("models/sleep_disorder_compact_quiz_demo_med_screening_labs_threshold_04.metadata.json", "features"),
    "anemia": ("models/anemia_combined_lr_metadata.json", "feature_names"),
    "liver": ("models/liver_lr_l2_13feat_metadata.json", "all_features"),
    "prediabetes": ("models/prediabetes_focused_quiz_demo_med_screening_labs_threshold_045.metadata.json", "features"),
    "hidden_inflammation": ("models/inflammation_lr_l1_45feat_metadata.json", "nonzero_features"),
    "electrolytes": ("models/electrolyte_imbalance_compact_quiz_demo_med_screening_labs_threshold_05.metadata.json", "features"),
    "hepatitis_bc": ("models/hepatitis_rf_cal_33feat_metadata.json", "feature_names"),
    "perimenopause": ("models/perimenopause_gradient_boosting_metadata.json", "features"),
    "iron_deficiency": ("models/iron_deficiency_checkup_lr_metadata.json", "feature_names"),
}


def load_model_features() -> dict[str, list[str]]:
    disease_to_features: dict[str, list[str]] = {}
    for disease, (rel_path, key) in MODEL_CONFIG.items():
        p = ROOT / rel_path
        with p.open() as f:
            data = json.load(f)
        feats = list(data[key])
        disease_to_features[disease] = feats
    return disease_to_features


def resolve_with_extra(raw_feature: str, dataset_columns, question_labels, lab_labels) -> dict[str, Any]:
    if raw_feature in EXTRA_ALIAS_MAP:
        existing = ALIAS_MAP.get(raw_feature)
        ALIAS_MAP[raw_feature] = EXTRA_ALIAS_MAP[raw_feature]
        resolved = resolve_feature(raw_feature, dataset_columns, question_labels, lab_labels)
        if existing is None:
            ALIAS_MAP.pop(raw_feature, None)
        else:
            ALIAS_MAP[raw_feature] = existing
        return resolved
    return resolve_feature(raw_feature, dataset_columns, question_labels, lab_labels)


def read_matrix() -> tuple[list[str], list[str], list[dict[str, str]]]:
    with SOURCE_MATRIX.open(newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    count_row = rows[0]
    header = rows[1]
    data_rows = [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in rows[2:]]
    return count_row, header, data_rows


def build_updated_rows() -> tuple[list[str], list[str], list[dict[str, str]], dict[str, str]]:
    count_row, header, rows = read_matrix()
    disease_to_features = load_model_features()
    dataset_columns = load_dataset_columns()
    question_labels = load_question_labels()
    lab_labels = load_lab_names()

    if "menopause" in header:
        idx = header.index("menopause")
        header[idx] = "perimenopause"
        if idx < len(count_row):
            count_row[idx] = ""
        for row in rows:
            row["perimenopause"] = row.pop("menopause", "")

    if "iron_deficiency" not in header:
        insert_at = len(header)
        header.insert(insert_at, "iron_deficiency")
        if insert_at <= len(count_row):
            count_row.insert(insert_at, "")
        else:
            count_row.append("")
        for row in rows:
            row["iron_deficiency"] = ""

    disease_columns = [col for col in header if col in disease_to_features]

    row_map = {row["canonical_feature"]: row for row in rows}

    for disease in disease_columns:
        for row in rows:
            row[disease] = "0"

    for disease, features in disease_to_features.items():
        for raw_feature in features:
            resolved = resolve_with_extra(raw_feature, dataset_columns, question_labels, lab_labels)
            key = resolved["canonical_key"]
            if key not in row_map:
                new_row = {col: "" for col in header}
                new_row["canonical_feature"] = key
                new_row["display_label"] = resolved["display_label"]
                new_row["mapped_dataset_column"] = resolved["mapped_dataset_column"]
                new_row["nhanes_code_match"] = resolved["nhanes_code"]
                new_row["feature_type"] = resolved["feature_type"]
                new_row["exclude"] = ""
                new_row["source_feature_names"] = raw_feature
                new_row["notes"] = resolved["notes"]
                for dcol in disease_columns:
                    new_row[dcol] = "0"
                row_map[key] = new_row
                rows.append(new_row)
            else:
                existing_sources = {s.strip() for s in row_map[key].get("source_feature_names", "").split("|") if s.strip()}
                existing_sources.add(raw_feature)
                row_map[key]["source_feature_names"] = " | ".join(sorted(existing_sources))
            row_map[key][disease] = "1"

    for row in rows:
        disease_sum = sum(int(row.get(col) or 0) for col in disease_columns)
        row["sum"] = str(disease_sum)

    counts = {disease: str(sum(int(row.get(disease) or 0) for row in rows)) for disease in disease_columns}
    for idx, col in enumerate(header):
        if col in counts:
            count_row[idx] = counts[col]
        elif col == "sum":
            count_row[idx] = ""
        elif idx >= len(count_row):
            count_row.append("")

    rows.sort(key=lambda r: r["canonical_feature"])
    return count_row, header, rows, counts


def write_output() -> dict[str, str]:
    count_row, header, rows, counts = build_updated_rows()
    with WORKSPACE_OUT.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(count_row)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(col, "") for col in header])
    return counts


if __name__ == "__main__":
    counts = write_output()
    print(f"Wrote {WORKSPACE_OUT}")
    print(json.dumps(counts, indent=2, sort_keys=True))
