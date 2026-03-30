# LLM Layer Improvements And Eval Workflow

This document captures the LLM-layer work completed in this branch, how we now evaluate the real MedGemma path, and the exact commands to run the checks locally or against a Vercel deployment.

It is written as a teammate handoff, especially for anyone working on the protected `medgemma_only` quiz eval path.

## What Changed In The Real LLM Pipeline

The app’s real user-facing path is:

1. `POST /api/deep-analyze`
2. MedGemma grounding
3. Groq synthesis with fallback chain
4. Tone rewrite on the real generated narrative
5. Deterministic final safety enforcement
6. Return final user report

The main improvements from this thread are:

- Moved useful rewrite logic into the real `/api/deep-analyze` flow instead of treating `/api/safety-rewrite` as the primary system.
- Kept deterministic safety floors in [`frontend/lib/medgemma-safety.ts`](/Users/annaesakova/aipm/halfFull/frontend/lib/medgemma-safety.ts) via `applyHardSafetyRules(...)`.
- Added real-route instrumentation headers in [`frontend/app/api/deep-analyze/route.ts`](/Users/annaesakova/aipm/halfFull/frontend/app/api/deep-analyze/route.ts) for:
  - grounding source
  - synthesis source / model / status
  - rewrite source / model / status
  - hard-safety application count
- Hardened schema handling so the route salvages usable model output instead of hard-failing on small omissions:
  - clamp oversized arrays
  - skip malformed nested entries
  - default missing optional arrays
  - trim extra entries instead of rejecting the whole payload
- Added deterministic condition-ID allowlist cleanup so fallback models cannot leak hallucinated conditions into the final output.
- Narrowed emergency escalation logic so mild cases are no longer over-escalated into “seek care today.”
- Expanded deterministic safety scanning across all user-facing fields, including summary, recovery, doctors, doctor kits, and next steps.
- Tightened `summaryPoints` so they should be short symptom bullets with no diagnoses.
- Added fallback-specific synthesis prompting to reduce Groq `413` request-too-large failures on smaller fallback models.
- Added Groq retry/backoff with jitter for real synthesis and rewrite calls on `429`.

## Protected MedGemma-Only Eval Mode

This push adds a protected `medgemma_only` eval path on top of the existing deep-analyze route, so we can run the MedGemma quiz-only arm through a Vercel preview deployment without affecting the normal product flow.

The protected mode requires:

- `EVAL_MODE_SECRET` to be defined in the server environment
- a matching `x-eval-mode-secret` request header

This keeps eval-only MedGemma testing isolated from real user traffic while still reusing the existing Vercel-to-MedGemma setup.

Implementation location:

- [`frontend/app/api/deep-analyze/route.ts`](/Users/annaesakova/aipm/halfFull/frontend/app/api/deep-analyze/route.ts)

Behavior:

- `evalMode: "medgemma_only"` withholds ML scores from the grounding prompt
- the route still uses the real MedGemma + synthesis + rewrite + hard-safety stack
- normal user traffic is unchanged

## How The LLM Layer Was Evaluated

We used two complementary evals.

### 1. Real Production-Path Eval

Runner:

- [`evals/run_llm_layer_eval.py`](/Users/annaesakova/aipm/halfFull/evals/run_llm_layer_eval.py)

Purpose:

- evaluate the actual `/api/deep-analyze` path users hit
- measure parse stability, hallucination control, final safety, and route-stage instrumentation

What it measures:

- JSON parse success rate
- condition-list match rate
- hallucination rate
- unsafe final-output rate
- route metadata for grounding / synthesis / rewrite / hard-safety stages

### 2. Quiz-Only / MedGemma Comparison Eval

Runner:

- [`evals/run_quiz_three_arm_eval.py`](/Users/annaesakova/aipm/halfFull/evals/run_quiz_three_arm_eval.py)

Default cohort:

- [`evals/cohort/nhanes_balanced_760.json`](/Users/annaesakova/aipm/halfFull/evals/cohort/nhanes_balanced_760.json)

Purpose:

- compare different input packages on the same sampled profiles
- understand how MedGemma performs alone versus with more context

Current arms:

