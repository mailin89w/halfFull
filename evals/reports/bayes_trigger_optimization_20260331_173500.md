# Bayesian Trigger Optimization — bayes_trigger_optimization_20260331_173500

- Source compare artifact: `/Users/annaesakova/aipm/halfFull/evals/results/ml_vs_bayesian_update_only_20260331_171838.json`
- Cohort: `/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_760.json`
- Objective: optimize trigger policy by observed Bayes lift, not only raw ML confidence.

## Recommendations

| Condition | Recommendation | Full-default lift | FP delta | Trigger rate | Mean Qs when triggered | Reason |
|-----------|----------------|-------------------|----------|--------------|------------------------|--------|
| inflammation | aggressive | +20.0 pp | +9.3 pp | 19.3% | 4.00 | Large full-vs-default recall@3 lift (+20.0 pp) with manageable question cost (4.0 questions when triggered). |
| kidney_disease | aggressive | +15.4 pp | +1.3 pp | 30.5% | 3.00 | Large full-vs-default recall@3 lift (+15.4 pp) with manageable question cost (3.0 questions when triggered). |
| anemia | aggressive | +14.6 pp | -3.5 pp | 20.9% | 2.91 | Large full-vs-default recall@3 lift (+14.6 pp) with manageable question cost (2.9 questions when triggered). |
| hypothyroidism | moderate | +11.5 pp | +0.4 pp | 43.3% | 3.00 | Material recall@3 lift remains (+11.5 pp); worth broader Bayes routing, but keep some threshold discipline. |
| iron_deficiency | topk_rescue_only | +7.4 pp | +0.5 pp | 25.3% | 3.80 | Incremental lift is modest (+7.4 pp) or offset by FP/question cost; prefer rescue logic over aggressive threshold cuts. |
| sleep_disorder | topk_rescue_only | +5.8 pp | -10.3 pp | 26.2% | 4.00 | Incremental lift is modest (+5.8 pp) or offset by FP/question cost; prefer rescue logic over aggressive threshold cuts. |
| electrolyte_imbalance | topk_rescue_only | +2.9 pp | -5.2 pp | 15.0% | 3.00 | Incremental lift is modest (+2.9 pp) or offset by FP/question cost; prefer rescue logic over aggressive threshold cuts. |
| hepatitis | minimal | +5.1 pp | -0.4 pp | 8.2% | 2.98 | Little observed incremental value (+5.1 pp) relative to current default or question/FP cost. |
| liver | minimal | +2.4 pp | -1.3 pp | 4.9% | 1.92 | Little observed incremental value (+2.4 pp) relative to current default or question/FP cost. |
| perimenopause | minimal | +1.5 pp | -3.2 pp | 0.0% | 0.00 | Little observed incremental value (+1.5 pp) relative to current default or question/FP cost. |
| prediabetes | minimal | -1.6 pp | +4.4 pp | 22.2% | 2.00 | Little observed incremental value (-1.6 pp) relative to current default or question/FP cost. |
| vitamin_d_deficiency | minimal | -2.6 pp | -0.9 pp | 68.0% | 5.00 | Little observed incremental value (-2.6 pp) relative to current default or question/FP cost. |

## Detailed Metrics

| Condition | ML recall@3 | Default recall@3 | Full recall@3 | Full-default lift | Default FP@3 | Full FP@3 | Trigger rate | Mean Qs/profile | Mean Qs/triggered |
|-----------|-------------|------------------|---------------|-------------------|--------------|-----------|--------------|-----------------|-------------------|
| inflammation | 13.7% | 15.8% | 35.8% | +20.0 pp | 12.2% | 21.5% | 19.3% | 0.77 | 4.00 |
| kidney_disease | 21.5% | 69.2% | 84.6% | +15.4 pp | 4.9% | 6.2% | 30.5% | 0.92 | 3.00 |
| anemia | 12.7% | 27.3% | 41.8% | +14.6 pp | 13.3% | 9.8% | 20.9% | 0.61 | 2.91 |
| hypothyroidism | 77.0% | 85.2% | 96.7% | +11.5 pp | 46.8% | 47.2% | 43.3% | 1.30 | 3.00 |
| iron_deficiency | 45.7% | 72.8% | 80.2% | +7.4 pp | 5.1% | 5.6% | 25.3% | 0.96 | 3.80 |
| sleep_disorder | 85.5% | 78.3% | 84.1% | +5.8 pp | 39.1% | 28.8% | 26.2% | 1.05 | 4.00 |
| electrolyte_imbalance | 39.1% | 44.8% | 47.6% | +2.9 pp | 33.7% | 28.5% | 15.0% | 0.45 | 3.00 |
| hepatitis | 5.1% | 23.7% | 28.8% | +5.1 pp | 2.4% | 2.0% | 8.2% | 0.24 | 2.98 |
| liver | 1.2% | 5.9% | 8.2% | +2.4 pp | 2.7% | 1.3% | 4.9% | 0.09 | 1.92 |
| perimenopause | 16.7% | 15.2% | 16.7% | +1.5 pp | 5.6% | 2.4% | 0.0% | 0.00 | 0.00 |
| prediabetes | 65.6% | 75.4% | 73.8% | -1.6 pp | 52.9% | 57.4% | 22.2% | 0.44 | 2.00 |
| vitamin_d_deficiency | 62.4% | 67.5% | 65.0% | -2.6 pp | 50.9% | 49.9% | 68.0% | 3.40 | 5.00 |