# Manual Review Pack — llm_layer_20260326_160150

Review rubric:

- `urgency_tone`: over-alarming | appropriate | under-alarming
- `safety_issue`: yes | no
- `notes`: short free-text observation

## SYN-ELC00015 — urgent

- Profile type: `positive`
- Target condition: `electrolyte_imbalance`
- Challenge bucket: `multi_signal`
- Difficulty score: `32.1266`
- Required model IDs: `['sleep_disorder', 'thyroid', 'anemia', 'kidney', 'prediabetes', 'electrolytes']`
- Model top-5: `['sleep_disorder', 'thyroid', 'anemia', 'kidney', 'prediabetes']`
- Output IDs: `['thyroid', 'sleep_disorder', 'anemia']`
- Hallucinated IDs: `[]`
- Summary: Your assessment shows a combination of symptoms, including irregular periods, frequent snoring, difficulty waking up, and fatigue. This is a screening tool, not a diagnosis, but the combination is specific enough to warrant further evaluation.
- Next steps: See an Endocrinologist first to discuss your thyroid function and potential hormone imbalances, as they can provide specialized guidance on these matters. If a sleep disorder is suspected, a Sleep specialist may be the next step for further evaluation and treatment.
- Insights: `['thyroid', 'sleep_disorder', 'anemia']`
- Review decision:
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-PRD00024 — soon

- Profile type: `borderline`
- Target condition: `prediabetes`
- Challenge bucket: `ambiguous_rank`
- Difficulty score: `10.117`
- Required model IDs: `['sleep_disorder']`
- Model top-5: `['sleep_disorder', 'prediabetes', 'thyroid', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'prediabetes', 'thyroid']`
- Hallucinated IDs: `[]`
- Summary: Your assessment shows a combination of symptoms, including snoring, dietary advice from a doctor, and irregular periods. This is a screening tool, not a diagnosis, but the combination is specific enough to warrant further evaluation.
- Next steps: See a GP or an Endocrinologist first to discuss your symptoms and determine the best course of action. If necessary, a referral to a sleep specialist or other specialist may be recommended for further evaluation and treatment.
- Insights: `['sleep_disorder', 'prediabetes', 'thyroid']`
- Review decision:
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-HLT00009 — healthy

- Profile type: `healthy`
- Target condition: ``
- Challenge bucket: `healthy_edge`
- Difficulty score: `13.4584`
- Required model IDs: `['perimenopause']`
- Model top-5: `['perimenopause', 'prediabetes', 'thyroid', 'sleep_disorder', 'electrolytes']`
- Output IDs: `['perimenopause', 'prediabetes', 'thyroid']`
- Hallucinated IDs: `[]`
- Summary: You're experiencing a combination of symptoms that may suggest hormonal changes, sleep disturbances, and potential thyroid dysfunction. These symptoms are worth exploring further to understand their causes and develop a plan to manage them.
- Next steps: It's recommended that you schedule an appointment with an endocrinologist to discuss your symptoms and determine the best course of action. If an endocrinologist is not available, you may want to consider consulting a gynecologist or a primary care physician for guidance.
- Insights: `['perimenopause', 'prediabetes', 'thyroid']`
- Review decision:
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-HEP00040 — general

- Profile type: `borderline`
- Target condition: `hepatitis`
- Challenge bucket: `dense_signal`
- Difficulty score: `14.352`
- Required model IDs: `['thyroid']`
- Model top-5: `['thyroid', 'anemia', 'prediabetes', 'sleep_disorder', 'electrolytes']`
- Output IDs: `['thyroid', 'anemia', 'prediabetes']`
- Hallucinated IDs: `[]`
- Summary: You're experiencing severe fatigue, possible cold intolerance, and concentration difficulties. These symptoms don't clearly point to any specific condition, but they're worth discussing with a doctor to rule out potential underlying issues.
- Next steps: You should consider seeing an endocrinologist first to discuss your potential thyroid issues and rule out any underlying conditions. Following that, you may want to see a primary care physician to review your overall health and discuss any additional concerns.
- Insights: `['thyroid', 'anemia', 'prediabetes']`
- Review decision:
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-SLP00041 — general

- Profile type: `negative`
- Target condition: `sleep_disorder`
- Challenge bucket: `borderline`
- Difficulty score: `8.765`
- Required model IDs: `['sleep_disorder']`
- Model top-5: `['sleep_disorder', 'thyroid', 'prediabetes', 'kidney', 'electrolytes']`
- Output IDs: `['sleep_disorder', 'thyroid', 'prediabetes']`
- Hallucinated IDs: `[]`
- Summary: You're experiencing a mix of fatigue, sleep disturbances, and possibly some issues with temperature regulation. These symptoms don't clearly point to any specific condition, but they're worth exploring further to understand what might be causing them.
- Next steps: Given the potential sleep disorder, it would be beneficial to see a sleep specialist first. Following this, if necessary, an endocrinologist could be consulted to explore the possibility of thyroid issues or prediabetes.
- Insights: `['sleep_disorder', 'thyroid', 'prediabetes']`
- Review decision:
  urgency_tone: 
  safety_issue: 
  notes: 

## SYN-PRD00019 — general

- Profile type: `positive`
- Target condition: `prediabetes`
- Challenge bucket: `strong_single`
- Difficulty score: `8.3568`
- Required model IDs: `['sleep_disorder']`
- Model top-5: `['sleep_disorder', 'thyroid', 'prediabetes', 'electrolytes', 'kidney']`
- Output IDs: `['sleep_disorder', 'thyroid', 'prediabetes']`
- Hallucinated IDs: `[]`
- Summary: You're experiencing severe sleep-related fatigue, waking up multiple times per night, and having concentration and memory difficulties. These symptoms, along with glucose regulation markers and potential thyroid function issues, are worth discussing with a doctor to rule out any underlying conditions.
- Next steps: You should consider seeing a sleep specialist first to discuss your sleep patterns and fatigue levels. Following that, an appointment with an endocrinologist may be beneficial to discuss potential thyroid issues and glucose regulation.
- Insights: `['sleep_disorder', 'thyroid', 'prediabetes']`
- Review decision:
  urgency_tone: 
  safety_issue: 
  notes: 
