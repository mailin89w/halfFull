// ─── Types ─────────────────────────────────────────────────────────────────

export type SignalStrength = 'strong' | 'moderate' | 'investigating';

export interface LabTest {
  name: string;
  note?: string;
  mustRequest?: boolean; // not in routine bloodwork
}

export interface Diagnosis {
  id: string;
  emoji: string;
  title: string;
  signal: SignalStrength;
  description: string;
  tests: LabTest[];
  prognosis: {
    timeframe: string;
    detail: string;
  };
}

export interface Doctor {
  specialty: string;
  icon: string;
  badge: string;
  reason: string;
}

export interface AssessmentResults {
  currentPct: number;   // 0–100, position on energy spectrum
  projectedPct: number; // 0–100, projected after treatment
  summaryLine: string;
  diagnoses: Diagnosis[];
  doctors: Doctor[];
}

// ─── Signal helper ─────────────────────────────────────────────────────────

function signal(score: number): SignalStrength {
  if (score >= 7) return 'strong';
  if (score >= 4) return 'moderate';
  return 'investigating';
}

function mlSignal(prob: number): SignalStrength {
  if (prob >= 0.65) return 'strong';
  if (prob >= 0.45) return 'moderate';
  return 'investigating';
}

// ─── ML condition catalogue ─────────────────────────────────────────────────

