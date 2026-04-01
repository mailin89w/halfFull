# Disease-Refinement Cluster Prototype — disease_refinement_cluster_20260331_215525

> Symptom/questionnaire-focused neighbor voting prototype. Offline only.

## Setup

- Cohort: `evals/cohort/nhanes_balanced_760.json`
- NHANES index rows: `7437`
- Neighbor count: `50`
- Refinement features: `25`

## Headline

| Metric | Value |
|--------|-------|
| Top-3 contains any true condition | 19.6% |
| Top-1 primary accuracy | 8.8% |
| Top-3 primary coverage | 19.2% |
| Healthy over-alert rate | 100.0% |

## Per Condition

| Condition | Recall@3 | Healthy flag rate | Threshold | N any-label+ |
|-----------|----------|-------------------|-----------|--------------|
| anemia | 0.0% | 0.0% | 0.10 | 55 |
| electrolyte_imbalance | 0.0% | 0.0% | 1.00 | 105 |
| hepatitis | 0.0% | 97.0% | 0.06 | 59 |
| hypothyroidism | 0.0% | 0.0% | 0.14 | 61 |
| inflammation | 0.0% | 0.0% | 1.00 | 95 |
| iron_deficiency | 0.0% | 0.0% | 0.10 | 81 |
| kidney_disease | 0.0% | 100.0% | 0.06 | 65 |
| liver | 0.0% | 0.0% | 0.10 | 85 |
| perimenopause | 100.0% | 3.0% | 0.36 | 27 |
| prediabetes | 100.0% | 0.0% | 0.46 | 61 |
| sleep_disorder | 100.0% | 0.0% | 0.66 | 69 |
| vitamin_d_deficiency | 0.0% | 0.0% | 1.00 | 117 |