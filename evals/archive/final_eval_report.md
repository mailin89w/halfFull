# Final Eval Report

Date: `2026-03-26`

## Scope

This report uses the current split eval stack rather than the legacy `evals/run_eval.py` path, because the current stack is now spread across:

- `evals/run_layer1_eval.py`
- `evals/run_bayesian_eval.py`
- `evals/run_knn_layer_eval.py`
- `evals/run_llm_layer_eval.py`

Runs used in this report:

- Layer 1, full cohort: `evals/results/layer1_20260326_220816.json`
- Bayesian, full cohort: `evals/results/bayesian_20260326_221238.json`
- KNN / cluster layer, eligible subset: `evals/results/knn_layer_eval_three_layer_20260326.json`
- Live MedGemma + Groq, 10 challenging cases: `evals/results/llm_layer_20260326_221107.json`
- Reviewer metric reference: `/Users/annaesakova/Downloads/halffull_eval_metrics_reference.html.pdf`

Evaluation plan actually executed:

- `600` profiles ran through Layer 1 and Bayesian.
- `340` lab-eligible profiles ran through the KNN layer.
- `10` challenging profiles ran through the live MedGemma + Groq path.
- The live path was intentionally limited to `10` because it depends on the app route and external model providers.

## Passed / Failed DoD

| Check | Target | Actual | Status | Notes |
|---|---:|---:|---|---|
| Layer 1 batch completes on all 600 profiles | clean run | `600/600` | PASS | `n_scoring_errors = 0` |
| ML top-1 accuracy | `>= 70%` | `16.3%` | FAIL | Current benchmark is much harder than the legacy cohort |
| Parse success rate | `>= 95%` | `0.0%` | FAIL | Live 10-case MedGemma + Groq batch failed before parse |
| Hallucination rate | `< 5%` | `0.0%` | PASS | On current live 10-case batch only |
| Over-alert rate on healthy profiles | `< 10%` | `79.2%` | FAIL | Alarm burden is far too high |
| `final_eval_report.md` saved | yes | yes | PASS | This file |
| `failure_taxonomy.md` saved | yes | yes | PASS | Companion file |

Bottom line: the eval infrastructure ran, but the product-level DoD does not pass.

## Reviewer Checklist From The PDF

| Metric from reference PDF | Status | What we have now |
|---|---|---|
| ML ROC-AUC per condition | MISSING | Not emitted by current runner |
| Recall at operating threshold | MEASURED | Present per condition in Layer 1 report |
| Precision at threshold | MEASURED | Present per condition in Layer 1 report |
| ML calibration / Brier | PARTIAL | Bayesian pre/post Brier is measured, raw ML per-condition calibration is not |
| Top-5 coverage rate | PARTIAL | Measured pre/post Bayesian and in KNN subset, but not emitted by current Layer 1 runner as a headline metric |
| Miss rate at threshold | PARTIAL | Can be inferred from recall, not reported in the severity-tier format from the PDF |
| Over-alert rate | MEASURED | `79.2%` system-level |
| LLM condition-list match | MEASURED | `0.0%` on current live 10-case run |
| LLM hallucination rate | MEASURED | `0.0%` on current live 10-case run |
| Urgency calibration | PARTIAL | Historical manual review exists; current live run could not be reviewed because parse failed |
| LLM delta vs models only | BLOCKED | Live parse failures prevent meaningful delta measurement |
| Questionnaire-only degradation | MISSING | Not run in this batch |
| Bayesian posterior calibration | MEASURED | Improved |
| Bayesian coverage delta | MEASURED | Improved |
| Bayesian question information gain | MEASURED | `24` questions flagged as low-value candidates |
| Bayesian order independence | MEASURED | Pass |
| Cluster extended lab precision | PARTIAL | Proxy precision available; no medical-review audit yet |
| Cluster coverage delta | MEASURED | Improved |
| Neighbour label consistency | MISSING | Not instrumented yet |

