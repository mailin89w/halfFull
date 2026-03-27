"""
run_bayesian.py
---------------
Subprocess entry point for the Bayesian update layer.
Called by Next.js API routes via child_process.spawn, same pattern as score_answers.py.

Reads JSON from stdin, writes JSON to stdout.

Input modes
-----------
1. "questions" — return structured follow-up questions for triggered conditions
   {
     "mode": "questions",
     "ml_scores": { "anemia": 0.55, "thyroid": 0.62, ... },
     "patient_sex": "female"          // optional
   }
   Output:
   {
     "condition_questions": [
       { condition, probability, questions: [{ id, text, answer_type, answer_options }, ...] },
       ...
     ]
   }

2. "update" — compute Bayesian posteriors from answers
   {
     "mode": "update",
     "ml_scores": { "anemia": 0.55, ... },
     "confounder_answers": { "phq2_q1": 1, "phq2_q2": 0, "gad2_q1": 0, "gad2_q2": 0 },
     "answers_by_condition": { "anemia": { "anemia_q1": "yes" }, ... },
     "patient_sex": "female"
   }
   Output:
   {
     "posterior_scores": { "anemia": 0.80, "thyroid": 0.62, ... },
     "details": { "anemia": { prior, posterior, lrs_applied, ... }, ... }
   }
"""

import json
import sys
import os

# Ensure the project root is on the path so bayesian/ is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from bayesian.bayesian_updater import BayesianUpdater  # noqa: E402
from bayesian.quiz_to_bayesian_map import get_prefilled_answers  # noqa: E402
from models_normalized.model_runner import BAYESIAN_TRIGGER_THRESHOLDS  # noqa: E402

NORMALIZED_TO_LEGACY_KEYS = {
    "anemia": "anemia",
    "iron_deficiency": "iron_deficiency",
    "thyroid": "thyroid",
    "kidney": "kidney",
    "sleep_disorder": "sleep_disorder",
    "liver": "liver",
    "prediabetes": "prediabetes",
    "hidden_inflammation": "inflammation",
    "electrolyte_imbalance": "electrolytes",
    "hepatitis_bc": "hepatitis",
    "perimenopause": "perimenopause",
}

LEGACY_FILTER_CRITERIA = {
    legacy_key: BAYESIAN_TRIGGER_THRESHOLDS[normalized_key]
    for normalized_key, legacy_key in NORMALIZED_TO_LEGACY_KEYS.items()
    if normalized_key in BAYESIAN_TRIGGER_THRESHOLDS
}

DISABLED_QUESTION_IDS = {
    "anemia_q3",
    "thyroid_q4",
    "thyroid_q5",
    "prediabetes_q2",
    "elec_q1",
    "hep_q1",
    "peri_q1",
}

SHARED_QUESTION_GROUPS = {
    "heavy_periods": {"anemia_q1", "iron_q1", "peri_q4"},
    "unusual_blood_loss": {"anemia_q2", "iron_q3"},
    "blood_donation": {"anemia_q3", "iron_q4"},
    "vegetarian": {"anemia_q4", "iron_q2"},
    "nocturia": {"kidney_q3", "prediabetes_q3"},
    "snoring": {"sleep_q2"},
    "alcohol_intake": {"liver_q1", "elec_q1", "hep_q1"},
    "jaundice": {"liver_q4", "hep_q2"},
}

QUESTION_TO_SHARED_KEY = {
    qid: shared_key
    for shared_key, ids in SHARED_QUESTION_GROUPS.items()
    for qid in ids
}

MAX_CONDITIONS = 5   # max suspect disease clarification screens
MAX_Q_PER_COND = 50  # surface all available Bayesian questions for that disease


def _canonical_question_key(question_id: str) -> str:
    return QUESTION_TO_SHARED_KEY.get(question_id, question_id)


def _translate_shared_answer(target_qid: str, answer: str) -> str:
    """
    Translate a shared answer into the target question's answer vocabulary.
    Most shared groups are literal yes/no copies; alcohol uses condition-
    specific category labels.
    """
    if target_qid in {"elec_q1", "hep_q1"}:
        if answer in {"none", "low", "low_none"}:
            return "low_none"
    if target_qid == "liver_q1" and answer == "low_none":
        return "low"
    return answer


def _build_question_to_condition_map(updater: BayesianUpdater, patient_sex: str | None) -> dict[str, str]:
    q_to_condition: dict[str, str] = {}
    for condition in updater._conditions:
        for question in updater.get_questions(condition, prior_prob=0.5, patient_sex=patient_sex, max_questions=50):
            q_to_condition[question["id"]] = condition
    return q_to_condition


def _apply_shared_answers_to_conditions(
    answers_by_condition: dict[str, dict[str, str]],
    q_to_condition: dict[str, str],
) -> None:
    shared_answers: dict[str, str] = {}
    for cond_answers in answers_by_condition.values():
        for qid, answer in cond_answers.items():
            shared_key = QUESTION_TO_SHARED_KEY.get(qid)
            if shared_key and shared_key not in shared_answers:
                shared_answers[shared_key] = answer

    for shared_key, answer in shared_answers.items():
        for target_qid in SHARED_QUESTION_GROUPS[shared_key]:
            target_condition = q_to_condition.get(target_qid)
            if not target_condition:
                continue
            cond_answers = answers_by_condition.setdefault(target_condition, {})
            cond_answers.setdefault(target_qid, _translate_shared_answer(target_qid, answer))


