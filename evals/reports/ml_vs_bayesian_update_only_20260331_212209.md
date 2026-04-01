# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_212209

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
| Top-3 contains any true condition | 51.7% | 63.5% | +11.8 pp | 71.4% |
| Top-1 primary accuracy | 18.4% | 30.8% | +12.4 pp | 36.8% |
| Top-3 primary coverage | 40.1% | 54.1% | +14.0 pp | 63.2% |
| Healthy over-alert rate | 18.0% | 14.0% | -4.0 pp | 28.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 27 | 81.5% | 81.5% | 85.2% | 4.6% | 5.7% | 2.2% |
| hypothyroidism | 61 | 77.0% | 85.2% | 95.1% | 48.1% | 32.8% | 47.6% |
| kidney_disease | 65 | 21.5% | 67.7% | 81.5% | 6.2% | 8.6% | 6.2% |
| sleep_disorder | 69 | 85.5% | 85.5% | 87.0% | 65.6% | 53.0% | 29.2% |
| anemia | 55 | 12.7% | 34.5% | 40.0% | 11.6% | 22.8% | 11.9% |
| iron_deficiency | 81 | 45.7% | 76.5% | 86.4% | 7.1% | 5.5% | 6.3% |
| hepatitis | 59 | 5.1% | 30.5% | 28.8% | 2.4% | 2.4% | 2.1% |
| liver | 85 | 1.2% | 4.7% | 7.1% | 0.4% | 3.3% | 1.5% |
| prediabetes | 61 | 65.6% | 65.6% | 73.8% | 49.6% | 48.1% | 55.6% |
| inflammation | 95 | 13.7% | 32.6% | 36.8% | 7.5% | 15.5% | 13.8% |
| electrolyte_imbalance | 105 | 39.1% | 45.7% | 54.3% | 32.2% | 40.2% | 33.9% |
| vitamin_d_deficiency | 117 | 62.4% | 65.8% | 83.8% | 46.5% | 26.1% | 44.6% |