#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import subprocess
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
DEFAULT_PROFILES = EVALS_DIR / "cohort" / "nhanes_balanced_800.json"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.run_bayesian import (
    DISABLED_QUESTION_IDS,
    _apply_shared_answers_to_conditions,
    _build_question_to_condition_map,
    handle_questions,
    handle_update,
)
from bayesian.quiz_to_bayesian_map import get_prefilled_answers
from compare_ml_vs_bayesian_update_only import EVAL_TO_BAYES
from run_quiz_three_arm_eval import ModelRunner, compute_model_scores

warnings.filterwarnings(
    "ignore",
    message="`sklearn.utils.parallel.delayed` should be used.*",
    category=UserWarning,
)
logging.getLogger("bayesian.bayesian_updater").disabled = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Current-state Bayes question ROI eval.")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--low-gain-threshold", type=float, default=0.01)
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
        return proc.stdout.strip() or None
    except Exception:
        return None


def entropy_bits(prob: float) -> float:
    p = min(max(float(prob), 1e-9), 1 - 1e-9)
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def patient_sex_for_profile(profile: dict[str, Any]) -> str | None:
    sex = str(profile.get("demographics", {}).get("sex", "")).lower().strip()
    return sex or None


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


def build_prefilled_by_condition(
    updater: BayesianUpdater,
    existing_answers: dict[str, Any],
    patient_sex: str | None,
) -> dict[str, dict[str, str]]:
    prefilled = {
        qid: answer
        for qid, answer in get_prefilled_answers(existing_answers).items()
        if qid not in DISABLED_QUESTION_IDS
    }
    q_to_condition = _build_question_to_condition_map(updater, patient_sex)
    grouped: dict[str, dict[str, str]] = defaultdict(dict)
    for qid, answer in prefilled.items():
        condition = q_to_condition.get(qid)
        if condition:
            grouped[condition][qid] = answer
    _apply_shared_answers_to_conditions(grouped, q_to_condition)
    return grouped


def valid_answer_values(question: dict[str, Any]) -> set[str] | None:
    options = question.get("answer_options")
    if not isinstance(options, list) or not options:
        return None
    values = {
        str(option.get("value"))
        for option in options
        if isinstance(option, dict) and option.get("value") is not None
    }
    return values or None


