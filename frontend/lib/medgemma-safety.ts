/**
 * medgemma-safety.ts
 * ------------------
 * Schema validation and hard safety rules for MedGemma deep-analyze output.
 *
 * Used exclusively by frontend/app/api/deep-analyze/route.ts.
 * Keep this file server-side only — no client imports.
 */

// ── Allowlist of valid diagnosisId values (mirrors the prompt allowlist) ───

export const DIAGNOSIS_ID_ALLOWLIST = new Set([
  'iron', 'thyroid', 'sleep', 'vitamins', 'stress', 'postviral',
  'anemia', 'iron_deficiency', 'kidney', 'sleep_disorder', 'liver',
  'prediabetes', 'inflammation', 'electrolytes', 'hepatitis', 'perimenopause',
]);

// ── V6: MedGemma grounding output types ───────────────────────────────────

export interface SupportedSuspicion {
  diagnosisId: string;
  confidence: 'probable' | 'possible' | 'worth_ruling_out';
  anchorEvidence: string;
  reasoning: string;
  keySymptoms: string[];
  recommendedTests: string[];
}

export interface DeclinedSuspicion {
  diagnosisId: string;
  reason: string;
}

export interface MedicationFlag {
  labOrSymptom: string;
  medication: string;
  note: string;
}

export interface RecommendedSpecialty {
  specialty: string;
  priority: string;
  clinicalReason: string;
  symptomsToRaise: string[];
  testsToRequest: string[];
  discussionPoints: string[];
}

export interface MedGemmaGroundingResult {
  supportedSuspicions: SupportedSuspicion[];
  declinedSuspicions: DeclinedSuspicion[];
  medicationFlags: MedicationFlag[];
  recommendedSpecialties: RecommendedSpecialty[];
}

export type GroundingValidationResult =
  | { ok: true;  data: MedGemmaGroundingResult }
  | { ok: false; reason: string };

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function asObjectArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object');
}

/**
 * Validates the V6 MedGemma grounding output (Call 1).
 */
export function validateMedGemmaGroundingSchema(
  parsed: Record<string, unknown> | null,
): GroundingValidationResult {
  if (!parsed) return { ok: false, reason: 'null input' };
  const err = (reason: string): GroundingValidationResult => ({ ok: false, reason });

  if (!Array.isArray(parsed.supportedSuspicions))
    return err('supportedSuspicions must be an array');

  const supportedSuspicions: SupportedSuspicion[] = [];
  for (const item of asObjectArray(parsed.supportedSuspicions).slice(0, 3)) {
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      continue;
    if (!['probable', 'possible', 'worth_ruling_out'].includes(item?.confidence as string))
      continue;
    if (typeof item?.anchorEvidence !== 'string' || !item.anchorEvidence.trim())
      continue;
    if (typeof item?.reasoning !== 'string' || !item.reasoning.trim())
      continue;
    supportedSuspicions.push({
      diagnosisId: item.diagnosisId,
      confidence: item.confidence as SupportedSuspicion['confidence'],
      anchorEvidence: item.anchorEvidence.trim(),
      reasoning: item.reasoning.trim(),
      keySymptoms: normalizeStringArray(item?.keySymptoms),
      recommendedTests: normalizeStringArray(item?.recommendedTests),
    });
  }

  const declinedSuspicions: DeclinedSuspicion[] = [];
  const declinedInput = asObjectArray(parsed.declinedSuspicions);
  for (let i = 0; i < declinedInput.length; i++) {
    const item = declinedInput[i];
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      continue;
    if (typeof item?.reason !== 'string' || !item.reason.trim())
      continue;
    declinedSuspicions.push({
      diagnosisId: item.diagnosisId,
      reason: item.reason.trim(),
    });
  }

  const medicationFlags: MedicationFlag[] = [];
  const medicationFlagsInput = asObjectArray(parsed.medicationFlags);
  for (let i = 0; i < medicationFlagsInput.length; i++) {
    const item = medicationFlagsInput[i];
    if (typeof item?.labOrSymptom !== 'string' || !item.labOrSymptom.trim())
      continue;
    if (typeof item?.medication !== 'string' || !item.medication.trim())
      continue;
    if (typeof item?.note !== 'string' || !item.note.trim())
      continue;
    medicationFlags.push({
      labOrSymptom: item.labOrSymptom.trim(),
      medication: item.medication.trim(),
      note: item.note.trim(),
    });
  }

  const recommendedSpecialties: RecommendedSpecialty[] = [];
  const specialtiesInput = asObjectArray(parsed.recommendedSpecialties).slice(0, 3);
  for (let i = 0; i < specialtiesInput.length; i++) {
    const item = specialtiesInput[i];
    if (typeof item?.specialty !== 'string' || !item.specialty.trim())
      continue;
    if (typeof item?.priority !== 'string' || !item.priority.trim())
      continue;
    if (typeof item?.clinicalReason !== 'string' || !item.clinicalReason.trim())
      continue;
    recommendedSpecialties.push({
      specialty: item.specialty.trim(),
      priority: item.priority.trim(),
      clinicalReason: item.clinicalReason.trim(),
      symptomsToRaise: normalizeStringArray(item?.symptomsToRaise),
      testsToRequest: normalizeStringArray(item?.testsToRequest),
      discussionPoints: normalizeStringArray(item?.discussionPoints),
    });
  }

  return {
    ok: true,
    data: {
      supportedSuspicions,
      declinedSuspicions,
      medicationFlags,
      recommendedSpecialties,
    },
  };
}

