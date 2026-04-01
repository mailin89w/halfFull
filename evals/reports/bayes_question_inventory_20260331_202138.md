# Bayes Question Inventory — bayes_question_inventory_20260331_202138

- Source of truth: `bayesian/lr_tables.json`
- Approx eval gain metric below: mean posterior lift for the owning condition when that question was actually used on the 760-person cohort.
- Caveat: this is not causal per-question lift; questions interact within the same Bayesian update.

## 2. Currently Off

- `anemia_q3`
- `elec_q1`
- `hep_q1`
- `peri_q1`
- `prediabetes_q2`
- `thyroid_q4`
- `thyroid_q5`

## 4. Shared Across Diseases

- `heavy_periods`: `anemia_q1`, `iron_q1`, `peri_q4`
- `unusual_blood_loss`: `anemia_q2`, `iron_q3`
- `blood_donation`: `anemia_q3`, `iron_q4`
- `vegetarian`: `anemia_q4`, `iron_q2`
- `nocturia`: `kidney_q3`, `prediabetes_q3`
- `snoring`: `sleep_q2`
- `alcohol_intake`: `elec_q1`, `hep_q1`, `liver_q1`
- `jaundice`: `hep_q2`, `liver_q4`

## 5. Derived From Quiz

- Direct quiz-derived question ids: `kidney_q3`, `liver_q1`, `peri_q3`, `prediabetes_q3`, `sleep_q2`, `sleep_q5`
- Indirectly shared from quiz-derived answers: `elec_q1`, `hep_q1`

## 1 + 3. Full Inventory With LR And Approx Eval Gain

