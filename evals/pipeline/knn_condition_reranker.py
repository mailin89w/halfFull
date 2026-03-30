from __future__ import annotations

from typing import Any

# KNN -> condition support mapping.
# Only conditions with reasonably condition-specific downstream lab support are
# eligible for a material boost.
GROUP_BONUSES: dict[str, dict[str, float]] = {
    "kidney": {"kidney": 0.08},
    "liver": {"liver_panel": 0.08},
    "hepatitis": {"liver_panel": 0.08},
    "inflammation": {"inflammation": 0.08},
    "prediabetes": {"glycemic": 0.08},  # lipids bonus removed 2026-03-27: fires on healthy profiles with borderline kidney/lipid signals, boosting prediabetes above its 0.45 threshold on profiles where there is no glycemic signal — too nonspecific to keep
    "thyroid": {"thyroid": 0.08},
    "iron_deficiency": {"iron_studies": 0.08, "cbc": 0.03},
    "anemia": {"cbc": 0.06, "iron_studies": 0.04},
    # These are intentionally disabled for now — KNN lab groups are too
    # nonspecific to safely rerank these conditions yet.
    "electrolytes": {},
    "sleep_disorder": {},
    "perimenopause": {},
}

# Small extra boosts for clinically plausible comorbidity rescue, but only when
# the candidate already has condition-specific KNN support and a plausible prior.
COMORBIDITY_PAIR_BONUSES: dict[tuple[str, str], float] = {
    ("anemia", "kidney"): 0.03,
    ("kidney", "anemia"): 0.03,
    ("liver", "hepatitis"): 0.03,
    ("hepatitis", "liver"): 0.03,
    ("prediabetes", "inflammation"): 0.02,
    ("inflammation", "prediabetes"): 0.02,
}

# Conditions that currently overfire and should be penalized when KNN finds no
# condition-specific neighborhood support.
UNSUPPORTED_PENALTIES: dict[str, float] = {
    "kidney": 0.10,
    "thyroid": 0.08,
    "prediabetes": 0.08,
    "inflammation": 0.08,
    "electrolytes": 0.06,
}


