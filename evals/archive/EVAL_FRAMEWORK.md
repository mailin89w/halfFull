# HalfFull — Evaluation Framework

**Version:** 1.1
**Status:** Draft
**Last updated:** March 2026
**Authors:** Inbal, Anna, Daniela

---

## Overview

This document defines the evaluation metrics, thresholds, and testing approach for each layer of the HalfFull ML pipeline. The goal is to ensure the system reliably identifies fatigue-related conditions without over-alerting users or missing clinically important signals.

HalfFull is a **screening tool, not a diagnostic tool**. This shapes every metric decision: we prioritise recall (catching real conditions) over precision (avoiding false positives), while keeping false positive burden manageable enough that users trust the output.

---

## Core Trade-off: Recall vs Precision

| Priority | Rationale |
|---|---|
| **Recall first** | Missing a real condition (false negative) means a user suffers unnecessarily without guidance |
| **Precision matters too** | Too many false positives erode user trust and create unnecessary anxiety |
| **Per-condition balance** | Thresholds are set per disease based on severity, test cost, and model confidence |

---

## Layer 1 — ML Models

### Metrics

| Metric | Description | Target |
|---|---|---|
| **AUC-ROC** | Discriminative power across all thresholds | ≥ 0.75 per model |
| **Recall at threshold** | True positive rate at the operating threshold | ≥ 0.70 for high-severity conditions |
| **Precision at threshold** | Positive predictive value at the operating threshold | Tracked; no hard target (varies by prevalence) |
| **F1 at threshold** | Harmonic mean of precision and recall | Tracked for comparison |
| **Brier score** | Probability calibration (lower = better) | ≤ 0.20 |
| **Flag rate** | % of users flagged per condition at threshold | Tracked; must be acceptable per condition |

### Per-condition Thresholds

Thresholds are disease-specific, set based on four factors: model AUC, disease severity, downstream test cost, and acceptable flag rate.

| Condition | Filter Threshold | Severity | Rationale |
|---|---|---|---|
| Hepatitis B/C | 0.10 | 🔴 High | Serious disease; cheap serology test; even borderline scores warrant follow-up |
| Liver | 0.10 | 🔴 High | Serious disease; cheap LFTs; 8% flag rate acceptable |
| Iron deficiency | 0.15 | 🟠 Mod-High | Common in women; trivial ferritin test; Bayesian refines further |
| Kidney | 0.20 | 🔴 High | Serious; lower filter lets Bayesian work on borderline CKD signals |
| Anemia | 0.35 | 🟠 Mod | Very cheap CBC test; 41% flag rate already high before Bayesian |
| Hidden inflammation | 0.35 | 🟡 Marker | Risk marker not a disease — let Bayesian decide |
| Prediabetes | 0.35 | 🟠 Mod | Reversible; lifestyle impact; weakest model so threshold not too low |
| Thyroid | 0.35 | 🟠 Mod | Manageable if caught early; moderate filter |
| Electrolytes | 0.40 | 🟠 Mod | Weakest model — need higher confidence before surfacing |
| Perimenopause | 0.40 | N/A | High base rate; excellent model (AUC 0.854); lower filter gives useful signal |
| Sleep disorder | 0.55 | 🟡 Low-Mod | Very high prevalence + expensive sleep study → only surface strong signals |

### Filtering Metrics (on synthetic cohort)

| Metric | Description | Target |
|---|---|---|
| **Miss rate at threshold** | False negative rate at the operating threshold | ≤ 15% for high-severity conditions |
| **Over-alert rate** | False positive burden — % of healthy users flagged | ≤ 20% across all conditions |
| **Top-3 coverage rate** | % of users where at least one true condition appears in the top-3 output | ≥ 70% (primary goal) |

---

## Layer 2 — Bayesian Update

The Bayesian layer refines ML posterior scores using targeted follow-up questions. Four metrics assess its contribution.

| Metric | Description | Target |
|---|---|---|
| **Posterior calibration** | Brier score after Bayesian update vs before; update should not worsen calibration | Brier after ≤ Brier before |
| **Coverage delta** | Does the update move borderline cases (0.40–0.60 prior) into confident recommendations? | Top-3 coverage improves ≥ 2pp on cases that triggered questions |
| **Question information gain** | Per question: how much does it reduce uncertainty (entropy) about the target condition? | Flag any question with expected gain < 0.02 bits as a candidate for removal |
| **Order independence** | Running Q1→Q2 should give same posterior as Q2→Q1 (tests conditional independence assumption) | Posterior variance across orderings < 0.02 |

---

## Layer 3 — KNN Neighbour Layer

