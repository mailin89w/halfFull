# Synthetic Cohort Improvement Analysis

## What The Current `evals/` Evidence Says

- The synthetic cohort is still too close to the model feature space it is testing. `evals/cohort_generator.py` derives symptom centroids directly from model coefficients and feature mappings, which creates leakage from training assumptions into evaluation profiles.
- The current reports already document this mismatch. `evals/reports/synthetic_cohort_v2_method_20260326.md` explicitly calls out disease centroids, diluted borderlines, weak mimics, deterministic Bayesian answers, and limited contradiction patterns.
- The strongest failure mode is not just class overlap. It is label-model mismatch plus unrealistic score geometry:
  - `iron_deficiency` has a structural female-coefficient problem and can dominate rankings on female profiles.
  - `menopause` is proxied through the `perimenopause` model.
  - `infection_inflammation` and `hidden_inflammation` are both present in the codebase, which means the target definition itself drifted while the eval stack still refers to a single inflammation concept.

## Why Synthetic Recall Swings From `0` To `100`

- The generator is partly optimizing around the same signals the models use, so some conditions become trivially recoverable while others collapse when their true evidence is missing or mis-specified.
- Several diseases rely on labs or direct questionnaire items in real NHANES, but the synthetic cohort sometimes replaces those with abstract symptom proxies. That is especially unstable for kidney disease, hepatitis, electrolyte imbalance, and inflammation.
- The Bayesian layer answers are hand-authored from disease strength heuristics. They are cleaner and more internally consistent than real users, so post-update lift depends heavily on whether the synthetic condition template happens to align with the model’s expected pattern.
- Missingness is still unrealistic. Real NHANES has module-level missingness, sex/age gating, and cycle-specific absence of variables. Synthetic profiles mostly do not.

## Most Important Improvement

Move the benchmark from fully synthetic generation to **real-NHANES anchored generation**:

1. Start from real NHANES participants and keep their actual demographics, questionnaire items, labs, and exam values.
2. Apply the same disease definitions used in `notebooks/disease_definitions.ipynb` and related scripts.
3. Only synthesize what NHANES does not directly contain:
   - eval symptom-vector compression
   - Bayesian follow-up answers
   - a small amount of answer noise / contradiction noise
4. Add calibrated missingness and contradiction patterns after anchoring to the real row, not before.

## Concrete Generator Changes

- Replace disease-centroid sampling with conditional sampling from real rows stratified by label, age band, sex, BMI, and cycle.
- Generate “mimic negatives” by selecting real rows with overlapping symptoms but different labels instead of scaling down positives.
- Use direct observed answers whenever NHANES contains the Bayesian signal, and reserve probabilistic completion only for gaps.
- Add disease-specific noise at the answer level, not at the latent-condition level:
  - low-probability answer flips
  - inconsistent duration reporting
  - partial symptom under-reporting
  - realistic module-level missingness
- Split evaluation into:
  - real anchored cohort
  - semi-synthetic completion cohort
  - stress-test synthetic edge cases

## Practical Risks To Fix In Parallel

- Unify inflammation targets: decide whether evals should use the broad `infection_inflammation` label or the stricter `hidden_inflammation` score.
- Stop treating menopause and perimenopause as interchangeable model targets.
- Revisit any generator logic derived from model coefficients, because it bakes current model behavior into the benchmark.
