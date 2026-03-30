# Slide Metrics Refresh

Date: `2026-03-26`

Source of truth:

- [final_eval_report.md](/Users/annaesakova/aipm/halfFull/evals/cohort/final_eval_report.md)
- [failure_taxonomy.md](/Users/annaesakova/aipm/halfFull/evals/cohort/failure_taxonomy.md)

## Slide 1

Title:

`Does HalfFull actually detect fatigue causes?`

Left-side copy:

- Evaluated on `600` synthetic user profiles
- `11` target conditions + healthy + multi-morbidity + edge cases
- Goal: detect conditions without over-alarming users
- Bayesian follow-up improves ranking, but healthy over-alert is still `79%`

Right-side table:

| Condition | Recall | Precision | Status |
|---|---:|---:|---|
| Hepatitis | `97 %` | `65 %` | `✅` |
| Iron Deficiency | `100 %` | `40 %` | `✅` |
| Hypothyroidism | `83 %` | `7 %` | `⚠️` |
| Kidney | `93 %` | `7 %` | `⚠️` |
| Prediabetes | `70 %` | `7 %` | `⚠️` |
| Anemia | `60 %` | `7 %` | `⚠️` |
| Electrolytes | `53 %` | `5 %` | `❌` |
| Inflammation | `45 %` | `4 %` | `❌` |
| Sleep Disorder | `31 %` | `6 %` | `❌` |
| Perimenopause | `18 %` | `9 %` | `❌` |
| Liver | `0 %` | `0 %` | `❌` |

Status legend used for this refresh:

- `✅` strongest current detectors
- `⚠️` useful recall but still too noisy
- `❌` not reliable enough for reviewer-facing claims

Presenter note:

- This is stricter and less flattering than the old slide.
- The biggest changes versus the old story are liver collapse, perimenopause weakness, and persistently high alarm burden.

Expanded version of the same table:

| Condition | Recall | Precision | Prevalence | Flag rate | Threshold | Status |
|---|---:|---:|---:|---:|---:|---|
| Hepatitis | `97 %` | `65 %` | `4.8 %` | `7.2 %` | `0.10` | `✅` |
| Iron Deficiency | `100 %` | `40 %` | `4.5 %` | `11.2 %` | `0.15` | `✅` |
| Hypothyroidism | `83 %` | `7 %` | `5.0 %` | `61.5 %` | `0.55` | `⚠️` |
| Kidney | `93 %` | `7 %` | `5.0 %` | `66.2 %` | `0.25` | `⚠️` |
| Prediabetes | `70 %` | `7 %` | `5.0 %` | `48.0 %` | `0.40` | `⚠️` |
| Anemia | `60 %` | `7 %` | `5.0 %` | `41.3 %` | `0.50` | `⚠️` |
| Electrolytes | `53 %` | `5 %` | `5.0 %` | `55.5 %` | `0.46` | `❌` |
| Inflammation | `45 %` | `4 %` | `4.8 %` | `55.3 %` | `0.30` | `❌` |
| Sleep Disorder | `31 %` | `6 %` | `4.8 %` | `24.5 %` | `0.70` | `❌` |
| Perimenopause | `18 %` | `9 %` | `8.3 %` | `16.5 %` | `0.40` | `❌` |
| Liver | `0 %` | `0 %` | `5.0 %` | `6.2 %` | `0.10` | `❌` |

Prevalence definition used here:

- positive target profiles for that condition divided by the full `600`-profile eval batch

## Slide 2

The old `ML only -> ML + Bayesian -> ML + Bayesian + KNN` bar chart should **not** be reused as-is.

Reason:

- The current full report gives:
  - Layer 1 on `600` profiles
  - Bayesian lift on `576` labeled non-healthy profiles
  - KNN lift on `340` lab-eligible profiles
- So a single 3-stage chart would mix different denominators.

### Recommended replacement

Use one slide with two compact charts or one chart plus two callouts.

Left-side copy:

