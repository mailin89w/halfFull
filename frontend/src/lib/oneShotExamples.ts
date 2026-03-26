/**
 * V6 one-shot examples for the Groq synthesis prompt.
 * Each example shows: MedGemma grounding JSON → ideal synthesis output.
 * Groq sees only the grounding JSON — no raw patient data.
 */

// ─── Example 1: Iron deficiency + perimenopause ───────────────────────────────

const EXAMPLE_1_INPUT = `{
  "supportedSuspicions": [
    {
      "diagnosisId": "iron_deficiency",
      "confidence": "probable",
      "anchorEvidence": "Patient reported 8-day periods with clotting for 6+ months and rates fatigue at 3/3",
      "reasoning": "Heavy prolonged menstrual bleeding is the most common cause of iron-loss anaemia in premenopausal women. Combined with 3/3 fatigue severity and no other identified source of blood loss, iron deficiency is the highest-probability explanation for the symptom cluster.",
      "keySymptoms": [
        "Fatigue rated 3 out of 3, worst in the mornings and not improved by sleep",
        "Heavy periods lasting 8 days with visible clotting, ongoing for 6 months",
        "Cold hands and feet even in warm environments",
        "Shortness of breath climbing one flight of stairs"
      ],
      "recommendedTests": [
        "Full blood count (FBC) with reticulocyte count",
        "Serum ferritin (target >50 µg/L for symptom resolution)",
        "Serum iron and TIBC",
        "B12 and folate to exclude concurrent deficiency"
      ]
    },
    {
      "diagnosisId": "perimenopause",
      "confidence": "possible",
      "anchorEvidence": "Age 44, irregular cycles (24–40 day range for 8 months), and night sweats 3–4 times per week",
      "reasoning": "Cycle length variability beyond 7 days from baseline, combined with vasomotor symptoms at age 44, meets clinical criteria for perimenopause. The irregular bleeding also exacerbates iron loss.",
      "keySymptoms": [
        "Irregular menstrual cycles ranging 24–40 days for the past 8 months",
        "Night sweats 3–4 nights per week, disrupting sleep",
        "Mood changes described as unexplained irritability and low mood",
        "Concentration difficulties affecting work performance"
      ],
      "recommendedTests": [
        "FSH and LH (day 2–5 of cycle if regular enough, or random if not)",
        "Oestradiol",
        "AMH for ovarian reserve context",
        "Thyroid function (TSH) to exclude thyroid as confound"
      ]
    }
  ],
  "declinedSuspicions": [
    { "diagnosisId": "thyroid", "reason": "No TSH in record; Bayesian answers did not confirm weight change or hair loss." }
  ],
  "medicationFlags": [],
  "recommendedSpecialties": [
    {
      "specialty": "GP",
      "priority": "start_here",
      "clinicalReason": "GP is the right entry point to order FBC, ferritin, iron studies, and hormone markers in a single visit, and to refer onward.",
      "symptomsToRaise": [
        "Fatigue rated 3/3, every day for 3 months, worst in the mornings",
        "Shortness of breath on minimal exertion (one flight of stairs)",
        "8-day periods with clotting ongoing for 6 months"
      ],
      "testsToRequest": ["FBC with reticulocyte count", "Serum ferritin, iron, TIBC", "FSH, LH, oestradiol", "TSH"],
      "discussionPoints": [
        "My ferritin has never been checked but I lose significant blood each cycle — I'd like to know if iron deficiency is driving this level of fatigue",
        "My cycles have become irregular (24–40 days) and I'm having night sweats 3–4 nights a week — I'd like to discuss whether this could be perimenopause"
      ]
    },
    {
      "specialty": "Gynaecologist",
      "priority": "consider_next",
      "clinicalReason": "Heavy prolonged bleeding with probable perimenopause warrants specialist assessment for uterine pathology and hormonal management options.",
      "symptomsToRaise": [
        "8-day periods with clotting, heavier than baseline, ongoing 6 months",
        "Cycle length variability of 24–40 days for 8 months",
        "Night sweats 3–4 nights per week and mood changes"
      ],
      "testsToRequest": ["Pelvic ultrasound to exclude fibroids or polyps", "Review FSH/LH/oestradiol results from GP"],
      "discussionPoints": [
        "I want to understand whether there is a structural cause (fibroids, polyps) before starting any hormonal treatment",
        "Given my age and cycle irregularity, I'd like to discuss the evidence for HRT to manage both perimenopausal symptoms and heavy bleeding"
      ]
    }
  ]
}`;

