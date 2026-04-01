# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_194616

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
| Top-3 contains any true condition | 48.9% | 60.2% | +11.2 pp | 65.9% |
| Top-1 primary accuracy | 17.1% | 28.8% | +11.7 pp | 33.2% |
| Top-3 primary coverage | 37.3% | 50.3% | +13.0 pp | 57.9% |
| Healthy over-alert rate | 18.0% | 27.0% | +9.0 pp | 23.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 15.9% | 16.7% | 5.4% | 8.4% | 2.4% |
| hypothyroidism | 61 | 77.0% | 83.6% | 95.1% | 48.1% | 27.9% | 48.2% |
| kidney_disease | 65 | 21.5% | 69.2% | 83.1% | 6.2% | 8.2% | 6.2% |
| sleep_disorder | 69 | 85.5% | 79.7% | 87.0% | 65.6% | 50.5% | 29.2% |
| anemia | 55 | 12.7% | 38.2% | 38.2% | 11.6% | 21.0% | 11.1% |
| iron_deficiency | 81 | 45.7% | 77.8% | 85.2% | 7.1% | 6.2% | 5.6% |
| hepatitis | 59 | 5.1% | 30.5% | 28.8% | 2.4% | 3.7% | 2.1% |
| liver | 85 | 1.2% | 9.4% | 7.1% | 0.4% | 3.6% | 1.2% |
| prediabetes | 61 | 65.6% | 50.8% | 73.8% | 49.6% | 37.6% | 58.9% |
| inflammation | 95 | 13.7% | 27.4% | 36.8% | 7.5% | 14.9% | 13.1% |
| electrolyte_imbalance | 105 | 39.1% | 56.2% | 51.4% | 32.2% | 45.6% | 30.2% |
| vitamin_d_deficiency | 117 | 62.4% | 59.0% | 65.8% | 46.5% | 40.1% | 51.2% |