const ML_CONDITIONS: Record<string, Omit<Diagnosis, 'signal'>> = {
  anemia: {
    id: 'anemia',
    emoji: '🩸',
    title: 'Anemia',
    description:
      'Low red blood cell count or hemoglobin reduces oxygen delivery to tissues, causing fatigue, weakness, and shortness of breath. Common in women, vegetarians, and those with chronic conditions.',
    tests: [
      { name: 'Full CBC (hemoglobin, hematocrit, MCV)', mustRequest: false },
      { name: 'Ferritin', note: 'Iron-storage marker — request by name', mustRequest: true },
      { name: 'Serum iron + TIBC' },
      { name: 'Vitamin B12 + Folate' },
      { name: 'Reticulocyte count', note: 'Assesses bone marrow response' },
    ],
    prognosis: {
      timeframe: '4–12 weeks with treatment',
      detail: 'Dietary or supplementation changes for iron/B12 deficiency typically show energy improvement within 6–8 weeks.',
    },
  },
  iron_deficiency: {
    id: 'iron_deficiency',
    emoji: '⚙️',
    title: 'Iron Deficiency',
    description:
      'Iron stores can be depleted even when hemoglobin appears normal — ferritin below 50 ng/mL impairs cellular energy production, causing fatigue, brain fog, and restless legs.',
    tests: [
      { name: 'Ferritin', note: 'NOT in standard CBC — request specifically', mustRequest: true },
      { name: 'Transferrin saturation', note: 'Below 20% is significant' },
      { name: 'Serum iron + TIBC' },
      { name: 'Full CBC' },
    ],
    prognosis: {
      timeframe: '3–6 months to optimal ferritin',
      detail: 'Most people notice energy improvement within 6–8 weeks of iron supplementation. Reaching optimal ferritin (≥50 ng/mL) takes 4–6 months.',
    },
  },
  thyroid: {
    id: 'thyroid',
    emoji: '🦋',
    title: 'Thyroid Dysfunction',
    description:
      "TSH alone misses subclinical dysfunction. Fatigue, cold intolerance, weight changes, and brain fog alongside normal TSH warrant Free T3/T4 testing.",
    tests: [
      { name: 'TSH' },
      { name: 'Free T3', mustRequest: true },
      { name: 'Free T4', mustRequest: true },
      { name: 'Anti-TPO antibodies', note: "Screens for Hashimoto's", mustRequest: true },
    ],
    prognosis: {
      timeframe: '2–4 months to notable improvement',
      detail: 'When thyroid levels are properly optimised, most patients see clear energy and cognitive gains within 6–12 weeks.',
    },
  },
  kidney: {
    id: 'kidney',
    emoji: '🫘',
    title: 'Kidney Function',
    description:
      'Reduced kidney filtration affects fluid balance, blood pressure regulation, and erythropoietin production — all of which drive fatigue. Often asymptomatic early.',
    tests: [
      { name: 'eGFR (estimated glomerular filtration rate)' },
      { name: 'Creatinine + BUN' },
      { name: 'Urine albumin-to-creatinine ratio (UACR)', mustRequest: true },
      { name: 'Urine dipstick / microscopy' },
    ],
    prognosis: {
      timeframe: 'Varies by cause and stage',
      detail: 'Early CKD management (blood pressure control, diet) can slow progression significantly. Specialist follow-up is recommended.',
    },
  },
  sleep_disorder: {
    id: 'sleep_disorder',
    emoji: '😴',
    title: 'Sleep Disorder',
    description:
      'Waking unrefreshed despite adequate hours often indicates disrupted deep or REM sleep — from sleep apnea, restless legs, or elevated cortisol. None of these appear on routine panels.',
    tests: [
      { name: 'Sleep study (polysomnography)', note: 'Rules out sleep apnea', mustRequest: true },
      { name: 'Morning cortisol (fasting, before 9am)', mustRequest: true },
      { name: 'Ferritin', note: 'Primary driver of RLS and fragmented sleep' },
      { name: 'Vitamin D (25-OH)' },
    ],
    prognosis: {
      timeframe: '1–3 months once cause identified',
      detail: 'CPAP for sleep apnea typically improves energy within 2–4 weeks. RLS resolves within 4–8 weeks of iron restoration.',
    },
  },
  liver: {
    id: 'liver',
    emoji: '🫁',
    title: 'Liver Health',
    description:
      'The liver processes hormones, nutrients, and toxins. Elevated enzymes or fatty liver impair metabolism, causing fatigue, brain fog, and digestive symptoms.',
    tests: [
      { name: 'Liver function panel (ALT, AST, GGT, ALP, bilirubin)' },
      { name: 'Albumin' },
      { name: 'Liver ultrasound', note: 'Screens for fatty liver or structural changes', mustRequest: true },
    ],
    prognosis: {
      timeframe: '3–6 months with lifestyle changes',
      detail: 'Non-alcoholic fatty liver often improves substantially with dietary changes and weight management within 6 months.',
    },
  },
  prediabetes: {
    id: 'prediabetes',
    emoji: '🍬',
    title: 'Prediabetes / Insulin Resistance',
    description:
      'Impaired glucose regulation causes energy crashes, brain fog, increased thirst, and fatigue — often years before a diabetes diagnosis. Frequently missed on standard panels.',
    tests: [
      { name: 'Fasting glucose' },
      { name: 'HbA1c (glycated hemoglobin)' },
      { name: 'Fasting insulin', mustRequest: true },
      { name: 'HOMA-IR (calculated)', note: 'Measures insulin resistance', mustRequest: true },
    ],
    prognosis: {
      timeframe: '3–6 months with lifestyle changes',
      detail: 'Dietary changes and increased physical activity can reverse prediabetes and restore energy regulation within a few months.',
    },
  },
  inflammation: {
    id: 'inflammation',
    emoji: '🔥',
    title: 'Chronic Inflammation',
    description:
      'Persistent low-grade inflammation suppresses energy, disrupts sleep, and accelerates fatigue. Often linked to diet, gut health, chronic infections, or autoimmune processes.',
    tests: [
      { name: 'hsCRP (high-sensitivity C-reactive protein)', mustRequest: true },
      { name: 'ESR (erythrocyte sedimentation rate)' },
      { name: 'Full CBC with differential' },
      { name: 'ANA panel', note: 'Screens for autoimmune causes', mustRequest: true },
    ],
    prognosis: {
      timeframe: '3–12 months depending on cause',
      detail: 'Identifying and addressing the underlying trigger (diet, gut, infection, autoimmune) is key. Many see improvement within 3 months of targeted intervention.',
    },
  },
  electrolytes: {
    id: 'electrolytes',
    emoji: '⚡',
    title: 'Electrolyte Imbalance',
    description:
      'Sodium, potassium, magnesium, and calcium regulate muscle function, nerve signalling, and hydration. Imbalances cause fatigue, muscle cramps, and brain fog — often missed on standard panels.',
    tests: [
      { name: 'Comprehensive metabolic panel (sodium, potassium, calcium, CO2)' },
      { name: 'Magnesium (RBC magnesium preferred)', mustRequest: true },
      { name: 'Phosphorus' },
    ],
    prognosis: {
      timeframe: 'Days to weeks with correction',
      detail: 'Electrolyte imbalances often resolve quickly once identified and corrected through diet, hydration, or targeted supplementation.',
    },
  },
  hepatitis: {
    id: 'hepatitis',
    emoji: '🦠',
    title: 'Hepatitis Markers',
    description:
      'Viral hepatitis (B or C) can be asymptomatic for years while causing progressive liver damage and chronic fatigue. Routine screening is not always done.',
    tests: [
      { name: 'Hepatitis B surface antigen (HBsAg)' },
      { name: 'Hepatitis C antibody (Anti-HCV)' },
      { name: 'Liver function panel (ALT, AST)' },
    ],
    prognosis: {
      timeframe: 'Variable — requires specialist management',
      detail: 'Modern antivirals for hepatitis C achieve cure rates above 95%. Hepatitis B can be managed long-term. Early detection significantly improves outcomes.',
    },
  },
  perimenopause: {
    id: 'perimenopause',
    emoji: '🌸',
    title: 'Perimenopause / Hormonal Transition',
    description:
      'Fluctuating estrogen and progesterone during the years before menopause cause fatigue, sleep disruption, brain fog, mood shifts, and temperature dysregulation — frequently misattributed to stress or depression.',
    tests: [
      { name: 'FSH (follicle-stimulating hormone)' },
      { name: 'Estradiol (E2)' },
      { name: 'AMH (anti-Müllerian hormone)', note: 'Ovarian reserve marker', mustRequest: true },
      { name: 'TSH', note: 'Rule out thyroid (overlapping symptoms)' },
    ],
    prognosis: {
      timeframe: '2–6 months on HRT to significant relief',
      detail: 'Hormone replacement therapy or targeted interventions significantly improve quality of life. Many women notice sleep and energy improvement within 6–8 weeks.',
    },
  },
};