// ── Output schema types ────────────────────────────────────────────────────

export interface InsightItem {
  diagnosisId: string;
  personalNote: string;
  confidence?: 'probable' | 'possible' | 'worth_ruling_out';
}

export interface RecommendedDoctor {
  specialty: string;
  priority: string;
  reason: string;
  symptomsToDiscuss: string[];
  suggestedTests: string[];
}

export interface DoctorKit {
  specialty: string;
  openingSummary: string;
  concerningSymptoms: string[];
  recommendedTests: string[];
  discussionPoints: string[];
  // V6 additions
  bringToAppointment?: string[];
  whatToSay?: string;
}

export interface DeepAnalyzeResult {
  personalizedSummary: string;
  summaryPoints?: string[];
  insights: InsightItem[];
  declinedSuspicions?: DeclinedSuspicion[];
  recoveryOutlook?: string;
  nextSteps: string;
  doctorKitSummary?: string;
  doctorKitQuestions: string[];
  doctorKitArguments: string[];
  recommendedDoctors: RecommendedDoctor[];
  doctorKits: DoctorKit[];
  allClear?: boolean;
}

export type ValidationResult =
  | { ok: true;  data: DeepAnalyzeResult }
  | { ok: false; reason: string };

// ── Schema validation ──────────────────────────────────────────────────────

/**
 * Validates parsed MedGemma output against the required schema.
 *
 * Returns { ok: true, data } on success, or { ok: false, reason } on failure.
 * Caller should return HTTP 422 with { error: "schema_validation_failed", raw } on failure.
 */
