# Threshold Quick Wins

Date: `2026-03-26`

Method:

- Used the current `600`-profile benchmark batch from the same eval set behind the latest report.
- Used the raw ML scores already captured in `evals/results/bayesian_20260326_221238.json`.
- Swept thresholds upward from the current deployed threshold for each condition.
- Evaluated:
  - precision
  - recall
  - flag rate
  - healthy-profile flag rate

Definition used for a "quick win":

- materially lower flag burden with modest recall loss, or
- clearly better precision without a large recall collapse

## Recommendations

| Condition | Current thr | Suggested thr | Why |
|---|---:|---:|---|
| inflammation | `0.30` | `0.40` first, maybe `0.50` | Best genuine quick win in the current sweep |
| anemia | `0.50` | `0.60` | Moderate quick win if we accept some recall loss |
| iron_deficiency | `0.15` | `0.20` optional | Not urgent, but a cleaner operating point if we want less flagging |
| sleep_disorder | `0.70` | `0.75` optional | Small cleanup only |
| hypothyroidism | `0.55` | no quick win | Raising threshold helps flag rate, but recall cost is too high |
| kidney_disease | `0.25` | no quick win | Very noisy, but threshold-only fix is not cheap on current cohort |
| prediabetes | `0.40` | no quick win | Precision barely improves before recall collapses |
| electrolyte_imbalance | `0.46` | no quick win | Threshold-only changes do not rescue it |
| perimenopause | `0.40` | no threshold fix | Model weakness, not threshold |
| liver | `0.10` | no threshold fix | Model is effectively broken |
| hepatitis | `0.10` | keep | Already strong on current benchmark |

## Best Threshold Moves

### inflammation

Current at `0.30`:

- precision `6.3%`
- recall `46.7%`
- flag rate `55.3%`
- healthy flag rate `41.7%`

Candidate `0.40`:

- precision `8.2%`
- recall `40.0%`
- flag rate `36.5%`
- healthy flag rate `16.7%`

Delta:

- precision `+1.9 pp`
- recall `-6.7 pp`
- flag rate `-18.8 pp`
- healthy flag rate `-25.0 pp`

Candidate `0.50`:

- precision `9.7%`
- recall `35.6%`
- flag rate `27.5%`
- healthy flag rate `8.3%`

Delta vs current:

- precision `+3.4 pp`
- recall `-11.1 pp`
- flag rate `-27.8 pp`
- healthy flag rate `-33.4 pp`

Recommendation:

- move to `0.40` first if we want the safer step
- move to `0.50` if reducing false alarms is the priority

### anemia

Current at `0.50`:

- precision `16.9%`
- recall `62.7%`
- flag rate `41.3%`
- healthy flag rate `4.2%`

Candidate `0.60`:

- precision `21.8%`
- recall `50.7%`
- flag rate `26.0%`
- healthy flag rate `0.0%`

Delta:

- precision `+4.9 pp`
- recall `-11.9 pp`
- flag rate `-15.3 pp`
- healthy flag rate `-4.2 pp`

Recommendation:

- good moderate cleanup if we can afford a recall drop from `62.7%` to `50.7%`

### iron_deficiency

Current at `0.15`:

- precision `53.3%`
- recall `100.0%`
- flag rate `12.5%`

Candidate `0.20`:

- precision `92.1%`
- recall `87.5%`
- flag rate `6.3%`

Delta:

- precision `+38.8 pp`
- recall `-12.5 pp`
- flag rate `-6.2 pp`

Recommendation:

- optional cleanup, not urgent
- only do this if we want a stricter operating point and are comfortable trading away perfect recall

### sleep_disorder

Current at `0.70`:

- precision `10.9%`
- recall `25.0%`
- flag rate `24.5%`

Candidate `0.75`:

- precision `13.1%`
- recall `20.3%`
- flag rate `16.5%`

Delta:

- precision `+2.2 pp`
- recall `-4.7 pp`
- flag rate `-8.0 pp`

Recommendation:

- minor cleanup only
- not a core fix

## Conditions That Do Not Have Cheap Threshold Wins

### hypothyroidism

Current at `0.55`:

- precision `12.2%`
- recall `75.0%`
- flag rate `61.5%`

At `0.60`:

- precision `13.3%`
- recall `66.7%`
- flag rate `50.0%`

Interpretation:

- some reduction in spam, but precision gain is small
- this is not a strong quick win

### kidney_disease

Current at `0.25`:

- precision `9.6%`
- recall `84.4%`
- flag rate `66.2%`

At `0.35`:

- precision `12.2%`
- recall `68.9%`
- flag rate `42.3%`

Interpretation:

- threshold increase does cut flags
- but recall cost is already large
- this needs better model separation, not just threshold tuning

### prediabetes

Current at `0.40`:

- precision `10.1%`
- recall `64.4%`
- flag rate `48.0%`

At `0.45`:

- precision `9.4%`
- recall `42.2%`
- flag rate `33.7%`

Interpretation:

- thresholding alone does not improve the tradeoff

### electrolyte_imbalance

Current at `0.46`:

- precision `6.9%`
- recall `51.1%`
- flag rate `55.5%`

At `0.50`:

- precision `7.6%`
- recall `46.7%`
- flag rate `46.0%`

Interpretation:

- only tiny precision improvement before recall falls apart

### perimenopause

Current at `0.40`:

- precision `13.1%`
- recall `17.3%`

Interpretation:

- already weak recall
- threshold is not the issue

### liver

Current at `0.10`:

- precision `0.0%`
- recall `0.0%`

Interpretation:

- threshold changes cannot rescue a dead model path

## Bottom Line

Actual quick wins on the current benchmark:

1. `inflammation: 0.30 -> 0.40` or `0.50`
2. `anemia: 0.50 -> 0.60`

