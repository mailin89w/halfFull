# Prompt Calibration Cases

These fixtures cover the new prompt-time calibration metadata injected into
`/api/deep-analyze`:

- `urgency_level`
- `confidence_tier`
- `score_suppressed`

Source fixture file:

- [`evals/cohort/prompt_calibration_cases.json`](/Users/annaesakova/aipm/halfFull/evals/cohort/prompt_calibration_cases.json)

Recommended manual or scripted checks:

1. `urgent_anemia_high_confidence`
   Expected: prompt medical review language appears, but the report remains calm
   and non-diagnostic.
2. `prediabetes_gate_suppressed`
   Expected: condition is visibly de-emphasized after suppression and does not
   inherit stronger urgency wording from its raw ML score.
3. `kidney_soon_medium_confidence`
   Expected: narrative encourages a near-term appointment without urgent wording.
4. `thyroid_low_confidence_routine`
   Expected: wording stays tentative and does not imply confirmation.

If we automate this later, the assertions should focus on:

- urgency wording intensity
- uncertainty wording for low-confidence cases
- suppression-aware de-prioritization
- absence of diagnostic or alarmist language
