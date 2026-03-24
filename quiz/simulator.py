"""
QuizSimulator stub.
Takes a dict of symptom scores, returns structured quiz output.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Mapping from symptom_vector keys to quiz question IDs
SYMPTOM_TO_QUESTION = {
    "fatigue_severity":        "dpq040",   # PHQ-4 tiredness
    "sleep_quality":           "slq050",   # SLQ sleep trouble
    "post_exertional_malaise": "cdq010",   # Short of breath / exertion
    "joint_pain":              "mpq010",   # Joint pain
    "cognitive_impairment":    "dpq030",   # Concentration difficulty
    "depressive_mood":         "dpq010",   # PHQ-4 depressed mood
    "anxiety_level":           "dpq020",   # PHQ-4 anxiety
    "digestive_symptoms":      "bpq070",   # GI symptoms proxy
    "heat_intolerance":        "mcq160l",  # Heat intolerance proxy
    "weight_change":           "whq030",   # Weight change
}


class QuizSimulator:
    """
    Simulates the HalfFull assessment quiz.

    Takes a normalised symptom_vector dict (float 0-1 per symptom) and
    optional lab_values, and returns a structured quiz output dict ready
    for MedGemma inference.
    """

    def __init__(self, symptom_scores: dict[str, float]):
        self.symptom_scores = symptom_scores
        self._output: dict | None = None

    def run(
        self,
        lab_values: dict | None = None,
        skip_modules: list[int] | None = None,
    ) -> dict:
        """
        Run the quiz simulation.

        Args:
            lab_values: Optional lab results dict. If provided, the Lab Gate
                        is applied and modules 2+3 are skipped.
            skip_modules: Explicit list of module numbers to skip.

        Returns:
            Structured quiz output dict.
        """
        answers: dict[str, float] = {}

        # Translate symptom scores to quiz answer format
        for symptom, score in self.symptom_scores.items():
            question_id = SYMPTOM_TO_QUESTION.get(symptom)
            if question_id:
                answers[question_id] = round(score, 4)

        # Build structured output
        output = {
            "answers": answers,
            "symptom_summary": self.symptom_scores,
            "lab_values": lab_values,
            "modules_completed": [1] if (lab_values or skip_modules) else [1, 2, 3],
            "quiz_path": "hybrid" if lab_values else "full",
            "n_questions_answered": len(answers),
        }

        if lab_values:
            output["lab_values"] = lab_values
            # Modules 2 and 3 use detailed questionnaire branching; with labs, skip them
            output["modules_completed"] = [1, 4]
            logger.debug("Lab Gate applied — skipping Modules 2 and 3")

        self._output = output
        return output
