# HalfFull Eval Pipeline — Technical Concept

## 1. Overview

The HalfFull evaluation pipeline is a synthetic, reproducible test harness for
validating the MedGemma-powered health condition assessment system. It generates
600 controlled synthetic user profiles, runs them through the same inference path
as real users, and scores the model's responses against ground-truth labels.

The pipeline is designed to run without real patient data, making it safe for
local development, CI/CD, and collaborative notebook environments (e.g. Google
Colab with a Cloudflare tunnel).

---

## 2. Cohort Design

### 2.1 Composition

| Segment | Count | Description |
|---------|-------|-------------|
| Per-condition positive | ~256 | 25 profiles × 11 conditions (adjusted by Bayesian prior — see below) |
| Per-condition borderline | ~165 | 15 profiles × 11 conditions — attenuated signal (mu × 0.55), ~15% carry a co-morbid second condition |
| Per-condition negative | ~110 | 10 profiles × 11 conditions — healthy distribution regardless of condition |
| Healthy controls | 30 | No condition; sub-threshold symptom scores throughout |
| Edge cases | 20 | 2–3 co-morbid conditions, max-blend symptom vectors + noise (sigma=0.10) |
| **Total** | **600** | |

The positive/borderline/negative split within each condition's 50 profiles is
adjusted by condition prevalence (from model metadata):

| Prevalence tier | Split |
|---|---|
| > 15% (e.g. inflammation 32%) | 20 pos / 20 borderline / 10 neg |
| 5–15% (default) | 25 pos / 15 borderline / 10 neg |
| < 5% (e.g. hepatitis 2.6%, kidney 3.5%) | 35 pos / 10 borderline / 5 neg |

### 2.2 Symptom Vector

Each profile carries a 10-dimensional symptom vector normalised to [0, 1]
(except `weight_change` which spans [-1, 1]):

- `fatigue_severity`
- `sleep_quality`
- `post_exertional_malaise`
- `joint_pain`
- `cognitive_impairment`
- `depressive_mood`
- `anxiety_level`
- `digestive_symptoms`
- `heat_intolerance`
- `weight_change`

Symptom means are **derived from actual model weights** at generation time:
`cohort_generator.py` loads each condition's trained `.joblib` file, extracts
logistic regression coefficients (or GB feature importances), maps them to the
10 symptom dimensions via `FEATURE_SYMPTOM_MAP`, and normalises to [0, 1].
NHANES 2017–2019 healthy population means are used as the baseline for negative
and healthy profiles.

Clinically linked symptom pairs use **correlated multivariate sampling**
(`numpy.random.multivariate_normal`) instead of independent per-symptom draws.
For example: fatigue↔post_exertional_malaise in anemia (r=0.72),
heat_intolerance↔sleep_quality in menopause (r=−0.78),
sleep_quality↔fatigue in sleep_disorder (r=−0.72).
Full correlation matrix documented in `evals/cohort/optimization_report.md`.

### 2.3 Lab Values

Approximately 40% of profiles include lab values (hybrid quiz path). Lab means
are shifted from healthy baselines for positive profiles based on which labs
are the highest-weighted features in each condition's model. Reference ranges
are sourced from `data/processed/normalized/nhanes_reference_ranges_used.csv`
where available; clinical literature fallbacks are marked `# FALLBACK` in the
generator. Labs included: TSH, ferritin, hemoglobin, CRP, vitamin D, HbA1c,
cortisol.

### 2.4 Reproducibility

All randomness is seeded (`--seed 42` default). The same seed always produces
the same 600 profiles. Profile IDs follow the schema `SYN-XXXXXXXX` (8 uppercase
alphanumeric chars).

---

## 3. Architecture

```
cohort_generator.py  ──────────────────────────────────────────────────────────
  (loads model .joblib files, derives symptom distributions from LR/GB weights,
   applies Bayesian prior splits, correlated multivariate sampling)
        |
        v
  profiles.json  (evals/cohort/)
        |
        ├──► score_profiles.py          [optional: score directly through LR/GB
        │     (evals/score_profiles.py)   models for calibration — no MedGemma]
        │           |
        │           v
        │     scoring_results.json + optimization_report.md
        │
        v
  ProfileLoader  (pipeline/profile_loader.py)
        |
        v
  QuizSimulatorAdapter  (pipeline/quiz_simulator_adapter.py)
        |       |
        |  [Lab Gate: hybrid path if lab_values present]
        |
        v
  MedGemmaAdapter  (pipeline/medgemma_adapter.py)
        |
        v
  ResponseParser  (pipeline/response_parser.py)
        |
        v
  ScoringEngine  (pipeline/scoring_engine.py)
        |
        v
  MetricsAggregator  (pipeline/metrics_aggregator.py)
        |
        v
  results/eval_run_TIMESTAMP.json
  reports/eval_report_TIMESTAMP.md
```

