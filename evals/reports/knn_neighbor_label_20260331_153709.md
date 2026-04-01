# HalfFull KNN Neighbor-Label Eval — knn_neighbor_label_20260331_153709

> KNN neighbor disease-label voting. No ML models. No Bayesian updating.  Condition score = fraction of 50 nearest NHANES neighbors carrying that disease label.

## Run Metadata

| Field | Value |
|-------|-------|
| Git SHA | 70acb82d813523d50895400728752baca18a8be5 |
| Profiles Path | `evals/cohort/nhanes_balanced_760.json` |
| KNN index | cosine-NN, k=50, NHANES 760-profile anchor |
| Condition score | fraction of 50 neighbors with disease label = 1 |
| Flag threshold | neighbor_fraction ≥ 2.0× population prevalence (lift ≥ 2.0) |

## NHANES Label → Eval Condition Mapping

| NHANES label | Eval condition(s) | Pop. prevalence | Lift-2 flag threshold |
|-------------|------------------|----------------|----------------------|
| `anemia` | `anemia`, `iron_deficiency` *(shared label)* | 4.8% | ≥ 9.6% |
| `diabetes` | `prediabetes` | 22.1% | ≥ 44.2% |
| `thyroid` | `hypothyroidism` | 6.2% | ≥ 12.4% |
| `sleep_disorder` | `sleep_disorder` | 32.1% | ≥ 64.1% |
| `kidney` | `kidney_disease` | 2.5% | ≥ 5.0% |
| `hepatitis_bc` | `hepatitis` | 2.6% | ≥ 5.2% |
| `liver` | `liver` | 4.1% | ≥ 8.1% |
| `menopause` | `perimenopause` *(approx)* | 17.1% | ≥ 34.2% |
| *no label* | `electrolyte_imbalance`, `inflammation`, `vitamin_d_deficiency` | — | — |

## Summary

| Metric | Primary-target | Any-label |
|--------|---------------|-----------|
| Profiles evaluated | 760 | — |
| Profiles scored    | 760 | — |
| Scoring errors     | 0 | — |
| Top-1 eligible (label-covered GT) | 495 (65%) | 496 (65%) |
| Top-1 Accuracy (all eligible) | 11.7% | 14.7% |
| Top-1 Accuracy (positives only) | 11.8% | 11.8% |
| Top-3 Coverage | 33.3% | 48.8% |
| Over-Alert Rate (healthy) | 100.0% | — |
| Hallucination Rate | skipped | skipped |
| Parse Success Rate | skipped | skipped |

> **Primary-target**: KNN top-1 (or top-3) matches the profile's single primary GT condition. Eligible only when that condition has a NHANES disease label.  Direct equivalent of `run_layer1_eval.py` metrics.

> **Any-label**: KNN top-1 (or top-3) matches *any* condition the user actually has (full `expected_conditions[]`).  Eligible when at least one of their conditions has a label.

## By Quiz Path

| Path | Top-1 (primary) | Top-1 (any-label) | Top-3 (primary) | Top-3 (any-label) | N |
|------|----------------|------------------|----------------|------------------|---|
| full | 0.0% | 0.0% | 0.0% | 0.0% | 0 |
| hybrid | 11.7% | 14.7% | 33.3% | 48.8% | 760 |

## Per-Condition Metrics — As Target

> Positive set = profiles where this condition is the **primary target** and profile type is `positive`.  Matches `run_layer1_eval.py` definition.

| Condition | NHANES Label | Pop. Prevalence | Flag Threshold | N target+ | N flagged | Recall | Precision | Flag Rate | Mean Score |
|-----------|-------------|----------------|---------------|-----------|-----------|--------|-----------|-----------|------------|
| anemia | `anemia` | 4.8% | 9.6% | 20 | 13 | 0.0% | 0.0% | 1.7% | 0.044 |
| electrolyte_imbalance *(no label)* | — | 0.0% | — | 43 | 0 | 0.0% | — | 0.0% | 0.000 |
| hepatitis | `hepatitis_bc` | 2.6% | 5.2% | 26 | 748 | 100.0% | 3.5% | 98.4% | 0.061 |
| hypothyroidism | `thyroid` | 6.2% | 12.4% | 16 | 0 | 0.0% | — | 0.0% | 0.080 |
| inflammation *(no label)* | — | 0.0% | — | 49 | 0 | 0.0% | — | 0.0% | 0.000 |
| iron_deficiency | `anemia` | 4.8% | 9.6% | 43 | 13 | 0.0% | 0.0% | 1.7% | 0.043 |
| kidney_disease | `kidney` | 2.5% | 5.0% | 23 | 713 | 100.0% | 3.2% | 93.8% | 0.064 |
| liver | `liver` | 4.1% | 8.1% | 34 | 273 | 64.7% | 8.1% | 35.9% | 0.092 |
| perimenopause | `menopause` | 17.1% | 34.2% | 42 | 8 | 9.5% | 50.0% | 1.1% | 0.262 |
| prediabetes | `diabetes` | 22.1% | 44.2% | 49 | 0 | 0.0% | — | 0.0% | 0.338 |
| sleep_disorder | `sleep_disorder` | 32.1% | 64.1% | 27 | 0 | 0.0% | — | 0.0% | 0.387 |
| vitamin_d_deficiency *(no label)* | — | 0.0% | — | 55 | 0 | 0.0% | — | 0.0% | 0.000 |

