#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_real_nhanes_2003_2006_cohort import (
    as_int_flag,
    derive_activity_level,
    derive_smoking_status,
    fill_bayesian_answers,
    symptom_vector_from_row,
)
REAL_COHORT_CSV = PROJECT_ROOT / "data" / "processed" / "nhanes_2003_2006_real_cohort.csv"
OUTPUT_JSON = EVALS_DIR / "cohort" / "profiles_v3_three_layer.json"
SUMMARY_JSON = EVALS_DIR / "cohort" / "profiles_v3_three_layer_summary.json"

BENCHMARK_CONDITIONS = [
    "anemia",
    "hepatitis",
    "hypothyroidism",
    "liver",
    "sleep_disorder",
    "kidney_disease",
    "iron_deficiency",
    "prediabetes",
    "inflammation",
    "electrolyte_imbalance",
    "perimenopause",
]

LABEL_SOURCE_MAP = {
    "anemia": "anemia",
    "hepatitis": "hepatitis_bc",
    "hypothyroidism": "thyroid",
    "liver": "liver",
    "sleep_disorder": "sleep_disorder",
    "kidney_disease": "kidney",
    "iron_deficiency": "iron_deficiency",
    "prediabetes": "prediabetes",
    "inflammation": "hidden_inflammation",
    "electrolyte_imbalance": "electrolyte_imbalance",
    "perimenopause": "perimenopause_proxy_probable",
}

TARGET_PREFIX = {
    "anemia": "ANM",
    "hepatitis": "HEP",
    "hypothyroidism": "THY",
    "liver": "LVR",
    "sleep_disorder": "SLP",
    "kidney_disease": "KDN",
    "iron_deficiency": "IRN",
    "prediabetes": "PRD",
    "inflammation": "INF",
    "electrolyte_imbalance": "ELC",
    "perimenopause": "PMN",
}

MIMIC_CONDITIONS = {
    "anemia": ["iron_deficiency", "hypothyroidism", "sleep_disorder", "inflammation"],
    "hepatitis": ["liver", "inflammation", "electrolyte_imbalance"],
    "hypothyroidism": ["anemia", "sleep_disorder", "perimenopause", "prediabetes"],
    "liver": ["hepatitis", "inflammation", "electrolyte_imbalance"],
    "sleep_disorder": ["hypothyroidism", "perimenopause", "anemia", "prediabetes"],
    "kidney_disease": ["prediabetes", "electrolyte_imbalance", "inflammation"],
    "iron_deficiency": ["anemia", "perimenopause", "hypothyroidism"],
    "prediabetes": ["sleep_disorder", "kidney_disease", "inflammation", "hypothyroidism"],
    "inflammation": ["anemia", "sleep_disorder", "electrolyte_imbalance", "kidney_disease"],
    "electrolyte_imbalance": ["kidney_disease", "inflammation", "sleep_disorder"],
    "perimenopause": ["sleep_disorder", "hypothyroidism", "iron_deficiency"],
}

SIGNAL_DIMS = {
    "anemia": ["fatigue_severity", "post_exertional_malaise"],
    "hepatitis": ["digestive_symptoms", "fatigue_severity", "weight_change"],
    "hypothyroidism": ["fatigue_severity", "cognitive_impairment", "weight_change"],
    "liver": ["digestive_symptoms", "fatigue_severity", "weight_change"],
    "sleep_disorder": ["sleep_quality", "fatigue_severity", "post_exertional_malaise"],
    "kidney_disease": ["fatigue_severity", "post_exertional_malaise"],
    "iron_deficiency": ["fatigue_severity", "cognitive_impairment"],
    "prediabetes": ["fatigue_severity", "weight_change", "sleep_quality"],
    "inflammation": ["joint_pain", "fatigue_severity", "digestive_symptoms"],
    "electrolyte_imbalance": ["fatigue_severity", "post_exertional_malaise", "digestive_symptoms"],
    "perimenopause": ["heat_intolerance", "sleep_quality", "depressive_mood", "anxiety_level"],
}

