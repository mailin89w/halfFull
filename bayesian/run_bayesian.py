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
    "vitamin_b12_deficiency": "vitamin_b12_deficiency",
    "vitamin_d_deficiency": "vitamin_d_deficiency",
}

LEGACY_FILTER_CRITERIA = {
    legacy_key: BAYESIAN_TRIGGER_THRESHOLDS[normalized_key]
    for normalized_key, legacy_key in NORMALIZED_TO_LEGACY_KEYS.items()
    if normalized_key in BAYESIAN_TRIGGER_THRESHOLDS
}

DISABLED_QUESTION_IDS = {
    "anemia_q3",
    "iron_q4",
    "thyroid_q4",
    "thyroid_q5",
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
MUST_ASK_TOP_N = 7
MUST_ASK_CONDITIONS = {
    "thyroid",
    "kidney",
    "prediabetes",
    "perimenopause",
}
DISEASE_LAYER_POLICY = {
    # End-to-end orchestration policy per disease. We keep Bayes itself fixed,
    # but decide differently per condition how aggressively we trigger, how
    # many questions we spend, and how strongly the condition competes for
    # limited clarification slots.
    "kidney": {"max_questions": 5, "screen_priority": 1.30},
    "anemia": {"max_questions": 5, "screen_priority": 1.26},
    "inflammation": {"max_questions": 5, "screen_priority": 1.24},
    "iron_deficiency": {"max_questions": 4, "screen_priority": 1.20},
    "thyroid": {"max_questions": 4, "screen_priority": 1.14},
    "hepatitis": {"max_questions": 4, "screen_priority": 1.12},
    "electrolytes": {"max_questions": 4, "screen_priority": 1.04},
    "sleep_disorder": {"max_questions": 3, "screen_priority": 1.02},
    "perimenopause": {"max_questions": 5, "screen_priority": 1.12},
    "prediabetes": {"max_questions": 3, "screen_priority": 0.90},
    "liver": {"max_questions": 3, "screen_priority": 0.88},
    "vitamin_d_deficiency": {"max_questions": 2, "screen_priority": 0.82},
}
DEFAULT_TRIGGER_POLICY = "minimal"
TRIGGER_POLICY_BY_CONDITION = {
    # Gain-optimized from the 760-person compare + trigger-optimization eval.
    # These classes express how valuable Bayesian follow-up has been per disease,
    # not just how confident the raw ML model is.
    "kidney": "aggressive",
    "anemia": "aggressive",
    "inflammation": "aggressive",
    "thyroid": "moderate",
    "iron_deficiency": "topk_rescue_only",
    "sleep_disorder": "topk_rescue_only",
    "electrolytes": "topk_rescue_only",
    "hepatitis": "minimal",
    "liver": "minimal",
    "perimenopause": "moderate",
    "prediabetes": "minimal",
    "vitamin_d_deficiency": "minimal",
}
TRIGGER_POLICY_SETTINGS = {
    "aggressive": {
        "top_k": 5,
        "near_top3_delta": 0.08,
        "floor_offset": -0.01,
    },
    "moderate": {
        "top_k": 5,
        "near_top3_delta": 0.08,
        "floor_offset": 0.0,
    },
    "topk_rescue_only": {
        "top_k": 5,
        "near_top3_delta": None,
        "floor_offset": 0.0,
    },
    "minimal": {
        "top_k": 0,
        "near_top3_delta": None,
        "floor_offset": 0.0,
    },
}
POSTERIOR_PROMOTION_FLOOR_BY_CONDITION = {
    # These conditions are frequent over-alert contributors in the 760 eval.
    # They may still be routed into Bayes for evidence gathering, but weak
    # posteriors should not be promoted into the surfaced shortlist unless
    # they clear a higher condition-specific bar.
    "vitamin_d_deficiency": 0.64,
    "prediabetes": 0.62,
    "thyroid": 0.75,
}
DEMOTED_SURFACING_CAP = 0.19
LOW_CONFIDENCE_TOP1_CUTOFF = 0.40
STAGED_FOLLOW_UP_RULES = {}
COMPETITION_RULES = [
    {
        "winner": "anemia",
        "losers": ["vitamin_d_deficiency"],
        "winner_min_posterior": 0.50,
        "winner_min_lift": 0.10,
        "loser_max_posterior": 0.75,
        "suppression_factor": 0.82,
    },
    {
        "winner": "kidney",
        "losers": ["electrolytes", "prediabetes"],
        "winner_min_posterior": 0.45,
        "winner_min_lift": 0.08,
        "loser_max_posterior": 0.72,
        "suppression_factor": 0.80,
    },
    {
        "winner": "hepatitis",
        "losers": ["liver"],
        "winner_min_posterior": 0.35,
        "winner_min_lift": 0.08,
        "loser_max_posterior": 0.65,
        "suppression_factor": 0.72,
    },
    {
        "winner": "iron_deficiency",
        "losers": ["vitamin_d_deficiency"],
        "winner_min_posterior": 0.42,
        "winner_min_lift": 0.08,
        "loser_max_posterior": 0.72,
        "suppression_factor": 0.82,
    },
    {
        "winner": "sleep_disorder",
        "losers": ["inflammation"],
        "winner_min_posterior": 0.55,
        "winner_min_lift": 0.06,
        "loser_max_posterior": 0.58,
        "suppression_factor": 0.84,
    },
]
MAX_RERANK_LIFT_BONUS = 0.08
POSITIVE_LR_THRESHOLD = 1.2
STRONG_POSITIVE_LR_THRESHOLD = 2.5
EVIDENCE_CONFIDENCE_WEIGHTS = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.25,
}
RERANK_ELIGIBLE_CONDITIONS = {
    "anemia",
    "inflammation",
    "kidney",
    "hepatitis",
}
MAX_CONSERVATIVE_RERANK_LIFT_BONUS = 0.04
RERANK_POLICY_BY_CONDITION = {
    "anemia": {
        "lift_bonus_scale": 0.24,
        "support_bonus_scale": 1.15,
        "min_lift_for_bonus": 0.03,
        "strong_evidence_bonus": 0.012,
    },
    "inflammation": {
        "lift_bonus_scale": 0.24,
        "support_bonus_scale": 1.15,
        "min_lift_for_bonus": 0.03,
        "strong_evidence_bonus": 0.01,
    },
    "kidney": {
        "lift_bonus_scale": 0.22,
        "support_bonus_scale": 1.1,
        "min_lift_for_bonus": 0.03,
        "strong_evidence_bonus": 0.01,
    },
    "hepatitis": {
        "lift_bonus_scale": 0.22,
        "support_bonus_scale": 1.1,
        "min_lift_for_bonus": 0.025,
        "strong_evidence_bonus": 0.008,
    },
    "iron_deficiency": {
        "lift_bonus_scale": 0.18,
        "support_bonus_scale": 1.0,
        "min_lift_for_bonus": 0.025,
        "strong_evidence_bonus": 0.006,
    },
    "sleep_disorder": {
        "lift_bonus_scale": 0.14,
        "support_bonus_scale": 0.9,
        "min_lift_for_bonus": 0.02,
        "strong_evidence_bonus": 0.004,
    },
    "vitamin_d_deficiency": {
        "flat_lift_penalty": 0.014,
        "weak_support_penalty": 0.01,
        "low_lift_threshold": 0.04,
        "requires_confident_support": True,
    },
    "prediabetes": {
        "flat_lift_penalty": 0.012,
        "weak_support_penalty": 0.008,
        "low_lift_threshold": 0.035,
        "requires_confident_support": True,
    },
    "liver": {
        "flat_lift_penalty": 0.012,
        "weak_support_penalty": 0.01,
        "low_lift_threshold": 0.03,
        "requires_confident_support": True,
    },
    "electrolytes": {
        "flat_lift_penalty": 0.008,
        "weak_support_penalty": 0.006,
        "low_lift_threshold": 0.03,
        "requires_confident_support": False,
    },
}


