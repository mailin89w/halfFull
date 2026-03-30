# Manual Review Pack — llm_layer_20260330_165813

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
- Next steps: See an endocrinologist first to discuss your thyroid function and potential thyroid issues, as well as to order the necessary blood tests. If your endocrinologist suspects a sleep disorder, they may refer you to a sleep specialist for further evaluation and treatment.
- Insights: `['thyroid', 'sleep_disorder', 'prediabetes']`
- Recommended doctors: `['Endocrinologist', 'Sleep Specialist']`
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
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 4, 'recommended_doctor_count': 3, 'doctor_kit_count': 3, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the dpq040___feeling_tired_or_having_little_energy: 0.567, ocq670___overall_work_schedule_past_3_months: 0.4285, and huq010___general_health_condition: 3.4. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See a GP or an endocrinologist first to discuss your symptoms and undergo initial testing. If necessary, a sleep specialist may be recommended for further evaluation and treatment of potential sleep disorders.
- Insights: `['sleep_disorder', 'prediabetes', 'thyroid']`
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
- Summary: From what you shared, your snoring while sleeping is worth looking into how it connects with your overall health. The frequency of snoring you described may suggest a connection to other aspects of your well-being. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See a GP or a relevant specialist first to discuss your symptoms and determine the best course of action. Depending on the initial assessment, you may be referred to a specialist for further evaluation and treatment.
- Insights: `['sleep_disorder', 'thyroid', 'prediabetes']`
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

## SYN-MUST0001 — general

- Profile type: `negative`
- Target condition: `sleep_disorder`
- Challenge bucket: `random`
- Difficulty score: `None`
- Required model IDs: `['sleep_disorder', 'anemia', 'thyroid']`
- Model top-5: `['sleep_disorder', 'anemia', 'thyroid', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'anemia', 'thyroid', 'electrolytes', 'kidney']`
- Hallucinated IDs: `[]`
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': False, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 5, 'recommended_doctor_count': 3, 'doctor_kit_count': 3, 'insight_count': 3, 'summary_point_count': 0, 'recovery_outlook_expected': False}`
- Summary: From what you shared, your fatigue is connected to the snoring more than once per night and overall health described as >3.5. This is worth investigating further. Below you can see some hypotheses on the root causes and which doctors to see first, and how to prepare for your visit.
- Next steps: See a GP or an internist first to discuss your symptoms and determine the best course of action. If necessary, a referral to a sleep specialist or an endocrinologist may be the next step for further evaluation and treatment.
- Insights: `['sleep_disorder', 'anemia', 'thyroid']`
- Recommended doctors: `['GP', 'Sleep specialist', 'Endocrinologist']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 