- Metric: ranking and coverage lift across validated layers
- Bayesian layer gives the biggest ranking improvement
- KNN layer adds lab-group recovery, but with a precision tradeoff
- Do not present old “full pipeline” numbers from the small KNN pack as if they came from the full `600`-profile eval

Chart A title:

`Bayesian Layer Lift on Full Eval`

Chart A data:

| Stage | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| ML only | `14.2` | `38.7` | `59.7` |
| ML + Bayesian | `36.1` | `55.9` | `66.5` |

Chart A callout:

- Top-1 gain: `+21.9 pp`
- Top-3 gain: `+17.2 pp`
- Top-5 gain: `+6.8 pp`

Chart B title:

`KNN Lab-Signal Lift on Eligible Profiles`

Chart B data:

| Stage | Hit Rate | Exact Coverage | Mean Recall | Mean Precision |
|---|---:|---:|---:|---:|
| Condition-driven panels only | `54.4` | `24.4` | `37.7` | `33.2` |
| + KNN similarity | `59.7` | `28.5` | `42.9` | `26.5` |

Chart B callout:

- Hit-rate gain: `+5.3 pp`
- Exact-coverage gain: `+4.1 pp`
- Mean-recall gain: `+5.2 pp`
- Precision tradeoff: `-6.7 pp`

If you must keep a single chart:

- Use only the Bayesian chart above.
- Put the KNN numbers as a small right-side callout box.

## Slide 3

Title:

`What we learned — and what comes next`

Left column, `Key learnings`:

Box 1:

`Bayesian update is the rescue story`

- Raw Layer 1 top-1 on labeled profiles: `14.2%`
- After Bayesian follow-up: `36.1%`
- Biggest gains: hepatitis, iron deficiency, kidney, thyroid, prediabetes

Box 2:

`Healthy over-alert is still the biggest product risk`

- System over-alert rate on healthy profiles: `79.2%`
- Threshold tuning alone is not enough
- We need healthy suppression and abstention logic

Box 3:

`Some targets are still fundamentally weak`

- Liver is effectively non-functional in the current eval
- Perimenopause and sleep Bayesian questions need rewriting
- KNN helps recovery, but adds noise if left unconstrained

Right column, `Next steps`:

`Validation`

- Add missing reviewer metrics: ROC-AUC, raw calibration, neighbour consistency, questionnaire-only degradation

`Model improvements`

- Retrain or recalibrate weak targets, especially liver and perimenopause
- Rewrite low-information Bayesian questions for perimenopause and sleep

`System`

- Stabilize `/api/deep-analyze`
- Add schema guards, retry/backoff for `429`, and fail-fast structured errors

`Product`

- Healthy-profile suppression
- Bayesian-posterior-based recommendation threshold
- Condition-to-doctor and condition-to-test alignment

## Copy To Avoid Reusing

These old claims should be removed from the deck:

- `Over-alert rate reduced from 93% -> 63%`
- `Mean recall gain: +19.7 pp`
- `Exact coverage gain: +18.2 pp`
- Any “full pipeline” chart built from the small KNN-focused pack and presented as the current end-to-end result

## Suggested Speaker Framing

One-line version:

`The current full eval shows that Bayesian follow-up is genuinely improving ranking, KNN adds useful lab recovery, but the system still over-alerts healthy users and the live MedGemma/Groq layer is not yet stable enough for final performance claims.`

## Additional Slide

Title:

`What improves after Bayesian and KNN?`

Use this as an extra evidence slide after the models-only condition table.

### Table A: Per-condition after Bayesian

Recommended framing:

- This is the cleanest per-condition “after Bayesian” table because it uses the current full eval and stays within one denominator.
- Use rank/coverage metrics here, not recall/precision, because the Bayesian layer is evaluated as posterior reranking.

