from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


INPUT_FILE = Path("data/processed/nhanes_merged_adults_final.csv")
OUTPUT_FILE = Path("data/processed/nhanes_merged_adults_final_normalized.csv")
ACTIONS_FILE = Path("data/processed/nhanes_merged_adults_final_normalization_actions.csv")
REFERENCES_FILE = Path("data/processed/nhanes_reference_ranges_used.csv")
METADATA_FILE = Path("data/processed/nhanes_hybrid_normalizer_metadata.json")
NORMALIZER_FILE = Path("models/nhanes_hybrid_normalizer.joblib")

DIETARY_COLUMNS = [
    "calories",
    "protein",
    "carbs",
    "fat",
    "iron",
    "vitamin_b12",
    "vitamin_d",
    "folate",
    "magnesium",
    "zinc",
]

PROTECTED_COLUMNS = {
    "SEQN",
    "age_years",
    "gender",
    "survey_psu",
    "survey_stratum",
    "nan_group",
}

CATEGORICAL_NAME_HINTS = (
    "comment_code",
    "_comment_code",
    "_comment",
    "_comt",
    "_cmt",
    "_code",
    "_flag",
    "_status",
    "status_",
    "questionnaire_mode_flag",
    "unit_of_measure",
)

AGE_BINS = [18, 30, 40, 50, 60, 66]
AGE_LABELS = ["18_29", "30_39", "40_49", "50_59", "60_65"]


@dataclass
class ReferenceSpec:
    name: str
    aliases: list[str]
    method: str
    source_label: str
    source_url: str
    note: str
    rules: list[dict[str, Any]] = field(default_factory=list)


