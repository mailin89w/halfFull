#!/usr/bin/env python3
"""
cohort_generator_v4_vitamins.py
-------------------------------
Parallel latent-factor cohort generator that extends the v2/v3 synthetic setup
with explicit liver, vitamin B12 deficiency, and vitamin D deficiency targets.

This intentionally does NOT replace the older cohorts.
It writes a separate benchmark file by default:
  evals/cohort/profiles_v4_vitamins.json
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = EVALS_DIR / "schema" / "profile_schema.json"
OUTPUT_PATH = EVALS_DIR / "cohort" / "profiles_v4_vitamins.json"

sys.path.insert(0, str(PROJECT_ROOT))

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)

from evals import cohort_generator_v2_latent as base

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


CONDITION_IDS = [
    "perimenopause",
    "hypothyroidism",
    "kidney_disease",
    "sleep_disorder",
    "anemia",
    "iron_deficiency",
    "hepatitis",
    "liver",
    "prediabetes",
    "inflammation",
    "electrolyte_imbalance",
    "vitamin_b12_deficiency",
    "vitamin_d_deficiency",
]

CONDITION_PREFIX = {
    "perimenopause": "PMN",
    "hypothyroidism": "THY",
    "kidney_disease": "KDN",
    "sleep_disorder": "SLP",
    "anemia": "ANM",
    "iron_deficiency": "IRN",
    "hepatitis": "HEP",
    "liver": "LVR",
    "prediabetes": "PRD",
    "inflammation": "INF",
    "electrolyte_imbalance": "ELC",
    "vitamin_b12_deficiency": "B12",
    "vitamin_d_deficiency": "VID",
}

BAYESIAN_PRIORS = {
    "hypothyroidism": 0.062,
    "kidney_disease": 0.035,
    "hepatitis": 0.026,
    "liver": 0.050,
    "iron_deficiency": 0.060,
    "inflammation": 0.324,
    "perimenopause": 0.400,
    "sleep_disorder": 0.200,
    "anemia": 0.080,
    "prediabetes": 0.380,
    "electrolyte_imbalance": 0.080,
    "vitamin_b12_deficiency": 0.020,
    "vitamin_d_deficiency": 0.360,
}

COMORBIDITY_PAIRS = [
    ("anemia", "iron_deficiency"),
    ("anemia", "vitamin_b12_deficiency"),
    ("iron_deficiency", "vitamin_b12_deficiency"),
    ("kidney_disease", "electrolyte_imbalance"),
    ("hepatitis", "liver"),
    ("prediabetes", "sleep_disorder"),
    ("prediabetes", "vitamin_d_deficiency"),
    ("sleep_disorder", "vitamin_d_deficiency"),
    ("perimenopause", "vitamin_d_deficiency"),
    ("inflammation", "vitamin_d_deficiency"),
    ("hypothyroidism", "anemia"),
    ("kidney_disease", "anemia"),
]


def _patch_base_constants() -> None:
    base.CONDITION_IDS = CONDITION_IDS
    base.CONDITION_PREFIX = CONDITION_PREFIX
    base.BAYESIAN_PRIORS = BAYESIAN_PRIORS
    base.COMORBIDITY_PAIRS = COMORBIDITY_PAIRS

    for factor in ("b12_depletion", "vitamin_d_depletion", "low_sun_exposure", "malabsorption"):
        if factor not in base.LATENT_FACTORS:
            base.LATENT_FACTORS.append(factor)

    base.FACTOR_BASELINE.update(
        {
            "b12_depletion": 0.05,
            "vitamin_d_depletion": 0.10,
            "low_sun_exposure": 0.16,
            "malabsorption": 0.05,
        }
    )

    base.CONDITION_FACTOR_WEIGHTS.update(
        {
            "liver": {
                "alcohol_exposure": 0.55,
                "digestive_irritation": 0.60,
                "inflammation_load": 0.40,
                "medication_burden": 0.25,
            },
            "vitamin_b12_deficiency": {
                "b12_depletion": 0.95,
                "malabsorption": 0.55,
                "iron_depletion": 0.20,
                "digestive_irritation": 0.20,
                "medication_burden": 0.20,
            },
            "vitamin_d_deficiency": {
                "vitamin_d_depletion": 0.95,
                "low_sun_exposure": 0.65,
                "inflammation_load": 0.15,
                "kidney_impairment": 0.15,
                "menopause_transition": 0.10,
            },
        }
    )

    base.MIMIC_FACTOR_WEIGHTS.update(
        {
            "liver": [
                {"digestive_irritation": 0.55, "alcohol_exposure": 0.40},
                {"inflammation_load": 0.45, "medication_burden": 0.35},
            ],
            "vitamin_b12_deficiency": [
                {"iron_depletion": 0.45, "sleep_fragmentation": 0.35},
                {"malabsorption": 0.35, "digestive_irritation": 0.35},
            ],
            "vitamin_d_deficiency": [
                {"sleep_fragmentation": 0.40, "inflammation_load": 0.35},
                {"kidney_impairment": 0.30, "low_sun_exposure": 0.35},
            ],
        }
    )

    base.LAB_REFERENCE.update(
        {
            "vitamin_b12": (430.0, 110.0),
            "alt_u_l": (24.0, 10.0),
            "ast_u_l": (23.0, 8.0),
        }
    )


_patch_base_constants()
_ORIG_SAMPLE_DEMOGRAPHICS = base.sample_demographics
_ORIG_LATENT_TO_LABS = base.latent_to_labs
_ORIG_GENERATE_BAYESIAN_ANSWERS = base.generate_bayesian_answers


def sample_demographics(
    rng: random.Random,
    nprng: np.random.Generator,
    condition: str | None,
    profile_type: str,
) -> dict[str, Any]:
    if condition == "liver":
        sex = rng.choice(["F", "M"])
        age = int(np.clip(nprng.normal(49, 12), 24, 82))
        bmi = round(float(np.clip(nprng.normal(29.0, 5.6), 17.0, 45.0)), 1)
        smoking = rng.choices(["never", "former", "current"], weights=[46, 28, 26])[0]
        activity = rng.choices(["sedentary", "low", "moderate", "high"], weights=[26, 32, 30, 12])[0]
        return {
            "age": age,
            "sex": sex,
            "bmi": bmi,
            "smoking_status": smoking,
            "activity_level": activity,
        }

    if condition == "vitamin_b12_deficiency":
        sex = rng.choices(["F", "M"], weights=[3, 2])[0]
        age = int(np.clip(nprng.normal(54, 15), 18, 85))
        bmi = round(float(np.clip(nprng.normal(26.5, 5.0), 16.0, 42.0)), 1)
        smoking = rng.choices(["never", "former", "current"], weights=[58, 27, 15])[0]
        activity = rng.choices(["sedentary", "low", "moderate", "high"], weights=[26, 31, 31, 12])[0]
        return {
            "age": age,
            "sex": sex,
            "bmi": bmi,
            "smoking_status": smoking,
            "activity_level": activity,
        }

    if condition == "vitamin_d_deficiency":
        sex = rng.choices(["F", "M"], weights=[3, 2])[0]
        age = int(np.clip(nprng.normal(50, 14), 18, 85))
        bmi = round(float(np.clip(nprng.normal(30.5, 5.8), 17.0, 48.0)), 1)
        smoking = rng.choices(["never", "former", "current"], weights=[56, 28, 16])[0]
        activity = rng.choices(["sedentary", "low", "moderate", "high"], weights=[30, 32, 28, 10])[0]
        return {
            "age": age,
            "sex": sex,
            "bmi": bmi,
            "smoking_status": smoking,
            "activity_level": activity,
        }

    return _ORIG_SAMPLE_DEMOGRAPHICS(rng, nprng, condition, profile_type)


def latent_to_labs(
    state: dict[str, float],
    demographics: dict[str, Any],
    profile_type: str,
    nprng: np.random.Generator,
) -> dict[str, float]:
    labs = _ORIG_LATENT_TO_LABS(state, demographics, profile_type, nprng)
    bmi = demographics["bmi"]

    labs["vitamin_b12"] = (
        455.0
        - 255.0 * state["b12_depletion"]
        - 120.0 * state["malabsorption"]
        - 35.0 * state["iron_depletion"]
        + nprng.normal(0.0, 35.0)
    )
    labs["vitamin_d"] = (
        36.0
        - 18.0 * state["vitamin_d_depletion"]
        - 11.0 * state["low_sun_exposure"]
        - 4.0 * state["kidney_impairment"]
        - 0.15 * max(bmi - 25.0, 0.0)
        + nprng.normal(0.0, 3.5)
    )
    labs["alt_u_l"] = (
        22.0
        + 34.0 * state["alcohol_exposure"]
        + 26.0 * state["digestive_irritation"]
        + 0.8 * max(bmi - 26.0, 0.0)
        + nprng.normal(0.0, 6.0)
    )
    labs["ast_u_l"] = (
        21.0
        + 22.0 * state["alcohol_exposure"]
        + 16.0 * state["digestive_irritation"]
        + nprng.normal(0.0, 5.0)
    )

    if profile_type == "healthy":
        labs["vitamin_b12"] = 460.0 + nprng.normal(0.0, 35.0)
        labs["vitamin_d"] = 34.0 + nprng.normal(0.0, 4.0)

    return {k: round(max(0.01, float(v)), 2) for k, v in labs.items()}


def generate_bayesian_answers(
    state: dict[str, float],
    symptoms: dict[str, float],
    demographics: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    answers = _ORIG_GENERATE_BAYESIAN_ANSWERS(state, symptoms, demographics, rng)

    answers.update(
        {
            "b12_q1": "yes" if state["medication_burden"] > 0.55 and rng.random() < 0.55 else "no",
            "b12_q2": "yes" if state["medication_burden"] > 0.50 and rng.random() < 0.45 else "no",
            "b12_q3": "yes" if rng.random() < (0.28 if state["b12_depletion"] > 0.60 else 0.08) else "no",
            "b12_q4": "yes" if state["malabsorption"] > 0.45 else "no",
            "b12_q5": "yes" if (symptoms["cognitive_impairment"] > 0.50 or symptoms["post_exertional_malaise"] > 0.45) else "no",
            "vitd_q1": "yes" if state["low_sun_exposure"] > 0.42 else "no",
            "vitd_q2": "yes" if demographics["bmi"] >= 30 else "no",
            "vitd_q3": "yes" if state["malabsorption"] > 0.45 else "no",
            "vitd_q4": "yes" if state["kidney_impairment"] > 0.45 else "no",
            "vitd_q5": "yes" if (
                symptoms["joint_pain"] > 0.42
                or symptoms["post_exertional_malaise"] > 0.48
                or symptoms["fatigue_severity"] > 0.60
            ) else "no",
        }
    )

    return answers


base.sample_demographics = sample_demographics
base.latent_to_labs = latent_to_labs
base.generate_bayesian_answers = generate_bayesian_answers


def generate_cohort(seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    profiles: list[dict[str, Any]] = []

    for condition in CONDITION_IDS:
        prefix = CONDITION_PREFIX[condition]
        prior = BAYESIAN_PRIORS.get(condition, 0.10)
        n_pos, n_bord, n_neg = base.adjusted_split(prior)
        cond_index = 0

        for _ in range(n_pos):
            cond_index += 1
            profiles.append(base.generate_profile("positive", condition, prefix, cond_index, rng, nprng))
        for _ in range(n_bord):
            cond_index += 1
            profiles.append(base.generate_profile("borderline", condition, prefix, cond_index, rng, nprng))
        for _ in range(n_neg):
            cond_index += 1
            profiles.append(base.generate_profile("negative", condition, prefix, cond_index, rng, nprng))

    for idx in range(1, 31):
        profiles.append(base.generate_profile("healthy", None, "HLT", idx, rng, nprng))

    for idx, (cond_a, cond_b) in enumerate(COMORBIDITY_PAIRS, start=1):
        profiles.append(base.generate_profile("edge", None, "EDG", idx, rng, nprng, edge_conditions=[cond_a, cond_b]))

    for idx in range(len(COMORBIDITY_PAIRS) + 1, len(COMORBIDITY_PAIRS) + 9):
        n_conditions = rng.choice([2, 2, 3])
        edge_conditions = rng.sample(CONDITION_IDS, n_conditions)
        profiles.append(base.generate_profile("edge", None, "EDG", idx, rng, nprng, edge_conditions=edge_conditions))

    expected_n = len(CONDITION_IDS) * 50 + 30 + len(COMORBIDITY_PAIRS) + 8
    assert len(profiles) == expected_n, f"Expected {expected_n} profiles, got {len(profiles)}"
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a vitamin-aware latent synthetic cohort.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH), help="Output path")
    parser.add_argument("--validate", action="store_true", help="Validate only; do not write file")
    args = parser.parse_args()

    with SCHEMA_PATH.open() as f:
        schema = json.load(f)

    logger.info("Generating vitamin-aware latent cohort with seed=%d ...", args.seed)
    profiles = generate_cohort(seed=args.seed)
    logger.info("Validating %d profiles against schema ...", len(profiles))
    validate_all(profiles, schema)
    logger.info("All profiles passed schema validation")

    if args.validate:
        print(f"\n--validate mode: schema check passed for {len(profiles)} profiles (v4 vitamins). No file written.\n")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    base.print_summary(profiles, args.seed, output_path)


if __name__ == "__main__":
    main()
