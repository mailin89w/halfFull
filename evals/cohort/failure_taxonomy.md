# Failure Taxonomy

Date: `2026-03-26`

Sources used:

- `evals/results/layer1_20260326_220816.json`
- `evals/results/bayesian_20260326_221238.json`
- `evals/results/knn_layer_eval_three_layer_20260326.json`
- `evals/results/llm_layer_20260326_221107.json`
- `evals/results/llm_layer_20260326_153705.json`
- `evals/reports/llm_layer_combined_sections_20260326_161138_manual_review.md`
- Dev server logs from the live `http://localhost:3000` run

## Summary

Curated set size: `16` concrete failures

| Bucket | Count | Share | Why it matters | Proposed fix |
|---|---:|---:|---|---|
| wrong_condition_ranked_first | `6` | `37.5%` | Core ranking error before the LLM layer | Threshold retuning, mimic-heavy retraining, stronger condition-specific gating |
| sparse_data_overconfident | `4` | `25.0%` | Very high confidence on weak or healthy profiles | Confidence calibration, healthy suppression rules, abstention logic |
| overclaiming | `3` | `18.8%` | User-facing output claims too much from weak evidence | Require evidence citations per surfaced condition |
| vague_next_steps | `2` | `12.5%` | Output recommends doctors/tests without linking them tightly to evidence | Force condition-to-doctor and condition-to-test alignment in schema |
| hallucinated_condition_id | `1` | `6.3%` | Model added a diagnosis not supported by the allowlist | Hard allowlist validation before final response |

Slide-ready summary:

`62.5%` of curated failures were ranking or overconfidence failures before the LLM layer, so the biggest gain will come from threshold/calibration repair, not prompt polish. The live LLM path also has a separate operational blocker: current MedGemma/Groq batches fail at schema/rate-limit level before content quality can be judged.

## Bucket 1: wrong_condition_ranked_first

These are cases where the primary target was not ranked first by the core model stack.

1. `SYN-R0000026` (`anemia`)
   - Actual top-1: `perimenopause 0.8761`
   - Expected: anemia-led ranking
   - Likely issue: menstrual and fatigue features overpower the anemia-specific signal

2. `SYN-R0000255` (`inflammation`)
   - Actual top-1: `hypothyroidism 0.9254`
   - Expected: inflammation
   - Likely issue: fatigue / cold-intolerance-style features are being mapped to thyroid too aggressively

3. `SYN-R0000109` (`liver`)
   - Actual top-1: `perimenopause 0.9419`
   - Expected: liver
   - Likely issue: liver feature path is too weak, so generic fatigue-cycle proxies win

4. `SYN-R0000225` (`prediabetes`)
   - Actual top-1: `hypothyroidism 0.9496`
   - Expected: prediabetes
   - Likely issue: metabolic fatigue overlap is not being separated cleanly

5. `SYN-R0000161` (`kidney_disease`)
   - Actual top-1: `sleep_disorder 0.7556`
   - Expected: kidney disease
   - Likely issue: fatigue/nocturia-style overlap is pulling the case into sleep

6. `SYN-R0000353` (`perimenopause`)
   - Actual top-1: `sleep_disorder 0.6674`
   - Expected: perimenopause
   - Likely issue: sleep symptoms dominate perimenopause in the current feature space

Proposed fix:

- Retrain or recalibrate with more mimic-rich counterfactuals.
- Add stronger condition-specific gates for liver and perimenopause.
- Prevent generic fatigue clusters from dominating top-1 without corroborating features.

## Bucket 2: sparse_data_overconfident

These are profiles where the system shows very high confidence despite weak, missing, or healthy evidence.

1. `SYN-T0000027` (`healthy`)
   - Top-1: `perimenopause 0.9613`
   - Failure mode: healthy profile still looks highly diseased

2. `SYN-T0000031` (`healthy`)
   - Top-1: `hypothyroidism 0.9333`
   - Failure mode: very high endocrine confidence on a healthy control

3. `SYN-T0000045` (`healthy`, live batch)
   - Required model IDs entering the LLM: `thyroid, sleep_disorder, electrolytes`
   - Failure mode: the live path receives a strongly over-alerted healthy case before synthesis starts

