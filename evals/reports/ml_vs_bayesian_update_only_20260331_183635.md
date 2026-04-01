# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_183635

- Cohort: `/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_760.json`
- Profiles evaluated: `760`
- Primary metric: `Top-3 contains any true condition (all_labels)`

## Headline Metrics

| Metric | ML-only | Bayesian update_only | Delta |
|--------|---------|----------------------|-------|
| Top-3 contains any true condition | 48.9% | 65.3% | +16.4 pp |
| Top-1 primary accuracy | 17.1% | 32.0% | +14.8 pp |
| Top-1 primary accuracy (positives only) | 16.4% | 30.7% | +14.3 pp |
| Top-3 primary coverage | 37.3% | 57.3% | +20.0 pp |
| Healthy over-alert rate | 18.0% | 21.0% | +3.0 pp |

## Default Flow

| Metric | ML-only | Default ML+Bayes | Delta | Full Bayesian update_only |
|--------|---------|------------------|-------|----------------------------|
| Top-3 contains any true condition | 48.9% | 58.9% | +10.0 pp | 65.3% |
| Top-1 primary accuracy | 17.1% | 26.1% | +8.9 pp | 32.0% |
| Top-3 primary coverage | 37.3% | 49.2% | +12.0 pp | 57.3% |
| Healthy over-alert rate | 18.0% | 15.0% | -3.0 pp | 21.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 15.9% | 16.7% | 5.4% | 7.3% | 2.4% |
| hypothyroidism | 61 | 77.0% | 82.0% | 96.7% | 48.1% | 31.8% | 47.2% |
| kidney_disease | 65 | 21.5% | 69.2% | 84.6% | 6.2% | 8.9% | 6.2% |
| sleep_disorder | 69 | 85.5% | 85.5% | 84.1% | 65.6% | 55.7% | 28.8% |
| anemia | 55 | 12.7% | 38.2% | 41.8% | 11.6% | 18.3% | 9.8% |
| iron_deficiency | 81 | 45.7% | 77.8% | 80.2% | 7.1% | 5.9% | 5.6% |
| hepatitis | 59 | 5.1% | 23.7% | 28.8% | 2.4% | 3.1% | 2.0% |
| liver | 85 | 1.2% | 10.6% | 8.2% | 0.4% | 3.3% | 1.3% |
| prediabetes | 61 | 65.6% | 47.5% | 73.8% | 49.6% | 36.9% | 57.4% |
| inflammation | 95 | 13.7% | 26.3% | 35.8% | 7.5% | 17.0% | 21.5% |
| electrolyte_imbalance | 105 | 39.1% | 52.4% | 47.6% | 32.2% | 45.2% | 28.5% |
| vitamin_d_deficiency | 117 | 62.4% | 53.0% | 65.0% | 46.5% | 36.1% | 49.9% |