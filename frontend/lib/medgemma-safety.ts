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

// ── Output schema types ────────────────────────────────────────────────────

export interface InsightItem {
  diagnosisId: string;
  personalNote: string;
}

export interface DeepAnalyzeResult {
  personalizedSummary: string;
  insights: InsightItem[];
  nextSteps: string;
  doctorKitSummary: string;
  doctorKitQuestions: [string, string];
  doctorKitArguments: [string, string];
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

  // doctorKitSummary — non-empty string
  if (typeof parsed.doctorKitSummary !== 'string' || !parsed.doctorKitSummary.trim())
    return err('doctorKitSummary must be a non-empty string');

  // doctorKitQuestions — 1 to 3 non-empty strings
  if (
    !Array.isArray(parsed.doctorKitQuestions) ||
    parsed.doctorKitQuestions.length < 1 ||
    parsed.doctorKitQuestions.length > 3
  )
    return err(
      `doctorKitQuestions must have between 1 and 3 items (got ${
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

  // doctorKitArguments — 1 to 3 non-empty strings
  if (
    !Array.isArray(parsed.doctorKitArguments) ||
    parsed.doctorKitArguments.length < 1 ||
    parsed.doctorKitArguments.length > 3
  )
    return err(
      `doctorKitArguments must have between 1 and 3 items (got ${
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
    doctorKitSummary: sanitizeString(data.doctorKitSummary, warnings),
    doctorKitQuestions: [
      sanitizeString(data.doctorKitQuestions[0], warnings),
      sanitizeString(data.doctorKitQuestions[1], warnings),
    ],
    doctorKitArguments: [
      sanitizeString(data.doctorKitArguments[0], warnings),
      sanitizeString(data.doctorKitArguments[1], warnings),
    ],
  };

  return { data: sanitized, warnings };
}