/**
 * Build a Diagnosis[] from ML model scores.
 * Only includes conditions above the threshold, sorted by probability.
 */
export function buildDiagnosesFromML(
  mlScores: Record<string, number>,
  threshold = 0.35
): Diagnosis[] {
  return Object.entries(mlScores)
    .filter(([, prob]) => prob >= threshold)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)
    .map(([condition, prob]) => {
      const def = ML_CONDITIONS[condition];
      if (!def) return null;
      return { ...def, signal: mlSignal(prob) } as Diagnosis;
    })
    .filter((d): d is Diagnosis => d !== null);
}

// ─── All possible diagnoses (pool) ─────────────────────────────────────────

function buildDiagnosisPool(scores: Record<string, number>): Record<string, Diagnosis> {
  return {
    iron: {
      id: 'iron',
      emoji: '🩸',
      title: 'Iron / Ferritin Depletion',
      signal: signal(scores.iron),
      description:
        'Ferritin — your iron storage protein — can sit within the "normal" lab range while still being too low for cellular function. Fatigue, brain fog, breathlessness, and restless legs are classic signs. Frequently missed because standard panels measure serum iron, not ferritin.',
      tests: [
        { name: 'Ferritin', note: 'NOT included in a standard CBC — request by name', mustRequest: true },
        { name: 'Serum iron' },
        { name: 'TIBC (Total Iron Binding Capacity)' },
        { name: 'Transferrin saturation', note: 'Below 20% is significant even with normal ferritin' },
        { name: 'Full CBC (hemoglobin, MCV, MCH)' },
      ],
      prognosis: {
        timeframe: '3–6 months to significant recovery',
        detail:
          'With supplementation and dietary adjustments, most people notice a real energy shift within 6–8 weeks. Reaching optimal ferritin (≥50 ng/mL) typically takes 4–6 months.',
      },
    },

    thyroid: {
      id: 'thyroid',
      emoji: '🦋',
      title: 'Subclinical Hypothyroidism',
      signal: signal(scores.thyroid),
      description:
        "TSH alone misses roughly 30% of subclinical thyroid dysfunction. Morning grogginess, cold hands, weight shifts, and brain fog alongside persistent fatigue are a strong thyroid signal — especially when TSH looks 'fine' but Free T3 is low.",
      tests: [
        { name: 'TSH' },
        { name: 'Free T3', note: 'Routinely excluded — request explicitly', mustRequest: true },
        { name: 'Free T4', note: 'Request alongside Free T3', mustRequest: true },
        {
          name: 'Anti-TPO antibodies',
          note: "Screens for Hashimoto's autoimmune thyroiditis",
          mustRequest: true,
        },
        {
          name: 'Reverse T3',
          note: 'Only if T3/T4 borderline; request via GP or endocrinologist',
        },
      ],
      prognosis: {
        timeframe: '2–4 months to notable improvement',
        detail:
          'When thyroid levels are optimised — not just "in range" — most patients report clear energy and cognitive gains within 6–12 weeks of correct treatment.',
      },
    },

    sleep: {
      id: 'sleep',
      emoji: '😴',
      title: 'Sleep Architecture Disruption',
      signal: signal(scores.sleep),
      description:
        'Waking unrefreshed despite adequate hours usually means disrupted deep or REM sleep — not simply "not enough" sleep. Common drivers include subclinical sleep apnea, iron deficiency (restless legs), and elevated evening cortisol — none of which appear on routine panels.',
      tests: [
        {
          name: 'Sleep study (polysomnography)',
          note: 'Rules out sleep apnea — ask your GP for a referral',
          mustRequest: true,
        },
        {
          name: 'Morning cortisol (fasting, before 9am)',
          note: 'Elevated evening cortisol fragments deep sleep',
          mustRequest: true,
        },
        { name: 'Ferritin', note: 'Primary driver of RLS and fragmented sleep' },
        { name: 'Vitamin D (25-OH)' },
      ],
      prognosis: {
        timeframe: '1–3 months once cause identified',
        detail:
          'Sleep apnea treated with CPAP typically improves energy within 2–4 weeks. RLS-related disruption resolves within 4–8 weeks of iron restoration.',
      },
    },

    vitamins: {
      id: 'vitamins',
      emoji: '☀️',
      title: 'Vitamin D & B12 Insufficiency',
      signal: signal(scores.vitamins),
      description:
        "B12 and Vitamin D deficiencies are among the most under-detected fatigue drivers and are frequently missed because labs only flag 'deficiency', not 'insufficiency'. B12 problems are especially common with plant-based diets or any gut absorption issues.",
      tests: [
        {
          name: 'Vitamin D (25-OH)',
          note: 'Optimal range for fatigue is 50–80 ng/mL — not just ≥20',
        },
        { name: 'Vitamin B12' },
        { name: 'Folate (B9)' },
        {
          name: 'MMA (Methylmalonic Acid)',
          note: 'More sensitive B12 marker — request if B12 is borderline',
          mustRequest: true,
        },
        {
          name: 'Homocysteine',
          note: 'Elevated with B12/folate insufficiency; also a cardiovascular marker',
        },
      ],
      prognosis: {
        timeframe: '2–3 months to full effect',
        detail:
          'B12 injections or high-dose oral supplements produce noticeable energy gains within 4–8 weeks. Vitamin D optimisation typically shows full effect at 3 months.',
      },
    },

    stress: {
      id: 'stress',
      emoji: '🧠',
      title: 'Cortisol / HPA Axis Dysregulation',
      signal: signal(scores.stress),
      description:
        "Sustained stress dysregulates your cortisol rhythm — your body's primary energy and arousal signal. Classic pattern: groggy in the morning, crashing in the afternoon, wired but exhausted at night. This won't show on standard panels unless you specifically test cortisol at the right times.",
      tests: [
        {
          name: 'Morning cortisol (fasting serum, before 9am)',
          note: 'Timing is critical — a mid-afternoon draw is clinically useless',
          mustRequest: true,
        },
        {
          name: 'DHEA-S',
          note: 'Adrenal reserve marker; declines with chronic stress',
          mustRequest: true,
        },
        {
          name: '4-point salivary cortisol curve',
          note: 'Shows daily pattern — available via functional medicine GP',
          mustRequest: true,
        },
        { name: 'CRP (C-reactive protein)', note: 'Inflammation marker elevated with chronic stress' },
      ],
      prognosis: {
        timeframe: '3–12 months depending on duration',
        detail:
          'HPA dysregulation responds best to sleep consistency, pacing, and stress reduction — alongside targeted supplementation (magnesium, ashwagandha). Most see meaningful improvement within 3 months of consistent effort.',
      },
    },

    postviral: {
      id: 'postviral',
      emoji: '🦠',
      title: 'Post-Viral / Long COVID Pattern',
      signal: signal(scores.postviral),
      description:
        'Post-exertional fatigue that worsens after activity — especially when onset followed a viral illness — is a key signature of post-viral syndromes including Long COVID and ME/CFS. This pattern does NOT appear in standard bloodwork and requires specialist recognition.',
      tests: [
        { name: 'CRP + ESR (inflammation markers)' },
        { name: 'Full CBC with differential' },
        { name: 'Ferritin' },
        {
          name: 'COVID antibodies (if history unclear)',
          note: 'Confirms prior infection',
          mustRequest: true,
        },
        {
          name: 'ANA panel (antinuclear antibodies)',
          note: 'Screens for autoimmune triggers post-viral',
          mustRequest: true,
        },
        { name: 'Cortisol + DHEA-S', note: 'Post-viral syndromes often dysregulate the HPA axis' },
      ],
      prognosis: {
        timeframe: '6–18 months with pacing protocol',
        detail:
          'Recovery requires strict pacing — avoiding pushing through fatigue, which worsens the condition. Gradual improvement is typical over 6–12 months when post-exertional crashes are consistently avoided.',
      },
    },
  };
}

