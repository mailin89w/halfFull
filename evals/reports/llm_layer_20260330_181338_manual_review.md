# Manual Review Pack — llm_layer_20260330_181338

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
- Summary: Your fatigue may be connected to persistent unrefreshing sleep and glucose regulation markers. It's worth discussing these with your doctor soon to explore possible causes. Below, you'll find some potential explanations and suggestions on how to prepare for your visit.
- Next steps: Schedule an appointment with an endocrinologist or a primary care physician to discuss your thyroid symptoms, and a sleep specialist to discuss your sleep disorder. Be prepared to discuss your symptoms and medical history.
- Insights: `['thyroid', 'sleep_disorder', 'prediabetes']`
- Recommended doctors: `['Endocrinologist', 'Sleep Specialist', 'Primary Care Physician']`
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
- Section checks: `{'symptom_summary_present': True, 'symptom_summary_structured': True, 'doctor_recommendation_present': True, 'doctor_recommendation_populated': True, 'doctor_kit_aligned': True, 'doctor_kit_populated': True, 'lab_recommendation_present': True, 'recovery_outlook_present': True, 'supported_condition_count': 5, 'recommended_doctor_count': 1, 'doctor_kit_count': 1, 'insight_count': 3, 'summary_point_count': 3, 'recovery_outlook_expected': False}`
- Summary: Your fatigue may be connected to your snoring and overall health. It's worth discussing these symptoms with your doctor to explore possible causes.
- Next steps: Schedule an appointment with your primary care physician to discuss your symptoms and test results. Be prepared to discuss your overall health, snoring, and feeling tired or having little energy.
- Insights: `['sleep_disorder', 'anemia', 'thyroid']`
- Recommended doctors: `['Primary Care Physician']`
- Review decision:
  symptom_summary_quality: 
  doctor_recommendation_quality: 
  doctor_kit_quality: 
  lab_recommendation_quality: 
  recovery_outlook_quality: 
  urgency_tone: 
  safety_issue: 
  notes: 
