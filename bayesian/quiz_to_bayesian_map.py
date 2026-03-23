"""
quiz_to_bayesian_map.py
-----------------------
Translation table: quiz field IDs → Bayesian question IDs + answer converters.

When the assessment quiz has already collected a value that semantically
matches a Bayesian clarification question, the Bayesian layer can use it
silently — the patient is not asked the same thing twice.

Confirmed overlaps identified by cross-referencing quiz_nhanes_v2.json
with lr_tables.json (see exploration report in project context):

  rhq031  (regular periods flag)     ↔  peri_q3       (menstrual irregularity — logically flipped)
  slq030  (snoring frequency scale)  ↔  sleep_q2      (snores loudly — binary)
  slq050  (doctor-told sleep trouble) ↔ sleep_q5      (difficulty sleeping ≥3 nights/week)
  kiq480  (nocturia count per night)  ↔ kidney_q3     (wakes to urinate)
  kiq480  (nocturia count per night)  ↔ prediabetes_q3 (urinary frequency inc. nocturia)

NHANES answer codes used here:
  rhq031:  1 = regular periods, 2 = irregular / no periods in past 12 months
  slq030:  1 = never, 2 = rarely, 3 = occasionally, 4 = frequently, 5 = always
  slq050:  1 = yes (ever told by doctor), 2 = no
  kiq480:  ordinal count: 0 = zero, 1 = once, 2 = twice, 3 = three or more times
"""

from typing import Union

# ── Translation table ─────────────────────────────────────────────────────────
#
# Each entry maps one quiz field to one Bayesian question (or a list of them).
#
# Keys:
#   "bayesian_id" — str or list[str]: target Bayesian question ID(s)
#   "convert"     — callable(str) -> str: maps raw quiz answer to Bayesian answer value
#
# Converter functions always receive the raw quiz answer as a string (quiz answers
# from the frontend are string-encoded NHANES codes).
# They must return "yes" / "no" for binary Bayesian questions.

QUIZ_TO_BAYESIAN: dict[str, dict[str, Union[str, list, object]]] = {
    "rhq031___had_regular_periods_in_past_12_months": {
        # Quiz:     "Have your periods been regular in the past year?"
        #           1 = regular, 2 = irregular / absent
        # Bayesian: "Have your menstrual cycles become irregular?"  (peri_q3)
        #           Answers are logically inverted: regular(1) → no, irregular(2) → yes
        "bayesian_id": "peri_q3",
        "convert": lambda v: "yes" if str(v) == "2" else "no",
    },
    "slq030___how_often_do_you_snore?": {
        # Quiz:     "How often do you snore while sleeping?"
        #           1=never, 2=rarely, 3=occasionally, 4=frequently, 5=always
        # Bayesian: "Do you snore loudly (loud enough to be heard through a closed door)?"  (sleep_q2)
        #           Threshold: ≥2 (rarely or more) counts as snoring
        "bayesian_id": "sleep_q2",
        "convert": lambda v: "yes" if int(v) >= 2 else "no",
    },
    "slq050___ever_told_doctor_had_trouble_sleeping?": {
        # Quiz:     "Has a doctor ever told you that you have trouble sleeping?"
        #           1 = yes, 2 = no
        # Bayesian: "Do you have difficulty falling or staying asleep ≥3 nights/week?"  (sleep_q5)
        #           A doctor diagnosis is a conservative proxy for the symptom being present
        "bayesian_id": "sleep_q5",
        "convert": lambda v: "yes" if str(v) == "1" else "no",
    },
    "kiq480___how_many_times_urinate_in_night?": {
        # Quiz:     "On a typical night, how many times do you wake up to urinate?"
        #           ordinal count (0, 1, 2, 3+)
        # Bayesian: Both kidney_q3 and prediabetes_q3 tap nocturia.
        #           Threshold: ≥2 waking episodes per night = clinically meaningful nocturia
        "bayesian_id": ["kidney_q3", "prediabetes_q3"],
        "convert": lambda v: "yes" if int(v) >= 2 else "no",
    },
}

# Short-key aliases so callers can look up by bare NHANES field ID too.
# The quiz stores answers under either the full or bare key depending on path.
_ALIASES: dict[str, str] = {
    "rhq031":  "rhq031___had_regular_periods_in_past_12_months",
    "slq030":  "slq030___how_often_do_you_snore?",
    "slq050":  "slq050___ever_told_doctor_had_trouble_sleeping?",
    "kiq480":  "kiq480___how_many_times_urinate_in_night?",
}


def get_prefilled_answers(quiz_answers: dict) -> dict:
    """
    Translate known quiz answers into Bayesian question answers.

    Checks every quiz field in QUIZ_TO_BAYESIAN (plus short-key aliases).
    Fields that are absent from quiz_answers, or whose value cannot be
    converted, are skipped silently — no exception is raised.

    Parameters
    ----------
    quiz_answers : dict
        Raw quiz answers keyed by NHANES field IDs (values may be str or int).
        Identical to the dict received by score_answers.py.

    Returns
    -------
    dict[str, str]
        {bayesian_question_id: converted_answer} for every successfully
        translated field.  Empty dict when quiz_answers is falsy or contains
        no mapped fields.
    """
    if not quiz_answers:
        # No quiz answers supplied — nothing to prefill; callers stay unchanged
        return {}

    prefilled: dict[str, str] = {}

    # Normalise quiz_answers: resolve aliases so we always look up by full key
    normalised = {}
    for k, v in quiz_answers.items():
        full_key = _ALIASES.get(k, k)  # expand alias if present, else use as-is
        normalised[full_key] = v

    for full_key, mapping in QUIZ_TO_BAYESIAN.items():
        raw_value = normalised.get(full_key)
        if raw_value is None:
            # Quiz field was not answered — skip; do not surface a default
            continue

        try:
            converted: str = mapping["convert"](raw_value)
        except (ValueError, TypeError):
            # Non-convertible value (e.g. free-text in a numeric field) — skip safely
            continue

        bayesian_id = mapping["bayesian_id"]
        if isinstance(bayesian_id, list):
            # One quiz field maps to multiple Bayesian question IDs (kiq480 case)
            for bid in bayesian_id:
                prefilled[bid] = converted
        else:
            prefilled[bayesian_id] = converted

    return prefilled