// ─── Main computation ───────────────────────────────────────────────────────
//
// Answer keys match the JSON decision tree question IDs (q0.0 format).
// Option values are the JSON-defined internal values (e.g. 'lab_yes', 'iron_yes').
//
export function computeResults(answers: Record<string, unknown>): AssessmentResults {

  // ── Sleep signals ──────────────────────────────────────────────────────────
  // q1.2 stores a numeric 1–10 from AnswerScale
  const sleepQuality = Number(answers['q1.2']) || 5;

  // q1.4 is multi_select, values like 'issue_restless_legs'
  const sleepIssues: string[] = Array.isArray(answers['q1.4']) ? answers['q1.4'] : [];
  const hasRLS = sleepIssues.includes('issue_restless_legs');

  // q1.3 wake frequency ordinal value
  const wakeFreq = String(answers['q1.3'] ?? '');
  const poorWake = wakeFreq === 'disruption_often' || wakeFreq === 'disruption_very_often';

  // ── Nutrition signals ──────────────────────────────────────────────────────
  // q2.1 dietary restrictions multi_select
  const dietary: string[] = Array.isArray(answers['q2.1']) ? answers['q2.1'] : [];
  const isPlantBased = dietary.some((v) => ['diet_vegetarian', 'diet_vegan'].includes(v));

  // q2.2 iron deficiency history
  const ironAnemia = answers['q2.2'] === 'iron_yes';

  // q2.5 digestive issues
  const digestiveIssues = answers['q2.5'] === 'gut_yes';

  // ── Hormonal signals ───────────────────────────────────────────────────────
  // q3.4 thyroid diagnosis
  const thyroidDx = String(answers['q3.4'] ?? 'thyroid_none');
  const hasThyroid =
    answers['q3.4'] !== undefined &&
    thyroidDx !== 'thyroid_none' &&
    thyroidDx !== 'thyroid_unsure';

  // q3.6 recent major stress
  const recentStress = answers['q3.6'] === 'stress_yes';

  // ── Activity signals ───────────────────────────────────────────────────────
  // q4.3 post-exertional malaise
  const postExertional = answers['q4.3'] === 'pem_yes';

  // q4.5 recent infection
  const recentInfection =
    answers['q4.5'] === 'infection_yes' || answers['q4.5'] === 'infection_currently';

  // ── PHQ-9 mental health signals ────────────────────────────────────────────
  // q5.1–q5.4: 'not_at_all'=0, 'few_days'=1, 'several_days'=2, 'nearly_every_day'=3
  const PHQ_IDS = ['q5.1', 'q5.2', 'q5.3', 'q5.4'];
  const phqItems = PHQ_IDS.map((id) => {
    const v = answers[id];
    if (v === 'nearly_every_day') return 3;
    if (v === 'several_days') return 2;
    if (v === 'few_days') return 1;
    return 0;
  });
  const phqScore = phqItems.reduce((a: number, b) => a + b, 0);

  // Proxy for anxiety/low mood from q5.1 (anhedonia) + q5.2 (depressed mood)
  const highAnxiety =
    answers['q5.1'] === 'several_days' || answers['q5.1'] === 'nearly_every_day' ||
    answers['q5.2'] === 'several_days' || answers['q5.2'] === 'nearly_every_day';

  // ── Score each diagnostic pathway ─────────────────────────────────────────
  const scores: Record<string, number> = {
    iron: 3,
    thyroid: 2,
    sleep: 2,
    vitamins: 3,
    stress: 2,
    postviral: 0,
  };

  // Iron / Ferritin
  if (hasRLS) scores.iron += 3;
  if (ironAnemia) scores.iron += 4;
  if (isPlantBased) scores.iron += 2;
  if (sleepQuality < 5) scores.iron += 1;

  // Thyroid
  if (hasThyroid) scores.thyroid += 5;
  if (sleepQuality < 5) scores.thyroid += 1;

  // Sleep architecture
  if (sleepQuality < 5) scores.sleep += 4;
  if (hasRLS) scores.sleep += 2;
  if (poorWake) scores.sleep += 2;

  // Vitamins / B12
  if (isPlantBased) scores.vitamins += 3;
  if (digestiveIssues) scores.vitamins += 2;

  // Stress / HPA axis
  if (recentStress) scores.stress += 3;
  if (highAnxiety) scores.stress += 2;
  if (phqScore > 6) scores.stress += 2;

  // Post-viral / Long COVID / ME·CFS
  if (recentInfection) scores.postviral += 5;
  if (postExertional) scores.postviral += 4;

  // ── Pick top 3 diagnoses by score ─────────────────────────────────────────
  const ranked = Object.entries(scores)
    .sort(([, a], [, b]) => b - a)
    .filter(([, s]) => s >= 2);

  const topIds = ranked.slice(0, 3).map(([id]) => id);
  const pool = buildDiagnosisPool(scores);
  const diagnoses = topIds.map((id) => pool[id]).filter(Boolean);

  // ── Energy spectrum positions ──────────────────────────────────────────────
  const strongCount = diagnoses.filter((d) => d.signal === 'strong').length;
  const rawEnergy =
    55 - strongCount * 8 - Math.max(0, (5 - sleepQuality) * 3) - Math.min(10, phqScore * 1.5);
  const currentPct = Math.round(Math.min(42, Math.max(8, rawEnergy)));
  const projectedPct = Math.round(Math.min(88, currentPct + 38 + strongCount * 3));

  // ── Doctor priority list ───────────────────────────────────────────────────
  const doctors: Doctor[] = [
    {
      specialty: 'GP / Primary Care',
      icon: '🩺',
      badge: 'Start here',
      reason:
        'Bring your HalfFull report and request the specific tests listed above. Your GP can order the iron panel, thyroid labs, vitamin levels, and referrals — all from one appointment.',
    },
  ];

  if (hasThyroid || scores.thyroid >= 7) {
    doctors.push({
      specialty: 'Endocrinologist',
      icon: '🦋',
      badge: 'After initial labs',
      reason:
        'If thyroid markers are borderline or symptoms persist despite normal TSH, an endocrinologist can interpret Free T3/T4 in full context and discuss treatment thresholds.',
    });
  }

  if (scores.sleep >= 6) {
    doctors.push({
      specialty: 'Sleep Specialist',
      icon: '😴',
      badge: 'If GP flags sleep apnea',
      reason:
        'A sleep study can diagnose apnea, periodic limb movement disorder, and REM disruption — patterns that never show up in standard bloodwork.',
    });
  }

  if (scores.postviral >= 5) {
    doctors.push({
      specialty: 'Long COVID / ME·CFS Clinic',
      icon: '🦠',
      badge: 'Specialist referral',
      reason:
        'Post-exertional patterns require a specialist familiar with pacing protocols and post-viral syndromes — a GP alone is unlikely to have the tools to manage this.',
    });
  }

  if (scores.stress >= 6 || phqScore > 8) {
    doctors.push({
      specialty: 'Functional Medicine or Psychiatry',
      icon: '🧠',
      badge: 'If standard results normal',
      reason:
        "If all standard labs return 'normal' but symptoms persist, a functional medicine practitioner can assess adrenal patterns and gut function. Psychiatric support is warranted if PHQ scores remain elevated.",
    });
  }

  const summaryLine =
    diagnoses.length > 0
      ? `${diagnoses.length} areas worth investigating — all with established treatment paths.`
      : 'Your pattern suggests subtle imbalances that routine tests often miss.';

  return { currentPct, projectedPct, summaryLine, diagnoses, doctors };
}

