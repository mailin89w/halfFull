# HalfFull Layer 1 — Engineering Handover

_Generated 2026-03-26. Covers all fixes, eval results, and open problems from the current engineering sprint._

---

## Baseline (where we started)

**Eval: `layer1_20260325_222624` — 600 profiles, original models**

| Metric | Value |
|--------|-------|
| Top-1 Accuracy | 16.6% |
| Top-3 Coverage | 37.8% |
| Over-Alert Rate | **93.3%** |

Key pathologies visible from the start:
- `iron_deficiency` scored 0% recall — the v3 model's gender_female coefficient (+1.32) pushed all female scores above the threshold floor, but the *wrong* direction: female scores were so uniformly high that the model lost all discriminating power
- `thyroid` fired 91.7% of all profiles at threshold 0.35
- `prediabetes` fired 95.2% at threshold 0.35
- `sleep_disorder` fired 89.3% at threshold 0.55
- `menopause` was a duplicate condition running the same perimenopause model, inflating the cohort

---

## Fix 1 — Remove menopause, standardize to perimenopause only

**What was done:**
- Removed `"menopause"` from `config.py` → `CONDITION_IDS`
- Removed from `cohort_generator_v2_latent.py`: condition list, `CONDITION_PREFIX`, `BAYESIAN_PRIORS`, two `COMORBIDITY_PAIRS`, `CONDITION_FACTOR_WEIGHTS`, `MIMIC_FACTOR_WEIGHTS`
- Removed `"menopause": "perimenopause"` proxy mapping from `run_layer1_eval.py` and `score_profiles.py`
- Updated cohort assert from 600 → 548 profiles

**Complication discovered:** `cohort_generator` imported `CONDITION_IDS` from the root `config.py` via `from config import CONDITION_IDS`. The root config still had menopause in it, causing the generated cohort to have 598 profiles instead of 548 (assert failed). Fixed by updating `config.py` at project root as well.

**Result:** Cohort now cleanly 548 profiles, no duplicate perimenopause/menopause scoring.

---

## Fix 2 — Retrain iron_deficiency without CBC markers (v3 → v4)

**Problem:** v3 used 4 CBC lab markers (Hgb, MCV, RDW, MCH) that users cannot self-report at quiz time (full blood count required). The model was being given data it would never have in production.

**What was done:**
- Created `train_iron_deficiency_v4.py` — RF+Cal, same architecture as v2, 35 features (4 CBC markers removed)
- The `education_ord` column needed to be derived at training time from the text `education` column (not stored in the normalized CSV) — added `_EDU_ORDER` mapping inline
- Trained successfully: CV AUC = 0.8094, AUPRC = 0.3175 (comparable to historical v2 AUC of 0.8094)
- Saved as `iron_deficiency_rf_cal_deduped35_v4.joblib`
- Updated `MODEL_REGISTRY` in `model_runner.py` to load v4

**Also in this fix:**
- Removed the CBC lab column mappings from `cohort_generator_v2_latent.py`'s `latent_to_labs()` — the cohort generator was synthesizing Hgb/MCV/RDW/MCH values that no longer feed any model
- Removed all CBC override logic from `run_layer1_eval.py`

**Complication:** Multiple failed training runs because the virtual environment path was not immediately obvious. Correct path: `.venv/bin/activate` (not `ml_project_env/bin/activate`).

**Result (eval `layer1_20260326_073411`):** iron_deficiency recall jumped from 0% → 96%, precision 35.3%, flag rate 11.3%. The v4 model works correctly without CBC features.

---

## Fix 3 — Threshold tuning, round 1 (anemia, thyroid, sleep_disorder)

**Problem:** Over-alert rate driven by models firing on most of the cohort. First pass targeted the three most obvious over-flaggers.

**What was done** in `FILTER_CRITERIA` in `model_runner.py`:
- `anemia`: 0.30 → 0.50
- `thyroid`: 0.35 → 0.55
- `sleep_disorder`: 0.55 → 0.70

**Result:** Over-alert rate came down but still very high.

---

## Fix 4 — Threshold tuning, round 2 (inflammation, prediabetes, kidney, electrolyte)

**Problem:** Second tier of over-flagging models had not yet been addressed.

**What was done** in `FILTER_CRITERIA`:
- `hidden_inflammation`: 0.20 → 0.30
- `prediabetes`: 0.35 → 0.40
- `kidney`: 0.20 → 0.25
- `electrolyte_imbalance`: 0.40 → 0.46

