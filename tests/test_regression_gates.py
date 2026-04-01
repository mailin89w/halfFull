import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_RESULTS_DIR = REPO_ROOT / "evals" / "results"
BALANCED_760_PATH = "evals/cohort/nhanes_balanced_760.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_compare_result() -> tuple[Path, dict]:
    path = max(
        EVAL_RESULTS_DIR.glob("ml_vs_bayesian_update_only_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return path, _load_json(path)


def _latest_balanced_layer1_metrics_export() -> tuple[Path, dict]:
    candidates: list[tuple[Path, dict]] = []
    for path in EVAL_RESULTS_DIR.glob("layer1_*_metrics_export.json"):
        data = _load_json(path)
        if data.get("profiles_path") == BALANCED_760_PATH:
            candidates.append((path, data))
    if not candidates:
        raise AssertionError("No balanced-760 layer1 metrics export found.")
    path, data = max(candidates, key=lambda item: item[0].stat().st_mtime)
    return path, data


def _headline_metric(metrics_export: dict, metric_id: str) -> float:
    for row in metrics_export.get("headline_metrics", []):
        if row.get("metric_id") == metric_id:
            return float(row["value"])
    raise AssertionError(f"Missing headline metric: {metric_id}")


def _per_condition_row(metrics_export: dict, condition_id: str) -> dict:
    for row in metrics_export.get("per_condition_table", []):
        if row.get("condition") == condition_id:
            return row
    raise AssertionError(f"Missing per-condition row: {condition_id}")


class RegressionGateTests(unittest.TestCase):
    def test_default_bayes_top3_any_true_does_not_materially_regress(self) -> None:
        path, data = _latest_compare_result()
        value = float(data["arms"]["default_triggered_bayesian"]["top3_contains_any_true_condition"])
        self.assertGreaterEqual(
            value,
            0.59,
            f"{path.name}: default ML+Bayes top3_any_true regressed materially ({value:.4f} < 0.59)",
        )

    def test_default_bayes_healthy_over_alert_does_not_regress(self) -> None:
        path, data = _latest_compare_result()
        value = float(data["arms"]["default_triggered_bayesian"]["healthy_over_alert_rate"])
        self.assertLessEqual(
            value,
            0.18,
            f"{path.name}: default ML+Bayes healthy_over_alert regressed ({value:.4f} > 0.18)",
        )

    def test_ml_layer_healthy_over_alert_stays_under_guardrail(self) -> None:
        path, data = _latest_balanced_layer1_metrics_export()
        value = _headline_metric(data, "over_alert_rate_healthy")
        self.assertLessEqual(
            value,
            0.15,
            f"{path.name}: ML-only healthy over-alert exceeded guardrail ({value:.4f} > 0.15)",
        )

    def test_ml_layer_top3_any_true_does_not_materially_regress(self) -> None:
        path, data = _latest_balanced_layer1_metrics_export()
        value = _headline_metric(data, "top3_coverage_any_true")
        self.assertGreaterEqual(
            value,
            0.49,
            f"{path.name}: ML-only top3_any_true regressed materially ({value:.4f} < 0.49)",
        )

    def test_per_model_healthy_flag_rates_stay_under_guardrails(self) -> None:
        path, data = _latest_balanced_layer1_metrics_export()
        guardrails = {
            "anemia": 0.05,
            "electrolyte_imbalance": 0.03,
            "hepatitis": 0.02,
            "hypothyroidism": 0.02,
            "inflammation": 0.05,
            "iron_deficiency": 0.05,
            "kidney_disease": 0.05,
            "liver": 0.01,
            "perimenopause": 0.01,
            "prediabetes": 0.03,
            "sleep_disorder": 0.01,
            "vitamin_d_deficiency": 0.05,
        }
        for condition_id, max_rate in guardrails.items():
            with self.subTest(condition=condition_id):
                row = _per_condition_row(data, condition_id)
                actual = float(row.get("healthy_flag_rate") or 0.0)
                self.assertLessEqual(
                    actual,
                    max_rate,
                    f"{path.name}: {condition_id} healthy_flag_rate regressed ({actual:.4f} > {max_rate:.4f})",
                )

    def test_recovered_models_do_not_fall_back_to_zero_recall(self) -> None:
        path, data = _latest_balanced_layer1_metrics_export()
        minimums = {
            "anemia": 0.10,
            "hepatitis": 0.50,
            "kidney_disease": 0.20,
            "inflammation": 0.05,
            "prediabetes": 0.10,
            "sleep_disorder": 0.20,
            "vitamin_d_deficiency": 0.10,
        }
        for condition_id, min_recall in minimums.items():
            with self.subTest(condition=condition_id):
                row = _per_condition_row(data, condition_id)
                actual = float(row.get("recall") or 0.0)
                self.assertGreaterEqual(
                    actual,
                    min_recall,
                    f"{path.name}: {condition_id} recall regressed ({actual:.4f} < {min_recall:.4f})",
                )


if __name__ == "__main__":
    unittest.main()
