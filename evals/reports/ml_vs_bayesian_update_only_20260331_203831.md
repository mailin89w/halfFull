# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_203831

- Cohort: `/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_760.json`
- Profiles evaluated: `760`
- Primary metric: `Top-3 contains any true condition (all_labels)`

## Headline Metrics

| Metric | ML-only | Bayesian update_only | Delta |
|--------|---------|----------------------|-------|
| Top-3 contains any true condition | 48.9% | 67.7% | +18.8 pp |
| Top-1 primary accuracy | 17.1% | 34.4% | +17.3 pp |
| Top-1 primary accuracy (positives only) | 16.4% | 35.1% | +18.7 pp |
| Top-3 primary coverage | 37.3% | 58.5% | +21.2 pp |
| Healthy over-alert rate | 18.0% | 25.0% | +7.0 pp |

## Default Flow

| Metric | ML-only | Default ML+Bayes | Delta | Full Bayesian update_only |
|--------|---------|------------------|-------|----------------------------|
| Top-3 contains any true condition | 48.9% | 60.2% | +11.2 pp | 67.7% |
| Top-1 primary accuracy | 17.1% | 28.5% | +11.4 pp | 34.4% |
| Top-3 primary coverage | 37.3% | 50.1% | +12.9 pp | 58.5% |
| Healthy over-alert rate | 18.0% | 16.0% | -2.0 pp | 25.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 16.7% | 16.7% | 5.4% | 7.0% | 2.2% |
| hypothyroidism | 61 | 77.0% | 85.2% | 95.1% | 48.1% | 31.8% | 47.9% |
| kidney_disease | 65 | 21.5% | 69.2% | 83.1% | 6.2% | 8.6% | 6.3% |
| sleep_disorder | 69 | 85.5% | 87.0% | 87.0% | 65.6% | 53.3% | 29.2% |
| anemia | 55 | 12.7% | 34.5% | 38.2% | 11.6% | 22.6% | 12.1% |
| iron_deficiency | 81 | 45.7% | 76.5% | 85.2% | 7.1% | 5.9% | 6.0% |
| hepatitis | 59 | 5.1% | 30.5% | 28.8% | 2.4% | 3.4% | 2.1% |
| liver | 85 | 1.2% | 4.7% | 7.1% | 0.4% | 2.8% | 1.2% |
| prediabetes | 61 | 65.6% | 52.5% | 73.8% | 49.6% | 45.8% | 60.8% |
| inflammation | 95 | 13.7% | 31.6% | 34.7% | 7.5% | 15.8% | 13.7% |
| electrolyte_imbalance | 105 | 39.1% | 51.4% | 54.3% | 32.2% | 42.9% | 31.3% |
| vitamin_d_deficiency | 117 | 62.4% | 65.0% | 83.8% | 46.5% | 25.5% | 42.8% |