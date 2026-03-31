# Inflammation v4 Validation — ML-INFLAM-02

**Cohort:** 760-profile NHANES balanced  |  **Date:** 2026-03-31

## Results

| Metric | v3 (production) | v4 (candidate) | Delta |
|--------|----------------|----------------|-------|
| Recall        | 38.8% | 0.0% | -38.8% |
| Precision     | 7.4% | 0.0% | — |
| Flag Rate     | 34.0% | 0.1% | — |
| Healthy FPR   | 10.0% | 0.0% | — |
| Mean Score (pos) | 0.3844 | 0.0779 | — |
| Mean Score (neg) | 0.3623 | 0.0717 | — |

## Recommendation

**v4 recall is still below the floor (15%).**
The calibration and waist-flag changes alone are not enough.

Next steps:
1. Run `audit_inflammation_missed.py` to characterise what the model misses.
2. Assess whether the `hidden_inflammation` label is too fuzzy for the current feature set.
3. Consider a feature redesign that separates generic illness from true inflammation.