**Eval `layer1_20260326_073814` — 548 profiles, post-threshold-tuning:**

| Metric | Value |
|--------|-------|
| Top-1 Accuracy | 14.8% |
| Top-3 Coverage | 44.5% |
| Over-Alert Rate | **90.0%** |

Flag rates were still very high: thyroid 81%, prediabetes 67%, sleep_disorder 73%.

---

## Fix 5 — RANK_NORMALIZE + SCORE_MEANS/SCORE_RANGES recalibration

**Problem:** Even with correct scores, ranking was distorted because models like thyroid (population mean 0.662) and sleep_disorder (mean 0.781) dominate by raw probability despite only modest elevation above baseline for true positives.

**What was done:**
- Added `RANK_NORMALIZE = True` — uses mean-floor normalization: `rank_key = (score − population_mean) / (observed_max − population_mean)`. This maps each model's score to "signal above baseline" rather than raw probability.
- Updated `SCORE_MEANS` and `SCORE_RANGES` from the 548-profile cohort observations

**Result:** Over-alert rate improved significantly from 90% → **63.3%**. Top-1 accuracy remained at 14.8%, top-3 coverage 44.5%.

---

## Fix 6 — iron_deficiency post-scoring menstrual gate

**Problem identified:** Even with v4 (no gender_female feature), iron_deficiency was still over-flagging post-menopausal women. For women over 45 with no regular periods, the primary iron deficiency mechanism (menstrual blood loss) does not apply.

**Design decision:** No retraining. Rule-based post-scoring gate:
- Condition: female AND age > 45 AND `rhq031___had_regular_periods_in_past_12_months` = 2.0 (explicitly answered "No")
- Action: multiply iron_deficiency score × 0.4

**What was done:**
1. Added `_apply_post_score_gates()` static method to `ModelRunner`, called from `run_all_with_context()` after all model scoring
2. `rhq031` is **not in the v4 feature vector** (only `rhq060` age-at-last-period and `rhq160` pregnancies are), so the value cannot be read from the feature matrix — had to thread it explicitly through `patient_context`
3. Updated `score_raw()` to copy `raw_inputs["rhq031___had_regular_periods_in_past_12_months"]` into `patient_context["rhq031_regular_periods_raw"]` before calling `run_all_with_context`
4. Updated `_score_profile()` in `run_layer1_eval.py` to do the same threading when building `patient_context` for eval runs
5. Fixed an inverted condition bug: the initial implementation had `if rhq031_val != 2.0: [apply gate]` — the logic was backwards. Fixed to `if rhq031_val != 2.0: return scores` (skip gate unless explicitly "No")

**Result (eval `layer1_20260326_085007`):**
- iron_deficiency flag rate: 11.7% → **11.3%**
- iron_deficiency precision: 31.2% → **32.3%**
- Over-alert: still 63.3% (gate covers only a small demographic slice)
- Top-1 accuracy: still 14.8%

---

## Current State — Final Snapshot

**Eval `layer1_20260326_085007` — latest, 548 profiles:**

| Metric | Baseline | Current | Target |
|--------|----------|---------|--------|
| Top-1 Accuracy | 16.6% | **14.8%** | ≥ 70% |
| Top-3 Coverage | 37.8% | **44.5%** | — |
| Over-Alert Rate | 93.3% | **63.3%** | < 10% |

Per-condition breakdown:

| Condition | Threshold | Recall | Precision | Flag Rate | Status |
|-----------|-----------|--------|-----------|-----------|--------|
| hepatitis | 0.10 | 100% | 44% | 9.1% | ✅ healthy |
| iron_deficiency | 0.15 | 100% | 32% | 11.3% | ✅ healthy |
| perimenopause | 0.40 | 72% | 8.6% | 27.7% | acceptable |
| anemia | 0.50 | 85% | 13.6% | 22.8% | acceptable |
| kidney_disease | 0.25 | 27% | 3.9% | 27.9% | ⚠️ low recall |
| inflammation | 0.30 | 55.6% | 5.7% | 32.3% | ⚠️ noisy |
| sleep_disorder | 0.70 | 70% | 8.5% | 29.9% | ⚠️ noisy |
| prediabetes | 0.40 | 44% | 3.5% | 41.8% | 🔴 very noisy |
| electrolyte | 0.46 | 15% | 1.6% | 34.3% | 🔴 very noisy |
| thyroid | 0.55 | 90% | 7.1% | 46.5% | 🔴 very noisy |