| Condition | Top-1 pre | Top-1 post | Top-3 pre | Top-3 post | Top-5 pre | Top-5 post |
|---|---:|---:|---:|---:|---:|---:|
| Hepatitis | `11.1 %` | `53.3 %` | `28.9 %` | `71.1 %` | `51.1 %` | `84.4 %` |
| Iron Deficiency | `0.0 %` | `70.0 %` | `15.0 %` | `87.5 %` | `55.0 %` | `87.5 %` |
| Kidney | `0.0 %` | `44.4 %` | `22.2 %` | `75.6 %` | `71.1 %` | `84.4 %` |
| Hypothyroidism | `65.0 %` | `83.3 %` | `80.0 %` | `93.3 %` | `96.7 %` | `98.3 %` |
| Prediabetes | `2.2 %` | `17.8 %` | `22.2 %` | `75.6 %` | `77.8 %` | `95.6 %` |
| Electrolytes | `0.0 %` | `42.2 %` | `46.7 %` | `60.0 %` | `64.4 %` | `68.9 %` |
| Anemia | `11.9 %` | `38.8 %` | `53.7 %` | `56.7 %` | `73.1 %` | `70.1 %` |
| Inflammation | `15.6 %` | `37.8 %` | `31.1 %` | `40.0 %` | `42.2 %` | `48.9 %` |
| Sleep Disorder | `29.7 %` | `21.9 %` | `95.3 %` | `57.8 %` | `100.0 %` | `92.2 %` |
| Perimenopause | `4.0 %` | `2.7 %` | `5.3 %` | `14.7 %` | `17.3 %` | `14.7 %` |
| Liver | `0.0 %` | `0.0 %` | `0.0 %` | `0.0 %` | `0.0 %` | `0.0 %` |

Suggested callout:

- Biggest Bayesian wins: hepatitis, iron deficiency, kidney, thyroid, prediabetes
- Bayesian hurts sleep and still fails to rescue liver

### Table B: KNN impact by condition

Recommended framing:

- This table is on the `340` KNN-eligible profiles only.
- It measures lab-group recovery, not condition ranking.

| Condition | N | Hit rate before | Hit rate after | Delta | Mean recall before | Mean recall after | Delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kidney | `39` | `53.8 %` | `66.7 %` | `+12.8 pp` | `34.2 %` | `48.3 %` | `+14.1 pp` |
| Liver | `22` | `36.4 %` | `50.0 %` | `+13.6 pp` | `23.5 %` | `32.6 %` | `+9.1 pp` |
| Electrolytes | `10` | `50.0 %` | `60.0 %` | `+10.0 pp` | `35.0 %` | `40.0 %` | `+5.0 pp` |
| Prediabetes | `32` | `43.8 %` | `53.1 %` | `+9.4 pp` | `25.5 %` | `33.3 %` | `+7.8 pp` |
| Sleep Disorder | `26` | `53.8 %` | `61.5 %` | `+7.7 pp` | `32.4 %` | `39.4 %` | `+7.1 pp` |
| Inflammation | `48` | `58.3 %` | `62.5 %` | `+4.2 pp` | `32.5 %` | `38.0 %` | `+5.5 pp` |
| Anemia | `33` | `60.6 %` | `63.6 %` | `+3.0 pp` | `42.4 %` | `44.9 %` | `+2.5 pp` |
| Hepatitis | `35` | `40.0 %` | `42.9 %` | `+2.9 pp` | `27.1 %` | `32.4 %` | `+5.2 pp` |
| Hypothyroidism | `41` | `46.3 %` | `46.3 %` | `+0.0 pp` | `30.7 %` | `30.7 %` | `+0.0 pp` |
| Iron Deficiency | `44` | `95.5 %` | `95.5 %` | `+0.0 pp` | `86.4 %` | `86.4 %` | `+0.0 pp` |
| Perimenopause | `10` | `0.0 %` | `0.0 %` | `+0.0 pp` | `0.0 %` | `0.0 %` | `+0.0 pp` |

Suggested callout:

- KNN helps most on kidney- and liver-related lab recovery
- It does little for thyroid and iron deficiency, where the control path is already strong or the KNN signal is not additive
- This layer still needs guardrails because aggregate precision falls