PRIMARY_COUNTS = {condition: 30 for condition in BENCHMARK_CONDITIONS}
PRIMARY_COUNTS["perimenopause"] = 54

BORDERLINE_COUNTS = {condition: 10 for condition in BENCHMARK_CONDITIONS}
BORDERLINE_COUNTS["perimenopause"] = 18

NEGATIVE_COUNTS = {condition: 5 for condition in BENCHMARK_CONDITIONS}
NEGATIVE_COUNTS["sleep_disorder"] = 10
NEGATIVE_COUNTS["hypothyroidism"] = 10
NEGATIVE_COUNTS["anemia"] = 10

MUST_PASS_PACK = [
    {"target": "sleep_disorder", "mimic": "hypothyroidism", "kind": "negative"},
    {"target": "sleep_disorder", "mimic": "anemia", "kind": "negative"},
    {"target": "hypothyroidism", "mimic": "sleep_disorder", "kind": "negative"},
    {"target": "hypothyroidism", "mimic": "anemia", "kind": "negative"},
    {"target": "anemia", "mimic": "sleep_disorder", "kind": "negative"},
    {"target": "anemia", "mimic": "hypothyroidism", "kind": "negative"},
    {"target": "perimenopause", "mimic": "sleep_disorder", "kind": "borderline"},
    {"target": "perimenopause", "mimic": "hypothyroidism", "kind": "borderline"},
]


def load_real_cohort() -> pd.DataFrame:
    if not REAL_COHORT_CSV.exists():
        raise FileNotFoundError(
            f"Missing real cohort CSV: {REAL_COHORT_CSV}\n"
            "Run: python3 scripts/build_real_nhanes_2003_2006_cohort.py --download --build"
        )
    df = pd.read_csv(REAL_COHORT_CSV, low_memory=False)
    df = df[pd.to_numeric(df["age_years"], errors="coerce").between(18, 85, inclusive="both")].copy()
    df["n_active_conditions"] = 0
    for condition in BENCHMARK_CONDITIONS:
        col = LABEL_SOURCE_MAP[condition]
        df["n_active_conditions"] += pd.to_numeric(df[col], errors="coerce").fillna(0).eq(1).astype(int)
    return df


def make_profile_id(layer_code: str, index: int) -> str:
    return f"SYN-{layer_code}{index:07d}"


def row_truth_conditions(row: pd.Series, target_first: str | None = None, confidence: str = "high") -> list[dict[str, Any]]:
    items: list[str] = []
    for condition in BENCHMARK_CONDITIONS:
        source_col = LABEL_SOURCE_MAP[condition]
        if as_int_flag(row.get(source_col, 0)) == 1:
            items.append(condition)
    if target_first and target_first in items:
        items.remove(target_first)
        items = [target_first, *items]
    return [
        {"condition_id": cond, "confidence": confidence if idx == 0 else "medium", "rank": idx + 1}
        for idx, cond in enumerate(items)
    ]