export function validateDeepAnalyzeSchema(
  parsed: Record<string, unknown>,
): ValidationResult {
  const err = (reason: string): ValidationResult => ({ ok: false, reason });

  // personalizedSummary — non-empty string
  if (typeof parsed.personalizedSummary !== 'string' || !parsed.personalizedSummary.trim())
    return err('personalizedSummary must be a non-empty string');

  // summaryPoints — optional array, skip items that aren't strings
  const summaryPoints = Array.isArray(parsed.summaryPoints)
    ? normalizeStringArray(parsed.summaryPoints)
    : [];

  // insights — array, 0–4 items, each with valid diagnosisId + non-empty personalNote
  if (!Array.isArray(parsed.insights))
    return err('insights must be an array');
  const insights: InsightItem[] = [];
  for (const item of asObjectArray(parsed.insights).slice(0, 4)) {
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      continue; // skip hallucinated or empty diagnosisIds rather than failing the whole response
    if (typeof item?.personalNote !== 'string' || !item.personalNote.trim())
      continue;
    insights.push({
      diagnosisId: item.diagnosisId,
      personalNote: item.personalNote.trim(),
      ...(typeof item?.confidence === 'string'
        && ['probable', 'possible', 'worth_ruling_out'].includes(item.confidence)
        ? { confidence: item.confidence as InsightItem['confidence'] }
        : {}),
    });
  }

  // nextSteps — non-empty string
  if (typeof parsed.nextSteps !== 'string' || !parsed.nextSteps.trim())
    return err('nextSteps must be a non-empty string');

  // recoveryOutlook — optional

  // doctorKitSummary — optional non-empty string
  if (
    parsed.doctorKitSummary !== undefined &&
    (typeof parsed.doctorKitSummary !== 'string' || !parsed.doctorKitSummary.trim())
  ) {
    return err('doctorKitSummary must be a non-empty string when provided');
  }

  // doctorKitQuestions — 0 to 6 non-empty strings
  const doctorKitQuestions = normalizeStringArray(parsed.doctorKitQuestions).slice(0, 6);

  // doctorKitArguments — 0 to 6 non-empty strings
  const doctorKitArguments = normalizeStringArray(parsed.doctorKitArguments).slice(0, 6);

  const recommendedDoctors: RecommendedDoctor[] = [];
  for (const item of asObjectArray(parsed.recommendedDoctors).slice(0, 3)) {
    if (typeof item?.specialty !== 'string' || !item.specialty.trim())
      continue;
    if (typeof item?.priority !== 'string' || !item.priority.trim())
      continue;
    if (typeof item?.reason !== 'string' || !item.reason.trim())
      continue;
    const symptomsToDiscuss = normalizeStringArray(item?.symptomsToDiscuss);
    const suggestedTests = normalizeStringArray(item?.suggestedTests);
    recommendedDoctors.push({
      specialty: item.specialty.trim(),
      priority: item.priority.trim(),
      reason: item.reason.trim(),
      symptomsToDiscuss: symptomsToDiscuss.slice(0, 5),
      suggestedTests: suggestedTests.slice(0, 6),
    });
  }

  const doctorKits: DoctorKit[] = [];
  for (const item of asObjectArray(parsed.doctorKits).slice(0, 3)) {
    if (typeof item?.specialty !== 'string' || !item.specialty.trim())
      continue;
    if (typeof item?.openingSummary !== 'string' || !item.openingSummary.trim())
      continue;
    const concerningSymptoms = normalizeStringArray(item?.concerningSymptoms);
    const recommendedTests = normalizeStringArray(item?.recommendedTests);
    const discussionPoints = normalizeStringArray(item?.discussionPoints);
    const bringToAppointment = normalizeStringArray(item?.bringToAppointment);
    doctorKits.push({
      specialty: item.specialty.trim(),
      openingSummary: item.openingSummary.trim(),
      concerningSymptoms: concerningSymptoms.slice(0, 6),
      recommendedTests: recommendedTests.slice(0, 6),
      discussionPoints: discussionPoints.slice(0, 6),
      ...(bringToAppointment.length > 0 ? { bringToAppointment: bringToAppointment.slice(0, 6) } : {}),
      ...(typeof item?.whatToSay === 'string' && item.whatToSay.trim()
        ? { whatToSay: item.whatToSay.trim() }
        : {}),
    });
  }

  const declinedInput = asObjectArray(parsed.declinedSuspicions);
  const declinedSuspicions: DeclinedSuspicion[] = [];
  for (let i = 0; i < declinedInput.length; i++) {
    const item = declinedInput[i];
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      continue; // skip hallucinated ids rather than failing the whole response
    if (typeof item?.reason !== 'string' || !item.reason.trim())
      continue;
    declinedSuspicions.push({
      diagnosisId: item.diagnosisId,
      reason: item.reason.trim(),
    });
  }

  const recoveryOutlook =
    typeof parsed.recoveryOutlook === 'string' && parsed.recoveryOutlook.trim()
      ? parsed.recoveryOutlook.trim()
      : undefined;

  return {
    ok: true,
    data: {
      personalizedSummary: parsed.personalizedSummary.trim(),
      ...(summaryPoints.length > 0 ? { summaryPoints } : {}),
      insights,
      ...(declinedSuspicions.length > 0 ? { declinedSuspicions } : {}),
      ...(recoveryOutlook ? { recoveryOutlook } : {}),
      nextSteps: parsed.nextSteps.trim(),
      ...(typeof parsed.doctorKitSummary === 'string' && parsed.doctorKitSummary.trim()
        ? { doctorKitSummary: parsed.doctorKitSummary.trim() }
        : {}),
      doctorKitQuestions,
      doctorKitArguments,
      recommendedDoctors,
      doctorKits,
      ...(typeof parsed.allClear === 'boolean' ? { allClear: parsed.allClear } : {}),
    },
  };
}

// ── Hard safety rules ──────────────────────────────────────────────────────

/** Replacement text for any string containing a forbidden phrase. */
const SAFE_FALLBACK =
  'Based on your responses, this may be worth discussing with your GP.';
const EMERGENCY_SUMMARY_FALLBACK =
  'Some of the symptoms mentioned here can need urgent medical assessment, so it would be safest to seek care promptly today.';
