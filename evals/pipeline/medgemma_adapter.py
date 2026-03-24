"""
medgemma_adapter.py — Wraps medgemma_client.query() for eval pipeline use.

Builds a structured prompt from quiz output, handles timeouts and retries.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import medgemma_client as _client
    _CLIENT_AVAILABLE = True
except ImportError:
    _CLIENT_AVAILABLE = False

try:
    from config import CONDITION_IDS
except ImportError:
    CONDITION_IDS = [
        "menopause", "perimenopause", "hypothyroidism", "kidney_disease",
        "sleep_disorder", "anemia", "iron_deficiency", "hepatitis",
        "prediabetes", "inflammation", "electrolyte_imbalance",
    ]

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 2.0   # seconds between retries
TIMEOUT = 30        # seconds per request

PROMPT_TEMPLATE = """You are a medical reasoning assistant. Based on the following patient questionnaire responses, rank the top 3 most likely conditions from this list: {condition_ids}.
Return ONLY valid JSON in this exact format:
{{
  "top_conditions": [
    {{"condition_id": "<id>", "confidence": <0.0-1.0>, "reasoning": "<max 2 sentences>"}},
    {{"condition_id": "<id>", "confidence": <0.0-1.0>, "reasoning": "<max 2 sentences>"}},
    {{"condition_id": "<id>", "confidence": <0.0-1.0>, "reasoning": "<max 2 sentences>"}}
  ]
}}
Patient data:
{quiz_output}"""


class MedGemmaAdapter:
    """
    Wraps medgemma_client.query() with structured prompt building,
    retry logic, and timeout handling.
    """

    def __init__(
        self,
        condition_ids: list[str] | None = None,
        max_retries: int = MAX_RETRIES,
        timeout: int = TIMEOUT,
    ) -> None:
        self.condition_ids = condition_ids or CONDITION_IDS
        self.max_retries = max_retries
        self.timeout = timeout

    def _build_prompt(self, quiz_output: dict, profile: dict) -> str:
        """Construct the MedGemma prompt from quiz output."""
        condition_ids_str = ", ".join(self.condition_ids)

        # Build a concise, structured patient data string
        symptom_summary = quiz_output.get("symptom_summary", quiz_output.get("answers", {}))
        demographics = quiz_output.get("demographics", profile.get("demographics", {}))
        lab_values = quiz_output.get("lab_values")

        patient_lines = []

        # Demographics
        if demographics:
            patient_lines.append(
                f"Age: {demographics.get('age', 'unknown')}, "
                f"Sex: {demographics.get('sex', 'unknown')}, "
                f"BMI: {demographics.get('bmi', 'unknown')}"
            )

        # Symptom scores
        if symptom_summary:
            patient_lines.append("Symptom scores (0=absent, 1=severe):")
            for symptom, score in symptom_summary.items():
                patient_lines.append(f"  {symptom}: {score:.2f}")

        # Lab values (if present)
        if lab_values:
            patient_lines.append("Lab values:")
            for lab, value in lab_values.items():
                patient_lines.append(f"  {lab}: {value:.2f}")

        quiz_output_str = "\n".join(patient_lines)

        return PROMPT_TEMPLATE.format(
            condition_ids=condition_ids_str,
            quiz_output=quiz_output_str,
        )

    def query(self, quiz_output: dict, profile: dict) -> str:
        """
        Query MedGemma with the built prompt.

        Retries up to max_retries times on network/timeout errors.
        Returns the raw response string, or raises on all retries exhausted.
        """
        if not _CLIENT_AVAILABLE:
            raise RuntimeError(
                "medgemma_client not available. "
                "Ensure medgemma_client.py is at the project root and "
                "the Colab tunnel is running."
            )

        prompt = self._build_prompt(quiz_output, profile)

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                logger.debug(
                    "MedGemma query attempt %d/%d for profile %s",
                    attempt,
                    self.max_retries + 1,
                    profile.get("profile_id", "?"),
                )
                response = _client.query(prompt, timeout=self.timeout)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "MedGemma attempt %d failed: %s", attempt, exc
                )
                if attempt <= self.max_retries:
                    time.sleep(RETRY_DELAY)

        raise RuntimeError(
            f"MedGemma unreachable after {self.max_retries + 1} attempts: {last_error}"
        )