def base_profile_from_row(
    row: pd.Series,
    profile_id: str,
    profile_type: str,
    target_condition: str,
    notes: str,
    layer: str,
    confidence: str = "high",
) -> dict[str, Any]:
    symptom_vector = symptom_vector_from_row(row)
    demographics = {
        "age": int(row["age_years"]) if pd.notna(row.get("age_years")) else 45,
        "sex": "F" if row.get("gender") == "Female" else "M",
        "bmi": round(float(row["bmi"]), 2) if pd.notna(row.get("bmi")) else 27.0,
        "smoking_status": _normalize_smoking(derive_smoking_status(row)),
        "activity_level": derive_activity_level(row),
    }
    lab_values = _compact_lab_values({
        "tsh": None,
        "alt": _num_or_none(row.get("alt_u_l")),
        "ast": _num_or_none(row.get("ast_u_l")),
        "ggt": _num_or_none(row.get("ggt_u_l")),
        "albumin": _num_or_none(row.get("serum_albumin_g_dl")),
        "ferritin": _num_or_none(row.get("ferritin_ng_ml")),
        "hemoglobin": _num_or_none(row.get("hemoglobin_g_dl")),
        "creatinine": _num_or_none(row.get("serum_creatinine_mg_dl")),
        "crp": _num_or_none(row.get("crp_mg_l")),
        "wbc": _num_or_none(row.get("wbc_1000_cells_ul")),
        "total_protein": _num_or_none(row.get("total_protein_g_dl")),
        "vitamin_d": None,
        "hba1c": _num_or_none(row.get("hba1c_pct")),
        "cortisol": None,
    })
    profile = {
        "profile_id": profile_id,
        "profile_type": profile_type,
        "target_condition": target_condition,
        "demographics": demographics,
        "symptom_vector": symptom_vector,
        "lab_values": lab_values,
        "quiz_path": "hybrid" if any(value is not None for value in lab_values.values()) else "full",
        "bayesian_answers": fill_bayesian_answers(row, symptom_vector),
        "ground_truth": {
            "expected_conditions": row_truth_conditions(row, target_first=target_condition, confidence=confidence),
            "notes": notes,
        },
        "metadata": {
            "generated_by": "build_three_layer_benchmark.py",
            "generation_date": "2026-03-26",
            "source_basis": layer,
            "eval_layer": [1],
            "seqn": int(row["SEQN"]),
            "cycle": row.get("cycle"),
        },
    }
    return profile


def _normalize_smoking(status: str) -> str:
    if status == "daily":
        return "current"
    if status == "some_days":
        return "current"
    if status == "not_at_all":
        return "never"
    return "former"


def _num_or_none(value: Any) -> float | None:
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(value) else round(float(value), 2)


def _compact_lab_values(values: dict[str, float | None]) -> dict[str, float]:
    return {key: value for key, value in values.items() if value is not None}


def _blend_toward(value: float, target: float, weight: float) -> float:
    return round(value * (1.0 - weight) + target * weight, 3)


def make_borderline_profile(base_profile: dict[str, Any], row: pd.Series, profile_id: str) -> dict[str, Any]:
    profile = json.loads(json.dumps(base_profile))
    target = profile["target_condition"]
    dims = SIGNAL_DIMS[target]
    for dim in dims:
        if dim == "sleep_quality":
            profile["symptom_vector"][dim] = _blend_toward(profile["symptom_vector"][dim], 0.48, 0.45)
        elif dim == "weight_change":
            profile["symptom_vector"][dim] = _blend_toward(profile["symptom_vector"][dim], 0.08, 0.55)
        elif dim == "heat_intolerance":
            profile["symptom_vector"][dim] = _blend_toward(profile["symptom_vector"][dim], 0.52, 0.35)
        else:
            profile["symptom_vector"][dim] = _blend_toward(profile["symptom_vector"][dim], 0.42, 0.45)

    if target == "iron_deficiency" and profile["lab_values"].get("ferritin") is not None:
        profile["lab_values"]["ferritin"] = max(18.0, min(34.0, profile["lab_values"]["ferritin"]))
    if target == "prediabetes" and profile["lab_values"].get("hba1c") is not None:
        profile["lab_values"]["hba1c"] = max(5.6, min(5.9, profile["lab_values"]["hba1c"]))
    if target == "inflammation" and profile["lab_values"].get("crp") is not None:
        profile["lab_values"]["crp"] = max(2.5, min(5.0, profile["lab_values"]["crp"]))
    if target == "kidney_disease" and row.get("gender") == "Female" and profile["lab_values"].get("hemoglobin") is not None:
        profile["lab_values"]["hemoglobin"] = min(profile["lab_values"]["hemoglobin"], 12.2)

    profile["profile_id"] = profile_id
    profile["profile_type"] = "borderline"
    profile["ground_truth"]["expected_conditions"] = row_truth_conditions(row, target_first=target, confidence="medium")
    profile["ground_truth"]["notes"] = f"Counterfactual borderline edit from real NHANES row for {target}."
    profile["metadata"]["source_basis"] = "counterfactual_real_edit"
    profile["metadata"]["variant_hash"] = profile_id
    profile["bayesian_answers"] = fill_bayesian_answers(row, profile["symptom_vector"])
    return profile


