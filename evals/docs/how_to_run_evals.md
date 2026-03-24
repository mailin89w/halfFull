# How to Run HalfFull Evals — Step-by-Step Guide

## Prerequisites

### Python Environment

Python 3.10 or later is required. Install eval dependencies:

```bash
cd /path/to/halfFull
pip install -r requirements_eval.txt
```

Or install manually:

```bash
pip install jsonschema>=4.17.0 tqdm>=4.64.0 numpy>=1.24.0 requests>=2.28.0
```

### MedGemma Endpoint (for live inference only)

For dry-run and `--no-medgemma` modes, no endpoint is needed. For live
inference, start the MedGemma Colab notebook and set:

```bash
export MEDGEMMA_ENDPOINT_URL="https://your-tunnel-url.trycloudflare.com"
```

---

## Step 1: Generate the Cohort

Run the cohort generator once. Output is written to `evals/cohort/profiles.json`
(gitignored — never commit patient-like data to the repository).

```bash
python evals/cohort_generator.py --seed 42
```

Expected output:
```
INFO: Generating cohort with seed=42 ...
INFO: Validating 600 profiles against schema ...
INFO: All profiles passed schema validation

Cohort generation complete (v2 — data-grounded)
─────────────────────────────────────────────────────
Total profiles:            600
Conditions:                11
Profiles/condition:        50  (split per Bayesian priors)
  └─ Multi-condition edge: 20
  └─ Co-morbid borderline: ~25
Healthy controls:          30
With lab values:           ~229  (38%)
Symptom distributions:     derived from model weights
Lab ranges:                from project data / fallback
Bayesian priors:           from project data
Co-morbidity pairs used:   19
Seed:                      42
Output: evals/cohort/profiles.json
─────────────────────────────────────────────────────
```

### Validate Without Writing

To check schema validity without writing the output file:

```bash
python evals/cohort_generator.py --seed 42 --validate
```

---

### Score Against the ML Models (Optional)

To check how well the generated symptom distributions trigger the right LR/GB
models — without MedGemma — run the standalone scoring script:

```bash
python evals/score_profiles.py
```

This scores all 600 profiles directly through all 11 models and writes
`evals/cohort/scoring_results.json`. See `evals/cohort/optimization_report.md`
for an explanation of the results and known structural constraints.

---

## Step 2: Dry Run (Validate Pipeline Imports)

Verify the pipeline loads profiles correctly without running any inference:

```bash
python evals/run_eval.py --dry-run
```

To sample a small number of profiles:

```bash
python evals/run_eval.py --dry-run --n 10
```

---

## Step 3: Run Without MedGemma (Fast Iteration)

The `--no-medgemma` flag runs the full pipeline except inference. Useful for
testing scoring logic and report generation:

```bash
python evals/run_eval.py --no-medgemma --n 50
```

Results and a Markdown report will be written to `evals/results/` and
`evals/reports/`.

---

## Step 4: Run a Targeted Eval

Evaluate only positive profiles for a specific condition:

```bash
python evals/run_eval.py --condition menopause --type positive --no-medgemma
```

Evaluate all profiles for hypothyroidism:

```bash
python evals/run_eval.py --condition hypothyroidism --no-medgemma
```

Evaluate only healthy controls:

```bash
python evals/run_eval.py --type healthy --no-medgemma
```

---

## Step 5: Full Eval with Live MedGemma

Ensure `MEDGEMMA_ENDPOINT_URL` is set, then run:

```bash
python evals/run_eval.py --layer 1
```

Or evaluate a sample of 100 profiles:

```bash
python evals/run_eval.py --n 100 --seed 42
```

---

## Reading the Results

### JSON Results File

Located at `evals/results/eval_run_YYYYMMDD_HHMMSS.json`. Structure:

```json
{
  "report": {
    "run_id": "run_20260323_120000",
    "n_profiles": 600,
    "cohort_top1_accuracy": 0.72,
    "hallucination_rate": 0.01,
    "parse_success_rate": 0.98,
    "over_alert_rate": 0.07,
    "dod_pass": true,
    "dod_checks": { ... },
    "per_condition": { ... },
    "by_quiz_path": { ... }
  },
  "results": [ ... ]
}
```

### Markdown Report

Located at `evals/reports/eval_report_YYYYMMDD_HHMMSS.md`. Contains:

- Cohort summary table
- DoD checks (PASS/FAIL per metric)
- Per-condition top-1 accuracy breakdown
- Results split by quiz path (full vs. hybrid)

### DoD Table in Terminal

The DoD summary is always printed to stdout at the end of a run:

```
============================================================
 DoD Summary
============================================================
Metric                              Target    Actual  Status
------------------------------------------------------------
cohort_top1_accuracy                   70%     72.1%    PASS
hallucination_rate                      5%      1.0%    PASS
parse_success_rate                     95%     98.0%    PASS
over_alert_rate                        10%      6.7%    PASS
------------------------------------------------------------
 ALL DoD TARGETS MET
============================================================
```

Exit code `0` = all DoD targets met. Exit code `1` = one or more failed.

---

## Regenerating with a Different Seed

```bash
python evals/cohort_generator.py --seed 123 --output evals/cohort/profiles_seed123.json
python evals/run_eval.py --dry-run  # uses default profiles.json
```

---

## Troubleshooting

### "Profiles file not found"

The cohort has not been generated yet. Run:
```bash
python evals/cohort_generator.py --seed 42
```

### "jsonschema not installed"

```bash
pip install jsonschema
```

### "MedGemma unreachable after 3 attempts"

- Check that the Colab notebook is running and the tunnel URL is active
- Verify `MEDGEMMA_ENDPOINT_URL` is set correctly
- Use `--no-medgemma` flag for local testing without inference

### Profile validation error

If a profile fails schema validation after regeneration, the schema or
generator may be out of sync. Check that `profile_schema.json` and
`cohort_generator.py` agree on symptom ranges and required fields.

### Low per-condition accuracy in `score_profiles.py`

If `scoring_results.json` shows a condition below 60% top-1 accuracy, increase
the `mu` for its highest-weighted symptoms in `CONDITION_SYMPTOM_PROFILES` by
0.10–0.15 and regenerate. Document changes with `# RECALIBRATED` comments.
See `evals/cohort/optimization_report.md` for known structural constraints that
cannot be resolved through generator tuning.

---

## CI Integration

Add to your CI workflow (e.g., GitHub Actions):

```yaml
- name: Generate eval cohort
  run: python evals/cohort_generator.py --seed 42

- name: Run eval (no-medgemma mode)
  run: python evals/run_eval.py --no-medgemma
  # Exit code 0 = DoD pass, 1 = DoD fail
```

For live MedGemma CI, set `MEDGEMMA_ENDPOINT_URL` as a GitHub Actions secret.
