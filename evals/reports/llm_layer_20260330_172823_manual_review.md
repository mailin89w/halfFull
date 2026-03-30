# Manual Review Pack — llm_layer_20260330_172823

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
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 5, 'recommended_doctor_count': 3, 'doctor_kit_count': 3, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the persistent unrefreshing sleep is worth discussing soon and glucose regulation markers support a follow-up soon. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See your GP first for a review of your thyroid function and to discuss your sleep. If necessary, a sleep specialist will be the next step for further evaluation and treatment.
- Insights: `['thyroid', 'sleep_disorder', 'prediabetes']`
- Recommended doctors: `['GP', 'Endocrinologist', 'Sleep specialist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-T0000025 — routine

- Profile type: `healthy`
- Target condition: ``
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `[]`
- Model top-5: `['sleep_disorder', 'thyroid', 'prediabetes', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'thyroid', 'prediabetes', 'electrolytes']`
- Hallucinated IDs: `[]`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 4, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is not a standalone symptom — it's worth looking into how it connects with how often you snore while sleeping, which is above the typical threshold for sleep disorder. You also mentioned heavy periods, which might be related to the heavy periods you mentioned. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See your GP first for a referral to a sleep specialist and a thyroid test. If the sleep specialist confirms a sleep disorder, they can guide further treatment.
- Insights: `['sleep_disorder', 'thyroid', 'prediabetes']`
- Recommended doctors: `['GP', 'Sleep specialist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-MUST0001 — general

- Profile type: `negative`
- Target condition: `sleep_disorder`
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `['sleep_disorder', 'anemia', 'thyroid']`
- Model top-5: `['sleep_disorder', 'anemia', 'thyroid', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'anemia', 'thyroid', 'electrolytes', 'kidney']`
- Hallucinated IDs: `[]`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 5, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the snoring more than once per night and overall health described as >3.5. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See your GP first for a complete blood count and a sleep study referral. If the sleep study confirms sleep apnea, a sleep specialist is the natural next step for further evaluation.
- Insights: `['sleep_disorder', 'anemia', 'thyroid']`
- Recommended doctors: `['GP', 'Sleep specialist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 