1. `models_only`
2. `medgemma_only`
3. `medgemma_plus_bayesian`
4. `hybrid_top5`

Important input rules:

- `medgemma_only` now uses raw quiz answers only
- those answers are filtered to real quiz question IDs from [`frontend/src/data/quiz_nhanes_v2.json`](/Users/annaesakova/aipm/halfFull/frontend/src/data/quiz_nhanes_v2.json)
- this avoids sending opaque feature-engineered columns such as derived aliases or model-only fields
- `medgemma_plus_bayesian` adds human-readable follow-up Q/A derived from `bayesian_answers`
- that arm does **not** send LR values, posterior scores, or condition labels in the follow-up group

## What We Learned From The Quiz Eval

On a recent 15-profile sample:

- `models_only`: strongest recall
- `medgemma_only`: low recall and high healthy over-alert
- `medgemma_plus_bayesian`: same recall as quiz-only on that sample, but better calibration
- `hybrid_top5`: weak recall in the sampled run, partly dragged down by route failures in earlier iterations

Interpretation:

- quiz answers alone are not enough for MedGemma
- adding follow-up evidence helps reduce false alarms
- the current follow-up comparison still needs refinement because the cohort stores a full latent answer sheet, which can add noise beyond what a real user would see

## Local Setup

### 1. Start The App

```bash
cd /Users/annaesakova/aipm/halfFull/frontend
npm run dev
```

### 2. Add A Local Eval Secret

Add this to [`frontend/.env.local`](/Users/annaesakova/aipm/halfFull/frontend/.env.local):

```env
EVAL_MODE_SECRET=my_local_medgemma_eval_secret_2026
```

Then restart `npm run dev`.

### 3. Smoke-Test The Protected Route

```bash
curl -i http://127.0.0.1:3000/api/deep-analyze \
  -H "Content-Type: application/json" \
  -H "x-eval-mode-secret: my_local_medgemma_eval_secret_2026" \
  -X POST \
  -d '{
    "evalMode": "medgemma_only",
    "evalCandidateConditions": ["hypothyroidism", "sleep_disorder", "anemia"],
    "answers": {
      "age_years": 42,
      "gender": 2,
      "dpq040___feeling_tired_or_having_little_energy": 3,
      "slq050___ever_told_doctor_had_trouble_sleeping?": 1,
      "sld012___sleep_hours___weekdays_or_workdays": 5.5,
      "sld013___sleep_hours___weekends": 6.0,
      "huq010___general_health_condition": 4
    },
    "confirmedConditions": [],
    "clarificationQA": [],
    "useKNN": false
  }'
```

Success signals:

- `HTTP/1.1 200 OK`
- `x-deep-analyze-grounding-source: live_medgemma_success`
- `x-deep-analyze-synthesis-source: ...`
- `x-deep-analyze-rewrite-source: ...`

## Local Eval Commands

### Real Production-Path Eval

Dry-run:

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_llm_layer_eval.py --dry-run --n 12
```

Live run:

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_llm_layer_eval.py --n 20 --base-url http://127.0.0.1:3000
```

### Quiz / MedGemma Comparison Eval

Small local smoke:

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_quiz_three_arm_eval.py \
  --base-url http://127.0.0.1:3000 \
  --eval-secret my_local_medgemma_eval_secret_2026 \
  --sample-per-condition 1 \
  --multi-per-condition 0 \
  --healthy-n 3
```

Larger local run:

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_quiz_three_arm_eval.py \
  --base-url http://127.0.0.1:3000 \
  --eval-secret my_local_medgemma_eval_secret_2026 \
  --sample-per-condition 4 \
  --multi-per-condition 1 \
  --healthy-n 12
```

## Vercel Preview Workflow

### Required Environment Variables

On the preview deployment, set:

- `HF_API_TOKEN`
- `GROQ_API_KEY`
- `OPENAI_API_KEY` if you want the full fallback chain available
- `EVAL_MODE_SECRET`

### Preview Smoke Test

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_quiz_three_arm_eval.py \
  --base-url https://your-preview-deployment.vercel.app \
  --eval-secret your_eval_secret_here \
  --sample-per-condition 1 \
  --multi-per-condition 0 \
  --healthy-n 3