const EXAMPLE_1_OUTPUT = `{
  "summaryPoints": [
    "Fatigue rated 3 out of 3, every day for the past 3 months, worst in the mornings and not improved by sleep",
    "Shortness of breath climbing a single flight of stairs — a level of exertion that didn't cause this previously",
    "Periods lasting 8 days with visible clotting, consistently heavier than baseline for the past 6 months",
    "Night sweats 3–4 nights per week, disrupting sleep and contributing to daytime exhaustion",
    "Menstrual cycle now ranging 24–40 days — irregular for the past 8 months",
    "Mood changes including unexplained irritability and difficulty concentrating at work"
  ],
  "personalizedSummary": "Your assessment shows a pattern of high-severity daily fatigue alongside significant menstrual changes — heavier and more irregular periods, plus night sweats several nights a week. This is a screening tool, not a diagnosis, but the pattern is clear enough to warrant a targeted blood panel and a conversation with your doctor.",
  "insights": [
    {
      "diagnosisId": "iron_deficiency",
      "confidence": "probable",
      "personalNote": "The combination of prolonged heavy bleeding each cycle with your level of fatigue is a strong clinical signal for iron deficiency. When blood is lost monthly at this volume, the body can struggle to maintain adequate iron stores — and low ferritin causes the kind of fatigue that sleep doesn't fix. This hasn't been tested yet, which makes it a high priority."
    },
    {
      "diagnosisId": "perimenopause",
      "confidence": "possible",
      "personalNote": "Your cycle length has shifted from a consistent pattern to a 16-day range of variability over 8 months, and night sweats have appeared at a clinically significant frequency. At 44, this timing and symptom combination is consistent with early perimenopausal hormonal changes. Importantly, irregular and heavier bleeding in perimenopause can also worsen iron loss — the two are likely interacting."
    }
  ],
  "nextSteps": "Start with your GP for a blood panel covering iron, ferritin, and hormone markers — one visit can gather the evidence for both suspected conditions at once. Depending on those results, a gynaecologist referral is the logical next step to assess the heavy bleeding and discuss hormonal management options.",
  "doctorKitSummary": "I've been experiencing severe daily fatigue for 3 months, shortness of breath on minimal exertion, and significantly heavier periods with clotting for 6 months. I'm 44 and my cycles have become irregular, with night sweats several nights a week.",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [
    {
      "specialty": "GP",
      "priority": "start_here",
      "reason": "Your GP can order the full blood panel needed to test both iron deficiency and hormonal markers in a single visit, and refer you to the right specialist based on results.",
      "symptomsToDiscuss": ["Fatigue rated 3/3, every day for 3 months, worst in the mornings", "Shortness of breath on minimal exertion (one flight of stairs)", "8-day periods with clotting ongoing for 6 months"],
      "suggestedTests": ["FBC with reticulocyte count", "Serum ferritin, iron, TIBC", "FSH, LH, oestradiol", "TSH"]
    },
    {
      "specialty": "Gynaecologist",
      "priority": "consider_next",
      "reason": "A gynaecologist can investigate whether there is a structural cause for the heavy bleeding and advise on hormonal management for both the perimenopause and cycle changes.",
      "symptomsToDiscuss": ["8-day periods with clotting, heavier than baseline, ongoing 6 months", "Cycle length variability of 24–40 days for 8 months", "Night sweats 3–4 nights per week and mood changes"],
      "suggestedTests": ["Pelvic ultrasound to exclude fibroids or polyps", "Review FSH/LH/oestradiol results from GP"]
    }
  ],
  "doctorKits": [
    {
      "specialty": "GP",
      "openingSummary": "I'm here because I've had severe daily fatigue for 3 months alongside significant changes to my periods and new night sweats. I'd like to investigate iron deficiency and possible perimenopause with a blood panel today.",
      "bringToAppointment": ["Period diary or app data showing cycle lengths and flow for the past 3 months", "List of any supplements or medications currently taking", "Note of any family history of thyroid or gynaecological conditions"],
      "concerningSymptoms": ["Fatigue rated 3/3, every day for 3 months, worst in the mornings", "Shortness of breath on minimal exertion (one flight of stairs)", "8-day periods with clotting ongoing for 6 months"],
      "recommendedTests": ["FBC with reticulocyte count", "Serum ferritin, iron, TIBC", "FSH, LH, oestradiol", "TSH"],
      "discussionPoints": ["My ferritin has never been checked but I lose significant blood each cycle — I'd like to know if iron deficiency is driving this level of fatigue", "My cycles have become irregular (24–40 days) and I'm having night sweats 3–4 nights a week — I'd like to discuss whether this could be perimenopause"],
      "whatToSay": "I suspect iron deficiency from heavy periods and possible early perimenopause — I'd like to rule both in or out with blood tests today. My priority is understanding why my fatigue is so severe that it's affecting my daily function."
    },
    {
      "specialty": "Gynaecologist",
      "openingSummary": "I've been referred because my periods have become significantly heavier and more irregular over the past 8 months, and I want to understand whether there is a structural cause before starting any hormonal treatment.",
      "bringToAppointment": ["GP referral letter and blood results (FBC, ferritin, FSH, oestradiol)", "Period diary showing flow, duration, and clotting pattern over the past 3 months", "List of any current medications or supplements"],
      "concerningSymptoms": ["8-day periods with clotting, heavier than baseline, ongoing 6 months", "Cycle length variability of 24–40 days for 8 months", "Night sweats 3–4 nights per week and mood changes"],
      "recommendedTests": ["Pelvic ultrasound to exclude fibroids or polyps", "Review FSH/LH/oestradiol results from GP"],
      "discussionPoints": ["My periods have been significantly heavier for 6 months — I want to understand whether there is a structural cause (fibroids, polyps) before starting any hormonal treatment", "Given my age and cycle irregularity, I'd like to discuss HRT options to manage both perimenopausal symptoms and the heavy bleeding"],
      "whatToSay": "I want to rule out fibroids or polyps as a cause of my heavier bleeding before we discuss hormonal management. I'm also open to discussing HRT if perimenopause is confirmed — I'd like to understand my options."
    }
  ],
  "allClear": false
}`;

