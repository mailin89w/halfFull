from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bayesian.synthetic_answer_sampler import generate_bayesian_answers

RAW_ROOT = ROOT / "data" / "raw" / "nhanes_2003_2006"
PROCESSED_CSV = ROOT / "data" / "processed" / "nhanes_2003_2006_real_cohort.csv"
PROFILES_JSON = ROOT / "evals" / "cohort" / "nhanes_2003_2006_real_profiles.json"
SUMMARY_JSON = ROOT / "data" / "processed" / "nhanes_2003_2006_real_summary.json"


@dataclass(frozen=True)
class FileSpec:
    logical_name: str
    stems: tuple[str, ...]
    columns: tuple[str, ...]


CYCLE_CONFIG: dict[str, dict[str, Any]] = {
    "C": {
        "begin_year": 2003,
        "questionnaire": (
            FileSpec("demo", ("DEMO_C",), ("SEQN", "RIAGENDR", "RIDAGEYR", "RIDEXPRG", "DMDEDUC2")),
            FileSpec("alq", ("ALQ_C",), ("SEQN", "ALQ111", "ALQ130", "ALQ151")),
            FileSpec("bpq", ("BPQ_C",), ("SEQN", "BPQ020", "BPQ040A", "BPQ080")),
            FileSpec("cdq", ("CDQ_C",), ("SEQN", "CDQ010")),
            FileSpec("diq", ("DIQ_C",), ("SEQN", "DIQ010", "DIQ050", "DIQ070", "DIQ160")),
            FileSpec("dpq", ("DPQ_C",), ("SEQN", "DPQ010", "DPQ020", "DPQ030", "DPQ040", "DPQ070")),
            FileSpec("heq", ("HEQ_C",), ("SEQN", "HEQ010", "HEQ030")),
            FileSpec("huq", ("HUQ_C",), ("SEQN", "HUQ010", "HUQ030", "HUQ051", "HUQ071")),
            FileSpec("kiq", ("KIQ_U_C", "KIQ_C"), ("SEQN", "KIQ005", "KIQ022", "KIQ026", "KIQ042", "KIQ044", "KIQ046", "KIQ480")),
            FileSpec("mcq", ("MCQ_C",), ("SEQN", "MCQ053", "MCQ080", "MCQ092", "MCQ160A", "MCQ160B", "MCQ160L", "MCQ160M", "MCQ170L", "MCQ170M", "MCQ300C", "MCQ520", "MCQ510A", "MCQ510B", "MCQ510C", "MCQ510D", "MCQ510E", "MCQ510F")),
            FileSpec("paq", ("PAQ_C",), ("SEQN", "PAQ620", "PAQ650", "PAQ665", "PAD680")),
            FileSpec("rhq", ("RHQ_C",), ("SEQN", "RHQ031", "RHQ060", "RHQ131", "RHQ200", "RHQ305", "RHQ540", "RHD043", "RHD143", "RHD280")),
            FileSpec("rxq", ("RXQ_RX_C",), ("SEQN", "RXDUSE", "RXDDRUG", "RXDDRGID", "RXQSEEN", "RXDDAYS", "RXDCOUNT")),
            FileSpec("smq", ("SMQ_C",), ("SEQN", "SMQ040")),
            FileSpec("whq", ("WHQ_C",), ("SEQN", "WHQ040", "WHQ070")),
            FileSpec("ocq", ("OCQ_C",), ("SEQN", "OCQ180", "OCQ670")),
        ),
        "examination": (
            FileSpec("bmx", ("BMX_C",), ("SEQN", "BMXHT", "BMXWT", "BMXBMI", "BMXWAIST")),
            FileSpec("bpx", ("BPX_C",), ("SEQN", "BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4", "BPXDI1", "BPXDI2", "BPXDI3", "BPXDI4", "BPXPULS")),
        ),
        "laboratory": (
            FileSpec("biochem", ("L40_C",), ("SEQN", "LBXSCR", "LBXSATSI", "LBXSASSI", "LBXSGTSI", "LBXSAL", "LBXSNASI", "LBXSKSI", "LBXSCA", "LBXSTP")),
            FileSpec("lipids", ("L13_C",), ("SEQN", "LBXTC", "LBXHDD")),
            FileSpec("fasting_glucose", ("L10AM_C",), ("SEQN", "LBXGLU")),
            FileSpec("trigly_ldl", ("L13AM_C",), ("SEQN", "LBXTR", "LBDLDL")),
            FileSpec("urine_albumin_creatinine", ("L16_C",), ("SEQN", "URXUMA", "URXUMS", "URXUCR")),
            FileSpec("iron", ("L40FE_C",), ("SEQN", "LBDPCT")),
            FileSpec("ferritin", ("L06TFR_C",), ("SEQN", "LBDFER")),
            FileSpec("vit_b12", ("L06NB_C",), ("SEQN", "LBXB12", "LBDB12SI")),
            FileSpec("vit_d", ("VID_C",), ("SEQN", "LBDVIDMS")),
            FileSpec("ghb", ("GHB_C",), ("SEQN", "LBXGH")),
            FileSpec("cbc", ("CBC_C",), ("SEQN", "LBXHGB", "LBXWBCSI", "LBXNEPCT", "LBXLYPCT")),
            FileSpec("crp", ("CRP_C",), ("SEQN", "LBXCRP")),
            FileSpec("hep_panel", ("L02_C",), ("SEQN", "LBXHBC", "LBDHBG", "LBDHCV", "LBDHD")),
            FileSpec("hep_c_rna", ("SSHCVR_C",), ("SEQN", "LBXHCR", "SSHCVRNA", "LBDHCR")),
        ),
    },
    "D": {
        "begin_year": 2005,
        "questionnaire": (
            FileSpec("demo", ("DEMO_D",), ("SEQN", "RIAGENDR", "RIDAGEYR", "RIDEXPRG", "DMDEDUC2")),
            FileSpec("alq", ("ALQ_D",), ("SEQN", "ALQ110", "ALQ120Q", "ALQ120U", "ALQ130", "ALQ151")),
            FileSpec("bpq", ("BPQ_D",), ("SEQN", "BPQ020", "BPQ040A", "BPQ080")),
            FileSpec("cdq", ("CDQ_D",), ("SEQN", "CDQ010")),
            FileSpec("diq", ("DIQ_D",), ("SEQN", "DIQ010", "DIQ050", "DIQ070", "DIQ160")),
            FileSpec("dpq", ("DPQ_D",), ("SEQN", "DPQ010", "DPQ020", "DPQ030", "DPQ040", "DPQ070")),
            FileSpec("heq", ("HEQ_D",), ("SEQN", "HEQ010", "HEQ030")),
            FileSpec("huq", ("HUQ_D",), ("SEQN", "HUQ010", "HUQ030", "HUQ051", "HUQ071")),
            FileSpec("kiq", ("KIQ_U_D",), ("SEQN", "KIQ005", "KIQ022", "KIQ026", "KIQ042", "KIQ044", "KIQ046", "KIQ480")),
            FileSpec("mcq", ("MCQ_D",), ("SEQN", "MCQ053", "MCQ080", "MCQ092", "MCQ160A", "MCQ160B", "MCQ160L", "MCQ160M", "MCQ170L", "MCQ170M", "MCQ300C", "MCQ520", "MCQ510A", "MCQ510B", "MCQ510C", "MCQ510D", "MCQ510E", "MCQ510F")),
            FileSpec("paq", ("PAQ_D",), ("SEQN", "PAQ620", "PAQ650", "PAQ665", "PAD680")),
            FileSpec("rhq", ("RHQ_D",), ("SEQN", "RHQ031", "RHQ060", "RHQ131", "RHQ200", "RHQ305", "RHQ540", "RHD043", "RHD143", "RHD280")),
            FileSpec("rxq", ("RXQ_RX_D",), ("SEQN", "RXDUSE", "RXDDRUG", "RXDDRGID", "RXQSEEN", "RXDDAYS", "RXDCOUNT")),
            FileSpec("slq", ("SLQ_D",), ("SEQN", "SLQ030", "SLQ040", "SLQ050", "SLD012", "SLD013")),
            FileSpec("smq", ("SMQ_D",), ("SEQN", "SMQ040")),
            FileSpec("whq", ("WHQ_D",), ("SEQN", "WHQ040", "WHQ070")),
            FileSpec("ocq", ("OCQ_D",), ("SEQN", "OCQ180", "OCQ670")),
        ),
        "examination": (
            FileSpec("bmx", ("BMX_D",), ("SEQN", "BMXHT", "BMXWT", "BMXBMI", "BMXWAIST")),
            FileSpec("bpx", ("BPX_D",), ("SEQN", "BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4", "BPXDI1", "BPXDI2", "BPXDI3", "BPXDI4", "BPXPULS")),
        ),
        "laboratory": (
            FileSpec("biochem", ("BIOPRO_D",), ("SEQN", "LBXSCR", "LBXSATSI", "LBXSASSI", "LBXSGTSI", "LBXSAL", "LBXSNASI", "LBXSKSI", "LBXSCA", "LBXSTP")),
            FileSpec("total_cholesterol", ("TCHOL_D",), ("SEQN", "LBXTC")),
            FileSpec("hdl", ("HDL_D",), ("SEQN", "LBDHDD")),
            FileSpec("glucose", ("GLU_D",), ("SEQN", "LBXGLU")),
            FileSpec("trigly_ldl", ("TRIGLY_D",), ("SEQN", "LBXTR", "LBDLDL")),
            FileSpec("urine_albumin_creatinine", ("ALB_CR_D",), ("SEQN", "URXUMA", "URXUMS", "URXUCR")),
            FileSpec("iron", ("FETIB_D",), ("SEQN", "LBDPCT")),
            FileSpec("ferritin", ("FERTIN_D",), ("SEQN", "LBXFER")),
            FileSpec("vit_b12", ("B12_D",), ("SEQN", "LBXB12", "LBDB12SI")),
            FileSpec("vit_d", ("VID_D",), ("SEQN", "LBDVIDMS")),
            FileSpec("ghb", ("GHB_D",), ("SEQN", "LBXGH")),
            FileSpec("cbc", ("CBC_D",), ("SEQN", "LBXHGB", "LBXWBCSI", "LBXNEPCT", "LBXLYPCT")),
            FileSpec("crp", ("CRP_D",), ("SEQN", "LBXCRP")),
            FileSpec("hep_b", ("HEPBD_D",), ("SEQN", "LBXHBC", "LBDHBG", "LBDHD")),
            FileSpec("hep_c", ("HEPC_D",), ("SEQN", "LBDHCV", "LBXHCR", "LBXHCG")),
        ),
    },
}