REFERENCE_SPECS: list[ReferenceSpec] = [
    ReferenceSpec(
        name="hemoglobin_g_dl",
        aliases=["LBXHGB_hemoglobin_g_dl"],
        method="interval",
        source_label="Beutler & Waalen 2019 (NHANES 1999-2012)",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6306047/",
        note="2.5th-97.5th percentile reference intervals.",
        rules=[
            {"sex": "Male", "age_min": 20, "age_max": 35, "lower": 13.5, "upper": 17.5},
            {"sex": "Male", "age_min": 36, "age_max": 55, "lower": 13.5, "upper": 17.3},
            {"sex": "Male", "age_min": 56, "age_max": 79, "lower": 12.4, "upper": 17.3},
            {"sex": "Female", "age_min": 20, "age_max": 25, "lower": 11.1, "upper": 15.4},
            {"sex": "Female", "age_min": 26, "age_max": 30, "lower": 11.1, "upper": 15.2},
            {"sex": "Female", "age_min": 31, "age_max": 40, "lower": 10.6, "upper": 15.2},
            {"sex": "Female", "age_min": 41, "age_max": 45, "lower": 10.6, "upper": 15.5},
            {"sex": "Female", "age_min": 46, "age_max": 50, "lower": 10.6, "upper": 15.9},
            {"sex": "Female", "age_min": 51, "age_max": 79, "lower": 11.4, "upper": 15.9},
        ],
    ),
    ReferenceSpec(
        name="hematocrit_pct",
        aliases=["LBXHCT_hematocrit"],
        method="interval",
        source_label="Beutler & Waalen 2019 (NHANES 1999-2012)",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6306047/",
        note="2.5th-97.5th percentile reference intervals.",
        rules=[
            {"sex": "Male", "age_min": 20, "age_max": 35, "lower": 40.2, "upper": 51.0},
            {"sex": "Male", "age_min": 36, "age_max": 60, "lower": 38.8, "upper": 51.0},
            {"sex": "Male", "age_min": 61, "age_max": 70, "lower": 37.0, "upper": 51.0},
            {"sex": "Male", "age_min": 71, "age_max": 79, "lower": 35.0, "upper": 51.0},
            {"sex": "Female", "age_min": 20, "age_max": 45, "lower": 32.5, "upper": 45.2},
            {"sex": "Female", "age_min": 46, "age_max": 50, "lower": 32.5, "upper": 46.8},
            {"sex": "Female", "age_min": 51, "age_max": 79, "lower": 34.2, "upper": 46.8},
        ],
    ),
    ReferenceSpec(
        name="rbc_million_cells_ul",
        aliases=["LBXRBCSI_red_blood_cell_count_million_cells_ul"],
        method="interval",
        source_label="Beutler & Waalen 2019 (NHANES 1999-2012)",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6306047/",
        note="2.5th-97.5th percentile reference intervals.",
        rules=[
            {"sex": "Male", "age_min": 20, "age_max": 35, "lower": 4.42, "upper": 5.82},
            {"sex": "Male", "age_min": 36, "age_max": 50, "lower": 4.23, "upper": 5.82},
            {"sex": "Male", "age_min": 51, "age_max": 60, "lower": 4.23, "upper": 5.69},
            {"sex": "Male", "age_min": 61, "age_max": 79, "lower": 3.90, "upper": 5.69},
            {"sex": "Female", "age_min": 20, "age_max": 79, "lower": 3.72, "upper": 5.20},
        ],
    ),
    ReferenceSpec(
        name="wbc_1000_cells_ul",
        aliases=["LBXWBCSI_white_blood_cell_count_1000_cells_ul"],
        method="interval",
        source_label="StatPearls WBC reference range",
        source_url="https://www.ncbi.nlm.nih.gov/books/NBK604207/",
        note="Adult clinical reference interval; not NHANES-specific.",
        rules=[{"lower": 4.5, "upper": 11.0}],
    ),
    ReferenceSpec(
        name="platelet_1000_cells_ul",
        aliases=["LBXPLTSI_platelet_count_1000_cells_ul"],
        method="interval",
        source_label="NHANES III platelet analysis",
        source_url="https://ashpublications.org/blood/article/104/11/3937/78171/",
        note="Sex- and age-specific platelet intervals summarized from NHANES III findings.",
        rules=[
            {"sex": "Male", "age_min": 15, "age_max": 64, "lower": 120.0, "upper": 369.0},
            {"sex": "Male", "age_min": 65, "age_max": 120, "lower": 112.0, "upper": 361.0},
            {"sex": "Female", "age_min": 15, "age_max": 64, "lower": 136.0, "upper": 436.0},
            {"sex": "Female", "age_min": 65, "age_max": 120, "lower": 119.0, "upper": 396.0},
        ],
    ),
    ReferenceSpec(
        name="mcv_fl",
        aliases=["LBXMCVSI_mean_cell_volume_fl"],
        method="interval",
        source_label="Beutler & Waalen 2019 (NHANES 1999-2012)",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6306047/",
        note="2.5th-97.5th percentile reference intervals.",
        rules=[
            {"sex": "Male", "age_min": 20, "age_max": 50, "lower": 81.2, "upper": 97.3},
            {"sex": "Male", "age_min": 51, "age_max": 79, "lower": 81.2, "upper": 100.0},
            {"sex": "Female", "age_min": 20, "age_max": 40, "lower": 75.9, "upper": 97.4},
            {"sex": "Female", "age_min": 41, "age_max": 55, "lower": 71.6, "upper": 99.2},
            {"sex": "Female", "age_min": 56, "age_max": 79, "lower": 79.7, "upper": 99.2},
        ],
    ),
    ReferenceSpec(
        name="mch_pg",
        aliases=["LBXMCHSI_mean_cell_hemoglobin_pg"],
        method="interval",
        source_label="Beutler & Waalen 2019 (NHANES 1999-2012)",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6306047/",
        note="2.5th-97.5th percentile reference intervals.",
        rules=[
            {"sex": "Male", "age_min": 20, "age_max": 35, "lower": 27.1, "upper": 33.4},
            {"sex": "Male", "age_min": 36, "age_max": 50, "lower": 27.1, "upper": 34.0},
            {"sex": "Male", "age_min": 51, "age_max": 75, "lower": 27.1, "upper": 34.5},
            {"sex": "Male", "age_min": 76, "age_max": 79, "lower": 24.8, "upper": 34.5},
            {"sex": "Female", "age_min": 20, "age_max": 40, "lower": 24.7, "upper": 33.7},
            {"sex": "Female", "age_min": 41, "age_max": 79, "lower": 24.7, "upper": 34.3},
        ],
    ),
    ReferenceSpec(
        name="fasting_glucose_mg_dl",
        aliases=["fasting_glucose_mg_dl", "LBXGLU_fasting_glucose_mg_dl"],
        method="upper_only",
        source_label="ADA Standards of Care 2025",
        source_url="https://diabetesjournals.org/care/article/48/Supplement_1/S27/157566/",
        note="Normal fasting glucose cutoff <100 mg/dL.",
        rules=[{"upper": 100.0, "scale": 100.0}],
    ),
    ReferenceSpec(
        name="hba1c_pct",
        aliases=["LBXGH_glycohemoglobin"],
        method="upper_only",
        source_label="ADA Standards of Care 2025",
        source_url="https://diabetesjournals.org/care/article/48/Supplement_1/S27/157566/",
        note="Normal HbA1c cutoff <5.7%.",
        rules=[{"upper": 5.7, "scale": 5.7}],
    ),
    ReferenceSpec(
        name="serum_creatinine_mg_dl",
        aliases=["serum_creatinine_mg_dl", "LBXSCR_creatinine_refrigerated_serum_mg_dl"],
        method="interval",
        source_label="NIH Clinical Methods creatinine interval",
        source_url="https://www.ncbi.nlm.nih.gov/books/NBK305/",
        note="Adult sex-specific reference intervals; dataset age range is 18-65 so elderly rule is not used here.",
        rules=[
            {"sex": "Male", "age_min": 18, "age_max": 69, "lower": 0.6, "upper": 1.2},
            {"sex": "Female", "age_min": 18, "age_max": 69, "lower": 0.5, "upper": 1.1},
        ],
    ),
    ReferenceSpec(
        name="bun_mg_dl",
        aliases=["bun_mg_dl"],
        method="interval",
        source_label="NIH Clinical Methods BUN interval",
        source_url="https://www.ncbi.nlm.nih.gov/books/NBK305/",
        note="General adult reference interval.",
        rules=[{"lower": 5.0, "upper": 20.0}],
    ),
    ReferenceSpec(
        name="sodium_mmol_l",
        aliases=["LBXSNASI_sodium_mmol_l"],
        method="interval",
        source_label="ACCP lab values table",
        source_url="https://www.accp.com/docs/sap/Lab_Values_Table_PSAP.pdf",
        note="General adult reference interval.",
        rules=[{"lower": 135.0, "upper": 145.0}],
    ),
    ReferenceSpec(
        name="potassium_mmol_l",
        aliases=["LBXSKSI_potassium_mmol_l"],
        method="interval",
        source_label="ACCP lab values table",
        source_url="https://www.accp.com/docs/sap/Lab_Values_Table_PSAP.pdf",
        note="General adult reference interval.",
        rules=[{"lower": 3.5, "upper": 5.0}],
    ),
    ReferenceSpec(
        name="bicarbonate_mmol_l",
        aliases=["LBXSC3SI_bicarbonate_mmol_l"],
        method="interval",
        source_label="ACCP lab values table",
        source_url="https://www.accp.com/docs/sap/Lab_Values_Table_PSAP.pdf",
        note="General adult reference interval.",
        rules=[{"lower": 23.0, "upper": 29.0}],
    ),
    ReferenceSpec(
        name="calcium_mg_dl",
        aliases=["LBXSCA_total_calcium_mg_dl"],
        method="interval",
        source_label="MedlinePlus CMP",
        source_url="https://medlineplus.gov/lab-tests/comprehensive-metabolic-panel-cmp/",
        note="General adult reference interval.",
        rules=[{"lower": 8.5, "upper": 10.2}],
    ),
    ReferenceSpec(
        name="total_protein_g_dl",
        aliases=["LBXSTP_total_protein_g_dl"],
        method="interval",
        source_label="MedlinePlus total protein interval",
        source_url="https://medlineplus.gov/ency/article/003468.htm",
        note="General adult reference interval.",
        rules=[{"lower": 6.0, "upper": 8.3}],
    ),
    ReferenceSpec(
        name="serum_albumin_g_dl",
        aliases=["serum_albumin_g_dl", "LBXSAL_albumin_refrigerated_serum_g_dl"],
        method="interval",
        source_label="MedlinePlus albumin interval",
        source_url="https://medlineplus.gov/ency/article/003468.htm",
        note="General adult reference interval.",
        rules=[{"lower": 3.4, "upper": 5.4}],
    ),
    ReferenceSpec(
        name="alt_u_l",
        aliases=["alt_u_l", "LBXSATSI_alanine_aminotransferase_alt_u_l"],
        method="interval",
        source_label="ACG abnormal liver chemistries guideline",
        source_url="https://pubmed.ncbi.nlm.nih.gov/27995906/",
        note="Lab upper-limit reference intervals used for transform.",
        rules=[
            {"sex": "Male", "lower": 7.0, "upper": 56.0},
            {"sex": "Female", "lower": 7.0, "upper": 45.0},
        ],
    ),
    ReferenceSpec(
        name="ast_u_l",
        aliases=["ast_u_l", "LBXSASSI_aspartate_aminotransferase_ast_u_l"],
        method="interval",
        source_label="ACG abnormal liver chemistries guideline",
        source_url="https://pubmed.ncbi.nlm.nih.gov/27995906/",
        note="Sex-specific AST reference intervals.",
        rules=[
            {"sex": "Male", "lower": 10.0, "upper": 40.0},
            {"sex": "Female", "lower": 10.0, "upper": 30.0},
        ],
    ),
    ReferenceSpec(
        name="ggt_u_l",
        aliases=["ggt_u_l", "LBXSGTSI_gamma_glutamyl_transferase_ggt_iu_l"],
        method="interval",
        source_label="GGT reference review",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC8637680/",
        note="Sex-specific adult GGT reference intervals.",
        rules=[
            {"sex": "Male", "lower": 8.0, "upper": 50.0},
            {"sex": "Female", "lower": 5.0, "upper": 35.0},
        ],
    ),
    ReferenceSpec(
        name="alp_u_l",
        aliases=["alp_u_l", "LBXSAPSI_alkaline_phosphatase_alp_iu_l"],
        method="interval",
        source_label="ACG abnormal liver chemistries guideline",
        source_url="https://pubmed.ncbi.nlm.nih.gov/27995906/",
        note="Sex-specific adult ALP reference intervals.",
        rules=[
            {"sex": "Male", "lower": 30.0, "upper": 115.0},
            {"sex": "Female", "lower": 30.0, "upper": 100.0},
        ],
    ),
    ReferenceSpec(
        name="total_bilirubin_mg_dl",
        aliases=["total_bilirubin_mg_dl", "LBXSTB_total_bilirubin_mg_dl"],
        method="interval",
        source_label="Medscape bilirubin overview",
        source_url="https://emedicine.medscape.com/article/2074068-overview",
        note="General adult total bilirubin reference interval.",
        rules=[{"lower": 0.2, "upper": 1.2}],
    ),
    ReferenceSpec(
        name="total_cholesterol_mg_dl",
        aliases=["total_cholesterol_mg_dl", "LBXTC_total_cholesterol_mg_dl"],
        method="upper_only",
        source_label="ACC/AHA dyslipidemia guideline",
        source_url="https://www.ahajournals.org/doi/10.1161/CIR.0000000000001423",
        note="Desirable total cholesterol <200 mg/dL.",
        rules=[{"upper": 200.0, "scale": 200.0}],
    ),
    ReferenceSpec(
        name="hdl_cholesterol_mg_dl",
        aliases=["hdl_cholesterol_mg_dl", "LBDHDD_direct_hdl_cholesterol_mg_dl"],
        method="interval",
        source_label="Cleveland Clinic HDL guidance",
        source_url="https://my.clevelandclinic.org/health/articles/24395-hdl-cholesterol",
        note="Sex-specific normal HDL range.",
        rules=[
            {"sex": "Male", "lower": 40.0, "upper": 80.0},
            {"sex": "Female", "lower": 50.0, "upper": 80.0},
        ],
    ),
    ReferenceSpec(
        name="triglycerides_mg_dl",
        aliases=["triglycerides_mg_dl", "LBXTR_triglyceride_mg_dl"],
        method="upper_only",
        source_label="ACC/AHA dyslipidemia guideline",
        source_url="https://www.ahajournals.org/doi/10.1161/CIR.0000000000001423",
        note="Normal triglycerides <150 mg/dL.",
        rules=[{"upper": 150.0, "scale": 150.0}],
    ),
    ReferenceSpec(
        name="ldl_cholesterol_mg_dl",
        aliases=["LBDLDL_ldl_cholesterol_friedewald_mg_dl"],
        method="upper_only",
        source_label="ACC/AHA dyslipidemia guideline",
        source_url="https://www.ahajournals.org/doi/10.1161/CIR.0000000000001423",
        note="General desirable LDL target <100 mg/dL.",
        rules=[{"upper": 100.0, "scale": 100.0}],
    ),
    ReferenceSpec(
        name="ferritin_ng_ml",
        aliases=["ferritin_ng_ml", "LBXFER_ferritin_ng_ml"],
        method="interval",
        source_label="CDC Nutrition Report and WHO ferritin guidance",
        source_url="https://www.cdc.gov/nutrition-report/media/Trace.pdf",
        note="Premenopausal vs postmenopausal female split approximated with age 50 because menopause status is not consistently available.",
        rules=[
            {"sex": "Male", "age_min": 18, "age_max": 120, "lower": 12.0, "upper": 300.0},
            {"sex": "Female", "age_min": 18, "age_max": 49, "lower": 12.0, "upper": 150.0},
            {"sex": "Female", "age_min": 50, "age_max": 120, "lower": 12.0, "upper": 200.0},
        ],
    ),
    ReferenceSpec(
        name="serum_iron_ug_dl",
        aliases=["serum_iron_ug_dl", "LBXIRN_iron_frozen_serum_ug_dl", "LBXSIR_iron_refrigerated_serum_ug_dl"],
        method="interval",
        source_label="MSD Manual serum iron interval",
        source_url="https://www.msdmanuals.com/professional/multimedia/table/typical-normal-serum-values-for-iron-iron-binding-capacity-ferritin-and-transferrin-saturation",
        note="Sex-specific adult serum iron reference intervals.",
        rules=[
            {"sex": "Male", "lower": 59.0, "upper": 158.0},
            {"sex": "Female", "lower": 37.0, "upper": 145.0},
        ],
    ),
    ReferenceSpec(
        name="tibc_ug_dl",
        aliases=["tibc_ug_dl", "LBDTIB_total_iron_binding_capacity_tibc_ug_dl"],
        method="interval",
        source_label="MSD Manual TIBC interval",
        source_url="https://www.msdmanuals.com/professional/multimedia/table/typical-normal-serum-values-for-iron-iron-binding-capacity-ferritin-and-transferrin-saturation",
        note="General adult TIBC reference interval.",
        rules=[{"lower": 235.0, "upper": 451.0}],
    ),
    ReferenceSpec(
        name="transferrin_saturation_pct",
        aliases=["transferrin_saturation_pct", "LBDPCT_transferrin_saturation"],
        method="interval",
        source_label="Medscape transferrin saturation interval",
        source_url="https://emedicine.medscape.com/article/2087960-overview",
        note="Sex-specific adult transferrin saturation intervals.",
        rules=[
            {"sex": "Male", "lower": 20.0, "upper": 50.0},
            {"sex": "Female", "lower": 15.0, "upper": 50.0},
        ],
    ),
    ReferenceSpec(
        name="bmi_kg_m2",
        aliases=["bmi"],
        method="interval",
        source_label="WHO BMI categories",
        source_url="https://www.worldobesity.org/about/about-obesity/obesity-classification",
        note="Healthy BMI interval 18.5-24.9 kg/m^2.",
        rules=[{"lower": 18.5, "upper": 24.9}],
    ),
    ReferenceSpec(
        name="waist_cm",
        aliases=["waist_cm"],
        method="upper_only",
        source_label="NIH NHLBI waist circumference risk",
        source_url="https://www.nhlbi.nih.gov/health/educational/lose_wt/risk.htm",
        note="Sex-specific at-risk waist thresholds.",
        rules=[
            {"sex": "Male", "upper": 102.0, "scale": 102.0},
            {"sex": "Female", "upper": 88.0, "scale": 88.0},
        ],
    ),
    ReferenceSpec(
        name="sbp_mm_hg",
        aliases=["sbp_1", "sbp_2", "sbp_3"],
        method="upper_only",
        source_label="ACC/AHA blood pressure guideline",
        source_url="https://www.ahajournals.org/doi/10.1161/CIR.0000000000001356",
        note="Normal systolic blood pressure threshold <120 mmHg.",
        rules=[{"upper": 120.0, "scale": 120.0}],
    ),
    ReferenceSpec(
        name="dbp_mm_hg",
        aliases=["dbp_1", "dbp_2", "dbp_3"],
        method="upper_only",
        source_label="ACC/AHA blood pressure guideline",
        source_url="https://www.ahajournals.org/doi/10.1161/CIR.0000000000001356",
        note="Normal diastolic blood pressure threshold <80 mmHg.",
        rules=[{"upper": 80.0, "scale": 80.0}],
    ),
    ReferenceSpec(
        name="hs_crp_mg_l",
        aliases=["LBXHSCRP_hs_c_reactive_protein_mg_l"],
        method="upper_only",
        source_label="AHA/CDC hs-CRP statement",
        source_url="https://www.ahajournals.org/doi/10.1161/01.cir.0000093381.57779.67",
        note="High cardiovascular risk threshold >3.0 mg/L.",
        rules=[{"upper": 3.0, "scale": 3.0}],
    ),
]


