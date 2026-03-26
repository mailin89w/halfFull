#!/usr/bin/env python3
"""
cohort_generator_v2_latent.py
-----------------------------
Separate synthetic cohort generator using latent-factor logic.

This intentionally does NOT replace the existing cohort generator.
It writes a parallel cohort file by default:
  evals/cohort/profiles_v2_latent.json

Design goals:
- reduce unrealistically easy disease centroids
- add mimic patterns and mild comorbidity
- separate latent physiology from observed questionnaire/lab outputs
- introduce answer noise, contradictions, and missingness-like softness
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = EVALS_DIR / "schema" / "profile_schema.json"
OUTPUT_PATH = EVALS_DIR / "cohort" / "profiles_v2_latent.json"

sys.path.insert(0, str(PROJECT_ROOT))

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)

try:
    from config import CONDITION_IDS
except ImportError:
    CONDITION_IDS = [
        "menopause", "perimenopause", "hypothyroidism", "kidney_disease",
        "sleep_disorder", "anemia", "iron_deficiency", "hepatitis",
        "prediabetes", "inflammation", "electrolyte_imbalance",
    ]

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SYMPTOMS = [
    "fatigue_severity",
    "sleep_quality",
    "post_exertional_malaise",
    "joint_pain",
    "cognitive_impairment",
    "depressive_mood",
    "anxiety_level",
    "digestive_symptoms",
    "heat_intolerance",
    "weight_change",
]

CONDITION_PREFIX: dict[str, str] = {
    "menopause": "MNP",
    "perimenopause": "PMN",
    "hypothyroidism": "THY",
    "kidney_disease": "KDN",
    "sleep_disorder": "SLP",
    "anemia": "ANM",
    "iron_deficiency": "IRN",
    "hepatitis": "HEP",
    "prediabetes": "PRD",
    "inflammation": "INF",
    "electrolyte_imbalance": "ELC",
}

BAYESIAN_PRIORS: dict[str, float] = {
    "hypothyroidism": 0.062,
    "kidney_disease": 0.035,
    "hepatitis": 0.026,
    "iron_deficiency": 0.060,
    "inflammation": 0.324,
    "menopause": 0.30,
    "perimenopause": 0.40,
    "sleep_disorder": 0.20,
    "anemia": 0.08,
    "prediabetes": 0.38,
    "electrolyte_imbalance": 0.08,
}

COMORBIDITY_PAIRS: list[tuple[str, str]] = [
    ("anemia", "iron_deficiency"),
    ("hypothyroidism", "anemia"),
    ("prediabetes", "inflammation"),
    ("kidney_disease", "anemia"),
    ("kidney_disease", "electrolyte_imbalance"),
    ("sleep_disorder", "hypothyroidism"),
    ("sleep_disorder", "perimenopause"),
    ("menopause", "perimenopause"),
    ("inflammation", "hepatitis"),
    ("prediabetes", "sleep_disorder"),
    ("menopause", "hypothyroidism"),
    ("iron_deficiency", "perimenopause"),
]

LATENT_FACTORS = [
    "blood_loss",
    "iron_depletion",
    "thyroid_slowdown",
    "kidney_impairment",
    "sleep_fragmentation",
    "airway_obstruction",
    "insulin_resistance",
    "inflammation_load",
    "alcohol_exposure",
    "volume_depletion",
    "menopause_transition",
    "infection_load",
    "digestive_irritation",
    "medication_burden",
    "psychological_load",
]

FACTOR_BASELINE = {
    "blood_loss": 0.05,
    "iron_depletion": 0.08,
    "thyroid_slowdown": 0.06,
    "kidney_impairment": 0.04,
    "sleep_fragmentation": 0.18,
    "airway_obstruction": 0.10,
    "insulin_resistance": 0.18,
    "inflammation_load": 0.14,
    "alcohol_exposure": 0.10,
    "volume_depletion": 0.06,
    "menopause_transition": 0.06,
    "infection_load": 0.07,
    "digestive_irritation": 0.10,
    "medication_burden": 0.10,
    "psychological_load": 0.12,
}

CONDITION_FACTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "anemia": {
        "blood_loss": 0.90,
        "iron_depletion": 0.55,
        "sleep_fragmentation": 0.20,
        "psychological_load": 0.15,
    },
    "iron_deficiency": {
        "iron_depletion": 0.95,
        "blood_loss": 0.65,
        "digestive_irritation": 0.15,
    },
    "hypothyroidism": {
        "thyroid_slowdown": 0.95,
        "sleep_fragmentation": 0.25,
        "psychological_load": 0.15,
    },
    "kidney_disease": {
        "kidney_impairment": 0.95,
        "inflammation_load": 0.35,
        "volume_depletion": 0.25,
    },
    "sleep_disorder": {
        "sleep_fragmentation": 0.95,
        "airway_obstruction": 0.70,
        "psychological_load": 0.20,
    },
    "prediabetes": {
        "insulin_resistance": 0.95,
        "sleep_fragmentation": 0.25,
        "inflammation_load": 0.20,
    },
    "inflammation": {
        "inflammation_load": 0.95,
        "infection_load": 0.45,
        "digestive_irritation": 0.20,
    },
    "electrolyte_imbalance": {
        "volume_depletion": 0.85,
        "medication_burden": 0.45,
        "kidney_impairment": 0.20,
        "alcohol_exposure": 0.25,
    },
    "hepatitis": {
        "alcohol_exposure": 0.30,
        "digestive_irritation": 0.70,
        "inflammation_load": 0.55,
        "infection_load": 0.60,
    },
    "perimenopause": {
        "menopause_transition": 0.95,
        "sleep_fragmentation": 0.30,
        "psychological_load": 0.35,
    },
    "menopause": {
        "menopause_transition": 0.98,
        "sleep_fragmentation": 0.28,
        "psychological_load": 0.25,
    },
}

MIMIC_FACTOR_WEIGHTS: dict[str, list[dict[str, float]]] = {
    "anemia": [
        {"sleep_fragmentation": 0.65, "psychological_load": 0.45},
        {"inflammation_load": 0.55, "digestive_irritation": 0.35},
    ],
    "iron_deficiency": [
        {"blood_loss": 0.45, "sleep_fragmentation": 0.35},
        {"psychological_load": 0.45, "digestive_irritation": 0.40},
    ],
    "hypothyroidism": [
        {"sleep_fragmentation": 0.70, "psychological_load": 0.50},
        {"insulin_resistance": 0.45, "inflammation_load": 0.25},
    ],
    "kidney_disease": [
        {"insulin_resistance": 0.45, "volume_depletion": 0.40},
        {"inflammation_load": 0.40, "medication_burden": 0.35},
    ],
    "sleep_disorder": [
        {"psychological_load": 0.75},
        {"menopause_transition": 0.45, "airway_obstruction": 0.25},
    ],
    "prediabetes": [
        {"sleep_fragmentation": 0.55, "inflammation_load": 0.35},
        {"thyroid_slowdown": 0.35, "psychological_load": 0.30},
    ],
    "inflammation": [
        {"sleep_fragmentation": 0.45, "psychological_load": 0.35},
        {"digestive_irritation": 0.55, "infection_load": 0.30},
    ],
    "electrolyte_imbalance": [
        {"volume_depletion": 0.55, "digestive_irritation": 0.45},
        {"kidney_impairment": 0.35, "medication_burden": 0.40},
    ],
    "hepatitis": [
        {"digestive_irritation": 0.60, "alcohol_exposure": 0.35},
        {"inflammation_load": 0.45, "weight_loss_proxy": 0.0},
    ],
    "perimenopause": [
        {"sleep_fragmentation": 0.55, "psychological_load": 0.45},
        {"thyroid_slowdown": 0.40, "menopause_transition": 0.25},
    ],
    "menopause": [
        {"sleep_fragmentation": 0.55, "psychological_load": 0.35},
        {"thyroid_slowdown": 0.35, "menopause_transition": 0.25},
    ],
}

LAB_REFERENCE: dict[str, tuple[float, float]] = {
    "hemoglobin": (14.4, 1.3),
    "tsh": (2.0, 0.9),
    "ferritin": (75.0, 28.0),
    "crp": (1.2, 0.8),
    "hba1c": (5.25, 0.28),
    "vitamin_d": (33.0, 10.0),
    "cortisol": (14.0, 4.0),
    "total_cholesterol_mg_dl": (186.0, 35.0),
    "triglycerides_mg_dl": (110.0, 45.0),
    "fasting_glucose_mg_dl": (98.0, 14.0),
    "wbc_1000_cells_ul": (7.0, 1.4),
}


def adjusted_split(prior_prevalence: float, n_profiles: int = 50) -> tuple[int, int, int]:
    if prior_prevalence >= 0.25:
        return 18, 20, 12
    if prior_prevalence <= 0.05:
        return 22, 16, 12
    return 20, 18, 12


def clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def clip_symptom(symptom: str, value: float) -> float:
    if symptom == "weight_change":
        return float(np.clip(value, -1.0, 1.0))
    return clip01(value)


def sample_demographics(
    rng: random.Random,
    nprng: np.random.Generator,
    condition: str | None,
    profile_type: str,
) -> dict[str, Any]:
    if condition in {"menopause", "perimenopause"}:
        sex = "F"
        if condition == "menopause":
            age = int(np.clip(nprng.normal(56, 5), 46, 68))
        else:
            age = int(np.clip(nprng.normal(47, 5), 35, 56))
    elif condition == "iron_deficiency":
        sex = rng.choices(["F", "M"], weights=[4, 1])[0]
        age = int(np.clip(nprng.normal(37, 11), 18, 70))
    elif condition == "anemia":
        sex = rng.choices(["F", "M"], weights=[3, 2])[0]
        age = int(np.clip(nprng.normal(43, 14), 18, 82))
    elif condition == "hypothyroidism":
        sex = rng.choices(["F", "M"], weights=[4, 1])[0]
        age = int(np.clip(nprng.normal(50, 12), 24, 82))
    elif condition in {"kidney_disease", "hepatitis"}:
        sex = rng.choice(["F", "M"])
        age = int(np.clip(nprng.normal(55, 12), 28, 82))
    elif condition == "prediabetes":
        sex = rng.choice(["F", "M"])
        age = int(np.clip(nprng.normal(51, 12), 28, 82))
    elif condition in {"sleep_disorder", "inflammation", "electrolyte_imbalance"}:
        sex = rng.choice(["F", "M"])
        age = int(np.clip(nprng.normal(48, 13), 20, 82))
    else:
        sex = rng.choice(["F", "M"])
        age = int(np.clip(nprng.normal(46, 15), 18, 85))

    bmi_base = 27.5
    if condition in {"prediabetes", "inflammation"}:
        bmi_base = 32.0
    elif condition in {"sleep_disorder", "menopause", "perimenopause"}:
        bmi_base = 29.5
    elif condition in {"anemia", "iron_deficiency", "hepatitis"}:
        bmi_base = 25.5
    bmi = round(float(np.clip(nprng.normal(bmi_base, 5.2), 16.0, 50.0)), 1)
    smoking_status = rng.choices(["never", "former", "current"], weights=[56, 28, 16])[0]
    activity_level = rng.choices(
        ["sedentary", "low", "moderate", "high"],
        weights=[28, 29, 31, 12] if condition in {"prediabetes", "sleep_disorder", "inflammation"} else [24, 28, 34, 14],
    )[0]

    # Borderline and healthy users should be a bit more heterogeneous.
    if profile_type in {"healthy", "negative"}:
        bmi = round(float(np.clip(nprng.normal(26.8, 5.5), 16.0, 45.0)), 1)

    return {
        "age": age,
        "sex": sex,
        "bmi": bmi,
        "smoking_status": smoking_status,
        "activity_level": activity_level,
    }


def sample_latent_state(
    profile_type: str,
    condition: str | None,
    demographics: dict[str, Any],
    rng: random.Random,
    nprng: np.random.Generator,
    edge_conditions: list[str] | None = None,
) -> dict[str, float]:
    state = {
        factor: clip01(nprng.normal(baseline, 0.05))
        for factor, baseline in FACTOR_BASELINE.items()
    }

    sex = demographics["sex"]
    age = demographics["age"]
    bmi = demographics["bmi"]
    activity = demographics["activity_level"]
    smoking = demographics["smoking_status"]

    if bmi >= 30:
        state["insulin_resistance"] = clip01(state["insulin_resistance"] + 0.18)
        state["inflammation_load"] = clip01(state["inflammation_load"] + 0.10)
        state["airway_obstruction"] = clip01(state["airway_obstruction"] + 0.08)
    if age >= 50:
        state["medication_burden"] = clip01(state["medication_burden"] + 0.10)
        state["kidney_impairment"] = clip01(state["kidney_impairment"] + 0.05)
    if smoking == "current":
        state["inflammation_load"] = clip01(state["inflammation_load"] + 0.10)
    if activity == "sedentary":
        state["sleep_fragmentation"] = clip01(state["sleep_fragmentation"] + 0.05)
        state["insulin_resistance"] = clip01(state["insulin_resistance"] + 0.06)

    target_conditions = edge_conditions[:] if profile_type == "edge" and edge_conditions else ([condition] if condition else [])

    strength_map = {
        "positive": (0.62, 0.92),
        "borderline": (0.35, 0.66),
        "negative": (0.08, 0.28),
        "healthy": (0.02, 0.14),
        "edge": (0.42, 0.74),
    }
    lo, hi = strength_map[profile_type]

    for cond in target_conditions:
        factor_weights = CONDITION_FACTOR_WEIGHTS.get(cond, {})
        severity = rng.uniform(lo, hi)
        subtype_noise = rng.uniform(0.82, 1.18)
        for factor, weight in factor_weights.items():
            state[factor] = clip01(state[factor] + severity * weight * subtype_noise)

        # Add one mimic component so positives are not too clean.
        mimic_pool = MIMIC_FACTOR_WEIGHTS.get(cond, [])
        if mimic_pool:
            mimic = rng.choice(mimic_pool)
            mimic_strength = rng.uniform(0.12, 0.32 if profile_type == "positive" else 0.22)
            for factor, weight in mimic.items():
                if factor in state:
                    state[factor] = clip01(state[factor] + mimic_strength * weight)

    # Borderline and negative cases get explicit confusing competitors.
    if condition and profile_type in {"borderline", "negative"}:
        mimic_pool = MIMIC_FACTOR_WEIGHTS.get(condition, [])
        if mimic_pool:
            mimic = rng.choice(mimic_pool)
            mimic_strength = rng.uniform(0.18, 0.36 if profile_type == "borderline" else 0.22)
            for factor, weight in mimic.items():
                if factor in state:
                    state[factor] = clip01(state[factor] + mimic_strength * weight)

    if sex == "F" and 40 <= age <= 58:
        menopausal_pressure = np.clip((age - 40) / 18.0, 0.0, 1.0)
        state["menopause_transition"] = clip01(state["menopause_transition"] + 0.22 * float(menopausal_pressure))
    if sex == "M":
        state["blood_loss"] = clip01(state["blood_loss"] * 0.6)

    return {k: round(v, 4) for k, v in state.items()}


def latent_to_symptoms(
    state: dict[str, float],
    demographics: dict[str, Any],
    nprng: np.random.Generator,
) -> dict[str, float]:
    bmi = demographics["bmi"]
    age = demographics["age"]
    sex = demographics["sex"]

    sleep_fragmentation = state["sleep_fragmentation"]
    airway = state["airway_obstruction"]
    inflammation = state["inflammation_load"]
    blood_loss = state["blood_loss"]
    iron = state["iron_depletion"]
    thyroid = state["thyroid_slowdown"]
    kidney = state["kidney_impairment"]
    insulin = state["insulin_resistance"]
    alcohol = state["alcohol_exposure"]
    volume = state["volume_depletion"]
    menopause = state["menopause_transition"]
    infection = state["infection_load"]
    digestive = state["digestive_irritation"]
    meds = state["medication_burden"]
    psych = state["psychological_load"]

    symptoms = {
        "fatigue_severity": (
            0.10 + 0.34 * iron + 0.24 * thyroid + 0.20 * sleep_fragmentation + 0.20 * inflammation +
            0.16 * kidney + 0.10 * menopause + 0.08 * insulin + 0.08 * psych
        ),
        "sleep_quality": (
            0.82 - 0.46 * sleep_fragmentation - 0.24 * airway - 0.18 * menopause - 0.10 * psych - 0.06 * alcohol
        ),
        "post_exertional_malaise": (
            0.08 + 0.22 * inflammation + 0.18 * iron + 0.18 * kidney + 0.14 * sleep_fragmentation + 0.10 * insulin
        ),
        "joint_pain": (
            0.08 + 0.38 * inflammation + 0.18 * menopause + 0.10 * thyroid + 0.08 * infection
        ),
        "cognitive_impairment": (
            0.10 + 0.20 * sleep_fragmentation + 0.16 * iron + 0.14 * thyroid + 0.12 * inflammation +
            0.10 * menopause + 0.10 * psych + 0.08 * alcohol
        ),
        "depressive_mood": (
            0.08 + 0.26 * psych + 0.12 * sleep_fragmentation + 0.10 * thyroid + 0.08 * menopause + 0.08 * inflammation
        ),
        "anxiety_level": (
            0.08 + 0.24 * psych + 0.12 * menopause + 0.08 * sleep_fragmentation + 0.06 * insulin
        ),
        "digestive_symptoms": (
            0.08 + 0.34 * digestive + 0.16 * alcohol + 0.10 * infection + 0.08 * volume
        ),
        "heat_intolerance": (
            0.08 + 0.42 * menopause + 0.16 * infection + 0.08 * alcohol - 0.20 * thyroid
        ),
        "weight_change": (
            0.40 * insulin + 0.22 * menopause - 0.32 * digestive - 0.18 * thyroid - 0.15 * alcohol
        ),
    }

    if sex == "F" and age >= 45:
        symptoms["heat_intolerance"] += 0.04
    if bmi >= 32:
        symptoms["post_exertional_malaise"] += 0.06
    if age >= 55:
        symptoms["cognitive_impairment"] += 0.03

    rendered: dict[str, float] = {}
    for symptom, value in symptoms.items():
        noise = nprng.normal(0.0, 0.06 if symptom != "weight_change" else 0.10)
        rendered[symptom] = round(clip_symptom(symptom, float(value + noise)), 4)
    return rendered


def latent_to_labs(
    state: dict[str, float],
    demographics: dict[str, Any],
    profile_type: str,
    nprng: np.random.Generator,
) -> dict[str, float]:
    bmi = demographics["bmi"]
    sex = demographics["sex"]
    age = demographics["age"]

    labs = {}
    hemo_sex_adj = -0.5 if sex == "F" else 0.4
    labs["hemoglobin"] = 14.2 + hemo_sex_adj - 3.6 * state["blood_loss"] - 2.2 * state["iron_depletion"] - 0.7 * state["kidney_impairment"] + nprng.normal(0.0, 0.6)
    labs["tsh"] = 1.9 + 5.2 * state["thyroid_slowdown"] + nprng.normal(0.0, 0.55)
    labs["ferritin"] = 82.0 - 62.0 * state["iron_depletion"] - 18.0 * state["blood_loss"] + nprng.normal(0.0, 8.0)
    labs["crp"] = 0.8 + 7.0 * state["inflammation_load"] + 1.8 * state["infection_load"] + nprng.normal(0.0, 0.8)
    labs["hba1c"] = 5.15 + 1.3 * state["insulin_resistance"] + nprng.normal(0.0, 0.18)
    labs["vitamin_d"] = 35.0 - 10.0 * state["inflammation_load"] - 6.0 * state["menopause_transition"] + nprng.normal(0.0, 4.0)
    labs["cortisol"] = 13.0 + 4.5 * state["psychological_load"] - 2.2 * state["sleep_fragmentation"] + nprng.normal(0.0, 2.0)
    labs["total_cholesterol_mg_dl"] = 182.0 + 24.0 * state["insulin_resistance"] - 12.0 * state["iron_depletion"] + nprng.normal(0.0, 16.0)
    labs["triglycerides_mg_dl"] = 98.0 + 70.0 * state["insulin_resistance"] + 14.0 * state["alcohol_exposure"] + nprng.normal(0.0, 22.0)
    labs["fasting_glucose_mg_dl"] = 92.0 + 38.0 * state["insulin_resistance"] + nprng.normal(0.0, 8.0)
    labs["wbc_1000_cells_ul"] = 6.4 + 3.0 * state["inflammation_load"] + 1.2 * state["infection_load"] + nprng.normal(0.0, 0.8)

    if bmi >= 32:
        labs["hba1c"] += 0.15
        labs["triglycerides_mg_dl"] += 8.0
    if age >= 55:
        labs["crp"] += 0.15

    if profile_type == "healthy":
        for lab, (mean, std) in LAB_REFERENCE.items():
            labs[lab] = mean + nprng.normal(0.0, std * 0.35)

    return {k: round(max(0.01, float(v)), 2) for k, v in labs.items()}


def generate_bayesian_answers(
    state: dict[str, float],
    symptoms: dict[str, float],
    demographics: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    sex = demographics["sex"]
    age = demographics["age"]

    heavy_periods = (
        sex == "F"
        and age < 53
        and (state["blood_loss"] > 0.48 or (state["menopause_transition"] > 0.45 and rng.random() < 0.35))
    )
    answers = {
        "anemia_q1": "yes" if heavy_periods else "no",
        "anemia_q2": "yes" if state["blood_loss"] > 0.55 or state["digestive_irritation"] > 0.5 else "no",
        "anemia_q3": "yes" if rng.random() < 0.10 else "no",
        "anemia_q4": "yes" if rng.random() < 0.10 else "no",
        "anemia_q5": "gt_6m" if symptoms["fatigue_severity"] > 0.55 else "4_12w",
        "iron_q1": "yes" if heavy_periods else "no",
        "iron_q2": "yes" if rng.random() < 0.12 else "no",
        "iron_q3": "yes" if state["blood_loss"] > 0.55 or state["digestive_irritation"] > 0.5 else "no",
        "iron_q4": "yes" if rng.random() < 0.10 else "no",
        "iron_q5": "yes" if state["iron_depletion"] > 0.72 and rng.random() < 0.7 else "no",
    }
    return answers


def make_ground_truth(
    profile_type: str,
    condition: str | None,
    edge_conditions: list[str] | None = None,
) -> dict[str, Any]:
    if profile_type == "healthy":
        return {"expected_conditions": [], "notes": "Healthy control — no condition expected"}
    if profile_type == "edge" and edge_conditions:
        return {
            "expected_conditions": [
                {"condition_id": cid, "confidence": "medium", "rank": idx + 1}
                for idx, cid in enumerate(edge_conditions)
            ],
            "notes": f"Edge case with overlapping signals: {', '.join(edge_conditions)}",
        }
    if not condition:
        return {"expected_conditions": []}
    confidence_map = {"positive": "high", "borderline": "medium", "negative": "low"}
    expected = [] if profile_type == "negative" else [{"condition_id": condition, "confidence": confidence_map.get(profile_type, "low"), "rank": 1}]
    return {
        "expected_conditions": expected,
        "notes": f"{profile_type.capitalize()} latent-factor profile for {condition}",
    }


def make_profile_id(prefix: str, index: int) -> str:
    return f"SYN-{prefix}{index:05d}"


def generate_profile(
    profile_type: str,
    condition: str | None,
    prefix: str,
    index: int,
    rng: random.Random,
    nprng: np.random.Generator,
    edge_conditions: list[str] | None = None,
) -> dict[str, Any]:
    demographics = sample_demographics(rng, nprng, condition, profile_type)
    state = sample_latent_state(profile_type, condition, demographics, rng, nprng, edge_conditions=edge_conditions)
    symptoms = latent_to_symptoms(state, demographics, nprng)

    has_labs = profile_type != "healthy" or rng.random() < 0.4
    lab_values = latent_to_labs(state, demographics, profile_type, nprng) if has_labs else None
    quiz_path = "hybrid" if lab_values is not None else "full"
    bayesian_answers = generate_bayesian_answers(state, symptoms, demographics, rng)

    return {
        "profile_id": make_profile_id(prefix, index),
        "profile_type": profile_type,
        "target_condition": condition if condition else "",
        "demographics": demographics,
        "symptom_vector": symptoms,
        "lab_values": lab_values,
        "quiz_path": quiz_path,
        "bayesian_answers": bayesian_answers,
        "ground_truth": make_ground_truth(profile_type, condition, edge_conditions),
        "metadata": {
            "generated_by": "cohort_generator_v2_latent.py",
            "generation_date": date.today().isoformat(),
            "source_basis": "Latent-factor synthetic generator with mimic patterns and noisy emission",
            "eval_layer": [1],
        },
    }


def generate_cohort(seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    profiles: list[dict[str, Any]] = []

    for condition in CONDITION_IDS:
        prefix = CONDITION_PREFIX.get(condition, condition[:3].upper())
        prior = BAYESIAN_PRIORS.get(condition, 0.10)
        n_pos, n_bord, n_neg = adjusted_split(prior)
        cond_index = 0

        for _ in range(n_pos):
            cond_index += 1
            profiles.append(generate_profile("positive", condition, prefix, cond_index, rng, nprng))
        for _ in range(n_bord):
            cond_index += 1
            profiles.append(generate_profile("borderline", condition, prefix, cond_index, rng, nprng))
        for _ in range(n_neg):
            cond_index += 1
            profiles.append(generate_profile("negative", condition, prefix, cond_index, rng, nprng))

    for idx in range(1, 31):
        profiles.append(generate_profile("healthy", None, "HLT", idx, rng, nprng))

    for idx, (cond_a, cond_b) in enumerate(COMORBIDITY_PAIRS[:12], start=1):
        profiles.append(generate_profile("edge", None, "EDG", idx, rng, nprng, edge_conditions=[cond_a, cond_b]))

    for idx in range(13, 21):
        n_conditions = rng.choice([2, 2, 3])
        edge_conditions = rng.sample(CONDITION_IDS, n_conditions)
        profiles.append(generate_profile("edge", None, "EDG", idx, rng, nprng, edge_conditions=edge_conditions))

    assert len(profiles) == 600, f"Expected 600 profiles, got {len(profiles)}"
    return profiles


def validate_all(profiles: list[dict[str, Any]], schema: dict[str, Any]) -> None:
    validator = jsonschema.Draft7Validator(schema)
    for idx, profile in enumerate(profiles):
        errors = list(validator.iter_errors(profile))
        if errors:
            error = errors[0]
            raise jsonschema.ValidationError(
                f"Profile {idx} ({profile.get('profile_id', '?')}) failed validation: "
                f"{error.message}\nPath: {' -> '.join(str(p) for p in error.absolute_path)}"
            )


def print_summary(profiles: list[dict[str, Any]], seed: int, output: Path) -> None:
    n_with_labs = sum(1 for p in profiles if p.get("lab_values") is not None)
    n_healthy = sum(1 for p in profiles if p["profile_type"] == "healthy")
    n_edge = sum(1 for p in profiles if p["profile_type"] == "edge")
    print()
    print("Cohort generation complete (latent v2)")
    print("─────────────────────────────────────────────────────")
    print(f"Total profiles:            {len(profiles)}")
    print(f"Conditions:                {len(CONDITION_IDS)}")
    print(f"Healthy controls:          {n_healthy}")
    print(f"Edge cases:                {n_edge}")
    print(f"With lab values:           {n_with_labs} ({n_with_labs / len(profiles) * 100:.0f}%)")
    print(f"Seed:                      {seed}")
    print(f"Output:                    {output}")
    print("─────────────────────────────────────────────────────")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a separate latent-factor synthetic cohort.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH), help="Output path")
    parser.add_argument("--validate", action="store_true", help="Validate only; do not write file")
    args = parser.parse_args()

    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema not found at {SCHEMA_PATH}")
        sys.exit(1)

    with SCHEMA_PATH.open() as f:
        schema = json.load(f)

    logger.info("Generating latent-factor cohort with seed=%d ...", args.seed)
    profiles = generate_cohort(seed=args.seed)
    logger.info("Validating %d profiles against schema ...", len(profiles))
    validate_all(profiles, schema)
    logger.info("All profiles passed schema validation")

    if args.validate:
        print(f"\n--validate mode: schema check passed for {len(profiles)} profiles (latent v2). No file written.\n")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    print_summary(profiles, args.seed, output_path)


if __name__ == "__main__":
    main()