Optional stricter cleanup:

3. `iron_deficiency: 0.15 -> 0.20`
4. `sleep_disorder: 0.70 -> 0.75`

Not enough by threshold alone:

- `kidney_disease`
- `hypothyroidism`
- `prediabetes`
- `electrolyte_imbalance`
- `perimenopause`
- `liver`

## What Else We Can Do Without Retraining

Threshold tuning is only one lever. On the current benchmark, several weak conditions do not have cheap threshold-only fixes, but there are still meaningful non-retraining improvements available.

### 1. Separate Bayesian Trigger From User-Facing Surfacing

Right now one threshold effectively controls too much:

- whether a condition enters Bayesian follow-up
- whether it is eligible to be surfaced to the user

Better pattern:

- a lower internal threshold to keep borderline-but-plausible conditions alive for Bayesian review
- a higher surfacing threshold for final user-facing alerts

Why this helps:

- preserves recall internally
- reduces false-positive user alerts
- especially useful for `kidney_disease`, `hypothyroidism`, `prediabetes`, and `inflammation`

### 2. Add Condition-Specific Suppression Rules

Several high-spam conditions are currently being surfaced on very generic fatigue overlap.

Examples:

- do not surface `kidney_disease` without at least one kidney-specific lab or symptom anchor
- do not surface `hypothyroidism` on fatigue alone
- do not surface `prediabetes` without glycemic or appetite/weight/nocturia support
- do not surface `inflammation` unless the pattern looks chronic, not just generic malaise

Why this helps:

- directly reduces precision collapse from generic symptoms
- likely more effective than threshold changes alone for `kidney_disease`, `prediabetes`, and `hypothyroidism`

### 3. Use Relative Rank / Score-Gap Suppression

A condition should not be surfaced just because it barely crosses threshold when:

- it sits very close to several stronger competing conditions
- and it lacks condition-specific supporting evidence

Suggested rule style:

- suppress condition if it is only marginally above threshold and within a small score gap of stronger mimics without corroborating evidence

Why this helps:

- reduces mimic-driven over-alerting
- especially relevant for:
  - `thyroid` vs `anemia`
  - `kidney_disease` vs `sleep_disorder`
  - `perimenopause` vs `anemia` / `sleep_disorder`

### 4. Require Two-Source Evidence For Weak Conditions

For weak or noisy conditions, require at least two of:

- model score above surfacing threshold
- Bayesian posterior above threshold
- direct lab abnormality or lab-group support
- condition-specific symptom rule

Best candidates:

- `kidney_disease`
- `hypothyroidism`
- `prediabetes`
- `inflammation`
- `electrolyte_imbalance`

Why this helps:

- improves precision without retraining
- turns KNN and Bayesian into confirmers rather than extra noise sources

### 5. Improve Bayesian Question Selection And Weighting

The current eval already shows that Bayesian updating is uneven:

- helps: `hepatitis`, `iron_deficiency`, `kidney_disease`, `hypothyroidism`, `prediabetes`
- hurts: `sleep_disorder`
- barely helps: `perimenopause`
- does not rescue: `liver`

Without retraining the base models, we can still:

- remove low-information questions
- reduce overweighted correlated questions
- ask fewer but more discriminative questions
- trigger questions only when the condition is genuinely in contention

This is one of the best non-retraining levers for improving post-Bayesian ranking.

### 6. Add More Hard Eligibility Gates

Eligibility gating is already used for `perimenopause`. More of it would help.

Examples:

- suppress `perimenopause` outside the appropriate age/sex window
- suppress `liver` unless liver-specific markers or history exist
- suppress `hepatitis` unless hepatitis/liver evidence exists
- suppress `sleep_disorder` when the case is dominated by metabolic or inflammatory evidence and lacks sleep anchors

Why this helps:

- avoids obviously implausible surfacing
- reduces high-confidence false positives on healthy and mimic-heavy profiles

### 7. Add Healthy-Profile Suppression

This is likely the single biggest product-level non-retraining win.

For healthy or low-signal profiles:

- require stronger evidence to surface any condition
- cap the number of surfaced conditions
- prefer soft monitoring language over multi-condition alert lists

Why this helps:

- directly targets the current healthy over-alert problem
- should reduce the system-level over-alert rate faster than per-condition threshold tuning alone

### 8. Let KNN Confirm, Not Spray

The current KNN layer improves recovery but reduces precision.

Better use:

- use KNN to confirm or strengthen plausible conditions
- use it to break ties or rescue missed lab groups
- do not let it freely add weak extra conditions without supporting evidence

Why this helps:

- preserves the current KNN coverage lift
- reduces the precision penalty

### 9. Post-Model Calibration / Score Shrinkage

Without retraining the classifiers themselves, we can still recalibrate their outputs operationally:

- monotonic remapping
- piecewise calibration
- percentile-based score shrinkage for known over-firing models
- model-specific score caps on weak signal patterns

Why this helps:

- better aligns scores with actual benchmark behavior
- especially helpful for chronically over-firing models

## Suggested No-Retraining Priority Order

If the goal is to improve metrics quickly without touching training:

1. healthy-profile suppression
2. separate internal Bayesian trigger from user-facing surfacing threshold
3. two-source evidence rules for weak models
4. Bayesian question cleanup for `sleep_disorder`, `perimenopause`, and `inflammation`
5. relative-rank / score-gap suppression
6. make KNN confirmatory rather than freely additive
7. post-model calibration / shrinkage

## Practical Takeaway

The current benchmark suggests:

- some conditions do benefit from threshold changes alone, especially `inflammation` and `anemia`
- several others are not mainly threshold problems anymore
- the biggest remaining non-retraining gains will come from gating, suppression, Bayesian cleanup, and better use of KNN