## Layer-By-Layer Headline Metrics

Important denominator note:

- Layer 1 is on `600` profiles.
- Bayesian layer comparisons below use `576` labeled non-healthy profiles for rank metrics and `534` triggered profiles for the official coverage-delta metric.
- KNN metrics use `340` lab-eligible profiles only.
- Live MedGemma + Groq uses `10` challenging profiles only.

| Layer comparison | Metric | Before | After | Delta | Notes |
|---|---:|---:|---:|---:|---|
| Layer 1 -> Bayesian | top-1 hit rate | `14.2%` | `36.1%` | `+21.9 pp` | Non-healthy labeled profiles only |
| Layer 1 -> Bayesian | top-3 coverage | `38.7%` | `55.9%` | `+17.2 pp` | Non-healthy labeled profiles only |
| Layer 1 -> Bayesian | top-5 coverage | `59.7%` | `66.5%` | `+6.8 pp` | Non-healthy labeled profiles only |
| Bayesian official triggered subset | top-5 coverage | `60.7%` | `67.4%` | `+6.7 pp` | Matches the metric spec for triggered cases |
| Layer 2 -> Layer 3 KNN | hit rate | `54.41%` | `59.71%` | `+5.29 pp` | Lab-eligible subset only |
| Layer 2 -> Layer 3 KNN | exact coverage | `24.41%` | `28.53%` | `+4.12 pp` | Lab-eligible subset only |
| Layer 2 -> Layer 3 KNN | mean recall | `37.73%` | `42.91%` | `+5.18 pp` | Lab-eligible subset only |
| Layer 2 -> Layer 3 KNN | mean precision | `33.16%` | `26.48%` | `-6.69 pp` | Improvement comes with extra noise |
| Live KNN -> MedGemma/Groq | parse success | n/a | `0.0%` | blocked | No reliable downstream comparison possible |

## Layer 1 Results

Overall Layer 1 metrics:

- `top1_accuracy = 16.32%`
- `positives_top1_accuracy = 13.37%`
- `top3_coverage = 41.32%`
- `over_alert_rate = 79.17%`
- `n_scoring_errors = 0`

Per-condition Layer 1 performance:

| Condition | Top-1 | Top-3 | Recall @ threshold | Precision @ threshold | Flag rate |
|---|---:|---:|---:|---:|---:|
| anemia | `22.4%` | `58.2%` | `60.0%` | `7.3%` | `41.3%` |
| electrolyte_imbalance | `0.0%` | `48.9%` | `53.3%` | `4.8%` | `55.5%` |
| hepatitis | `15.6%` | `31.1%` | `96.6%` | `65.1%` | `7.2%` |
| hypothyroidism | `58.3%` | `88.3%` | `83.3%` | `6.8%` | `61.5%` |
| inflammation | `15.6%` | `33.3%` | `44.8%` | `3.9%` | `55.3%` |
| iron_deficiency | `10.0%` | `27.5%` | `100.0%` | `40.3%` | `11.2%` |
| kidney_disease | `0.0%` | `20.0%` | `93.3%` | `7.0%` | `66.2%` |
| liver | `4.4%` | `8.9%` | `0.0%` | `0.0%` | `6.2%` |
| perimenopause | `1.3%` | `6.7%` | `18.0%` | `9.1%` | `16.5%` |
| prediabetes | `8.9%` | `33.3%` | `70.0%` | `7.3%` | `48.0%` |
| sleep_disorder | `29.7%` | `79.7%` | `31.0%` | `6.1%` | `24.5%` |

Main Layer 1 problems:

- Healthy false alarms are the dominant blocker. `19/24` healthy profiles were over-alerted.
- Liver is effectively non-functional in this batch: `0%` recall and `4.4%` top-1.
- Perimenopause is badly confounded by anemia, thyroid, and sleep.
- Kidney and hypothyroidism are highly sensitive but extremely low precision.
- Hepatitis is the one condition that currently behaves like a usable disease-specific detector.

