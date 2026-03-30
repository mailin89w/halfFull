# Eval Strategy — HalfFull Pipeline Benchmarking

> Last updated: 2026-03-30
> Branch: `after_eval`
> Latest change: condition-aware PHQ-9/SLQ imputation, SLQ_D sleep hours, all labs nulled to match user report

---

## Overview

This document records the full history of eval cohort design decisions — what we tried, why each version was built, what its limitations were, and how the final benchmark was shaped. It is meant to be a living reference so we don't repeat reasoning and so the eval results can be interpreted correctly.

---

## Cohort Version History

### v1 — `profiles.json` (600 profiles, synthetic)

**Created:** early March 2026
**Generator:** `evals/cohort_generator.py`
**Still used by:** `run_eval.py`, `run_llm_layer_eval.py` (both stale)

The original eval cohort. All profiles are fully synthetic — generated programmatically from condition-specific templates with hand-tuned lab values and symptom scores. No Bayesian answers were included at this stage because the Bayesian layer didn't exist yet.

**Profile type breakdown:** positive (261), borderline (177), negative (112), healthy (30), edge (20)
**Condition coverage:** 11 conditions, ~46 profiles each

**Limitations:**
- No Bayesian answers — can't be used for Layer 2+ evals
- Lab values are template-derived, not drawn from real distributions
- Healthy profiles are purely fabricated (all labs at midrange), not representative of real healthy NHANES adults
- Condition co-occurrence is artificial

---

### v2 — `profiles_v2_latent.json` (548 profiles, synthetic + Bayesian)

**Created:** mid-March 2026
**Generator:** `evals/cohort_generator_v2_latent.py`
**Still used by:** `run_knn_layer_eval.py` (stale — uses v2 as its default)

Added Bayesian answers using the `synthetic_answer_sampler` — the first version that could run through the full ML → Bayesian → KNN pipeline. Profiles were still fully synthetic.

**Limitations:**
- Same synthetic lab distribution problem as v1
- Slightly smaller cohort (548) because some generation paths were pruned
- KNN layer evals still use this by default (should be updated to v3)

---

### v3 — `profiles_v3_three_layer.json` (622 profiles, synthetic)

**Created:** 2026-03-26
**Generator:** `evals/build_three_layer_benchmark.py`
**Superseded by:** `nhanes_balanced_650.json` — update eval script defaults if you see v3 still wired in

Rebuilt the cohort to better reflect the full three-layer pipeline. Bayesian answers are included. The condition distribution was expanded to cover conditions the Bayesian layer cares about most (electrolyte_imbalance, inflammation added explicitly).

**Profile type breakdown:** positive (354), borderline (120), negative (100), healthy (24), edge (24)

**Key problem — sleep_disorder dominance:** sleep_disorder appears as primary condition in 241/622 profiles (39%) because the generator over-sampled it. This skews all aggregate metrics — sleep_disorder's weak ML and Bayesian performance drags down the "average" significantly.

**Limitations:**
- Synthetic lab values, not real population distributions
- Only 24 healthy profiles — too small for reliable over-alert rate estimates
- sleep_disorder massively over-represented
- No vitamin conditions (vitamin_d, vitamin_b12 not included)
- Healthy profiles are still fabricated, not drawn from real data

---

### v4 — `profiles_v4_vitamins.json` (700 profiles, synthetic)

**Created:** 2026-03-27
**Generator:** `evals/cohort_generator_v4_vitamins.py`
**Currently used by:** nothing (not yet wired into any eval script)

Extended v3 to include two new conditions: `vitamin_b12_deficiency` and `vitamin_d_deficiency`. Includes 42 profiles per new condition. The vitamin model training used a separate NHANES 2017–2018 dataset (9,254 rows) for vitamin D prevalence reference.

**Status:** Orphaned — the vitamin models exist but no eval script points to this cohort yet.

---

### Real NHANES intermediate — `nhanes_2003_2006_real_profiles.json` (6,617 profiles)

