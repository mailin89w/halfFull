/**
 * Shared answer-formatting utilities.
 *
 * formatAnswers    – legacy formatter for the old quiz (q1.1, q2.1, … keys).
 * formatAnswersV2  – formatter for the NHANES v2 quiz (NHANES field_id keys).
 *
 * Both produce a human-readable text block suitable for MedGemma prompts.
 */

import type { LabUploadAnswer } from './types';

const LAB_UPLOAD_FIELDS: Record<string, string> = {
  total_cholesterol_mg_dl: 'Total cholesterol',
  hdl_cholesterol_mg_dl: 'HDL cholesterol',
  ldl_cholesterol_mg_dl: 'LDL cholesterol',
  triglycerides_mg_dl: 'Triglycerides',
  fasting_glucose_mg_dl: 'Fasting glucose',
  glucose_mg_dl: 'Glucose',
  uacr_mg_g: 'UACR',
  wbc_1000_cells_ul: 'WBC',
};

// ── v2 formatter (NHANES field_id keys) ─────────────────────────────────────

const HEALTH_MAP: Record<number, string> = {
  1: 'Excellent', 2: 'Very good', 3: 'Good', 4: 'Fair', 5: 'Poor',
};
const SNORE_MAP: Record<number, string> = {
  0: 'Never', 1: 'Rarely (1–2 nights/week)', 2: 'Sometimes (3–4 nights/week)',
  3: 'Often (5+ nights/week)', 4: 'Almost every night',
};
const TIRED_MAP: Record<number, string> = {
  0: 'Not at all', 1: 'Several days',
  2: 'More than half the days', 3: 'Nearly every day',
};
const SCHED_MAP: Record<number, string> = {
  1: 'Standard 9–5', 2: 'Early morning shift', 3: 'Evening shift',
  4: 'Night shift', 5: 'Rotating shifts', 6: 'Split shift',
  7: 'Irregular hours', 8: 'Not currently working',
};
const NOCT_MAP: Record<number, string> = {
  0: '0 times', 1: '1 time', 2: '2 times', 3: '3 times', 4: '4 times', 5: '5+ times',
};
const LEAK_MAP: Record<number, string> = {
  0: 'Never', 1: '<Once/month', 2: 'A few times/month',
  3: 'A few times/week', 4: 'Daily or almost daily',
};
const SMOKE_MAP: Record<number, string> = { 1: 'Every day', 2: 'Some days', 3: 'Not at all' };
const PREG_MAP: Record<number, string> = { 1: 'Yes', 2: 'No', 3: 'Not sure' };

function _yes(v: unknown): boolean { return String(v) === '1'; }
function _no(v: unknown): boolean { return String(v) === '2'; }

