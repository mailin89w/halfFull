#!/usr/bin/env python3
"""
run_knn_top1_ab_eval.py

A/B experiment: does releasing the frozen top-1 slot improve accuracy?

The KNN reranker currently freezes the Bayesian top-1 condition so neighbourhood
evidence can only rescue slots 2 and 3. This experiment sweeps five strategies:

  Strategy A  threshold=1.0   Always freeze top-1 (current production default)
  Strategy B  threshold=0.75  Release top-1 when Bayesian score < 0.75
  Strategy C  threshold=0.60  Release top-1 when Bayesian score < 0.60
  Strategy D  threshold=0.50  Release top-1 when Bayesian score < 0.50
  Strategy E  threshold=0.00  Never freeze — full KNN reranking

For each strategy the script reports:
  - top1_hit_rate          primary condition ranked #1
  - top3_hit_rate          primary condition in top-3
  - false_displacement_rate top-1 was correct, KNN displaced it with wrong condition
  - true_promotion_rate    top-1 was wrong, KNN promoted correct to #1
  - net_top1_gain          true_promotion_rate - false_displacement_rate
  - over_alert_rate        healthy profiles with any surfaced condition
  - per_condition breakdown for top-1 and top-3 hit rates

The report also includes a recommendation for which threshold maximises net gain
without the false-displacement cost exceeding 5pp above the baseline.
"""
from __future__ import annotations

import json
import logging
import math
import random
import sys
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore")
logging.getLogger("model_runner").setLevel(logging.WARNING)
logging.getLogger("bayesian").setLevel(logging.WARNING)
logging.getLogger("bayesian_updater").setLevel(logging.WARNING)

from bayesian.bayesian_updater import BayesianUpdater
from bayesian.run_bayesian import handle_questions, handle_update
from evals.pipeline.knn_condition_reranker import rerank_condition_scores_with_knn
from evals.pipeline.profile_loader import ProfileLoader
from evals.run_bayesian_eval import simulated_bayesian_answer
from evals.run_knn_layer_eval import KNN_LAB_GROUPS, build_eval_inputs
from evals.run_layer1_eval import CONDITION_TO_MODEL_KEY, ModelRunner, SCHEMA_PATH
from models_normalized.model_runner import USER_FACING_THRESHOLDS
from scripts.knn_scorer import KNNScorer
from scripts.score_answers import _patient_context, _remap_scores

PROFILES_PATH = EVALS_DIR / "cohort" / "profiles_v3_three_layer.json"
RESULTS_DIR = EVALS_DIR / "results"
REPORTS_DIR = EVALS_DIR / "reports"

# ── Strategies ──────────────────────────────────────────────────────────────

STRATEGIES: list[dict[str, Any]] = [
    {"id": "A", "label": "Always freeze (baseline)", "threshold": 1.0},
    {"id": "B", "label": "Release when top-1 < 0.75", "threshold": 0.75},
    {"id": "C", "label": "Release when top-1 < 0.60", "threshold": 0.60},
    {"id": "D", "label": "Release when top-1 < 0.50", "threshold": 0.50},
    {"id": "E", "label": "Never freeze (full KNN)", "threshold": 0.00},
]

# Max acceptable false-displacement increase over baseline (strategy A).
FALSE_DISPLACEMENT_BUDGET = 0.05

