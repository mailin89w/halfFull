# Edge Cases And Safety Test Plan

## Purpose

This document lists the key edge cases the project should handle safely and predictably, especially when inputs are messy, ambiguous, incomplete, or broken. It also outlines how to test each case and the professional best practices to prepare for them.

The goal is not only to avoid crashes. The goal is to make sure the system:

- behaves consistently
- avoids misleading certainty
- avoids unnecessary alarm
- degrades gracefully when confidence or data quality is low

## Core Principle

The system should never confuse these states:

- healthy user with no meaningful fatigue problem
- symptomatic user with no confident disease match
- user with ambiguous or conflicting evidence
- user with broken, incomplete, or invalid input data

These states need distinct logic and distinct result-page behavior.

## Edge Cases To Cover

### 1. Totally healthy user with no fatigue problem

Expected behavior:

- show a calm low-concern result state
- do not surface unnecessary disease concern
- do not ask clarification questions
- provide simple guidance on when to re-check or seek care if symptoms change

How to test:

- run fully healthy synthetic profiles
- run healthy profiles with normal labs and low symptom burden
- verify no disease scare language appears

Best practices:

- create a dedicated "healthy / low concern" result state
- do not treat "no top disease" as the same thing by accident

### 2. User has fatigue, but all 11 model scores are below `0.4`

Expected behavior:

- acknowledge that symptoms are real
- clearly say no disease model is currently confident
- avoid fake specificity or forced diagnosis
- recommend next steps such as PCP follow-up, repeat assessment, or labs if appropriate

How to test:

- construct symptomatic profiles with broad fatigue features but no score above `0.4`
- verify the result page differs from the healthy-user page

Best practices:

- maintain a separate "symptoms present, no confident match" result state
- do not collapse this into healthy

### 3. Clarification answers lower a disease score below `0.4`

Expected behavior:

- disease confidence should drop cleanly
- ranking should update correctly
- stale disease messaging should disappear
- user should not see a condition still framed as strong if Bayesian reduced it

How to test:

- start from priors between `0.40` and `0.60`
- answer low-LR clarification options
- verify posterior drop, re-ranking, and result-page wording

Best practices:

- Bayesian update must be allowed to both increase and decrease confidence
- UI should reflect the latest posterior, not the initial trigger

### 4. Retrain models without any labs

Expected behavior:

- no-lab pathway remains functional
- system does not crash or silently over-impute
- predictions remain bounded and interpretable

How to test:

- evaluate each condition with all labs absent
- evaluate with partial labs absent
- compare no-lab and hybrid performance separately

Best practices:

- maintain explicit no-lab operating points
- report no-lab metrics independently from hybrid metrics

## Additional Product Edge Cases

### 5. Healthy user with one noisy high score

Expected behavior:

- avoid alarming result page from a single brittle false positive

How to test:

- create healthy profiles with one isolated high score

Best practices:

- require corroborating evidence before strong wording

### 6. Multiple medium scores, no clear winner

Expected behavior:

- say several possible contributors are present
- avoid pretending the top score is highly reliable

How to test:

- create clustered-score profiles such as `0.42`, `0.46`, `0.48`

Best practices:

- support ambiguous-result copy and ordering logic

### 7. All models score high

Expected behavior:

- do not create an "everything is wrong" result page
- rank and group conditions sensibly

How to test:

- create broad false-positive profiles

Best practices:

- cap recommendations
- group related conditions
- keep wording proportional to confidence

### 8. No disease triggers Bayesian clarification

Expected behavior:

- skip clarification entirely
- route directly to results

How to test:

- create profiles where every score is below trigger threshold

Best practices:

- never show an empty clarification screen

### 9. More than 5 diseases trigger Bayesian clarification

Expected behavior:

- ask only the top 5 suspect diseases
- use deterministic tie-breaking

How to test:

- create profiles with 6 to 8 triggered conditions

Best practices:

- keep prioritization stable and documented

### 10. Shared question reused across diseases

Expected behavior:

- ask the question once
- reuse the answer across all linked diseases

How to test:

- verify shared-question cases such as anemia and iron, liver and hepatitis, kidney and prediabetes

Best practices:

- use canonical question identity and evidence sharing

### 11. Clarification makes another disease more likely than the original trigger

Expected behavior:

- re-rank diseases after update
- reflect the new top disease correctly

How to test:

- create shared-answer cases where disease B overtakes disease A after clarification

Best practices:

- recompute affected diseases globally, not only the disease on the current screen

### 12. User abandons clarification flow midway

Expected behavior:

- partial answers persist
- flow is resumable
- no corrupt or duplicated state

How to test:

- reload after partial completion
- use browser back
- restore from saved session

Best practices:

- use idempotent saves and a resumable state machine

## Data And Input Edge Cases

### 13. Missing required demographics

Examples:

- missing age
- missing sex
- missing menopause-eligibility inputs

Expected behavior:

- fail gracefully
- request missing information if needed
- avoid unsafe inference

Best practices:

- validate before scoring

### 14. Impossible or contradictory answers

Examples:

- no fatigue but severe daytime sleep episodes
- male user with heavy periods

Expected behavior:

- invalid combinations should not crash the system
- disease logic should not rely blindly on impossible inputs

Best practices:

- validate contradictions
- ignore impossible features where appropriate
- log contradictions for analysis

