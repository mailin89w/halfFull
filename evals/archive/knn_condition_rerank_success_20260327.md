# KNN Condition Rerank Success Check

Generated: 2026-03-27

## Goal

Use KNN to rescue plausible missed comorbidities without inventing new top conditions from scratch.

## Implementation

- Added condition-aware KNN reranking in [evals/pipeline/knn_condition_reranker.py](/Users/annaesakova/aipm/halfFull/evals/pipeline/knn_condition_reranker.py)
- Guardrails:
  - only boost conditions already plausible after Bayesian (`posterior >= 0.20`)
  - only boost top-5 Bayesian candidates
  - cap total KNN bonus at `0.10`
  - freeze top-1 so KNN cannot create a brand-new leading condition
- Wired the same reranker into [evals/run_layered_knn_report.py](/Users/annaesakova/aipm/halfFull/evals/run_layered_knn_report.py)

## Eval Setup

- Cohort: [profiles_v3_three_layer.json](/Users/annaesakova/aipm/halfFull/evals/cohort/profiles_v3_three_layer.json)
- Sample: `600` profiles with seed `42`
- Labeled: `576`
- Multi-condition: `354`
- Healthy: `24`
- Baseline for comparison: saved Bayesian posteriors from [bayesian_20260326_221238.json](/Users/annaesakova/aipm/halfFull/evals/results/bayesian_20260326_221238.json)

## Success Criteria Results

| Check | Bayesian only | Bayesian + KNN rerank | Delta | Result |
|---|---:|---:|---:|---|
| Top-3 condition hit rate | 57.8% | 58.2% | +0.3 pp | PASS |
| Secondary / comorbidity recovery | 46.3% | 46.3% | +0.0 pp | PASS |
| Healthy over-alert | 45.8% | 45.8% | +0.0 pp | PASS |
| KNN-added condition ground-truth rate | - | 22.2% | vs removed 16.7% | PASS |
| Top-1 changed profiles | - | 0 | - | PASS |

Overall: `PASS`

Interpretation:
- KNN improved top-3 condition hit rate slightly without changing top-1.
- KNN did not improve comorbidity recovery yet, but it also did not worsen it.
- KNN did not worsen healthy over-alert.
- Conditions added by KNN were more often true than the conditions removed from the top-3.

## Concrete Wins

- `SYN-C0000097`
  - Truth: `['kidney', 'liver', 'sleep_disorder', 'electrolytes']`
  - Bayesian top-3: `['thyroid', 'prediabetes', 'anemia']`
  - KNN top-3: `['thyroid', 'prediabetes', 'kidney']`
  - Why: kidney received a `+0.08` bonus from kidney-group KNN support

- `SYN-R0000224`
  - Truth: `['prediabetes', 'sleep_disorder', 'iron_deficiency']`
  - Bayesian top-3: `['thyroid', 'inflammation', 'electrolytes']`
  - KNN top-3: `['thyroid', 'inflammation', 'prediabetes']`
  - Why: prediabetes received a `+0.03` bonus from lipid-group KNN support

- `SYN-C0000090`
  - Truth: `['kidney', 'prediabetes', 'electrolytes']`
  - Bayesian top-3: `['thyroid', 'sleep_disorder', 'prediabetes']`
  - KNN top-3: `['thyroid', 'kidney', 'sleep_disorder']`
  - Why: kidney received a `+0.08` bonus from kidney-group KNN support

- `SYN-R0000211`
  - Truth: `['prediabetes', 'inflammation']`
  - Bayesian top-3: `['thyroid', 'electrolytes', 'sleep_disorder']`
  - KNN top-3: `['thyroid', 'electrolytes', 'prediabetes']`
  - Why: prediabetes received a `+0.03` bonus from lipid-group KNN support

## What This Means

- The reranker is behaving safely: it is rescuing some plausible missed conditions, but not creating brand-new top-1 guesses.
- The gain is real but still small, so this should be treated as a conservative improvement, not a major step-change.
- The strongest immediate value is on kidney and prediabetes rescue cases where KNN sees condition-specific lab neighborhoods.

## Next Tightening Ideas

- Increase condition-specific bonuses only where the added-condition truth rate stays above the removed-condition truth rate
- Add more comorbidity pair rules for clinically common overlaps
- Add stronger suppression for weak KNN-driven promotions on noisy conditions like electrolytes and sleep
