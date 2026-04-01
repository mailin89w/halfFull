# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_201910

- Cohort: `/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_760.json`
- Profiles evaluated: `760`
- Primary metric: `Top-3 contains any true condition (all_labels)`

## Headline Metrics

| Metric | ML-only | Bayesian update_only | Delta |
|--------|---------|----------------------|-------|
| Top-3 contains any true condition | 48.9% | 65.9% | +17.0 pp |
| Top-1 primary accuracy | 17.1% | 33.2% | +16.1 pp |
| Top-1 primary accuracy (positives only) | 16.4% | 32.3% | +15.9 pp |
| Top-3 primary coverage | 37.3% | 57.9% | +20.6 pp |
| Healthy over-alert rate | 18.0% | 23.0% | +5.0 pp |

## Default Flow

| Metric | ML-only | Default ML+Bayes | Delta | Full Bayesian update_only |
|--------|---------|------------------|-------|----------------------------|
| Top-3 contains any true condition | 48.9% | 59.1% | +10.1 pp | 65.9% |
| Top-1 primary accuracy | 17.1% | 29.1% | +12.0 pp | 33.2% |
| Top-3 primary coverage | 37.3% | 48.8% | +11.5 pp | 57.9% |
| Healthy over-alert rate | 18.0% | 15.0% | -3.0 pp | 23.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 16.7% | 16.7% | 5.4% | 7.2% | 2.4% |
| hypothyroidism | 61 | 77.0% | 83.6% | 95.1% | 48.1% | 26.9% | 48.2% |
| kidney_disease | 65 | 21.5% | 69.2% | 83.1% | 6.2% | 8.6% | 6.2% |
| sleep_disorder | 69 | 85.5% | 87.0% | 87.0% | 65.6% | 53.5% | 29.2% |
| anemia | 55 | 12.7% | 34.5% | 38.2% | 11.6% | 22.0% | 11.1% |
| iron_deficiency | 81 | 45.7% | 76.5% | 85.2% | 7.1% | 6.0% | 5.6% |
| hepatitis | 59 | 5.1% | 28.8% | 28.8% | 2.4% | 3.4% | 2.1% |
| liver | 85 | 1.2% | 4.7% | 7.1% | 0.4% | 2.8% | 1.2% |
| prediabetes | 61 | 65.6% | 44.3% | 73.8% | 49.6% | 35.8% | 58.9% |
| inflammation | 95 | 13.7% | 28.4% | 36.8% | 7.5% | 15.6% | 13.1% |
| electrolyte_imbalance | 105 | 39.1% | 51.4% | 51.4% | 32.2% | 43.2% | 30.2% |
| vitamin_d_deficiency | 117 | 62.4% | 61.5% | 65.8% | 46.5% | 43.7% | 51.2% |