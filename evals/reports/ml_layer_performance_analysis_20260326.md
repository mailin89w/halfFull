# ML Layer Performance Analysis Across Synthetic Cohorts

## Purpose

This note is intended for a downstream agent or teammate retraining the Layer 1 disease models. It compares model behavior on two synthetic cohorts:

- the original cohort used in earlier Layer 1 evaluations
- the separate latent-factor `v2` cohort introduced to better simulate overlap, mimic conditions, and noisy clarification signals

Primary source reports:

- Old cohort: [layer1_20260325_222624.md](/Users/annaesakova/aipm/halfFull/evals/reports/layer1_20260325_222624.md)
- New latent cohort: [layer1_20260325_231306.md](/Users/annaesakova/aipm/halfFull/evals/reports/layer1_20260325_231306.md)

## Executive Summary

The Layer 1 ML stack is not failing because every individual disease model has low recall. It is weak because the stack behaves like a broad, noisy detector rather than a discriminative ranking system.

Across both cohorts:

- top-1 accuracy is very low at `16.6%` to `17.6%`
- top-3 coverage is low at `37.8%` to `42.2%`
- healthy-user over-alerting is extreme at `93.3%` on the old cohort and `90.0%` on the latent cohort
- precision is poor for most conditions, often in the `1%` to `8%` range

The old cohort made several models look better than they are because it was more separable. The latent `v2` cohort exposes generalization weakness more honestly by adding overlap and mimic cases.

The most important retraining goal is not simply to preserve high recall. It is to make scores more discriminative, better calibrated, and less likely to fire on broad nonspecific presentations.

## Why Earlier "Strong Recall" Results Were Misleading

The earlier summary highlighting strong recall on 9 conditions was directionally true for the old cohort at each model's threshold, but incomplete.

High recall on the old cohort did not mean strong end-to-end performance because:

- recall ignores whether the model also fires on many wrong users
- recall ignores whether the correct disease is ranked first
- recall ignores whether healthy users are heavily over-alerted

Example from the old cohort:

- `hypothyroidism` recall was `100%`, but precision was only `4.5%` and flag rate was `91.7%`
- `prediabetes` recall was `95.0%`, but precision was only `3.3%` and flag rate was `95.2%`
- `sleep_disorder` recall was `100%`, but precision was only `4.7%` and flag rate was `89.3%`

Those are not strong classifiers. They are highly sensitive scorers with very poor specificity.

## Cohort-Level Comparison

### System Metrics

| Metric | Old cohort | New latent cohort | Interpretation |
|---|---:|---:|---|
| Top-1 accuracy | 16.6% | 17.6% | Very low on both; correct disease usually not ranked first |
| Top-1 accuracy, positives only | 13.4% | 17.1% | Still very low even when disease is present |
| Top-3 coverage | 37.8% | 42.2% | Too low for a useful triage shortlist |
| Healthy over-alert rate | 93.3% | 90.0% | Healthy users are almost always over-flagged |

### Interpretation

- The latent cohort did not collapse the ML layer. Instead, it revealed that the layer was already weak as a ranking system.
- Slightly better top-1 and top-3 on the latent cohort should not be interpreted as "better models." The cohort composition changed and created different overlap patterns.
- The common pattern across both cohorts is poor discrimination, not isolated threshold mistakes.

## Per-Condition Analysis

### 1. Hypothyroidism

Old cohort:

- recall `100.0%`
- precision `4.5%`
- flag rate `91.7%`
- mean target score `0.805`

New latent cohort:

- recall `90.0%`
- precision `3.6%`
- flag rate `83.2%`
- mean target score `0.602`

Assessment:

- strong signal capture, but specificity is extremely poor
- this model likely relies too heavily on broad fatigue/metabolic features
- it is one of the largest contributors to noisy multi-condition firing

Retraining priority:

- high
- optimize for discrimination against anemia, sleep disorder, and nonspecific fatigue states

### 2. Kidney Disease

Old cohort:

- recall `100.0%`
- precision `6.1%`
- flag rate `76.7%`

New latent cohort:

- recall `81.8%`
- precision `6.2%`
- flag rate `48.2%`

Assessment:

- this is one of the more stable models across cohorts
- it retains useful signal under harder overlap conditions
- precision is still too low for deployment

Retraining priority:

- medium-high
- preserve signal while reducing broad false positives

### 3. Sleep Disorder

Old cohort:

- recall `100.0%`
- precision `4.7%`
- flag rate `89.3%`

New latent cohort:

- recall `100.0%`
- precision `4.4%`
- flag rate `75.3%`

Assessment:

- recall stability suggests a strong generic signal
- low precision indicates the signal is too generic or thresholded too aggressively
- likely overreacting to fatigue and daytime impairment proxies

Retraining priority:

- high
- improve specificity against thyroid, anemia, and stress-related fatigue mimics

### 4. Prediabetes

Old cohort:

- recall `95.0%`
- precision `3.3%`
- flag rate `95.2%`

New latent cohort:

- recall `55.6%`
- precision `2.4%`
- flag rate `68.2%`

Assessment:

- large generalization drop under the latent cohort
- likely too dependent on broad metabolic or demographic correlates
- old-cohort success was probably optimistic

Retraining priority:

- high
- revisit features, calibration, and class boundary definition

### 5. Hepatitis

Old cohort:

- recall `85.7%`
- precision `40.0%`
- flag rate `10.0%`

New latent cohort:

- recall `0.0%`
- precision undefined
- flag rate `0.0%`

Assessment:

- most brittle model across cohorts
- this is a classic sign of overfitting to old synthetic assumptions or to a narrow feature pattern
- unlike the broad detectors above, this model appears under-sensitive when mimic overlap changes

Retraining priority:

- highest
- validate label logic, feature coverage, and whether the model learned cohort-specific artifacts

### 6. Inflammation

Old cohort:

- recall `15.0%`
- precision `4.5%`
- flag rate `11.2%`

New latent cohort:

- recall `27.8%`
- precision `4.1%`
- flag rate `20.5%`

Assessment:

- weak on both cohorts
- this is not just a threshold issue
- the target may be too heterogeneous, poorly labeled, or under-featured

Retraining priority:

- highest
- likely needs target redesign or feature redesign, not only retraining

### 7. Iron Deficiency

Old cohort:

- recall `0.0%`
- flag rate `0.0%`

New latent cohort:

- recall `0.0%`
- flag rate `0.0%`

Assessment:

- fully nonfunctional in both cohorts
- prior note in the report indicates the current formulation has a problematic female coefficient dynamic
- regardless of root cause, this model is not usable as-is

Retraining priority:

- highest
- inspect training labels, score formula, coefficient signs, thresholding, and any gating behavior before retraining

### 8. Electrolyte Imbalance

Old cohort:

- recall `76.0%`
- precision `4.4%`
- flag rate `72.7%`

New latent cohort:

- recall `20.0%`
- precision `1.1%`
- flag rate `60.3%`

Assessment:

- large degradation under the latent cohort
- behaves like a broad false-positive model on the old cohort and a weak model on the new cohort
- probably lacks robust disease-specific features

Retraining priority:

- high
- improve signal quality and sharpen negatives

### 9. Anemia

Old cohort:

- recall `92.0%`
- precision `5.7%`
- flag rate `66.8%`

New latent cohort:

- recall `60.0%`
- precision `3.5%`
- flag rate `56.8%`

Assessment:

- meaningful signal exists, but specificity and robustness are poor
- overlap with thyroid, sleep, and iron pathways appears unresolved

Retraining priority:

- medium-high
- retrain jointly with iron strategy to avoid duplicated or conflicting feature logic

### 10. Perimenopause and Menopause Proxy

Perimenopause old cohort:

- recall `70.0%`
- precision `6.9%`
- flag rate `33.8%`

Perimenopause new latent cohort:

- recall `88.9%`
- precision `8.5%`
- flag rate `31.5%`

Menopause proxy old cohort:

- recall `80.0%`
- precision `7.9%`

Menopause proxy new latent cohort:

- recall `55.6%`
- precision `5.3%`

Assessment:

- perimenopause itself is one of the better-performing models in relative terms
- the menopause proxy setup is structurally awkward because both tasks depend on the same model
- hard gating by age and sex may be masking underlying ranking issues

Retraining priority:

- medium
- consider separating target definitions instead of sharing one proxy model

## What The Two Cohorts Together Suggest

### Stable Signals

The conditions with some evidence of persistent signal are:

- kidney disease
- sleep disorder
- hypothyroidism
- perimenopause

These still need much better specificity, but they appear to contain real signal worth preserving.

### Brittle or Likely Overfit Signals

The conditions most sensitive to cohort-generation style are:

- hepatitis
- prediabetes
- electrolyte imbalance
- anemia

These are the strongest candidates for synthetic-overfitting or overreliance on generic correlates.

### Structurally Broken or Underdefined

- iron deficiency
- inflammation

These should be treated as redesign problems, not mere threshold-tuning problems.

## Implications For Retraining

### 1. Optimize For Ranking And Precision, Not Recall Alone

Do not use recall at current thresholds as the main success metric. It is already clear that high recall can coexist with unusable behavior.

Track at minimum:

- top-1 accuracy
- top-3 coverage
- per-condition AUROC or PR-AUC if available
- calibration
- healthy over-alert rate
- per-condition precision at selected recall points

### 2. Threshold Tuning Alone Is Not Enough

The current problem is not only threshold placement. In several models, precision is too low because the score distributions are not sufficiently separated.

Threshold tuning should come after retraining and recalibration, not instead of it.

### 3. Retrain Against Hard Negatives And Mimics

The most likely missing ingredient is better negative construction:

- thyroid vs anemia vs sleep
- kidney vs dehydration vs prediabetes
- hepatitis vs alcohol-related liver patterns vs nonspecific fatigue
- perimenopause vs sleep/stress/fatigue

### 4. Revisit Label Definitions

Some targets may be too broad or too weakly grounded:

- `hidden_inflammation` is probably too heterogeneous
- `iron_deficiency` may have label or formula issues
- proxying `menopause` with the `perimenopause` model is likely limiting both interpretation and retraining quality

### 5. Inspect Score Calibration Explicitly

The Bayesian layer improved substantially on the latent cohort, which suggests the ML priors contain useful directional signal but are not well calibrated or well ranked.

That means retraining should include:

- calibration review
- score distribution review on healthy users
- error analysis on cases with many simultaneous high scores

## Recommended Retraining Order

1. `iron_deficiency`
2. `inflammation`
3. `hepatitis`
4. `prediabetes`
5. `electrolyte_imbalance`
6. `hypothyroidism`
7. `sleep_disorder`
8. `anemia`
9. `kidney_disease`
10. `perimenopause` and menopause proxy split

## Bottom Line

The current Layer 1 stack contains some real disease signal, but it is not yet a strong triage layer. The dominant failure mode is low discrimination with extreme over-alerting. The old cohort obscured some of that weakness by being too separable. The new latent cohort is a better stress test and should be used alongside the old cohort for retraining and validation.