**Created:** 2026-03-27
**Source:** NHANES cycles C (2003–2004) and D (2005–2006) — real survey + lab data
**Script:** `scripts/build_real_nhanes_2003_2006_cohort.py`

The first real-data cohort. Built by downloading and processing the raw NHANES public-use files. Lab values, symptom signals, and demographics are real. Bayesian answers are probabilistically projected from NHANES fields (see [Bayesian Answer Quality](#bayesian-answer-quality-assessment) below).

**Why it was not used as-is:**
1. **Ground truth format mismatch** — the build script output `"ground_truth": [{"condition": "...", "rank": 1}]` instead of the `{"expected_conditions": [{...}]}` dict format that ProfileLoader expects. A migration script (`evals/migrate_nhanes_real_profiles.py`) was written to convert it.
2. **No healthy profiles** — the build script filtered to only rows with ≥1 condition. Of 20,470 raw rows, 10,560 had zero conditions and were silently dropped.
3. **Vitamin D threshold too loose** — used `< 50 nmol/L` (insufficiency) which labeled 36% of the population as vitamin D deficient, making the condition artificially prevalent. Clinical "deficiency" is `< 30 nmol/L` (12 ng/mL).
4. **6,617 profiles is too large** — running 6k profiles through the ML → Bayesian → KNN chain takes ~30 minutes. The LLM layer eval becomes completely impractical.
5. **Condition name mismatches** — `menopause` should be `perimenopause`, `thyroid` should be `hypothyroidism`, `hepatitis_bc` should be `hepatitis`.

---

### Real NHANES migrated — `nhanes_2003_2006_profiles_migrated.json` (6,617 profiles)

**Created:** 2026-03-30
**Script:** `evals/migrate_nhanes_real_profiles.py`

Converted the raw real-data cohort to ProfileLoader-compatible format. Fixed condition name mappings. Schema relaxed to accept real NHANES profile_ids, `null` BMI, `null` target_condition, `"unknown"` demographics, and open lab_values.

Still suffers from the no-healthy-profiles and 6,617-profile-size problems. Not used directly in evals — exists as an archive of the full real dataset.

---

### Final benchmark — `nhanes_balanced_650.json` (760 profiles)

**Created:** 2026-03-30
**Script:** `evals/build_nhanes_balanced_cohort.py`
**Recommended for:** all evals going forward

**Profile data layout (current):**
Each profile stores a `nhanes_inputs` dict. Fields are populated with the following priority:
1. **Real NHANES value** — used when the field was measured for this participant
2. **Condition-aware imputed value** — for fields not measured (see table below), estimated from condition flags + bounded per-person noise
3. **Activity-based estimate** — for sedentary minutes (not collected in 2003-2006 NHANES)

**`symptom_vector` is not stored.** It was an intermediate representation used only by the synthetic cohort generators. Eval scripts use `nhanes_inputs` directly.

**PHQ-9 and SLQ coverage by cycle:**

| Feature group | Cycle C (2003–04) | Cycle D (2005–06) |
|---|---|---|
| PHQ-9 items (dpq040, dpq010, dpq020, dpq030, dpq070) | 100% missing — imputed | ~53% missing — real where present, imputed otherwise |
| Sleep questionnaire (slq030, slq040, slq050) | 100% missing — imputed | ~41% missing — real where present, imputed otherwise |
| Sleep hours (sld012) | 100% missing — imputed | Real `SLD010H` from `SLQ_D.XPT` where measured, imputed otherwise |
| Sedentary minutes (pad680) | Not in 2003-2006 NHANES | Not in 2003-2006 NHANES |
| All other questionnaire items (BPQ, DIQ, MCQ, RHQ, etc.) | Real values | Real values |
| All lab values | Null (not available from user report) | Null (not available from user report) |

**Imputation logic** (`_impute_phq`, `_impute_slq` in `build_nhanes_balanced_cohort.py`):
- PHQ-9 scores are estimated from condition flags (anemia → +1.2 fatigue, sleep_disorder → +1.4 sleep trouble, thyroid → +0.9 fatigue, etc.) plus general health rating and per-person SEQN-keyed noise (SHA256-based, deterministic, same person always gets same answers)
- SLQ items are estimated from sleep_disorder flag + BMI + sex, on the correct 0-3 NHANES ordinal scale
- NHANES "refused" (7) and "don't know" (9) codes are treated as missing and replaced with imputed values
- Imputed PHQ-9/SLQ values feed into the Bayesian answer generation (via a merged row) so the 52-question quiz answers reflect realistic symptom patterns even for cycle C profiles

**Bayesian answer generation:** A merged row (real CSV values + imputed quiz features) is passed to `symptom_vector_from_row` and then `generate_bayesian_answers`. Clinical labs (ferritin, HbA1c, etc.) remain available in the merged row for latent state computation at build time, even though those labs are withheld from `nhanes_inputs`.

**Cohort rebuild note:** Any `nhanes_balanced_650.json` produced before 2026-03-30 (end of day) will be missing imputation and will have all PHQ-9/SLQ items at 0 for cycle C profiles. Rebuild with `python evals/build_nhanes_balanced_cohort.py`.

---

## Available Lab Data — User Report Format

Users upload a standard **Clinical Chemistry & Urinalysis** report. The only numeric lab values available from this report are:

| Panel | Analytes |
|---|---|
| Lipid profile | Total cholesterol, LDL, HDL, Triglycerides |
| Fasting blood sugar | Glucose (fasting) |
| Urine dipstick | Protein, Glucose, Erythrocytes (RBC), Leukocytes (WBC), Nitrite |

**All other lab values are not available and must be null at eval time.** This includes ferritin, hemoglobin, HbA1c, creatinine, CRP, ALT/AST/GGT, albumin, serum WBC, total protein, vitamin D, vitamin B12, transferrin saturation, and all electrolytes.

**NHANES 2003-2006 data situation:** The processed CSV does not contain lipid panel, fasting glucose, or urine dipstick as numeric values — these tests were not included in the csv-building pipeline. As a result, **all lab fields in `nhanes_balanced_650.json` profiles are null**, including the report's own analytes.

**Ground truth vs. observable data:** The ground-truth condition labels (anemia, iron_deficiency, vitamin_d_deficiency, electrolyte_imbalance, etc.) were derived during NHANES preprocessing using the underlying lab values. Those derivations are kept as ground truth. The raw lab values that produced them are intentionally withheld from the model — the model must rely on quiz answers alone.

This is the correct realistic evaluation. It reflects what the pipeline can actually do given real user inputs.

---

## Eval Script — Input Routing

`run_layer1_eval.py` contains two feature-construction paths:

| Path | Function | Used when |
|---|---|---|
| Real NHANES | `_build_raw_inputs_from_nhanes(profile)` | profile has `nhanes_inputs` key (all v5 profiles) |
| Synthetic fallback | `_build_raw_inputs(profile)` | profile has no `nhanes_inputs` (v1–v4 synthetic cohorts) |

The routing is a single `if "nhanes_inputs" in profile` check at the scoring call site. The synthetic path is kept intact so old cohorts continue to work unchanged.

**Why the routing matters:** the synthetic path reverse-engineers NHANES ordinal codes from normalised 0–1 scores (e.g. `dpq040 = fatigue_severity × 3`). This introduces rounding errors and loses the real ordinal structure. The `nhanes_inputs` path bypasses this entirely — PHQ-9 items, snoring frequency, nocturia counts, etc. are stored as the NHANES integer codes and passed directly to `InputNormalizer`.

---

## Final Cohort Design Decisions

### Why 760 profiles (not 600 or 650)

We targeted 55 profiles per condition × 12 conditions = 660 labeled, plus 100 healthy. The 12th condition (vitamin_d_deficiency) was included at 55 because the tighter threshold still yielded 689 eligible profiles. Total came to 760 rather than a round number — this is intentional; we used all available prediabetes profiles (only 57 existed at threshold) rather than artificially inflating.

### Vitamin D threshold: < 30 nmol/L

The original build used `< 50 nmol/L` (the WHO "insufficiency" cut), which labeled 36% of the NHANES population as deficient. At that threshold, 2,575 of 6,617 profiles had vitamin D as a condition, dominating the cohort.

`< 30 nmol/L` corresponds to the clinical "deficiency" threshold (12 ng/mL) used in guideline-level diagnosis. At this threshold:
- 659 profiles (10.5%) are vitamin D deficient — a more realistic prevalence for a diagnostic tool
- 13,164 of 20,470 NHANES rows have zero conditions — providing a large, real "healthy" pool

### Vitamin D model surfacing threshold: 0.40

The **model operating threshold** for `vitamin_d_deficiency` is distinct from the **clinical cohort-label threshold** above.

On 2026-03-30 we re-ran `run_layer1_eval.py` on `nhanes_balanced_760.json` and swept the current repo model across candidate thresholds. The previous user-facing threshold (`0.25`) produced excessive alert burden:

- threshold `0.25` → recall `78.2%`, precision `9.2%`, flag rate `61.3%`, healthy flag rate `52.0%`
- threshold `0.40` → recall `30.9%`, precision `13.6%`, flag rate `16.4%`, healthy flag rate `8.0%`
- threshold `0.50` → recall `16.4%`, precision `14.8%`, flag rate `8.0%`, healthy flag rate `4.0%`

We adopted **`0.40`** as the new default operating threshold because it is the best balanced point on the current benchmark:

- flag rate is close to cohort prevalence (`15.4%`)
- healthy over-alert falls below the 10% guardrail
- precision improves materially over `0.25`
- recall remains usable, unlike more conservative thresholds such as `0.50+`

### 100 healthy profiles

Healthy profiles are drawn from the 13,164 NHANES rows with genuinely zero conditions under the tightened thresholds. These are real adults who happen to not meet any of our 12 condition definitions at the time of their NHANES survey.

This is important for over-alert rate measurement — the synthetic v3 cohort had only 24 healthy profiles, making the 45.8% over-alert rate estimate noisy (one profile = ~4pp). With 100 healthy profiles, each profile represents 1pp.

**All healthy profiles confirmed to have vitamin D ≥ 30 nmol/L** (range 30.2–117.0, median 58.0 nmol/L).

### Condition balance: 55 per condition

Capped at 55 to keep total size manageable. The rarest condition (prediabetes) had only 57 available profiles under the tightened definitions — making 55 the natural cap. All conditions are now equally represented, removing the sleep_disorder skew from v3.

---

## Bayesian Answer Quality Assessment

### What is actually in NHANES

The NHANES survey contains direct questionnaire responses and lab measurements that map to a meaningful subset of our 52 Bayesian questions:

| NHANES field | Maps to |
|---|---|
| `slq030_snore_freq`, `slq040_stop_breathing_freq` | sleep apnea signals (sleep_q1, sleep_q2) |
| `slq050_sleep_trouble_doctor` | insomnia pattern (sleep_q3) |
| `dpq040_fatigue`, `dpq010_anhedonia`, `dpq020_depressed`, `dpq070_concentration` | fatigue and mood symptoms |
| `alq130_avg_drinks_per_day` | alcohol questions (hep_q1, liver_q1, elec_q1) |
| `kiq480_nocturia` | nocturia (kidney_q1) |
| `bpq020_high_bp`, `diq010_diabetes`, `diq160_prediabetes` | comorbidity context |
| `ferritin_ng_ml`, `hemoglobin_g_dl` | anemia/iron severity (anemia_q2, iron_q3) |
| `hba1c_pct` | glycemic signal (prediabetes_q2) |
| `crp_mg_l`, `wbc_1000_cells_ul` | inflammation markers |
| `serum_creatinine_mg_dl` | kidney function |
| `alt_u_l`, `ast_u_l`, `ggt_u_l` | liver enzymes |
| `sodium_mmol_l`, `potassium_mmol_l`, `calcium_mg_dl` | electrolyte values |
| `mcq160a_arthritis` | joint symptoms |
| `rhq031_regular_periods` | menstrual pattern (peri_q1) |
| `mcq092_transfusion` | hepatitis exposure risk (hep_q4) |

That covers approximately **26 direct source fields** driving ~30 of 52 questions with meaningful signal.

### What is inferred / synthesised

The remaining ~22 question answers cannot be directly observed in NHANES and are modelled via `synthetic_answer_sampler.py`. The approach is:

1. **Derive latent states** — 30+ intermediate float signals are computed from NHANES fields and the condition flags. Examples:
   - `bleeding_burden`: derived from sex + age + anemia + iron flags (proxy for heavy periods)
   - `thyroid_cold_pattern`: derived from thyroid flag + heat_intolerance score
   - `hepatitis_exposure_risk`: derived from transfusion history + alcohol level
   - `perimenopause_mood_burden`: derived from depressive/anxiety scores + sleep quality

2. **Sample answers deterministically** — each answer is derived using a sigmoid-scaled probability over the latent state, seeded by `SEQN + question_id` (deterministic, reproducible per person, no random noise across runs).

3. **Duration answers** are driven by a chronicity signal (e.g., `thyroid_duration = 0.75 × thyroid_flag + 0.25 × fatigue`), mapped to `lt_4w / 4_12w / 12w_6m / gt_6m`.

### Honest limitations

**High confidence (directly observable, where measured):**
- Alcohol questions (direct daily intake measure — present for all participants)
- Nocturia (direct frequency question — present for all participants)
- Medical history flags: arthritis, thyroid history, liver condition, kidney disease, diabetes, BP meds, transfusion, reproductive history (all present for all participants)
- Lab-derived questions: HbA1c, ferritin, hemoglobin, electrolytes, liver enzymes, creatinine — **used at Bayesian build time only** (these drive the latent states that generate quiz answers, but the values themselves are withheld from the model at inference)

**Medium confidence (measured for a subset, imputed for the rest):**
- Sleep apnea questions (slq030, slq040, slq050): real for ~59% of cycle D participants; condition-aware imputed for 100% of cycle C and ~41% of cycle D
- Sleep hours (sld012): real from SLQ_D.XPT for measured cycle D participants; imputed for cycle C and unmeasured cycle D
- Fatigue, mood, concentration scores (PHQ-9 dpq040, dpq010, dpq020, dpq030, dpq070): real for ~47% of cycle D; condition-aware imputed for 100% of cycle C and ~53% of cycle D. Imputation is directionally correct (anemia → higher fatigue, sleep_disorder → higher sleep trouble) but individual variation is high

**Medium confidence (plausible inference, not observable):**
- Heavy menstrual bleeding — no direct NHANES question; inferred from sex + age + anemia/iron flags. The biological logic is sound but individual variation is high.
- Cold intolerance, dry skin, constipation for thyroid — inferred from the thyroid condition flag + symptom vector. If a person has hypothyroidism in NHANES, they probably do have these symptoms, but we are asserting rather than observing.
- Weight change pattern for thyroid — driven by BMI + weight preference code, reasonable approximation.

**Low confidence (weakly grounded):**
- Pica cravings — inferred from ferritin < 20 ng/mL. Directionally right (severe iron deficiency → pica) but pica is rare even in severe deficiency. Many profiles will have this answer incorrectly set to "yes".
- Spider angioma, ascites, jaundice for liver/hepatitis — physical exam findings. In NHANES these are never directly asked. We infer from condition flag + liver enzymes. For a real patient who has liver disease on paper, these may or may not be present.
- Perimenopause self-assessment questions (peri_q2b, peri_q5) — these two questions were already flagged as negative-gain in the Bayesian eval. The synthetic answers likely reinforce a circular signal (perimenopause flag → perimenopause answers → perimenopause posterior) that may explain why these questions subtract rather than add information.

**Structural note:** The Bayesian sampler uses the condition labels (thyroid=1, anemia=1, etc.) as inputs to derive the latent states. This creates a mild circular dependency: profiles labelled as thyroid-positive will have thyroid-consistent Bayesian answers, which will then score well on the Bayesian layer. This is a deliberate design choice (it lets us measure the *maximum possible* gain from the Bayesian layer given correct labels), but it means the Bayesian accuracy numbers on this cohort are **optimistic** compared to a real user population where self-reported symptoms are noisier.

---

## Which Cohort to Use for Which Eval

| Eval | Recommended cohort | Reason |
|---|---|---|
| ML Layer 1 accuracy | `nhanes_balanced_650.json` | Real lab distributions, balanced |
| Bayesian layer (L2) | `nhanes_balanced_650.json` | Has all 52 answers, real demographics |
| KNN reranker (L3) | `nhanes_balanced_650.json` | Real lab features drive KNN groups |
| KNN top-1 A/B | `nhanes_balanced_650.json` | Drop-in for profiles_v3_three_layer |
| LLM layer (L4) | `nhanes_balanced_650.json` (sample ~50) | LLM eval is slow; sample 50 profiles |
| Safety (L5) | Dedicated red-team cases only | Not a cohort eval |
| Over-alert rate | `nhanes_balanced_650.json` | 100 real healthy profiles |
| Vitamin model evals | `profiles_v4_vitamins.json` (synthetic) | nhanes cohort has vitamin_d included; B12 coverage sparse in NHANES 2003-2006 |

---

## What Is Still Missing

1. **No real "borderline" labels** — the real NHANES profiles are binary (condition present or not). The v3 synthetic cohort had explicit borderline/edge profiles that stress-test the pipeline at the decision boundary. Consider adding a borderline tier using profiles where the condition threshold was narrowly met (e.g. hemoglobin 11.5–12.0 g/dL for anemia, HbA1c 5.7–5.9% for prediabetes).

2. **Vitamin B12 coverage is thin** — NHANES 2003-2006 only has B12 measured on a subsample. The 2003-2006 cohort has 275 B12-deficient profiles vs 1,315 iron-deficient. A separate NHANES 2017–2018 dataset exists for vitamin D (`nhanes_2017_2018_vitd_real_cohort.csv`) but was never converted to profiles.

3. **No comorbidity-stratified sampling** — `multi` profiles exist naturally (233/760 = 30.7%) and carry full comorbidity ground truth. But sampling is first-label-wins, not stratified by pair. The KNN comorbidity rescue eval would benefit from profiles explicitly seeded with known co-occurrences (e.g., anemia + iron_deficiency, kidney + prediabetes).

4. **peri_q2b and peri_q5 are known bad questions** — the Bayesian eval flagged these as negative-gain. Until the LR table for perimenopause is audited and these questions removed, perimenopause Bayesian performance on this cohort should be treated as a lower bound.

5. **Lipid panel and fasting glucose not populated** — the user-facing report format includes total cholesterol, LDL, HDL, triglycerides, and fasting glucose, but the NHANES 2003-2006 extract used to build the cohort does not contain these as numeric values. All lab fields are currently null. If those values are added to the NHANES processing pipeline, they should be joined in and the cohort rebuilt.

---

> **Resolved — symptom_vector back-calculation:** `run_layer1_eval.py` previously reconstructed NHANES ordinal inputs from the normalised `symptom_vector`. Fixed: real profiles now store `nhanes_inputs`; eval script routes to `_build_raw_inputs_from_nhanes()`.

> **Resolved — neutral PHQ-9/SLQ defaults:** PHQ-9 and SLQ items previously defaulted to 0 for cycle C and unsampled cycle D profiles. Fixed: condition-aware imputation with per-person noise now produces realistic symptom scores; sleep hours use real SLQ_D.XPT values where available.

> **Resolved — lab data leakage:** Eval profiles previously included ferritin, HbA1c, creatinine, CRP, liver enzymes, etc. which the model would never have from a real user. Fixed: all clinical lab fields are null; model relies on quiz answers only.
