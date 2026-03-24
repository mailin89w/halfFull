"""
quiz_simulator_adapter.py — Wraps quiz.QuizSimulator for eval pipeline use.

Translates a synthetic profile's symptom_vector into QuizSimulator input
format and applies the Lab Gate (hybrid quiz path) when lab_values are present.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from quiz import QuizSimulator
    _SIMULATOR_AVAILABLE = True
except ImportError:
    _SIMULATOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class QuizSimulatorAdapter:
    """
    Adapts a synthetic profile for use with quiz.QuizSimulator.

    If the profile has lab_values (hybrid path), injects them into the
    simulator and applies the Lab Gate (Modules 2+3 are skipped).
    """

    def run(self, profile: dict) -> dict:
        """
        Run the quiz simulator for a given profile.

        Args:
            profile: A validated synthetic profile dict.

        Returns:
            Structured quiz output dict ready for MedGemma inference.
        """
        symptom_vector: dict[str, float] = profile.get("symptom_vector", {})
        lab_values: dict | None = profile.get("lab_values")
        quiz_path: str = profile.get("quiz_path", "full")

        if _SIMULATOR_AVAILABLE:
            simulator = QuizSimulator(symptom_scores=symptom_vector)
            quiz_output = simulator.run(
                lab_values=lab_values,
                skip_modules=[2, 3] if lab_values else None,
            )
        else:
            # Fallback: build a minimal quiz output dict directly
            logger.warning(
                "QuizSimulator not available — using fallback output builder"
            )
            quiz_output = _build_fallback_output(profile, symptom_vector, lab_values, quiz_path)

        # Attach profile metadata useful for prompting
        quiz_output["profile_id"] = profile.get("profile_id")
        quiz_output["demographics"] = profile.get("demographics", {})

        return quiz_output


def _build_fallback_output(
    profile: dict,
    symptom_vector: dict,
    lab_values: dict | None,
    quiz_path: str,
) -> dict:
    """Minimal quiz output when QuizSimulator is unavailable."""
    return {
        "answers": symptom_vector,
        "symptom_summary": symptom_vector,
        "lab_values": lab_values,
        "modules_completed": [1, 4] if lab_values else [1, 2, 3],
        "quiz_path": quiz_path,
        "n_questions_answered": len(symptom_vector),
    }
