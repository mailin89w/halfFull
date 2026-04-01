# Roadmap KNN Condition Rescue Eval — roadmap_knn_condition_rescue_20260331_232626

- Cohort: `evals/cohort/nhanes_balanced_800.json`
- Profiles evaluated: `800`
- KNN policy: `top-1 frozen`, `rank 2-6 only`, `small rescue bonus`

## Headline

| Metric | Default ML+Bayes | + KNN all supported | Delta |
|--------|------------------|---------------------|-------|
| Top-3 contains any true condition | 64.7% | 63.5% | -1.2 pp |
| Top-1 primary accuracy | 34.5% | 34.5% | +0.0 pp |
| Top-3 primary coverage | 56.4% | 55.1% | -1.2 pp |
| Healthy over-alert rate | 13.4% | 13.4% | +0.0 pp |

## Condition Arms

| Condition | Top-3 any true | Delta | Top-1 primary | Delta | Healthy over-alert | Delta |
|-----------|----------------|-------|---------------|-------|--------------------|-------|
| anemia | 64.4% | -0.3 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| electrolyte_imbalance | 64.8% | +0.1 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| hepatitis | 64.7% | +0.0 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| hidden_inflammation | 64.7% | +0.0 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| hypothyroidism | 64.4% | -0.3 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| iron_deficiency | 64.5% | -0.2 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| kidney_disease | 64.7% | +0.0 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| liver | 64.7% | +0.0 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| perimenopause | 64.7% | +0.0 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| prediabetes | 64.5% | -0.2 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |
| sleep_disorder | 63.6% | -1.0 pp | 34.5% | +0.0 pp | 13.4% | +0.0 pp |

## Rescue Counts

- `roadmap_knn_all_supported`: top-3 changed on `233` profiles; primary rescues `12`
- `roadmap_knn_anemia`: top-3 changed on `19` profiles; primary rescues `1`
- `roadmap_knn_electrolyte_imbalance`: top-3 changed on `31` profiles; primary rescues `0`
- `roadmap_knn_hepatitis`: top-3 changed on `0` profiles; primary rescues `0`
- `roadmap_knn_hidden_inflammation`: top-3 changed on `0` profiles; primary rescues `0`
- `roadmap_knn_hypothyroidism`: top-3 changed on `20` profiles; primary rescues `0`
- `roadmap_knn_iron_deficiency`: top-3 changed on `35` profiles; primary rescues `2`
- `roadmap_knn_kidney_disease`: top-3 changed on `2` profiles; primary rescues `0`
- `roadmap_knn_liver`: top-3 changed on `2` profiles; primary rescues `0`
- `roadmap_knn_perimenopause`: top-3 changed on `1` profiles; primary rescues `0`
- `roadmap_knn_prediabetes`: top-3 changed on `65` profiles; primary rescues `5`
- `roadmap_knn_sleep_disorder`: top-3 changed on `145` profiles; primary rescues `4`