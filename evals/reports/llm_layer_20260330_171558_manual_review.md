# Manual Review Pack — llm_layer_20260330_171558

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
- Summary: You've shared some concerning symptoms, including fatigue and unrefreshing sleep. It's possible that these could be related to thyroid function or glucose regulation issues. It's worth discussing these with a specialist to understand what might be going on and what the next steps could be.
- Next steps: It's worth discussing your symptoms with an endocrinologist first to understand your thyroid function and potential metabolic issues, and then considering a consultation with a sleep specialist if your sleep issues persist.
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
- Summary: You've shared some concerns about fatigue, snoring, and overall health. It's worth exploring these issues further to understand what might be contributing to your symptoms. Below, you'll find some ideas on potential causes and which doctors to see first, as well as tips on how to prepare for your visit.
- Next steps: See a GP first to discuss your symptoms and undergo initial tests, such as a Complete Blood Count and TSH and Free T4 levels. If necessary, a referral to a sleep specialist or an endocrinologist may be the next step for further evaluation and treatment.
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