export interface LocalDeepResultLike {
  personalizedSummary: string;
  insights: Array<{
    diagnosisId: string;
    personalNote: string;
  }>;
  nextSteps: string;
  doctorKitSummary?: string;
  doctorKitQuestions?: string[];
  doctorKitArguments?: string[];
  coachingTips?: Array<{
    category: string;
    tip: string;
    timeframe: string;
  }>;
}

function buildDoctorKitQuestions(diagnoses: Diagnosis[]): string[] {
  const defaults = diagnoses.slice(0, 2).map((d) => {
    const leadTest = d.tests[0]?.name;
    return leadTest
      ? `Could ${d.title.toLowerCase()} fit this pattern, and should we check ${leadTest}?`
      : `Could ${d.title.toLowerCase()} fit this pattern?`;
  });

  return [
    defaults[0] ?? 'Which first-line tests make the most sense for this fatigue pattern?',
    defaults[1] ?? 'If the basic tests are normal, what should we investigate next?',
  ];
}

function buildDoctorKitArguments(diagnoses: Diagnosis[]): string[] {
  const argumentsFromTests = diagnoses
    .flatMap((d) =>
      d.tests
        .filter((t) => t.mustRequest)
        .map((t) => `Because ${d.title.toLowerCase()} is being considered, I would like to discuss ${t.name}${t.note ? ` because ${t.note.toLowerCase()}` : '.'}`)
    )
    .slice(0, 2);

  return [
    argumentsFromTests[0] ?? 'My fatigue pattern feels persistent enough that I would like to discuss tests beyond a routine basic panel.',
    argumentsFromTests[1] ?? 'If common causes are not obvious, I would like help ruling out the most plausible hidden drivers step by step.',
  ];
}