// ─── Example 2: Prediabetes + sleep apnea ────────────────────────────────────

const EXAMPLE_2_INPUT = `{
  "supportedSuspicions": [
    {
      "diagnosisId": "prediabetes",
      "confidence": "possible",
      "anchorEvidence": "Patient reported increased thirst, frequent urination 4–5 times per night, and BMI 32 with recent 8kg weight gain over 12 months",
      "reasoning": "Polydipsia, nocturia, high BMI, and recent weight gain represent the canonical early metabolic risk pattern. Bayesian answers confirmed post-meal fatigue and increased hunger — both consistent with glycaemic dysregulation.",
      "keySymptoms": [
        "Increased thirst throughout the day, drinking 4+ litres daily",
        "Waking 4–5 times per night to urinate",
        "Fatigue worst in the afternoon, 2–3 hours after meals",
        "Increased hunger shortly after meals, not resolved by normal portions",
        "BMI 32 with 8kg weight gain over the past 12 months"
      ],
      "recommendedTests": ["Fasting plasma glucose", "HbA1c", "Fasting lipid panel", "Blood pressure measurement"]
    },
    {
      "diagnosisId": "sleep_disorder",
      "confidence": "possible",
      "anchorEvidence": "Partner confirmed loud snoring and observed breathing pauses; patient reports waking unrefreshed on 7 hours sleep and rated daytime sleepiness at 2/3",
      "reasoning": "Witnessed apnoeas combined with unrefreshing sleep, daytime hypersomnolence, and morning headaches on 4/7 days form a clinical triad highly specific to obstructive sleep apnoea. The nocturia is also a recognised consequence of OSA.",
      "keySymptoms": [
        "Partner-witnessed breathing pauses during sleep, several times per night",
        "Loud snoring confirmed by partner",
        "Waking unrefreshed despite 7 hours of sleep",
        "Morning headaches 4 out of 7 days",
        "Daytime sleepiness rated 2 out of 3"
      ],
      "recommendedTests": ["Home sleep apnoea test (HST) or polysomnography referral", "Epworth Sleepiness Scale score documentation"]
    }
  ],
  "declinedSuspicions": [
    { "diagnosisId": "iron_deficiency", "reason": "No menstrual blood loss; no dietary restriction; Bayesian answers did not confirm cold intolerance or breathlessness on exertion." },
    { "diagnosisId": "thyroid", "reason": "Weight gain better explained by metabolic and sleep factors; Bayesian answers did not confirm constipation or slowed cognition." }
  ],
  "medicationFlags": [],
  "recommendedSpecialties": [
    {
      "specialty": "GP",
      "priority": "start_here",
      "clinicalReason": "GP can order fasting glucose and HbA1c and initiate the sleep apnoea pathway via a home test referral in a single visit.",
      "symptomsToRaise": ["Increased thirst, drinking 4+ litres daily", "Waking 4–5 times per night to urinate", "Fatigue worst 2–3 hours after meals", "Partner-witnessed breathing pauses and loud snoring"],
      "testsToRequest": ["Fasting plasma glucose and HbA1c", "Fasting lipid panel", "Blood pressure", "Home sleep apnoea test referral"],
      "discussionPoints": [
        "I have multiple features of prediabetes — polydipsia, nocturia, post-meal fatigue, and recent weight gain — and I'd like fasting glucose and HbA1c to find out where I stand",
        "My partner has observed me stopping breathing during sleep and I wake with a headache most mornings — I'd like a home sleep test to rule out OSA"
      ]
    },
    {
      "specialty": "Sleep specialist",
      "priority": "consider_next",
      "clinicalReason": "Witnessed apnoeas, unrefreshing sleep, morning headaches, and daytime sleepiness meet the threshold for formal evaluation. A sleep specialist can interpret the home test and initiate CPAP if indicated.",
      "symptomsToRaise": ["Partner-witnessed breathing pauses several times per night", "Waking unrefreshed on 7 hours sleep", "Morning headaches 4 out of 7 days", "Daytime sleepiness affecting concentration"],
      "testsToRequest": ["Polysomnography if home sleep test inconclusive", "CPAP titration study if OSA confirmed"],
      "discussionPoints": [
        "My partner has observed breathing pauses — I want to understand my AHI score and whether CPAP is indicated",
        "My nocturia (4–5 times per night) may be a consequence of OSA rather than a bladder problem — I'd like to discuss whether treating OSA might reduce it"
      ]
    }
  ]
}`;