def _canonical_question_key(question_id: str) -> str:
    return QUESTION_TO_SHARED_KEY.get(question_id, question_id)


def _normalized_question_text(question_text: str) -> str:
    return " ".join(question_text.strip().split()).casefold()


def _layer_policy_for_condition(condition: str) -> dict:
    return DISEASE_LAYER_POLICY.get(condition, {})


def _screen_priority_for_condition(condition: str) -> float:
    return float(_layer_policy_for_condition(condition).get("screen_priority", 1.0))


def _max_questions_for_condition(condition: str) -> int:
    return int(_layer_policy_for_condition(condition).get("max_questions", MAX_Q_PER_COND))


def _trigger_policy_for_condition(condition: str) -> dict[str, float | int | None]:
    policy_name = TRIGGER_POLICY_BY_CONDITION.get(condition, DEFAULT_TRIGGER_POLICY)
    return TRIGGER_POLICY_SETTINGS[policy_name]


def _maybe_guardrail_policy(
    condition: str,
    top1_score: float,
) -> dict[str, float | int | None]:
    policy_name = TRIGGER_POLICY_BY_CONDITION.get(condition, DEFAULT_TRIGGER_POLICY)
    if top1_score < LOW_CONFIDENCE_TOP1_CUTOFF and policy_name == "aggressive":
        # On low-signal profiles, skip aggressive rescue expansion and fall
        # back to strict threshold-triggered Bayes for these conditions.
        return TRIGGER_POLICY_SETTINGS["minimal"]
    return TRIGGER_POLICY_SETTINGS[policy_name]