def make_negative_profile(row: pd.Series, target_condition: str, profile_id: str) -> dict[str, Any]:
    symptom_vector = symptom_vector_from_row(row)
    for dim in SIGNAL_DIMS[target_condition]:
        if dim == "sleep_quality":
            symptom_vector[dim] = _blend_toward(symptom_vector[dim], 0.42, 0.25)
        elif dim == "weight_change":
            symptom_vector[dim] = _blend_toward(symptom_vector[dim], 0.12, 0.35)
        else:
            symptom_vector[dim] = _blend_toward(symptom_vector[dim], 0.38, 0.25)

    profile = {
        "profile_id": profile_id,
        "profile_type": "negative",
        "target_condition": target_condition,
        "demographics": {
            "age": int(row["age_years"]) if pd.notna(row.get("age_years")) else 45,
            "sex": "F" if row.get("gender") == "Female" else "M",
            "bmi": round(float(row["bmi"]), 2) if pd.notna(row.get("bmi")) else 27.0,
            "smoking_status": _normalize_smoking(derive_smoking_status(row)),
            "activity_level": derive_activity_level(row),
        },
        "symptom_vector": symptom_vector,
        "lab_values": _compact_lab_values({
            "tsh": None,
            "alt": _num_or_none(row.get("alt_u_l")),
            "ast": _num_or_none(row.get("ast_u_l")),
            "ggt": _num_or_none(row.get("ggt_u_l")),
            "albumin": _num_or_none(row.get("serum_albumin_g_dl")),
            "ferritin": _num_or_none(row.get("ferritin_ng_ml")),
            "hemoglobin": _num_or_none(row.get("hemoglobin_g_dl")),
            "creatinine": _num_or_none(row.get("serum_creatinine_mg_dl")),
            "crp": _num_or_none(row.get("crp_mg_l")),
            "wbc": _num_or_none(row.get("wbc_1000_cells_ul")),
            "total_protein": _num_or_none(row.get("total_protein_g_dl")),
            "vitamin_d": None,
            "hba1c": _num_or_none(row.get("hba1c_pct")),
            "cortisol": None,
        }),
        "quiz_path": "hybrid",
        "bayesian_answers": fill_bayesian_answers(row, symptom_vector),
        "ground_truth": {
            "expected_conditions": row_truth_conditions(row, confidence="high"),
            "notes": f"Hard-negative real NHANES mimic for {target_condition}.",
        },
        "metadata": {
            "generated_by": "build_three_layer_benchmark.py",
            "generation_date": "2026-03-26",
            "source_basis": "hard_negative_real_anchor",
            "eval_layer": [1],
            "seqn": int(row["SEQN"]),
            "cycle": row.get("cycle"),
        },
    }
    return profile


def make_stress_profile(base_profile: dict[str, Any], row: pd.Series, profile_id: str, idx: int) -> dict[str, Any]:
    profile = json.loads(json.dumps(base_profile))
    profile["profile_id"] = profile_id
    profile["profile_type"] = "edge"
    profile["metadata"]["source_basis"] = "stress_test"
    profile["ground_truth"]["notes"] = "Stress-test profile with contradictions and comorbidity preserved from a real row."
    if idx % 2 == 0:
        profile["symptom_vector"]["sleep_quality"] = max(0.18, profile["symptom_vector"]["sleep_quality"] - 0.18)
        profile["bayesian_answers"]["sleep_q5"] = "no"
    else:
        profile["symptom_vector"]["fatigue_severity"] = min(0.88, profile["symptom_vector"]["fatigue_severity"] + 0.16)
        profile["bayesian_answers"]["anemia_q2"] = "no"
    if idx % 3 == 0:
        profile["bayesian_answers"]["peri_q2"] = "no"
        profile["bayesian_answers"]["inflam_q3"] = "yes"
    return profile