const EXAMPLE_2_OUTPUT = `{
  "summaryPoints": [
    "Persistent thirst throughout the day, drinking over 4 litres — significantly above normal intake",
    "Waking 4–5 times per night to urinate, severely fragmenting sleep",
    "Fatigue that peaks 2–3 hours after meals and improves temporarily with eating — a cyclical pattern",
    "Partner-confirmed loud snoring with witnessed breathing pauses during sleep",
    "Waking unrefreshed despite 7 hours in bed, with morning headaches on most days",
    "8kg weight gain over the past 12 months alongside increased hunger shortly after meals"
  ],
  "personalizedSummary": "Your assessment shows two intersecting patterns: a metabolic picture — thirst, post-meal fatigue, recent weight gain — alongside a sleep disruption picture with witnessed breathing pauses and unrefreshing sleep. This is a screening tool, not a diagnosis, but the combination is specific enough to warrant blood tests and a sleep evaluation.",
  "insights": [
    {
      "diagnosisId": "prediabetes",
      "confidence": "possible",
      "personalNote": "The pairing of increased thirst with fatigue that spikes a few hours after eating suggests blood sugar may not be staying within normal range after meals. Your recent weight gain is also an established risk factor for early metabolic changes. None of this is confirmed — it needs a fasting glucose and HbA1c test — but the pattern is specific enough to prioritise."
    },
    {
      "diagnosisId": "sleep_disorder",
      "confidence": "possible",
      "personalNote": "Breathing pauses witnessed by your partner, combined with waking unrefreshed and morning headaches most days, form a clinical pattern highly associated with obstructive sleep apnoea. Your frequent night-time urination is also a recognised consequence of untreated sleep apnoea — it's not necessarily a bladder problem. A home sleep test would clarify this quickly."
    }
  ],
  "nextSteps": "See your GP first for a fasting blood test and a home sleep apnoea test referral — both can be initiated in a single appointment. If the sleep test confirms apnoea, a sleep specialist is the natural next step for CPAP evaluation.",
  "doctorKitSummary": "I'm experiencing persistent thirst, post-meal fatigue, significant recent weight gain, and partner-witnessed breathing pauses during sleep. I'd like to test for prediabetes and obstructive sleep apnoea today.",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [
    {
      "specialty": "GP",
      "priority": "start_here",
      "reason": "Your GP can run the metabolic blood panel and initiate the sleep apnoea pathway in one visit — the most efficient starting point for both suspected conditions.",
      "symptomsToDiscuss": ["Increased thirst, drinking 4+ litres daily", "Waking 4–5 times per night to urinate", "Fatigue worst 2–3 hours after meals", "Partner-witnessed breathing pauses and loud snoring"],
      "suggestedTests": ["Fasting plasma glucose and HbA1c", "Fasting lipid panel", "Blood pressure", "Home sleep apnoea test referral"]
    },
    {
      "specialty": "Sleep specialist",
      "priority": "consider_next",
      "reason": "A sleep specialist can interpret your home test result and initiate CPAP if obstructive sleep apnoea is confirmed — this is beyond GP scope for complex cases.",
      "symptomsToDiscuss": ["Partner-witnessed breathing pauses several times per night", "Waking unrefreshed on 7 hours sleep", "Morning headaches 4 out of 7 days", "Daytime sleepiness affecting concentration"],
      "suggestedTests": ["Polysomnography if home sleep test inconclusive", "CPAP titration study if OSA confirmed"]
    }
  ],
  "doctorKits": [
    {
      "specialty": "GP",
      "openingSummary": "I'm here because I've had persistent thirst, post-meal fatigue, and an 8kg weight gain over the past year — I'd like to test for prediabetes. I also want to discuss my sleep: my partner witnesses me stopping breathing, and I wake with a headache most mornings.",
      "bringToAppointment": ["3-day food and fluid diary showing typical intake", "1-week log of night-time awakenings (keep before the appointment)", "List of any current medications or supplements"],
      "concerningSymptoms": ["Increased thirst, drinking 4+ litres daily", "Waking 4–5 times per night to urinate", "Fatigue worst 2–3 hours after meals", "Partner-witnessed breathing pauses and loud snoring"],
      "recommendedTests": ["Fasting plasma glucose and HbA1c", "Fasting lipid panel", "Blood pressure", "Home sleep apnoea test referral"],
      "discussionPoints": ["I have multiple features of prediabetes — polydipsia, nocturia, post-meal fatigue, and recent weight gain — I'd like fasting glucose and HbA1c today", "My partner has observed me stopping breathing during sleep and I wake with a headache most mornings — I'd like a home sleep test to rule out OSA"],
      "whatToSay": "I'm here to investigate prediabetes and possible sleep apnoea — two things that may be connected. I'd like fasting glucose, HbA1c, and a home sleep test referral today if possible."
    },
    {
      "specialty": "Sleep specialist",
      "openingSummary": "I've been referred for possible obstructive sleep apnoea. My partner witnesses me stopping breathing several times a night, I wake unrefreshed on 7 hours sleep, and I have morning headaches most days.",
      "bringToAppointment": ["Home sleep test results from GP if already completed", "Sleep diary: 2 weeks of bedtime, wake time, number of awakenings", "Partner's written account of witnessed events if they can provide one"],
      "concerningSymptoms": ["Partner-witnessed breathing pauses several times per night", "Waking unrefreshed on 7 hours sleep", "Morning headaches 4 out of 7 days", "Daytime sleepiness affecting concentration"],
      "recommendedTests": ["Polysomnography if home sleep test inconclusive", "CPAP titration study if OSA confirmed"],
      "discussionPoints": ["My partner has observed breathing pauses — I want to understand my AHI score and whether CPAP is indicated", "My nocturia (4–5 times per night) may be a consequence of OSA — I'd like to discuss whether treating it might reduce night-time urination"],
      "whatToSay": "I'm here because my partner confirms I stop breathing during sleep, and I wake with a headache most mornings despite 7 hours in bed. I'd like to confirm whether I have OSA and, if so, start CPAP treatment."
    }
  ],
  "allClear": false
}`;

