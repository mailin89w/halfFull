# ML-KIDNEY-02 & ML-INFLAM-02: Kidney Recovery + Inflammation Rebuild

**Branch:** `feat/kidney-inflam-optimization`
**Date:** 2026-03-31
**Tickets:** ML-KIDNEY-02, ML-INFLAM-02
**Baseline:** `evals/reports/layer1_20260331_000041.md`

---

## What this folder is

This folder contains the scripts, audit results, and documentation for two model improvement efforts triggered after the 2026-03-31 baseline eval on the 760-cohort:

| Model | Baseline Recall | Problem |
|-------|----------------|---------|
| Kidney v2 (production) | 39.1% | v3 over-corrected and killed recall |
| Inflammation v3 (production) | **4.1%** | Effectively dead — top-3 competition starves it |

All results are in `results/`. All scripts run against `evals/cohort/nhanes_balanced_760.json`.

---

## ML-KIDNEY-02 — Results

### Step 1: FP Audit (`audit_kidney_fps.py`)

Ran the v2 model against all 760 profiles at threshold 0.35.

| Bucket | Count | % of FPs | What it means |
|--------|-------|----------|---------------|
| other | 109 | 54% | Mostly **perimenopause** (81 hits!), liver, hypothyroidism |
| metabolic | 51 | 25% | Prediabetes, iron deficiency, vitamin-D overlap |
| hypertensive | 32 | 16% | Electrolyte imbalance — HTN is a legit CKD risk factor |
| healthy | 9 | 4% | Pure noise |

**Key finding:** Perimenopause dominates FPs. Shared features (age, hormonal stress markers, general symptoms) make these look like borderline CKD. The hard-negative strategy correctly targets fatigue/thyroid/sleep mimics but under-targets perimenopause overlap.

### Step 2: Train Kidney v4 (`train_kidney_v4.py`)

**Why v3 failed on the 760-cohort:**
- v3 added `serum_creatinine` and `uric_acid` as discriminative anchors
- These are NHANES **lab values users can't self-report**
- The 760-cohort always has them as `None` → imputed to training median → model loses all signal
- Result: ~0% recall on the 760-cohort despite good CV AUC

**v4 fix:**
1. Reverted to v2's 17-feature questionnaire-only set (no lab values)
2. Replaced `class_weight='balanced'` (~28x positive weight) with explicit `{0:1.0, 1:4.0}`
3. Applied `sample_weight=0.40` on hard-negative rows so they guide the boundary without dominating the loss
4. Recalibrated thresholds: soft weighting produces lower absolute probabilities, so gate moves from 0.35 → 0.15

**760-cohort results (v4 vs v2 baseline):**

| Metric | v2 (production) | v4 (candidate) |
|--------|----------------|----------------|
| Recall | 39.1% | **43.5%** |
| Precision | 8.0% | **8.3%** |
| Healthy FP rate | 3.0% | **3.0%** |
| Pipeline gate | 0.35 | 0.15 (recalibrated) |
| Hard-neg validation | — | 0.0% score ≥ 0.30 (PASS) |
| CV AUC | — | 0.808 ± 0.023 |

**Status: READY FOR PROMOTION** — all constraints passed.

---

## ML-INFLAM-02 — Results

### Step 1: Validate v4 (`validate_inflammation_v4.py`)

| Metric | v3 (production) | v4 (candidate) |
|--------|----------------|----------------|
| Recall (primary positives) | 38.8% raw | **0.0%** |
| Flag rate | 34.0% | 0.1% |
| Mean score (positives) | 0.384 | 0.078 |

Note: v3 raw recall (38.8%) is higher than the baseline top-3 recall (4.1%) because
the baseline measures whether inflammation survives the top-3 ranking competition, not just
whether the raw score exceeds the threshold.

**v4 root cause identified:**
`CalibratedClassifierCV(method='isotonic')` has **collapsed all scores to ~0.07–0.08**.
The isotonic regression overfits the calibration folds and maps everything to near-zero.
This is confirmed by the 0.1% flag rate at threshold 0.40 — the model scores everyone below 0.40.

**Recommendation: PROCEED_TO_MISSED_POSITIVE_AUDIT**

### Step 2: Missed Positive Audit (`audit_inflammation_missed.py`)

Analysed the 49 primary inflammation positives (target_condition=inflammation, profile_type=positive).

| Group | Count | % |
|-------|-------|---|
| found_by_v3_only | 19 | 39% |
| missed_both | 30 | 61% |

**Feature differences between found vs missed cases:**

| Feature | Found (v3) | Missed (both) | Interpretation |
|---------|-----------|---------------|----------------|
| waist_cm (z-score) | +0.14 | **–0.18** | Missed cases are **lean** |
| waist_elevated_female | 0.16 | **0.00** | Missed cases: no waist flag |
| General health condition | 2.84 | 2.37 | Found cases report worse health |

**Label fuzziness verdict: NOT fuzzy.**
Missed positives have broadly similar generic-illness signal to found positives. This is NOT a label quality problem — the inflammation label is real. The problem is a feature coverage gap:

- The model was tuned to detect **metabolic inflammation** (central adiposity, low HDL, high BP)
- It misses **lean inflammation** — immune/endocrine cases without elevated waist or metabolic markers
- These cases likely require different features: CRP-proxy signals, autoimmune markers, or a symptom bundle approach

### Inflammation redesign plan (ML-INFLAM-03)

**Root cause of v4 failure:**
The isotonic calibration in `CalibratedClassifierCV` is collapsing all scores. This must be fixed before any further work.

**Recommended path:**
1. **Fix calibration**: Remove isotonic calibration or switch to `method='sigmoid'` (Platt scaling). Re-run v4.
2. **Add lean-inflammation features**: Symptom bundle (fatigue + joint pain + no waist signal) — same approach that recovered anemia recall in ML-ANEMIA-02.
3. **Split the label (longer term)**: Separate `hidden_inflammation` into:
   - `metabolic_inflammation` — waist + HDL + BP (what the current model finds)
   - `immune_inflammation` — arthritis type, treatment for anemia, systemic symptoms
4. **Open ticket ML-INFLAM-03** for the v5 redesign.

---

## How to run

```bash
cd evals/2026-03-kidney-inflam-recovery

# 1. Kidney FP audit (read-only, fast)
python audit_kidney_fps.py

# 2. Train kidney v4
python train_kidney_v4.py

# 3. Validate inflammation v4
python validate_inflammation_v4.py

# 4. Missed-positive audit (run after step 3 confirms v4 is dead)
python audit_inflammation_missed.py
```

All outputs go to `results/`. Kidney v4 model artifact saved to `models_normalized/`.

---

## Promotion checklist

### Kidney v4 — READY
- [x] 760-cohort recall 43.5% ≥ 35% floor
- [x] Hard-neg validation: 0.0% ≥ 0.30
- [x] Healthy FP rate 3.0% ≤ 5%
- [ ] Wire into `MODEL_REGISTRY_AUDIT["kidney"]` with new artifact `kidney_lr_v4_soft_weights.joblib`
- [ ] Update `USER_FACING_THRESHOLDS["kidney"]` to 0.15 (recalibrated)
- [ ] Run full `run_quiz_three_arm_eval.py` to confirm no regressions

### Inflammation v4 — BLOCKED
- [ ] Fix isotonic calibration collapse (switch to sigmoid or remove)
- [ ] Open ML-INFLAM-03 for lean-inflammation feature additions
- [ ] Validate fixed model before promotion