def rerank_condition_scores_with_knn(
    bayesian_scores: dict[str, float],
    knn_groups: set[str],
    *,
    min_prior: float = 0.20,
    max_bonus: float = 0.16,
    max_candidate_rank: int = 6,
    max_distance_from_top3: float = 0.22,
    freeze_top1: bool = True,
    top1_confidence_threshold: float = 1.0,
    top_n: int = 3,
    # When the profile has zero KNN lab-signal groups (no lab evidence at all),
    # UNSUPPORTED_PENALTIES are doubled (up to this cap) and the score guard is
    # raised so that even high-confidence mispredictions get penalised.
    zero_groups_max_penalty: float = 0.20,
) -> dict[str, Any]:
    """
    Conservative post-Bayesian reranker.

    Design goals:
    - rescue plausible missed comorbidities into the top-k
    - never invent a brand-new top condition from scratch
    - use KNN as weak supporting evidence, not as a primary classifier

    top1_confidence_threshold:
        When freeze_top1=True, the top-1 slot is still released if the Bayesian
        top-1 score falls below this threshold — i.e. the model is uncertain.
        1.0 (default) = always freeze regardless of score (original behaviour).
        0.0           = never freeze (pure KNN reranking).
        0.60          = unfreeze only when top-1 posterior < 0.60.
        This enables A/B testing a confidence-gated unfreeze without changing the
        production default.
    """
    if not bayesian_scores:
        return {
            "adjusted_scores": {},
            "top_conditions": [],
            "bonuses": {},
            "frozen_top1": None,
        }

    ranked = sorted(bayesian_scores.items(), key=lambda item: item[1], reverse=True)
    top1_condition = ranked[0][0]
    top1_score = ranked[0][1]
    top2_cutoff = ranked[min(1, len(ranked) - 1)][1]
    top3_cutoff = ranked[min(2, len(ranked) - 1)][1]

    adjusted = dict(bayesian_scores)
    bonuses: dict[str, dict[str, Any]] = {}
    penalties: dict[str, dict[str, Any]] = {}

    for rank, (condition, base_score) in enumerate(ranked, start=1):
        if rank > max_candidate_rank:
            continue
        if base_score < min_prior:
            continue
        if base_score + max_bonus < top3_cutoff - max_distance_from_top3:
            continue

        matched_groups: list[str] = []
        bonus = 0.0
        for group, group_bonus in GROUP_BONUSES.get(condition, {}).items():
            if group in knn_groups:
                matched_groups.append(group)
                bonus += group_bonus

        if matched_groups and condition != top1_condition:
            bonus += COMORBIDITY_PAIR_BONUSES.get((top1_condition, condition), 0.0)

            # Let KNN work harder on rescuing slot 2 / slot 3 candidates without
            # ever touching top-1. These bonuses only apply to candidates already
            # close enough to the shortlist and backed by condition-specific KNN
            # evidence.
            gap_to_slot3 = max(top3_cutoff - base_score, 0.0)
            gap_to_slot2 = max(top2_cutoff - base_score, 0.0)

            if rank >= 4 and gap_to_slot3 <= 0.12:
                bonus += 0.04
            if rank >= 5 and gap_to_slot3 <= 0.08:
                bonus += 0.02
            if rank >= 4 and gap_to_slot2 <= 0.05:
                bonus += 0.02

        if bonus <= 0.0:
            penalty = 0.0
            zero_groups = len(knn_groups) == 0
            # Standard penalty: condition overflies, no condition-specific KNN support.
            # Guard is raised to 0.90 (from 0.75) when the profile has zero lab signals
            # at all — the absence of any signal is itself evidence against high-scoring
            # conditions that have well-defined lab markers.
            score_guard = 0.90 if zero_groups else 0.75
            if (
                condition in UNSUPPORTED_PENALTIES
                and not matched_groups
                and rank <= top_n
                and base_score < score_guard
            ):
                base_penalty = UNSUPPORTED_PENALTIES[condition]
                # Double the penalty when the whole profile has no lab signal groups —
                # that is stronger negative evidence than merely lacking one specific group.
                penalty = min(base_penalty * 2 if zero_groups else base_penalty,
                              zero_groups_max_penalty)
                # Be a bit stricter on lower-ranked shortlist entries, since
                # these are the most common false-positive extras.
                if rank >= 3:
                    penalty += 0.02
                elif rank == 2 and base_score < top1_score and base_score < 0.60:
                    penalty += 0.01

            if penalty > 0.0:
                adjusted[condition] = max(0.05, round(base_score - penalty, 4))
                penalties[condition] = {
                    "base_score": round(base_score, 4),
                    "adjusted_score": adjusted[condition],
                    "applied_penalty": round(penalty, 4),
                    "reason": "no_condition_specific_knn_support",
                    "rank_before": rank,
                }
            continue

        applied_bonus = min(bonus, max_bonus)
        adjusted[condition] = min(0.99, round(base_score + applied_bonus, 4))
        bonuses[condition] = {
            "base_score": round(base_score, 4),
            "adjusted_score": adjusted[condition],
            "applied_bonus": round(applied_bonus, 4),
            "matched_groups": matched_groups,
            "top1_anchor": top1_condition,
            "rank_before": rank,
        }

    remaining = sorted(
        [(cond, score) for cond, score in adjusted.items() if cond != top1_condition],
        key=lambda item: item[1],
        reverse=True,
    )

    # Respect freeze_top1 flag, but release the freeze when the Bayesian top-1
    # score is below the confidence threshold — the model is uncertain enough
    # that neighbourhood evidence should be allowed to promote a different condition.
    effective_freeze = freeze_top1 and (top1_score >= top1_confidence_threshold)

    if effective_freeze:
        top_conditions = [top1_condition] + [cond for cond, _ in remaining[: max(top_n - 1, 0)]]
    else:
        top_conditions = [cond for cond, _ in sorted(adjusted.items(), key=lambda item: item[1], reverse=True)[:top_n]]

    return {
        "adjusted_scores": adjusted,
        "top_conditions": top_conditions,
        "bonuses": bonuses,
        "penalties": penalties,
        "frozen_top1": top1_condition if effective_freeze else None,
        "top1_confidence_threshold": top1_confidence_threshold,
        "top1_score": round(top1_score, 4),
        "top1_released": not effective_freeze,
    }