```

### Preview Real Run

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_quiz_three_arm_eval.py \
  --base-url https://your-preview-deployment.vercel.app \
  --eval-secret your_eval_secret_here \
  --sample-per-condition 4 \
  --multi-per-condition 1 \
  --healthy-n 12
```

## Output Files

Production-path eval:

- `evals/results/llm_layer_YYYYMMDD_HHMMSS.json`
- `evals/reports/llm_layer_YYYYMMDD_HHMMSS.md`
- `evals/reports/llm_layer_YYYYMMDD_HHMMSS_manual_review.md`

Quiz / MedGemma eval:

- `evals/results/quiz_three_arm_YYYYMMDD_HHMMSS.json`
- `evals/reports/quiz_three_arm_YYYYMMDD_HHMMSS.md`

## Troubleshooting For Teammates

These are the exact issues we hit while wiring this up.

### Problem: `npm run dev` fails from repo root

Symptom:

```text
npm error enoent Could not read package.json
```

Fix:

```bash
cd /Users/annaesakova/aipm/halfFull/frontend
npm run dev
```

### Problem: `python3: can't open file '.../evals/run_something.py'`

Cause:

- the command was run from `~` instead of the repo root

Fix:

```bash
cd /Users/annaesakova/aipm/halfFull
python3 evals/run_quiz_three_arm_eval.py ...
```

### Problem: `medgemma_only` returns `403`

Cause:

- missing `EVAL_MODE_SECRET` on the server
- or missing / mismatched `x-eval-mode-secret` header

Fix:

1. set `EVAL_MODE_SECRET` in the deployment or local `.env.local`
2. restart the local app if testing locally
3. pass `--eval-secret ...` to the runner

### Problem: eval runner crashes on missing BMI

Cause:

- some real cohort profiles have `demographics.bmi = null`

Fix already implemented:

- the runner backfills missing BMI from `nhanes_inputs.bmi`

### Problem: MedGemma was seeing opaque feature columns instead of real quiz answers

Cause:

- the initial runner reused the layer-1 raw-input builder for the live MedGemma arms

Fix already implemented:

- the runner now filters to canonical quiz question IDs from `quiz_nhanes_v2.json`
- model scoring still uses the engineered feature path, but MedGemma eval payloads do not

### Problem: `--dry-run` shows `0%` for live MedGemma arms

This is expected.

`--dry-run` only validates:

- cohort sampling
- local model scoring
- imports / path setup
- output report generation

It does **not** call `/api/deep-analyze`.

Use a real local or preview run to evaluate live MedGemma behavior.

## Suggested Team Workflow

1. Pull the latest branch with the protected `medgemma_only` mode and updated runner.
2. Confirm the app starts locally from `frontend/`.
3. Add `EVAL_MODE_SECRET` locally and smoke-test `/api/deep-analyze`.
4. Run a tiny local quiz eval.
5. Push the branch and let Vercel create a preview deployment.
6. Add `HF_API_TOKEN`, `GROQ_API_KEY`, `OPENAI_API_KEY` if needed, and `EVAL_MODE_SECRET` to the preview environment.
7. Run the same smoke test against the preview deployment.
8. Run a larger stratified benchmark once the smoke looks healthy.

## Current Recommendation

Use both evals:

- `run_llm_layer_eval.py` to evaluate the actual production-style route
- `run_quiz_three_arm_eval.py` to compare what MedGemma does with different input packages

For MedGemma-specific diagnosis quality, the next best comparison is:

1. quiz-only
2. quiz + realistically selected follow-up questions
3. quiz + selected follow-up + optional neutral lab summary

Avoid leaking:

- LR values
- posterior probabilities
- disease labels in the follow-up evidence

## Current Quiz-Only Vs Quiz-Plus-Bayesian Findings

On the recent 15-profile comparison run:

- `models_only`: `recall@3 = 50.0%`, `healthy_over_alert = 33.3%`, `neighbour_fp = 22.2%`
- `medgemma_only`: `recall@3 = 16.7%`, `healthy_over_alert = 100.0%`, `neighbour_fp = 25.0%`
- `medgemma_plus_bayesian`: `recall@3 = 16.7%`, `healthy_over_alert = 66.7%`, `neighbour_fp = 19.4%`
- `hybrid_top5`: `recall@3 = 8.3%`, `healthy_over_alert = 100.0%`, `neighbour_fp = 2.8%`

