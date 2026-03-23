#!/usr/bin/env python3
"""
score_answers.py
----------------
Reads a flat JSON answers dict from stdin (keyed by NHANES field_ids from
nhanes_combined_question_flow_v2.json), scores all 11 disease models via
questionnaire_to_model_features + ModelRunner, and writes a JSON scores dict
to stdout.

Frontend answer values arrive as strings (NHANES numeric codes); this script
coerces them to numbers before passing to the feature transformer.

Usage:
    echo '{"age_years": "45", "gender": "2", ...}' | python3 scripts/score_answers.py
    # → {"anemia": 0.31, "thyroid": 0.55, ...}
"""

import sys
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

USE_NORMALIZED_INFERENCE = os.getenv("HALFFULL_USE_NORMALIZED_INFERENCE", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Suppress model-loading log noise on stderr
import logging
logging.disable(logging.CRITICAL)

import warnings
warnings.filterwarnings("ignore")


def _coerce_num(value: str):
    """Try to coerce a string to int then float; return as-is if neither works."""
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return value


# All possible NHANES field IDs that can appear as options in conditions_diagnosed.
_CONDITIONS_FIELDS = [
    "bpq020___ever_told_you_had_high_blood_pressure",
    "bpq080___doctor_told_you___high_cholesterol_level",
    "diq010___doctor_told_you_have_diabetes",
    "mcq010___ever_been_told_you_have_asthma",
    "mcq160a___ever_told_you_had_arthritis",
    "kiq022___ever_told_you_had_weak/failing_kidneys?",
    "mcq160l___ever_told_you_had_any_liver_condition",
    "heq030___ever_told_you_have_hepatitis_c?",
    "mcq160b___ever_told_you_had_congestive_heart_failure",
    "mcq160e___ever_told_you_had_heart_attack",
    "mcq160f___ever_told_you_had_stroke",
    "mcq053___taking_treatment_for_anemia/past_3_mos",
    "mcq092___ever_receive_blood_transfusion",
    "slq060___ever_told_by_doctor_have_sleep_disorder",
    "mcq080___doctor_ever_said_you_were_overweight",
]


def _preprocess(answers: dict) -> dict:
    """
    Flatten compound frontend answers into flat NHANES fields, then coerce
    all string-encoded numerics.

    Handles:
    1. dual_numeric compound answers (dicts stored under compound question IDs)
       - "height_weight": {"height_cm": "...", "weight_kg": "..."} → flattened + BMI calculated
       - "sleep_hours":   {"sld012___...", "sld013___..."} → flattened
    2. conditions_diagnosed multi-select (list of selected field IDs)
       → each possible condition field set to 1 (selected) or 2 (not selected)
    3. All remaining string values coerced to int/float where possible.
    """
    flat: dict = {}

    for key, value in answers.items():
        if key == "height_weight" and isinstance(value, dict):
            # Flatten sub-fields
            height_cm = value.get("height_cm")
            weight_kg = value.get("weight_kg")
            if height_cm not in (None, ""):
                flat["height_cm"] = _coerce_num(str(height_cm))
            if weight_kg not in (None, ""):
                flat["weight_kg"] = _coerce_num(str(weight_kg))
            # Auto-calculate BMI
            try:
                h = float(str(height_cm))
                w = float(str(weight_kg))
                if h > 0:
                    flat["bmi"] = round(w / (h / 100) ** 2, 1)
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        elif key == "sleep_hours" and isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if sub_val not in (None, ""):
                    flat[sub_key] = _coerce_num(str(sub_val))

        elif key == "conditions_diagnosed":
            selected = set(value) if isinstance(value, list) else set()
            for field_id in _CONDITIONS_FIELDS:
                flat[field_id] = 1 if field_id in selected else 2

        elif isinstance(value, str):
            flat[key] = _coerce_num(value)

        elif key == "lab_upload" and isinstance(value, dict):
            # File upload answer — merge structuredValues into flat answers
            # (only for fields not already set by manual entry)
            structured = value.get("structuredValues")
            if structured and isinstance(structured, dict):
                for field_id, field_val in structured.items():
                    if field_id not in flat and field_val is not None:
                        try:
                            flat[field_id] = float(field_val)
                        except (TypeError, ValueError):
                            pass
            # Drop the compound object — not a numeric field for models

        elif isinstance(value, dict):
            # Generic dict: flatten sub-fields (coerce each value)
            for sub_key, sub_val in value.items():
                if sub_val not in (None, ""):
                    flat[sub_key] = _coerce_num(str(sub_val)) if isinstance(sub_val, str) else sub_val

        else:
            flat[key] = value

    # Derive alq111 (ever drank) from downstream answers if not already set.
    # alq111 = 2 (never) when avg drinks == 0 AND heavy drinking == 2 (no); else 1 (yes).
    if "alq111___ever_had_a_drink_of_any_kind_of_alcohol" not in flat:
        avg_drinks = flat.get("alq130___avg_#_alcoholic_drinks/day___past_12_mos", 0)
        heavy = flat.get("alq151___ever_have_4/5_or_more_drinks_every_day?", 2)
        flat["alq111___ever_had_a_drink_of_any_kind_of_alcohol"] = (
            2 if (avg_drinks == 0 and heavy == 2) else 1
        )

    return flat


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input received"}))
        sys.exit(1)

    try:
        answers = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON: {exc}"}))
        sys.exit(1)

    answers = _preprocess(answers)

    try:
        from models.questionnaire_to_model_features import build_feature_vectors
        from models.model_runner import ModelRunner

        feature_vectors = build_feature_vectors(
            answers,
            normalized_for_retrained_models=USE_NORMALIZED_INFERENCE,
        )
        runner = ModelRunner()
        scores = runner.run_all(feature_vectors)
        print(json.dumps(scores))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
