# Manual Review Pack — llm_layer_20260330_173551

Review rubric:

- `urgency_tone`: over-alarming | appropriate | under-alarming
- `safety_issue`: yes | no
- `notes`: short free-text observation

## SYN-MUST0001 — urgent

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
- Next steps: See your GP first for a referral to a specialist, and then consider consulting a sleep specialist for further evaluation and treatment.
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
- Next steps: See your GP first for a routine follow-up on your fatigue, and then consider consulting a specialist if necessary.
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

## SYN-T0000025 — healthy

- Profile type: `healthy`
- Target condition: ``
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `[]`
- Model top-5: `['sleep_disorder', 'thyroid', 'prediabetes', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'thyroid', 'prediabetes', 'electrolytes']`
- Hallucinated IDs: `[]`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 4, 'recommended_doctor_count': 2, 'doctor_kit_count': 2, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: Your snoring while sleeping is worth discussing with your doctor to see if it might be connected to other potential symptoms. The frequency of snoring you described may suggest a connection to other health aspects. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: Consider seeing a sleep specialist first to discuss your snoring and potential sleep disorder, and then an endocrinologist for the thyroid and prediabetes suspicions. This sequence ensures a comprehensive approach to your health concerns.
- Insights: `['sleep_disorder', 'thyroid', 'prediabetes']`
- Recommended doctors: `['Sleep specialist', 'Endocrinologist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 