### 15. Out-of-range labs or unit mismatch

Examples:

- negative ferritin
- impossible TSH
- units uploaded in a different convention

Expected behavior:

- reject or normalize safely
- never silently treat bad numeric input as real clinical evidence

Best practices:

- strict parsing
- explicit unit normalization
- impossible-value guards

### 16. Stale labs

Expected behavior:

- older labs should be down-weighted or routed to no-lab style guidance

How to test:

- evaluate fresh vs stale lab uploads

Best practices:

- implement lab recency gate

### 17. Sparse questionnaire

Expected behavior:

- avoid overconfident output when too much information is missing

Best practices:

- define minimum data sufficiency rules

### 18. Ineligible disease gates

Examples:

- perimenopause outside female 35 to 55 eligibility

Expected behavior:

- disease should be gated cleanly
- no meaningless Bayesian questions should be asked

Best practices:

- apply eligibility before ranking display and before clarification triggers

## Model And Scoring Edge Cases

### 19. Threshold mismatch between metadata and pipeline

Expected behavior:

- scoring thresholds should match the intended operating points

How to test:

- contract-test loaded thresholds against model metadata

Best practices:

- maintain one source of truth for thresholds

### 20. Model returns `NaN`, `inf`, or missing disease key

Expected behavior:

- system should fail closed, not crash
- broken score should not poison the whole ranking

Best practices:

- bound-check and validate all model outputs
- omit invalid outputs and log loudly

### 21. Calibration drift after retraining

Expected behavior:

- new models should not become less calibrated without explicit decision

How to test:

- compare Brier score and reliability before and after retraining

Best practices:

- calibration checks should be required for release

### 22. No-lab model behaves very differently from hybrid model

Expected behavior:

- differences should be measurable and understood

Best practices:

- maintain separate dashboards for `full` vs `hybrid`

### 23. Proxy model misuse

Example:

- menopause currently using the perimenopause model as proxy

Expected behavior:

- UI and evaluation should make proxy use explicit

Best practices:

- separate targets where possible
- until then, keep proxy QA explicit

## Bayesian-Specific Edge Cases

### 24. No answer mapping exists for a reused question

Expected behavior:

- missing mapping should not silently drop evidence

Best practices:

- unit-test every shared-question alias

### 25. Answer is already known from quiz, but Bayesian asks again

Expected behavior:

- system should prefill and skip the redundant question

Best practices:

- test quiz-prefill resolution for every mapped question

### 26. Duplicate evidence counted twice

Expected behavior:

- the same signal should not be applied once from quiz and again from clarification

Best practices:

- deduplicate evidence before LR multiplication

### 27. Extreme priors near 0 or 1

Expected behavior:

- posterior math should remain numerically stable

How to test:

- test priors such as `0.01`, `0.99`, and near-threshold priors

Best practices:

- use numerical stability guards and posterior caps carefully

### 28. Invalid LR table entries

Examples:

- missing answer option
- zero LR
- broken disease mapping

Expected behavior:

- invalid tables should be detected before runtime

Best practices:

- schema validation and startup checks

## Professional Test Strategy

### 1. Unit Tests

Cover:

- feature mapping
- disease eligibility gates
- threshold loading
- posterior update math
- shared-question reuse
- quiz-prefill logic

### 2. Integration Tests

Cover:

- quiz to model-runner to Bayesian to result page
- healthy, ambiguous, low-confidence, and high-trigger scenarios

### 3. End-To-End Tests

Cover:

- healthy user flow
- symptomatic but no confident disease flow
- one-disease clarification flow
- five-disease clarification flow
- refresh, back, and resume scenarios

### 4. Synthetic Cohort Testing

Best practice:

- keep both the original cohort and the latent `v2` cohort
- add a dedicated edge-case pack with hand-authored scenarios

### 5. Golden Case Fixtures

Best practice:

- maintain curated patient fixtures with expected rankings, posterior shifts, and result wording

### 6. Contract Tests

Best practice:

- every model must return bounded numeric scores
- every scoring response must include valid disease keys
- every threshold reference must resolve correctly

### 7. Regression Gates Before Release

Track at minimum:

- top-1 accuracy
- top-3 coverage
- over-alert rate
- calibration
- Bayesian delta
- no-lab performance
- clarification reuse correctness

### 8. Production Safeguards

Log and monitor:

- skipped questions
- invalid inputs
- missing labs
- empty rankings
- abnormal posterior changes
- model output validation failures

## Product And Safety Best Practices

### Never equate "no confident disease" with "healthy"

These are different user states and need different messaging.

### Never show more certainty than the scores support

If evidence is weak or conflicting, the language should reflect that.

### Make Bayesian updates reversible

Clarification should be allowed to lower confidence, not only increase it.

### Use deterministic fallback behavior

Broken or partial inputs should lead to predictable fallback logic, not undefined behavior.

### Separate clinical logic from UI wording

This helps keep safety messaging consistent even when ranking logic changes.

### Validate all external or generated data

Models, thresholds, LR tables, labs, and mapped quiz answers should all have explicit validation.

## Recommended Next Step

Convert this list into a formal QA matrix with:

- scenario ID
- description
- input fixture
- expected model behavior
- expected Bayesian behavior
- expected UI result state
- automated vs manual test owner

That will make it much easier to operationalize this into release criteria.
