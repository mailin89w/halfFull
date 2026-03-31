# PR: ML-KIDNEY-02 & ML-INFLAM-02 — Kidney Recovery + Inflammation Rebuild

**Branch:** `feat/kidney-inflam-optimization` → `main`
**Date:** 2026-03-31
**Cohort:** `evals/cohort/nhanes_balanced_760.json` (760 NHANES profiles)

---

## Summary

Two model issues confirmed against the 760-cohort baseline (`layer1_20260331_000041.md`):

| Model | Baseline Recall | Problem |
|-------|----------------|---------|
| Kidney v2 (prod) | 39.1% | v3 over-corrected — killed recall |
| Inflammation v3 (prod) | 4.1% (top-3) | Effectively dead in top-3 competition |

---

## ML-KIDNEY-02 — Kidney v4

### Root cause of v3 recall collapse
v3 added `serum_creatinine` and `uric_acid` as discriminative anchors. These are NHANES **lab values that users can't self-report** — the 760-cohort always has them as `None`. Imputed to training median → model loses all signal → ~0% recall.

### FP Audit findings
Ran v2 (production) on all 760 profiles. Of 201 false positives:
- 54% "other" — **perimenopause dominates** (81 hits), plus liver, hypothyroidism, sleep
- 25% metabolic — prediabetes, iron deficiency, vitamin-D overlap
- 16% hypertensive — electrolyte imbalance (HTN is a legitimate CKD risk factor)
- 4% healthy — pure noise

### v4 fix
- Reverted to v2's 17-feature **questionnaire-only** set (no lab values)
- Replaced `class_weight='balanced'` (~28x) with explicit `{0:1.0, 1:4.0}` (softer positive boost)
- Applied `sample_weight=0.40` on hard-negative rows (they guide the boundary without dominating)
- Recalibrated thresholds: soft weighting produces lower absolute probabilities (gate 0.35 → 0.15)

### Results

| Metric | v2 (baseline) | v4 (candidate) |
|--------|--------------|----------------|
| 760-cohort recall | 39.1% | **43.5%** ✓ |
| Precision | 8.0% | 8.3% |
| Healthy FP rate | 3.0% | 3.0% |
| Hard-neg ≥ 0.30 | — | 0.0% (PASS) |
| CV AUC | — | 0.808 ± 0.023 |
| Pipeline gate | 0.35 | 0.15 (recalibrated) |

**Status: READY FOR PROMOTION.**

---

## ML-INFLAM-02 — Inflammation

### v4 validation result
The v4 candidate (`hidden_inflammation_lr_v4_hard_neg.joblib`) failed: **0% recall, mean score 0.078** at threshold 0.40.

Root cause: `CalibratedClassifierCV(method='isotonic')` collapsed all scores to near-zero. The isotonic regression overfits calibration folds and pushes all outputs toward the minimum. This kills the model completely.

### Missed-positive audit
Analysed all 49 primary inflammation positives. 30/49 (61%) are missed by both v3 and v4.

Key finding from feature comparison (found-by-v3 vs missed-both):

| Feature | Found | Missed |
|---------|-------|--------|
| waist_cm (z-score) | +0.14 | **−0.18** |
| waist_elevated_female flag | 0.16 | **0.00** |
| General health (self-report) | 2.84 | 2.37 |

The model finds **metabolic inflammation** (elevated waist, worse health). It misses **lean inflammation** — immune/endocrine cases with no central adiposity signal. This is a feature gap, not label noise.

### Recommended next steps (ML-INFLAM-03)
1. Fix v4: remove isotonic calibration or switch to `method='sigmoid'`
2. Add a lean-inflammation symptom bundle (fatigue + joint pain + no waist signal)
3. Long-term: split `hidden_inflammation` into metabolic vs immune subtypes

---

## Files changed

All new files are in `evals/2026-03-kidney-inflam-recovery/`:

| File | Purpose |
|------|---------|
| `audit_kidney_fps.py` | Classifies v2 FPs into healthy/metabolic/hypertensive/other |
| `train_kidney_v4.py` | Trains kidney v4 with soft hard-neg weighting |
| `validate_inflammation_v4.py` | v3 vs v4 head-to-head on 760-cohort |
| `audit_inflammation_missed.py` | Missed-positive feature analysis + label fuzziness check |
| `README.md` | Full walkthrough with results |
| `results/kidney_fp_audit.json` | Raw FP records |
| `results/kidney_fp_summary.md` | Human-readable FP breakdown |
| `results/kidney_v4_training_report.json` | v4 training and validation metrics |
| `results/inflammation_v4_validation.json` | v3 vs v4 comparison |
| `results/inflammation_missed_audit.json` | Per-profile missed-positive analysis |

The kidney v4 model artifact (`kidney_lr_v4_soft_weights.joblib`) is saved to `models_normalized/`.
**No changes to `model_runner.py` or `MODEL_REGISTRY`** — promotion happens in a follow-up PR.

---

## Test plan

- [x] `audit_kidney_fps.py` — runs clean on 760 profiles, produces bucketed FP summary
- [x] `train_kidney_v4.py` — recall constraint PASSED (43.5% ≥ 35%), hard-neg PASSED
- [x] `validate_inflammation_v4.py` — v4 correctly identified as dead, root cause (isotonic calibration) documented
- [x] `audit_inflammation_missed.py` — label fuzziness: NOT fuzzy; feature gap identified
- [ ] Wire kidney v4 into `MODEL_REGISTRY_AUDIT` and run full `run_quiz_three_arm_eval.py` (follow-up PR)
- [ ] Open ML-INFLAM-03 for the v5 redesign