def normalize_sex(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"male", "m", "1", "man"}:
        return "Male"
    if text in {"female", "f", "2", "woman"}:
        return "Female"
    return None


def make_age_group(age_series: pd.Series) -> pd.Series:
    return pd.cut(
        age_series,
        bins=AGE_BINS,
        labels=AGE_LABELS,
        right=False,
        include_lowest=True,
    ).astype("object")


class HybridReferenceNormalizer:
    def __init__(self, reference_specs: list[ReferenceSpec]) -> None:
        self.reference_specs = reference_specs
        self.reference_columns: dict[str, dict[str, Any]] = {}
        self.zscore_columns: list[str] = []
        self.untouched_columns: list[str] = []
        self.zscore_stats: dict[str, dict[str, Any]] = {}
        self.actions: list[dict[str, Any]] = []
        self.reference_table_rows: list[dict[str, Any]] = []

    @staticmethod
    def _is_numeric_categorical(series: pd.Series, column_name: str) -> bool:
        lower_name = column_name.lower()
        if column_name in PROTECTED_COLUMNS:
            return True
        if any(hint in lower_name for hint in CATEGORICAL_NAME_HINTS):
            return True
        non_null = series.dropna()
        if non_null.empty:
            return True
        nunique = non_null.nunique()
        if nunique <= 1:
            return True
        if nunique <= 12:
            return True
        return False

    def _match_rule(self, spec: ReferenceSpec, gender: Any, age: Any) -> dict[str, Any] | None:
        sex_value = normalize_sex(gender)
        age_value = None if pd.isna(age) else float(age)

        for rule in spec.rules:
            rule_sex = rule.get("sex")
            if rule_sex is not None and rule_sex != sex_value:
                continue

            age_min = rule.get("age_min")
            age_max = rule.get("age_max")
            if age_min is not None or age_max is not None:
                if age_value is None:
                    continue
                if age_min is not None and age_value < age_min:
                    continue
                if age_max is not None and age_value > age_max:
                    continue

            return rule
        return None

    def _compute_reference_score(self, value: Any, spec: ReferenceSpec, gender: Any, age: Any) -> float:
        if pd.isna(value):
            return np.nan
        rule = self._match_rule(spec, gender, age)
        if rule is None:
            return np.nan

        x = float(value)
        if spec.method == "interval":
            lower = float(rule["lower"])
            upper = float(rule["upper"])
            half_range = (upper - lower) / 2.0
            midpoint = (upper + lower) / 2.0
            if half_range == 0:
                return np.nan
            return (x - midpoint) / half_range

        if spec.method == "upper_only":
            upper = float(rule["upper"])
            scale = float(rule.get("scale", upper))
            if scale == 0:
                return np.nan
            return (x - upper) / scale

        if spec.method == "lower_only":
            lower = float(rule["lower"])
            scale = float(rule.get("scale", lower))
            if scale == 0:
                return np.nan
            return (lower - x) / scale

        raise ValueError(f"Unsupported reference method: {spec.method}")

    @staticmethod
    def _build_group_key(gender: Any, age_group: Any) -> str | None:
        sex_value = normalize_sex(gender)
        if sex_value is None or pd.isna(age_group):
            return None
        return f"{sex_value}|{age_group}"

    @staticmethod
    def _safe_mean_std(series: pd.Series) -> tuple[float | None, float | None]:
        clean = series.dropna().astype(float)
        if clean.empty:
            return None, None
        std = clean.std(ddof=0)
        if pd.isna(std) or std == 0:
            return float(clean.mean()), None
        return float(clean.mean()), float(std)

    def fit(self, df: pd.DataFrame) -> "HybridReferenceNormalizer":
        working = df.drop(columns=[c for c in DIETARY_COLUMNS if c in df.columns]).copy()
        working["_sex_normalized"] = working["gender"].map(normalize_sex) if "gender" in working.columns else None
        working["_age_group"] = make_age_group(working["age_years"]) if "age_years" in working.columns else None

        numeric_columns = working.select_dtypes(include=[np.number]).columns.tolist()
        non_numeric_columns = [c for c in working.columns if c not in numeric_columns]
        self.untouched_columns.extend([c for c in non_numeric_columns if not c.startswith("_")])

        reference_aliases: dict[str, ReferenceSpec] = {}
        for spec in self.reference_specs:
            for alias in spec.aliases:
                if alias in working.columns:
                    reference_aliases[alias] = spec
                    for rule in spec.rules:
                        self.reference_table_rows.append(
                            {
                                "feature_name": spec.name,
                                "dataset_column": alias,
                                "method": spec.method,
                                "sex": rule.get("sex"),
                                "age_min": rule.get("age_min"),
                                "age_max": rule.get("age_max"),
                                "lower": rule.get("lower"),
                                "upper": rule.get("upper"),
                                "scale": rule.get("scale"),
                                "source_label": spec.source_label,
                                "source_url": spec.source_url,
                                "note": spec.note,
                            }
                        )

        for column in working.columns:
            if column.startswith("_"):
                continue

            series = working[column]
            if column in reference_aliases:
                spec = reference_aliases[column]
                self.reference_columns[column] = {
                    "feature_name": spec.name,
                    "method": spec.method,
                    "source_label": spec.source_label,
                    "source_url": spec.source_url,
                    "note": spec.note,
                    "rules": spec.rules,
                }
                self.actions.append(
                    {
                        "column": column,
                        "action": "reference_normalize",
                        "method": spec.method,
                        "reason": spec.note,
                        "source_label": spec.source_label,
                        "source_url": spec.source_url,
                    }
                )
                continue

            if column not in numeric_columns:
                self.actions.append(
                    {
                        "column": column,
                        "action": "untouched",
                        "method": "non_numeric",
                        "reason": "Non-numeric column preserved as-is.",
                        "source_label": "",
                        "source_url": "",
                    }
                )
                continue

            if self._is_numeric_categorical(series, column):
                self.untouched_columns.append(column)
                self.actions.append(
                    {
                        "column": column,
                        "action": "untouched",
                        "method": "categorical_numeric_or_protected",
                        "reason": "Protected identifier or low-cardinality numeric code kept as categorical-like.",
                        "source_label": "",
                        "source_url": "",
                    }
                )
                continue

            self.zscore_columns.append(column)
            grouped: dict[str, dict[str, Any]] = {}
            for label in AGE_LABELS:
                for sex in ("Male", "Female"):
                    key = f"{sex}|{label}"
                    mask = (working["_sex_normalized"] == sex) & (working["_age_group"] == label)
                    mean, std = self._safe_mean_std(series[mask])
                    grouped[key] = {"mean": mean, "std": std, "n": int(mask.sum())}

            gender_only: dict[str, dict[str, Any]] = {}
            for sex in ("Male", "Female"):
                mask = working["_sex_normalized"] == sex
                mean, std = self._safe_mean_std(series[mask])
                gender_only[sex] = {"mean": mean, "std": std, "n": int(mask.sum())}

            global_mean, global_std = self._safe_mean_std(series)
            self.zscore_stats[column] = {
                "grouped": grouped,
                "gender_only": gender_only,
                "global": {"mean": global_mean, "std": global_std, "n": int(series.notna().sum())},
            }
            self.actions.append(
                {
                    "column": column,
                    "action": "zscore_normalize",
                    "method": "sex_age_stratified_zscore_with_gender_then_global_fallback",
                    "reason": "Continuous numeric column without a curated reference rule.",
                    "source_label": "",
                    "source_url": "",
                }
            )

        return self

    def _apply_zscore(self, value: Any, column: str, gender: Any, age_group: Any) -> float:
        if pd.isna(value):
            return np.nan

        stats = self.zscore_stats[column]
        group_key = self._build_group_key(gender, age_group)
        stat_candidates = []
        if group_key is not None:
            stat_candidates.append(stats["grouped"].get(group_key))
        normalized_sex = normalize_sex(gender)
        if normalized_sex is not None:
            stat_candidates.append(stats["gender_only"].get(normalized_sex))
        stat_candidates.append(stats["global"])

        for stat in stat_candidates:
            if not stat:
                continue
            mean = stat.get("mean")
            std = stat.get("std")
            if mean is None or std in (None, 0):
                continue
            return (float(value) - mean) / std
        return np.nan

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        transformed = df.drop(columns=[c for c in DIETARY_COLUMNS if c in df.columns]).copy()
        transformed["_sex_normalized"] = transformed["gender"].map(normalize_sex) if "gender" in transformed.columns else None
        transformed["_age_group"] = make_age_group(transformed["age_years"]) if "age_years" in transformed.columns else None

        for column in self.reference_columns:
            if column not in transformed.columns:
                continue
            spec_data = self.reference_columns[column]
            spec = ReferenceSpec(
                name=spec_data["feature_name"],
                aliases=[column],
                method=spec_data["method"],
                source_label=spec_data["source_label"],
                source_url=spec_data["source_url"],
                note=spec_data["note"],
                rules=spec_data["rules"],
            )
            result = pd.Series(np.nan, index=transformed.index, dtype="float64")
            values = pd.to_numeric(transformed[column], errors="coerce")

            for rule in spec.rules:
                mask = values.notna()
                if "sex" in rule:
                    mask &= transformed["_sex_normalized"] == rule["sex"]
                if "age_min" in rule:
                    mask &= transformed["age_years"] >= rule["age_min"]
                if "age_max" in rule:
                    mask &= transformed["age_years"] <= rule["age_max"]

                if spec.method == "interval":
                    lower = float(rule["lower"])
                    upper = float(rule["upper"])
                    midpoint = (upper + lower) / 2.0
                    half_range = (upper - lower) / 2.0
                    if half_range != 0:
                        result.loc[mask] = (values.loc[mask] - midpoint) / half_range
                elif spec.method == "upper_only":
                    upper = float(rule["upper"])
                    scale = float(rule.get("scale", upper))
                    if scale != 0:
                        result.loc[mask] = (values.loc[mask] - upper) / scale
                elif spec.method == "lower_only":
                    lower = float(rule["lower"])
                    scale = float(rule.get("scale", lower))
                    if scale != 0:
                        result.loc[mask] = (lower - values.loc[mask]) / scale

            transformed[column] = result

        for column in self.zscore_columns:
            if column not in transformed.columns:
                continue
            values = pd.to_numeric(transformed[column], errors="coerce")
            result = pd.Series(np.nan, index=transformed.index, dtype="float64")
            stats = self.zscore_stats[column]

            for label in AGE_LABELS:
                for sex in ("Male", "Female"):
                    key = f"{sex}|{label}"
                    stat = stats["grouped"].get(key, {})
                    mean = stat.get("mean")
                    std = stat.get("std")
                    if mean is None or std in (None, 0):
                        continue
                    mask = (
                        values.notna()
                        & result.isna()
                        & (transformed["_sex_normalized"] == sex)
                        & (transformed["_age_group"] == label)
                    )
                    result.loc[mask] = (values.loc[mask] - mean) / std

            for sex in ("Male", "Female"):
                stat = stats["gender_only"].get(sex, {})
                mean = stat.get("mean")
                std = stat.get("std")
                if mean is None or std in (None, 0):
                    continue
                mask = values.notna() & result.isna() & (transformed["_sex_normalized"] == sex)
                result.loc[mask] = (values.loc[mask] - mean) / std

            global_mean = stats["global"].get("mean")
            global_std = stats["global"].get("std")
            if global_mean is not None and global_std not in (None, 0):
                mask = values.notna() & result.isna()
                result.loc[mask] = (values.loc[mask] - global_mean) / global_std

            transformed[column] = result

        transformed = transformed.drop(columns=["_sex_normalized", "_age_group"], errors="ignore")
        return transformed

    def to_metadata(self) -> dict[str, Any]:
        return {
            "input_file": str(INPUT_FILE),
            "output_file": str(OUTPUT_FILE),
            "dietary_columns_dropped": DIETARY_COLUMNS,
            "age_bins": AGE_BINS,
            "age_labels": AGE_LABELS,
            "reference_columns": self.reference_columns,
            "zscore_columns": self.zscore_columns,
            "untouched_columns": sorted(set(self.untouched_columns)),
            "zscore_stats": self.zscore_stats,
            "action_counts": pd.DataFrame(self.actions)["action"].value_counts().to_dict(),
        }