def make_healthy_profile(row: pd.Series, profile_id: str, idx: int) -> dict[str, Any]:
    symptom_vector = symptom_vector_from_row(row)
    symptom_vector["fatigue_severity"] = _blend_toward(symptom_vector["fatigue_severity"], 0.32, 0.45)
    symptom_vector["sleep_quality"] = _blend_toward(symptom_vector["sleep_quality"], 0.58, 0.25)
    if idx % 2 == 0:
        symptom_vector["digestive_symptoms"] = _blend_toward(symptom_vector["digestive_symptoms"], 0.28, 0.45)
    profile = {
        "profile_id": profile_id,
        "profile_type": "healthy",
        "target_condition": "",
        "demographics": {
            "age": int(row["age_years"]) if pd.notna(row.get("age_years")) else 45,
            "sex": "F" if row.get("gender") == "Female" else "M",
            "bmi": round(float(row["bmi"]), 2) if pd.notna(row.get("bmi")) else 26.0,
            "smoking_status": _normalize_smoking(derive_smoking_status(row)),
            "activity_level": derive_activity_level(row),
        },
        "symptom_vector": symptom_vector,
        "lab_values": _compact_lab_values({
            "tsh": None,
            "alt": _num_or_none(row.get("alt_u_l")),
            "ast": _num_or_none(row.get("ast_u_l")),
            "ggt": _num_or_none(row.get("ggt_u_l")),
            "albumin": _num_or_none(row.get("serum_albumin_g_dl")),
            "ferritin": _num_or_none(row.get("ferritin_ng_ml")),
            "hemoglobin": _num_or_none(row.get("hemoglobin_g_dl")),
            "creatinine": _num_or_none(row.get("serum_creatinine_mg_dl")),
            "crp": _num_or_none(row.get("crp_mg_l")),
            "wbc": _num_or_none(row.get("wbc_1000_cells_ul")),
            "total_protein": _num_or_none(row.get("total_protein_g_dl")),
            "vitamin_d": None,
            "hba1c": _num_or_none(row.get("hba1c_pct")),
            "cortisol": None,
        }),
        "quiz_path": "hybrid",
        "bayesian_answers": fill_bayesian_answers(row, symptom_vector),
        "ground_truth": {
            "expected_conditions": [],
            "notes": "Healthy real-anchor control with mild nonspecific noise.",
        },
        "metadata": {
            "generated_by": "build_three_layer_benchmark.py",
            "generation_date": "2026-03-26",
            "source_basis": "stress_test_healthy_control",
            "eval_layer": [1],
            "seqn": int(row["SEQN"]),
            "cycle": row.get("cycle"),
        },
    }
    return profile


def sample_rows(df: pd.DataFrame, condition: str, positive: bool, n: int, rng: random.Random, with_replacement: bool = False) -> list[pd.Series]:
    source_col = LABEL_SOURCE_MAP[condition]
    cond_series = pd.to_numeric(df[source_col], errors="coerce")
    if positive:
        pool = df[cond_series.eq(1)].copy()
    else:
        pool = df[cond_series.eq(0)].copy()
    if pool.empty:
        return []
    if with_replacement:
        indices = [rng.choice(list(pool.index)) for _ in range(n)]
        return [pool.loc[idx] for idx in indices]
    if len(pool) <= n:
        return [row for _, row in pool.iterrows()]
    indices = rng.sample(list(pool.index), n)
    return [pool.loc[idx] for idx in indices]