const EMERGENCY_ACTION_FALLBACK =
  'Because some of the symptoms mentioned here can need urgent medical assessment, it would be safest to seek prompt medical review today rather than waiting.';

/**
 * Forbidden phrase patterns (case-insensitive, whole-word where applicable).
 * If any pattern matches a string field, the entire field is replaced with SAFE_FALLBACK
 * and a warning is recorded.
 */
const FORBIDDEN_PATTERNS: RegExp[] = [
  /\byou have\b/gi,
  /\byou are diagnosed\b/gi,
  /\byou suffer from\b/gi,
  /\byou definitely\b/gi,
  /\bcertain\b/gi,
  /\bconfirmed diagnosis\b/gi,
];

const FALSE_REASSURANCE_PATTERNS: RegExp[] = [
  /\bnothing serious\b/gi,
  /\bprobably nothing\b/gi,
  /\byou are fine\b/gi,
  /\bsafe to ignore\b/gi,
  /\bsafe to stay home\b/gi,
  /\bsafe to wait\b/gi,
  /\bstay home\b/gi,
  /\bignore this\b/gi,
  /\bwatch and see\b/gi,
  /\bwatchful waiting\b/gi,
  /\bno need to (?:see a doctor|seek care|talk to a doctor)\b/gi,
  /\bno need to worry\b/gi,
  /\bjust stress\b/gi,
  /\bjust getting older\b/gi,
  /\bnormal aging\b/gi,
  /\blikely benign\b/gi,
  /\bnot a big deal\b/gi,
  /\bnot(?: especially)? worrisome\b/gi,
  /\blow odds of anything major\b/gi,
  /\bhopefully nothing major\b/gi,
  /\bcan probably wait\b/gi,
  /\bcan likely hold off\b/gi,
  /\bnever need\b/gi,
  /\bwait a few weeks\b/gi,
  /\bwait a few months\b/gi,
  /\bwait a month\b/gi,
  /\bwait a year\b/gi,
];

const CHEST_SYMPTOM_PATTERNS: RegExp[] = [
  /\bchest pain\b/gi,
  /\bchest tightness\b/gi,
  /\bchest pressure\b/gi,
];

const BREATHING_SYMPTOM_PATTERNS: RegExp[] = [
  /\bbreathlessness\b/gi,
  /\bshortness of breath\b/gi,
];

const BLEEDING_SYMPTOM_PATTERNS: RegExp[] = [
  /\bblack stools?\b/gi,
];

const FAINTING_SYMPTOM_PATTERNS: RegExp[] = [
  /\bfaint(?:ing|ed)?\b/gi,
  /\bnear-faint(?:ing|ed)?\b/gi,
];

const LIVER_NEURO_SYMPTOM_PATTERNS: RegExp[] = [
  /\bjaundice\b/gi,
  /\bconfusion\b/gi,
];

const PALPITATION_PATTERNS: RegExp[] = [
  /\bpalpitations?\b/gi,
];

const WEAKNESS_SYMPTOM_PATTERNS: RegExp[] = [
  /\bweakness\b/gi,
  /\bmarked weakness\b/gi,
  /\bsevere fatigue\b/gi,
  /\bprofound fatigue\b/gi,
  /\bexhaustion\b/gi,
  /\bdizziness\b/gi,
];

const URGENCY_PATTERNS: RegExp[] = [
  /\burgent\b/gi,
  /\bprompt\b/gi,
  /\bsame day\b/gi,
  /\btoday\b/gi,
  /\bemergency\b/gi,
  /\bimmediate\b/gi,
];

function matchesAnyPattern(value: string, patterns: RegExp[]): RegExp | null {
  for (const pattern of patterns) {
    pattern.lastIndex = 0;
    if (pattern.test(value)) return pattern;
  }
  return null;
}