RENAME_MAP = {
    "RIAGENDR": "gender_code",
    "RIDAGEYR": "age_years",
    "RIDEXPRG": "pregnancy_status_code",
    "DMDEDUC2": "education_code",
    "ALQ130": "alq130_avg_drinks_per_day",
    "ALQ151": "alq151_4_5_plus_daily",
    "BPQ020": "bpq020_high_bp",
    "BPQ040A": "bpq040a_bp_meds",
    "BPQ080": "bpq080_high_cholesterol",
    "CDQ010": "cdq010_sob_stairs",
    "DIQ010": "diq010_diabetes",
    "DIQ050": "diq050_insulin",
    "DIQ070": "diq070_diabetes_pills",
    "DIQ160": "diq160_prediabetes",
    "DPQ010": "dpq010_anhedonia",
    "DPQ020": "dpq020_depressed",
    "DPQ030": "dpq030_sleep",
    "DPQ040": "dpq040_fatigue",
    "DPQ070": "dpq070_concentration",
    "HEQ010": "heq010_hep_b",
    "HEQ030": "heq030_hep_c",
    "HUQ010": "huq010_general_health",
    "HUQ030": "huq030_routine_care",
    "HUQ051": "huq051_visits",
    "HUQ071": "huq071_hospital",
    "KIQ005": "kiq005_urinary_leakage_freq",
    "KIQ022": "kiq022_weak_kidneys",
    "KIQ026": "kiq026_kidney_stones",
    "KIQ042": "kiq042_leak_exertion",
    "KIQ044": "kiq044_urge_incontinence",
    "KIQ046": "kiq046_nonphysical_incontinence",
    "KIQ480": "kiq480_nocturia",
    "MCQ053": "mcq053_anemia_treatment",
    "MCQ080": "mcq080_overweight_dx",
    "MCQ092": "mcq092_transfusion",
    "MCQ160A": "mcq160a_arthritis",
    "MCQ160B": "mcq160b_heart_failure",
    "MCQ160L": "mcq160l_liver_condition",
    "MCQ160M": "mcq160m_ever_thyroid",
    "MCQ170L": "mcq170l_active_liver",
    "MCQ170M": "mcq170m_active_thyroid",
    "MCQ510A": "mcq510a_liver_condition_liver_disease",
    "MCQ510B": "mcq510b_liver_condition_non_alcoholic_fatty_liver",
    "MCQ510C": "mcq510c_liver_condition_alcoholic_liver_disease",
    "MCQ510D": "mcq510d_liver_condition_hepatitis",
    "MCQ510E": "mcq510e_liver_condition_autoimmune",
    "MCQ510F": "mcq510f_liver_condition_other",
    "MCQ300C": "mcq300c_family_diabetes",
    "MCQ520": "mcq520_abdominal_pain",
    "PAQ620": "paq620_moderate_work",
    "PAQ650": "paq650_vigorous_recreation",
    "PAQ665": "paq665_moderate_recreation",
    "PAD680": "pad680_sedentary_minutes",
    "RHQ031": "rhq031_regular_periods",
    "RHQ060": "rhq060_age_last_period",
    "RHQ131": "rhq131_ever_pregnant",
    "RHQ200": "rhq200_breastfeeding",
    "RHQ305": "rhq305_both_ovaries_removed",
    "RHQ540": "rhq540_hormone_use",
    "RHD043": "rhd043_no_period_reason",
    "RHD143": "rhd143_pregnant_now",
    "RHD280": "rhd280_hysterectomy",
    "SMQ040": "smq040_smoke_now",
    "WHQ040": "whq040_weight_preference",
    "WHQ070": "whq070_tried_to_lose_weight",
    "OCQ180": "ocq180_hours_worked_week",
    "OCQ670": "ocq670_work_schedule",
    "SLQ030": "slq030_snore_freq",
    "SLQ040": "slq040_stop_breathing_freq",
    "SLQ050": "slq050_sleep_trouble_doctor",
    "SLD012": "sld012_sleep_hours_weekday",
    "SLD013": "sld013_sleep_hours_weekend",
    "BMXHT": "height_cm",
    "BMXWT": "weight_kg",
    "BMXBMI": "bmi",
    "BMXWAIST": "waist_cm",
    "LBXSCR": "serum_creatinine_mg_dl",
    "LBXSATSI": "alt_u_l",
    "LBXSASSI": "ast_u_l",
    "LBXSGTSI": "ggt_u_l",
    "LBXSAL": "serum_albumin_g_dl",
    "LBXSNASI": "sodium_mmol_l",
    "LBXSKSI": "potassium_mmol_l",
    "LBXSCA": "calcium_mg_dl",
    "LBXSTP": "total_protein_g_dl",
    "LBXTC": "total_cholesterol_mg_dl",
    "LBXHDD": "hdl_cholesterol_mg_dl",
    "LBDHDD": "hdl_cholesterol_mg_dl",
    "LBXTR": "triglycerides_mg_dl",
    "LBDLDL": "ldl_cholesterol_mg_dl",
    "LBXGLU": "fasting_glucose_mg_dl",
    "URXUMA": "urine_albumin_ug_ml",
    "URXUMS": "urine_albumin_mg_l",
    "URXUCR": "urine_creatinine_mg_dl",
    "LBDPCT": "transferrin_saturation_pct",
    "LBDFER": "ferritin_ng_ml",
    "LBXFER": "ferritin_ng_ml",
    "LBXB12": "vitamin_b12_serum_pg_ml",
    "LBDB12SI": "vitamin_b12_serum_pmol_l",
    "LBDVIDMS": "vitamin_d_25oh_nmol_l",
    "LBXGH": "hba1c_pct",
    "LBXHGB": "hemoglobin_g_dl",
    "LBXWBCSI": "wbc_1000_cells_ul",
    "LBXNEPCT": "neutrophils_pct",
    "LBXLYPCT": "lymphocytes_pct",
    "LBXCRP": "crp_mg_dl",
    "LBXHBC": "hbv_core_antibody_code",
    "LBDHBG": "hbv_surface_antigen_code",
    "LBDHCV": "hcv_antibody_confirmed_code",
    "LBXHCR": "hcv_rna_code",
    "SSHCVRNA": "hcv_rna_code",
    "LBDHCR": "hcv_rna_code",
}