4. `SYN-C0000030` (`hepatitis`, borderline)
   - Top-1: `perimenopause 0.9879`
   - Failure mode: borderline case gets near-certain confidence in the wrong condition

Proposed fix:

- Add abstain logic for healthy and borderline profiles.
- Cap confidence when the evidence comes from generic symptom clusters rather than direct markers.
- Recalibrate confidence after Bayesian update and before user-facing recommendations.

## Bucket 3: overclaiming

These are outputs that say more than the evidence supports, even when the final wording includes a disclaimer.

1. `SYN-HLT00009` (`healthy`) from archived manual review
   - Output IDs: `perimenopause, prediabetes, thyroid`
   - Next step: book an endocrinologist
   - Why this is overclaiming: a healthy-edge case turns into a specialist recommendation stack

2. `SYN-ANM00001` (`anemia`) from archived manual review
   - Output IDs: `sleep_disorder, kidney, inflammation`
   - User-facing wording suggested kidney issues based on weak, generic support
   - Why this is overclaiming: the surfaced conditions are broader than the evidence quality

3. `SYN-ELC00015` (`electrolyte_imbalance`) from archived manual review
   - Output IDs: `thyroid, sleep_disorder, anemia`
   - Electrolytes were dropped, but specialist urgency was still confident
   - Why this is overclaiming: confident action guidance without preserving the key model condition

Proposed fix:

- Require every surfaced condition to carry an evidence trace.
- Downrank conditions that are not supported by either direct markers or Bayes-confirming answers.
- Add a healthy-profile suppression rule before generating next steps.

## Bucket 4: vague_next_steps

These are outputs where the next-step advice is too generic or not well aligned with the actual differential.

1. `SYN-HEP00040` (`hepatitis`) from archived manual review
   - Next step: endocrinologist first, then PCP
   - Problem: the advice is not aligned with the hepatitis target and does not explain why liver/infectious workup is not prioritized

2. `SYN-PRD00024` (`prediabetes`) from archived manual review
   - Next step: GP or endocrinologist, maybe sleep specialist
   - Problem: this is broad and non-committal, with little condition-to-test specificity

Proposed fix:

- Make doctor recommendations condition-linked rather than generic.
- Enforce at least one named rationale per recommended doctor and per suggested test.
- Reject outputs where `nextSteps` does not mention the highest-confidence supported condition.

## Bucket 5: hallucinated_condition_id

This bucket was under-observed in the current live run because parse failed before condition extraction. Only one historical example was found in archived results.

1. `SYN-MNP00026` from `llm_layer_20260326_153705.json`
   - Required IDs: `perimenopause, thyroid`
   - Hallucinated ID: `sleep_disorder`
   - Why it matters: the model added a diagnosis outside the required set even though the output otherwise parsed cleanly

Proposed fix:

- Hard-check output diagnosis IDs against the allowlist before returning the response.
- If a non-allowlisted condition appears, either remove it automatically or fail the response and retry.

## Operational Failures Found In The Live LLM Path

These are not content-taxonomy items, but they are currently the main blockers to trustworthy end-to-end evaluation.

1. Groq rate limiting
   - Repeated `429` errors during `/api/deep-analyze`

2. Route instability
   - Repeated `503` after about `51-55s`

3. Schema conformance failures
   - Historical MedGemma grounding emitted a field with too many items for the schema
   - Historical Groq synthesis emitted invalid `recommendedDoctors[].priority`

Proposed fix:

- Add schema validation and trimming before accepting model outputs.
- Add retries with backoff for `429`.
- Fail fast with structured error capture instead of timing out the whole route.

## Recommended Order Of Fixes

1. Fix ranking and calibration first.
   - This addresses `62.5%` of the curated failures.

2. Add healthy-profile suppression and abstention.
   - This directly attacks alarm fatigue and sparse-data overconfidence.

3. Tighten doctor/test recommendation alignment.
   - This reduces overclaiming and vague next steps.

4. Stabilize the live LLM route.
   - Without this, end-to-end metrics will stay dominated by transport failures rather than medical-quality failures.
