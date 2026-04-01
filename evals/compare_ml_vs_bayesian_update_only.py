#!/usr/bin/env python3
"""
Compare ML-only vs Bayesian update_only on the same NHANES 760-person cohort.

Primary metric:
  Top-3 contains any true condition (`ground_truth.expected_conditions`)

Secondary metrics:
  - Top-1 primary accuracy
  - Top-3 primary coverage
  - Healthy over-alert rate
  - Per-condition recall@3 (any-label view)
  - Per-condition absent false-positive rate
  - Per-condition threshold metrics on posterior / raw scores
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
DEFAULT_PROFILES = EVALS_DIR / "cohort" / "nhanes_balanced_760.json"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.run_bayesian import DISABLED_QUESTION_IDS, handle_questions, handle_update
from run_quiz_three_arm_eval import (
    EVAL_CONDITIONS_12,
    ModelRunner,
    compute_model_scores,
    expected_condition_ids,
)
from run_layer1_eval import CONDITION_TO_MODEL_KEY, FILTER_CRITERIA


EVAL_TO_BAYES = {
    "hypothyroidism": "thyroid",
    "kidney_disease": "kidney",
    "electrolyte_imbalance": "electrolytes",
}
for _condition_id in EVAL_CONDITIONS_12:
    EVAL_TO_BAYES.setdefault(_condition_id, _condition_id)

BAYES_TO_EVAL = {bayes_id: eval_id for eval_id, bayes_id in EVAL_TO_BAYES.items()}

warnings.filterwarnings(
    "ignore",
    message="`sklearn.utils.parallel.delayed` should be used.*",
    category=UserWarning,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare ML-only vs Bayesian update_only on the same cohort.")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES, help="Cohort JSON path.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR, help="JSON output directory.")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help="Markdown output directory.")
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
        filtered_expected = [
            item for item in expected
            if item.get("condition_id") in EVAL_CONDITIONS_12
        ]
        profile["ground_truth"]["expected_conditions"] = filtered_expected
        filtered.append(profile)
    return filtered


def top3_from_scores(score_map: dict[str, float]) -> list[str]:
    return [condition_id for condition_id, _ in sorted(score_map.items(), key=lambda item: item[1], reverse=True)[:3]]


def flagged_from_scores(score_map: dict[str, float]) -> list[str]:
    flagged: list[str] = []
    for condition_id, score in score_map.items():
        model_key = CONDITION_TO_MODEL_KEY.get(condition_id)
        if model_key is None:
            continue
        if score >= FILTER_CRITERIA.get(model_key, 0.40):
            flagged.append(condition_id)
    return flagged


def visible_questions_for_condition_block(
    condition_block: dict[str, Any],
    staged_answers: dict[str, str],
) -> list[dict[str, Any]]:
    questions = condition_block.get("questions", []) or []
    staged = condition_block.get("staged_follow_up")
    if not isinstance(staged, dict):
        return questions

    entry_question_id = staged.get("entry_question_id")
    continue_on_values = set(staged.get("continue_on_values", []) or [])
    hidden_ids = set(staged.get("hidden_question_ids", []) or [])
    base_questions = [q for q in questions if q.get("id") not in hidden_ids]
    entry_answer = staged_answers.get(str(entry_question_id))
    if entry_answer in continue_on_values:
        return questions
    return base_questions


def bayesian_update_only_scores(
    profile: dict[str, Any],
    model_scores_eval: dict[str, float],
    updater: BayesianUpdater,
    q_to_condition: dict[str, str],
) -> dict[str, float]:
    legacy_priors = {
        EVAL_TO_BAYES[condition_id]: score
        for condition_id, score in model_scores_eval.items()
        if condition_id in EVAL_TO_BAYES
    }
    answers_by_condition: dict[str, dict[str, str]] = {}
    for question_id, answer in profile.get("bayesian_answers", {}).items():
        if question_id in DISABLED_QUESTION_IDS or answer in (None, "", []):
            continue
        condition = q_to_condition.get(question_id)
        if condition is None:
            continue
        answers_by_condition.setdefault(condition, {})[question_id] = answer

    shortlist = [
        {"condition": condition_id, "probability": score}
        for condition_id, score in legacy_priors.items()
    ]
    updated = updater.update_shortlist(
        shortlist=shortlist,
        answers_by_condition=answers_by_condition,
        confounder_answers=None,
        patient_sex=str(profile.get("demographics", {}).get("sex", "")).lower() or None,
    )
    posterior_scores = {
        item["condition"]: item["probability"]
        for item in updated
    }
    normalized: dict[str, float] = {}
    for legacy_condition, score in posterior_scores.items():
        eval_condition = BAYES_TO_EVAL.get(legacy_condition)
        if eval_condition in EVAL_CONDITIONS_12:
            normalized[eval_condition] = float(score)
    return dict(sorted(normalized.items(), key=lambda item: item[1], reverse=True))


def bayesian_default_triggered_scores(
    profile: dict[str, Any],
    model_scores_eval: dict[str, float],
    updater: BayesianUpdater,
) -> dict[str, float]:
    legacy_priors = {
        EVAL_TO_BAYES[condition_id]: score
        for condition_id, score in model_scores_eval.items()
        if condition_id in EVAL_TO_BAYES
    }
    patient_sex = str(profile.get("demographics", {}).get("sex", "")).lower() or None
    existing_answers = profile.get("nhanes_inputs", {})

    questions_result = handle_questions(
        {
            "ml_scores": legacy_priors,
            "patient_sex": patient_sex,
            "existing_answers": existing_answers,
        },
        updater,
    )

    answers_by_condition: dict[str, dict[str, str]] = {}
    stored_answers = profile.get("bayesian_answers", {})
    for condition_block in questions_result.get("condition_questions", []):
        legacy_condition = condition_block.get("condition")
        if not isinstance(legacy_condition, str):
            continue
        staged_answers: dict[str, str] = {}
        all_questions = condition_block.get("questions", []) or []
        entry_question = all_questions[0] if all_questions else None
        staged = condition_block.get("staged_follow_up")
        if isinstance(staged, dict):
            entry_question_id = staged.get("entry_question_id")
            if isinstance(entry_question_id, str):
                entry_question = next(
                    (question for question in all_questions if question.get("id") == entry_question_id),
                    entry_question,
                )
        if isinstance(entry_question, dict):
            entry_question_id = entry_question.get("id")
            if isinstance(entry_question_id, str):
                entry_answer = stored_answers.get(entry_question_id)
                if entry_answer not in (None, "", []) and entry_question_id not in DISABLED_QUESTION_IDS:
                    staged_answers[entry_question_id] = entry_answer

        for question in visible_questions_for_condition_block(condition_block, staged_answers):
            question_id = question.get("id")
            if not isinstance(question_id, str):
                continue
            answer = stored_answers.get(question_id)
            if answer in (None, "", []) or question_id in DISABLED_QUESTION_IDS:
                continue
            answers_by_condition.setdefault(legacy_condition, {})[question_id] = answer

    result = handle_update(
        {
            "ml_scores": legacy_priors,
            "existing_answers": existing_answers,
            "answers_by_condition": answers_by_condition,
            "confounder_answers": {},
            "patient_sex": patient_sex,
        },
        updater,
    )
    posterior_scores = result.get("posterior_scores", {})
    normalized: dict[str, float] = {}
    for legacy_condition, score in posterior_scores.items():
        eval_condition = BAYES_TO_EVAL.get(legacy_condition)
        if eval_condition in EVAL_CONDITIONS_12:
            normalized[eval_condition] = float(score)
    return dict(sorted(normalized.items(), key=lambda item: item[1], reverse=True))


def primary_condition(profile: dict[str, Any]) -> str | None:
    for item in profile.get("ground_truth", {}).get("expected_conditions", []):
        if item.get("is_primary"):
            return item.get("condition_id")
    return None


def score_arm_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [r for r in records if r["expected_conditions"]]
    healthy = [r for r in records if r.get("profile_type") == "healthy"]
    positives = [r for r in records if r.get("profile_type") == "positive"]
    scored_primary = [r for r in records if r.get("ground_truth_primary") and r.get("top1_prediction")]

    top1_primary_accuracy = (
        sum(1 for r in scored_primary if r["top1_prediction"] == r["ground_truth_primary"]) / len(scored_primary)
        if scored_primary else 0.0
    )
    top3_primary_coverage = (
        sum(1 for r in scored_primary if r["ground_truth_primary"] in r["top3_predictions"]) / len(scored_primary)
        if scored_primary else 0.0
    )
    top3_any_true = (
        sum(1 for r in labeled if set(r["expected_conditions"]) & set(r["top3_predictions"])) / len(labeled)
        if labeled else 0.0
    )
    positive_top1_accuracy = (
        sum(1 for r in positives if r.get("top1_prediction") == r.get("ground_truth_primary")) / len(positives)
        if positives else 0.0
    )
    healthy_over_alert_rate = (
        sum(1 for r in healthy if r["flagged_conditions"]) / len(healthy)
        if healthy else 0.0
    )

    per_condition: dict[str, dict[str, Any]] = {}
    for condition_id in EVAL_CONDITIONS_12:
        condition_positive = [r for r in records if condition_id in r["expected_conditions"]]
        condition_absent = [r for r in records if condition_id not in r["expected_conditions"]]
        condition_flagged = [r for r in records if condition_id in r["flagged_conditions"]]

        hits_at_3 = sum(1 for r in condition_positive if condition_id in r["top3_predictions"])
        true_positive = sum(1 for r in condition_positive if condition_id in r["flagged_conditions"])
        absent_fp = sum(1 for r in condition_absent if condition_id in r["top3_predictions"])
        healthy_flagged = sum(
            1 for r in records
            if r.get("profile_type") == "healthy" and condition_id in r["flagged_conditions"]
        )

        per_condition[condition_id] = {
            "n_positive_profiles": len(condition_positive),
            "recall_at_3": round(hits_at_3 / len(condition_positive), 4) if condition_positive else None,
            "absent_false_positive_rate_at_3": round(absent_fp / len(condition_absent), 4) if condition_absent else None,
            "threshold_recall": round(true_positive / len(condition_positive), 4) if condition_positive else None,
            "threshold_precision": round(true_positive / len(condition_flagged), 4) if condition_flagged else None,
            "threshold_flag_rate": round(len(condition_flagged) / len(records), 4) if records else 0.0,
            "healthy_flag_rate": round(healthy_flagged / len(healthy), 4) if healthy else None,
            "mean_score_positive": round(
                sum(r["score_map"].get(condition_id, 0.0) for r in condition_positive) / len(condition_positive),
                4,
            ) if condition_positive else None,
        }

    return {
        "n_profiles": len(records),
        "n_labeled": len(labeled),
        "n_healthy": len(healthy),
        "top1_primary_accuracy": round(top1_primary_accuracy, 4),
        "top1_primary_accuracy_positive_only": round(positive_top1_accuracy, 4),
        "top3_primary_coverage": round(top3_primary_coverage, 4),
        "top3_contains_any_true_condition": round(top3_any_true, 4),
        "healthy_over_alert_rate": round(healthy_over_alert_rate, 4),
        "per_condition": per_condition,
    }


def build_records(
    profiles: list[dict[str, Any]],
    runner: ModelRunner,
    updater: BayesianUpdater,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    ml_records: list[dict[str, Any]] = []
    bayes_records: list[dict[str, Any]] = []
    default_records: list[dict[str, Any]] = []

    q_to_condition: dict[str, str] = {}
    for condition, data in updater._conditions.items():
        for question in data.get("questions", []):
            q_to_condition[question["id"]] = condition

    total = len(profiles)
    for index, profile in enumerate(profiles, start=1):
        if index % 50 == 0 or index == total:
            print(f"[{index}/{total}] {profile['profile_id']}", file=sys.stderr)

        expected = expected_condition_ids(profile)
        gt_primary = primary_condition(profile)
        ml_scores = compute_model_scores(profile, runner)
        bayes_scores = bayesian_update_only_scores(profile, ml_scores, updater, q_to_condition)
        default_scores = bayesian_default_triggered_scores(profile, ml_scores, updater)

        base = {
            "profile_id": profile["profile_id"],
            "profile_type": profile.get("profile_type"),
            "target_condition": profile.get("target_condition"),
            "expected_conditions": expected,
            "ground_truth_primary": gt_primary,
        }

        ml_records.append({
            **base,
            "score_map": ml_scores,
            "top1_prediction": next(iter(ml_scores), None),
            "top3_predictions": top3_from_scores(ml_scores),
            "flagged_conditions": flagged_from_scores(ml_scores),
        })
        bayes_records.append({
            **base,
            "score_map": bayes_scores,
            "top1_prediction": next(iter(bayes_scores), None),
            "top3_predictions": top3_from_scores(bayes_scores),
            "flagged_conditions": flagged_from_scores(bayes_scores),
        })
        default_records.append({
            **base,
            "score_map": default_scores,
            "top1_prediction": next(iter(default_scores), None),
            "top3_predictions": top3_from_scores(default_scores),
            "flagged_conditions": flagged_from_scores(default_scores),
        })

    return ml_records, bayes_records, default_records


def pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1%}"


def diff_pct(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "-"
    return f"{(b - a) * 100:+.1f} pp"


def build_markdown(
    run_id: str,
    profiles_path: Path,
    summary: dict[str, Any],
) -> str:
    ml = summary["arms"]["ml_only"]
    bayes = summary["arms"]["bayesian_update_only"]

    lines: list[str] = []
    lines.append(f"# ML vs Bayesian Update-Only Comparison — {run_id}")
    lines.append("")
    lines.append(f"- Cohort: `{profiles_path}`")
    lines.append(f"- Profiles evaluated: `{ml['n_profiles']}`")
    lines.append(f"- Primary metric: `Top-3 contains any true condition (all_labels)`")
    lines.append("")
    lines.append("## Headline Metrics")
    lines.append("")
    lines.append("| Metric | ML-only | Bayesian update_only | Delta |")
    lines.append("|--------|---------|----------------------|-------|")
    for metric_id, label in (
        ("top3_contains_any_true_condition", "Top-3 contains any true condition"),
        ("top1_primary_accuracy", "Top-1 primary accuracy"),
        ("top1_primary_accuracy_positive_only", "Top-1 primary accuracy (positives only)"),
        ("top3_primary_coverage", "Top-3 primary coverage"),
        ("healthy_over_alert_rate", "Healthy over-alert rate"),
    ):
        lines.append(
            f"| {label} | {pct(ml[metric_id])} | {pct(bayes[metric_id])} | {diff_pct(ml[metric_id], bayes[metric_id])} |"
        )
    if "default_triggered_bayesian" in summary["arms"]:
        default = summary["arms"]["default_triggered_bayesian"]
        lines.append("")
        lines.append("## Default Flow")
        lines.append("")
        lines.append("| Metric | ML-only | Default ML+Bayes | Delta | Full Bayesian update_only |")
        lines.append("|--------|---------|------------------|-------|----------------------------|")
        for metric_id, label in (
            ("top3_contains_any_true_condition", "Top-3 contains any true condition"),
            ("top1_primary_accuracy", "Top-1 primary accuracy"),
            ("top3_primary_coverage", "Top-3 primary coverage"),
            ("healthy_over_alert_rate", "Healthy over-alert rate"),
        ):
            lines.append(
                f"| {label} | {pct(ml[metric_id])} | {pct(default[metric_id])} | {diff_pct(ml[metric_id], default[metric_id])} | {pct(bayes[metric_id])} |"
            )
    lines.append("")
    lines.append("## Per-Disease")
    lines.append("")
    include_default = "default_triggered_bayesian" in summary["arms"]
    if include_default:
        lines.append("| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |")
        lines.append("|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|")
    else:
        lines.append("| Condition | N+ | ML recall@3 | Bayes recall@3 | Delta | ML absent FP@3 | Bayes absent FP@3 | ML threshold recall | Bayes threshold recall |")
        lines.append("|-----------|----|-------------|----------------|-------|-----------------|--------------------|---------------------|------------------------|")
    for condition_id in EVAL_CONDITIONS_12:
        ml_row = ml["per_condition"][condition_id]
        bayes_row = bayes["per_condition"][condition_id]
        if include_default:
            default_row = summary["arms"]["default_triggered_bayesian"]["per_condition"][condition_id]
            lines.append(
                f"| {condition_id} | {ml_row['n_positive_profiles']} | {pct(ml_row['recall_at_3'])} | "
                f"{pct(default_row['recall_at_3'])} | {pct(bayes_row['recall_at_3'])} | "
                f"{pct(ml_row['absent_false_positive_rate_at_3'])} | {pct(default_row['absent_false_positive_rate_at_3'])} | "
                f"{pct(bayes_row['absent_false_positive_rate_at_3'])} |"
            )
        else:
            lines.append(
                f"| {condition_id} | {ml_row['n_positive_profiles']} | {pct(ml_row['recall_at_3'])} | "
                f"{pct(bayes_row['recall_at_3'])} | {diff_pct(ml_row['recall_at_3'], bayes_row['recall_at_3'])} | "
                f"{pct(ml_row['absent_false_positive_rate_at_3'])} | {pct(bayes_row['absent_false_positive_rate_at_3'])} | "
                f"{pct(ml_row['threshold_recall'])} | {pct(bayes_row['threshold_recall'])} |"
            )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    logging.getLogger("bayesian.bayesian_updater").setLevel(logging.WARNING)

    profiles = load_profiles(args.profiles)
    runner = ModelRunner(max_workers=1)
    updater = BayesianUpdater()

    ml_records, bayes_records, default_records = build_records(profiles, runner, updater)

    run_id = datetime.utcnow().strftime("ml_vs_bayesian_update_only_%Y%m%d_%H%M%S")
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "profiles_path": str(args.profiles),
        "primary_metric": "top3_contains_any_true_condition",
        "arms": {
            "ml_only": score_arm_records(ml_records),
            "bayesian_update_only": score_arm_records(bayes_records),
            "default_triggered_bayesian": score_arm_records(default_records),
        },
        "records_by_arm": {
            "ml_only": ml_records,
            "bayesian_update_only": bayes_records,
            "default_triggered_bayesian": default_records,
        },
    }

    results_path = args.output_dir / f"{run_id}.json"
    report_path = args.reports_dir / f"{run_id}.md"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(build_markdown(run_id, args.profiles, payload), encoding="utf-8")

    print(f"Saved JSON results: {results_path}")
    print(f"Saved Markdown report: {report_path}")
    print(f"ML-only top3_any_true: {payload['arms']['ml_only']['top3_contains_any_true_condition']:.1%}")
    print(f"Default ML+Bayes top3_any_true: {payload['arms']['default_triggered_bayesian']['top3_contains_any_true_condition']:.1%}")
    print(f"Bayesian top3_any_true: {payload['arms']['bayesian_update_only']['top3_contains_any_true_condition']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