// ─── Example 3: All-clear (no supported suspicions) ──────────────────────────

const EXAMPLE_3_INPUT = `{
  "supportedSuspicions": [],
  "declinedSuspicions": [
    { "diagnosisId": "iron_deficiency", "reason": "Normal menstrual pattern; no breathlessness on exertion; Bayesian answers did not confirm cold intolerance or palpitations." },
    { "diagnosisId": "sleep_disorder", "reason": "Fatigue severity rated 1/3; patient reports feeling refreshed on waking; no snoring; Bayesian answers confirmed adequate 7–8 hour sleep." },
    { "diagnosisId": "thyroid", "reason": "No weight change, no hair loss, no cold intolerance; Bayesian answers did not confirm constipation or slowed cognition." }
  ],
  "medicationFlags": [],
  "recommendedSpecialties": []
}`;

const EXAMPLE_3_OUTPUT = `{
  "summaryPoints": [],
  "personalizedSummary": "Your answers didn't reveal a pattern that points toward any of the 11 fatigue-related conditions we screen for. The signals that would support conditions like iron deficiency, thyroid dysfunction, or sleep apnoea were individually assessed and didn't hold up against your specific answers.",
  "insights": [],
  "nextSteps": "No specialist referral is indicated based on your current symptom picture. If your symptoms change or worsen, it's worth repeating this assessment or speaking with your GP.",
  "doctorKitSummary": "",
  "doctorKitQuestions": [],
  "doctorKitArguments": [],
  "recommendedDoctors": [],
  "doctorKits": [],
  "allClear": true
}`;