## Bayesian Layer Results

Headline Bayesian metrics:

- Posterior calibration improved:
  - `pre_brier = 0.1821`
  - `post_brier = 0.1389`
  - `delta = -0.0433`
- Triggered-case calibration improved even more:
  - `triggered_pre_brier = 0.3524`
  - `triggered_post_brier = 0.2503`
  - `delta = -0.1021`
- Triggered-case top-5 coverage improved from `60.7%` to `67.4%` (`+6.7 pp`)
- Order independence passed with effectively zero posterior variance across tested permutations

Per-condition Bayesian effect:

| Condition | Top-1 pre | Top-1 post | Top-3 pre | Top-3 post | Top-5 pre | Top-5 post |
|---|---:|---:|---:|---:|---:|---:|
| anemia | `11.9%` | `38.8%` | `53.7%` | `56.7%` | `73.1%` | `70.1%` |
| electrolyte_imbalance | `0.0%` | `42.2%` | `46.7%` | `60.0%` | `64.4%` | `68.9%` |
| hepatitis | `11.1%` | `53.3%` | `28.9%` | `71.1%` | `51.1%` | `84.4%` |
| hypothyroidism | `65.0%` | `83.3%` | `80.0%` | `93.3%` | `96.7%` | `98.3%` |
| inflammation | `15.6%` | `37.8%` | `31.1%` | `40.0%` | `42.2%` | `48.9%` |
| iron_deficiency | `0.0%` | `70.0%` | `15.0%` | `87.5%` | `55.0%` | `87.5%` |
| kidney_disease | `0.0%` | `44.4%` | `22.2%` | `75.6%` | `71.1%` | `84.4%` |
| liver | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` |
| perimenopause | `4.0%` | `2.7%` | `5.3%` | `14.7%` | `17.3%` | `14.7%` |
| prediabetes | `2.2%` | `17.8%` | `22.2%` | `75.6%` | `77.8%` | `95.6%` |
| sleep_disorder | `29.7%` | `21.9%` | `95.3%` | `57.8%` | `100.0%` | `92.2%` |

Interpretation:

- Bayesian updating is a real win for hepatitis, iron deficiency, kidney disease, prediabetes, electrolyte imbalance, and thyroid.
- Liver does not move at all, which means the current question set is not supplying useful evidence.
- Sleep disorder gets worse after update, which means its questions are likely correlated with mimics or weighted incorrectly.
- Perimenopause gains a little at top-3 but worsens at top-1 and top-5, so those questions are still misaligned.

Question information gain audit:

- `24` questions were flagged as candidates for removal or rewrite.
- Most concerning low-value questions:
  - `peri_q2 = -0.0673 bits`
  - `peri_q2b = -0.0406 bits`
  - `peri_q5 = -0.0296 bits`
  - `peri_q4 = -0.0261 bits`
  - `anemia_q5 = -0.0127 bits`
  - `sleep_q3 = -0.0024 bits`
  - `liver_q5 = -0.0003 bits`
- Best-performing questions:
  - `anemia_q1 = 0.0885 bits`
  - `iron_q3 = 0.0900 bits`
  - `iron_q5 = 0.1249 bits`
  - `liver_q4 = 0.1382 bits`, but only `n_asked = 1`, so not robust

## KNN / Cluster Layer Results

KNN summary on the `340` eligible profiles:

- `control_hit_rate = 54.41%`
- `treatment_hit_rate = 59.71%`
- `delta_hit_rate = +5.29 pp`
- `control_exact_coverage = 24.41%`
- `treatment_exact_coverage = 28.53%`
- `delta_exact_coverage = +4.12 pp`
- `control_mean_recall = 37.73%`
- `treatment_mean_recall = 42.91%`
- `control_mean_precision = 33.16%`
- `treatment_mean_precision = 26.48%`
- `profiles_with_knn_signal = 226`
- `profiles_improved_by_knn = 28`

Profile-type breakdown:

| Profile type | Count | Control hit rate | KNN hit rate | Improved rate |
|---|---:|---:|---:|---:|
| borderline | `78` | `55.1%` | `57.7%` | `2.6%` |
| edge | `17` | `76.5%` | `76.5%` | `0.0%` |
| negative | `48` | `54.2%` | `60.4%` | `10.4%` |
| positive | `197` | `52.3%` | `58.9%` | `10.7%` |

Main KNN tradeoff:

- KNN helps recovery of missed lab groups.
- KNN also injects low-specificity extras, especially `kidney` and `lipids`.
- That is why coverage and recall improve while precision drops by `6.69 pp`.

Examples of real KNN improvements:

- `SYN-R0000039`: expected `kidney + liver_panel`; control only suggested `liver_panel`; KNN added `kidney`.
- `SYN-R0000094`: expected `cbc + iron_studies + kidney + liver_panel`; control missed `kidney`; KNN restored it.
- `SYN-R0000126`: expected `kidney + thyroid`; control missed `kidney`; KNN added it.

## Live MedGemma + Groq Results

Current live batch:

- `10` challenging cases
- `parse_success_rate = 0.0%`
- `condition_list_match_rate = 0.0%`
- `hallucination_rate = 0.0%`
- `manual_review_count = 0`

This is not a reasoning-quality failure first. It is a serving / schema failure first.

Observed live blockers from the dev server logs:

- MedGemma grounding previously emitted schema-invalid payloads such as `supportedSuspicions` with `4` items when the schema allows `3`.
- Current runs hit repeated Groq `429` responses.
- The app route returned `POST /api/deep-analyze 503` after roughly `51-55s`.
- Because the route failed before final structured output, no downstream section checks could pass.

Current 10-case live pack covered:

- `5` multi-signal cases
- `2` borderline cases
- `1` healthy-edge case
- `1` dense-signal case
- `1` strong-single case

Interpretation:

- The LLM layer is not currently evaluable as a medical synthesis layer because it is failing at transport/schema level.
- Fixing prompt or ranking alone will not change the live metrics until schema and rate-limit handling are stabilized.

## Threshold And Risk Tradeoff

Requested product question: what threshold should trigger recommendations for further tests?

Current answer:

- The current raw Layer 1 thresholds are not safe enough for a reviewer-facing recommendation policy.
- They preserve recall on some conditions, but the healthy over-alert rate of `79.2%` makes the current trigger logic unacceptable.

Provisional threshold policy for the next eval cycle:

1. Use Bayesian posterior, not raw ML score, as the default trigger variable.
2. Trigger a condition-specific test recommendation when:
   - posterior `>= 0.65`, or
   - posterior `>= 0.45` and there is corroborating lab-group evidence from KNN or a direct abnormal marker.
3. Suppress tertiary conditions on healthy or low-signal cases unless they are supported by both:
   - top-5 ranking, and
   - at least one condition-specific Bayes answer or direct lab abnormality.

Why this tradeoff is better:

- It keeps the high-recall benefit of Bayesian updates on hepatitis, kidney, thyroid, iron deficiency, and prediabetes.
- It reduces the current tendency to over-trigger on healthy and mimic-heavy profiles.
- It prevents raw ML confounding from directly turning into user-facing test recommendations.

This threshold policy is still provisional. It should be rechecked after:

- liver and perimenopause fixes,
- sleep Bayes question retuning,
- and live MedGemma/Groq stabilization.

## Main Problems Discovered

1. Layer 1 confounding is the largest offline blocker.
   - Perimenopause, thyroid, sleep, anemia, and kidney heavily over-rank one another.

2. Healthy over-alerting is far above acceptable levels.
   - Examples: `SYN-T0000027` top-1 `perimenopause 0.9613`, `SYN-T0000031` top-1 `hypothyroidism 0.9333`, `SYN-T0000045` top-1 `hypothyroidism 0.9313`.

3. Liver is still broken as a target.
   - No Layer 1 recall and no Bayesian lift.

4. Bayes questions are helping unevenly.
   - Strong for hepatitis, iron deficiency, kidney, thyroid, and prediabetes.
   - Harmful for sleep disorder and weak for perimenopause.

5. KNN adds real recovery but also real noise.
   - Coverage goes up, precision goes down.

6. Live end-to-end evaluation is blocked by route stability and schema conformance.
   - The current app path cannot yet support a trustworthy MedGemma-layer metric.

## Top-3 Failure Examples Per Condition

- anemia: `SYN-R0000026` -> top-1 `perimenopause 0.8761`; `SYN-C0000003` -> top-1 `hypothyroidism 0.9358`; `SYN-R0000028` -> top-1 `hypothyroidism 0.8367`
- electrolyte_imbalance: `SYN-R0000283` -> `hypothyroidism 0.7148`; `SYN-R0000280` -> `hypothyroidism 0.8064`; `SYN-C0000160` -> `sleep_disorder 0.6195`
- hepatitis: `SYN-C0000030` -> `perimenopause 0.9879`; `SYN-C0000021` -> `sleep_disorder 0.5627`; `SYN-C0000035` -> mislabeled toward `perimenopause 0.9712` with liver-like ground truth
- hypothyroidism: `SYN-R0000080` -> `perimenopause 0.8857`; `SYN-C0000038` -> `perimenopause 0.9639`; `SYN-C0000053` -> `perimenopause 0.7458`
- inflammation: `SYN-R0000255` -> `hypothyroidism 0.9254`; `SYN-R0000253` -> `hypothyroidism 0.9297`; `SYN-R0000245` -> `sleep_disorder 0.9013`
- iron_deficiency: `SYN-R0000196` -> `perimenopause 0.6666`; `SYN-R0000192` -> `inflammation 0.7124`; `SYN-C0000114` -> `anemia 0.5306`
- kidney_disease: `SYN-R0000161` -> `sleep_disorder 0.7556`; `SYN-C0000102` -> `perimenopause 0.9601`; `SYN-C0000105` -> `hypothyroidism 0.5614`
- liver: `SYN-R0000109` -> `perimenopause 0.9419`; `SYN-R0000105` -> `hypothyroidism 0.7412`; `SYN-R0000112` -> `sleep_disorder 0.8974`
- perimenopause: `SYN-R0000353` -> `sleep_disorder 0.6674`; `SYN-R0000306` -> `anemia 0.6773`; `SYN-R0000309` -> `anemia 0.7123`
- prediabetes: `SYN-R0000229` -> `hypothyroidism 0.7880`; `SYN-R0000225` -> `hypothyroidism 0.9496`; `SYN-C0000128` -> `sleep_disorder 0.6043`
- sleep_disorder: `SYN-C0000074` -> `inflammation 0.7667`; `SYN-C0000089` -> `hypothyroidism 0.7892`; `SYN-MUST0001` -> false positive `sleep_disorder 0.9530` against hypothyroid ground truth

## Conclusions

What works:

- Bayesian updating is adding real value on several core conditions.
- KNN helps recover missed lab groups.
- Hepatitis is the strongest disease-specific signal in the current ML layer.

What does not work yet:

- Overall Layer 1 discrimination is not reviewer-ready.
- Healthy over-alert is far too high.
- Liver and perimenopause need targeted repair.
- The live MedGemma + Groq path is operationally unstable and cannot currently support reliable end-to-end scoring.

Most important next fixes:

1. Retune thresholds against the healthy over-alert constraint.
2. Rewrite or remove the low-information perimenopause and sleep Bayes questions.
3. Repair the liver feature path and label support.
4. Add ML ROC-AUC, raw ML calibration, neighbour consistency, and questionnaire-only degradation to the eval harness.
5. Stabilize `/api/deep-analyze` with schema guards, retries, and Groq rate-limit handling before rerunning the live LLM eval.
