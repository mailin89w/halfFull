import type { LabUploadAnswer } from '@/src/lib/types';

export type ConfidenceTier = 'low' | 'medium' | 'high';
export type UrgencyLevel = 'routine' | 'soon' | 'urgent';

export interface ConfidenceAssessment {
  score: number;
  tier: ConfidenceTier;
  summary: string;
  clusterAgreement: number;
}

export interface UrgencyAssessment {
  level: UrgencyLevel;
  reasons: string[];
  cta: string;
}

interface KnnSignal {
  lab: string;
  direction: string;
  neighbour_pct: number;
  lift: number | null;
  ref_lower: number | null;
  ref_upper: number | null;
  context: string | null;
}

interface BiomarkerSnapshot {
  ferritin?: number;
  hemoglobin?: number;
  tsh?: number;
  free_t4?: number;
  hba1c?: number;
  fasting_glucose_mg_dl?: number;
  glucose_mg_dl?: number;
  egfr?: number;
  creatinine?: number;
  alt?: number;
  ast?: number;
  bilirubin?: number;
  crp?: number;
  esr?: number;
  sodium?: number;
  potassium?: number;
  magnesium?: number;
  uacr_mg_g?: number;
  wbc_1000_cells_ul?: number;
  hbsag_positive?: boolean;
  hcv_positive?: boolean;
}

const CONDITION_LABELS: Record<string, string> = {
  anemia: 'anemia',
  iron_deficiency: 'iron deficiency',
  thyroid: 'thyroid dysfunction',
  kidney: 'kidney function',
  sleep_disorder: 'sleep disorder',
  liver: 'liver health',
  prediabetes: 'prediabetes',
  inflammation: 'inflammation',
  electrolytes: 'electrolyte balance',
  hepatitis: 'hepatitis markers',
  perimenopause: 'perimenopause',
  vitamin_b12_deficiency: 'vitamin B12 deficiency',
  vitamin_d_deficiency: 'vitamin D deficiency',
};

const CLUSTER_MARKER_MAP: Record<string, string[]> = {
  anemia: ['hemoglobin', 'ferritin', 'mcv', 'iron'],
  iron_deficiency: ['ferritin', 'iron', 'transferrin', 'hemoglobin'],
  thyroid: ['tsh', 'free t4', 'free t3', 'anti-tpo'],
  kidney: ['egfr', 'creatinine', 'uacr', 'bun'],
  sleep_disorder: ['ferritin', 'cortisol', 'vitamin d'],
  liver: ['alt', 'ast', 'ggt', 'bilirubin', 'albumin'],
  prediabetes: ['glucose', 'a1c', 'hba1c', 'insulin'],
  inflammation: ['crp', 'esr', 'wbc', 'ana'],
  electrolytes: ['sodium', 'potassium', 'magnesium', 'calcium', 'phosphorus'],
  hepatitis: ['alt', 'ast', 'bilirubin', 'hepatitis'],
  perimenopause: ['fsh', 'estradiol', 'amh'],
  vitamin_b12_deficiency: ['b12', 'vitamin b12', 'methylmalonic', 'homocysteine'],
  vitamin_d_deficiency: ['vitamin d', '25-oh', '25(oh)', '25 hydroxy'],
};

const URGENCY_RULES: Record<string, { urgent: string[]; soon: string[] }> = {
  anemia: {
    urgent: ['Hemoglobin is in a range that needs prompt medical review.'],
    soon: ['Low hemoglobin or ferritin makes anemia worth checking soon.'],
  },
  iron_deficiency: {
    urgent: ['Very low ferritin alongside fatigue can deteriorate quickly.'],
    soon: ['Low ferritin supports asking for iron studies soon.'],
  },
  thyroid: {
    urgent: ['Marked thyroid abnormalities can worsen quickly and need prompt review.'],
    soon: ['TSH / free T4 pattern supports booking a doctor visit soon.'],
  },
  kidney: {
    urgent: ['Kidney markers are in a range that should be reviewed urgently.'],
    soon: ['Reduced filtration markers support seeing a doctor soon.'],
  },
  sleep_disorder: {
    urgent: ['Severe sleep-related fatigue plus strong signal warrants prompt follow-up.'],
    soon: ['Persistent unrefreshing sleep is worth discussing soon.'],
  },
  liver: {
    urgent: ['Liver markers are elevated enough to justify urgent medical review.'],
    soon: ['Abnormal liver markers make a near-term GP visit appropriate.'],
  },
  prediabetes: {
    urgent: ['Glucose markers are high enough that a doctor should review them urgently.'],
    soon: ['Glucose regulation markers support a follow-up soon.'],
  },
  inflammation: {
    urgent: ['Inflammation markers are high enough to warrant prompt review.'],
    soon: ['Persistent inflammation markers support a near-term workup.'],
  },
  electrolytes: {
    urgent: ['Electrolyte markers can become risky quickly and should be reviewed urgently.'],
    soon: ['Electrolyte imbalance is worth checking soon.'],
  },
  hepatitis: {
    urgent: ['Positive hepatitis markers or liver strain warrant urgent review.'],
    soon: ['Hepatitis-related signal should be followed up soon.'],
  },
  perimenopause: {
    urgent: ['Heavy cycle disruption plus severe fatigue warrants prompt review.'],
    soon: ['Hormonal-transition pattern supports booking a visit soon.'],
  },
  vitamin_b12_deficiency: {
    urgent: ['Neurologic symptoms together with a strong B12 signal should be reviewed promptly.'],
    soon: ['A vitamin B12 deficiency pattern is worth checking with a clinician soon.'],
  },
  vitamin_d_deficiency: {
    urgent: ['Severe weakness, falls, or bone pain with a strong vitamin D signal should be reviewed promptly.'],
    soon: ['A vitamin D deficiency pattern supports follow-up soon.'],
  },
};

