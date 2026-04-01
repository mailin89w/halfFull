# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_200552

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
| Top-3 contains any true condition | 48.9% | 55.5% | +6.5 pp | 65.9% |
| Top-1 primary accuracy | 17.1% | 26.1% | +8.9 pp | 33.2% |
| Top-3 primary coverage | 37.3% | 44.9% | +7.6 pp | 57.9% |
| Healthy over-alert rate | 18.0% | 15.0% | -3.0 pp | 23.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 15.9% | 16.7% | 5.4% | 7.2% | 2.4% |
| hypothyroidism | 61 | 77.0% | 70.5% | 95.1% | 48.1% | 27.2% | 48.2% |
| kidney_disease | 65 | 21.5% | 67.7% | 83.1% | 6.2% | 10.9% | 6.2% |
| sleep_disorder | 69 | 85.5% | 84.1% | 87.0% | 65.6% | 50.8% | 29.2% |
| anemia | 55 | 12.7% | 40.0% | 38.2% | 11.6% | 25.0% | 11.1% |
| iron_deficiency | 81 | 45.7% | 74.1% | 85.2% | 7.1% | 5.9% | 5.6% |
| hepatitis | 59 | 5.1% | 11.9% | 28.8% | 2.4% | 4.4% | 2.1% |
| liver | 85 | 1.2% | 2.4% | 7.1% | 0.4% | 3.6% | 1.2% |
| prediabetes | 61 | 65.6% | 34.4% | 73.8% | 49.6% | 33.5% | 58.9% |
| inflammation | 95 | 13.7% | 25.3% | 36.8% | 7.5% | 17.4% | 13.1% |
| electrolyte_imbalance | 105 | 39.1% | 52.4% | 51.4% | 32.2% | 44.3% | 30.2% |
| vitamin_d_deficiency | 117 | 62.4% | 60.7% | 65.8% | 46.5% | 43.4% | 51.2% |