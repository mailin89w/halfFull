# ML vs Bayesian Update-Only Comparison — ml_vs_bayesian_update_only_20260331_174239

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
| Top-3 contains any true condition | 48.9% | 60.2% | +11.2 pp | 65.3% |
| Top-1 primary accuracy | 17.1% | 26.7% | +9.6 pp | 32.0% |
| Top-3 primary coverage | 37.3% | 48.8% | +11.5 pp | 57.3% |
| Healthy over-alert rate | 18.0% | 19.0% | +1.0 pp | 21.0% |

## Per-Disease

| Condition | N+ | ML recall@3 | Default recall@3 | Full Bayes recall@3 | ML absent FP@3 | Default absent FP@3 | Full Bayes absent FP@3 |
|-----------|----|-------------|------------------|---------------------|-----------------|---------------------|------------------------|
| perimenopause | 132 | 16.7% | 15.2% | 16.7% | 5.4% | 5.6% | 2.4% |
| hypothyroidism | 61 | 77.0% | 85.2% | 96.7% | 48.1% | 46.5% | 47.2% |
| kidney_disease | 65 | 21.5% | 67.7% | 84.6% | 6.2% | 5.3% | 6.2% |
| sleep_disorder | 69 | 85.5% | 78.3% | 84.1% | 65.6% | 38.9% | 28.8% |
| anemia | 55 | 12.7% | 27.3% | 41.8% | 11.6% | 13.1% | 9.8% |
| iron_deficiency | 81 | 45.7% | 72.8% | 80.2% | 7.1% | 5.1% | 5.6% |
| hepatitis | 59 | 5.1% | 22.0% | 28.8% | 2.4% | 2.4% | 2.0% |
| liver | 85 | 1.2% | 5.9% | 8.2% | 0.4% | 2.7% | 1.3% |
| prediabetes | 61 | 65.6% | 73.8% | 73.8% | 49.6% | 52.9% | 57.4% |
| inflammation | 95 | 13.7% | 18.9% | 35.8% | 7.5% | 12.6% | 21.5% |
| electrolyte_imbalance | 105 | 39.1% | 44.8% | 47.6% | 32.2% | 33.6% | 28.5% |
| vitamin_d_deficiency | 117 | 62.4% | 68.4% | 65.0% | 46.5% | 50.7% | 49.9% |