function normalizeConditionId(conditionId: string): string {
  if (conditionId === 'hepatitis_bc') return 'hepatitis';
  if (conditionId === 'electrolyte_imbalance') return 'electrolytes';
  return conditionId;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function getLabUploadValue(answers: Record<string, unknown>): LabUploadAnswer | null {
  const value = answers.lab_upload;
  if (!value || typeof value !== 'object') return null;
  return value as LabUploadAnswer;
}

function parseNumberFromText(patterns: RegExp[], text: string): number | undefined {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      const value = Number(match[1]);
      if (Number.isFinite(value)) return value;
    }
  }
  return undefined;
}

export function extractBiomarkerSnapshot(answers: Record<string, unknown>): BiomarkerSnapshot {
  const labUpload = getLabUploadValue(answers);
  const structured = labUpload?.structuredValues ?? {};
  const text = labUpload?.extractedText ?? '';

  return {
    ferritin: parseNumberFromText([/ferritin[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    hemoglobin: parseNumberFromText([/(?:hemoglobin|hgb)[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    tsh: parseNumberFromText([/\btsh[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    free_t4: parseNumberFromText([/free\s*t4[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    hba1c: parseNumberFromText([/(?:hba1c|a1c)[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    fasting_glucose_mg_dl: structured.fasting_glucose_mg_dl,
    glucose_mg_dl: structured.glucose_mg_dl,
    egfr: parseNumberFromText([/\begfr[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    creatinine: parseNumberFromText([/creatinine[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    alt: parseNumberFromText([/\balt[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    ast: parseNumberFromText([/\bast[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    bilirubin: parseNumberFromText([/bilirubin[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    crp: parseNumberFromText([/\bcrp[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    esr: parseNumberFromText([/\besr[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    sodium: parseNumberFromText([/sodium[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    potassium: parseNumberFromText([/potassium[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    magnesium: parseNumberFromText([/magnesium[^\d]{0,24}(\d+(?:\.\d+)?)/i], text),
    uacr_mg_g: structured.uacr_mg_g,
    wbc_1000_cells_ul: structured.wbc_1000_cells_ul,
    hbsag_positive: /hbsag[^\n]*(positive|reactive)/i.test(text),
    hcv_positive: /(hcv|hepatitis c)[^\n]*(positive|reactive)/i.test(text),
  };
}

export function computeClusterAgreement(conditionId: string, labSignals: KnnSignal[] = []): number {
  const normalized = normalizeConditionId(conditionId);
  const markers = CLUSTER_MARKER_MAP[normalized] ?? [];
  if (markers.length === 0 || labSignals.length === 0) return 0;

  const matched = labSignals.filter((signal) =>
    markers.some((marker) => signal.lab.toLowerCase().includes(marker))
  );
  if (matched.length === 0) return 0;

  const strongest = Math.max(...matched.map((signal) => signal.neighbour_pct ?? 0));
  return clamp(strongest / 100, 0, 1);
}

export function computeConfidence(args: {
  conditionId: string;
  mlScore?: number;
  posteriorScore?: number;
  labSignals?: KnnSignal[];
}): ConfidenceAssessment {
  const { conditionId, mlScore = 0, posteriorScore, labSignals = [] } = args;
  const normalized = normalizeConditionId(conditionId);
  const posterior = posteriorScore ?? mlScore;
  const delta = Math.max(0, posterior - mlScore);
  const clusterAgreement = computeClusterAgreement(normalized, labSignals);

  const score = clamp(
    mlScore * 0.5 + posterior * 0.3 + clusterAgreement * 0.2 + Math.min(delta, 0.2),
    0,
    1
  );

  const tier: ConfidenceTier =
    score >= 0.72 ? 'high' : score >= 0.5 ? 'medium' : 'low';

  const clusterLabel =
    clusterAgreement >= 0.6
      ? 'strong cluster support'
      : clusterAgreement >= 0.3
        ? 'some cluster support'
        : 'limited cluster support';

  return {
    score,
    tier,
    clusterAgreement,
    summary: `${Math.round(posterior * 100)}% posterior with ${clusterLabel}.`,
  };
}

export function computeUrgency(args: {
  conditionId: string;
  posteriorScore?: number;
  biomarkers: BiomarkerSnapshot;
}): UrgencyAssessment {
  const conditionId = normalizeConditionId(args.conditionId);
  const posterior = args.posteriorScore ?? 0;
  const biomarkers = args.biomarkers;
  const rules = URGENCY_RULES[conditionId];
  const reasons: string[] = [];

  const urgentByProbability = posterior >= 0.82;
  const soonByProbability = posterior >= 0.58;

  let urgentFlag = false;
  let soonFlag = false;

  switch (conditionId) {
    case 'anemia':
      urgentFlag = (biomarkers.hemoglobin ?? Infinity) < 10;
      soonFlag = (biomarkers.hemoglobin ?? Infinity) < 12;
      break;
    case 'iron_deficiency':
      urgentFlag = (biomarkers.ferritin ?? Infinity) < 10;
      soonFlag = (biomarkers.ferritin ?? Infinity) < 30;
      break;
    case 'thyroid':
      urgentFlag = (biomarkers.tsh ?? 0) >= 10 || ((biomarkers.free_t4 ?? Infinity) < 0.7 && (biomarkers.tsh ?? 0) > 4.5);
      soonFlag = (biomarkers.tsh ?? 0) >= 4.5 || (biomarkers.free_t4 ?? Infinity) < 0.9;
      break;
    case 'kidney':
      urgentFlag = (biomarkers.egfr ?? Infinity) < 45 || (biomarkers.uacr_mg_g ?? 0) >= 300;
      soonFlag = (biomarkers.egfr ?? Infinity) < 60 || (biomarkers.uacr_mg_g ?? 0) >= 30 || (biomarkers.creatinine ?? 0) >= 1.5;
      break;
    case 'sleep_disorder':
      urgentFlag = false;
      soonFlag = posterior >= 0.68;
      break;
    case 'liver':
      urgentFlag = (biomarkers.alt ?? 0) >= 120 || (biomarkers.ast ?? 0) >= 120 || (biomarkers.bilirubin ?? 0) >= 2;
      soonFlag = (biomarkers.alt ?? 0) >= 60 || (biomarkers.ast ?? 0) >= 60 || (biomarkers.bilirubin ?? 0) >= 1.2;
      break;
    case 'prediabetes':
      urgentFlag = (biomarkers.hba1c ?? 0) >= 6.5 || (biomarkers.fasting_glucose_mg_dl ?? 0) >= 126;
      soonFlag = (biomarkers.hba1c ?? 0) >= 5.7 || (biomarkers.fasting_glucose_mg_dl ?? 0) >= 100 || (biomarkers.glucose_mg_dl ?? 0) >= 140;
      break;
    case 'inflammation':
      urgentFlag = (biomarkers.crp ?? 0) >= 10 || (biomarkers.esr ?? 0) >= 40 || (biomarkers.wbc_1000_cells_ul ?? 0) >= 14;
      soonFlag = (biomarkers.crp ?? 0) >= 5 || (biomarkers.esr ?? 0) >= 20 || (biomarkers.wbc_1000_cells_ul ?? 0) >= 11;
      break;
    case 'electrolytes':
      urgentFlag =
        (biomarkers.sodium ?? 140) < 130 ||
        (biomarkers.sodium ?? 140) > 150 ||
        (biomarkers.potassium ?? 4) < 3 ||
        (biomarkers.potassium ?? 4) > 5.8;
      soonFlag =
        (biomarkers.sodium ?? 140) < 135 ||
        (biomarkers.sodium ?? 140) > 145 ||
        (biomarkers.potassium ?? 4) < 3.5 ||
        (biomarkers.potassium ?? 4) > 5.1 ||
        (biomarkers.magnesium ?? 2) < 1.7;
      break;
    case 'hepatitis':
      urgentFlag = Boolean(biomarkers.hbsag_positive || biomarkers.hcv_positive) || (biomarkers.alt ?? 0) >= 120;
      soonFlag = Boolean(biomarkers.hbsag_positive || biomarkers.hcv_positive) || (biomarkers.alt ?? 0) >= 60 || (biomarkers.ast ?? 0) >= 60;
      break;
    case 'perimenopause':
      urgentFlag = false;
      soonFlag = posterior >= 0.62;
      break;
    default:
      break;
  }

  let level: UrgencyLevel = 'routine';
  if (urgentFlag || urgentByProbability) level = 'urgent';
  else if (soonFlag || soonByProbability) level = 'soon';

  if (level === 'urgent') {
    reasons.push(rules.urgent[0] ?? 'This pattern deserves urgent review.');
  } else if (level === 'soon') {
    reasons.push(rules.soon[0] ?? 'This pattern deserves near-term review.');
  } else {
    reasons.push(`Current evidence supports a routine follow-up for ${CONDITION_LABELS[conditionId] ?? conditionId}.`);
  }

  return {
    level,
    reasons,
    cta:
      level === 'urgent'
        ? 'Please arrange a prompt medical review.'
        : level === 'soon'
          ? 'Book a doctor visit in the near term.'
          : 'Bring this up at your next routine visit.',
  };
}
