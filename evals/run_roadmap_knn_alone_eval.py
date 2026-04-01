#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
COHORT_PATH = ROOT / "evals" / "cohort" / "nhanes_balanced_800.json"
REPORTS_DIR = ROOT / "evals" / "reports"
RESULTS_DIR = ROOT / "evals" / "results"

sys.path.insert(0, str(ROOT))

from scripts.roadmap_knn_scorer import RoadmapKNNScorer

CONDITIONS = [
    "hepatitis",
    "perimenopause",
    "anemia",
    "iron_deficiency",
    "kidney_disease",
    "hypothyroidism",
    "liver",
    "sleep_disorder",
    "hidden_inflammation",
    "electrolyte_imbalance",
    "prediabetes",
    "vitamin_d_deficiency",
]


def parse_expected(ground_truth: dict) -> tuple[set[str], str | None]:
    expected = set()
    primary = None
    for item in ground_truth.get("expected_conditions") or []:
        if isinstance(item, str):
            expected.add(item)
        elif isinstance(item, dict):
            condition_id = item.get("condition_id")
            if not condition_id:
                continue
            expected.add(condition_id)
            if item.get("is_primary") and primary is None:
                primary = condition_id
    return expected, primary


def to_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def main() -> int:
    profiles = json.loads(COHORT_PATH.read_text())
    knn = RoadmapKNNScorer()
    rows = []

    for profile in profiles:
        result = knn.score(profile.get("nhanes_inputs", {}))
        score_map = {condition: 0.0 for condition in CONDITIONS}
        for row in result.get("disease_scores", []):
            condition = row["condition"]
            if condition in score_map:
                score_map[condition] = float(row["weighted_neighbor_fraction"])

        ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
        top3 = [condition for condition, _ in ranked[:3]]
        top1 = ranked[0][0] if ranked else None
        expected, primary = parse_expected(profile["ground_truth"])

        rows.append(
            {
                "profile_id": profile["profile_id"],
                "expected": sorted(expected),
                "primary": primary,
                "profile_type": profile.get("profile_type"),
                "top1": top1,
                "top3": top3,
                "score_map": score_map,
            }
        )

    n_profiles = len(rows)
    primary_rows = [row for row in rows if row["primary"]]
    healthy_rows = [row for row in rows if row["profile_type"] == "healthy"]

    headline = {
        "n_profiles": n_profiles,
        "top3_any_true": sum(bool(set(row["expected"]).intersection(row["top3"])) for row in rows) / n_profiles,
        "top1_primary_accuracy": sum(row["top1"] == row["primary"] for row in primary_rows) / len(primary_rows),
        "top3_primary_coverage": sum(row["primary"] in row["top3"] for row in primary_rows) / len(primary_rows),
        "healthy_over_alert": sum(any(row["score_map"][condition] > 0 for condition in row["top3"]) for row in healthy_rows)
        / len(healthy_rows),
    }

    per_condition = {}
    for condition in CONDITIONS:
        positives = [row for row in rows if condition in row["expected"]]
        negatives = [row for row in rows if condition not in row["expected"]]
        per_condition[condition] = {
            "n_positive": len(positives),
            "recall_at_3": sum(condition in row["top3"] for row in positives) / len(positives) if positives else None,
            "recall_at_1": sum(condition == row["top1"] for row in positives) / len(positives) if positives else None,
            "absent_fp_at_3": sum(condition in row["top3"] for row in negatives) / len(negatives) if negatives else None,
            "mean_score_positive": mean([row["score_map"][condition] for row in positives]) if positives else None,
            "mean_score_negative": mean([row["score_map"][condition] for row in negatives]) if negatives else None,
        }

    run_id = f"roadmap_knn_alone_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    results_path = RESULTS_DIR / f"{run_id}.json"
    report_path = REPORTS_DIR / f"{run_id}.md"
    results_path.write_text(json.dumps({"run_id": run_id, "headline": headline, "per_condition": per_condition}, indent=2))

    lines = [
        f"# Roadmap KNN Alone Eval — {run_id}",
        "",
        f"- Cohort: `{COHORT_PATH.relative_to(ROOT)}`",
        f"- Profiles evaluated: `{n_profiles}`",
        "",
        "## Headline",
        "",
        "| Metric | Roadmap KNN alone |",
        "|--------|-------------------|",
        f"| Top-3 contains any true condition | {to_pct(headline['top3_any_true'])} |",
        f"| Top-1 primary accuracy | {to_pct(headline['top1_primary_accuracy'])} |",
        f"| Top-3 primary coverage | {to_pct(headline['top3_primary_coverage'])} |",
        f"| Healthy over-alert rate | {to_pct(headline['healthy_over_alert'])} |",
        "",
        "## Per Disease",
        "",
        "| Condition | N+ | Recall@3 | Recall@1 | Absent FP@3 | Mean score (pos) | Mean score (neg) |",
        "|-----------|----|----------|----------|--------------|------------------|------------------|",
    ]
    for condition in CONDITIONS:
        stats = per_condition[condition]
        pos_mean = "—" if stats["mean_score_positive"] is None else f"{stats['mean_score_positive']:.3f}"
        neg_mean = "—" if stats["mean_score_negative"] is None else f"{stats['mean_score_negative']:.3f}"
        lines.append(
            f"| {condition} | {stats['n_positive']} | {to_pct(stats['recall_at_3'])} | {to_pct(stats['recall_at_1'])} | "
            f"{to_pct(stats['absent_fp_at_3'])} | {pos_mean} | {neg_mean} |"
        )
    report_path.write_text("\n".join(lines) + "\n")

    print(results_path)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