def _apply_posterior_promotion_floor(
    updated: list[dict],
    priors_by_condition: dict[str, float],
) -> tuple[dict[str, float], dict[str, dict]]:
    surfaced_scores: dict[str, float] = {}
    surface_meta: dict[str, dict] = {}

    for item in updated:
        condition = item["condition"]
        posterior = float(item["probability"])
        prior = float(priors_by_condition.get(condition, posterior))
        floor = POSTERIOR_PROMOTION_FLOOR_BY_CONDITION.get(condition)

        surfaced = posterior
        demoted = False
        if floor is not None and posterior < floor:
            surfaced = min(prior, DEMOTED_SURFACING_CAP)
            demoted = True

        surfaced_scores[condition] = round(surfaced, 4)
        surface_meta[condition] = {
            "raw_posterior": round(posterior, 4),
            "surfaced_probability": round(surfaced, 4),
            "promotion_floor": floor,
            "demoted_for_surfacing": demoted,
        }

    return surfaced_scores, surface_meta


def _apply_condition_competition(
    surfaced_scores: dict[str, float],
    raw_posteriors: dict[str, float],
    priors_by_condition: dict[str, float],
) -> tuple[dict[str, float], dict[str, dict]]:
    competition_meta: dict[str, dict] = {}
    adjusted_scores = dict(surfaced_scores)

    for rule in COMPETITION_RULES:
        winner = rule["winner"]
        winner_posterior = raw_posteriors.get(winner, 0.0)
        winner_prior = priors_by_condition.get(winner, winner_posterior)
        winner_lift = winner_posterior - winner_prior
        if winner_posterior < rule["winner_min_posterior"]:
            continue
        if winner_lift < rule["winner_min_lift"]:
            continue

        for loser in rule["losers"]:
            loser_score = adjusted_scores.get(loser)
            loser_raw = raw_posteriors.get(loser, 0.0)
            if loser_score is None:
                continue
            if loser_raw > rule["loser_max_posterior"]:
                continue

            suppressed = round(loser_score * rule["suppression_factor"], 4)
            if suppressed == loser_score:
                continue
            adjusted_scores[loser] = suppressed
            competition_meta[loser] = {
                "suppressed_by": winner,
                "raw_posterior": round(loser_raw, 4),
                "pre_competition_score": round(loser_score, 4),
                "post_competition_score": suppressed,
                "winner_posterior": round(winner_posterior, 4),
                "winner_lift": round(winner_lift, 4),
                "suppression_factor": rule["suppression_factor"],
            }

    return adjusted_scores, competition_meta