def choose_hard_negatives(df: pd.DataFrame, condition: str, n: int, rng: random.Random) -> list[pd.Series]:
    source_col = LABEL_SOURCE_MAP[condition]
    negatives = df[pd.to_numeric(df[source_col], errors="coerce").eq(0)].copy()
    mimic_cols = [LABEL_SOURCE_MAP[c] for c in MIMIC_CONDITIONS[condition] if LABEL_SOURCE_MAP[c] in negatives.columns]
    if mimic_cols:
        mask = pd.Series(False, index=negatives.index)
        for col in mimic_cols:
            mask = mask | pd.to_numeric(negatives[col], errors="coerce").eq(1)
        hard_pool = negatives[mask]
        if len(hard_pool) >= n:
            negatives = hard_pool
    if negatives.empty:
        return []
    if len(negatives) <= n:
        return [row for _, row in negatives.iterrows()]
    indices = rng.sample(list(negatives.index), n)
    return [negatives.loc[idx] for idx in indices]


def choose_condition_specific_negatives(
    df: pd.DataFrame,
    target_condition: str,
    mimic_condition: str,
    n: int,
    rng: random.Random,
) -> list[pd.Series]:
    target_col = LABEL_SOURCE_MAP[target_condition]
    mimic_col = LABEL_SOURCE_MAP[mimic_condition]
    target_series = pd.to_numeric(df[target_col], errors="coerce")
    mimic_series = pd.to_numeric(df[mimic_col], errors="coerce")
    pool = df[target_series.eq(0) & mimic_series.eq(1)].copy()
    if pool.empty:
        return []
    if len(pool) <= n:
        return [row for _, row in pool.iterrows()]
    indices = rng.sample(list(pool.index), n)
    return [pool.loc[idx] for idx in indices]


def make_must_pass_profile(
    row: pd.Series,
    target_condition: str,
    mimic_condition: str,
    profile_id: str,
    kind: str,
) -> dict[str, Any]:
    if kind == "borderline":
        base = base_profile_from_row(
            row=row,
            profile_id=profile_id,
            profile_type="positive",
            target_condition=target_condition,
            notes=f"Fixed must-pass borderline case: {target_condition} with {mimic_condition} overlap.",
            layer="must_pass_pack",
        )
        profile = make_borderline_profile(base, row, profile_id)
        profile["metadata"]["source_basis"] = "must_pass_pack"
        profile["ground_truth"]["notes"] = f"Fixed must-pass borderline case for {target_condition} against {mimic_condition}."
        return profile

    profile = make_negative_profile(row, target_condition, profile_id)
    profile["metadata"]["source_basis"] = "must_pass_pack"
    profile["ground_truth"]["notes"] = f"Fixed must-pass hard negative: mimic {mimic_condition} queried as {target_condition}."
    return profile


