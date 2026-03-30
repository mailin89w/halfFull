"""
bayesian_updater.py
-------------------
Bayesian posterior update layer (Layer 1.5 in the HalfFull architecture).

Sits between the ML model runner and the LLM synthesis layer.
Triggered for any condition whose ML prior probability >= trigger_threshold (default 0.40).

Update rule (Bayes in odds form):
    prior_odds       = p / (1 - p)
    posterior_odds   = prior_odds × LR₁ × LR₂ × ... × LRₙ
    posterior_prob   = posterior_odds / (1 + posterior_odds)
    posterior_prob   = clip(posterior_prob, 0.05, 0.95)

Usage
-----
    from bayesian.bayesian_updater import BayesianUpdater

    updater = BayesianUpdater()

    # 1. Get confounder adjustments first (depression / anxiety)
    confounder_multiplier = updater.score_confounders({"phq2_q1": 2, "phq2_q2": 1,
                                                        "gad2_q1": 0, "gad2_q2": 0})

    # 2. Get questions to ask for a triggered condition
    questions = updater.get_questions("anemia", prior_prob=0.55, patient_sex="female")

    # 3. After user answers, compute posterior
    answers = {"anemia_q1": "yes", "anemia_q3": "yes", "anemia_q2": "no"}
    result  = updater.update("anemia", prior_prob=0.55,
                              answers=answers,
                              confounder_multiplier=confounder_multiplier)
    # result → {"prior": 0.55, "posterior": 0.81, "lrs_applied": [...], "questions_used": [...]}
"""

import json
import math
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
_LR_TABLES_PATH = os.path.join(_DIR, "lr_tables.json")

POSTERIOR_CLIP_LOW  = 0.05
POSTERIOR_CLIP_HIGH = 0.95