The KNN layer finds the 50 most similar NHANES participants (by cosine distance on questionnaire-derived features) and surfaces lab tests that are disproportionately out of range in that neighbourhood vs the general population. It does not contribute to condition ranking — it exclusively adds lab suggestions downstream of the ML + Bayesian layers.

| Metric | Description | Target |
|---|---|---|
| **Condition-lab recall** | For synthetic profiles with a known target condition, what fraction of the clinically expected labs for that condition appear in the KNN output? (e.g. anemia profile → hemoglobin, MCV, ferritin) | ≥ 50% of condition-expected labs surfaced |
| **Mean signal lift** | Average lift (neighbour abnormality rate ÷ population base rate) across all surfaced signals across the synthetic cohort. Already filtered at lift > 1.5×; this tracks the realised quality above that floor. | Mean lift ≥ 2.5× |
| **Cross-condition differentiation** | Do different condition profiles receive meaningfully different lab recommendations? Measured as Jaccard overlap between the top-5 surfaced labs for any two distinct condition profiles. Low overlap = KNN is condition-sensitive, not returning the same generic labs for everyone. | Pairwise Jaccard overlap < 35% |

---

## Layer 4 — LLM Layer (MedGemma + Safety Filter)

| Metric | Description | Target |
|---|---|---|
| **Condition list match** | Do the conditions mentioned in MedGemma's report match the top conditions from the ML pipeline? | ≥ 95% pass-through fidelity |
| **Hallucination rate** | % of reports mentioning a condition ID not present in the model output | ≤ 5% |
| **Urgency calibration** | Does tone match condition severity? High-severity conditions should not be downplayed | Qualitative review; ≥ 90% appropriate tone on sample |
| **JSON parse success rate** | % of MedGemma responses successfully parsed as valid JSON | ≥ 95% |

---

## End-to-End Metrics

| Metric | Description | Target |
|---|---|---|
| **LLM delta vs models only** | Does the LLM layer add value vs showing raw model scores? | Qualitative + user study |
| **Questionnaire-only degradation** | How much does removing lab values degrade top-3 coverage? | < 10pp degradation (MVP assumption: labs always present) |

---

## Synthetic Cohort Design

All metrics are evaluated on a synthetic cohort of ~600 users (pending Daniela's cohort generation):

- ~50 users per condition (balanced positive/negative/borderline)
- ~30 "healthy" users (no true conditions) to measure over-alert rate
- Demographics balanced across age groups and sex
- Lab values generated to match NHANES distributions

> **Note:** Cohort generation in progress (Daniela). Metrics marked with "on synthetic cohort" above are pending this dependency.

---

## Open Decisions

The following thresholds and rules require validation against the synthetic cohort before being finalised:

1. **Per-condition thresholds** — current values are proposals based on model performance and clinical judgement; to be validated against miss rate and over-alert rate on synthetic cohort
2. **Top-N selection** — currently top-3; to be confirmed based on coverage rate analysis
3. **Composite scoring logic** — how posterior scores from all 11 models are combined and ranked into the final recommendation; to be defined after Layer 1 + 2 eval
4. **Question removal candidates** — Bayesian questions with information gain < 0.02 bits to be identified and reviewed with Anna before removal

---

## Known Limitations & Open Findings

### Iron deficiency model — eval not representative of MVP
The iron deficiency RF v2 model's top discriminative features are `triglycerides_mg_dl` and `total_cholesterol_mg_dl`. Only 38% of synthetic cohort profiles include lab values, meaning 62% of profiles trigger population-average defaults for these features. Result: iron deficiency scores ~0.05 on symptom-only profiles and never clears the threshold.

Since the HalfFull MVP requires Check-up 35 lab upload (which includes cholesterol and triglycerides), real-world performance is expected to be significantly better. The eval results for iron deficiency should be interpreted as worst-case symptom-only performance.

Pending decision: whether to restrict iron deficiency scoring to lab-upload users only, retrain with better indirect features, or remove temporarily.

### Anemia model — gender bias on female profiles
The anemia LR model carries a `gender_female` coefficient of +1.32, causing it to score 0.87–0.97 on most female profiles regardless of symptoms. This structurally suppresses top-1 accuracy for all other female-heavy conditions (perimenopause, menopause, thyroid, iron deficiency).

This is a model-level issue documented in `evals/cohort/optimization_report.md`. A retrain with reduced gender weight or replacement by reproductive features is recommended before final eval.

### Synthetic cohort lab coverage
Only 38% of profiles (229/600) include lab values. For MVP evaluation, regenerating the cohort with lab values for all profiles would more accurately reflect real user journeys. Current results should be treated as a symptom-only baseline.
