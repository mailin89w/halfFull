# Kidney FP Audit — ML-KIDNEY-02

**Cohort:** 760-profile NHANES balanced  |  **Threshold:** 0.35

## Overall
- Total FPs: **201** (26.4% of all profiles)
- Flag rate across all profiles: 28.4%
- Mean kidney score (all profiles): 0.2425

## FP Breakdown by Bucket

| Bucket | Count | % of FPs | Description |
|--------|-------|----------|-------------|
| healthy      | 9 | 4% | No conditions, model still fires |
| metabolic    | 51 | 25% | Prediabetes / anemia / iron / vit-D |
| hypertensive | 32 | 16% | Electrolyte / cardiovascular overlap |
| other        | 109 | 54% | Sleep, thyroid, or mixed patterns |

## Top Confounding Conditions

| Condition | Times a Confounder |
|-----------|-------------------|
| perimenopause | 81 |
| liver | 38 |
| hypothyroidism | 33 |
| electrolyte_imbalance | 32 |
| sleep_disorder | 29 |
| prediabetes | 25 |
| inflammation | 24 |
| anemia | 21 |
| vitamin_d_deficiency | 19 |
| hepatitis | 13 |

## Implication for v4

- **Healthy FPs** → pure noise; hard-negative anchors from v3 already target this.
- **Metabolic FPs** → shared symptom burden (fatigue, frequent urination); soft-weighting the hard negatives should help without suppressing borderline CKD.
- **Hypertensive FPs** → HTN is a legitimate CKD risk factor; do NOT over-penalise these — Bayesian layer should disambiguate.
- **Other FPs** → thyroid/sleep overlap; already captured in v3 hard-neg set.