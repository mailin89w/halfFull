# Quiz-Only Three-Arm Eval

This eval compares three arms on the same stratified sample from [`nhanes_balanced_650.json`](C:\Users\Philipp\AIBootcamp\halfFull\evals\cohort\nhanes_balanced_650.json):

1. `models_only`
2. `medgemma_only`
3. `hybrid_top5`

## Defaults

- Cohort: real NHANES balanced benchmark
- Conditions: 12 only (`vitamin_b12_deficiency` excluded)
- Sampling: small stratified iteration set
- No Bayesian follow-up
- No KNN neighbour signals
- Primary metric: `recall@3`
- Guardrails:
  - healthy over-alert rate
  - per-condition neighbour false positives

## Command

```bash
python evals/run_quiz_three_arm_eval.py --base-url http://127.0.0.1:3000
```

Helpful flags:

- `--sample-per-condition 8`
- `--multi-per-condition 2`
- `--healthy-n 24`
- `--seed 42`
- `--timeout 180`
- `--dry-run`

## Arm Definitions

### `models_only`

Runs the 12 condition models locally on quiz-only inputs and ranks conditions by score.

### `medgemma_only`

Calls the live [`/api/deep-analyze`](C:\Users\Philipp\AIBootcamp\halfFull\frontend\app\api\deep-analyze\route.ts) route with quiz answers only. An eval-specific request mode keeps the product route but withholds ML scores from the MedGemma grounding prompt.

### `hybrid_top5`

Calls the same live route with quiz answers plus only the top-5 model scores.

## Outputs

- `evals/results/quiz_three_arm_YYYYMMDD_HHMMSS.json`
- `evals/reports/quiz_three_arm_YYYYMMDD_HHMMSS.md`

## Recommendation Logic

Per condition:

- `keep`: hybrid improves recall@3 over MedGemma-only without a large neighbour-FP penalty
- `maybe`: mixed result
- `skip_candidate`: MedGemma-only already performs better and the condition model does not recover the gap