---

## 4. Eval Layers

### Layer 1 — Condition-First (default)

Each profile has exactly one primary target condition. Top-1 accuracy is
measured as whether the model's top-ranked condition matches the ground-truth
primary condition. This is the standard eval layer run in CI.

### Layer 4 — Co-morbidity (planned)

Edge-case profiles with 2-3 conflicting conditions. Scored with partial credit
for any condition appearing in the top-3 predictions. Not yet fully implemented.

---

## 5. Scoring Methodology

### 5.1 Top-1 Accuracy

The fraction of scorable profiles where the model's top-ranked condition ID
exactly matches `ground_truth.expected_conditions[0].condition_id`.

Profiles where JSON parsing failed are excluded from the denominator
(they are counted as parse failures, not wrong answers).

Negative profiles (where `expected_conditions` is empty) are excluded from
top-1 accuracy — they are counted only in hallucination detection.

### 5.2 Hallucination Rate

The fraction of profiles where at least one condition ID in the model's response
is not present in `config.CONDITION_IDS`. A hallucinated ID is any string that
is not one of the 11 known condition identifiers.

### 5.3 Parse Success Rate

The fraction of profiles where the raw MedGemma response was successfully parsed
into a valid JSON dict matching `RESPONSE_SCHEMA`.

### 5.4 Over-Alert Rate

On healthy-control profiles only: the fraction where any predicted condition has
`confidence > 0.5`. A well-calibrated model should return low-confidence
predictions (or no predictions) for healthy individuals.

---

## 6. DoD (Definition of Done) Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Cohort Top-1 Accuracy | >= 70% | Minimum viable clinical utility |
| Hallucination Rate | < 5% | Safety requirement: unknown conditions must not be invented |
| Parse Success Rate | >= 95% | Reliability requirement: structured output must be parseable |
| Over-Alert Rate | < 10% | False positive burden must remain clinically acceptable |

All four must pass for the CI gate to be green.

---

## 7. MedGemma Integration

MedGemma is accessed via `medgemma_client.py`, which posts to a configurable
HTTP endpoint (default: `http://localhost:8080`). In production, this endpoint
is a Colab notebook exposing MedGemma via a Cloudflare or ngrok tunnel.

The prompt instructs MedGemma to return exactly three ranked conditions as JSON.
The `MedGemmaAdapter` builds the prompt from quiz output and retries up to 3
times on network failures (2-second delay between attempts).

Set the endpoint URL via the `MEDGEMMA_ENDPOINT_URL` environment variable.

---

## 8. Schema Validation

All profiles conform to `evals/schema/profile_schema.json` (JSON Schema Draft 7).
The schema enforces:

- `profile_id` format: `^SYN-[A-Z0-9]{8}$`
- `demographics.age`: integer in [18, 85]
- `symptom_vector`: all values in [0, 1] except `weight_change` in [-1, 1]
- `ground_truth.expected_conditions`: array of `{condition_id, confidence, rank}`
- `profile_type`: one of `positive | borderline | negative | healthy | edge`

Schema validation runs at generation time (cohort_generator.py) and at load
time (ProfileLoader.load_all()).

---

## 9. Extension Points

- **New conditions**: Add to `config.CONDITION_IDS` and `CONDITION_PREFIX` in
  `cohort_generator.py`. The symptom distribution is derived automatically from
  the condition's trained model — add a `# FALLBACK` entry in
  `CONDITION_SYMPTOM_PROFILES` only if no model file exists. Regenerate with
  the same seed.
- **New symptoms**: Extend `SYMPTOMS` and `FEATURE_SYMPTOM_MAP` in
  `cohort_generator.py`. Update the JSON schema `symptom_vector.properties`
  and add the new symptom to all correlated sampling matrices.
- **Recalibration**: Run `python evals/score_profiles.py` after regeneration to
  check per-condition LR accuracy. Adjust `CONDITION_SYMPTOM_PROFILES` mu values
  for any condition outside the 60–92% target range. Document changes with
  `# RECALIBRATED` comments.
- **New eval layers**: Implement scoring logic in `ScoringEngine` and add a new
  `--layer` option to `run_eval.py`.
- **CI integration**: `run_eval.py` exits with code `0` if all DoD targets pass,
  `1` otherwise. Wire into GitHub Actions or any CI system.
