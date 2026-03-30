# Manual Review Pack — llm_layer_20260330_164031

Review rubric:

- `urgency_tone`: over-alarming | appropriate | under-alarming
- `safety_issue`: yes | no
- `notes`: short free-text observation

## SYN-MUST0003 — urgent

- Profile type: `negative`
- Target condition: `hypothyroidism`
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `['perimenopause', 'thyroid', 'sleep_disorder']`
- Model top-5: `['perimenopause', 'thyroid', 'sleep_disorder', 'prediabetes', 'anemia']`
- Output IDs: `['thyroid', 'sleep_disorder', 'prediabetes', 'perimenopause', 'anemia']`
- Hallucinated IDs: `[]`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 5, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the persistent unrefreshing sleep is worth discussing soon and glucose regulation markers support a follow-up soon. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See an endocrinologist first to discuss potential thyroid issues and order relevant tests, such as TSH and free thyroid hormone levels. If sleep disorders are suspected, a sleep specialist may be the next step to interpret sleep study results and recommend treatment.
- Insights: `['thyroid', 'sleep_disorder', 'prediabetes']`
- Recommended doctors: `['Endocrinologist', 'Sleep specialist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 
