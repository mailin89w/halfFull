# Manual Review Pack — llm_layer_20260330_171810

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
- Summary: You've shared some concerns about your fatigue, and it's worth discussing your persistent unrefreshing sleep and glucose regulation markers with a doctor soon. This could be a good opportunity to explore some possible causes and develop a plan to address them.
- Next steps: See an endocrinologist first to discuss your thyroid symptoms and determine if a blood test is needed. If your symptoms are related to a sleep disorder, a sleep specialist may be the next step to help you get a proper diagnosis and treatment.
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

## SYN-C0000021 — routine

- Profile type: `borderline`
- Target condition: `hepatitis`
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `[]`
- Model top-5: `['sleep_disorder', 'prediabetes', 'thyroid', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'prediabetes', 'thyroid', 'electrolytes']`
- Hallucinated IDs: `[]`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 4, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the dpq040___feeling_tired_or_having_little_energy: 0.567, ocq670___overall_work_schedule_past_3_months: 0.4285, and huq010___general_health_condition: 3.4. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See your GP first to discuss your fatigue and potential sleep disorder, and then consider a specialist if further evaluation is needed.
- Insights: `['sleep_disorder', 'prediabetes', 'thyroid']`
- Recommended doctors: `['GP', 'Endocrinologist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-MUST0001 — hallucination

- Profile type: `negative`
- Target condition: `sleep_disorder`
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `['sleep_disorder', 'anemia', 'thyroid']`
- Model top-5: `['sleep_disorder', 'anemia', 'thyroid', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'anemia', 'thyroid', 'iron_deficiency', 'electrolytes', 'kidney']`
- Hallucinated IDs: `['iron_deficiency']`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 6, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the snoring more than once per night and overall health described as >3.5. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See a GP first to discuss your fatigue, heavy periods, disrupted sleep schedule, and night sweats. If the GP suspects a sleep disorder, they may refer you to a sleep specialist for further evaluation.
- Insights: `['sleep_disorder', 'anemia', 'thyroid']`
- Recommended doctors: `['GP', 'Endocrinologist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-T0000025 — healthy

- Profile type: `healthy`
- Target condition: ``
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `[]`
- Model top-5: `['sleep_disorder', 'thyroid', 'prediabetes', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'thyroid', 'prediabetes', 'iron_deficiency', 'electrolytes']`
- Hallucinated IDs: `['iron_deficiency']`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 5, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is not a standalone symptom — it's worth looking into how it connects with your heavy periods and disrupted sleep schedule. You mentioned experiencing night sweats, which may be related to your fatigue. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See your GP first for a referral to a sleep specialist and to discuss your thyroid issues. If your sleep test confirms sleep apnea, a sleep specialist is the natural next step for CPAP evaluation.
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