def _apply_evidence_reranker(
    updated: list[dict],
    surfaced_scores: dict[str, float],
    updater: BayesianUpdater,
) -> tuple[dict[str, float], dict[str, dict]]:
    reranked_scores = dict(surfaced_scores)
    rerank_meta: dict[str, dict] = {}

    for item in updated:
        condition = item["condition"]
        surfaced = float(reranked_scores.get(condition, item["probability"]))
        detail = item.get("bayesian_detail", {})
        prior = float(detail.get("prior", item.get("prior", item["probability"])))
        posterior = float(detail.get("posterior", item["probability"]))
        lrs_applied = detail.get("lrs_applied", []) or []
        question_lookup = {
            question["id"]: question
            for question in updater._conditions.get(condition, {}).get("questions", [])
        }

        lift = max(posterior - prior, 0.0)
        positive_count = sum(1 for entry in lrs_applied if float(entry.get("lr", 1.0)) >= POSITIVE_LR_THRESHOLD)
        strong_positive_count = sum(1 for entry in lrs_applied if float(entry.get("lr", 1.0)) >= STRONG_POSITIVE_LR_THRESHOLD)
        negative_count = sum(1 for entry in lrs_applied if float(entry.get("lr", 1.0)) < 1.0)
        confidence_weights: list[float] = []
        low_conf_positive_count = 0
        for entry in lrs_applied:
            qid = str(entry.get("question_id", ""))
            answer = str(entry.get("answer", ""))
            lr = float(entry.get("lr", 1.0))
            question = question_lookup.get(qid, {})
            answer_option = next(
                (
                    option for option in question.get("answer_options", [])
                    if str(option.get("value")) == answer
                ),
                {},
            )
            confidence = str(answer_option.get("lr_confidence", "low")).lower()
            weight = EVIDENCE_CONFIDENCE_WEIGHTS.get(confidence, EVIDENCE_CONFIDENCE_WEIGHTS["low"])
            confidence_weights.append(weight)
            if lr >= POSITIVE_LR_THRESHOLD and confidence == "low":
                low_conf_positive_count += 1

        average_confidence_weight = (
            sum(confidence_weights) / len(confidence_weights) if confidence_weights else 0.0
        )

        condition_policy = RERANK_POLICY_BY_CONDITION.get(condition, {})
        is_eligible = condition in RERANK_ELIGIBLE_CONDITIONS or "lift_bonus_scale" in condition_policy
        if is_eligible:
            lift_bonus_scale = float(condition_policy.get("lift_bonus_scale", 0.18))
            min_lift_for_bonus = float(condition_policy.get("min_lift_for_bonus", 0.0))
            effective_lift = lift if lift >= min_lift_for_bonus else 0.0
            lift_bonus = min(effective_lift * lift_bonus_scale, MAX_CONSERVATIVE_RERANK_LIFT_BONUS)
            support_bonus_scale = float(condition_policy.get("support_bonus_scale", 1.0))
            support_bonus = (
                min(positive_count, 2) * 0.006 + min(strong_positive_count, 1) * 0.01
            ) * average_confidence_weight * support_bonus_scale
            strong_evidence_bonus = 0.0
            if strong_positive_count >= 1 and average_confidence_weight >= 0.6 and lift >= max(min_lift_for_bonus, 0.05):
                strong_evidence_bonus = float(condition_policy.get("strong_evidence_bonus", 0.0))
        else:
            lift_bonus = 0.0
            support_bonus = 0.0
            strong_evidence_bonus = 0.0
        weak_support_penalty = 0.0
        if positive_count > 0 and average_confidence_weight < 0.4:
            weak_support_penalty += 0.01
        if low_conf_positive_count >= 2:
            weak_support_penalty += 0.008
        if condition_policy:
            low_lift_threshold = float(condition_policy.get("low_lift_threshold", 0.0))
            if lift < low_lift_threshold:
                weak_support_penalty += float(condition_policy.get("flat_lift_penalty", 0.0))
            requires_confident_support = bool(condition_policy.get("requires_confident_support", False))
            weak_support_penalty_value = float(condition_policy.get("weak_support_penalty", 0.0))
            if requires_confident_support and positive_count > 0 and average_confidence_weight < 0.6:
                weak_support_penalty += weak_support_penalty_value
            elif positive_count == 0 and weak_support_penalty_value > 0:
                weak_support_penalty += weak_support_penalty_value
        evidence_penalty = min(negative_count, 2) * 0.008 + weak_support_penalty
        rerank_delta = round(lift_bonus + support_bonus + strong_evidence_bonus - evidence_penalty, 4)

        reranked = round(max(surfaced + rerank_delta, 0.0), 4)
        reranked_scores[condition] = reranked
        rerank_meta[condition] = {
            "pre_rerank_score": round(surfaced, 4),
            "reranked_score": reranked,
            "posterior_lift": round(lift, 4),
            "eligible_for_bonus": is_eligible,
            "average_confidence_weight": round(average_confidence_weight, 4),
            "positive_lr_count": positive_count,
            "strong_positive_lr_count": strong_positive_count,
            "low_conf_positive_count": low_conf_positive_count,
            "negative_lr_count": negative_count,
            "condition_policy": condition_policy,
            "rerank_delta": rerank_delta,
        }

    return reranked_scores, rerank_meta


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


