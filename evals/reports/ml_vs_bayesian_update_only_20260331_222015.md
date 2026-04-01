# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_222015

- Cohort: `evals/cohort/nhanes_balanced_760.json`
- Profiles evaluated: `760`
- Primary metric: `Top-3 contains any true condition (all_labels)`

## Headline Metrics

| Metric | ML-only | Bayesian update_only | Delta |
|--------|---------|----------------------|-------|
| Top-3 contains any true condition | 51.7% | 71.4% | +19.7 pp |
| Top-1 primary accuracy | 18.4% | 36.8% | +18.4 pp |
| Top-1 primary accuracy (positives only) | 16.4% | 34.7% | +18.3 pp |
| Top-3 primary coverage | 40.1% | 63.2% | +23.1 pp |
| Healthy over-alert rate | 18.0% | 28.0% | +10.0 pp |

## Default Flow

| Metric | ML-only | Default ML+Bayes | Delta | Full Bayesian update_only |
|--------|---------|------------------|-------|----------------------------|
| Top-3 contains any true condition | 51.7% | 62.7% | +11.0 pp | 71.4% |
| Top-1 primary accuracy | 18.4% | 31.4% | +13.0 pp | 36.8% |
| Top-3 primary coverage | 40.1% | 53.8% | +13.7 pp | 63.2% |
| Healthy over-alert rate | 18.0% | 13.0% | -5.0 pp | 28.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 27 | 81.5% | 77.8% | 85.2% | 4.6% | 5.6% | 2.2% |
| hypothyroidism | 61 | 77.0% | 86.9% | 95.1% | 48.1% | 39.5% | 47.6% |
| kidney_disease | 65 | 21.5% | 66.1% | 81.5% | 6.2% | 8.5% | 6.2% |
| sleep_disorder | 69 | 85.5% | 84.1% | 87.0% | 65.6% | 58.6% | 29.2% |
| anemia | 55 | 12.7% | 34.5% | 40.0% | 11.6% | 25.5% | 11.9% |
| iron_deficiency | 81 | 45.7% | 77.8% | 86.4% | 7.1% | 5.6% | 6.3% |
| hepatitis | 59 | 5.1% | 30.5% | 28.8% | 2.4% | 2.4% | 2.1% |
| liver | 85 | 1.2% | 7.1% | 7.1% | 0.4% | 3.1% | 1.5% |
| prediabetes | 61 | 65.6% | 55.7% | 73.8% | 49.6% | 37.2% | 55.6% |
| inflammation | 95 | 13.7% | 35.8% | 36.8% | 7.5% | 17.6% | 13.8% |
| electrolyte_imbalance | 105 | 39.1% | 44.8% | 54.3% | 32.2% | 38.3% | 33.9% |
| vitamin_d_deficiency | 117 | 62.4% | 58.1% | 83.8% | 46.5% | 23.5% | 44.6% |