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
  if (parsed.supportedSuspicions.length > 3)
    return err(`supportedSuspicions has ${parsed.supportedSuspicions.length} items — max 3`);

  for (let i = 0; i < parsed.supportedSuspicions.length; i++) {
    const item = parsed.supportedSuspicions[i] as Record<string, unknown>;
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      return err(`supportedSuspicions[${i}].diagnosisId "${String(item?.diagnosisId)}" not in allowlist`);
    if (!['probable', 'possible', 'worth_ruling_out'].includes(item?.confidence as string))
      return err(`supportedSuspicions[${i}].confidence must be probable | possible | worth_ruling_out`);
    if (typeof item?.anchorEvidence !== 'string' || !item.anchorEvidence.trim())
      return err(`supportedSuspicions[${i}].anchorEvidence must be a non-empty string`);
    if (typeof item?.reasoning !== 'string' || !item.reasoning.trim())
      return err(`supportedSuspicions[${i}].reasoning must be a non-empty string`);
    if (!Array.isArray(item?.keySymptoms) || item.keySymptoms.length < 1)
      return err(`supportedSuspicions[${i}].keySymptoms must be a non-empty array`);
    if (!Array.isArray(item?.recommendedTests) || item.recommendedTests.length < 1)
      return err(`supportedSuspicions[${i}].recommendedTests must be a non-empty array`);
  }

  if (!Array.isArray(parsed.declinedSuspicions))
    return err('declinedSuspicions must be an array');

  for (let i = 0; i < parsed.declinedSuspicions.length; i++) {
    const item = parsed.declinedSuspicions[i] as Record<string, unknown>;
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      return err(`declinedSuspicions[${i}].diagnosisId not in allowlist`);
    if (typeof item?.reason !== 'string' || !item.reason.trim())
      return err(`declinedSuspicions[${i}].reason must be a non-empty string`);
  }

  if (!Array.isArray(parsed.medicationFlags))
    return err('medicationFlags must be an array');

  if (!Array.isArray(parsed.recommendedSpecialties))
    return err('recommendedSpecialties must be an array');
  if (parsed.recommendedSpecialties.length > 3)
    return err(`recommendedSpecialties has ${parsed.recommendedSpecialties.length} items — max 3`);

  for (let i = 0; i < parsed.recommendedSpecialties.length; i++) {
    const item = parsed.recommendedSpecialties[i] as Record<string, unknown>;
    if (typeof item?.specialty !== 'string' || !item.specialty.trim())
      return err(`recommendedSpecialties[${i}].specialty must be a non-empty string`);
    if (typeof item?.priority !== 'string' || !item.priority.trim())
      return err(`recommendedSpecialties[${i}].priority must be a non-empty string`);
    if (typeof item?.clinicalReason !== 'string' || !item.clinicalReason.trim())
      return err(`recommendedSpecialties[${i}].clinicalReason must be a non-empty string`);
    if (!Array.isArray(item?.symptomsToRaise) || item.symptomsToRaise.length < 1)
      return err(`recommendedSpecialties[${i}].symptomsToRaise must be a non-empty array`);
    if (!Array.isArray(item?.testsToRequest) || item.testsToRequest.length < 1)
      return err(`recommendedSpecialties[${i}].testsToRequest must be a non-empty array`);
    if (!Array.isArray(item?.discussionPoints) || item.discussionPoints.length < 1)
      return err(`recommendedSpecialties[${i}].discussionPoints must be a non-empty array`);
  }

  return {
    ok: true,
    data: parsed as unknown as MedGemmaGroundingResult,
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

  // insights — array, 0–4 items, each with valid diagnosisId + non-empty personalNote
  if (!Array.isArray(parsed.insights))
    return err('insights must be an array');
  if (parsed.insights.length > 4)
    return err(`insights has ${parsed.insights.length} items — max is 4`);
  for (let i = 0; i < parsed.insights.length; i++) {
    const item = parsed.insights[i] as Record<string, unknown>;
    if (typeof item?.diagnosisId !== 'string' || !DIAGNOSIS_ID_ALLOWLIST.has(item.diagnosisId))
      return err(
        `insights[${i}].diagnosisId "${String(item?.diagnosisId)}" is not in the allowlist`,
      );
    if (typeof item?.personalNote !== 'string' || !item.personalNote.trim())
      return err(`insights[${i}].personalNote must be a non-empty string`);
  }

  // nextSteps — non-empty string
  if (typeof parsed.nextSteps !== 'string' || !parsed.nextSteps.trim())
    return err('nextSteps must be a non-empty string');

  // doctorKitSummary — optional non-empty string
  if (
    parsed.doctorKitSummary !== undefined &&
    (typeof parsed.doctorKitSummary !== 'string' || !parsed.doctorKitSummary.trim())
  ) {
    return err('doctorKitSummary must be a non-empty string when provided');
  }

  // doctorKitQuestions — 0 to 6 non-empty strings
  if (
    !Array.isArray(parsed.doctorKitQuestions) ||
    parsed.doctorKitQuestions.length > 6
  )
    return err(
      `doctorKitQuestions must have between 0 and 6 items (got ${
        Array.isArray(parsed.doctorKitQuestions)
          ? parsed.doctorKitQuestions.length
          : typeof parsed.doctorKitQuestions
      })`,
    );
  for (let i = 0; i < parsed.doctorKitQuestions.length; i++) {
    if (
      typeof parsed.doctorKitQuestions[i] !== 'string' ||
      !(parsed.doctorKitQuestions[i] as string).trim()
    )
      return err(`doctorKitQuestions[${i}] must be a non-empty string`);
  }

  // doctorKitArguments — 0 to 6 non-empty strings
  if (
    !Array.isArray(parsed.doctorKitArguments) ||
    parsed.doctorKitArguments.length > 6
  )
    return err(
      `doctorKitArguments must have between 0 and 6 items (got ${
        Array.isArray(parsed.doctorKitArguments)
          ? parsed.doctorKitArguments.length
          : typeof parsed.doctorKitArguments
      })`,
    );
  for (let i = 0; i < parsed.doctorKitArguments.length; i++) {
    if (
      typeof parsed.doctorKitArguments[i] !== 'string' ||
      !(parsed.doctorKitArguments[i] as string).trim()
    )
      return err(`doctorKitArguments[${i}] must be a non-empty string`);
  }

  if (!Array.isArray(parsed.recommendedDoctors))
    return err('recommendedDoctors must be an array');
  if (parsed.recommendedDoctors.length > 3)
    return err(`recommendedDoctors has ${parsed.recommendedDoctors.length} items — max is 3`);
  for (let i = 0; i < parsed.recommendedDoctors.length; i++) {
    const item = parsed.recommendedDoctors[i] as Record<string, unknown>;
    if (typeof item?.specialty !== 'string' || !item.specialty.trim())
      return err(`recommendedDoctors[${i}].specialty must be a non-empty string`);
    if (typeof item?.priority !== 'string' || !item.priority.trim())
      return err(`recommendedDoctors[${i}].priority must be a non-empty string`);
    if (typeof item?.reason !== 'string' || !item.reason.trim())
      return err(`recommendedDoctors[${i}].reason must be a non-empty string`);
    if (!Array.isArray(item?.symptomsToDiscuss) || item.symptomsToDiscuss.length < 1 || item.symptomsToDiscuss.length > 5)
      return err(`recommendedDoctors[${i}].symptomsToDiscuss must have between 1 and 5 items`);
    if (!Array.isArray(item?.suggestedTests) || item.suggestedTests.length < 1 || item.suggestedTests.length > 6)
      return err(`recommendedDoctors[${i}].suggestedTests must have between 1 and 6 items`);
  }

  if (!Array.isArray(parsed.doctorKits))
    return err('doctorKits must be an array');
  if (parsed.doctorKits.length > 3)
    return err(`doctorKits has ${parsed.doctorKits.length} items — max is 3`);
  for (let i = 0; i < parsed.doctorKits.length; i++) {
    const item = parsed.doctorKits[i] as Record<string, unknown>;
    if (typeof item?.specialty !== 'string' || !item.specialty.trim())
      return err(`doctorKits[${i}].specialty must be a non-empty string`);
    if (typeof item?.openingSummary !== 'string' || !item.openingSummary.trim())
      return err(`doctorKits[${i}].openingSummary must be a non-empty string`);
    if (!Array.isArray(item?.concerningSymptoms) || item.concerningSymptoms.length < 1 || item.concerningSymptoms.length > 6)
      return err(`doctorKits[${i}].concerningSymptoms must have between 1 and 6 items`);
    if (!Array.isArray(item?.recommendedTests) || item.recommendedTests.length < 1 || item.recommendedTests.length > 6)
      return err(`doctorKits[${i}].recommendedTests must have between 1 and 6 items`);
    if (!Array.isArray(item?.discussionPoints) || item.discussionPoints.length < 2 || item.discussionPoints.length > 6)
      return err(`doctorKits[${i}].discussionPoints must have between 2 and 6 items`);
  }

  return { ok: true, data: parsed as unknown as DeepAnalyzeResult };
}

