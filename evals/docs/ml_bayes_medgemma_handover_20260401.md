# ML + Bayes + MedGemma Handover (KNN Paused)

This handoff captures the current intended product/eval path:

- ML scoring
- Bayesian clarification and posterior update
- MedGemma deep analysis using the latest Bayesian posterior scores
- KNN paused everywhere for now

## Current KNN Pause

KNN is now paused in three places:

1. Frontend request path
   - [`frontend/src/lib/medgemma.ts`](/Users/annaesakova/aipm/halfFull/frontend/src/lib/medgemma.ts)
   - `fetchDeepAnalysis(...)` now sends `useKNN: false` via [`frontend/src/lib/featureFlags.ts`](/Users/annaesakova/aipm/halfFull/frontend/src/lib/featureFlags.ts)

2. Deep-analyze route
   - [`frontend/app/api/deep-analyze/route.ts`](/Users/annaesakova/aipm/halfFull/frontend/app/api/deep-analyze/route.ts)
   - server now ignores `body.useKNN` unless `ENABLE_KNN_LAYER` is set back to `true`

3. Railway backend endpoint
   - [`api/server.py`](/Users/annaesakova/aipm/halfFull/api/server.py)
   - `/knn-score` is now disabled by default unless `USE_KNN=true`

4. Final report page
   - [`frontend/app/results/page.tsx`](/Users/annaesakova/aipm/halfFull/frontend/app/results/page.tsx)
   - [`frontend/src/components/results/DiagnosisCard.tsx`](/Users/annaesakova/aipm/halfFull/frontend/src/components/results/DiagnosisCard.tsx)
   - KNN lab signals and KNN/cluster reasoning are hidden

## MedGemma Receives Latest Bayes

The current live handoff is:

1. Clarification page runs Bayesian update
   - [`frontend/app/clarify/page.tsx`](/Users/annaesakova/aipm/halfFull/frontend/app/clarify/page.tsx)
   - stores:
     - posterior scores via `storeBayesianScores(...)`
     - Bayesian traces via `storeBayesianDetails(...)`
     - human-readable clarification Q/A via `storeBayesianAnswers(...)`

2. Processing page prefers Bayesian scores over raw ML
   - [`frontend/app/processing/page.tsx`](/Users/annaesakova/aipm/halfFull/frontend/app/processing/page.tsx)
   - `mlScores = readStoredBayesianScores() ?? rawMlScores`
   - `rawMlScores` are still passed separately for reference

3. Deep-analyze route receives:
   - Bayesian posteriors as `mlScores`
   - raw ML as `rawMlScores`
   - clarification evidence as `clarificationQA`

So MedGemma is currently grounded on the latest Bayesian-adjusted scores, not stale raw ML alone.

## Local Product Run

### 1. Start the Railway-style backend

```bash
cd /Users/annaesakova/aipm/halfFull
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

KNN remains paused by default because `/knn-score` now requires:

```bash
USE_KNN=true
```

to turn back on.

### 2. Start the frontend

```bash
cd /Users/annaesakova/aipm/halfFull/frontend
npm run dev
```

If you want protected MedGemma-only eval mode locally, set:

```env
EVAL_MODE_SECRET=my_local_medgemma_eval_secret_2026
```

in [`frontend/.env.local`](/Users/annaesakova/aipm/halfFull/frontend/.env.local).

## Core Eval Commands

### A. ML-only baseline

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_layer1_eval.py \
  --profiles-path evals/cohort/nhanes_balanced_800.json
```

### B. ML vs default Bayes vs Bayes max

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/compare_ml_vs_bayesian_update_only.py \
  --profiles evals/cohort/nhanes_balanced_800.json
```

This gives:

- ML-only
- default triggered ML + Bayes
- full Bayes update-only upper bound

### C. Bayes-only

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_bayes_only_eval.py
```

If you need the realistic prior comparison, use the latest sex/age prevalence outputs already produced by that runner.

### D. MedGemma end-to-end eval on top of ML + Bayes

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_quiz_three_arm_eval.py \
  --base-url http://127.0.0.1:3000 \
  --eval-secret my_local_medgemma_eval_secret_2026 \
  --profiles evals/cohort/nhanes_balanced_800.json \
  --sample-per-condition 4 \
  --multi-per-condition 1 \
  --healthy-n 12
```

Important:

- this runner already sends `useKNN: false`
- `medgemma_plus_bayesian` is the relevant arm for “MedGemma complementing ML + Bayes”

## Recommended End-to-End Sequence

If you want a clean rerun from the current state:

1. Start backend API
2. Start frontend app
3. Run ML/Bayes metric compare:

```bash
python3 evals/compare_ml_vs_bayesian_update_only.py --profiles evals/cohort/nhanes_balanced_800.json
```

4. Run MedGemma complement eval:

```bash
python3 evals/run_quiz_three_arm_eval.py \
  --base-url http://127.0.0.1:3000 \
  --eval-secret my_local_medgemma_eval_secret_2026 \
  --profiles evals/cohort/nhanes_balanced_800.json \
  --sample-per-condition 4 \
  --multi-per-condition 1 \
  --healthy-n 12
```

5. If needed, run the current question ROI audit:

```bash
python3 evals/run_bayes_question_roi_eval.py
```

## Verification Notes

- Backend compile check passed for [`api/server.py`](/Users/annaesakova/aipm/halfFull/api/server.py)
- Focused frontend lint passed for the touched files:
  - [`frontend/app/api/deep-analyze/route.ts`](/Users/annaesakova/aipm/halfFull/frontend/app/api/deep-analyze/route.ts)
  - [`frontend/app/results/page.tsx`](/Users/annaesakova/aipm/halfFull/frontend/app/results/page.tsx)
  - [`frontend/src/components/results/DiagnosisCard.tsx`](/Users/annaesakova/aipm/halfFull/frontend/src/components/results/DiagnosisCard.tsx)
  - [`frontend/src/lib/medgemma.ts`](/Users/annaesakova/aipm/halfFull/frontend/src/lib/medgemma.ts)
  - [`frontend/src/lib/featureFlags.ts`](/Users/annaesakova/aipm/halfFull/frontend/src/lib/featureFlags.ts)

## Re-enable Later

When ready to test KNN again:

1. set [`frontend/src/lib/featureFlags.ts`](/Users/annaesakova/aipm/halfFull/frontend/src/lib/featureFlags.ts) to `true`
2. run backend with:

```bash
USE_KNN=true uvicorn api.server:app --host 0.0.0.0 --port 8000
```

That restores both the request path and the backend endpoint.