function buildCoachingTips(diagnoses: Diagnosis[]): NonNullable<LocalDeepResultLike['coachingTips']> {
  const top = diagnoses[0]?.title ?? 'energy recovery';
  return [
    {
      category: 'Pacing',
      tip: `Keep activity steady for the next 1-2 weeks instead of pushing through crashes while you investigate ${top.toLowerCase()}.`,
      timeframe: 'This week',
    },
    {
      category: 'Sleep',
      tip: 'Protect a consistent sleep and wake window so your symptom pattern is easier to interpret and discuss with your clinician.',
      timeframe: 'Next 7 days',
    },
    {
      category: 'Tracking',
      tip: 'Write down your lowest-energy times, major triggers, and any related symptoms so you can bring a cleaner story into the appointment.',
      timeframe: 'Until your visit',
    },
  ];
}

function buildLocalInsights(
  diagnoses: Diagnosis[],
  tone: 'mock' | 'offline'
): LocalDeepResultLike['insights'] {
  return diagnoses.slice(0, 3).map((d, index) => ({
    diagnosisId: d.id,
    personalNote:
      tone === 'mock'
        ? `Demo insight ${index + 1}: this pattern overlaps with ${d.title.toLowerCase()}, so HalfFull would normally tailor follow-up guidance around the symptoms already reported.`
        : `Local fallback note: your answers contain signals that make ${d.title.toLowerCase()} worth discussing, especially alongside the tests already suggested in this report.`,
  }));
}