| Condition | QID | On? | Shared? | Quiz-derived? | Question | LR answers | Approx eval gain | Uses | Condition recall gain |
|-----------|-----|-----|---------|---------------|----------|------------|------------------|------|-----------------------|
| anemia | `anemia_q1` | on | heavy_periods |  | Do you have heavy periods lasting more than 7 days, with at least 3 days being heavy or very heavy? | yes=2.4 (low); no=0.53 (medium) | -0.025 | 760 | +25.4 pp |
| anemia | `anemia_q2` | on | unusual_blood_loss |  | Have you noticed any unusual blood loss — for example in your urine, stools, nosebleeds, or elsewhere? | yes=3.5 (medium); no=0.74 (medium) | -0.025 | 760 | +25.4 pp |
| anemia | `anemia_q3` | off | blood_donation |  | Have you donated blood in the last 12 months? | yes=2.0 (medium); no=0.85 (low) | -0.025 | 760 | +25.4 pp |
| anemia | `anemia_q4` | on | vegetarian |  | Are you vegetarian or vegan? | yes=1.8 (medium); no=0.88 (low) | -0.025 | 760 | +25.4 pp |
| anemia | `anemia_q5` | on |  |  | Do you get short of breath, lightheaded, or feel your heart racing with mild exertion that used to feel easy? | yes=2.2 (medium); no=0.82 (low) | +0.000 | 0 | +25.4 pp |
| iron_deficiency | `iron_q1` | on | heavy_periods |  | Do you have heavy periods lasting more than 7 days, with at least 3 days being heavy or very heavy? | yes=3.5 (medium); no=0.5 (medium) | +0.052 | 760 | +39.5 pp |
| iron_deficiency | `iron_q2` | on | vegetarian |  | Are you vegetarian or vegan? | yes=2.5 (medium); no=0.75 (medium) | +0.052 | 760 | +39.5 pp |
| iron_deficiency | `iron_q3` | on | unusual_blood_loss |  | Have you noticed any unusual blood loss — for example in your urine, stools, nosebleeds, or elsewhere? | yes=4.0 (medium); no=0.72 (medium) | +0.052 | 760 | +39.5 pp |
| iron_deficiency | `iron_q4` | on | blood_donation |  | Have you donated blood in the last 12 months? | yes=2.5 (medium); no=0.83 (low) | +0.052 | 760 | +39.5 pp |
| iron_deficiency | `iron_q5` | on |  |  | Do you ever have strong cravings to chew ice, raw starch, dirt, or other non-food substances? | yes=5.8 (medium); no=0.62 (medium) | +0.052 | 760 | +39.5 pp |
| thyroid | `thyroid_q1` | on |  |  | Have you lost or gained more than 5% of your body weight in the last 3 months? | gained=1.6 (low); lost=0.5 (medium); no=0.7 (medium) | -0.044 | 760 | +18.0 pp |
| thyroid | `thyroid_q2` | on |  |  | Do you often feel cold when others around you do not? | yes=3.5 (medium); no=0.65 (medium) | -0.044 | 760 | +18.0 pp |
| thyroid | `thyroid_q3` | on |  |  | Have you noticed your skin becoming drier, or your hair becoming coarser or falling out more than usual? | yes=5.0 (medium); no=0.75 (medium) | -0.044 | 760 | +18.0 pp |
| thyroid | `thyroid_q4` | off |  |  | Have you been constipated more than usual (fewer than 3 bowel movements per week)? | yes=2.0 (high); no=0.8 (medium) | -0.044 | 760 | +18.0 pp |
| thyroid | `thyroid_q5` | off |  |  | For how long have you been experiencing this tiredness every day? | lt_4w=0.6 (low); 4_12w=1.0 (low); 12w_6m=1.5 (low); gt_6m=1.4 (low) | -0.044 | 760 | +18.0 pp |
| kidney | `kidney_q1` | on |  |  | Have you noticed blood in your urine, or has your urine appeared dark, foamy, or brown? | yes=4.0 (low); no=0.75 (medium) | +0.027 | 760 | +61.5 pp |
| kidney | `kidney_q2` | on |  |  | Have you noticed any swelling in your ankles, feet, or around your eyes, particularly in the morning? | yes=3.5 (low); no=0.72 (low) | +0.027 | 760 | +61.5 pp |
| kidney | `kidney_q3` | on | nocturia | direct | Do you wake up at night to urinate, and has this become more frequent recently? | yes=2.0 (low); no=0.85 (low) | +0.027 | 760 | +61.5 pp |
| kidney | `kidney_q4` | on |  |  | Have you lost or gained more than 5% of your body weight in the last 3 months without trying? | yes_loss=2.5 (low); no=0.88 (low) | +0.027 | 760 | +61.5 pp |
| sleep_disorder | `sleep_q1` | on |  |  | Do you wake up at night choking, gasping for air, or feeling like you cannot breathe? | yes=3.3 (high); no=0.71 (medium) | -0.142 | 760 | +1.5 pp |
| sleep_disorder | `sleep_q2` | on | snoring | direct | Do you snore loudly (loud enough to be heard through a closed door)? | yes=1.1 (high); no=0.6 (medium) | -0.142 | 760 | +1.5 pp |
| sleep_disorder | `sleep_q3` | on |  |  | Do you fall asleep involuntarily during the day — for example while driving, watching TV, or in a meeting? | yes=2.3 (medium); no=0.68 (medium) | -0.142 | 760 | +1.5 pp |
| sleep_disorder | `sleep_q4` | on |  |  | Even when you sleep for a full night, do you wake up feeling unrefreshed or as tired as when you went to bed? | yes=1.6 (medium); no=0.75 (low) | -0.142 | 760 | +1.5 pp |
| sleep_disorder | `sleep_q5` | on |  | direct | Do you have difficulty falling or staying asleep at least 3 nights per week? | yes=2.0 (medium); no=0.55 (medium) | -0.142 | 760 | +1.5 pp |
| liver | `liver_q1` | on | alcohol_intake | direct | How many standard alcoholic drinks do you have per week? (1 drink = 1 glass of wine, 1 bottle of beer, or 1 shot of spirits) | high_risk=4.5 (low); moderate=2.0 (medium); low=0.65 (medium); none=0.35 (medium) | +0.032 | 760 | +5.9 pp |
| liver | `liver_q2` | on |  |  | Have you noticed small red spider-like marks on your skin, especially on your chest, shoulders, or face? | yes=4.3 (high); no=0.75 (high) | +0.032 | 760 | +5.9 pp |
| liver | `liver_q3` | on |  |  | Has your abdomen become noticeably swollen or distended, or have you been told you have fluid in your belly? | yes=7.2 (high); no=0.37 (high) | +0.032 | 760 | +5.9 pp |
| liver | `liver_q4` | on | jaundice |  | Have you noticed any yellowing of your skin or the whites of your eyes? | yes=3.8 (high); no=0.65 (medium) | +0.032 | 760 | +5.9 pp |
| liver | `liver_q5` | on |  |  | Have your ankles or legs become swollen, or do you bruise more easily than before? | yes=3.2 (medium); no=0.78 (low) | +0.032 | 760 | +5.9 pp |
| prediabetes | `prediabetes_q1` | on |  |  | Have you gained more than 5% of your body weight in the last 3 months? | yes=2.0 (low); no=0.8 (low) | +0.028 | 760 | +8.2 pp |
| prediabetes | `prediabetes_q2` | off |  |  | Do you feel unusually thirsty most days, even when you have had enough to drink? | yes=3.0 (low); no=0.73 (medium) | +0.028 | 760 | +8.2 pp |
| prediabetes | `prediabetes_q3` | on | nocturia | direct | Do you urinate more frequently than usual, including waking at night to urinate? | yes=2.5 (medium); no=0.78 (medium) | +0.028 | 760 | +8.2 pp |
| prediabetes | `prediabetes_q4` | on |  |  | Overall, how would you describe your level of physical activity? | none=1.8 (low); moderate=1.0 (low); intensive=0.6 (low) | +0.028 | 760 | +8.2 pp |
| inflammation | `inflam_q1` | on |  |  | Have you had fevers, night sweats, or felt feverish without a clear explanation in the last 6 weeks? | yes=2.8 (medium); no=0.8 (medium) | +0.028 | 760 | +23.2 pp |
| inflammation | `inflam_q2` | on |  |  | Have you had a recent infection or a lingering inflammatory illness in the last 6 weeks? | yes=2.6 (medium); no=0.72 (medium) | +0.028 | 760 | +23.2 pp |
| inflammation | `inflam_q3` | on |  |  | Do you have swollen joints or morning stiffness lasting more than 30 minutes? | yes=3.0 (medium); no=0.72 (medium) | +0.028 | 760 | +23.2 pp |
| inflammation | `inflam_q4` | on |  |  | Have you had swollen glands, mouth ulcers, rashes, or red/painful eyes along with the fatigue? | yes=2.4 (medium); no=0.84 (low) | +0.000 | 0 | +23.2 pp |
| electrolytes | `elec_q1` | off | alcohol_intake | indirect | How many standard alcoholic drinks do you have per week? | high_risk=3.0 (medium); moderate=1.5 (low); low_none=0.75 (low) | +0.003 | 760 | +12.4 pp |
| electrolytes | `elec_q2` | on |  |  | Have you had prolonged vomiting or diarrhoea for more than 2 days, or obvious dehydration, in the past 2 weeks? | yes=4.0 (low); no=0.72 (low) | +0.003 | 760 | +12.4 pp |
| electrolytes | `elec_q3` | on |  |  | Do you get muscle cramps or twitching together with weakness, tingling, palpitations, or feeling faint? | yes=2.6 (medium); no=0.78 (low) | +0.003 | 760 | +12.4 pp |
| electrolytes | `elec_q4` | on |  |  | Do you take diuretics (water pills), laxatives, antacids, or other medicines that have caused dehydration or low potassium before? | yes=3.4 (low); no=0.76 (low) | +0.003 | 760 | +12.4 pp |
| hepatitis | `hep_q1` | off | alcohol_intake | indirect | How many standard alcoholic drinks do you have per week? | high_risk=3.5 (high); moderate=1.3 (medium); low_none=0.5 (medium) | +0.036 | 760 | +23.7 pp |
| hepatitis | `hep_q2` | on | jaundice |  | Have you noticed any yellowing of your skin or the whites of your eyes? | yes=8.0 (low); no=0.55 (medium) | +0.036 | 760 | +23.7 pp |
| hepatitis | `hep_q3` | on |  |  | Have you had any of the following in the past: a blood transfusion before 1992, tattooing or piercing with shared equipment, or intravenous drug use? | yes=5.0 (low); no=0.55 (medium) | +0.036 | 760 | +23.7 pp |
| hepatitis | `hep_q4` | on |  |  | Have you had dark urine, pale stools, or pain/discomfort under the right ribs along with the fatigue? | yes=3.2 (medium); no=0.78 (low) | +0.036 | 760 | +23.7 pp |
| perimenopause | `peri_q1` | off |  |  | Do you think you might be going through the menopause transition or perimenopause? | yes=1.83 (high); no=0.27 (high) | +0.018 | 760 | +0.0 pp |
| perimenopause | `peri_q2` | on |  |  | Do you experience hot flushes — sudden feelings of intense heat in your face, neck, or chest? | yes=3.1 (high); no=0.5 (medium) | +0.018 | 760 | +0.0 pp |
| perimenopause | `peri_q2b` | on |  |  | Do you wake up at night drenched in sweat, even when your bedroom is not hot? | yes=1.9 (high); no=0.6 (medium) | +0.018 | 760 | +0.0 pp |
| perimenopause | `peri_q2c` | on |  |  | Have you noticed vaginal dryness or discomfort during sex that is new or getting worse? | yes=2.6 (high); no=0.65 (medium) | +0.018 | 760 | +0.0 pp |
| perimenopause | `peri_q3` | on |  | direct | Have your menstrual cycles become irregular — either shorter, longer, or skipping months? | yes=3.5 (high); no=0.45 (medium) | +0.018 | 760 | +0.0 pp |
| perimenopause | `peri_q4` | on | heavy_periods |  | Do you have heavy periods lasting more than 7 days, with at least 3 days being heavy or very heavy? | yes=2.0 (medium); no=0.75 (medium) | +0.018 | 760 | +0.0 pp |
| perimenopause | `peri_q5` | on |  |  | Have you noticed changes in your mood, such as increased irritability, anxiety, or low mood, particularly linked to your cycle? | yes=2.2 (medium); no=0.72 (medium) | +0.018 | 760 | +0.0 pp |
| vitamin_b12_deficiency | `b12_q1` | on |  |  | Do you take metformin most days, or have you taken it regularly for at least 6 months? | yes=2.2 (medium); no=0.85 (low) | +0.000 | 0 | +0.0 pp |
| vitamin_b12_deficiency | `b12_q2` | on |  |  | Do you take acid-suppressing medication like omeprazole, pantoprazole, or famotidine most days for more than 3 months? | yes=1.8 (medium); no=0.9 (low) | +0.000 | 0 | +0.0 pp |
| vitamin_b12_deficiency | `b12_q3` | on |  |  | Do you avoid most animal products, or follow a vegan diet? | yes=2.0 (medium); no=0.85 (low) | +0.000 | 0 | +0.0 pp |
| vitamin_b12_deficiency | `b12_q4` | on |  |  | Have you ever been told you have pernicious anemia, autoimmune gastritis, Crohn's disease, celiac disease, or had bowel surgery affecting absorption? | yes=3.2 (medium); no=0.8 (low) | +0.000 | 0 | +0.0 pp |
| vitamin_b12_deficiency | `b12_q5` | on |  |  | Have you had new tingling or numbness in your hands or feet, trouble with balance, or unexplained memory changes? | yes=1.6 (low); no=0.9 (low) | +0.000 | 0 | +0.0 pp |
| vitamin_d_deficiency | `vitd_q1` | on |  |  | Do your thighs or hips feel weak when rising from a chair, climbing stairs, or getting up from the floor? | yes=2.0 (low); no=0.8 (low) | +0.000 | 0 | +3.4 pp |
| vitamin_d_deficiency | `vitd_q2` | on |  |  | Do you have deep aching bone pain in your low back, pelvis, hips, ribs, or legs, especially with standing or walking? | yes=1.8 (low); no=0.85 (low) | +0.000 | 0 | +3.4 pp |
| vitamin_d_deficiency | `vitd_q3` | on |  |  | Have you been falling more often, or has your walking become noticeably slower, more unsteady, or waddling because your legs feel weak? | yes=1.7 (low); no=0.9 (low) | +0.000 | 0 | +3.4 pp |
| vitamin_d_deficiency | `vitd_q4` | on |  |  | Have you ever had a low-trauma fracture, stress fracture, or been told you might have a pseudofracture? | yes=3.0 (low); no=0.95 (low) | +0.000 | 0 | +3.4 pp |
| vitamin_d_deficiency | `vitd_q5` | on |  |  | When someone presses on your shins, ribs, hips, or breastbone, do they feel unusually tender or painful? | yes=1.5 (low); no=0.9 (low) | +0.000 | 0 | +3.4 pp |