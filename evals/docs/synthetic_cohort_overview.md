# Synthetic Evaluation Cohort — Overview

The HalfFull eval pipeline uses a fully synthetic cohort of **600 user profiles** to stress-test the condition scoring and MedGemma layers without real patient data. All profiles are reproducible via `python evals/cohort_generator.py --seed 42`.

---

## Cohort Composition

| Segment | Count | Description |
|---|---|---|
| Positive | 261 | Strong symptom signal for target condition |
| Borderline | 177 | Attenuated signal (~55% of positive mu) |
| Negative | 112 | Queried for a condition but ruled out (healthy-level symptoms) |
| Healthy controls | 30 | No condition — all symptoms sub-threshold |
| Edge cases | 20 | 2–3 co-morbid conditions, conflicting signals |
| **Total** | **600** | |

---

## Conditions Covered (11)

Each condition gets exactly **50 profiles**, with the positive/borderline/negative split adjusted by real-world prevalence (from model metadata):

| Condition | Positive | Borderline | Negative | Prevalence tier |
|---|---|---|---|---|
| anemia | 25 | 15 | 10 | default |
| electrolyte_imbalance | 25 | 15 | 10 | default |
| hepatitis | 28 | 15 | 7 | rare (<5%) |
| hypothyroidism | 25 | 15 | 10 | default |
| inflammation | 20 | 18 | 12 | common (>15%) |
| iron_deficiency | 25 | 15 | 10 | default |
| kidney_disease | 28 | 15 | 7 | rare (<5%) |
| menopause | 20 | 18 | 12 | common |
| perimenopause | 20 | 18 | 12 | common |
| prediabetes | 20 | 18 | 12 | common |
| sleep_disorder | 25 | 15 | 10 | default |

---

## Profile Structure

Each profile contains:

- **Profile ID** — `SYN-XXXXXXXX` (e.g. `SYN-ANM00001`)
- **Demographics** — age, sex, BMI, smoking status, activity level
- **Symptom vector** — 10 normalised scores [0–1] (`weight_change`: [−1, 1]):
  `fatigue_severity`, `sleep_quality`, `post_exertional_malaise`, `joint_pain`, `cognitive_impairment`, `depressive_mood`, `anxiety_level`, `digestive_symptoms`, `heat_intolerance`, `weight_change`
- **Lab values** — present in ~38% of profiles (229/600); `null` otherwise
- **Quiz path** — `hybrid` (with labs, 229 profiles) or `full` (without labs, 371 profiles)
- **Ground truth** — expected condition(s) with confidence (`high` / `medium` / `low`) and rank

---

## How Distributions Are Generated

Symptom means are **derived from the actual trained models** — not manually set:

- LR coefficients and GB feature importances are loaded at runtime from `.joblib` files
- Mapped from NHANES feature IDs (e.g. `dpq040`) to the 10 symptom dimensions
- Normalised to [0–1] so high-weight features produce high symptom scores in positive profiles
- Clinically linked pairs use **correlated sampling** (e.g. fatigue ↔ post-exertional malaise in anemia, heat intolerance ↔ sleep quality in menopause)

Lab reference ranges come from `data/processed/normalized/nhanes_reference_ranges_used.csv` where available; clinical literature fallbacks are documented inline.

---

## Multi-Condition Profiles

- **Edge cases (20):** always 2–3 conditions; symptom vectors merged with `max()` per dimension — user shows the worst signal of all conditions
- **Co-morbid borderlines:** ~15% of borderline profiles carry a second condition; vectors merged with `average()`

---

## Known Limitations

The `iron_deficiency` LR model carries a large `gender_female` coefficient (+1.32), causing it to score 0.63–0.97 on **all female profiles** regardless of symptoms. This makes it the top-ranked model for most female profiles, which structurally limits top-1 accuracy for perimenopause, menopause, hypothyroidism, and several other conditions when scored against the raw LR layer. Full analysis in `evals/cohort/optimization_report.md`.

---

## Further Reading

- [`evals/docs/concept.md`](concept.md) — Full technical architecture and design rationale
- [`evals/docs/how_to_run_evals.md`](how_to_run_evals.md) — Step-by-step operational guide
- [`evals/cohort/optimization_report.md`](../cohort/optimization_report.md) — Pre/post calibration analysis