---

## Remaining Problems

### 1. Top-1 accuracy gap (14.8% vs 70% target)

The right condition lands in top-3 for 44.5% of profiles but only reaches #1 for 14.8%. The ranking is wrong more often than not. Root causes:

- **thyroid fires on 46.5% of all profiles at threshold 0.55** — its population mean is 0.662, so the threshold is below the cohort baseline. Nearly every profile with any mild symptom overlap gets flagged.
- **prediabetes fires on 41.8%** — same structural problem, mean 0.557, threshold 0.40 is below the mean.
- **electrolyte fires on 34.3%** with only 1.6% precision — essentially random flagging.

These three models produce so many false flags that the correct condition rarely ranks first.

### 2. Poor model discrimination for several conditions

Some models score positives only marginally above negatives:
- **kidney**: recall dropped to 27.3% after raising threshold to 0.25 — the model simply doesn't separate well; negatives cluster at similar scores to true positives
- **electrolyte_imbalance**: 15% recall at 0.46 — signal is barely above noise
- **prediabetes**: 44% recall at 0.40 — common symptom overlap with sleep, thyroid, and inflammation means the model fires broadly

Threshold tuning is fundamentally limited here. You can trade recall for precision, but the overlap is so severe that no threshold gives both.

### 3. SCORE_MEANS/SCORE_RANGES stale for v4 iron_deficiency

The rank-normalization constants for `iron_deficiency` (`SCORE_MEANS = 0.038`, `SCORE_RANGES max = 0.850`) were calibrated on the v3 model which had CBC features and pushed female scores to 0.63–0.97. With v4, actual scores range from roughly 0.05–0.50 and the population mean is higher than 0.038. This means v4 iron_deficiency may be over-credited in ranking relative to its true signal. These constants need to be recalibrated from the actual v4 score distribution across the 548-profile cohort.

### 4. "Full" quiz path — 0% coverage

20 profiles (mostly healthy, no lab values) get zero conditions past any threshold. These are symptom-only profiles. This is partly correct behavior (healthy should not flag), but some may have target conditions with no lab-dependent signals — the models can't recover from missing labs. The current thresholds assume lab data is present; symptom-only profiles are effectively unscored.

---

## What Can Be Done Next

| Option | Expected Impact | Effort |
|--------|----------------|--------|
| **Retrain thyroid, prediabetes, electrolyte** with better feature engineering or GBT instead of LR/RF | High — tackles root discrimination problem | High |
| **Add eligibility pre-gates** for noisy models (e.g., prediabetes requires BMI > 25 or fasting glucose ≥ 100; electrolyte requires specific symptom flags) | Medium — reduces false flags without retraining | Medium |
| **Recalibrate SCORE_MEANS/SCORE_RANGES for v4** from current 548-profile cohort actual score distributions | Medium — fixes ranking bias introduced by stale v3 constants | Low |
| **Raise thresholds further**: thyroid → 0.78+, prediabetes → 0.65+, electrolyte → 0.60+ | Reduces over-alert but will crater recall for these conditions | Low |
| **Expand the eval cohort** with more diverse profiles, particularly male profiles and older age bands, to better calibrate flag rates | Improves eval reliability | Medium |
| **Retrain kidney model** — currently only 27% recall; the model seems unable to separate kidney disease from general inflammation/metabolic profiles | High recall impact | High |
| **Add more informative features** to prediabetes/thyroid models (e.g., direct quiz questions about diagnosis history, family history) | High — better signal reduces noise | High |

---

## Key Files Changed This Sprint

| File | What changed |
|------|-------------|
| `config.py` | Removed `"menopause"` from `CONDITION_IDS` |
| `evals/cohort_generator_v2_latent.py` | Removed menopause everywhere; removed CBC field mapping from `latent_to_labs()` |
| `evals/run_layer1_eval.py` | Removed menopause proxy; removed CBC overrides; added `rhq031` threading into `patient_context` for gate |
| `evals/score_profiles.py` | Removed menopause proxy |
| `models_normalized/train_iron_deficiency_v4.py` | New file — trains v4 model without CBC features |
| `models_normalized/iron_deficiency_rf_cal_deduped35_v4.joblib` | New model artifact |
| `models_normalized/model_runner.py` | Pointed registry to v4; raised all thresholds; added `RANK_NORMALIZE`; added `SCORE_MEANS`/`SCORE_RANGES`; added `_apply_post_score_gates()` and `rhq031` threading in `score_raw()` |