export function buildMockDeepResult(answers: Record<string, unknown>): LocalDeepResultLike {
  const { diagnoses, summaryLine } = computeResults(answers);
  const titles = diagnoses.slice(0, 2).map((d) => d.title).join(' and ');
  const leadingLabel = titles || 'a few subtle energy drivers';

  return {
    personalizedSummary:
      `Demo mode: this is a stable mock report rather than a live MedGemma response. Based on your assessment, HalfFull would normally focus on ${leadingLabel.toLowerCase()}. ${summaryLine} This report is educational only and not medical advice.`,
    insights: buildLocalInsights(diagnoses, 'mock'),
    nextSteps:
      `Demo next steps: bring this report to your GP, review the flagged areas, and start with the first recommended tests for ${leadingLabel.toLowerCase()}. If those are unrevealing, use the doctor-kit prompts below to discuss the next layer of testing.`,
    doctorKitSummary:
      `I have been dealing with ongoing low energy and this assessment highlighted ${leadingLabel.toLowerCase()} as worth checking. I would like to use this visit to review the most relevant tests instead of stopping at a generic fatigue workup.`,
    doctorKitQuestions: buildDoctorKitQuestions(diagnoses),
    doctorKitArguments: buildDoctorKitArguments(diagnoses),
    coachingTips: buildCoachingTips(diagnoses),
  };
}