## Per-Condition Metrics — As Any-Label

> Positive set = all non-healthy profiles where this condition appears **anywhere** in `expected_conditions[]`.

| Condition | N any-label+ | N flagged | Recall | Precision | Flag Rate | Mean Score |
|-----------|-------------|-----------|--------|-----------|-----------|------------|
| anemia | 55 | 13 | 1.8% | 7.7% | 1.7% | 0.048 |
| electrolyte_imbalance *(no label)* | 105 | 0 | 0.0% | — | 0.0% | 0.000 |
| hepatitis | 59 | 748 | 100.0% | 7.9% | 98.4% | 0.061 |
| hypothyroidism | 61 | 0 | 0.0% | — | 0.0% | 0.085 |
| inflammation *(no label)* | 95 | 0 | 0.0% | — | 0.0% | 0.000 |
| iron_deficiency | 81 | 13 | 0.0% | 0.0% | 1.7% | 0.045 |
| kidney_disease | 65 | 713 | 95.4% | 8.7% | 93.8% | 0.064 |
| liver | 85 | 273 | 47.1% | 14.6% | 35.9% | 0.088 |
| perimenopause | 132 | 8 | 6.1% | 100.0% | 1.1% | 0.252 |
| prediabetes | 61 | 0 | 0.0% | — | 0.0% | 0.336 |
| sleep_disorder | 69 | 0 | 0.0% | — | 0.0% | 0.389 |
| vitamin_d_deficiency *(no label)* | 117 | 0 | 0.0% | — | 0.0% | 0.000 |

## Healthy False Positives

| Condition | NHANES Label | Flag Threshold | Healthy Flagged | Healthy Flag Rate |
|-----------|-------------|---------------|-----------------|-------------------|
| anemia | `anemia` | 9.6% | 1 | 1.0% |
| electrolyte_imbalance | — | — | 0 | 0.0% |
| hepatitis | `hepatitis_bc` | 5.2% | 100 | 100.0% |
| hypothyroidism | `thyroid` | 12.4% | 0 | 0.0% |
| inflammation | — | — | 0 | 0.0% |
| iron_deficiency | `anemia` | 9.6% | 1 | 1.0% |
| kidney_disease | `kidney` | 5.0% | 95 | 95.0% |
| liver | `liver` | 8.1% | 31 | 31.0% |
| perimenopause | `menopause` | 34.2% | 0 | 0.0% |
| prediabetes | `diabetes` | 44.2% | 0 | 0.0% |
| sleep_disorder | `sleep_disorder` | 64.1% | 0 | 0.0% |
| vitamin_d_deficiency | — | — | 0 | 0.0% |

## Caveats

> **No NHANES label** — The following conditions have no binary label in `nhanes_merged_adults_diseases.csv` and always score 0. Excluded from top-1 / top-3 denominators: `electrolyte_imbalance`, `inflammation`, `vitamin_d_deficiency`.

> **Shared label** — `anemia` and `iron_deficiency` both map to the same NHANES label and will always receive identical scores. KNN label voting cannot distinguish between them.

> **`menopause` → `perimenopause`** — The NHANES `menopause` label (prevalence 17.1%) covers all post-menopausal women, which is broader than the product's `perimenopause` definition (females 35–55 with irregular periods). Expect inflated recall and potentially inflated false-positive rates on younger profiles.

> **`diabetes` → `prediabetes`** — The NHANES `diabetes` label (prevalence 22.1%) includes both type-2 diabetes and borderline cases. Neighbor-fraction scores for `prediabetes` reflect the full diabetes+prediabetes spectrum, not just the pre-diabetic subgroup.

> **Score interpretation** — Scores are raw neighbor fractions (0.0–1.0), not probabilities. A score of 0.10 means 5 of 50 nearest NHANES neighbors carry that label. Do not compare magnitudes directly to ML model probabilities in the layer1 report.