class BayesianUpdater:
    """
    Loads lr_tables.json once and exposes methods to:
      - select questions for a triggered condition
      - score PHQ-2 / GAD-2 confounder screens
      - compute a Bayesian posterior from prior + answers
    """

    def __init__(self, lr_tables_path: str = _LR_TABLES_PATH):
        with open(lr_tables_path, "r") as f:
            self._tables = json.load(f)
        self._conditions  = self._tables["conditions"]
        self._confounders = self._tables["confounders"]
        log.info(
            "BayesianUpdater loaded: %d conditions, %d confounders",
            len(self._conditions),
            sum(1 for k in self._confounders if not k.startswith("_")),
        )

    # ── Public API ──────────────────────────────────────────────────────────────

    def get_questions(
        self,
        condition: str,
        prior_prob: float,
        patient_sex: Optional[str] = None,
        max_questions: int = 5,
    ) -> list[dict]:
        """
        Return the ordered list of questions to ask the user for a given condition.

        Parameters
        ----------
        condition : str
            One of the ML conditions supported by the runner (e.g. "anemia", "perimenopause").
        prior_prob : float
            ML posterior probability for this condition (0–1).
        patient_sex : str, optional
            "female" or "male". Questions with gender_filter are skipped when
            the patient's sex does not match.
        max_questions : int
            Hard cap on how many questions to return (default 5).

        Returns
        -------
        list[dict]
            Each dict is a question entry from lr_tables.json, augmented with
            the condition name. Questions are pre-filtered for gender and for
            high-prior-only items (spider nevi, ascites require prior >= 0.50).
        """
        if condition not in self._conditions:
            log.warning("Unknown condition '%s' — no questions returned.", condition)
            return []

        questions = self._conditions[condition]["questions"]
        selected  = []

        for q in questions:
            # Gender filter
            gender_filter = q.get("gender_filter")
            if gender_filter and patient_sex and patient_sex.lower() != gender_filter:
                continue

            # High-prior-only filter: some questions (cirrhosis signs) are only
            # useful when the ML prior is already high
            note = q.get("supplementary_note", "") + q.get("_scope_note", "")
            if "≥0.50" in note and prior_prob < 0.50:
                continue

            selected.append({**q, "_condition": condition})

            if len(selected) >= max_questions:
                break

        return selected

    def get_confounder_questions(self) -> dict[str, list[dict]]:
        """
        Return PHQ-2 and GAD-2 question dicts, ready to display before
        condition-specific questions.

        Returns
        -------
        dict with keys "depression" and "anxiety", each a list of question dicts.
        """
        return {
            name: data["questions"]
            for name, data in self._confounders.items()
            if not name.startswith("_")
        }

    def score_confounders(self, answers: dict[str, int]) -> float:
        """
        Score PHQ-2 and GAD-2 answers and return a single multiplier to apply
        to ALL physical condition priors before condition-specific updates.

        Parameters
        ----------
        answers : dict[str, int]
            e.g. {"phq2_q1": 2, "phq2_q2": 1, "gad2_q1": 0, "gad2_q2": 0}
            Values are the ordinal scores (0–3) from each question.

        Returns
        -------
        float
            Combined multiplier (< 1.0 when confounders are present).
            1.0 means no adjustment (both screens negative).
        """
        multiplier = 1.0

        for name, data in self._confounders.items():
            if name.startswith("_"):
                continue

            scoring  = data["scoring"]
            q_ids    = [q["id"] for q in data["questions"]]
            total    = sum(answers.get(qid, 0) for qid in q_ids)

            for threshold in scoring["thresholds"]:
                lo, hi = threshold["score_range"]
                if lo <= total <= hi:
                    lr_phys = threshold["lr_physical_conditions"]
                    multiplier *= lr_phys
                    log.debug(
                        "Confounder '%s' score=%d → lr_physical=%.2f",
                        name, total, lr_phys,
                    )
                    break

        return multiplier

    def update(
        self,
        condition: str,
        prior_prob: float,
        answers: dict[str, str],
        confounder_multiplier: float = 1.0,
    ) -> dict:
        """
        Compute the Bayesian posterior for a condition given answered questions.

        Parameters
        ----------
        condition : str
            ML condition name (e.g. "anemia").
        prior_prob : float
            ML probability (0–1) for this condition — the prior.
        answers : dict[str, str]
            {question_id: answer_value} for each answered question.
            e.g. {"anemia_q1": "yes", "anemia_q2": "no"}
            Unanswered questions (not in dict) are skipped.
        confounder_multiplier : float
            Output of score_confounders(). Applied once before symptom LRs.
            Default 1.0 (no adjustment).

        Returns
        -------
        dict with keys:
            prior            : float  — input ML probability
            posterior        : float  — updated probability after Bayes
            prior_odds       : float
            posterior_odds   : float
            lrs_applied      : list[dict]  — each LR used with its question_id and value
            questions_used   : list[str]   — question IDs that contributed
            confounder_mult  : float
            clipped          : bool   — True if posterior hit the 0.05/0.95 clip
        """
        if condition not in self._conditions:
            log.warning("Unknown condition '%s' — returning prior unchanged.", condition)
            return {"prior": prior_prob, "posterior": prior_prob, "error": "unknown_condition"}

        prior_prob  = float(prior_prob)
        prior_odds  = _prob_to_odds(prior_prob)
        running_odds = prior_odds * confounder_multiplier

        lrs_applied   = []
        questions_used = []

        # Build a lookup: question_id → question dict
        q_lookup = {q["id"]: q for q in self._conditions[condition]["questions"]}

        for q_id, answer_val in answers.items():
            if q_id not in q_lookup:
                log.debug("Question '%s' not found for condition '%s' — skipped.", q_id, condition)
                continue

            question = q_lookup[q_id]
            lr       = _find_lr(question, answer_val)

            if lr is None:
                log.warning(
                    "Answer '%s' not found for question '%s' — skipped.", answer_val, q_id
                )
                continue

            running_odds *= lr
            lrs_applied.append({"question_id": q_id, "answer": answer_val, "lr": lr})
            questions_used.append(q_id)

        posterior_raw  = _odds_to_prob(running_odds)
        posterior_clip = max(POSTERIOR_CLIP_LOW, min(POSTERIOR_CLIP_HIGH, posterior_raw))
        clipped        = posterior_clip != posterior_raw

        log.info(
            "Bayesian update | condition=%-18s  prior=%.3f  posterior=%.3f  "
            "confounder_mult=%.2f  questions=%d",
            condition, prior_prob, posterior_clip,
            confounder_multiplier, len(questions_used),
        )

        return {
            "condition":          condition,
            "prior":              round(prior_prob, 4),
            "posterior":          round(posterior_clip, 4),
            "prior_odds":         round(prior_odds, 4),
            "posterior_odds":     round(running_odds, 4),
            "lrs_applied":        lrs_applied,
            "questions_used":     questions_used,
            "confounder_mult":    round(confounder_multiplier, 4),
            "clipped":            clipped,
        }

    def update_shortlist(
        self,
        shortlist: list[dict],
        answers_by_condition: dict[str, dict[str, str]],
        confounder_answers: Optional[dict[str, int]] = None,
        patient_sex: Optional[str] = None,
    ) -> list[dict]:
        """
        Run Bayesian updates across an entire ML shortlist in one call.
        This is the main integration point with model_runner.py.

        Parameters
        ----------
        shortlist : list[dict]
            Output of ModelRunner.score() — e.g.
            [{"condition": "anemia", "probability": 0.72}, ...]
        answers_by_condition : dict[str, dict[str, str]]
            {condition: {question_id: answer_value}}
        confounder_answers : dict[str, int], optional
            PHQ-2 / GAD-2 answers. If None, no confounder adjustment is applied.
        patient_sex : str, optional
            "female" or "male" for gender-filtered questions.

        Returns
        -------
        list[dict]
            Same structure as shortlist but with "probability" replaced by the
            Bayesian posterior, plus "bayesian_detail" key for each condition.
            Re-sorted by updated probability descending.
        """
        confounder_mult = 1.0
        if confounder_answers:
            confounder_mult = self.score_confounders(confounder_answers)

        updated = []
        for item in shortlist:
            condition   = item["condition"]
            prior_prob  = item["probability"]
            cond_answers = answers_by_condition.get(condition, {})

            result = self.update(
                condition=condition,
                prior_prob=prior_prob,
                answers=cond_answers,
                confounder_multiplier=confounder_mult,
            )

            updated.append({
                "condition":       condition,
                "probability":     result["posterior"],
                "prior":           result["prior"],
                "bayesian_detail": result,
            })

        updated.sort(key=lambda x: x["probability"], reverse=True)
        return updated


