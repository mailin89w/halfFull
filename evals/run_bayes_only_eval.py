#!/usr/bin/env python3
"""
Evaluate a Bayes-only routing policy on the balanced 760-person cohort.

This script intentionally removes ML ranking from the loop and answers:
  "If Bayesian clarification had to operate without ML priors, how well would
   a realistic question-asking policy perform, and how many questions would it ask?"

Policy
------
1. Start from a configurable prior scheme (default: flat 0.05 per condition).
2. Apply silent quiz-prefill overlaps from NHANES inputs without counting them
   as asked clarification questions.
3. Ask one screening Bayesian question per condition with available questions.
4. Recompute posteriors and continue asking only for active conditions:
     - posterior >= continue_threshold, OR
     - in the current top_k_active conditions
5. Respect a global question budget and a per-condition question cap.

Important caveat
----------------
`profile["bayesian_answers"]` in this cohort are synthetic. They were generated
at cohort-build time from the NHANES row plus latent-state heuristics, not from
real patient dialogue. Bayes-only results can therefore look stronger than a
real deployment where follow-up answers are noisier and must be collected live.
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import subprocess
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
DEFAULT_PROFILES = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"
REAL_NHANES_CSV = PROJECT_ROOT / "data" / "processed" / "nhanes_2003_2006_real_cohort.csv"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.quiz_to_bayesian_map import get_prefilled_answers
from bayesian.run_bayesian import (
    DISABLED_QUESTION_IDS,
    QUESTION_TO_SHARED_KEY,
    _apply_shared_answers_to_conditions,
)
from run_quiz_three_arm_eval import EVAL_CONDITIONS_12, expected_condition_ids
from compare_ml_vs_bayesian_update_only import (
    EVAL_TO_BAYES,
    BAYES_TO_EVAL,
    top3_from_scores,
    flagged_from_scores,
    primary_condition,
    score_arm_records,
)

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

SEX_AGE_BUCKETS: list[tuple[int, int | None, str]] = [
    (0, 17, "0-17"),
    (18, 39, "18-39"),
    (40, 59, "40-59"),
    (60, None, "60+"),
]
REAL_PANEL_CONDITION_COLUMNS = {
    "anemia": "anemia",
    "hypothyroidism": "thyroid",
    "sleep_disorder": "sleep_disorder",
    "kidney_disease": "kidney",
    "hepatitis": "hepatitis_bc",
    "liver": "liver",
    "iron_deficiency": "iron_deficiency",
    "vitamin_d_deficiency": "vitamin_d_deficiency",
    "electrolyte_imbalance": "electrolyte_imbalance",
    "inflammation": "hidden_inflammation",
    "prediabetes": "prediabetes",
    "perimenopause": "perimenopause_proxy_probable",
}
SEX_AGE_PRIOR_SMOOTHING = 25.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Bayes-only eval with question-count metrics.")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES, help="Cohort JSON path.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="JSON output directory.")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help="Markdown output directory.")
    parser.add_argument(
        "--prior-schemes",
        nargs="+",
        default=["flat_0.05", "flat_0.10", "cohort_prevalence"],
        choices=["flat_0.05", "flat_0.10", "flat_0.20", "cohort_prevalence", "sex_age_prevalence"],
        help="Prior schemes to evaluate.",
    )
    parser.add_argument("--max-total-questions", type=int, default=20, help="Max asked Bayesian questions per profile.")
    parser.add_argument("--max-questions-per-condition", type=int, default=3, help="Max asked questions per condition.")
    parser.add_argument("--top-k-active", type=int, default=5, help="Always continue top-K posterior conditions.")
    parser.add_argument("--continue-threshold", type=float, default=0.08, help="Continue asking when posterior >= threshold.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Max explicit questioning rounds.")
    return parser.parse_args()


def _safe_git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        sha = proc.stdout.strip()
        return sha or None
    except Exception:
        return None


def load_profiles(path: Path) -> list[dict[str, Any]]:
    profiles = json.loads(path.read_text(encoding="utf-8"))
    filtered: list[dict[str, Any]] = []
    for profile in profiles:
        expected = profile.get("ground_truth", {}).get("expected_conditions", [])
        profile["ground_truth"]["expected_conditions"] = [
            item for item in expected
            if item.get("condition_id") in EVAL_CONDITIONS_12
        ]
        filtered.append(profile)
    return filtered


def _age_bucket_label(age: float | int | None) -> str:
    if age is None:
        return "unknown"
    age_value = float(age)
    for lower, upper, label in SEX_AGE_BUCKETS:
        if upper is None and age_value >= lower:
            return label
        if upper is not None and lower <= age_value <= upper:
            return label
    return "unknown"


def _sex_label(value: object) -> str:
    text = str(value).strip().upper()
    if text in {"F", "FEMALE", "2", "2.0"}:
        return "F"
    if text in {"M", "MALE", "1", "1.0"}:
        return "M"
    return "unknown"


def build_prior_map(profiles: list[dict[str, Any]], scheme: str) -> dict[str, float]:
    if scheme.startswith("flat_"):
        value = float(scheme.split("_", 1)[1])
        return {condition_id: value for condition_id in EVAL_CONDITIONS_12}

    if scheme == "cohort_prevalence":
        counts = Counter()
        for profile in profiles:
            for condition_id in expected_condition_ids(profile):
                counts[condition_id] += 1
        return {
            condition_id: counts[condition_id] / len(profiles)
            for condition_id in EVAL_CONDITIONS_12
        }

    if scheme == "sex_age_prevalence":
        raise ValueError("sex_age_prevalence is profile-specific; use build_prior_context/get_prior_map_for_profile.")

    raise ValueError(f"Unsupported prior scheme: {scheme}")


def build_prior_context(profiles: list[dict[str, Any]], scheme: str) -> dict[str, Any]:
    if scheme != "sex_age_prevalence":
        return {"scheme": scheme, "prior_map": build_prior_map(profiles, scheme)}

    usecols = ["SEQN", "gender_code", "age_years", *REAL_PANEL_CONDITION_COLUMNS.values()]
    df = pd.read_csv(REAL_NHANES_CSV, usecols=usecols)
    deduped = (
        df.groupby("SEQN", as_index=False)
        .agg({
            "gender_code": "first",
            "age_years": "first",
            **{column: "max" for column in REAL_PANEL_CONDITION_COLUMNS.values()},
        })
        .copy()
    )
    deduped["sex"] = deduped["gender_code"].map(lambda value: _sex_label(value))
    deduped["age_bucket"] = deduped["age_years"].map(_age_bucket_label)

    overall_rates: dict[str, float] = {}
    sex_rates: dict[str, dict[str, float]] = {}
    sex_age_rates: dict[tuple[str, str], dict[str, float]] = {}
    stratum_sizes: dict[tuple[str, str], int] = {}

    for condition_id, column in REAL_PANEL_CONDITION_COLUMNS.items():
        condition_series = pd.to_numeric(deduped[column], errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
        overall = float(condition_series.mean())
        overall_rates[condition_id] = overall

        for sex in sorted(deduped["sex"].dropna().unique()):
            mask = deduped["sex"] == sex
            if int(mask.sum()) == 0:
                continue
            sex_rates.setdefault(sex, {})[condition_id] = float(condition_series[mask].mean())

        for sex in sorted(deduped["sex"].dropna().unique()):
            for bucket in sorted(deduped["age_bucket"].dropna().unique()):
                mask = (deduped["sex"] == sex) & (deduped["age_bucket"] == bucket)
                n = int(mask.sum())
                if n == 0:
                    continue
                positives = float(condition_series[mask].sum())
                smoothed = (positives + SEX_AGE_PRIOR_SMOOTHING * overall) / (n + SEX_AGE_PRIOR_SMOOTHING)
                sex_age_rates.setdefault((sex, bucket), {})[condition_id] = float(smoothed)
                stratum_sizes[(sex, bucket)] = n

    return {
        "scheme": scheme,
        "source_csv": str(REAL_NHANES_CSV),
        "n_unique_people": int(len(deduped)),
        "age_buckets": [label for _lower, _upper, label in SEX_AGE_BUCKETS],
        "overall_rates": overall_rates,
        "sex_rates": sex_rates,
        "sex_age_rates": {
            f"{sex}|{bucket}": rates for (sex, bucket), rates in sex_age_rates.items()
        },
        "stratum_sizes": {
            f"{sex}|{bucket}": size for (sex, bucket), size in stratum_sizes.items()
        },
        "smoothing_pseudo_count": SEX_AGE_PRIOR_SMOOTHING,
    }


def get_prior_map_for_profile(
    profile: dict[str, Any],
    scheme: str,
    prior_context: dict[str, Any],
) -> dict[str, float]:
    if scheme != "sex_age_prevalence":
        return dict(prior_context["prior_map"])

    demographics = profile.get("demographics", {})
    sex = _sex_label(demographics.get("sex"))
    age_bucket = _age_bucket_label(demographics.get("age"))
    key = f"{sex}|{age_bucket}"
    overall = prior_context["overall_rates"]
    sex_only = prior_context["sex_rates"].get(sex, {})
    sex_age = prior_context["sex_age_rates"].get(key, {})

    return {
        condition_id: float(
            sex_age.get(condition_id, sex_only.get(condition_id, overall.get(condition_id, 0.05)))
        )
        for condition_id in EVAL_CONDITIONS_12
    }


def summarise_counts(values: list[int]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0}
    ordered = sorted(values)
    p90_index = min(len(ordered) - 1, max(0, int(0.9 * len(ordered)) - 1))
    return {
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "p90": round(float(ordered[p90_index]), 2),
        "max": round(float(max(values)), 2),
    }


def _available_questions(
    updater: BayesianUpdater,
    legacy_condition: str,
    posterior: float,
    patient_sex: str | None,
) -> list[dict[str, Any]]:
    return updater.get_questions(
        legacy_condition,
        prior_prob=posterior,
        patient_sex=patient_sex,
        max_questions=50,
    )


def run_policy_for_profile(
    profile: dict[str, Any],
    updater: BayesianUpdater,
    base_priors_eval: dict[str, float],
    q_to_condition: dict[str, str],
    *,
    max_total_questions: int,
    max_questions_per_condition: int,
    top_k_active: int,
    continue_threshold: float,
    max_rounds: int,
) -> dict[str, Any]:
    patient_sex = str(profile.get("demographics", {}).get("sex", "")).lower() or None
    legacy_priors = {
        EVAL_TO_BAYES[condition_id]: base_priors_eval[condition_id]
        for condition_id in EVAL_CONDITIONS_12
    }

    raw_existing_answers = profile.get("nhanes_inputs", {})
    prefilled = get_prefilled_answers(raw_existing_answers)

    answers_by_condition: dict[str, dict[str, str]] = {}
    asked_questions: list[dict[str, Any]] = []
    asked_counts_by_condition: Counter[str] = Counter()
    seen_question_ids: set[str] = set()
    seen_shared_keys: set[str] = set()

    for question_id, answer in prefilled.items():
        if question_id in DISABLED_QUESTION_IDS:
            continue
        condition = q_to_condition.get(question_id)
        if condition is None:
            continue
        answers_by_condition.setdefault(condition, {})[question_id] = answer
        seen_question_ids.add(question_id)
        seen_shared_keys.add(QUESTION_TO_SHARED_KEY.get(question_id, question_id))

    _apply_shared_answers_to_conditions(answers_by_condition, q_to_condition)

    shortlist = [
        {"condition": legacy_condition, "probability": prior}
        for legacy_condition, prior in legacy_priors.items()
    ]
    updated = updater.update_shortlist(
        shortlist=shortlist,
        answers_by_condition=answers_by_condition,
        confounder_answers=None,
        patient_sex=patient_sex,
    )
    current_posteriors = {item["condition"]: float(item["probability"]) for item in updated}

    for round_index in range(max_rounds):
        if len(asked_questions) >= max_total_questions:
            break

        ranked_conditions = [
            condition
            for condition, _score in sorted(current_posteriors.items(), key=lambda kv: kv[1], reverse=True)
        ]
        if round_index == 0:
            candidate_conditions = [
                condition for condition in ranked_conditions
                if _available_questions(updater, condition, current_posteriors[condition], patient_sex)
            ]
        else:
            top_k = set(ranked_conditions[:top_k_active])
            candidate_conditions = [
                condition for condition in ranked_conditions
                if condition in top_k or current_posteriors.get(condition, 0.0) >= continue_threshold
            ]

        asked_this_round = 0
        for legacy_condition in candidate_conditions:
            if len(asked_questions) >= max_total_questions:
                break
            if asked_counts_by_condition[legacy_condition] >= max_questions_per_condition:
                continue

            question_list = _available_questions(
                updater,
                legacy_condition,
                current_posteriors.get(legacy_condition, legacy_priors.get(legacy_condition, 0.05)),
                patient_sex,
            )
            next_question: dict[str, Any] | None = None
            for question in question_list:
                question_id = question["id"]
                shared_key = QUESTION_TO_SHARED_KEY.get(question_id, question_id)
                if question_id in DISABLED_QUESTION_IDS:
                    continue
                if question_id in seen_question_ids or shared_key in seen_shared_keys:
                    continue
                next_question = question
                break
            if next_question is None:
                continue

            question_id = next_question["id"]
            answer = profile.get("bayesian_answers", {}).get(question_id)
            if answer in (None, "", []):
                continue

            answers_by_condition.setdefault(legacy_condition, {})[question_id] = answer
            seen_question_ids.add(question_id)
            seen_shared_keys.add(QUESTION_TO_SHARED_KEY.get(question_id, question_id))
            asked_counts_by_condition[legacy_condition] += 1
            asked_questions.append(
                {
                    "round": round_index + 1,
                    "condition": legacy_condition,
                    "question_id": question_id,
                    "answer": answer,
                }
            )
            asked_this_round += 1

        if asked_this_round == 0:
            break

        _apply_shared_answers_to_conditions(answers_by_condition, q_to_condition)
        updated = updater.update_shortlist(
            shortlist=shortlist,
            answers_by_condition=answers_by_condition,
            confounder_answers=None,
            patient_sex=patient_sex,
        )
        current_posteriors = {item["condition"]: float(item["probability"]) for item in updated}

    final_eval_scores: dict[str, float] = {}
    for legacy_condition, score in current_posteriors.items():
        eval_condition = BAYES_TO_EVAL.get(legacy_condition)
        if eval_condition in EVAL_CONDITIONS_12:
            final_eval_scores[eval_condition] = score
    final_eval_scores = dict(sorted(final_eval_scores.items(), key=lambda kv: kv[1], reverse=True))

    return {
        "score_map": final_eval_scores,
        "asked_questions": asked_questions,
        "n_questions_asked": len(asked_questions),
        "n_prefilled_quiz_overlaps": len(prefilled),
        "asked_counts_by_condition": dict(asked_counts_by_condition),
        "posterior_trace_final": current_posteriors,
    }


def summarise_question_metrics(profile_records: list[dict[str, Any]]) -> dict[str, Any]:
    asked_counts = [record["n_questions_asked"] for record in profile_records]
    prefilled_counts = [record["n_prefilled_quiz_overlaps"] for record in profile_records]

    by_condition_asked: defaultdict[str, list[int]] = defaultdict(list)
    by_condition_surface: Counter[str] = Counter()
    by_round: Counter[int] = Counter()
    for record in profile_records:
        local_counts = Counter()
        for question in record.get("asked_questions", []):
            local_counts[question["condition"]] += 1
            by_round[int(question["round"])] += 1
        for condition_id in EVAL_CONDITIONS_12:
            bayes_condition = EVAL_TO_BAYES[condition_id]
            by_condition_asked[condition_id].append(local_counts.get(bayes_condition, 0))
            if local_counts.get(bayes_condition, 0) > 0:
                by_condition_surface[condition_id] += 1

    return {
        "asked_questions_per_profile": summarise_counts(asked_counts),
        "prefilled_quiz_overlaps_per_profile": summarise_counts(prefilled_counts),
        "questions_asked_by_round": dict(sorted(by_round.items())),
        "per_condition_question_load": {
            condition_id: {
                "mean_questions_asked": round(statistics.mean(values), 2),
                "profiles_with_any_question_rate": round(by_condition_surface[condition_id] / len(profile_records), 4),
            }
            for condition_id, values in by_condition_asked.items()
        },
    }


def build_markdown(
    run_id: str,
    payload: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    lines: list[str] = []
    lines.append(f"# Bayes-Only Eval — {run_id}")
    lines.append("")
    lines.append(f"- Cohort: `{payload['profiles_path']}`")
    lines.append(f"- Profiles evaluated: `{payload['n_profiles']}`")
    lines.append(f"- Policy: `screen all conditions once, then continue only active conditions`")
    lines.append(f"- Budget: `max_total_questions={args.max_total_questions}`, `max_questions_per_condition={args.max_questions_per_condition}`, `max_rounds={args.max_rounds}`")
    lines.append("")
    lines.append("## Caveat")
    lines.append("")
    lines.append("- `bayesian_answers` in this cohort are synthetic and were generated at build time from NHANES rows plus latent-state heuristics.")
    lines.append("- This can overstate Bayes-only performance because the evaluator is consuming simulator-generated follow-up answers, not real patient dialogue.")
    lines.append("- Quiz-overlap prefills use `nhanes_inputs` and are not counted as asked Bayesian clarification questions.")
    if "sex_age_prevalence" in payload["schemes"]:
        context = payload["schemes"]["sex_age_prevalence"].get("prior_context", {})
        lines.append(
            f"- `sex_age_prevalence` priors come from deduped real NHANES 2003–2006 participants "
            f"(`{context.get('n_unique_people', 'unknown')}` people), stratified by sex and age bucket with light smoothing."
        )
    lines.append("")
    lines.append("## Headline By Prior Scheme")
    lines.append("")
    lines.append("| Prior scheme | Top-3 any true | Top-1 primary | Top-3 primary | Healthy over-alert | Mean asked Qs | Median asked Qs | P90 asked Qs | Mean quiz-prefills |")
    lines.append("|--------------|----------------|---------------|---------------|--------------------|---------------|-----------------|--------------|--------------------|")
    for scheme in payload["schemes"]:
        summary = payload["schemes"][scheme]["summary"]
        q = payload["schemes"][scheme]["question_metrics"]
        lines.append(
            f"| {scheme} | {summary['top3_contains_any_true_condition']:.1%} | {summary['top1_primary_accuracy']:.1%} | "
            f"{summary['top3_primary_coverage']:.1%} | {summary['healthy_over_alert_rate']:.1%} | "
            f"{q['asked_questions_per_profile']['mean']:.2f} | {q['asked_questions_per_profile']['median']:.2f} | "
            f"{q['asked_questions_per_profile']['p90']:.2f} | {q['prefilled_quiz_overlaps_per_profile']['mean']:.2f} |"
        )
    default_scheme = payload["default_scheme"]
    default_summary = payload["schemes"][default_scheme]["summary"]
    default_q = payload["schemes"][default_scheme]["question_metrics"]
    lines.append("")
    lines.append(f"## Per-Disease — {default_scheme}")
    lines.append("")
    lines.append("| Condition | N+ | Recall@3 | Absent FP@3 | Threshold recall | Mean questions asked | Profiles with any question |")
    lines.append("|-----------|----|----------|-------------|------------------|----------------------|----------------------------|")
    for condition_id in EVAL_CONDITIONS_12:
        row = default_summary["per_condition"][condition_id]
        qrow = default_q["per_condition_question_load"][condition_id]
        lines.append(
            f"| {condition_id} | {row['n_positive_profiles']} | {row['recall_at_3']:.1%} | "
            f"{row['absent_false_positive_rate_at_3']:.1%} | {row['threshold_recall']:.1%} | "
            f"{qrow['mean_questions_asked']:.2f} | {qrow['profiles_with_any_question_rate']:.1%} |"
        )
    lines.append("")
    lines.append("## Question Load")
    lines.append("")
    lines.append(f"- Mean asked Bayesian questions/profile: `{default_q['asked_questions_per_profile']['mean']}`")
    lines.append(f"- Median asked Bayesian questions/profile: `{default_q['asked_questions_per_profile']['median']}`")
    lines.append(f"- P90 asked Bayesian questions/profile: `{default_q['asked_questions_per_profile']['p90']}`")
    lines.append(f"- Max asked Bayesian questions/profile: `{default_q['asked_questions_per_profile']['max']}`")
    lines.append(f"- Mean silent quiz-prefills/profile: `{default_q['prefilled_quiz_overlaps_per_profile']['mean']}`")
    lines.append(f"- Questions asked by round: `{default_q['questions_asked_by_round']}`")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles(args.profiles)
    updater = BayesianUpdater()

    q_to_condition: dict[str, str] = {}
    for condition, data in updater._conditions.items():
        for question in data.get("questions", []):
            q_to_condition[question["id"]] = condition

    results_by_scheme: dict[str, Any] = {}
    for scheme in args.prior_schemes:
        print(f"Running scheme: {scheme}", file=sys.stderr)
        prior_context = build_prior_context(profiles, scheme)
        profile_records: list[dict[str, Any]] = []
        for index, profile in enumerate(profiles, start=1):
            if index % 100 == 0 or index == len(profiles):
                print(f"[{scheme}] {index}/{len(profiles)}", file=sys.stderr)
            priors = get_prior_map_for_profile(profile, scheme, prior_context)
            policy_result = run_policy_for_profile(
                profile,
                updater,
                priors,
                q_to_condition,
                max_total_questions=args.max_total_questions,
                max_questions_per_condition=args.max_questions_per_condition,
                top_k_active=args.top_k_active,
                continue_threshold=args.continue_threshold,
                max_rounds=args.max_rounds,
            )
            score_map = policy_result["score_map"]
            profile_records.append(
                {
                    "profile_id": profile["profile_id"],
                    "profile_type": profile.get("profile_type"),
                    "target_condition": profile.get("target_condition"),
                    "expected_conditions": expected_condition_ids(profile),
                    "ground_truth_primary": primary_condition(profile),
                    "score_map": score_map,
                    "top1_prediction": next(iter(score_map), None),
                    "top3_predictions": top3_from_scores(score_map),
                    "flagged_conditions": flagged_from_scores(score_map),
                    "asked_questions": policy_result["asked_questions"],
                    "n_questions_asked": policy_result["n_questions_asked"],
                    "n_prefilled_quiz_overlaps": policy_result["n_prefilled_quiz_overlaps"],
                    "asked_counts_by_condition": policy_result["asked_counts_by_condition"],
                }
            )

        results_by_scheme[scheme] = {
            "summary": score_arm_records(profile_records),
            "question_metrics": summarise_question_metrics(profile_records),
            "profile_records": profile_records,
            "prior_context": prior_context,
        }

    run_id = datetime.utcnow().strftime("bayes_only_%Y%m%d_%H%M%S")
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "profiles_path": str(args.profiles),
        "n_profiles": len(profiles),
        "policy": {
            "max_total_questions": args.max_total_questions,
            "max_questions_per_condition": args.max_questions_per_condition,
            "top_k_active": args.top_k_active,
            "continue_threshold": args.continue_threshold,
            "max_rounds": args.max_rounds,
        },
        "default_scheme": args.prior_schemes[0],
        "schemes": results_by_scheme,
        "notes": {
            "synthetic_bayesian_answers": True,
            "note": "bayesian_answers are synthetic, generated from NHANES row + latent-state heuristics during cohort build.",
        },
    }

    results_path = args.output_dir / f"{run_id}.json"
    report_path = args.reports_dir / f"{run_id}.md"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(build_markdown(run_id, payload, args), encoding="utf-8")

    print(f"Saved JSON results: {results_path}")
    print(f"Saved Markdown report: {report_path}")
    for scheme in args.prior_schemes:
        summary = payload["schemes"][scheme]["summary"]
        q = payload["schemes"][scheme]["question_metrics"]["asked_questions_per_profile"]
        print(
            f"{scheme}: top3_any_true={summary['top3_contains_any_true_condition']:.1%}, "
            f"healthy_over_alert={summary['healthy_over_alert_rate']:.1%}, "
            f"mean_questions={q['mean']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
