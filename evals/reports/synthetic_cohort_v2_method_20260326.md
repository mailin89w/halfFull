# Synthetic Cohort V2 Method Summary

## Old Logic

The original synthetic cohort generator was good for early smoke testing, but it made the evaluation environment too clean:

- many profiles sat close to hand-authored disease centroids
- borderline users were often diluted positives instead of genuinely ambiguous cases
- competing mimic conditions were too weak
- Bayesian clarification answers were too deterministic
- missingness and contradiction patterns were limited

This produced two recurring problems:

- unrealistically separable diseases, including suspiciously strong recall in some categories
- low or zero information gain for questions that should have been clinically useful

## New Logic

The separate `v2` generator in [cohort_generator_v2_latent.py](/Users/annaesakova/aipm/halfFull/evals/cohort_generator_v2_latent.py) keeps the original generator untouched and builds a parallel cohort at [profiles_v2_latent.json](/Users/annaesakova/aipm/halfFull/evals/cohort/profiles_v2_latent.json).

Its core change is to generate latent patient state first, then emit observed quiz answers, Bayesian answers, and labs from that state with noise.

Main design shifts:

- latent-factor generation instead of direct disease templates
- stronger mimic and overlap cases
- more realistic ambiguity in borderline profiles
- noisy answer emission rather than deterministic symptom assignment
- preserved healthy and edge-case slices for control coverage

The generated latent cohort contains `600` profiles across `11` conditions, including `30` healthy controls, `20` edge cases, and `578` profiles with labs.

## What Changed

The practical effect of the new generator is that it tests the stack under more believable overlap:

- the ML layer must distinguish among competing explanations instead of obvious disease bundles
- the Bayesian layer sees clarification questions in settings where the answer actually matters
- low-value and redundant questions are easier to identify
- top-k ranking becomes a more meaningful metric than simple separability

This is intentionally a separate benchmark and does not replace the original cohort.

## Eval Results

### ML-only

| Metric | Old cohort | New latent cohort |
|---|---:|---:|
| Top-1 accuracy | 16.6% | 17.6% |
| Top-3 coverage | 37.8% | 42.2% |
| Healthy over-alert rate | 93.3% | 90.0% |

Reports:

- Old: [layer1_20260325_222624.md](/Users/annaesakova/aipm/halfFull/evals/reports/layer1_20260325_222624.md)
- New latent: [layer1_20260325_231306.md](/Users/annaesakova/aipm/halfFull/evals/reports/layer1_20260325_231306.md)

Interpretation:

- the base ML layer remains weak
- the new cohort is not just harsher; it is more overlapped and exposes ranking noise more honestly
- over-alerting is still a major issue

### Bayesian

| Metric | Old cohort | New latent cohort |
|---|---:|---:|
| Pre-update Brier | 0.2221 | 0.1570 |
| Post-update Brier | 0.2191 | 0.1124 |
| Brier delta | -0.0030 | -0.0446 |
| Top-5 coverage delta | +3.13 pp | +7.01 pp |
| Low-gain questions flagged | 24 | 13 |

Reports:

- Old: [bayesian_20260325_221003.md](/Users/annaesakova/aipm/halfFull/evals/reports/bayesian_20260325_221003.md)
- New latent: [bayesian_20260325_231751.md](/Users/annaesakova/aipm/halfFull/evals/reports/bayesian_20260325_231751.md)

Interpretation:

- the Bayesian layer helps on both cohorts
- the lift is much clearer on the latent `v2` cohort
- the new cohort produces more believable clarification scenarios and fewer low-value-question flags

## Bottom Line

The latent `v2` cohort is a better stress test for the current system. It makes the ML weaknesses more visible while also showing that the Bayesian layer provides meaningful value when cases are realistically ambiguous.