function flattenDeepAnalyzeStrings(data: DeepAnalyzeResult): string[] {
  const output: string[] = [
    data.personalizedSummary,
    data.nextSteps,
    ...data.insights.map((item) => item.personalNote),
    ...data.doctorKitQuestions,
    ...data.doctorKitArguments,
    ...data.recommendedDoctors.flatMap((doctor) => [
      doctor.reason,
      ...doctor.symptomsToDiscuss,
      ...doctor.suggestedTests,
    ]),
    ...data.doctorKits.flatMap((kit) => [
      kit.openingSummary,
      ...kit.concerningSymptoms,
      ...kit.recommendedTests,
      ...kit.discussionPoints,
      ...(kit.bringToAppointment ?? []),
      ...(kit.whatToSay ? [kit.whatToSay] : []),
    ]),
  ];
  if (data.summaryPoints) output.push(...data.summaryPoints);
  if (data.recoveryOutlook) output.push(data.recoveryOutlook);
  if (data.doctorKitSummary) output.push(data.doctorKitSummary);
  if (data.declinedSuspicions) output.push(...data.declinedSuspicions.map((item) => item.reason));
  return output;
}

function hasPatternInStrings(strings: string[], patterns: RegExp[]): boolean {
  return strings.some((value) => matchesAnyPattern(value, patterns));
}

function hasMustEscalateEmergencySignals(strings: string[]): boolean {
  const hasChest = hasPatternInStrings(strings, CHEST_SYMPTOM_PATTERNS);
  const hasBreathing = hasPatternInStrings(strings, BREATHING_SYMPTOM_PATTERNS);
  const hasBlackStools = hasPatternInStrings(strings, BLEEDING_SYMPTOM_PATTERNS);
  const hasFainting = hasPatternInStrings(strings, FAINTING_SYMPTOM_PATTERNS);
  const hasJaundiceOrConfusion = hasPatternInStrings(strings, LIVER_NEURO_SYMPTOM_PATTERNS);
  const hasPalpitations = hasPatternInStrings(strings, PALPITATION_PATTERNS);
  const hasWeaknessOrDizziness = hasPatternInStrings(strings, WEAKNESS_SYMPTOM_PATTERNS);

  return (
    hasFainting ||
    (hasChest && hasBreathing) ||
    (hasBlackStools && hasWeaknessOrDizziness) ||
    hasJaundiceOrConfusion ||
    (hasPalpitations && hasWeaknessOrDizziness)
  );
}

function hasUrgencyLanguage(strings: string[]): boolean {
  return strings.some((value) => matchesAnyPattern(value, URGENCY_PATTERNS));
}

function sanitizeString(
  value: string,
  warnings: string[],
  options?: { emergency?: boolean; preserveActionLanguage?: boolean },
): string {
  const diagnosticPattern = matchesAnyPattern(value, FORBIDDEN_PATTERNS);
  if (diagnosticPattern) {
    warnings.push(
      `[medgemma-safety] Replaced forbidden phrase (/${diagnosticPattern.source}/) in: "${value.slice(0, 100)}"`,
    );
    return options?.emergency
      ? options.preserveActionLanguage
        ? EMERGENCY_ACTION_FALLBACK
        : EMERGENCY_SUMMARY_FALLBACK
      : SAFE_FALLBACK;
  }

  const falseReassurancePattern = matchesAnyPattern(value, FALSE_REASSURANCE_PATTERNS);
  if (falseReassurancePattern) {
    warnings.push(
      `[medgemma-safety] Replaced dismissive phrase (/${falseReassurancePattern.source}/) in: "${value.slice(0, 100)}"`,
    );
    return options?.emergency
      ? options.preserveActionLanguage
        ? EMERGENCY_ACTION_FALLBACK
        : EMERGENCY_SUMMARY_FALLBACK
      : SAFE_FALLBACK;
  }

  return value;
}

export interface SafetyResult {
  data: DeepAnalyzeResult;
  /** Non-empty when at least one replacement was made. Log these as warnings. */
  warnings: string[];
}

interface SafetyOptions {
  allowedDiagnosisIds?: string[];
}

function filterDiagnosisItems<T extends { diagnosisId: string }>(
  items: T[] | undefined,
  allowedDiagnosisIds: Set<string> | null,
  warnings: string[],
  label: string,
): T[] | undefined {
  if (!items) return items;
  if (!allowedDiagnosisIds) return items;

  const filtered = items.filter((item) => allowedDiagnosisIds.has(item.diagnosisId));
  if (filtered.length !== items.length) {
    const removed = items
      .filter((item) => !allowedDiagnosisIds.has(item.diagnosisId))
      .map((item) => item.diagnosisId);
    warnings.push(
      `[medgemma-safety] Removed unsupported ${label}: ${removed.join(', ')}`,
    );
  }
  return filtered;
}

/**
 * Scans all string fields in the validated output for forbidden phrases
 * and replaces any offending field with SAFE_FALLBACK.
 *
 * Returns the sanitized data and a list of warning messages (empty if clean).
 */
