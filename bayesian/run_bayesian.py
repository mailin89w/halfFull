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
     "confounder_questions": [ { id, text, answer_options }, ... ],
     "condition_questions":  [ { condition, probability, question: { id, text, answer_type, answer_options } }, ... ]
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

TRIGGER_THRESHOLD = 0.40
MAX_CONDITIONS    = 3   # max conditions to surface questions for
MAX_Q_PER_COND   = 1   # questions per condition shown in clarify UI


def _best_question(questions: list[dict]) -> dict:
    """
    Pick the single most informative question for a condition.
    Informativeness = max LR across all answer options (largest spread).
    """
    def _info(q):
        lrs = [opt["lr"] for opt in q.get("answer_options", [])]
        return max(lrs) / min(lrs) if lrs and min(lrs) > 0 else 1.0

    return max(questions, key=_info)


def handle_questions(payload: dict, updater: BayesianUpdater) -> dict:
    ml_scores   = payload.get("ml_scores", {})
    patient_sex = payload.get("patient_sex")
    existing_answers = payload.get("existing_answers", {})

    # Translate quiz answers that overlap with Bayesian questions
    prefilled = get_prefilled_answers(existing_answers)

    # Condition questions: top MAX_CONDITIONS triggered, one best question each
    triggered = sorted(
        [(cond, prob) for cond, prob in ml_scores.items() if prob >= TRIGGER_THRESHOLD],
        key=lambda x: x[1],
        reverse=True,
    )[:MAX_CONDITIONS]

    # Confounder questions only shown when at least one condition triggered
    confounder_qs = []
    if triggered:
        for name, data in updater._confounders.items():
            if name.startswith("_"):
                continue
            for q in data["questions"]:
                confounder_qs.append({
                    "id":             q["id"],
                    "confounder":     name,
                    "text":           q["text"],
                    "answer_type":    q["answer_type"],
                    "answer_options": q["answer_options"],
                })

    condition_questions = []
    for condition, prob in triggered:
        questions = updater.get_questions(
            condition,
            prior_prob=prob,
            patient_sex=patient_sex,
            max_questions=10,
        )
        if not questions:
            continue
        # Skip questions whose answer was already prefilled from the quiz
        questions = [q for q in questions if q["id"] not in prefilled]
        if not questions:
            continue
        best = _best_question(questions)
        condition_questions.append({
            "condition":   condition,
            "probability": round(prob, 4),
            "question": {
                "id":             best["id"],
                "text":           best["text"],
                "answer_type":    best["answer_type"],
                "answer_options": [
                    {"value": str(o["value"]), "label": o["label"]}
                    for o in best["answer_options"]
                ],
            },
        })

    return {
        "confounder_questions": confounder_qs,
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
    if prefilled:
        # Map each Bayesian question ID back to its condition
        q_to_condition: dict[str, str] = {}
        for condition in updater._conditions:
            for q in updater.get_questions(condition, prior_prob=0.5, patient_sex=patient_sex, max_questions=50):
                q_to_condition[q["id"]] = condition

        for q_id, answer in prefilled.items():
            condition = q_to_condition.get(q_id)
            if condition is None:
                continue
            # User-supplied answers take priority — only fill if not already answered
            cond_answers = answers_by_condition.setdefault(condition, {})
            if q_id not in cond_answers:
                cond_answers[q_id] = answer

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