# ── Helpers ──────────────────────────────────────────────────────────────────

def _prob_to_odds(p: float) -> float:
    p = max(1e-9, min(1 - 1e-9, p))
    return p / (1 - p)


def _odds_to_prob(odds: float) -> float:
    return odds / (1 + odds)


def _find_lr(question: dict, answer_val: str) -> Optional[float]:
    """Look up the LR for a given answer value in a question's answer_options."""
    for option in question.get("answer_options", []):
        if str(option["value"]) == str(answer_val):
            return float(option["lr"])
    return None


# ── Standalone demo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

    updater = BayesianUpdater()

    print("\n" + "=" * 65)
    print("  BayesianUpdater — standalone demo")
    print("=" * 65)

    # ── 1. Confounder screen ────────────────────────────────────────────────
    print("\n── 1. Confounder screen (PHQ-2 + GAD-2) " + "-" * 25)
    confounder_answers = {
        "phq2_q1": 1,   # some days of low interest
        "phq2_q2": 1,   # some days of low mood
        "gad2_q1": 0,   # no anxiety
        "gad2_q2": 0,
    }
    mult = updater.score_confounders(confounder_answers)
    print(f"PHQ-2 score: {confounder_answers['phq2_q1'] + confounder_answers['phq2_q2']}  "
          f"GAD-2 score: {confounder_answers['gad2_q1'] + confounder_answers['gad2_q2']}")
    print(f"Confounder multiplier: {mult:.3f}  "
          f"({'mild downgrade' if mult < 1 else 'no adjustment'})")

    # ── 2. Single condition update — anemia ─────────────────────────────────
    print("\n── 2. Single condition update: anemia " + "-" * 27)
    prior = 0.55
    questions = updater.get_questions("anemia", prior_prob=prior, patient_sex="female")
    print(f"Prior: {prior}  |  Questions available: {len(questions)}")
    for q in questions:
        print(f"  [{q['id']}] {q['text'][:70]}...")

    answers = {
        "anemia_q1": "yes",   # heavy periods       → LR+ 2.4
        "anemia_q3": "yes",   # blood donation       → LR+ 2.0
        "anemia_q2": "no",    # no unusual blood loss → LR- 0.74
    }
    result = updater.update("anemia", prior_prob=prior,
                             answers=answers, confounder_multiplier=mult)

    print(f"\nAnswers: {answers}")
    print(f"Prior prob    : {result['prior']:.4f}")
    print(f"Prior odds    : {result['prior_odds']:.4f}")
    print(f"Confounder ×  : {result['confounder_mult']:.4f}")
    for lr_entry in result["lrs_applied"]:
        print(f"  × LR({lr_entry['question_id']}={lr_entry['answer']}) = {lr_entry['lr']}")
    print(f"Posterior odds: {result['posterior_odds']:.4f}")
    print(f"Posterior prob: {result['posterior']:.4f}  {'[CLIPPED]' if result['clipped'] else ''}")

    # ── 3. Full shortlist update ────────────────────────────────────────────
    print("\n── 3. Full shortlist update " + "-" * 37)
    shortlist = [
        {"condition": "anemia",        "probability": 0.55},
        {"condition": "perimenopause", "probability": 0.48},
        {"condition": "iron_deficiency","probability": 0.43},
    ]
    answers_by_condition = {
        "anemia": {
            "anemia_q1": "yes",
            "anemia_q3": "yes",
            "anemia_q2": "no",
        },
        "perimenopause": {
            "peri_q1": "yes",   # self-assessment positive  → LR+ 1.83
            "peri_q2": "yes",   # hot flushes               → LR+ 3.1
            "peri_q2b": "yes",  # night sweats              → LR+ 1.90
        },
        "iron_deficiency": {
            "iron_q5": "yes",   # pica / ice craving        → LR+ 5.8
            "iron_q1": "yes",   # heavy periods             → LR+ 3.5
        },
    }

    updated = updater.update_shortlist(
        shortlist=shortlist,
        answers_by_condition=answers_by_condition,
        confounder_answers=confounder_answers,
        patient_sex="female",
    )

    print(f"{'Condition':<20} {'Prior':>7} {'Posterior':>10}  {'Δ':>7}")
    print("-" * 50)
    for item in updated:
        delta = item["probability"] - item["prior"]
        print(f"{item['condition']:<20} {item['prior']:>7.4f} {item['probability']:>10.4f}  "
              f"{delta:>+7.4f}")