Interpretation:

- quiz-only MedGemma underperformed the local model stack by a wide margin
- adding Bayesian follow-up did **not** improve recall on that sample
- adding Bayesian follow-up **did** reduce false alarms on healthy and neighbouring-condition profiles

In plain language:

- `medgemma_only` found the right condition on `2/12` labeled disease cases
- `medgemma_plus_bayesian` also found the right condition on `2/12`
- but `medgemma_plus_bayesian` was less likely to invent extra diagnoses on cases that should not have them

### Side-By-Side Metric Table

| Arm | Run 1: Quiz Only / Hybrid Baseline | Run 2: Added `medgemma_plus_bayesian` | Change |
|---|---:|---:|---:|
| `models_only` recall@3 | 50.0% | 50.0% | 0.0 |
| `models_only` healthy_over_alert | 33.3% | 33.3% | 0.0 |
| `models_only` neighbour_fp | 22.2% | 22.2% | 0.0 |
| `medgemma_only` recall@3 | 16.7% | 16.7% | 0.0 |
| `medgemma_only` healthy_over_alert | 100.0% | 100.0% | 0.0 |
| `medgemma_only` neighbour_fp | 25.0% | 25.0% | 0.0 |
| `medgemma_plus_bayesian` recall@3 | not run | 16.7% | new arm |
| `medgemma_plus_bayesian` healthy_over_alert | not run | 66.7% | new arm |
| `medgemma_plus_bayesian` neighbour_fp | not run | 19.4% | new arm |
| `hybrid_top5` recall@3 | 8.3% | 8.3% | 0.0 |
| `hybrid_top5` healthy_over_alert | 100.0% | 100.0% | 0.0 |
| `hybrid_top5` neighbour_fp | 2.8% | 2.8% | 0.0 |

### Focused MedGemma Comparison

| Comparison | Recall@3 | Healthy Over-Alert | Neighbour FP |
|---|---:|---:|---:|
| `medgemma_only` | 16.7% | 100.0% | 25.0% |
| `medgemma_plus_bayesian` | 16.7% | 66.7% | 19.4% |
| Effect of adding Bayesian follow-up | no recall gain | better | better |

Source files:

- [`evals/results/quiz_three_arm_20260330_194150.json`](/Users/annaesakova/aipm/halfFull/evals/results/quiz_three_arm_20260330_194150.json)
- [`evals/results/quiz_three_arm_20260330_204050.json`](/Users/annaesakova/aipm/halfFull/evals/results/quiz_three_arm_20260330_204050.json)

### Why `medgemma_plus_bayesian` Helped Calibration But Not Recall

The likely reason is that the extra evidence made the model more cautious, but not more discriminative.

What we saw:

- MedGemma quiz-only often collapsed onto a generic fatigue cluster such as `iron_deficiency`, `sleep_disorder`, and `perimenopause`
- with follow-up evidence added, some of those generic false positives dropped away
- but the model still did not recover the truly correct condition for many kidney, liver, hepatitis, inflammation, or endocrine cases

Why this likely happened:

1. The cohort currently stores a full latent follow-up answer sheet for each profile.
   That means `medgemma_plus_bayesian` is receiving many more follow-up answers than a real user would actually get.
2. Those extra answers are human-readable now, but they are still broad and noisy.
3. So the model gets more evidence to say “be less certain,” but not necessarily cleaner evidence to say “this is kidney disease instead of sleep disorder.”

So the current takeaway is:

- follow-up evidence helps reduce over-calling
- follow-up evidence, as currently packaged, is not yet targeted enough to improve recall

### Next Recommended Improvement

The next evaluation refinement should be:

1. `quiz_only`
2. `quiz + realistically triggered follow-up only`
3. `quiz + realistically triggered follow-up + optional neutral lab summary`

This would better match the real product flow and should be a fairer test of whether follow-up evidence actually helps MedGemma identify the right condition.