def handle_questions(payload: dict, updater: BayesianUpdater) -> dict:
    ml_scores   = payload.get("ml_scores", {})
    patient_sex = payload.get("patient_sex")
    existing_answers = payload.get("existing_answers", {})

    # Translate quiz answers that overlap with Bayesian questions
    prefilled = get_prefilled_answers(existing_answers)
    prefilled_keys = {_canonical_question_key(qid) for qid in prefilled}

    # Condition questions: top MAX_CONDITIONS triggered by per-disease filter criteria
    triggered = sorted(
        [
            (cond, prob)
            for cond, prob in ml_scores.items()
            if prob >= LEGACY_FILTER_CRITERIA.get(cond, 1.0)
        ],
        key=lambda x: x[1],
        reverse=True,
    )[:MAX_CONDITIONS]

    condition_questions = []
    asked_shared_keys = set(prefilled_keys)
    for condition, prob in triggered:
        questions = updater.get_questions(
            condition,
            prior_prob=prob,
            patient_sex=patient_sex,
            max_questions=MAX_Q_PER_COND,
        )
        filtered_questions = []
        for q in questions:
            qid = q["id"]
            shared_key = _canonical_question_key(qid)
            if qid in DISABLED_QUESTION_IDS:
                continue
            if qid in prefilled or shared_key in asked_shared_keys:
                continue
            filtered_questions.append(q)
            asked_shared_keys.add(shared_key)

        questions = filtered_questions
        if not questions:
            continue
        condition_questions.append({
            "condition":   condition,
            "probability": round(prob, 4),
            "questions": [
                {
                    "id":             q["id"],
                    "text":           q["text"],
                    "answer_type":    q["answer_type"],
                    "answer_options": [
                        {"value": str(o["value"]), "label": o["label"]}
                        for o in q["answer_options"]
                    ],
                }
                for q in questions
            ],
        })

    return {
        "condition_questions":  condition_questions,
    }


def handle_update(payload: dict, updater: BayesianUpdater) -> dict:
    ml_scores            = payload.get("ml_scores", {})
    confounder_answers   = payload.get("confounder_answers", {})
    answers_by_condition = payload.get("answers_by_condition", {})
    patient_sex          = payload.get("patient_sex")
    existing_answers     = payload.get("existing_answers", {})

    # Translate quiz answers into Bayesian answers and merge into answers_by_condition.
    # Build a reverse map: {bayesian_question_id: condition} from the updater's conditions.
    prefilled = get_prefilled_answers(existing_answers)
    prefilled = {
        qid: answer
        for qid, answer in prefilled.items()
        if qid not in DISABLED_QUESTION_IDS
    }
    if prefilled:
        # Map each Bayesian question ID back to its condition
        q_to_condition = _build_question_to_condition_map(updater, patient_sex)

        for q_id, answer in prefilled.items():
            condition = q_to_condition.get(q_id)
            if condition is None:
                continue
            # User-supplied answers take priority — only fill if not already answered
            cond_answers = answers_by_condition.setdefault(condition, {})
            if q_id not in cond_answers:
                cond_answers[q_id] = answer

    for condition, cond_answers in list(answers_by_condition.items()):
        answers_by_condition[condition] = {
            qid: answer
            for qid, answer in cond_answers.items()
            if qid not in DISABLED_QUESTION_IDS
        }

    q_to_condition = _build_question_to_condition_map(updater, patient_sex)
    _apply_shared_answers_to_conditions(answers_by_condition, q_to_condition)

    # Build shortlist from all conditions (not just triggered ones, so
    # non-triggered conditions pass through unchanged)
    shortlist = [
        {"condition": cond, "probability": prob}
        for cond, prob in ml_scores.items()
    ]

    updated = updater.update_shortlist(
        shortlist=shortlist,
        answers_by_condition=answers_by_condition,
        confounder_answers=confounder_answers if confounder_answers else None,
        patient_sex=patient_sex,
    )

    posterior_scores = {item["condition"]: item["probability"] for item in updated}
    details          = {item["condition"]: item.get("bayesian_detail", {}) for item in updated}

    return {
        "posterior_scores": posterior_scores,
        "details":          details,
    }


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "Empty stdin"}))
        sys.exit(1)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON: {exc}"}))
        sys.exit(1)

    mode = payload.get("mode", "update")

    try:
        updater = BayesianUpdater()
    except Exception as exc:
        print(json.dumps({"error": f"Failed to load BayesianUpdater: {exc}"}))
        sys.exit(1)

    try:
        if mode == "questions":
            result = handle_questions(payload, updater)
        elif mode == "update":
            result = handle_update(payload, updater)
        else:
            result = {"error": f"Unknown mode: {mode}"}
    except Exception as exc:
        result = {"error": str(exc)}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