export function formatAnswersV2(answers: Record<string, unknown>): string {
  const lines: string[] = [];
  const a = answers;

  // --- Flatten compound answers ---
  // height_weight dual_numeric → height_cm, weight_kg, bmi
  const hw = a['height_weight'] as Record<string, string> | undefined;
  if (hw && typeof hw === 'object') {
    if (hw['height_cm']) (a as Record<string, unknown>)['height_cm'] = hw['height_cm'];
    if (hw['weight_kg']) (a as Record<string, unknown>)['weight_kg'] = hw['weight_kg'];
    const h = parseFloat(hw['height_cm'] ?? '');
    const w = parseFloat(hw['weight_kg'] ?? '');
    if (!isNaN(h) && !isNaN(w) && h > 0) {
      (a as Record<string, unknown>)['bmi'] = (w / (h / 100) ** 2).toFixed(1);
    }
  }
  // sleep_hours dual_numeric → individual NHANES fields
  const sh = a['sleep_hours'] as Record<string, string> | undefined;
  if (sh && typeof sh === 'object') {
    for (const [k, v] of Object.entries(sh)) {
      if (v) (a as Record<string, unknown>)[k] = v;
    }
  }
  // free_time_activity dual_numeric → individual NHANES fields
  const fta = a['free_time_activity'] as Record<string, string> | undefined;
  if (fta && typeof fta === 'object') {
    for (const [k, v] of Object.entries(fta)) {
      if (v) (a as Record<string, unknown>)[k] = v;
    }
  }
  // symptoms_physical dual_numeric → individual NHANES fields
  const sp = a['symptoms_physical'] as Record<string, string> | undefined;
  if (sp && typeof sp === 'object') {
    for (const [k, v] of Object.entries(sp)) {
      if (v) (a as Record<string, unknown>)[k] = v;
    }
  }
  // conditions_diagnosed multi-select → individual binary fields
  const condsDx = a['conditions_diagnosed'];
  if (Array.isArray(condsDx)) {
    const selected = new Set(condsDx as string[]);
    const allCondFields = [
      'bpq020___ever_told_you_had_high_blood_pressure',
      'bpq080___doctor_told_you___high_cholesterol_level',
      'diq010___doctor_told_you_have_diabetes',
      'mcq010___ever_been_told_you_have_asthma',
      'mcq160a___ever_told_you_had_arthritis',
      'kiq022___ever_told_you_had_weak/failing_kidneys?',
      'mcq160l___ever_told_you_had_any_liver_condition',
      'heq030___ever_told_you_have_hepatitis_c?',
      'mcq160b___ever_told_you_had_congestive_heart_failure',
      'mcq160e___ever_told_you_had_heart_attack',
      'mcq160f___ever_told_you_had_stroke',
      'mcq053___taking_treatment_for_anemia/past_3_mos',
      'mcq092___ever_receive_blood_transfusion',
      'slq060___ever_told_by_doctor_have_sleep_disorder',
      'mcq080___doctor_ever_said_you_were_overweight',
    ];
    for (const f of allCondFields) {
      (a as Record<string, unknown>)[f] = selected.has(f) ? '1' : '2';
    }
  }

  // Demographics
  if (a['age_years']) lines.push(`Age: ${a['age_years']} years`);
  const gender = Number(a['gender']);
  if (gender === 1) lines.push('Sex: Male');
  if (gender === 2) lines.push('Sex: Female');

  // General health
  const gh = Number(a['huq010___general_health_condition']);
  if (gh) lines.push(`Self-rated health: ${HEALTH_MAP[gh] ?? gh}`);
  if (a['weight_kg']) lines.push(`Weight: ${a['weight_kg']} kg`);
  if (a['bmi']) lines.push(`BMI: ${a['bmi']}`);
  if (_yes(a['huq071___overnight_hospital_patient_in_last_year'])) lines.push('Hospitalised overnight in past year: Yes');
  if (a['med_count']) lines.push(`Prescription medications: ${a['med_count']}`);

  // Sleep
  if (a['sld012___sleep_hours___weekdays_or_workdays'])
    lines.push(`Sleep (weeknights): ${a['sld012___sleep_hours___weekdays_or_workdays']} hrs`);
  if (a['sld013___sleep_hours___weekends'])
    lines.push(`Sleep (weekends): ${a['sld013___sleep_hours___weekends']} hrs`);
  const snore = Number(a['slq030___how_often_do_you_snore?']);
  if (a['slq030___how_often_do_you_snore?'] !== undefined)
    lines.push(`Snoring: ${SNORE_MAP[snore] ?? snore}`);
  if (_yes(a['slq050___ever_told_doctor_had_trouble_sleeping?'])) lines.push('Doctor-diagnosed sleep disorder: Yes');
  const tired = Number(a['dpq040___feeling_tired_or_having_little_energy']);
  if (a['dpq040___feeling_tired_or_having_little_energy'] !== undefined)
    lines.push(`Tiredness (past 2 weeks): ${TIRED_MAP[tired] ?? tired}`);

  // Activity & work
  const sched = Number(a['ocq670___overall_work_schedule_past_3_months']);
  if (sched) lines.push(`Work schedule: ${SCHED_MAP[sched] ?? sched}`);
  if (_yes(a['paq620___moderate_work_activity'])) lines.push('Moderate physical work: Yes');
  if (_yes(a['paq665___moderate_recreational_activities'])) lines.push('Moderate recreational activity: Yes');
  if (_yes(a['paq650___vigorous_recreational_activities'])) lines.push('Vigorous recreational activity: Yes');
  if (a['pad680___minutes_sedentary_activity']) lines.push(`Sedentary time: ${a['pad680___minutes_sedentary_activity']} min/day`);

  // Alcohol — derive ever-drank from downstream answers
  const avgDrinks = Number(a['alq130___avg_#_alcoholic_drinks/day___past_12_mos'] ?? -1);
  const heavyDrinking = _yes(a['alq151___ever_have_4/5_or_more_drinks_every_day?']);
  const everDrank = avgDrinks > 0 || heavyDrinking;
  if (avgDrinks === 0 && !heavyDrinking) {
    lines.push('Alcohol: Never / does not drink');
  } else if (everDrank) {
    if (avgDrinks > 0) lines.push(`Avg drinks/occasion: ${avgDrinks}`);
    if (heavyDrinking) lines.push('Heavy drinking pattern (4/5+ drinks daily): Yes');
  }

  // Smoking
  const smoke = Number(a['smq040___do_you_now_smoke_cigarettes?']);
  if (smoke) lines.push(`Current smoking: ${SMOKE_MAP[smoke] ?? smoke}`);
  if (smoke !== 3 && a['smd650___avg_#_cigarettes/day_during_past_30_days'])
    lines.push(`Cigarettes/day: ${a['smd650___avg_#_cigarettes/day_during_past_30_days']}`);

  // Medical history
  if (_yes(a['bpq020___ever_told_you_had_high_blood_pressure'])) {
    lines.push('High blood pressure (diagnosed): Yes');
    if (_yes(a['bpq040a___taking_prescription_for_hypertension'])) lines.push('On BP medication: Yes');
  }
  if (_yes(a['bpq080___doctor_told_you___high_cholesterol_level'])) lines.push('High cholesterol (diagnosed): Yes');

  const diab = Number(a['diq010___doctor_told_you_have_diabetes']);
  if (diab === 1) {
    lines.push('Diabetes: Yes');
    if (_yes(a['diq050___taking_insulin_now'])) lines.push('Taking insulin: Yes');
    if (_yes(a['diq070___take_diabetic_pills_to_lower_blood_sugar'])) lines.push('Taking diabetes pills: Yes');
  } else if (diab === 3) {
    lines.push('Diabetes: Borderline / pre-diabetes');
  }
  if (_yes(a['whq070___tried_to_lose_weight_in_past_year'])) lines.push('Tried to lose weight (past year): Yes');
  if (_yes(a['mcq300c___close_relative_had_diabetes'])) lines.push('Family history of diabetes: Yes');

  // Conditions
  const conditionMap: [string, string][] = [
    ['mcq053___taking_treatment_for_anemia/past_3_mos', 'Receiving anaemia treatment'],
    ['mcq092___ever_receive_blood_transfusion', 'Blood transfusion history'],
    ['mcq160a___ever_told_you_had_arthritis', 'Arthritis (diagnosed)'],
    ['mcq160l___ever_told_you_had_any_liver_condition', 'Liver condition (diagnosed)'],
    ['heq030___ever_told_you_have_hepatitis_c?', 'Hepatitis C'],
    ['mcq160b___ever_told_you_had_congestive_heart_failure', 'Heart failure (diagnosed)'],
    ['mcq160e___ever_told_you_had_heart_attack', 'Heart attack history'],
    ['mcq160f___ever_told_you_had_stroke', 'Stroke history'],
    ['kiq022___ever_told_you_had_weak/failing_kidneys?', 'Kidney disease (diagnosed)'],
    ['mcq010___ever_been_told_you_have_asthma', 'Asthma (diagnosed)'],
    ['slq060___ever_told_by_doctor_have_sleep_disorder', 'Sleep disorder (diagnosed)'],
    ['mcq080___doctor_ever_said_you_were_overweight', 'Overweight (told by doctor)'],
  ];
  for (const [key, label] of conditionMap) {
    if (_yes(a[key])) lines.push(`${label}: Yes`);
  }

  // Symptoms
  if (_yes(a['kiq026___ever_had_kidney_stones?'])) lines.push('Kidney stones history: Yes');
  const noct = Number(a['kiq480___how_many_times_urinate_in_night?']);
  if (a['kiq480___how_many_times_urinate_in_night?'] !== undefined)
    lines.push(`Night-time urination: ${NOCT_MAP[noct] ?? noct}`);
  const leak = Number(a['kiq005___how_often_have_urinary_leakage?']);
  if (a['kiq005___how_often_have_urinary_leakage?'] !== undefined && leak > 0)
    lines.push(`Urinary leakage: ${LEAK_MAP[leak] ?? leak}`);
  if (_yes(a['kiq044___urinated_before_reaching_the_toilet?'])) lines.push('Urgency incontinence: Yes');
  if (_yes(a['cdq010___shortness_of_breath_on_stairs/inclines'])) lines.push('Short of breath on stairs/hills: Yes');
  if (_yes(a['mcq520___abdominal_pain_during_past_12_months?'])) lines.push('Recurring abdominal pain (past year): Yes');

  // Women's health
  if (gender === 2) {
    const preg = Number(a['pregnancy_status']);
    if (preg) lines.push(`Currently pregnant: ${PREG_MAP[preg] ?? preg}`);
    if (_yes(a['rhq031___had_regular_periods_in_past_12_months'])) lines.push('Regular periods: Yes');
    else if (_no(a['rhq031___had_regular_periods_in_past_12_months'])) {
      lines.push('Regular periods: No');
      if (a['rhq060___age_at_last_menstrual_period'])
        lines.push(`Age at last period: ${a['rhq060___age_at_last_menstrual_period']}`);
    }
    if (_yes(a['rhq540___ever_use_female_hormones?'])) lines.push('Used female hormones (HRT/pill): Yes');
  }

  // Lab values
  const labFields: [string, string, string][] = [
    ['total_cholesterol_mg_dl', 'Total cholesterol', 'mg/dL'],
    ['hdl_cholesterol_mg_dl', 'HDL cholesterol', 'mg/dL'],
    ['ldl_cholesterol_mg_dl', 'LDL cholesterol', 'mg/dL'],
    ['triglycerides_mg_dl', 'Triglycerides', 'mg/dL'],
    ['fasting_glucose_mg_dl', 'Fasting glucose', 'mg/dL'],
    ['glucose_mg_dl', 'Glucose', 'mg/dL'],
    ['uacr_mg_g', 'UACR', 'mg/g'],
    ['wbc_1000_cells_ul', 'WBC', '×10³/µL'],
  ];
  const labLines: string[] = [];
  for (const [key, label, unit] of labFields) {
    if (a[key]) labLines.push(`${label}: ${a[key]} ${unit}`);
  }
  if (labLines.length > 0) lines.push(`Lab results: ${labLines.join(' | ')}`);

  // Lab file upload (structured values + extracted text)
  const labUpload = a['lab_upload'] as LabUploadAnswer | undefined;
  if (labUpload?.status === 'done') {
    if (labUpload.structuredValues && Object.keys(labUpload.structuredValues).length > 0) {
      const sv = labUpload.structuredValues;
      const uploadedLabLines = Object.entries(sv)
        .filter(([k]) => LAB_UPLOAD_FIELDS[k])
        .map(([k, v]) => `${LAB_UPLOAD_FIELDS[k]}: ${v}`);
      if (uploadedLabLines.length > 0) lines.push(`Uploaded lab values: ${uploadedLabLines.join(' | ')}`);
    } else if (labUpload.extractedText) {
      lines.push(`Uploaded lab results:\n${labUpload.extractedText.slice(0, 1500)}`);
    }
  }

  // Clarifying answers (from /clarify page)
  const clarifyAnswers = Object.entries(answers)
    .filter(([k, v]) => k.startsWith('clarify_') && typeof v === 'string' && (v as string).trim())
    .map(([, v]) => String(v).trim());
  if (clarifyAnswers.length > 0)
    lines.push(`Follow-up answers: ${clarifyAnswers.join(' | ')}`);

  return lines.length > 0 ? lines.join('\n') : 'No specific information provided.';
}

