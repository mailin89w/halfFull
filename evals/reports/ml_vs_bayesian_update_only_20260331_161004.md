# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_161004

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
| Healthy over-alert rate | 19.0% | 24.0% | +5.0 pp |

## Per-Disease

| Condition | N+ | ML recall@3 | Bayes recall@3 | Delta | ML absent FP@3 | Bayes absent FP@3 | ML threshold recall | Bayes threshold recall |
|-----------|----|-------------|----------------|-------|-----------------|--------------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 16.7% | +0.0 pp | 5.4% | 2.4% | 17.4% | 18.9% |
| hypothyroidism | 61 | 77.0% | 96.7% | +19.7 pp | 48.1% | 47.2% | 47.5% | 93.4% |
| kidney_disease | 65 | 21.5% | 84.6% | +63.1 pp | 6.2% | 6.2% | 40.0% | 84.6% |
| sleep_disorder | 69 | 85.5% | 84.1% | -1.4 pp | 65.6% | 28.8% | 36.2% | 59.4% |
| anemia | 55 | 12.7% | 41.8% | +29.1 pp | 11.6% | 9.8% | 23.6% | 49.1% |
| iron_deficiency | 81 | 45.7% | 80.2% | +34.6 pp | 7.1% | 5.6% | 56.8% | 88.9% |
| hepatitis | 59 | 5.1% | 28.8% | +23.7 pp | 2.4% | 2.0% | 27.1% | 37.3% |
| liver | 85 | 1.2% | 8.2% | +7.1 pp | 0.4% | 1.3% | 23.5% | 23.5% |
| prediabetes | 61 | 65.6% | 73.8% | +8.2 pp | 49.6% | 57.4% | 19.7% | 45.9% |
| inflammation | 95 | 13.7% | 35.8% | +22.1 pp | 7.5% | 21.5% | 11.6% | 31.6% |
| electrolyte_imbalance | 105 | 39.1% | 47.6% | +8.6 pp | 32.2% | 28.5% | 21.9% | 32.4% |
| vitamin_d_deficiency | 117 | 62.4% | 65.0% | +2.6 pp | 46.5% | 49.9% | 17.1% | 17.1% |