EVAL_CONDITION_LABELS = {
    "anemia": "anemia",
    "thyroid": "hypothyroidism",
    "sleep_disorder": "sleep_disorder",
    "kidney": "kidney_disease",
    "hepatitis_bc": "hepatitis",
    "liver": "liver",
    "menopause": "menopause",
    "iron_deficiency": "iron_deficiency",
    "electrolyte_imbalance": "electrolyte_imbalance",
    "hidden_inflammation": "inflammation",
    "prediabetes": "prediabetes",
    "perimenopause_proxy_probable": "perimenopause",
}


def stable_unit(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16**12 - 1)


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def download_url(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response:
            dest.write_bytes(response.read())
        return True
    except urllib.error.HTTPError:
        return False


def resolve_stem(cycle: str, begin_year: int, stems: tuple[str, ...], component_dir: Path) -> Path:
    for stem in stems:
        local_path = component_dir / f"{stem}.XPT"
        if local_path.exists():
            return local_path
        url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{begin_year}/DataFiles/{stem}.XPT"
        if download_url(url, local_path):
            return local_path
    raise FileNotFoundError(f"Could not resolve any of {stems} for cycle {cycle}")


def maybe_download_cycle(cycle: str) -> None:
    cycle_cfg = CYCLE_CONFIG[cycle]
    for component in ("questionnaire", "examination", "laboratory"):
        component_dir = RAW_ROOT / cycle / component
        for spec in cycle_cfg[component]:
            try:
                resolve_stem(cycle, cycle_cfg["begin_year"], spec.stems, component_dir)
            except FileNotFoundError:
                print(f"[warn] skipping unavailable {spec.logical_name} for cycle {cycle}: {spec.stems}")


def read_selected_columns(path: Path, columns: tuple[str, ...]) -> pd.DataFrame:
    df = pd.read_sas(path, format="xport", encoding="latin1")
    keep = [col for col in columns if col in df.columns]
    if "SEQN" not in keep and "SEQN" in df.columns:
        keep = ["SEQN", *keep]
    if not keep:
        raise ValueError(f"{path.name} did not contain any requested columns from {columns}")
    return df[keep].copy()


def load_component_frames(cycle: str, component: str) -> list[pd.DataFrame]:
    cycle_cfg = CYCLE_CONFIG[cycle]
    frames: list[pd.DataFrame] = []
    component_dir = RAW_ROOT / cycle / component
    for spec in cycle_cfg[component]:
        path = None
        for stem in spec.stems:
            candidate = component_dir / f"{stem}.XPT"
            if candidate.exists():
                path = candidate
                break
        if path is None:
            continue
        df = read_selected_columns(path, spec.columns)
        frames.append(df)
    return frames


def merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=["SEQN"])
    merged = frames[0].copy()
    for frame in frames[1:]:
        merged = merged.merge(frame, on="SEQN", how="outer")
    return merged