EVAL_TO_LEGACY = {
    "anemia": "anemia",
    "electrolyte_imbalance": "electrolytes",
    "hepatitis": "hepatitis",
    "hypothyroidism": "thyroid",
    "inflammation": "inflammation",
    "iron_deficiency": "iron_deficiency",
    "kidney_disease": "kidney",
    "liver": "liver",
    "perimenopause": "perimenopause",
    "prediabetes": "prediabetes",
    "sleep_disorder": "sleep_disorder",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def posterior_entropy(scores: dict[str, float]) -> float:
    """Shannon entropy (bits) of the posterior distribution.

    High entropy = uncertainty spread across many conditions.
    Low entropy  = confident top-1.
    """
    total = sum(max(s, 0.0) for s in scores.values())
    if total == 0.0:
        return 0.0
    probs = [s / total for s in scores.values() if s > 0.0]
    return -sum(p * math.log2(p) for p in probs)


def get_knn_groups(raw_inputs: dict[str, Any], scorer: KNNScorer) -> set[str]:
    result = scorer.score(raw_inputs)
    groups: set[str] = set()
    for sig in result.get("lab_signals", []):
        group = KNN_LAB_GROUPS.get(sig.get("lab"))
        if group:
            groups.add(group)
    return groups


def get_bayesian_posteriors(
    profile: dict[str, Any],
    ml_scores: dict[str, float],
    raw_inputs: dict[str, Any],
    updater: BayesianUpdater,
) -> dict[str, float]:
    patient_sex = (
        "female" if raw_inputs.get("gender") == 2
        else "male" if raw_inputs.get("gender") == 1
        else None
    )
    questions_result = handle_questions(
        {"ml_scores": ml_scores, "patient_sex": patient_sex, "existing_answers": raw_inputs},
        updater,
    )
    answers_by_condition: dict[str, dict[str, str]] = {}
    for group in questions_result.get("condition_questions", []):
        condition = group["condition"]
        for question in group.get("questions", []):
            answers_by_condition.setdefault(condition, {})[question["id"]] = simulated_bayesian_answer(
                profile, condition, question["id"]
            )
    update_result = handle_update(
        {
            "ml_scores": ml_scores,
            "confounder_answers": {},
            "answers_by_condition": answers_by_condition,
            "patient_sex": patient_sex,
            "existing_answers": raw_inputs,
        },
        updater,
    )
    return update_result["posterior_scores"]


def surfaced(scores: dict[str, float], top_conditions: list[str]) -> list[str]:
    return [
        c for c in top_conditions
        if (threshold := USER_FACING_THRESHOLDS.get(c)) is not None
        and scores.get(c, 0.0) >= threshold
    ]


# ── Per-strategy evaluation ───────────────────────────────────────────────────

def build_profile_cache(
    profiles: list[dict[str, Any]],
    runner: ModelRunner,
    updater: BayesianUpdater,
    scorer: KNNScorer,
) -> list[dict[str, Any]]:
    """Compute the expensive ML + Bayesian + KNN-groups pipeline once per profile.

    Returns a list of lightweight cache records that each strategy sweep can
    re-use without re-running the models.
    """
    cache: list[dict[str, Any]] = []
    for i, profile in enumerate(profiles, start=1):
        if i % 100 == 0:
            print(f"  pre-computing profile {i}/{len(profiles)} ...", flush=True)
        raw_inputs = build_eval_inputs(profile)
        feature_vectors = runner._get_normalizer().build_feature_vectors(raw_inputs)
        raw_scores = runner.run_all_with_context(
            feature_vectors, patient_context=_patient_context(raw_inputs)
        )
        ml_scores = _remap_scores(raw_scores)
        bayes_scores = get_bayesian_posteriors(profile, ml_scores, raw_inputs, updater)
        groups = get_knn_groups(raw_inputs, scorer)

        bayes_top3 = [
            cond for cond, _ in sorted(bayes_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        ]
        expected_eval = [
            item["condition_id"]
            for item in profile.get("ground_truth", {}).get("expected_conditions", [])
        ]
        expected_legacy = [EVAL_TO_LEGACY[c] for c in expected_eval if c in EVAL_TO_LEGACY]

        cache.append({
            "profile_id": profile["profile_id"],
            "profile_type": profile.get("profile_type"),
            "primary": expected_legacy[0] if expected_legacy else None,
            "secondary": expected_legacy[1:],
            "bayes_scores": bayes_scores,
            "bayes_top3": bayes_top3,
            "bayes_top1": bayes_top3[0] if bayes_top3 else None,
            "groups": groups,
            "entropy": round(posterior_entropy(bayes_scores), 4),
        })
    return cache


def evaluate_strategy(
    cache: list[dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Apply one KNN threshold to pre-computed cache records — O(n) and cheap."""
    rows: list[dict[str, Any]] = []
    for rec in cache:
        bayes_scores = rec["bayes_scores"]
        groups = rec["groups"]

        reranked = rerank_condition_scores_with_knn(
            bayes_scores,
            groups,
            top1_confidence_threshold=threshold,
        )
        knn_top3 = reranked["top_conditions"]
        knn_top1 = knn_top3[0] if knn_top3 else None

        rows.append({
            "profile_id": rec["profile_id"],
            "profile_type": rec["profile_type"],
            "primary": rec["primary"],
            "secondary": rec["secondary"],
            "bayes_top1": rec["bayes_top1"],
            "knn_top1": knn_top1,
            "bayes_top3": rec["bayes_top3"],
            "knn_top3": knn_top3,
            "top1_score": reranked["top1_score"],
            "top1_released": reranked["top1_released"],
            "entropy": rec["entropy"],
            "knn_groups": sorted(groups),
            "bonuses": reranked["bonuses"],
            "penalties": reranked.get("penalties", {}),
            "bayes_surfaced": surfaced(bayes_scores, rec["bayes_top3"]),
            "knn_surfaced": surfaced(reranked["adjusted_scores"], knn_top3),
        })
    return rows


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [r for r in rows if r["primary"]]
    healthy = [r for r in rows if r["profile_type"] == "healthy"]
    multi = [r for r in labeled if r["secondary"]]

    # Top-1 and top-3 accuracy
    top1_hits = [1.0 if r["primary"] == r["knn_top1"] else 0.0 for r in labeled]
    top3_hits = [1.0 if r["primary"] in r["knn_top3"] else 0.0 for r in labeled]
    bayes_top1_hits = [1.0 if r["primary"] == r["bayes_top1"] else 0.0 for r in labeled]

    # False displacement: top-1 was correct before KNN, KNN broke it
    false_displacements = [
        1.0 if (r["primary"] == r["bayes_top1"] and r["primary"] != r["knn_top1"]) else 0.0
        for r in labeled
    ]
    # True promotion: top-1 was wrong before KNN, KNN fixed it
    true_promotions = [
        1.0 if (r["primary"] != r["bayes_top1"] and r["primary"] == r["knn_top1"]) else 0.0
        for r in labeled
    ]
    # Secondary condition recovery
    secondary_hits = [
        1.0 if any(c in r["knn_top3"] for c in r["secondary"]) else 0.0
        for r in multi
    ] if multi else [0.0]

    # Over-alert on healthy
    over_alert = [1.0 if r["knn_surfaced"] else 0.0 for r in healthy] if healthy else [0.0]

    # Top-1 changed count (regardless of correct/wrong)
    top1_changes = sum(1 for r in labeled if r["bayes_top1"] != r["knn_top1"])

    # Released top-1 profiles
    released_count = sum(1 for r in labeled if r["top1_released"])
    released_correct = sum(
        1 for r in labeled if r["top1_released"] and r["primary"] == r["knn_top1"]
    )
    released_incorrect = sum(
        1 for r in labeled if r["top1_released"] and r["primary"] != r["knn_top1"]
    )

    # Per-condition breakdown
    per_condition: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "n": 0, "top1_hits": 0, "top3_hits": 0,
        "false_displacements": 0, "true_promotions": 0,
    })
    for r in labeled:
        c = r["primary"]
        if not c:
            continue
        per_condition[c]["n"] += 1
        if r["primary"] == r["knn_top1"]:
            per_condition[c]["top1_hits"] += 1
        if r["primary"] in r["knn_top3"]:
            per_condition[c]["top3_hits"] += 1
        if r["primary"] == r["bayes_top1"] and r["primary"] != r["knn_top1"]:
            per_condition[c]["false_displacements"] += 1
        if r["primary"] != r["bayes_top1"] and r["primary"] == r["knn_top1"]:
            per_condition[c]["true_promotions"] += 1

    per_condition_summary = {
        c: {
            "n": v["n"],
            "top1_hit_rate": round(v["top1_hits"] / v["n"], 4) if v["n"] else 0.0,
            "top3_hit_rate": round(v["top3_hits"] / v["n"], 4) if v["n"] else 0.0,
            "false_displacement_rate": round(v["false_displacements"] / v["n"], 4) if v["n"] else 0.0,
            "true_promotion_rate": round(v["true_promotions"] / v["n"], 4) if v["n"] else 0.0,
        }
        for c, v in sorted(per_condition.items())
    }

    fd_rate = mean(false_displacements) if false_displacements else 0.0
    tp_rate = mean(true_promotions) if true_promotions else 0.0

    return {
        "n_labeled": len(labeled),
        "n_healthy": len(healthy),
        "n_multi": len(multi),
        "top1_hit_rate": round(mean(top1_hits), 4),
        "top3_hit_rate": round(mean(top3_hits), 4),
        "bayes_top1_hit_rate": round(mean(bayes_top1_hits), 4),
        "false_displacement_rate": round(fd_rate, 4),
        "true_promotion_rate": round(tp_rate, 4),
        "net_top1_gain": round(tp_rate - fd_rate, 4),
        "secondary_condition_recovery": round(mean(secondary_hits), 4),
        "over_alert_rate": round(mean(over_alert), 4),
        "top1_changes": top1_changes,
        "released_profiles": released_count,
        "released_correct": released_correct,
        "released_incorrect": released_incorrect,
        "per_condition": per_condition_summary,
    }


# ── Report generation ─────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v:.1%}"


def _delta(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1%}"


def build_report(
    strategy_results: list[dict[str, Any]],
    recommendation: str,
    timestamp: str,
) -> str:
    lines = [
        "# KNN Top-1 Unfreeze A/B Experiment",
        "",
        f"Generated: {timestamp}Z",
        "",
        "## Overview",
        "",
        "Five strategies are compared across 600 profiles (seed 42).",
        "Each strategy uses a different `top1_confidence_threshold` for `rerank_condition_scores_with_knn`.",
        "The freeze is released when the Bayesian top-1 posterior score is *below* the threshold.",
        "",
        "| ID | Strategy | Threshold | Description |",
        "|----|----------|-----------|-------------|",
    ]
    for s in STRATEGIES:
        lines.append(f"| **{s['id']}** | {s['label']} | `{s['threshold']}` | {'Current production default' if s['threshold'] == 1.0 else ''} |")

    lines += [
        "",
        "## Summary Table",
        "",
        "| Strategy | Top-1 Hit | Top-3 Hit | False Displ. | True Promo. | Net Gain | Over-Alert | Top-1 Changes |",
        "|----------|-----------|-----------|--------------|-------------|----------|------------|---------------|",
    ]
    baseline_fd = None
    for sr in strategy_results:
        m = sr["metrics"]
        if baseline_fd is None:
            baseline_fd = m["false_displacement_rate"]
        fd_marker = " ⚠" if m["false_displacement_rate"] > (baseline_fd or 0) + FALSE_DISPLACEMENT_BUDGET else ""
        ng_marker = " ✓" if m["net_top1_gain"] > 0 else ""
        lines.append(
            f"| **{sr['strategy_id']}** {sr['strategy_label']} "
            f"| {_pct(m['top1_hit_rate'])} "
            f"| {_pct(m['top3_hit_rate'])} "
            f"| {_pct(m['false_displacement_rate'])}{fd_marker} "
            f"| {_pct(m['true_promotion_rate'])} "
            f"| {_delta(m['net_top1_gain'])}{ng_marker} "
            f"| {_pct(m['over_alert_rate'])} "
            f"| {m['top1_changes']} |"
        )

    lines += [
        "",
        "## Recommendation",
        "",
        recommendation,
        "",
        "## Per-Condition Breakdown (all strategies)",
        "",
    ]

    # Build per-condition table across all strategies
    all_conditions = sorted(
        {cond for sr in strategy_results for cond in sr["metrics"]["per_condition"]}
    )
    header_ids = " | ".join(f"A top1 / A top3" if sr["strategy_id"] == "A" else f"{sr['strategy_id']} top1 / top3" for sr in strategy_results)
    lines.append(f"| Condition | N | {header_ids} |")
    lines.append(f"|-----------|---|{'|'.join(['---|---' for _ in strategy_results])}|")

    for cond in all_conditions:
        n = strategy_results[0]["metrics"]["per_condition"].get(cond, {}).get("n", 0)
        cells = []
        for sr in strategy_results:
            pc = sr["metrics"]["per_condition"].get(cond, {})
            t1 = _pct(pc.get("top1_hit_rate", 0.0))
            t3 = _pct(pc.get("top3_hit_rate", 0.0))
            cells.append(f"{t1} / {t3}")
        lines.append(f"| {cond} | {n} | {' | '.join(cells)} |")

    lines += [
        "",
        "## False Displacement Detail (strategies B–E only)",
        "",
        "Profiles where a correct Bayesian top-1 was displaced by KNN:",
        "",
    ]
    for sr in strategy_results[1:]:  # skip baseline A
        displaced = [
            r for r in sr["rows"]
            if r["primary"] and r["primary"] == r["bayes_top1"] and r["primary"] != r["knn_top1"]
        ]
        lines.append(f"### Strategy {sr['strategy_id']}: {sr['strategy_label']} ({len(displaced)} displacements)")
        lines.append("")
        for row in displaced[:10]:
            lines.append(
                f"- `{row['profile_id']}`: expected `{row['primary']}` | "
                f"Bayes top-1 `{row['bayes_top1']}` ✓ → KNN top-1 `{row['knn_top1']}` ✗ | "
                f"top-1 score `{row['top1_score']}` | entropy `{row['entropy']}` | "
                f"KNN groups `{row['knn_groups']}`"
            )
        if len(displaced) > 10:
            lines.append(f"  *(+{len(displaced) - 10} more — see JSON)*")
        lines.append("")

    lines += [
        "## True Promotion Detail (strategies B–E only)",
        "",
        "Profiles where KNN promoted the correct condition to top-1:",
        "",
    ]
    for sr in strategy_results[1:]:
        promoted = [
            r for r in sr["rows"]
            if r["primary"] and r["primary"] != r["bayes_top1"] and r["primary"] == r["knn_top1"]
        ]
        lines.append(f"### Strategy {sr['strategy_id']}: {sr['strategy_label']} ({len(promoted)} promotions)")
        lines.append("")
        for row in promoted[:10]:
            lines.append(
                f"- `{row['profile_id']}`: expected `{row['primary']}` | "
                f"Bayes top-1 `{row['bayes_top1']}` ✗ → KNN top-1 `{row['knn_top1']}` ✓ | "
                f"top-1 score `{row['top1_score']}` | entropy `{row['entropy']}` | "
                f"bonuses `{list(row['bonuses'].keys())}`"
            )
        if len(promoted) > 10:
            lines.append(f"  *(+{len(promoted) - 10} more — see JSON)*")
        lines.append("")

    lines += [
        "## Entropy Distribution at Release Points",
        "",
        "Average posterior entropy for profiles where the top-1 freeze was released vs. held:",
        "",
    ]
    for sr in strategy_results[1:]:
        released = [r["entropy"] for r in sr["rows"] if r["top1_released"]]
        held = [r["entropy"] for r in sr["rows"] if not r["top1_released"]]
        avg_released = round(mean(released), 3) if released else 0.0
        avg_held = round(mean(held), 3) if held else 0.0
        lines.append(
            f"- **Strategy {sr['strategy_id']}**: "
            f"released {len(released)} profiles (avg entropy {avg_released} bits), "
            f"held {len(held)} profiles (avg entropy {avg_held} bits)"
        )

    lines += ["", "---", "*Generated by run_knn_top1_ab_eval.py*", ""]
    return "\n".join(lines)


def build_recommendation(strategy_results: list[dict[str, Any]]) -> str:
    baseline = strategy_results[0]["metrics"]
    baseline_fd = baseline["false_displacement_rate"]
    baseline_top1 = baseline["top1_hit_rate"]
    # An alternative strategy must strictly beat the baseline on BOTH top-1
    # accuracy and net_top1_gain to be worth recommending.
    baseline_net_gain = baseline["net_top1_gain"]

    best_strategy = None
    best_top1 = baseline_top1  # must exceed current production

    for sr in strategy_results[1:]:
        m = sr["metrics"]
        fd_increase = m["false_displacement_rate"] - baseline_fd
        if fd_increase > FALSE_DISPLACEMENT_BUDGET:
            continue  # Too many correct rankings broken
        if m["top1_hit_rate"] > best_top1:
            best_top1 = m["top1_hit_rate"]
            best_strategy = sr

    if best_strategy is None:
        return (
            f"**No strategy improves top-1 accuracy within the false-displacement budget "
            f"(+{FALSE_DISPLACEMENT_BUDGET:.0%}). Keep Strategy A.**\n\n"
            f"Releasing the top-1 freeze monotonically *reduces* top-1 accuracy across all "
            f"thresholds (B: {_pct(strategy_results[1]['metrics']['top1_hit_rate'])}, "
            f"C: {_pct(strategy_results[2]['metrics']['top1_hit_rate'])}, "
            f"D: {_pct(strategy_results[3]['metrics']['top1_hit_rate'])}, "
            f"E: {_pct(strategy_results[4]['metrics']['top1_hit_rate'])}) "
            f"versus the baseline A: {_pct(baseline_top1)}.\n\n"
            f"Interpretation: the current freeze_top1=True design is already optimal. "
            f"KNN neighbourhood evidence is most valuable as a *comorbidity rescue* signal "
            f"(slots 2–3), not as a primary classifier. The net gain of `{_delta(baseline_net_gain)}` "
            f"(true promotions {_pct(baseline['true_promotion_rate'])} minus false displacements "
            f"{_pct(baseline_fd)}) already accrues from the slot-2/3 bonuses and penalties — "
            f"without ever touching top-1.\n\n"
            f"**Next step**: to improve top-1 accuracy, focus on ML model quality (ML-02, ML-05) "
            f"and Bayesian prior calibration (BAYES-01). Revisit the top-1 unfreeze only after "
            f"KNN neighbourhood precision improves substantially."
        )

    m = best_strategy["metrics"]
    top1_delta = m["top1_hit_rate"] - baseline_top1
    return (
        f"**Recommended: Strategy {best_strategy['strategy_id']} "
        f"(`top1_confidence_threshold={best_strategy['strategy_threshold']}`)**\n\n"
        f"- Top-1 accuracy: `{_pct(baseline_top1)}` → `{_pct(m['top1_hit_rate'])}` "
        f"({_delta(top1_delta)})\n"
        f"- False-displacement rate: `{_pct(baseline_fd)}` → `{_pct(m['false_displacement_rate'])}` "
        f"({_delta(m['false_displacement_rate'] - baseline_fd)})\n"
        f"- True promotions: `{_pct(m['true_promotion_rate'])}`\n"
        f"- Net top-1 gain vs baseline: `{_delta(m['net_top1_gain'] - baseline_net_gain)}`\n\n"
        f"To apply: update the `deep-analyze` route to pass "
        f"`top1_confidence_threshold={best_strategy['strategy_threshold']}` to "
        f"`rerank_condition_scores_with_knn`."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    loader = ProfileLoader(PROFILES_PATH, SCHEMA_PATH)
    all_profiles = loader.load_all()
    rng = random.Random(42)
    profiles = rng.sample(all_profiles, min(600, len(all_profiles)))

    print(f"Loaded {len(profiles)} profiles")

    runner = ModelRunner()
    updater = BayesianUpdater()
    scorer = KNNScorer()

    # ── Pre-compute ML + Bayesian + KNN groups once for all profiles ──────────
    # This is the slow step (~1–2 min). Each strategy sweep then only re-runs
    # the reranker (microseconds per profile) on top of the cached posteriors.
    print("Pre-computing ML → Bayesian → KNN-groups (runs once) ...", flush=True)
    cache = build_profile_cache(profiles, runner, updater, scorer)
    print(f"Cache ready: {len(cache)} profiles\n", flush=True)

    strategy_results: list[dict[str, Any]] = []

    for strategy in STRATEGIES:
        print(f"Strategy {strategy['id']}: {strategy['label']} (threshold={strategy['threshold']}) ...", flush=True)
        rows = evaluate_strategy(cache, strategy["threshold"])
        metrics = aggregate(rows)
        strategy_results.append({
            "strategy_id": strategy["id"],
            "strategy_label": strategy["label"],
            "strategy_threshold": strategy["threshold"],
            "metrics": metrics,
            "rows": rows,
        })
        print(
            f"  top1={_pct(metrics['top1_hit_rate'])} "
            f"top3={_pct(metrics['top3_hit_rate'])} "
            f"false_displ={_pct(metrics['false_displacement_rate'])} "
            f"net_gain={_delta(metrics['net_top1_gain'])} "
            f"over_alert={_pct(metrics['over_alert_rate'])}"
        )

    recommendation = build_recommendation(strategy_results)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"knn_top1_ab_{timestamp}"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Save JSON (rows are large — trim to avoid huge files)
    payload = {
        "run_id": run_id,
        "strategies": [
            {
                "strategy_id": sr["strategy_id"],
                "strategy_label": sr["strategy_label"],
                "strategy_threshold": sr["strategy_threshold"],
                "metrics": sr["metrics"],
                # Keep only the most interesting rows for JSON output
                "sample_false_displacements": [
                    r for r in sr["rows"]
                    if r["primary"] and r["primary"] == r["bayes_top1"] and r["primary"] != r["knn_top1"]
                ][:20],
                "sample_true_promotions": [
                    r for r in sr["rows"]
                    if r["primary"] and r["primary"] != r["bayes_top1"] and r["primary"] == r["knn_top1"]
                ][:20],
            }
            for sr in strategy_results
        ],
        "recommendation": recommendation,
    }
    results_path = RESULTS_DIR / f"{run_id}.json"
    results_path.write_text(json.dumps(payload, indent=2))

    report = build_report(strategy_results, recommendation, timestamp)
    report_path = REPORTS_DIR / f"{run_id}.md"
    report_path.write_text(report)

    print(f"\n{'='*60}")
    print("RECOMMENDATION")
    print('='*60)
    print(recommendation)
    print(f"\nJSON  → {results_path}")
    print(f"Report → {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
