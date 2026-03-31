#!/usr/bin/env python3
"""
Canonical exporter for Layer 1 benchmark metrics used by slides / UI.

This module converts the verbose layer1 eval JSON into one normalized structure
with explicit metric names and definitions so downstream consumers stop
re-deriving incompatible tables from markdown or partial JSON fields.
"""
from __future__ import annotations

from typing import Any


EXPORT_SCHEMA_VERSION = "2026-03-31.layer1.v1"


HEADLINE_DEFINITIONS: dict[str, dict[str, str]] = {
    "top1_accuracy_all": {
        "label": "Top-1 Accuracy",
        "scope": "all_scored_profiles",
        "definition": "Fraction of scored profiles where the top-ranked model matches the ground-truth primary condition.",
    },
    "top1_accuracy_positives_only": {
        "label": "Top-1 Accuracy (positives only)",
        "scope": "positive_profiles_only",
        "definition": "Fraction of positive profiles where the top-ranked model matches the ground-truth primary condition.",
    },
    "top3_coverage_all": {
        "label": "Top-3 Coverage",
        "scope": "all_scored_profiles",
        "definition": "Fraction of scored profiles where the ground-truth primary condition appears in the top 3 ranked models.",
    },
    "over_alert_rate_healthy": {
        "label": "Over-Alert Rate",
        "scope": "healthy_profiles_only",
        "definition": "Fraction of healthy profiles with at least one condition score at or above that condition's user-facing surfacing threshold.",
    },
}


def _headline_row(metric_id: str, value: float) -> dict[str, Any]:
    meta = HEADLINE_DEFINITIONS[metric_id]
    return {
        "metric_id": metric_id,
        "label": meta["label"],
        "scope": meta["scope"],
        "definition": meta["definition"],
        "value": round(value, 4),
        "display_pct": f"{value:.1%}",
    }


def build_layer1_metrics_export(payload: dict[str, Any]) -> dict[str, Any]:
    run_metadata = payload.get("run_metadata") or payload.get("report", {}).get("run_metadata") or {}
    report = payload["report"]
    per_condition = report.get("per_condition", {})
    healthy_per_condition = report.get("healthy_per_condition", {})
    registry = run_metadata.get("model_registry", {})

    headline_metrics = [
        _headline_row("top1_accuracy_all", report.get("top1_accuracy", 0.0)),
        _headline_row("top1_accuracy_positives_only", report.get("positives_top1_accuracy", 0.0)),
        _headline_row("top3_coverage_all", report.get("top3_coverage", 0.0)),
        _headline_row("over_alert_rate_healthy", report.get("over_alert_rate", 0.0)),
    ]

    per_condition_rows: list[dict[str, Any]] = []
    for condition in sorted(per_condition):
        row = per_condition[condition]
        healthy = healthy_per_condition.get(condition, {})
        model_key = row.get("model_key")
        registry_meta = registry.get(model_key, {})

        per_condition_rows.append({
            "condition": condition,
            "model_key": model_key,
            "artifact": row.get("artifact") or registry_meta.get("artifact"),
            "metadata_version": row.get("metadata_version") or registry_meta.get("metadata_version"),
            "metadata_file": registry_meta.get("metadata_file"),
            "metadata_created_at": registry_meta.get("metadata_created_at"),
            "threshold": row.get("threshold"),
            "recommended_threshold": registry_meta.get("recommended_threshold"),
            "user_facing_threshold": registry_meta.get("user_facing_threshold", row.get("threshold")),
            "n_positive_target": row.get("n_positive_target"),
            "n_flagged": row.get("n_flagged"),
            "n_true_positive": row.get("n_true_positive"),
            "recall": row.get("recall"),
            "precision": row.get("precision"),
            "flag_rate": row.get("flag_rate"),
            "healthy_flag_rate": healthy.get("healthy_flag_rate"),
            "n_healthy_flagged": healthy.get("n_healthy_flagged"),
            "mean_target_score": row.get("mean_target_score"),
        })

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "source_type": "layer1_eval",
        "run_id": run_metadata.get("run_id") or report.get("run_id"),
        "git_sha": run_metadata.get("git_sha"),
        "profiles_path": run_metadata.get("profiles_path"),
        "headline_metrics": headline_metrics,
        "per_condition_table": per_condition_rows,
    }