def is_rx_frame(df: pd.DataFrame) -> bool:
    cols = set(df.columns)
    return "SEQN" in cols and (
        {"RXDUSE", "RXDDRUG", "RXDCOUNT"}.issubset(cols)
        or {"RXDRSD1", "RXDRSD2", "RXDRSD3"}.issubset(cols)
    )


def aggregate_rxd(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["SEQN", "rxd_disease_list", "med_count"])

    if {"RXDUSE", "RXDDRUG", "RXDCOUNT"}.issubset(df.columns):
        rxduse = pd.to_numeric(df["RXDUSE"], errors="coerce")
        rxdcount = pd.to_numeric(df["RXDCOUNT"], errors="coerce")
        med_name = df["RXDDRUG"].astype("string").str.strip()
        med_row = rxduse.eq(1) & med_name.notna() & med_name.ne("")

        med_count = (
            pd.DataFrame({"SEQN": df["SEQN"], "_med_count": rxdcount.where(med_row)})
            .groupby("SEQN", as_index=False)["_med_count"]
            .max()
            .rename(columns={"_med_count": "med_count"})
        )

        fallback_counts = (
            pd.DataFrame({"SEQN": df.loc[med_row, "SEQN"]})
            .groupby("SEQN", as_index=False)
            .size()
            .rename(columns={"size": "_fallback_med_count"})
        )
        med_count = med_count.merge(fallback_counts, on="SEQN", how="outer")
        med_count["med_count"] = med_count["med_count"].fillna(med_count["_fallback_med_count"]).fillna(0)
        med_count = med_count[["SEQN", "med_count"]]

        disease_list = (
            pd.DataFrame({"SEQN": df.loc[med_row, "SEQN"], "drug": med_name.loc[med_row]})
            .drop_duplicates(subset=["SEQN", "drug"])
            .groupby("SEQN", as_index=False)["drug"]
            .agg(lambda values: ", ".join(sorted(values)))
            .rename(columns={"drug": "rxd_disease_list"})
        )

        return med_count.merge(disease_list, on="SEQN", how="left")

    if not {"RXDRSD1", "RXDRSD2", "RXDRSD3"}.issubset(df.columns):
        return pd.DataFrame(columns=["SEQN", "rxd_disease_list", "med_count"])

    melted = df.melt(id_vars="SEQN", value_vars=["RXDRSD1", "RXDRSD2", "RXDRSD3"], value_name="disease")
    melted["disease"] = melted["disease"].astype("string").str.strip()
    melted = melted[melted["disease"].notna() & (melted["disease"] != "")]
    grouped = (
        melted.drop_duplicates(subset=["SEQN", "disease"])
        .groupby("SEQN")["disease"]
        .agg(lambda values: ", ".join(sorted(values)))
        .reset_index()
        .rename(columns={"disease": "rxd_disease_list"})
    )
    med_count = (
        df.groupby("SEQN")
        .size()
        .reset_index(name="med_count")
    )
    return grouped.merge(med_count, on="SEQN", how="outer")