ReferenceSpec.__module__ = "scripts.normalize_final_dataset"
HybridReferenceNormalizer.__module__ = "scripts.normalize_final_dataset"


def main() -> None:
    sys.modules.setdefault("scripts.normalize_final_dataset", sys.modules[__name__])
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    normalizer = HybridReferenceNormalizer(REFERENCE_SPECS).fit(df)
    transformed = normalizer.transform(df)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    NORMALIZER_FILE.parent.mkdir(parents=True, exist_ok=True)

    transformed.to_csv(OUTPUT_FILE, index=False)
    pd.DataFrame(normalizer.actions).sort_values(["action", "column"]).to_csv(ACTIONS_FILE, index=False)
    pd.DataFrame(normalizer.reference_table_rows).drop_duplicates().to_csv(REFERENCES_FILE, index=False)

    metadata = normalizer.to_metadata()
    with METADATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    joblib.dump(normalizer, NORMALIZER_FILE)

    print(f"Saved normalized dataset to {OUTPUT_FILE}")
    print(f"Saved action log to {ACTIONS_FILE}")
    print(f"Saved reference table to {REFERENCES_FILE}")
    print(f"Saved metadata to {METADATA_FILE}")
    print(f"Saved fitted normalizer to {NORMALIZER_FILE}")


if __name__ == "__main__":
    main()