export function applyHardSafetyRules(
  data: DeepAnalyzeResult,
  options: SafetyOptions = {},
): SafetyResult {
  const warnings: string[] = [];
  const allowedDiagnosisIds = options.allowedDiagnosisIds?.length
    ? new Set(options.allowedDiagnosisIds)
    : null;
  const mustEscalateEmergency = hasMustEscalateEmergencySignals(flattenDeepAnalyzeStrings(data));

  const filteredInsights = filterDiagnosisItems(data.insights, allowedDiagnosisIds, warnings, 'insight IDs') ?? [];
  const filteredDeclined = filterDiagnosisItems(
    data.declinedSuspicions,
    allowedDiagnosisIds,
    warnings,
    'declined suspicion IDs',
  );

  const sanitizedInsights = filteredInsights.map((item) => ({
    ...item,
    personalNote: sanitizeString(item.personalNote, warnings, { emergency: mustEscalateEmergency }),
  }));
  const sanitizedDeclined = filteredDeclined?.map((item) => ({
    ...item,
    reason: sanitizeString(item.reason, warnings, { emergency: mustEscalateEmergency }),
  }));

  const sanitized: DeepAnalyzeResult = {
    ...data,
    personalizedSummary: sanitizeString(data.personalizedSummary, warnings, { emergency: mustEscalateEmergency }),
    summaryPoints: data.summaryPoints?.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
    insights: sanitizedInsights,
    declinedSuspicions: sanitizedDeclined,
    recoveryOutlook: data.recoveryOutlook
      ? sanitizeString(data.recoveryOutlook, warnings, { emergency: mustEscalateEmergency })
      : data.recoveryOutlook,
    nextSteps: sanitizeString(data.nextSteps, warnings, { emergency: mustEscalateEmergency, preserveActionLanguage: true }),
    doctorKitSummary: data.doctorKitSummary
      ? sanitizeString(data.doctorKitSummary, warnings, { emergency: mustEscalateEmergency, preserveActionLanguage: mustEscalateEmergency })
      : data.doctorKitSummary,
    doctorKitQuestions: data.doctorKitQuestions.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
    doctorKitArguments: data.doctorKitArguments.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
    recommendedDoctors: data.recommendedDoctors.map((doctor) => ({
      ...doctor,
      reason: sanitizeString(doctor.reason, warnings, { emergency: mustEscalateEmergency }),
      symptomsToDiscuss: doctor.symptomsToDiscuss.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
      suggestedTests: doctor.suggestedTests.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
    })),
    doctorKits: data.doctorKits.map((kit) => ({
      ...kit,
      openingSummary: sanitizeString(kit.openingSummary, warnings, { emergency: mustEscalateEmergency, preserveActionLanguage: mustEscalateEmergency }),
      concerningSymptoms: kit.concerningSymptoms.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
      recommendedTests: kit.recommendedTests.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
      discussionPoints: kit.discussionPoints.map((item) => sanitizeString(item, warnings, { emergency: mustEscalateEmergency })),
      ...(kit.bringToAppointment
        ? {
            bringToAppointment: kit.bringToAppointment.map((item) =>
              sanitizeString(item, warnings, { emergency: mustEscalateEmergency }),
            ),
          }
        : {}),
      ...(kit.whatToSay
        ? {
            whatToSay: sanitizeString(kit.whatToSay, warnings, {
              emergency: mustEscalateEmergency,
              preserveActionLanguage: mustEscalateEmergency,
            }),
          }
        : {}),
    })),
  };

  if (mustEscalateEmergency && !hasUrgencyLanguage(flattenDeepAnalyzeStrings(sanitized))) {
    warnings.push('[medgemma-safety] Added urgent guidance for emergency symptom pattern');
    sanitized.personalizedSummary = EMERGENCY_SUMMARY_FALLBACK;
    sanitized.nextSteps = EMERGENCY_ACTION_FALLBACK;
    if (sanitized.doctorKitSummary) {
      sanitized.doctorKitSummary = EMERGENCY_ACTION_FALLBACK;
    }
    sanitized.doctorKits = sanitized.doctorKits.map((kit) => ({
      ...kit,
      openingSummary: EMERGENCY_ACTION_FALLBACK,
      ...(kit.whatToSay ? { whatToSay: EMERGENCY_ACTION_FALLBACK } : {}),
    }));
  }

  return { data: sanitized, warnings };
}