def add_exam_means(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for prefix, target in (("BPXSY", "sbp_mean"), ("BPXDI", "dbp_mean")):
        cols = [col for col in out.columns if col.startswith(prefix)]
        if cols:
            out[target] = out[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    pulse_cols = [col for col in out.columns if re.fullmatch(r"BPXPULS\d?", col)]
    if pulse_cols:
        out["pulse_mean"] = out[pulse_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    return out


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ALQ150" in out.columns and "ALQ151" not in out.columns:
        out["ALQ151"] = out["ALQ150"]
    if "HUQ050" in out.columns and "HUQ051" not in out.columns:
        out["HUQ051"] = out["HUQ050"]
    if "RHD042" in out.columns and "RHD043" not in out.columns:
        out["RHD043"] = out["RHD042"]
    if "DID070" in out.columns and "DIQ070" not in out.columns:
        out["DIQ070"] = out["DID070"]
    out = out.rename(columns={col: RENAME_MAP[col] for col in out.columns if col in RENAME_MAP})
    if out.columns.duplicated().any():
        deduped: dict[str, pd.Series] = {}
        for col_name in dict.fromkeys(out.columns):
            same = out.loc[:, out.columns == col_name]
            if same.shape[1] == 1:
                deduped[col_name] = same.iloc[:, 0]
            else:
                deduped[col_name] = same.bfill(axis=1).iloc[:, 0]
        out = pd.DataFrame(deduped)
    out["SEQN"] = pd.to_numeric(out["SEQN"], errors="coerce").astype("Int64")
    out["gender"] = out["gender_code"].map({1: "Male", 2: "Female"}) if "gender_code" in out.columns else pd.NA
    out["cycle"] = out["cycle"].astype("string")
    if "urine_albumin_mg_l" not in out.columns and "urine_albumin_ug_ml" in out.columns:
        out["urine_albumin_mg_l"] = pd.to_numeric(out["urine_albumin_ug_ml"], errors="coerce")
    if "urine_albumin_mg_l" in out.columns and "urine_creatinine_mg_dl" in out.columns:
        albumin_mg_l = pd.to_numeric(out["urine_albumin_mg_l"], errors="coerce")
        creatinine_mg_dl = pd.to_numeric(out["urine_creatinine_mg_dl"], errors="coerce")
        out["uacr_mg_g"] = albumin_mg_l / (creatinine_mg_dl * 0.01)
    if "crp_mg_dl" in out.columns:
        out["crp_mg_l"] = pd.to_numeric(out["crp_mg_dl"], errors="coerce") * 10.0
    return out


def yes(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").eq(1)


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def compute_inflammation_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    crp = num(out.get("crp_mg_l", pd.Series(np.nan, index=out.index)))
    wbc = num(out.get("wbc_1000_cells_ul", pd.Series(np.nan, index=out.index)))
    neut = num(out.get("neutrophils_pct", pd.Series(np.nan, index=out.index)))
    lymph = num(out.get("lymphocytes_pct", pd.Series(np.nan, index=out.index)))
    nlr = neut / lymph.replace(0, np.nan)

    score = pd.Series(0.0, index=out.index)
    score += np.where(crp > 10.0, 3, np.where(crp > 3.0, 2, np.where(crp > 1.0, 1, 0)))
    score += np.where(wbc > 10.0, 2, np.where(wbc > 7.5, 1, 0))
    score += np.where(nlr > 3.0, 2, np.where(nlr > 2.0, 1, 0))

    acute = (wbc > 15.0) & (crp > 10.0)
    unavailable = crp.isna() | wbc.isna() | neut.isna() | lymph.isna()
    out["nlr"] = nlr
    out["inflammation_score"] = score
    legacy = pd.Series(np.where(score >= 3, 1.0, 0.0), index=out.index)
    out["infection_inflammation"] = legacy.where(~unavailable, np.nan).astype("Float64")
    hidden = pd.Series(np.where(score >= 5, 1.0, 0.0), index=out.index)
    hidden = hidden.where(~acute & ~unavailable, np.nan)
    out["hidden_inflammation"] = hidden.astype("Float64")
    return out


def compute_perimenopause_proxy(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    age = num(out["age_years"])
    female = out["gender"].astype("string").str.lower().eq("female")
    menopause = num(out.get("menopause", pd.Series(0, index=out.index)))
    regular_periods = num(out.get("rhq031_regular_periods", pd.Series(np.nan, index=out.index)))
    age_last_period = num(out.get("rhq060_age_last_period", pd.Series(np.nan, index=out.index)))
    years_since_last_period = age - age_last_period
    hormone_use = num(out.get("rhq540_hormone_use", pd.Series(np.nan, index=out.index)))
    pregnant_now = num(out.get("rhd143_pregnant_now", pd.Series(np.nan, index=out.index)))
    breastfeeding = num(out.get("rhq200_breastfeeding", pd.Series(np.nan, index=out.index)))
    hysterectomy = num(out.get("rhd280_hysterectomy", pd.Series(np.nan, index=out.index)))
    ovaries_removed = num(out.get("rhq305_both_ovaries_removed", pd.Series(np.nan, index=out.index)))
    sleep_problem = num(out.get("slq050_sleep_trouble_doctor", pd.Series(np.nan, index=out.index)))
    fatigue = num(out.get("dpq040_fatigue", pd.Series(np.nan, index=out.index)))
    urinary_support = (
        num(out.get("kiq005_urinary_leakage_freq", pd.Series(np.nan, index=out.index))).gt(1)
        | num(out.get("kiq042_leak_exertion", pd.Series(np.nan, index=out.index))).eq(1)
        | num(out.get("kiq044_urge_incontinence", pd.Series(np.nan, index=out.index))).eq(1)
        | num(out.get("kiq046_nonphysical_incontinence", pd.Series(np.nan, index=out.index))).eq(1)
    )

    eligible = (
        female
        & age.between(35, 55, inclusive="both")
        & menopause.fillna(0).eq(0)
        & ~hysterectomy.eq(1)
        & ~ovaries_removed.eq(1)
        & ~pregnant_now.eq(1)
        & ~breastfeeding.eq(1)
    )
    irregular_periods = regular_periods.eq(2)
    recent_last_period = years_since_last_period.between(0, 1.5, inclusive="both")
    major_transition_evidence = irregular_periods | recent_last_period
    score = pd.Series(0.0, index=out.index)
    score += np.where(age.between(40, 44, inclusive="both"), 1, 0)
    score += np.where(age.between(45, 55, inclusive="both"), 2, 0)
    score += np.where(irregular_periods, 4, 0)
    score += np.where(recent_last_period, 2, 0)
    score += np.where(sleep_problem.eq(1), 1, 0)
    score += np.where(fatigue >= 2, 1, 0)
    score += np.where(urinary_support, 1, 0)
    score -= np.where(hormone_use.eq(1), 1, 0)

    out["perimenopause_proxy_score"] = score.where(eligible, np.nan)
    probable = (eligible & major_transition_evidence & score.ge(6)).astype("float64")
    out["perimenopause_proxy_probable"] = probable.where(eligible, np.nan).astype("Float64")
    return out


def apply_disease_definitions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    def col(name: str) -> pd.Series:
        return out[name] if name in out.columns else pd.Series(np.nan, index=out.index)
    female = out["gender"].eq("Female")
    male = out["gender"].eq("Male")
    creat = num(col("serum_creatinine_mg_dl"))
    ferritin = num(col("ferritin_ng_ml"))
    transf_sat = num(col("transferrin_saturation_pct"))
    vitamin_b12 = num(col("vitamin_b12_serum_pg_ml"))
    vitamin_d = num(col("vitamin_d_25oh_nmol_l"))
    sodium = num(col("sodium_mmol_l"))
    potassium = num(col("potassium_mmol_l"))
    calcium = num(col("calcium_mg_dl"))
    hgb = num(col("hemoglobin_g_dl"))
    hba1c = num(col("hba1c_pct"))
    ferritin_normal = ferritin >= 15

    out["anemia"] = yes(col("mcq053_anemia_treatment")).astype("Int64")
    out["thyroid"] = yes(col("mcq170m_active_thyroid")).astype("Int64")
    sleep_signal = (
        num(col("slq040_stop_breathing_freq")).isin([2, 3])
        | yes(col("slq050_sleep_trouble_doctor"))
        | out.get("rxd_disease_list", pd.Series(pd.NA, index=out.index)).astype("string").str.contains("Insomnia|Sleep disorder", case=False, na=False)
    )
    sleep_available = col("slq040_stop_breathing_freq").notna() | col("slq050_sleep_trouble_doctor").notna() | out.get("rxd_disease_list", pd.Series(pd.NA, index=out.index)).notna()
    out["sleep_disorder"] = pd.Series(np.where(sleep_signal, 1.0, 0.0), index=out.index).where(sleep_available, np.nan).astype("Float64")
    kidney_signal = (
        yes(col("kiq022_weak_kidneys"))
        | (female & (creat > 1.2))
        | (male & (creat > 1.4))
    )
    out["kidney"] = kidney_signal.astype("Int64")
    hep_b_surface_ag = num(col("hbv_surface_antigen_code"))
    hcv_confirmed_ab = num(col("hcv_antibody_confirmed_code"))
    hcv_rna = num(col("hcv_rna_code"))
    hep_available = hep_b_surface_ag.notna() | hcv_confirmed_ab.notna() | hcv_rna.notna()
    hep_signal = hep_b_surface_ag.eq(1) | hcv_confirmed_ab.eq(1) | hcv_rna.eq(1)
    out["hepatitis_bc"] = pd.Series(np.where(hep_signal, 1.0, 0.0), index=out.index).where(hep_available, np.nan).astype("Float64")
    liver_specific_cols = [
        "mcq510a_liver_condition_liver_disease",
        "mcq510b_liver_condition_non_alcoholic_fatty_liver",
        "mcq510c_liver_condition_alcoholic_liver_disease",
        "mcq510d_liver_condition_hepatitis",
        "mcq510e_liver_condition_autoimmune",
        "mcq510f_liver_condition_other",
    ]
    specific_available = pd.Series(False, index=out.index)
    specific_signal = pd.Series(False, index=out.index)
    for code, field in enumerate(liver_specific_cols, start=1):
        series = num(col(field))
        specific_available = specific_available | series.notna()
        specific_signal = specific_signal | series.eq(code)
    fallback_available = col("mcq160l_liver_condition").notna() | col("mcq170l_active_liver").notna()
    fallback_signal = yes(col("mcq160l_liver_condition")) | yes(col("mcq170l_active_liver"))
    liver_available = specific_available | (~specific_available & fallback_available)
    liver_signal = specific_signal.where(specific_available, fallback_signal)
    out["liver"] = pd.Series(np.where(liver_signal, 1.0, 0.0), index=out.index).where(liver_available, np.nan).astype("Float64")
    out["menopause"] = (
        female
        & (
            yes(col("rhq305_both_ovaries_removed"))
            | num(col("rhd043_no_period_reason")).eq(7)
            | (num(col("rhq031_regular_periods")).eq(2) & num(col("age_years")).gt(40))
        )
    ).astype("Int64")
    out["iron_deficiency"] = ((ferritin < 30) & (transf_sat < 20)).astype("Int64")
    b12_available = vitamin_b12.notna()
    vit_d_available = vitamin_d.notna()
    out["vitamin_b12_deficiency"] = (
        pd.Series(np.where(vitamin_b12 < 200, 1.0, 0.0), index=out.index)
        .where(b12_available, np.nan)
        .astype("Float64")
    )
    out["vitamin_d_deficiency"] = (
        pd.Series(np.where(vitamin_d < 50, 1.0, 0.0), index=out.index)
        .where(vit_d_available, np.nan)
        .astype("Float64")
    )
    any_available = b12_available | vit_d_available
    out["vitamin_deficiency_any"] = (
        pd.Series(
            np.where(
                out["vitamin_b12_deficiency"].fillna(0).eq(1)
                | out["vitamin_d_deficiency"].fillna(0).eq(1),
                1.0,
                0.0,
            ),
            index=out.index,
        )
        .where(any_available, np.nan)
        .astype("Float64")
    )
    out["electrolyte_imbalance"] = (
        (sodium < 136) | (sodium > 145)
        | (potassium < 3.5) | (potassium > 5.0)
        | (calcium < 8.5) | (calcium > 10.5)
    ).astype("Int64")
    out["diabetes"] = yes(out["diq010_diabetes"]).astype("Int64")
    prediabetes_available = col("diq160_prediabetes").notna()
    out["prediabetes"] = pd.Series(np.where(yes(col("diq160_prediabetes")), 1.0, 0.0), index=out.index).where(prediabetes_available, np.nan).astype("Float64")
    out["CFS_suspect"] = (
        num(col("slq040_stop_breathing_freq")).ge(3)
        & num(col("huq030_routine_care")).eq(1)
        & num(col("huq010_general_health")).ge(3)
        & num(col("slq030_snore_freq")).le(2)
        & ((female & hgb.ge(12.0)) | (male & hgb.ge(13.5)))
        & hba1c.lt(6.5)
        & ferritin_normal
        & ~yes(col("mcq053_anemia_treatment"))
        & ~yes(col("diq010_diabetes"))
        & (num(col("mcq160m_ever_thyroid")).eq(2) | num(col("mcq170m_active_thyroid")).eq(2))
        & ~yes(col("mcq160b_heart_failure"))
        & ~yes(col("kiq022_weak_kidneys"))
    ).astype("Int64")
    out = compute_inflammation_scores(out)
    out = compute_perimenopause_proxy(out)
    return out


def fill_bayesian_answers(row: pd.Series, symptom_vector: dict[str, float]) -> dict[str, str]:
    return generate_bayesian_answers(row, symptom_vector)


def derive_activity_level(row: pd.Series) -> str:
    sedentary = num(pd.Series([row.get("pad680_sedentary_minutes")])).iloc[0]
    moderate = is_code(row.get("paq665_moderate_recreation"), 1) or is_code(row.get("paq620_moderate_work"), 1)
    vigorous = is_code(row.get("paq650_vigorous_recreation"), 1)
    if vigorous:
        return "high"
    if moderate:
        return "moderate"
    if pd.notna(sedentary) and sedentary >= 600:
        return "sedentary"
    return "low"


def derive_smoking_status(row: pd.Series) -> str:
    code = row.get("smq040_smoke_now")
    if is_code(code, 1):
        return "daily"
    if is_code(code, 2):
        return "some_days"
    if is_code(code, 3):
        return "not_at_all"
    return "unknown"


def clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def as_int_flag(value: Any) -> int:
    if pd.isna(value):
        return 0
    return int(float(value))


def is_code(value: Any, code: int) -> bool:
    return as_int_flag(value) == code


def symptom_vector_from_row(row: pd.Series) -> dict[str, float]:
    fatigue = clip01((num(pd.Series([row.get("dpq040_fatigue")])).iloc[0] or 0.0) / 3.0 if pd.notna(row.get("dpq040_fatigue")) else 0.15)
    weekday_sleep = num(pd.Series([row.get("sld012_sleep_hours_weekday")])).iloc[0]
    weekend_sleep = num(pd.Series([row.get("sld013_sleep_hours_weekend")])).iloc[0]
    sleep_problem = num(pd.Series([row.get("slq050_sleep_trouble_doctor")])).iloc[0]
    snore = num(pd.Series([row.get("slq030_snore_freq")])).iloc[0]
    if pd.notna(weekday_sleep):
        sleep_debt = min(abs(7.5 - weekday_sleep) / 4.0, 1.0)
    else:
        sleep_debt = 0.2
    sleep_quality = clip01(1.0 - max(sleep_debt, 0.35 if is_code(sleep_problem, 1) else 0.0, 0.25 if pd.notna(snore) and snore >= 2 else 0.0))
    pem = clip01((0.6 if is_code(row.get("cdq010_sob_stairs"), 1) else 0.15) + fatigue * 0.25)
    joint = clip01(0.65 if is_code(row.get("mcq160a_arthritis"), 1) else 0.12)
    cognitive = clip01(((num(pd.Series([row.get("dpq070_concentration")])).iloc[0] or 0.0) / 3.0 if pd.notna(row.get("dpq070_concentration")) else 0.12) + fatigue * 0.15)
    depressive = clip01(np.nanmean([
        (num(pd.Series([row.get("dpq010_anhedonia")])).iloc[0] / 3.0) if pd.notna(row.get("dpq010_anhedonia")) else np.nan,
        (num(pd.Series([row.get("dpq020_depressed")])).iloc[0] / 3.0) if pd.notna(row.get("dpq020_depressed")) else np.nan,
    ]) if pd.notna(row.get("dpq010_anhedonia")) or pd.notna(row.get("dpq020_depressed")) else 0.12)
    rxd_list = "" if pd.isna(row.get("rxd_disease_list")) else str(row.get("rxd_disease_list"))
    anxiety = clip01(max(depressive * 0.8, 0.6 if "Anxiety disorder" in rxd_list else 0.1))
    digestive = clip01(0.65 if is_code(row.get("mcq520_abdominal_pain"), 1) else 0.1)
    heat = clip01(max(
        0.75 if is_code(row.get("perimenopause_proxy_probable"), 1) else 0.0,
        0.45 if is_code(row.get("menopause"), 1) else 0.0,
        0.2 if is_code(row.get("thyroid"), 1) else 0.0,
        0.1,
    ))
    weight_pref = row.get("whq040_weight_preference")
    weight_change = 0.0
    if is_code(weight_pref, 1):
        weight_change = -0.35
    elif is_code(weight_pref, 2):
        weight_change = 0.35
    elif is_code(weight_pref, 3):
        weight_change = 0.0
    return {
        "fatigue_severity": round(fatigue, 3),
        "sleep_quality": round(sleep_quality, 3),
        "post_exertional_malaise": round(pem, 3),
        "joint_pain": round(joint, 3),
        "cognitive_impairment": round(cognitive, 3),
        "depressive_mood": round(depressive, 3),
        "anxiety_level": round(anxiety, 3),
        "digestive_symptoms": round(digestive, 3),
        "heat_intolerance": round(heat, 3),
        "weight_change": round(weight_change, 3),
    }


def build_ground_truth(row: pd.Series) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    for source_col, eval_condition in EVAL_CONDITION_LABELS.items():
        raw = row.get(source_col)
        present = False
        if pd.notna(raw):
            if isinstance(raw, (np.floating, float)):
                present = raw >= 0.5
            else:
                present = int(raw) == 1
        if present:
            labels.append(
                {
                    "condition": eval_condition,
                    "confidence": "high",
                    "rank": len(labels) + 1,
                }
            )
    return labels


def build_profiles(df: pd.DataFrame) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        row_s = pd.Series(row._asdict())
        symptom_vector = symptom_vector_from_row(row_s)
        activity_level = derive_activity_level(row_s)
        ground_truth = build_ground_truth(row_s)
        if not ground_truth:
            continue
        profile_id = f"NHANES-{row_s['cycle']}-{int(row_s['SEQN']):05d}"
        bayesian_answers = fill_bayesian_answers(row_s, symptom_vector)
        profiles.append(
            {
                "profile_id": profile_id,
                "source": "real_nhanes_2003_2006",
                "seqn": int(row_s["SEQN"]),
                "demographics": {
                    "age": int(row_s["age_years"]) if pd.notna(row_s["age_years"]) else None,
                    "sex": "F" if row_s.get("gender") == "Female" else "M",
                    "bmi": round(float(row_s["bmi"]), 2) if pd.notna(row_s.get("bmi")) else None,
                    "smoking_status": derive_smoking_status(row_s),
                    "activity_level": activity_level,
                },
                "symptom_vector": symptom_vector,
                "lab_values": {
                    "total_cholesterol_mg_dl": None if pd.isna(row_s.get("total_cholesterol_mg_dl")) else round(float(row_s["total_cholesterol_mg_dl"]), 2),
                    "hdl_cholesterol_mg_dl": None if pd.isna(row_s.get("hdl_cholesterol_mg_dl")) else round(float(row_s["hdl_cholesterol_mg_dl"]), 2),
                    "ldl_cholesterol_mg_dl": None if pd.isna(row_s.get("ldl_cholesterol_mg_dl")) else round(float(row_s["ldl_cholesterol_mg_dl"]), 2),
                    "triglycerides_mg_dl": None if pd.isna(row_s.get("triglycerides_mg_dl")) else round(float(row_s["triglycerides_mg_dl"]), 2),
                    "fasting_glucose_mg_dl": None if pd.isna(row_s.get("fasting_glucose_mg_dl")) else round(float(row_s["fasting_glucose_mg_dl"]), 2),
                    "uacr_mg_g": None if pd.isna(row_s.get("uacr_mg_g")) else round(float(row_s["uacr_mg_g"]), 2),
                    "wbc_1000_cells_ul": None if pd.isna(row_s.get("wbc_1000_cells_ul")) else round(float(row_s["wbc_1000_cells_ul"]), 2),
                    "total_protein_g_dl": None if pd.isna(row_s.get("total_protein_g_dl")) else round(float(row_s["total_protein_g_dl"]), 2),
                    "ferritin": None if pd.isna(row_s.get("ferritin_ng_ml")) else round(float(row_s["ferritin_ng_ml"]), 2),
                    "vitamin_b12": None if pd.isna(row_s.get("vitamin_b12_serum_pg_ml")) else round(float(row_s["vitamin_b12_serum_pg_ml"]), 2),
                    "vitamin_d": None if pd.isna(row_s.get("vitamin_d_25oh_nmol_l")) else round(float(row_s["vitamin_d_25oh_nmol_l"]), 2),
                    "hba1c": None if pd.isna(row_s.get("hba1c_pct")) else round(float(row_s["hba1c_pct"]), 2),
                    "creatinine": None if pd.isna(row_s.get("serum_creatinine_mg_dl")) else round(float(row_s["serum_creatinine_mg_dl"]), 2),
                    "crp": None if pd.isna(row_s.get("crp_mg_l")) else round(float(row_s["crp_mg_l"]), 2),
                    "hemoglobin": None if pd.isna(row_s.get("hemoglobin_g_dl")) else round(float(row_s["hemoglobin_g_dl"]), 2),
                    "alt": None if pd.isna(row_s.get("alt_u_l")) else round(float(row_s["alt_u_l"]), 2),
                    "ast": None if pd.isna(row_s.get("ast_u_l")) else round(float(row_s["ast_u_l"]), 2),
                    "ggt": None if pd.isna(row_s.get("ggt_u_l")) else round(float(row_s["ggt_u_l"]), 2),
                    "albumin": None if pd.isna(row_s.get("serum_albumin_g_dl")) else round(float(row_s["serum_albumin_g_dl"]), 2),
                    "wbc": None if pd.isna(row_s.get("wbc_1000_cells_ul")) else round(float(row_s["wbc_1000_cells_ul"]), 2),
                    "total_protein": None if pd.isna(row_s.get("total_protein_g_dl")) else round(float(row_s["total_protein_g_dl"]), 2),
                },
                "ground_truth": ground_truth,
                "bayesian_answers": bayesian_answers,
                "metadata": {
                    "cycle": row_s["cycle"],
                    "rxd_disease_list": None if pd.isna(row_s.get("rxd_disease_list")) else str(row_s.get("rxd_disease_list")),
                    "notes": "Real NHANES anchor row with probabilistic Bayesian-answer completion and lightweight symptom-noise projection.",
                },
            }
        )
    return profiles


def build_dataset() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    cycle_frames: list[pd.DataFrame] = []
    for cycle in ("C", "D"):
        q_frames = load_component_frames(cycle, "questionnaire")
        e_frames = load_component_frames(cycle, "examination")
        l_frames = load_component_frames(cycle, "laboratory")

        q_merged = merge_frames([df for df in q_frames if not is_rx_frame(df)])
        rx_frames = [df for df in q_frames if is_rx_frame(df)]
        rx_agg = aggregate_rxd(rx_frames[0]) if rx_frames else pd.DataFrame(columns=["SEQN", "rxd_disease_list", "med_count"])
        exam = add_exam_means(merge_frames(e_frames))
        lab = merge_frames(l_frames)
        merged = q_merged.merge(exam, on="SEQN", how="left").merge(lab, on="SEQN", how="left").merge(rx_agg, on="SEQN", how="left")
        merged["cycle"] = cycle
        cycle_frames.append(merged)

    combined = pd.concat(cycle_frames, ignore_index=True, sort=False)
    combined = normalize_columns(combined)
    combined = apply_disease_definitions(combined)
    combined["activity_level"] = combined.apply(derive_activity_level, axis=1)
    profiles = build_profiles(combined)
    return combined, profiles


def save_outputs(df: pd.DataFrame, profiles: list[dict[str, Any]]) -> None:
    PROCESSED_CSV.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_JSON.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_CSV, index=False)
    PROFILES_JSON.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    label_prevalence: dict[str, float | None] = {}
    for col in [
        "anemia",
        "thyroid",
        "sleep_disorder",
        "kidney",
        "hepatitis_bc",
        "liver",
        "menopause",
        "iron_deficiency",
        "vitamin_b12_deficiency",
        "vitamin_d_deficiency",
        "vitamin_deficiency_any",
        "electrolyte_imbalance",
        "infection_inflammation",
        "hidden_inflammation",
        "CFS_suspect",
        "prediabetes",
        "perimenopause_proxy_probable",
    ]:
        if col not in df.columns:
            continue
        mean_value = pd.to_numeric(df[col], errors="coerce").mean()
        label_prevalence[col] = None if pd.isna(mean_value) else float(mean_value)

    summary = {
        "rows": int(len(df)),
        "profiles": int(len(profiles)),
        "cycles": df["cycle"].value_counts(dropna=False).to_dict(),
        "label_prevalence": label_prevalence,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NHANES 2003-2006 data and build a real-cohort eval dataset.")
    parser.add_argument("--download", action="store_true", help="Download the required NHANES XPT files from CDC.")
    parser.add_argument("--build", action="store_true", help="Build the processed CSV and eval-ready profiles.")
    args = parser.parse_args()

    if args.download:
        for cycle in ("C", "D"):
            maybe_download_cycle(cycle)

    if args.build:
        df, profiles = build_dataset()
        save_outputs(df, profiles)
        print(f"Saved {len(df):,} rows to {PROCESSED_CSV}")
        print(f"Saved {len(profiles):,} eval profiles to {PROFILES_JSON}")


if __name__ == "__main__":
    main()