// ── Hard safety rules ──────────────────────────────────────────────────────

/** Replacement text for any string containing a forbidden phrase. */
const SAFE_FALLBACK =
  'Based on your responses, this may be worth discussing with your GP.';

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

function sanitizeString(value: string, warnings: string[]): string {
  for (const pattern of FORBIDDEN_PATTERNS) {
    // Reset lastIndex for global patterns between calls
    pattern.lastIndex = 0;
    if (pattern.test(value)) {
      warnings.push(
        `[medgemma-safety] Replaced forbidden phrase (/${pattern.source}/) in: "${value.slice(0, 100)}"`,
      );
      return SAFE_FALLBACK;
    }
  }
  return value;
}

export interface SafetyResult {
  data: DeepAnalyzeResult;
  /** Non-empty when at least one replacement was made. Log these as warnings. */
  warnings: string[];
}

/**
 * Scans all string fields in the validated output for forbidden phrases
 * and replaces any offending field with SAFE_FALLBACK.
 *
 * Returns the sanitized data and a list of warning messages (empty if clean).
 */
export function applyHardSafetyRules(data: DeepAnalyzeResult): SafetyResult {
  const warnings: string[] = [];

  const sanitized: DeepAnalyzeResult = {
    ...data,
    personalizedSummary: sanitizeString(data.personalizedSummary, warnings),
    insights: data.insights.map((item) => ({
      ...item,
      personalNote: sanitizeString(item.personalNote, warnings),
    })),
    nextSteps:       sanitizeString(data.nextSteps, warnings),
    doctorKitSummary: data.doctorKitSummary
      ? sanitizeString(data.doctorKitSummary, warnings)
      : data.doctorKitSummary,
    doctorKitQuestions: data.doctorKitQuestions.map((item) => sanitizeString(item, warnings)),
    doctorKitArguments: data.doctorKitArguments.map((item) => sanitizeString(item, warnings)),
    recommendedDoctors: data.recommendedDoctors.map((doctor) => ({
      ...doctor,
      reason: sanitizeString(doctor.reason, warnings),
      symptomsToDiscuss: doctor.symptomsToDiscuss.map((item) => sanitizeString(item, warnings)),
      suggestedTests: doctor.suggestedTests.map((item) => sanitizeString(item, warnings)),
    })),
    doctorKits: data.doctorKits.map((kit) => ({
      ...kit,
      openingSummary: sanitizeString(kit.openingSummary, warnings),
      concerningSymptoms: kit.concerningSymptoms.map((item) => sanitizeString(item, warnings)),
      recommendedTests: kit.recommendedTests.map((item) => sanitizeString(item, warnings)),
      discussionPoints: kit.discussionPoints.map((item) => sanitizeString(item, warnings)),
    })),
  };

  return { data: sanitized, warnings };
}
