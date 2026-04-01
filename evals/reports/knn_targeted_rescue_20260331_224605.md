# Targeted KNN Rescue Eval — knn_targeted_rescue_20260331_224605

- Cohort: `/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_760.json`
- Profiles evaluated: `760`
- KNN mode: `kidney-only rescue`, `top-1 frozen`, `slot-2/3 only`

## Headline Metrics

| Metric | Default ML+Bayes | + Targeted KNN rescue | Delta |
|--------|------------------|-----------------------|-------|
| Top-3 contains any true condition | 62.7% | 62.7% | +0.0 pp |
| Top-1 primary accuracy | 31.1% | 31.6% | +0.5 pp |
| Top-3 primary coverage | 53.8% | 53.8% | +0.0 pp |
| Healthy over-alert rate | 13.0% | 13.0% | +0.0 pp |

## KNN Checks

- Kidney rescued into top-3 on `0` profiles
- Top-1 changed profiles: `9`

## Kidney Focus

| Metric | Default ML+Bayes | + Targeted KNN rescue | Delta |
|--------|------------------|-----------------------|-------|
| Kidney recall@3 | 66.1% | 66.1% | +0.0 pp |
| Kidney absent FP@3 | 8.5% | 9.2% | +0.7 pp |
| Kidney healthy flag rate | 1.0% | 1.0% | +0.0 pp |