def build_benchmark(seed: int = 42) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    df = load_real_cohort()
    profiles: list[dict[str, Any]] = []
    counts = {
        "primary": 0,
        "secondary_borderline": 0,
        "secondary_negative": 0,
        "tertiary_edge": 0,
        "tertiary_healthy": 0,
        "must_pass": 0,
    }

    pid_counter = {"R": 0, "C": 0, "T": 0, "M": 0}

    def next_id(layer: str) -> str:
        pid_counter[layer] += 1
        return make_profile_id(layer, pid_counter[layer])

    for condition in BENCHMARK_CONDITIONS:
        positive_rows = sample_rows(
            df,
            condition,
            positive=True,
            n=PRIMARY_COUNTS[condition],
            rng=rng,
            with_replacement=(condition == "perimenopause"),
        )
        for row in positive_rows:
            profiles.append(
                base_profile_from_row(
                    row=row,
                    profile_id=next_id("R"),
                    profile_type="positive",
                    target_condition=condition,
                    notes=f"Primary real-anchor NHANES positive for {condition}.",
                    layer="real_anchor",
                )
            )
            counts["primary"] += 1

        borderline_rows = sample_rows(
            df,
            condition,
            positive=True,
            n=BORDERLINE_COUNTS[condition],
            rng=rng,
            with_replacement=(condition == "perimenopause"),
        )
        for row in borderline_rows:
            base = base_profile_from_row(
                row=row,
                profile_id=next_id("C"),
                profile_type="positive",
                target_condition=condition,
                notes=f"Base real-anchor row for {condition}.",
                layer="counterfactual_real_edit",
            )
            profiles.append(make_borderline_profile(base, row, base["profile_id"]))
            counts["secondary_borderline"] += 1

        negative_rows = choose_hard_negatives(df, condition, n=NEGATIVE_COUNTS[condition], rng=rng)
        for row in negative_rows:
            profiles.append(make_negative_profile(row, condition, next_id("C")))
            counts["secondary_negative"] += 1

    triad_pairs = [("sleep_disorder", "hypothyroidism"), ("sleep_disorder", "anemia"), ("hypothyroidism", "sleep_disorder"), ("hypothyroidism", "anemia"), ("anemia", "sleep_disorder"), ("anemia", "hypothyroidism")]
    for target_condition, mimic_condition in triad_pairs:
        extra_rows = choose_condition_specific_negatives(df, target_condition, mimic_condition, n=4, rng=rng)
        for row in extra_rows:
            profiles.append(make_negative_profile(row, target_condition, next_id("C")))
            counts["secondary_negative"] += 1

    edge_pool = df[df["n_active_conditions"] >= 2].copy()
    if not edge_pool.empty:
        edge_indices = rng.sample(list(edge_pool.index), min(24, len(edge_pool)))
        for idx, row_idx in enumerate(edge_indices):
            row = edge_pool.loc[row_idx]
            gt = row_truth_conditions(row)
            if not gt:
                continue
            base = base_profile_from_row(
                row=row,
                profile_id=next_id("T"),
                profile_type="edge",
                target_condition=gt[0]["condition_id"],
                notes="Base real multi-condition row for stress testing.",
                layer="stress_test",
            )
            profiles.append(make_stress_profile(base, row, base["profile_id"], idx))
            counts["tertiary_edge"] += 1

    healthy_pool = df[df["n_active_conditions"] == 0].copy()
    if not healthy_pool.empty:
        healthy_indices = rng.sample(list(healthy_pool.index), min(24, len(healthy_pool)))
        for idx, row_idx in enumerate(healthy_indices):
            profiles.append(make_healthy_profile(healthy_pool.loc[row_idx], next_id("T"), idx))
            counts["tertiary_healthy"] += 1

    for idx, spec in enumerate(MUST_PASS_PACK, start=1):
        rows = choose_condition_specific_negatives(df, spec["target"], spec["mimic"], n=1, rng=rng)
        if not rows and spec["kind"] == "borderline":
            rows = sample_rows(df, spec["target"], positive=True, n=1, rng=rng)
        if not rows:
            continue
        profile = make_must_pass_profile(
            row=rows[0],
            target_condition=spec["target"],
            mimic_condition=spec["mimic"],
            profile_id=f"SYN-MUST{idx:04d}",
            kind=spec["kind"],
        )
        profiles.append(profile)
        counts["must_pass"] += 1

    summary = {
        "seed": seed,
        "total_profiles": len(profiles),
        "layer_counts": counts,
        "per_type": pd.Series([p["profile_type"] for p in profiles]).value_counts().to_dict(),
        "per_target_condition": pd.Series([p["target_condition"] for p in profiles if p["target_condition"]]).value_counts().to_dict(),
        "notes": [
            "Primary layer uses real NHANES anchors only.",
            "Secondary layer uses counterfactual edits on real rows and hard negative mimics from real rows.",
            "Tertiary layer uses a small stress-test slice with contradictions and multi-condition cases.",
            "A fixed must-pass regression pack is appended with deterministic profile IDs.",
            "Perimenopause is used; menopause is excluded from the benchmark.",
            "Inflammation is benchmarked using the stricter chronic hidden-inflammation definition rather than broad acute inflammation.",
            "No model-derived coefficients are used to create eval truth.",
        ],
    }
    return profiles, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the 3-layer eval benchmark from real NHANES anchors.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    profiles, summary = build_benchmark(seed=args.seed)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved {len(profiles):,} profiles to {OUTPUT_JSON}")
    print(f"Saved summary to {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
