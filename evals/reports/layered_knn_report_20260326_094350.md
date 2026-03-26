# Layered KNN Evaluation Report

Generated: 2026-03-26T09:43:50

## Cohort

- Profiles evaluated: `22`
- Source: `/Users/annaesakova/aipm/halfFull/evals/cohort/knn_overlap_pack.json`
- Source: `/Users/annaesakova/aipm/halfFull/evals/cohort/knn_liver_pack.json`

## Overall Lab Coverage

| Layer | Hit Rate | Exact Coverage | Mean Recall | Mean Precision |
|---|---:|---:|---:|---:|
| ML only | 63.6% | 22.7% | 42.4% | 45.5% |
| ML + Bayesian | 59.1% | 22.7% | 44.7% | 49.2% |
| ML + Bayesian + KNN | 77.3% | 40.9% | 62.1% | 39.3% |

## Incremental Gain

| Delta | Hit Rate | Exact Coverage | Mean Recall | Mean Precision |
|---|---:|---:|---:|---:|
| Bayesian over ML | -4.5% | +0.0% | +2.3% | +3.8% |
| KNN over ML+Bayesian | +18.2% | +18.2% | +17.4% | -9.9% |
| Total gain over ML | +13.6% | +18.2% | +19.7% | -6.1% |

## Per Condition

| Condition | N | ML Top-1 | Bayesian Top-1 | ML Lab Hit | Bayes Lab Hit | Full Lab Hit | Full Exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| anemia | 1 | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| hepatitis | 6 | 0.0% | 50.0% | 100.0% | 83.3% | 83.3% | 66.7% |
| hypothyroidism | 1 | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% |
| iron_deficiency | 1 | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| kidney_disease | 4 | 0.0% | 0.0% | 25.0% | 25.0% | 100.0% | 50.0% |
| liver | 8 | 0.0% | 0.0% | 50.0% | 37.5% | 50.0% | 12.5% |
| prediabetes | 1 | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% | 0.0% |

## KNN Wins

- Profiles improved by KNN over ML+Bayesian: `7/22`
- `KNN-OVR-001` (kidney_disease): Bayes groups `['glycemic', 'lipids']` -> Full groups `['glycemic', 'kidney', 'lipids']` vs truth `['kidney']`
- `KNN-OVR-002` (kidney_disease): Bayes groups `['glycemic', 'lipids']` -> Full groups `['glycemic', 'kidney', 'lipids']` vs truth `['cbc', 'kidney']`
- `KNN-OVR-003` (kidney_disease): Bayes groups `['glycemic', 'lipids']` -> Full groups `['glycemic', 'kidney', 'lipids']` vs truth `['glycemic', 'kidney', 'lipids']`
- `KNN-OVR-007` (anemia): Bayes groups `['cbc', 'iron_studies']` -> Full groups `['cbc', 'iron_studies', 'kidney']` vs truth `['cbc', 'iron_studies', 'kidney']`
- `KNN-OVR-012` (kidney_disease): Bayes groups `['glycemic', 'lipids']` -> Full groups `['glycemic', 'kidney', 'lipids']` vs truth `['inflammation', 'kidney']`
- `KNN-LVR-004` (hepatitis): Bayes groups `['liver_panel']` -> Full groups `['glycemic', 'kidney', 'lipids', 'liver_panel']` vs truth `['glycemic', 'lipids', 'liver_panel']`
- `KNN-LVR-007` (liver): Bayes groups `['glycemic', 'inflammation', 'lipids']` -> Full groups `['glycemic', 'inflammation', 'kidney', 'lipids']` vs truth `['kidney', 'liver_panel']`

## Cases Unchanged After KNN

- `KNN-OVR-004` (liver): Bayes groups `[]`, KNN added `['glycemic', 'kidney', 'lipids']`, truth `['liver_panel']`
- `KNN-OVR-005` (hepatitis): Bayes groups `['liver_panel']`, KNN added `['glycemic', 'kidney', 'lipids']`, truth `['liver_panel']`
- `KNN-OVR-006` (liver): Bayes groups `['glycemic', 'lipids']`, KNN added `['kidney', 'lipids']`, truth `['inflammation', 'liver_panel']`
- `KNN-OVR-008` (iron_deficiency): Bayes groups `['cbc', 'glycemic', 'iron_studies', 'lipids']`, KNN added `['kidney']`, truth `['cbc', 'iron_studies']`
- `KNN-OVR-009` (hypothyroidism): Bayes groups `['glycemic', 'lipids']`, KNN added `['glycemic', 'kidney', 'lipids']`, truth `['glycemic', 'lipids', 'thyroid']`
- `KNN-OVR-010` (prediabetes): Bayes groups `['glycemic', 'lipids']`, KNN added `['kidney', 'lipids']`, truth `['glycemic', 'inflammation', 'lipids']`
- `KNN-OVR-011` (liver): Bayes groups `['glycemic', 'lipids']`, KNN added `['kidney', 'lipids']`, truth `['glycemic', 'lipids', 'liver_panel']`
- `KNN-LVR-001` (liver): Bayes groups `['liver_panel']`, KNN added `['kidney', 'lipids']`, truth `['liver_panel']`
- `KNN-LVR-002` (hepatitis): Bayes groups `['glycemic', 'lipids', 'liver_panel']`, KNN added `['glycemic', 'kidney', 'lipids']`, truth `['liver_panel']`
- `KNN-LVR-003` (liver): Bayes groups `['glycemic', 'lipids']`, KNN added `['kidney', 'lipids']`, truth `['inflammation', 'liver_panel']`