export function buildOfflineDeepResult(answers: Record<string, unknown>): LocalDeepResultLike {
  const { diagnoses, summaryLine } = computeResults(answers);
  const titles = diagnoses.slice(0, 2).map((d) => d.title).join(' and ');
  const leadingLabel = titles || 'subtle but actionable patterns';

  return {
    personalizedSummary:
      `Offline fallback: this report was generated locally because live AI analysis was unavailable. Your answers suggest ${leadingLabel.toLowerCase()} may be worth discussing with your GP. ${summaryLine} This report is educational only and not medical advice.`,
    insights: buildLocalInsights(diagnoses, 'offline'),
    nextSteps:
      'Use the structured report to guide a focused GP conversation and ask about the top recommended tests first. If symptoms continue despite normal routine bloodwork, discuss the more specific tests attached to the highest-ranked areas.',
    doctorKitSummary:
      `I have persistent low energy and this local assessment suggests ${leadingLabel.toLowerCase()} could be relevant. I would like help reviewing the most appropriate targeted tests and what to investigate next if routine results look normal.`,
    doctorKitQuestions: buildDoctorKitQuestions(diagnoses),
    doctorKitArguments: buildDoctorKitArguments(diagnoses),
    coachingTips: buildCoachingTips(diagnoses),
  };
}
