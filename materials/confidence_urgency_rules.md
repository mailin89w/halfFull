# Confidence And Urgency Rules

Live implementation paths:

- `frontend/app/results/page.tsx`
- `frontend/src/lib/clinicalSignals.ts`
- `frontend/src/components/results/DiagnosisCard.tsx`

## Confidence

Per condition, the UI computes a confidence score from:

- ML probability
- Bayesian posterior probability when present
- Condition-specific KNN lab-signal support from `deepAnalyze.knnSignals.lab_signals`

Rendered tiers:

- `Low confidence`
- `Medium confidence`
- `High confidence`

## Urgency Table

| Condition | `Soon` trigger | `Urgent` trigger |
|---|---|---|
| Anemia | Hemoglobin `< 12` or posterior `>= 0.58` | Hemoglobin `< 10` or posterior `>= 0.82` |
| Iron deficiency | Ferritin `< 30` | Ferritin `< 10` |
| Thyroid | TSH `>= 4.5` or low free T4 | TSH `>= 10` or clearly low free T4 with elevated TSH |
| Kidney | eGFR `< 60`, UACR `>= 30`, or creatinine `>= 1.5` | eGFR `< 45` or UACR `>= 300` |
| Sleep disorder | Strong posterior signal | Very high posterior signal |
| Liver | ALT/AST `>= 60` or bilirubin `>= 1.2` | ALT/AST `>= 120` or bilirubin `>= 2.0` |
| Prediabetes | HbA1c `>= 5.7`, fasting glucose `>= 100`, or random glucose `>= 140` | HbA1c `>= 6.5` or fasting glucose `>= 126` |
| Inflammation | CRP `>= 5`, ESR `>= 20`, or WBC `>= 11` | CRP `>= 10`, ESR `>= 40`, or WBC `>= 14` |
| Electrolytes | Mild sodium / potassium / magnesium abnormality | Sodium `< 130` or `> 150`, potassium `< 3` or `> 5.8` |
| Hepatitis | Positive marker or moderate liver enzyme elevation | Positive marker with high concern or ALT `>= 120` |
| Perimenopause | Strong posterior signal | Not biomarker-driven today; only escalates via very high posterior |

## UI behavior

- Every diagnosis card shows confidence tier and urgency tier.
- Any `urgent` diagnosis triggers a prominent CTA banner on the results screen.