export function formatAnswers(answers: Record<string, unknown>): string {
  const lines: string[] = [];

  // ── Lab results ──────────────────────────────────────────────────────────
  const labAnswer = answers['q0.1'] as LabUploadAnswer | undefined;
  if (labAnswer?.status === 'done' && labAnswer.extractedText) {
    lines.push(`Uploaded lab results:\n${labAnswer.extractedText}`);
  }

  // ── Sleep ────────────────────────────────────────────────────────────────
  if (answers['q1.1']) lines.push(`Sleep duration: ${answers['q1.1']} hours per night`);
  if (answers['q1.2']) lines.push(`Sleep quality: ${answers['q1.2']}/10`);

  const wakeMap: Record<string, string> = {
    disruption_never: 'never',
    disruption_sometimes: '1–2 times per week',
    disruption_often: '3–4 times per week',
    disruption_very_often: '5+ times per week',
  };
  const wakeFreq = String(answers['q1.3'] ?? '');
  if (wakeMap[wakeFreq]) lines.push(`Night wakings: ${wakeMap[wakeFreq]}`);

  const sleepIssues = Array.isArray(answers['q1.4']) ? answers['q1.4'] : [];
  const issueMap: Record<string, string> = {
    issue_restless_legs: 'restless legs syndrome',
    issue_unrefreshed: 'unrefreshed upon waking',
    issue_nightmare: 'nightmares',
    issue_apnea: 'suspected sleep apnea',
  };
  const mappedIssues = sleepIssues
    .filter((i: string) => i !== 'issue_none')
    .map((i: string) => issueMap[i] ?? i);
  if (mappedIssues.length > 0) lines.push(`Sleep issues: ${mappedIssues.join(', ')}`);

  // ── Nutrition ────────────────────────────────────────────────────────────
  const dietary = Array.isArray(answers['q2.1']) ? answers['q2.1'] : [];
  const dietMap: Record<string, string> = {
    diet_vegetarian: 'vegetarian',
    diet_vegan: 'vegan',
    diet_gluten_free: 'gluten-free',
    diet_dairy_free: 'dairy-free',
  };
  const mappedDiet = dietary
    .filter((d: string) => d !== 'diet_no_restrictions')
    .map((d: string) => dietMap[d] ?? d);
  if (mappedDiet.length > 0) lines.push(`Dietary pattern: ${mappedDiet.join(', ')}`);

  if (answers['q2.2'] === 'iron_yes') lines.push('History of iron deficiency anaemia: yes');
  if (answers['q2.5'] === 'gut_yes') lines.push('Digestive/gut issues: yes');

  // ── Hormonal ─────────────────────────────────────────────────────────────
  const thyroid = String(answers['q3.4'] ?? '');
  if (thyroid && thyroid !== 'thyroid_none' && thyroid !== 'thyroid_unsure') {
    lines.push(`Thyroid history: ${thyroid}`);
  }
  if (answers['q3.6'] === 'stress_yes') lines.push('Recent major life stressor: yes');

  // ── Activity ─────────────────────────────────────────────────────────────
  const activityMap: Record<string, string> = {
    activity_sedentary: 'sedentary (desk-bound, little movement)',
    activity_light: 'lightly active',
    activity_moderate: 'moderately active',
    activity_active: 'active',
    activity_very_active: 'very active',
  };
  const activity = String(answers['q4.1'] ?? '');
  if (activityMap[activity]) lines.push(`Activity level: ${activityMap[activity]}`);
  if (answers['q4.3'] === 'pem_yes') {
    lines.push('Post-exertional malaise: fatigue noticeably worsens after physical or mental effort');
  }

  const infection = String(answers['q4.5'] ?? '');
  if (infection === 'infection_yes') lines.push('Recent viral illness in past 6 months: yes');
  if (infection === 'infection_currently') lines.push('Currently experiencing a viral illness: yes');

  // ── Mental health (PHQ-9 proxy) ──────────────────────────────────────────
  const phqMap: Record<string, string> = {
    not_at_all: 'not at all',
    few_days: 'a few days',
    several_days: 'several days',
    nearly_every_day: 'nearly every day',
  };
  const q51 = String(answers['q5.1'] ?? '');
  if (q51 && q51 !== 'not_at_all') lines.push(`Loss of interest in activities: ${phqMap[q51] ?? q51}`);
  const q52 = String(answers['q5.2'] ?? '');
  if (q52 && q52 !== 'not_at_all') lines.push(`Low or depressed mood: ${phqMap[q52] ?? q52}`);
  const q54 = String(answers['q5.4'] ?? '');
  if (q54 && q54 !== 'not_at_all') lines.push(`Fatigue / low energy: ${phqMap[q54] ?? q54}`);

  // ── Additional symptoms (free text q6.0) ─────────────────────────────────
  const additionalSymptoms = String(answers['q6.0'] ?? '').trim();
  if (additionalSymptoms) lines.push(`Patient's additional symptoms (own words): ${additionalSymptoms}`);

  // ── Clarifying answers ───────────────────────────────────────────────────
  const clarificationAnswers = Object.entries(answers)
    .filter(([key, value]) => key.startsWith('clarify_') && typeof value === 'string' && value.trim())
    .map(([, value]) => String(value).trim());
  if (clarificationAnswers.length > 0) {
    lines.push(`Follow-up clarifications: ${clarificationAnswers.join(' | ')}`);
  }

  return lines.length > 0 ? lines.join('\n') : 'No specific symptoms reported.';
}