def classify_question(
    avg_gain_bits: float,
    n_valid_answers: int,
    invalid_rate: float,
    top3_gain_count: int,
    top3_loss_count: int,
    low_gain_threshold: float,
) -> str:
    if n_valid_answers == 0:
        return "no_data"
    if avg_gain_bits < 0 and top3_gain_count <= top3_loss_count:
        return "remove_candidate"
    if invalid_rate >= 0.20:
        return "replace_or_refresh_data"
    if avg_gain_bits < low_gain_threshold:
        return "review_low_gain"
    return "keep"


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    profiles = json.loads(args.profiles.read_text(encoding="utf-8"))
    runner = ModelRunner(max_workers=1)
    updater = BayesianUpdater()

    question_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "condition": None,
            "text": None,
            "n_visible": 0,
            "n_valid_answers": 0,
            "n_invalid_answers": 0,
            "n_missing_answers": 0,
            "gain_bits": [],
            "posterior_delta": [],
            "surface_delta": [],
            "top3_gain_count": 0,
            "top3_loss_count": 0,
            "invalid_examples": set(),
        }
    )

    for index, profile in enumerate(profiles, start=1):
        if index % 50 == 0 or index == len(profiles):
            print(f"[{index}/{len(profiles)}] {profile['profile_id']}", file=sys.stderr)

        existing_answers = profile.get("nhanes_inputs", {})
        stored_answers = profile.get("bayesian_answers", {})
        patient_sex = patient_sex_for_profile(profile)

        ml_scores_eval = compute_model_scores(profile, runner)
        legacy_priors = {
            EVAL_TO_BAYES[condition_id]: score
            for condition_id, score in ml_scores_eval.items()
            if condition_id in EVAL_TO_BAYES
        }

        base_surface = handle_update(
            {
                "ml_scores": legacy_priors,
                "existing_answers": existing_answers,
                "answers_by_condition": {},
                "confounder_answers": {},
                "patient_sex": patient_sex,
            },
            updater,
        )
        base_surface_scores = base_surface.get("posterior_scores", {})
        base_surface_top3 = {
            condition_id
            for condition_id, _ in sorted(base_surface_scores.items(), key=lambda item: item[1], reverse=True)[:3]
        }
        prefilled_by_condition = build_prefilled_by_condition(updater, existing_answers, patient_sex)

        questions_result = handle_questions(
            {
                "ml_scores": legacy_priors,
                "patient_sex": patient_sex,
                "existing_answers": existing_answers,
            },
            updater,
        )

        for condition_block in questions_result.get("condition_questions", []):
            condition = condition_block.get("condition")
            if not isinstance(condition, str):
                continue

            staged_answers: dict[str, str] = {}
            all_questions = condition_block.get("questions", []) or []
            if all_questions:
                entry_question = all_questions[0]
                entry_qid = entry_question.get("id")
                if isinstance(entry_qid, str):
                    entry_answer = stored_answers.get(entry_qid)
                    if entry_answer not in (None, "", []):
                        staged_answers[entry_qid] = str(entry_answer)

            prior = float(legacy_priors.get(condition, 0.0))
            base_answers = dict(prefilled_by_condition.get(condition, {}))
            base_posterior = updater.update(
                condition,
                prior_prob=prior,
                answers=base_answers,
                confounder_multiplier=1.0,
            )["posterior"]

            for question in visible_questions_for_condition_block(condition_block, staged_answers):
                qid = question.get("id")
                if not isinstance(qid, str):
                    continue

                stats = question_stats[qid]
                stats["condition"] = condition
                stats["text"] = question.get("text")
                stats["n_visible"] += 1

                raw_answer = stored_answers.get(qid)
                if raw_answer in (None, "", []):
                    stats["n_missing_answers"] += 1
                    continue

                answer = str(raw_answer)
                valid_values = valid_answer_values(question)
                if valid_values is not None and answer not in valid_values:
                    stats["n_invalid_answers"] += 1
                    if len(stats["invalid_examples"]) < 3:
                        stats["invalid_examples"].add(answer)
                    continue

                stats["n_valid_answers"] += 1

                answers = {**base_answers, qid: answer}
                posterior = updater.update(
                    condition,
                    prior_prob=prior,
                    answers=answers,
                    confounder_multiplier=1.0,
                )["posterior"]
                stats["gain_bits"].append(float(entropy_bits(base_posterior) - entropy_bits(posterior)))
                stats["posterior_delta"].append(float(posterior - base_posterior))

                single_surface = handle_update(
                    {
                        "ml_scores": legacy_priors,
                        "existing_answers": existing_answers,
                        "answers_by_condition": {condition: {qid: answer}},
                        "confounder_answers": {},
                        "patient_sex": patient_sex,
                    },
                    updater,
                )
                single_surface_scores = single_surface.get("posterior_scores", {})
                stats["surface_delta"].append(
                    float(single_surface_scores.get(condition, 0.0) - base_surface_scores.get(condition, 0.0))
                )
                single_top3 = {
                    condition_id
                    for condition_id, _ in sorted(single_surface_scores.items(), key=lambda item: item[1], reverse=True)[:3]
                }
                if condition not in base_surface_top3 and condition in single_top3:
                    stats["top3_gain_count"] += 1
                if condition in base_surface_top3 and condition not in single_top3:
                    stats["top3_loss_count"] += 1

    question_rows: list[dict[str, Any]] = []
    for qid, stats in question_stats.items():
        gains = stats["gain_bits"]
        invalid_rate = (
            stats["n_invalid_answers"] / (stats["n_invalid_answers"] + stats["n_valid_answers"])
            if (stats["n_invalid_answers"] + stats["n_valid_answers"]) else 0.0
        )
        avg_gain = float(statistics.mean(gains)) if gains else 0.0
        median_gain = float(statistics.median(gains)) if gains else 0.0
        avg_post_delta = float(statistics.mean(stats["posterior_delta"])) if stats["posterior_delta"] else 0.0
        avg_surface_delta = float(statistics.mean(stats["surface_delta"])) if stats["surface_delta"] else 0.0
        row = {
            "question_id": qid,
            "condition": stats["condition"],
            "text": stats["text"],
            "n_visible": stats["n_visible"],
            "n_valid_answers": stats["n_valid_answers"],
            "n_invalid_answers": stats["n_invalid_answers"],
            "n_missing_answers": stats["n_missing_answers"],
            "invalid_rate": round(invalid_rate, 4),
            "avg_information_gain_bits": round(avg_gain, 4),
            "median_information_gain_bits": round(median_gain, 4),
            "avg_posterior_delta": round(avg_post_delta, 4),
            "avg_surface_delta": round(avg_surface_delta, 4),
            "top3_gain_count": stats["top3_gain_count"],
            "top3_loss_count": stats["top3_loss_count"],
            "invalid_examples": sorted(stats["invalid_examples"]),
            "status": classify_question(
                avg_gain_bits=avg_gain,
                n_valid_answers=stats["n_valid_answers"],
                invalid_rate=invalid_rate,
                top3_gain_count=stats["top3_gain_count"],
                top3_loss_count=stats["top3_loss_count"],
                low_gain_threshold=args.low_gain_threshold,
            ),
        }
        question_rows.append(row)

    question_rows.sort(
        key=lambda row: (
            row["status"] != "remove_candidate",
            row["status"] != "replace_or_refresh_data",
            row["avg_information_gain_bits"],
        )
    )

    summary = {
        "n_questions_scored": len(question_rows),
        "n_remove_candidates": sum(row["status"] == "remove_candidate" for row in question_rows),
        "n_replace_or_refresh_data": sum(row["status"] == "replace_or_refresh_data" for row in question_rows),
        "n_review_low_gain": sum(row["status"] == "review_low_gain" for row in question_rows),
        "n_keep": sum(row["status"] == "keep" for row in question_rows),
        "low_gain_threshold_bits": args.low_gain_threshold,
    }

    run_id = f"bayes_question_roi_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    payload = {
        "run_id": run_id,
        "git_sha": _safe_git_sha(),
        "profiles_path": str(args.profiles),
        "summary": summary,
        "questions": question_rows,
    }

    json_path = args.output_dir / f"{run_id}.json"
    md_path = args.reports_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2))

    lines = [
        f"# Bayes Question ROI — {run_id}",
        "",
        f"- Cohort: `{args.profiles}`",
        f"- Questions scored: `{summary['n_questions_scored']}`",
        f"- Low-gain threshold: `{args.low_gain_threshold:.3f}` bits",
        "",
        "## Summary",
        "",
        f"- Remove candidates: `{summary['n_remove_candidates']}`",
        f"- Replace / refresh-data candidates: `{summary['n_replace_or_refresh_data']}`",
        f"- Review low-gain: `{summary['n_review_low_gain']}`",
        f"- Keep: `{summary['n_keep']}`",
        "",
        "## Current Keep / Review / Remove",
        "",
        "| Question | Condition | Status | N valid | N invalid | Avg gain (bits) | Avg posterior delta | Top-3 gains | Top-3 losses |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in question_rows:
        lines.append(
            f"| {row['question_id']} | {row['condition']} | {row['status']} | "
            f"{row['n_valid_answers']} | {row['n_invalid_answers']} | "
            f"{row['avg_information_gain_bits']:.4f} | {row['avg_posterior_delta']:.4f} | "
            f"{row['top3_gain_count']} | {row['top3_loss_count']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `remove_candidate`: negative average information gain with no compensating top-3 benefit.",
            "- `replace_or_refresh_data`: answer schema mismatch or stale cohort-answer problem is likely dominating the metric.",
            "- `review_low_gain`: active question with near-zero average gain on the current setup.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n")

    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