// ─── Formatted example strings (input + output together) ─────────────────────

function formatExample(input: string, output: string): string {
  return `INPUT CLINICAL EVIDENCE:\n${input}\n\nIDEAL OUTPUT:\n${output}`;
}

export const ONE_SHOT_EXAMPLE_1 = formatExample(EXAMPLE_1_INPUT, EXAMPLE_1_OUTPUT);
export const ONE_SHOT_EXAMPLE_2 = formatExample(EXAMPLE_2_INPUT, EXAMPLE_2_OUTPUT);
export const ONE_SHOT_EXAMPLE_3 = formatExample(EXAMPLE_3_INPUT, EXAMPLE_3_OUTPUT);

// ─── Dynamic example selector ────────────────────────────────────────────────

interface GroundingResultForSelection {
  supportedSuspicions: Array<{ diagnosisId: string }>;
}

/**
 * Selects the most relevant one-shot example based on the MedGemma grounding result.
 * - All-clear (no supported suspicions) → Example 3
 * - Prediabetes or sleep_disorder present → Example 2
 * - All other cases (iron, perimenopause, thyroid, etc.) → Example 1
 */
export function selectOneShotExample(grounding: GroundingResultForSelection): string {
  const ids = grounding.supportedSuspicions.map((s) => s.diagnosisId);

  if (ids.length === 0) return ONE_SHOT_EXAMPLE_3;

  if (ids.some((id) => id === 'prediabetes' || id === 'sleep_disorder')) {
    return ONE_SHOT_EXAMPLE_2;
  }

  return ONE_SHOT_EXAMPLE_1;
}