def _staged_follow_up_meta(condition: str, question_ids: list[str]) -> dict | None:
    rule = STAGED_FOLLOW_UP_RULES.get(condition)
    if not rule:
        return None
    entry_question_id = rule["entry_question_id"]
    hidden_question_ids = [qid for qid in rule["hidden_question_ids"] if qid in question_ids]
    if entry_question_id not in question_ids or not hidden_question_ids:
        return None
    return {
        "entry_question_id": entry_question_id,
        "continue_on_values": list(rule["continue_on_values"]),
        "hidden_question_ids": hidden_question_ids,
    }


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
            if target_qid in DISABLED_QUESTION_IDS:
                continue
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

    ranked_all = sorted(
        [(cond, prob) for cond, prob in ml_scores.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    # Condition questions: top MAX_CONDITIONS triggered by per-disease filter criteria
    eligible = sorted(
        [
            (cond, prob)
            for cond, prob in ml_scores.items()
            if prob >= LEGACY_FILTER_CRITERIA.get(cond, 1.0)
        ],
        key=lambda x: (x[1] * _screen_priority_for_condition(x[0]), x[1]),
        reverse=True,
    )

    triggered_scores = {cond: prob for cond, prob in eligible[:MAX_CONDITIONS]}
    triggered_conditions = set(triggered_scores)

    top1_score = ranked_all[0][1] if ranked_all else 0.0
    slot3_cutoff = ranked_all[min(2, len(ranked_all) - 1)][1] if ranked_all else 0.0

    # Disease-specific rescue: the 760-person eval shows Bayes is much more
    # valuable for some conditions (kidney, anemia, inflammation) than others.
    # Use those observed gains to decide how much borderline ML signal should
    # be allowed into Bayesian follow-up.
    for rank, (cond, prob) in enumerate(ranked_all, start=1):
        if cond in triggered_conditions:
            continue
        policy = _maybe_guardrail_policy(cond, top1_score)
        base_floor = LEGACY_FILTER_CRITERIA.get(cond, 1.0)
        rescue_floor = max(base_floor + float(policy["floor_offset"]), 0.0)
        top_k = int(policy["top_k"])
        near_top3_delta = policy["near_top3_delta"]
        is_top_k = top_k > 0 and rank <= top_k
        near_top3 = False
        if near_top3_delta is not None:
            near_top3 = prob >= max(slot3_cutoff - float(near_top3_delta), 0.0)
        if prob < rescue_floor:
            continue
        if not (is_top_k or near_top3):
            continue
        triggered_scores[cond] = prob
        triggered_conditions.add(cond)

    # Overfiring models can crowd clinically important conditions like thyroid
    # out of the top-5. If one of these key conditions is still above its
    # Bayesian trigger threshold and ranks within the top-N overall, force it
    # into the clarification set as an extra condition rather than dropping it.
    for cond, prob in eligible[:MUST_ASK_TOP_N]:
        if cond in MUST_ASK_CONDITIONS and cond not in triggered_conditions:
            triggered_scores[cond] = prob
            triggered_conditions.add(cond)

    triggered = sorted(
        triggered_scores.items(),
        key=lambda x: (x[1] * _screen_priority_for_condition(x[0]), x[1]),
        reverse=True,
    )

    condition_questions = []
    asked_shared_keys = set(prefilled_keys)
    previous_screen_question_texts: set[str] = set()
    for condition, prob in triggered:
        questions = updater.get_questions(
            condition,
            prior_prob=prob,
            patient_sex=patient_sex,
            max_questions=_max_questions_for_condition(condition),
        )
        filtered_questions = []
        for q in questions:
            qid = q["id"]
            shared_key = _canonical_question_key(qid)
            normalized_text = _normalized_question_text(q["text"])
            if qid in DISABLED_QUESTION_IDS:
                continue
            if qid in prefilled or shared_key in asked_shared_keys:
                continue
            if normalized_text in previous_screen_question_texts:
                continue
            filtered_questions.append(q)
            asked_shared_keys.add(shared_key)

        questions = filtered_questions
        if not questions:
            continue
        question_ids = [q["id"] for q in questions]
        previous_screen_question_texts = {
            _normalized_question_text(q["text"])
            for q in questions
        }
        condition_questions.append({
            "condition":   condition,
            "probability": round(prob, 4),
            "staged_follow_up": _staged_follow_up_meta(condition, question_ids),
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

    priors_by_condition = {item["condition"]: float(item["probability"]) for item in shortlist}
    raw_posteriors = {item["condition"]: float(item["probability"]) for item in updated}
    posterior_scores, surface_meta = _apply_posterior_promotion_floor(updated, priors_by_condition)
    posterior_scores, competition_meta = _apply_condition_competition(
        posterior_scores,
        raw_posteriors,
        priors_by_condition,
    )
    posterior_scores, rerank_meta = _apply_evidence_reranker(
        updated,
        posterior_scores,
        updater,
    )
    details = {item["condition"]: item.get("bayesian_detail", {}) for item in updated}
    for condition, meta in surface_meta.items():
        if condition not in details:
            details[condition] = {}
        details[condition]["surface_meta"] = meta
    for condition, meta in competition_meta.items():
        if condition not in details:
            details[condition] = {}
        details[condition]["competition_meta"] = meta
    for condition, meta in rerank_meta.items():
        if condition not in details:
            details[condition] = {}
        details[condition]["rerank_meta"] = meta

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
