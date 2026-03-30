#!/usr/bin/env python3
"""
run_quiz_three_arm_eval.py

Three-arm quiz-only evaluation on the real NHANES balanced cohort:
  1. models_only     -> local 12-condition model ranking only
  2. medgemma_only   -> live /api/deep-analyze using quiz answers only
  3. hybrid_top5     -> live /api/deep-analyze using quiz answers + top-5 model scores

Design goals:
  - same sampled profiles for every arm
  - no Bayesian follow-up inputs
  - no KNN neighbour signals
  - primary metric: recall@3
  - guardrails: healthy over-alert, per-condition false-positive pressure
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import types
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"
PROFILES_PATH = EVALS_DIR / "cohort" / "nhanes_balanced_650.json"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

EVAL_CONDITIONS_12: list[str] = [
    "perimenopause",
    "hypothyroidism",
    "kidney_disease",
    "sleep_disorder",
    "anemia",
    "iron_deficiency",
    "hepatitis",
    "liver",
    "prediabetes",
    "inflammation",
    "electrolyte_imbalance",
    "vitamin_d_deficiency",
]

LEGACY_TO_EVAL_CONDITION: dict[str, str] = {
    "thyroid": "hypothyroidism",
    "kidney": "kidney_disease",
    "electrolytes": "electrolyte_imbalance",
    "vitamins": "vitamin_d_deficiency",
}

ABSENT_NEIGHBOUR_MAP: dict[str, list[str]] = {
    "perimenopause": ["hypothyroidism", "anemia", "sleep_disorder"],
    "hypothyroidism": ["perimenopause", "anemia", "sleep_disorder"],
    "kidney_disease": ["prediabetes", "electrolyte_imbalance"],
    "sleep_disorder": ["hypothyroidism", "perimenopause", "anemia"],
    "anemia": ["iron_deficiency", "hypothyroidism", "sleep_disorder"],
    "iron_deficiency": ["anemia", "perimenopause"],
    "hepatitis": ["liver", "inflammation"],
    "liver": ["hepatitis", "inflammation"],
    "prediabetes": ["kidney_disease", "electrolyte_imbalance"],
    "inflammation": ["hepatitis", "liver", "anemia"],
    "electrolyte_imbalance": ["kidney_disease", "prediabetes"],
    "vitamin_d_deficiency": ["sleep_disorder", "inflammation"],
}


@dataclass
class EvalConfig:
    base_url: str
    profiles_path: Path
    output_dir: Path
    reports_dir: Path
    sample_per_condition: int
    multi_per_condition: int
    healthy_n: int
    seed: int
    timeout: float
    dry_run: bool


def parse_args() -> EvalConfig:
    parser = argparse.ArgumentParser(description="Run 3-arm quiz-only eval on the NHANES balanced cohort.")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000", help="Base URL of the local Next app.")
    parser.add_argument("--profiles", type=Path, default=PROFILES_PATH, help="Balanced NHANES cohort path.")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR, help="JSON output directory.")
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR, help="Markdown output directory.")
    parser.add_argument("--sample-per-condition", type=int, default=4, help="Profiles per target condition in the eval sample.")
    parser.add_argument("--multi-per-condition", type=int, default=1, help="Max multi-condition profiles per target condition sample.")
    parser.add_argument("--healthy-n", type=int, default=12, help="Healthy profiles in the eval sample.")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Per-request timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Build sample and local model outputs only.")
    args = parser.parse_args()
    return EvalConfig(
        base_url=args.base_url.rstrip("/"),
        profiles_path=args.profiles,
        output_dir=args.output,
        reports_dir=args.reports,
        sample_per_condition=args.sample_per_condition,
        multi_per_condition=args.multi_per_condition,
        healthy_n=args.healthy_n,
        seed=args.seed,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )


def _load_layer1_module():
    # The archived runner imports ProfileLoader -> jsonschema at module import time,
    # but this eval only reuses its scoring helpers and mappings. Provide a tiny
    # shim so the import works in lightweight local environments.
    if "jsonschema" not in sys.modules:
        jsonschema_stub = types.ModuleType("jsonschema")
        jsonschema_stub.validate = lambda instance, schema: True  # type: ignore[attr-defined]
        sys.modules["jsonschema"] = jsonschema_stub

    module_path = EVALS_DIR / "archive" / "run_layer1_eval.py"
    spec = importlib.util.spec_from_file_location("evals_archive_run_layer1_eval", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load layer1 helper module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAYER1 = _load_layer1_module()
ModelRunner = LAYER1.ModelRunner
FILTER_CRITERIA = LAYER1.FILTER_CRITERIA
CONDITION_TO_MODEL_KEY = dict(LAYER1.CONDITION_TO_MODEL_KEY)
MODEL_KEY_TO_CONDITION = dict(LAYER1.MODEL_KEY_TO_CONDITION)
BUILD_RAW_INPUTS_FROM_NHANES = LAYER1._build_raw_inputs_from_nhanes


def load_profiles(path: Path) -> list[dict[str, Any]]:
    profiles = json.loads(path.read_text(encoding="utf-8"))
    filtered: list[dict[str, Any]] = []
    for profile in profiles:
        expected = profile.get("ground_truth", {}).get("expected_conditions", [])
        filtered_conditions = [item for item in expected if item.get("condition_id") in EVAL_CONDITIONS_12]
        profile["ground_truth"]["expected_conditions"] = filtered_conditions
        if profile.get("target_condition") == "vitamin_b12_deficiency":
            continue
        filtered.append(profile)
    return filtered


def expected_condition_ids(profile: dict[str, Any]) -> list[str]:
    expected = profile.get("ground_truth", {}).get("expected_conditions", [])
    return [item["condition_id"] for item in expected if item.get("condition_id") in EVAL_CONDITIONS_12]


def sample_profiles(profiles: list[dict[str, Any]], config: EvalConfig) -> list[dict[str, Any]]:
    rng = random.Random(config.seed)
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    healthy_pool = [p for p in profiles if p.get("profile_type") == "healthy"]
    selected.extend(rng.sample(healthy_pool, min(config.healthy_n, len(healthy_pool))))
    used_ids.update(p["profile_id"] for p in selected)

    for condition_id in EVAL_CONDITIONS_12:
        cond_pool = [p for p in profiles if p.get("target_condition") == condition_id and p["profile_id"] not in used_ids]
        multi_pool = [p for p in cond_pool if p.get("profile_type") == "multi"]
        positive_pool = [p for p in cond_pool if p.get("profile_type") == "positive"]

        chosen_multi = rng.sample(multi_pool, min(config.multi_per_condition, len(multi_pool)))
        remaining = max(config.sample_per_condition - len(chosen_multi), 0)
        chosen_positive = rng.sample(positive_pool, min(remaining, len(positive_pool)))

        chosen_ids = {p["profile_id"] for p in chosen_multi + chosen_positive}
        fallback_pool = [p for p in cond_pool if p["profile_id"] not in chosen_ids]
        fallback_n = max(config.sample_per_condition - len(chosen_multi) - len(chosen_positive), 0)
        chosen_fallback = rng.sample(fallback_pool, min(fallback_n, len(fallback_pool)))

        picked = chosen_multi + chosen_positive + chosen_fallback
        selected.extend(picked)
        used_ids.update(p["profile_id"] for p in picked)

    rng.shuffle(selected)
    return selected


def build_quiz_answers(profile: dict[str, Any]) -> dict[str, Any]:
    answers = BUILD_RAW_INPUTS_FROM_NHANES(profile)
    return {key: value for key, value in answers.items() if value is not None}


def compute_model_scores(profile: dict[str, Any], runner: Any) -> dict[str, float]:
    raw_inputs = BUILD_RAW_INPUTS_FROM_NHANES(profile)
    patient_context = {
        "gender": "Female" if float(raw_inputs.get("gender", 2.0)) == 2.0 else "Male",
        "age_years": raw_inputs.get("age_years"),
        "rhq031_regular_periods_raw": raw_inputs.get("rhq031___had_regular_periods_in_past_12_months"),
        "raw_bmi": raw_inputs.get("bmi"),
        "raw_fasting_glucose": raw_inputs.get("fasting_glucose_mg_dl"),
    }
    feature_vectors = runner._get_normalizer().build_feature_vectors(raw_inputs)
    scores = runner.run_all_with_context(feature_vectors, patient_context)
    normalized: dict[str, float] = {}
    for model_key, score in scores.items():
        condition_id = MODEL_KEY_TO_CONDITION.get(model_key)
        if condition_id not in EVAL_CONDITIONS_12:
            continue
        normalized[condition_id] = float(score)
    return dict(sorted(normalized.items(), key=lambda item: item[1], reverse=True))


def top3_from_scores(scores: dict[str, float]) -> list[str]:
    return [condition_id for condition_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]]


def flagged_from_scores(scores: dict[str, float]) -> list[str]:
    flagged: list[str] = []
    for condition_id, score in scores.items():
        model_key = CONDITION_TO_MODEL_KEY.get(condition_id)
        if model_key is None:
            continue
        threshold = FILTER_CRITERIA.get(model_key, 0.40)
        if score >= threshold:
            flagged.append(condition_id)
    return flagged


def top5_scores(scores: dict[str, float]) -> dict[str, float]:
    return dict(list(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:5]))


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status_code = response.getcode()
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = raw
    return status_code, parsed


def extract_supported_ids(response: dict[str, Any]) -> list[str]:
    insights = response.get("insights", [])
    if not isinstance(insights, list):
        return []
    ids: list[str] = []
    for item in insights:
        if isinstance(item, dict):
            diagnosis_id = item.get("diagnosisId")
            if isinstance(diagnosis_id, str):
                normalized_id = LEGACY_TO_EVAL_CONDITION.get(diagnosis_id, diagnosis_id)
                if normalized_id in EVAL_CONDITIONS_12:
                    ids.append(normalized_id)
    return list(dict.fromkeys(ids))


def build_medgemma_only_payload(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "answers": build_quiz_answers(profile),
        "clarificationQA": [],
        "confirmedConditions": [],
        "useKNN": False,
        "evalMode": "medgemma_only",
        "evalCandidateConditions": EVAL_CONDITIONS_12,
    }


def build_hybrid_payload(profile: dict[str, Any], scores_top5: dict[str, float]) -> dict[str, Any]:
    return {
        "answers": build_quiz_answers(profile),
        "mlScores": scores_top5,
        "rawMlScores": scores_top5,
        "clarificationQA": [],
        "confirmedConditions": [],
        "useKNN": False,
    }


def evaluate_models_only(profile: dict[str, Any], score_map: dict[str, float]) -> dict[str, Any]:
    return {
        "parse_success": True,
        "top3_predictions": top3_from_scores(score_map),
        "flagged_conditions": flagged_from_scores(score_map),
        "response": None,
        "http_status": None,
        "error": None,
    }


def evaluate_deep_analyze_arm(
    profile: dict[str, Any],
    payload: dict[str, Any],
    config: EvalConfig,
) -> dict[str, Any]:
    if config.dry_run:
        return {
            "parse_success": False,
            "top3_predictions": [],
            "flagged_conditions": [],
            "response": None,
            "http_status": None,
            "error": "dry_run",
        }

    try:
        status_code, parsed = post_json(f"{config.base_url}/api/deep-analyze", payload, config.timeout)
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        return {
            "parse_success": False,
            "top3_predictions": [],
            "flagged_conditions": [],
            "response": None,
            "http_status": None,
            "error": str(exc),
        }

    if status_code != 200 or not isinstance(parsed, dict):
        return {
            "parse_success": False,
            "top3_predictions": [],
            "flagged_conditions": [],
            "response": parsed,
            "http_status": status_code,
            "error": f"HTTP {status_code}",
        }

    top3_predictions = extract_supported_ids(parsed)[:3]
    return {
        "parse_success": True,
        "top3_predictions": top3_predictions,
        "flagged_conditions": top3_predictions,
        "response": parsed,
        "http_status": status_code,
        "error": None,
    }


def make_base_record(profile: dict[str, Any], model_scores: dict[str, float]) -> dict[str, Any]:
    return {
        "profile_id": profile["profile_id"],
        "profile_type": profile.get("profile_type"),
        "target_condition": profile.get("target_condition"),
        "expected_conditions": expected_condition_ids(profile),
        "model_scores_all12": model_scores,
        "model_top5": top5_scores(model_scores),
    }


def score_arm_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [r for r in records if r.get("expected_conditions")]
    healthy = [r for r in records if r.get("profile_type") == "healthy"]
    parse_successes = sum(1 for r in records if r.get("parse_success"))
    recall_hits = sum(
        1 for r in labeled
        if set(r.get("expected_conditions", [])) & set(r.get("top3_predictions", []))
    )
    recall_at_3 = recall_hits / len(labeled) if labeled else 0.0

    healthy_over_alerts = sum(1 for r in healthy if r.get("flagged_conditions"))
    healthy_over_alert_rate = healthy_over_alerts / len(healthy) if healthy else 0.0

    per_condition: dict[str, dict[str, Any]] = {}
    false_positive_rates: dict[str, float] = {}
    neighbour_fp_rates: dict[str, float] = {}

    for condition_id in EVAL_CONDITIONS_12:
        positives = [r for r in records if condition_id in r.get("expected_conditions", [])]
        positives_hit = sum(1 for r in positives if condition_id in r.get("top3_predictions", []))

        absent = [r for r in records if condition_id not in r.get("expected_conditions", [])]
        absent_fp = sum(1 for r in absent if condition_id in r.get("top3_predictions", []))
        false_positive_rate = absent_fp / len(absent) if absent else 0.0

        neighbour_pool = [
            r for r in records
            if r.get("expected_conditions")
            and condition_id not in r.get("expected_conditions", [])
            and any(neighbour in r.get("expected_conditions", []) for neighbour in ABSENT_NEIGHBOUR_MAP.get(condition_id, []))
        ]
        neighbour_fp = sum(1 for r in neighbour_pool if condition_id in r.get("top3_predictions", []))
        neighbour_fp_rate = neighbour_fp / len(neighbour_pool) if neighbour_pool else 0.0

        per_condition[condition_id] = {
            "n_positive_profiles": len(positives),
            "recall_at_3": round(positives_hit / len(positives), 4) if positives else None,
            "false_positive_rate_absent": round(false_positive_rate, 4),
            "neighbour_false_positive_rate": round(neighbour_fp_rate, 4),
        }
        false_positive_rates[condition_id] = false_positive_rate
        neighbour_fp_rates[condition_id] = neighbour_fp_rate

    return {
        "n_profiles": len(records),
        "n_labeled": len(labeled),
        "n_healthy": len(healthy),
        "parse_success_rate": round(parse_successes / len(records), 4) if records else 0.0,
        "recall_at_3": round(recall_at_3, 4),
        "healthy_over_alert_rate": round(healthy_over_alert_rate, 4),
        "mean_false_positive_rate_absent": round(sum(false_positive_rates.values()) / len(false_positive_rates), 4),
        "mean_neighbour_false_positive_rate": round(sum(neighbour_fp_rates.values()) / len(neighbour_fp_rates), 4),
        "per_condition": per_condition,
    }


def derive_recommendations(summary: dict[str, Any]) -> dict[str, dict[str, str]]:
    hybrid = summary["arms"]["hybrid_top5"]
    medgemma = summary["arms"]["medgemma_only"]
    models = summary["arms"]["models_only"]

    recommendations: dict[str, dict[str, str]] = {}
    for condition_id in EVAL_CONDITIONS_12:
        hybrid_stats = hybrid["per_condition"][condition_id]
        medgemma_stats = medgemma["per_condition"][condition_id]
        model_stats = models["per_condition"][condition_id]

        hybrid_recall = hybrid_stats["recall_at_3"] or 0.0
        medgemma_recall = medgemma_stats["recall_at_3"] or 0.0
        model_recall = model_stats["recall_at_3"] or 0.0

        hybrid_guardrail = hybrid_stats["neighbour_false_positive_rate"]
        medgemma_guardrail = medgemma_stats["neighbour_false_positive_rate"]

        if hybrid_recall >= medgemma_recall + 0.08 and hybrid_guardrail <= medgemma_guardrail + 0.05:
            recommendation = "keep"
            reason = "Hybrid adds clear recall@3 lift without a large neighbour-FP penalty."
        elif hybrid_recall < medgemma_recall and model_recall < medgemma_recall:
            recommendation = "skip_candidate"
            reason = "MedGemma-only already performs better and the condition model does not recover the gap."
        else:
            recommendation = "maybe"
            reason = "Signal is mixed; inspect examples before changing the pipeline."

        recommendations[condition_id] = {
            "recommendation": recommendation,
            "reason": reason,
        }
    return recommendations


def build_markdown(run_id: str, config: EvalConfig, sample_profiles_list: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Quiz-Only Three-Arm Eval - {run_id}")
    lines.append("")
    lines.append(f"- Cohort: `{config.profiles_path}`")
    lines.append(f"- Sample size: `{len(sample_profiles_list)}`")
    lines.append(f"- Sampling: `{config.sample_per_condition}` per condition, up to `{config.multi_per_condition}` multi-condition cases per target, `{config.healthy_n}` healthy")
    lines.append(f"- API base URL: `{config.base_url}`")
    lines.append("")
    lines.append("## Arm Summary")
    lines.append("")
    lines.append("| Arm | Recall@3 | Healthy over-alert | Mean absent FP | Mean neighbour FP | Parse success |")
    lines.append("|-----|-----------|--------------------|----------------|-------------------|---------------|")
    for arm_name in ("models_only", "medgemma_only", "hybrid_top5"):
        arm = summary["arms"][arm_name]
        lines.append(
            f"| {arm_name} | {arm['recall_at_3']:.1%} | {arm['healthy_over_alert_rate']:.1%} | "
            f"{arm['mean_false_positive_rate_absent']:.1%} | {arm['mean_neighbour_false_positive_rate']:.1%} | "
            f"{arm['parse_success_rate']:.1%} |"
        )
    lines.append("")
    lines.append("## Per-Condition Recommendation")
    lines.append("")
    lines.append("| Condition | Models recall@3 | MedGemma recall@3 | Hybrid recall@3 | Hybrid neighbour FP | Recommendation |")
    lines.append("|-----------|------------------|-------------------|-----------------|---------------------|----------------|")
    for condition_id in EVAL_CONDITIONS_12:
        model_recall = summary["arms"]["models_only"]["per_condition"][condition_id]["recall_at_3"] or 0.0
        med_recall = summary["arms"]["medgemma_only"]["per_condition"][condition_id]["recall_at_3"] or 0.0
        hybrid_stats = summary["arms"]["hybrid_top5"]["per_condition"][condition_id]
        hybrid_recall = hybrid_stats["recall_at_3"] or 0.0
        recommendation = summary["recommendations"][condition_id]["recommendation"]
        lines.append(
            f"| {condition_id} | {model_recall:.1%} | {med_recall:.1%} | {hybrid_recall:.1%} | "
            f"{hybrid_stats['neighbour_false_positive_rate']:.1%} | {recommendation} |"
        )
    lines.append("")
    lines.append("## Sample Mix")
    lines.append("")
    lines.append("| Profile type | Count |")
    lines.append("|--------------|-------|")
    for profile_type, count in sorted(Counter(p.get('profile_type') for p in sample_profiles_list).items()):
        lines.append(f"| {profile_type} | {count} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `MedGemma-only` uses the live `/api/deep-analyze` path with quiz answers only and an eval-specific prompt mode that withholds ML scores.")
    lines.append("- `Hybrid` passes only the top-5 model scores to the same route.")
    lines.append("- `healthy over-alert` counts any surfaced diagnosis on healthy profiles.")
    lines.append("- `neighbour false positive` measures how often a condition appears on clinically adjacent profiles where it is absent.")
    return "\n".join(lines)


def main() -> int:
    config = parse_args()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.reports_dir.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles(config.profiles_path)
    sampled = sample_profiles(profiles, config)
    runner = ModelRunner(max_workers=1)

    arm_records: dict[str, list[dict[str, Any]]] = {
        "models_only": [],
        "medgemma_only": [],
        "hybrid_top5": [],
    }

    total_profiles = len(sampled)
    for index, profile in enumerate(sampled, start=1):
        print(f"[{index}/{total_profiles}] {profile['profile_id']} ({profile.get('target_condition') or profile.get('profile_type')})")
        model_scores = compute_model_scores(profile, runner)
        base = make_base_record(profile, model_scores)

        model_record = dict(base)
        model_record.update(evaluate_models_only(profile, model_scores))
        arm_records["models_only"].append(model_record)

        med_record = dict(base)
        med_record.update(evaluate_deep_analyze_arm(profile, build_medgemma_only_payload(profile), config))
        arm_records["medgemma_only"].append(med_record)

        hybrid_record = dict(base)
        hybrid_record.update(evaluate_deep_analyze_arm(profile, build_hybrid_payload(profile, top5_scores(model_scores)), config))
        arm_records["hybrid_top5"].append(hybrid_record)

    run_id = datetime.utcnow().strftime("quiz_three_arm_%Y%m%d_%H%M%S")
    summary = {
        "run_id": run_id,
        "conditions": EVAL_CONDITIONS_12,
        "sample_size": len(sampled),
        "arms": {arm_name: score_arm_records(records) for arm_name, records in arm_records.items()},
    }
    summary["recommendations"] = derive_recommendations(summary)

    payload = {
        "summary": summary,
        "sample_profile_ids": [profile["profile_id"] for profile in sampled],
        "results_by_arm": arm_records,
    }

    results_path = config.output_dir / f"{run_id}.json"
    report_path = config.reports_dir / f"{run_id}.md"
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(build_markdown(run_id, config, sampled, summary), encoding="utf-8")

    print(f"Saved JSON results: {results_path}")
    print(f"Saved Markdown report: {report_path}")
    for arm_name, arm_summary in summary["arms"].items():
        print(
            f"{arm_name}: recall@3={arm_summary['recall_at_3']:.1%}, "
            f"healthy_over_alert={arm_summary['healthy_over_alert_rate']:.1%}, "
            f"neighbour_fp={arm_summary['mean_neighbour_false_positive_rate']:.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
